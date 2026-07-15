"""AI Fleet Copilot — structured tool calls with RAG grounding + LLM fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from disruption_agent import DisruptionAgent
from fleet_optimizer import FleetOptimizer
from fleet_store import FleetStore
from rag_store import RagStore


class FleetCopilot:
    TOOL_DEFINITIONS = [
        {"name": "optimize_fleet", "description": "Generate Economy, Green, and Service route plans"},
        {"name": "compare_plans", "description": "Compare candidate plans by score"},
        {"name": "simulate_breakdown", "description": "Simulate vehicle breakdown"},
        {"name": "insert_urgent_order", "description": "Add urgent delivery order"},
        {"name": "apply_road_penalty", "description": "Simulate road blockage near coordinates"},
        {"name": "get_at_risk_deliveries", "description": "List at-risk deliveries"},
        {"name": "generate_recovery", "description": "Generate recovery plans after disruption"},
        {"name": "apply_recovery_plan", "description": "Apply a selected recovery plan"},
        {"name": "generate_impact_summary", "description": "Summarize operational and sustainability impact"},
        {"name": "explain_active_plan", "description": "Explain the currently active fleet plan"},
        {"name": "rag_retrieve", "description": "Retrieve grounded knowledge + live fleet facts"},
    ]

    def __init__(
        self,
        store: FleetStore | None = None,
        disruption: DisruptionAgent | None = None,
        rag: RagStore | None = None,
    ) -> None:
        self.store = store or FleetStore()
        self.disruption = disruption or DisruptionAgent(self.store)
        self.optimizer = FleetOptimizer()
        self.rag = rag or RagStore()

    def answer_help(self, message: str) -> dict[str, Any]:
        """RAG-first help path for the floating Sky Assistant (non-mutating)."""
        msg = message.strip().lower()
        greetings = {"hi", "hello", "hey", "yo", "salam", "hola", "help"}
        if msg in greetings or msg.rstrip("!") in greetings:
            return {
                "message": message,
                "reply": (
                    "Hey — I'm Sky Assistant. Ask about the demo loop, Economy/Green/Service modes, "
                    "breakdown recovery, carbon estimates, or how to open Control Tower.\n\n"
                    "Tip: on Login, use Continue as Demo Operator, then press ▶ Run guided demo."
                ),
                "rag": {"sources": [], "chunk_count": len(self.rag.chunks)},
                "tool_calls": [{"tool": "rag_retrieve", "result": {"sources": 0}}],
                "mode": "help",
            }
        ctx = self.rag.build_context(message, self.store, top_k=4)
        grounded = self._grounded_answer(message, ctx)
        return {
            "message": message,
            "reply": grounded,
            "rag": {
                "sources": [{"id": d["id"], "source": d["source"], "score": d["score"]} for d in ctx["retrieved"]],
                "chunk_count": ctx["chunk_count"],
            },
            "tool_calls": [{"tool": "rag_retrieve", "result": {"sources": len(ctx["retrieved"])}}],
            "mode": "help",
        }

    def process_message(
        self,
        message: str,
        confirm_action: bool = False,
        pending_action: str | None = None,
        allow_mutations: bool = True,
    ) -> dict[str, Any]:
        msg = message.strip().lower()
        tool_calls: list[dict[str, Any]] = []
        reply_parts: list[str] = []
        rag_meta = None

        help_signals = ("how do", "what is", "what are", "explain mode", "faq", "help", "demo loop", "judge", "rag")
        if any(s in msg for s in help_signals) and not any(
            s in msg for s in ("breakdown", "optimize", "recovery", "apply plan", "urgent")
        ):
            help_resp = self.answer_help(message)
            return {
                **help_resp,
                "tools_available": [t["name"] for t in self.TOOL_DEFINITIONS],
                "pending_confirmation": None,
            }

        if confirm_action and allow_mutations:
            action = (pending_action or "").strip().lower()
            if action == "apply_plan" or ("apply" in msg and "plan" in msg):
                plans = self.store.get_state().get("candidate_plans", [])
                if plans:
                    pid = plans[0]["id"]
                    applied = self.disruption.apply_recovery_plan(pid, auto=False)
                    tool_calls.append({"tool": "apply_recovery_plan", "result": applied})
                    reply_parts.append(f"Confirmed: applied plan {pid}.")
                    return self._response(message, reply_parts, tool_calls)
            result = self.disruption.simulate_breakdown(self._extract_vehicle_id(msg))
            recovery = self.disruption.generate_recovery_plans("breakdown")
            tool_calls.extend([
                {"tool": "simulate_breakdown", "result": result},
                {"tool": "generate_recovery", "result": recovery},
            ])
            reply_parts.append(
                f"Confirmed: breakdown on {result.get('vehicle_id')}. "
                f"{len(result.get('affected_orders', []))} orders affected. "
                f"Recovery recommendation: plan {recovery.get('recommended_plan_id')}."
            )
            return self._response(message, reply_parts, tool_calls)

        if any(k in msg for k in ("optimize", "plan", "route")) and not ("explain" in msg or "why" in msg):
            if not allow_mutations:
                return self.answer_help(message)
            result = self._tool_optimize_fleet(msg)
            tool_calls.append({"tool": "optimize_fleet", "result": result})
            best = result["plans"][0] if result.get("plans") else None
            if best:
                reply_parts.append(
                    f"Generated 3 plans. Recommended: **{best.get('label')}** — "
                    f"{best.get('deliveries_assigned', 0)} deliveries, "
                    f"{best.get('total_co2_kg', 0)} kg est. CO₂e, PKR {best.get('total_operating_cost_pkr', 0)}."
                )

        elif "breakdown" in msg or "break down" in msg:
            if not allow_mutations:
                return self.answer_help(message)
            vid = self._extract_vehicle_id(msg) or "auto"
            reply_parts.append(
                f"I can simulate a breakdown ({vid}). Confirm to proceed and auto-generate recovery plans."
            )
            return self._response(message, reply_parts, tool_calls, pending_confirmation="breakdown")

        elif "urgent" in msg or "emergency order" in msg:
            reply_parts.append(
                "Urgent order insertion: use Event Center or POST /api/fleet/events with type urgent_order."
            )

        elif "at risk" in msg or "at-risk" in msg:
            at_risk = self.store.get_at_risk_deliveries()
            tool_calls.append({"tool": "get_at_risk_deliveries", "result": at_risk})
            reply_parts.append(
                f"{len(at_risk)} deliveries at risk: {', '.join(o['id'] for o in at_risk) or 'none'}."
            )

        elif "recovery" in msg or "recover" in msg:
            if not allow_mutations:
                return self.answer_help(message)
            result = self.disruption.generate_recovery_plans("copilot_request")
            tool_calls.append({"tool": "generate_recovery", "result": result})
            reply_parts.append(result.get("explanation", "Recovery plans generated."))

        elif "apply" in msg and "plan" in msg:
            plans = self.store.get_state().get("candidate_plans", [])
            if not plans:
                reply_parts.append("No candidate plans available. Run optimize or recovery first.")
            elif not allow_mutations:
                reply_parts.append("Plan apply requires Control Tower session actions.")
            else:
                reply_parts.append(
                    f"Confirm to apply recommended plan {plans[0]['id']} ({plans[0].get('label')})."
                )
                return self._response(message, reply_parts, tool_calls, pending_confirmation="apply_plan")

        elif "impact" in msg or "summary" in msg or "report" in msg:
            summary = self.store.get_impact_summary()
            tool_calls.append({"tool": "generate_impact_summary", "result": summary})
            reply_parts.append(
                f"Impact: {summary['km_planned']} km planned, "
                f"{summary['estimated_co2_kg']} kg est. CO₂e, "
                f"{summary['disruptions_resolved']} disruptions handled, "
                f"{summary['agent_actions']} agent decisions logged."
            )

        elif "why" in msg or "explain" in msg:
            explanation = self._tool_explain_active_plan()
            tool_calls.append({"tool": "explain_active_plan", "result": explanation})
            ctx = self.rag.build_context(message, self.store, top_k=2)
            rag_meta = {"sources": [d["source"] for d in ctx["retrieved"]]}
            reply_parts.append(explanation.get("text", "No active plan to explain."))
            if ctx["retrieved"]:
                reply_parts.append("Grounded note: " + ctx["retrieved"][0]["text"][:220] + "…")

        elif "greener" in msg or "green alternative" in msg:
            if not allow_mutations:
                return self.answer_help(message)
            state = self.store.get_state()
            plan = self.optimizer.optimize_fleet(
                state["depot"], state["vehicles"], state["orders"], mode="green"
            )
            tool_calls.append({"tool": "optimize_fleet", "result": {"plans": [plan]}})
            reply_parts.append(
                f"Green alternative: {plan.get('total_co2_kg', 0)} kg CO₂e (est.), "
                f"{plan.get('deliveries_assigned', 0)} deliveries, score {plan.get('score')}."
            )

        else:
            help_resp = self.answer_help(message)
            return {
                **help_resp,
                "tools_available": [t["name"] for t in self.TOOL_DEFINITIONS],
                "pending_confirmation": None,
            }

        if not reply_parts:
            help_resp = self.answer_help(message)
            return {
                **help_resp,
                "tools_available": [t["name"] for t in self.TOOL_DEFINITIONS],
                "pending_confirmation": None,
            }

        resp = self._response(message, reply_parts, tool_calls)
        if rag_meta:
            resp["rag"] = rag_meta
        return resp

    def _grounded_answer(self, message: str, ctx: dict[str, Any]) -> str:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                return self._call_gemini_rag(message, ctx["context_text"], api_key)
            except Exception:
                pass
        if not ctx["retrieved"] and not ctx.get("live_snapshot"):
            return (
                "I don't have a matching knowledge chunk yet. Try asking about the demo loop, "
                "planning modes, breakdown recovery, or carbon estimates."
            )
        bits = []
        if ctx.get("live_snapshot"):
            live_lines = [ln for ln in ctx["live_snapshot"].splitlines() if ln.startswith("-")][:4]
            if live_lines:
                bits.append("Live state:\n" + "\n".join(live_lines))
        for doc in ctx["retrieved"][:2]:
            body = doc["text"]
            lines = body.splitlines()
            content = "\n".join(lines[1:] if lines and lines[0].startswith("#") else lines)
            bits.append(content.strip()[:420])
        sources = ", ".join(sorted({d["source"] for d in ctx["retrieved"]})) or "live state"
        return ("\n\n".join(bits) + f"\n\n— Retrieved from: {sources}").strip()

    def _tool_optimize_fleet(self, msg: str) -> dict[str, Any]:
        state = self.store.get_state()
        plans = self.optimizer.generate_all_modes(state["depot"], state["vehicles"], state["orders"])
        ranked = self.optimizer.compare_plans(plans)
        self.store.set_candidate_plans(ranked)
        best = ranked[0] if ranked else None
        if best:
            self.store.log_decision(
                trigger="initial_optimization" if "initial" in msg else "copilot_optimize",
                alternatives=[{k: p.get(k) for k in ("id", "mode", "score", "total_co2_kg")} for p in ranked],
                selected=best,
                explanation=f"Copilot requested optimization; recommended {best.get('label')}.",
            )
        return {"plans": ranked, "recommended_plan_id": best.get("id") if best else None}

    def _tool_explain_active_plan(self) -> dict[str, Any]:
        state = self.store.get_state()
        plan = state.get("active_plan")
        decisions = state.get("decisions", [])
        if not plan:
            return {"text": "No active plan applied yet. Run optimization and apply a plan first."}
        last = decisions[-1] if decisions else None
        text = (
            f"Active plan: {plan.get('label', plan.get('id'))}. "
            f"{plan.get('deliveries_assigned', 0)} deliveries across {len(plan.get('vehicle_routes', []))} vehicles. "
            f"Estimated {plan.get('total_co2_kg', 0)} kg CO₂e and PKR {plan.get('total_operating_cost_pkr', 0)} operating cost."
        )
        if last:
            text += f" Last agent decision: {last.get('explanation', '')}"
        return {"text": text, "plan": plan, "last_decision": last}

    def _extract_vehicle_id(self, msg: str) -> str | None:
        for token in msg.upper().split():
            if token.startswith("V") and token[1:].isdigit():
                return token
        return None

    def _call_gemini_rag(self, message: str, context: str, api_key: str) -> str:
        import urllib.request

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={api_key}"
        )
        prompt = (
            "You are Sky.EcoAI assistant. Answer ONLY using the retrieved context. "
            "If context is insufficient, say what the operator should try next. Be concise.\n\n"
            f"CONTEXT:\n{context[:6000]}\n\nUSER: {message}"
        )
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _response(
        self,
        message: str,
        reply_parts: list[str],
        tool_calls: list[dict[str, Any]],
        pending_confirmation: str | None = None,
    ) -> dict[str, Any]:
        return {
            "message": message,
            "reply": " ".join(reply_parts),
            "tool_calls": tool_calls,
            "tools_available": [t["name"] for t in self.TOOL_DEFINITIONS],
            "pending_confirmation": pending_confirmation,
        }
