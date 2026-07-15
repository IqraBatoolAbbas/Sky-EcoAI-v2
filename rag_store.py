"""Lightweight in-process RAG over knowledge docs + live fleet facts (no vector DB required)."""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from typing import Any

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class RagStore:
    """TF-IDF retrieval over markdown chunks for Fleet Copilot / Help Assistant."""

    def __init__(self) -> None:
        self.chunks: list[dict[str, Any]] = []
        self._df: Counter[str] = Counter()
        self._load()

    def _load(self) -> None:
        self.chunks = []
        if not os.path.isdir(KNOWLEDGE_DIR):
            return
        for name in sorted(os.listdir(KNOWLEDGE_DIR)):
            if not name.endswith((".md", ".txt")):
                continue
            path = os.path.join(KNOWLEDGE_DIR, name)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            # Split on ## headings or blank-line paragraphs
            parts = re.split(r"\n(?=##\s)", text) if "## " in text else text.split("\n\n")
            for i, part in enumerate(parts):
                part = part.strip()
                if len(part) < 40:
                    continue
                tokens = _tokenize(part)
                self.chunks.append(
                    {
                        "id": f"{name}#{i}",
                        "source": name,
                        "text": part,
                        "tokens": tokens,
                        "tf": Counter(tokens),
                    }
                )
        self._df = Counter()
        for chunk in self.chunks:
            for term in set(chunk["tokens"]):
                self._df[term] += 1

    def reload(self) -> int:
        self._load()
        return len(self.chunks)

    def _score(self, query_tokens: list[str], chunk: dict[str, Any]) -> float:
        if not query_tokens or not chunk["tokens"]:
            return 0.0
        n = len(self.chunks) or 1
        score = 0.0
        tf = chunk["tf"]
        length = len(chunk["tokens"])
        for term in query_tokens:
            if term not in tf:
                continue
            idf = math.log((n + 1) / (1 + self._df.get(term, 0))) + 1
            score += (tf[term] / length) * idf
        # Boost if query terms appear in source name
        source_boost = sum(1 for t in query_tokens if t in chunk["source"].lower()) * 0.05
        # Prefer heading / opening lines matching the query
        head = " ".join(chunk["text"].splitlines()[:2]).lower()
        head_hits = sum(1 for t in query_tokens if len(t) > 3 and t in head) * 0.08
        return score + source_boost + head_hits

    def retrieve(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        q_tokens = _tokenize(query)
        ranked = sorted(
            (
                {
                    "id": c["id"],
                    "source": c["source"],
                    "text": c["text"][:900],
                    "score": round(self._score(q_tokens, c), 4),
                }
                for c in self.chunks
            ),
            key=lambda x: x["score"],
            reverse=True,
        )
        return [r for r in ranked if r["score"] > 0][:top_k]

    def live_fleet_facts(self, store: Any) -> str:
        """Inject current operational state as retrieval context."""
        try:
            dash = store.get_dashboard()
            k = dash.get("kpis", {})
            decisions = store.get_decisions()[-3:]
            at_risk = store.get_at_risk_deliveries()
            lines = [
                "## Live fleet snapshot",
                f"- Active vehicles: {k.get('active_vehicles')}, broken: {k.get('broken_vehicles')}",
                f"- Pending orders: {k.get('pending_orders')}, at-risk: {k.get('at_risk_orders')}",
                f"- Est. CO2e: {k.get('total_co2_kg')} kg / budget {k.get('carbon_budget_kg')} kg "
                f"({k.get('carbon_budget_used_pct')}%)",
                f"- Operating cost: PKR {k.get('total_cost_pkr')}, distance: {k.get('total_distance_km')} km",
            ]
            if at_risk:
                lines.append("- At-risk deliveries: " + ", ".join(o["id"] for o in at_risk))
            if decisions:
                lines.append("- Recent agent decisions:")
                for d in decisions:
                    lines.append(f"  • {d.get('trigger')}: {d.get('explanation', '')[:160]}")
            return "\n".join(lines)
        except Exception as exc:
            return f"## Live fleet snapshot\nUnavailable ({exc})"

    def build_context(self, query: str, store: Any | None = None, top_k: int = 4) -> dict[str, Any]:
        docs = self.retrieve(query, top_k=top_k)
        live = self.live_fleet_facts(store) if store is not None else ""
        blocks = []
        if live:
            blocks.append(live)
        for d in docs:
            blocks.append(f"### Source: {d['source']}\n{d['text']}")
        return {
            "retrieved": docs,
            "live_snapshot": live,
            "context_text": "\n\n".join(blocks),
            "chunk_count": len(self.chunks),
        }
