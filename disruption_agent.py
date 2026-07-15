"""Disruption simulation and autonomous recovery planning."""

from __future__ import annotations

from typing import Any

from carbon_cost_engine import compare_plans
from fleet_optimizer import FleetOptimizer
from fleet_store import FleetStore


class DisruptionAgent:
    def __init__(self, store: FleetStore | None = None) -> None:
        self.store = store or FleetStore()
        self.optimizer = FleetOptimizer()

    def simulate_breakdown(self, vehicle_id: str | None = None) -> dict[str, Any]:
        state = self.store.get_state()
        if not vehicle_id:
            # Prefer a vehicle that currently carries assigned deliveries
            assigned_counts: dict[str, int] = {}
            for o in state["orders"]:
                vid = o.get("assigned_vehicle")
                if vid and o.get("status") in ("assigned", "in_transit"):
                    assigned_counts[vid] = assigned_counts.get(vid, 0) + 1
            if assigned_counts:
                vehicle_id = max(assigned_counts, key=assigned_counts.get)
            else:
                active = [v["id"] for v in state["vehicles"] if v.get("status") == "active"]
                vehicle_id = active[0] if active else "V1"

        result = self.store.mark_vehicle_breakdown(vehicle_id)
        event = self.store.log_event(
            "breakdown",
            {"vehicle_id": vehicle_id, "affected_orders": result["affected_orders"]},
        )
        return {"event": event, **result}

    def insert_urgent_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order = self.store.add_order(
            {
                **payload,
                "priority": "high",
                "status": "at_risk",
                "deadline_minutes": payload.get("deadline_minutes", 60),
            }
        )
        event = self.store.log_event("urgent_order", {"order_id": order["id"], "customer": order["customer"]})
        return {"event": event, "order": order}

    def apply_road_penalty(self, lat: float, lng: float, radius_km: float = 2.0) -> dict[str, Any]:
        result = self.store.apply_road_penalty(lat, lng, radius_km)
        event = self.store.log_event(
            "road_blockage",
            {"lat": lat, "lng": lng, "radius_km": radius_km, "affected_orders": result["affected_orders"]},
        )
        return {"event": event, **result}

    def simulate_range_warning(self, vehicle_id: str) -> dict[str, Any]:
        result = self.store.mark_low_range(vehicle_id)
        event = self.store.log_event(
            "range_warning",
            {"vehicle_id": vehicle_id, "affected_orders": result["affected_orders"]},
        )
        return {"event": event, **result}

    def generate_recovery_plans(self, trigger: str = "disruption") -> dict[str, Any]:
        state = self.store.get_state()
        at_risk = self.store.get_at_risk_deliveries()
        pending = [o for o in state["orders"] if o.get("status") in ("pending", "at_risk", "assigned")]

        plans = self.optimizer.generate_all_modes(state["depot"], state["vehicles"], state["orders"])

        # Recovery-specific: boost service mode ranking when many at-risk
        if len(at_risk) >= 2:
            for p in plans:
                if p["mode"] == "service":
                    p["score"] = round(p["score"] * 0.85, 2)
                    p["recovery_recommended"] = True

        ranked = compare_plans(plans)
        self.store.set_candidate_plans(ranked)

        best = ranked[0] if ranked else None
        explanation = self._build_explanation(trigger, ranked, at_risk)

        if best:
            decision = self.store.log_decision(
                trigger=trigger,
                alternatives=[{k: p.get(k) for k in ("id", "mode", "label", "score", "total_co2_kg", "total_operating_cost_pkr", "unassigned_orders")} for p in ranked],
                selected=best,
                explanation=explanation,
                approval_status="pending",
            )
        else:
            decision = None

        return {
            "recovery_plans": ranked,
            "recommended_plan_id": best.get("id") if best else None,
            "at_risk_orders": [o["id"] for o in at_risk],
            "pending_orders": len(pending),
            "decision": decision,
            "explanation": explanation,
        }

    def apply_recovery_plan(self, plan_id: str, auto: bool = False) -> dict[str, Any]:
        plan = self.store.apply_plan(plan_id)
        explanation = (
            f"Applied {plan.get('label', plan_id)}: {plan.get('deliveries_assigned', 0)} deliveries assigned, "
            f"estimated {plan.get('total_co2_kg', 0)} kg CO₂e, PKR {plan.get('total_operating_cost_pkr', 0)} operating cost."
        )
        decision = self.store.log_decision(
            trigger="recovery_applied",
            alternatives=[],
            selected=plan,
            explanation=explanation,
            approval_status="auto_applied" if auto else "approved",
        )
        self.store.log_event("recovery_applied", {"plan_id": plan_id, "auto": auto})
        delta = self.store.compute_delta(plan)
        return {"plan": plan, "decision": decision, "delta": delta}

    def run_scenario(self, scenario: str) -> dict[str, Any]:
        """One-click judge scenarios."""
        key = (scenario or "").strip().lower().replace("-", "_").replace(" ", "_")
        state = self.store.get_state()

        if key in ("medical_rush", "medical"):
            result = self.insert_urgent_order(
                {
                    "customer": "Emergency trauma pack — Shaukat Khanum",
                    "lat": 31.5620,
                    "lng": 74.3300,
                    "weight_kg": 35,
                    "deadline_minutes": 35,
                    "priority": "high",
                }
            )
            self.store.log_event("scenario", {"scenario": "medical_rush"})
            return {"scenario": "medical_rush", "title": "Medical rush", "result": result}

        if key in ("carbon_budget_breach", "carbon", "carbon_breach"):
            # Tighten budget below current/active plan emissions so Overview flags breach
            active = state.get("active_plan") or {}
            current = float(active.get("total_co2_kg") or 12)
            budget = round(max(1.0, current * 0.55), 2)
            new_budget = self.store.set_carbon_budget(budget)
            event = self.store.log_event(
                "carbon_budget_breach",
                {"carbon_budget_kg": new_budget, "active_co2_kg": current},
            )
            return {
                "scenario": "carbon_budget_breach",
                "title": "Carbon-budget breach",
                "result": {"carbon_budget_kg": new_budget, "active_co2_kg": current, "event": event},
            }

        if key in ("ev_low_range", "ev_range", "low_range"):
            # Prefer an electric vehicle that currently has assignments
            assigned = {}
            for o in state.get("orders", []):
                vid = o.get("assigned_vehicle")
                if vid:
                    assigned[vid] = assigned.get(vid, 0) + 1
            evs = [v for v in state.get("vehicles", []) if v.get("engine_type") == "electric"]
            pick = None
            for v in sorted(evs, key=lambda x: assigned.get(x["id"], 0), reverse=True):
                pick = v["id"]
                break
            pick = pick or "V6"
            result = self.simulate_range_warning(pick)
            self.store.log_event("scenario", {"scenario": "ev_low_range", "vehicle_id": pick})
            return {"scenario": "ev_low_range", "title": "EV low range", "result": result}

        raise ValueError(f"Unknown scenario: {scenario}")

    def _build_explanation(self, trigger: str, plans: list[dict[str, Any]], at_risk: list[dict]) -> str:
        if not plans:
            return "No feasible recovery plan could be generated with available vehicles."
        best = plans[0]
        alt_count = len(plans) - 1
        risk_note = f"{len(at_risk)} deliveries were at risk after {trigger.replace('_', ' ')}."
        mode_note = f"Selected {best.get('label')} (mode={best.get('mode')}) with score {best.get('score')}."
        impact = (
            f"Covers {best.get('deliveries_assigned', 0)} stops, "
            f"estimated {best.get('total_co2_kg', 0)} kg CO₂e, "
            f"PKR {best.get('total_operating_cost_pkr', 0)} cost."
        )
        if best.get("unassigned_orders"):
            impact += f" Warning: {len(best['unassigned_orders'])} orders remain unassigned."
        return f"{risk_note} Evaluated {len(plans)} alternatives ({alt_count} others). {mode_note} {impact}"
