"""Persistent fleet state: vehicles, orders, plans, events, and agent decisions."""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STATE_PATH = os.path.join(DATA_DIR, "fleet_state.json")
SEED_PATH = os.path.join(DATA_DIR, "lahore_demo.json")


def _bounded_number(value: Any, field: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return number


def _clean_label(value: Any, field: str, default: str) -> str:
    label = str(value or default).strip()
    if not 1 <= len(label) <= 100:
        raise ValueError(f"{field} must be between 1 and 100 characters.")
    return label


class FleetStore:
    def __init__(self, state_path: str = STATE_PATH, seed_path: str = SEED_PATH) -> None:
        self._lock = Lock()
        self.state_path = state_path
        self.seed_path = seed_path
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        if not os.path.exists(self.state_path):
            self.reset_demo()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> dict[str, Any]:
        with open(self.state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, state: dict[str, Any]) -> None:
        temp_path = f"{self.state_path}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.state_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def reset_demo(self) -> dict[str, Any]:
        with self._lock:
            with open(self.seed_path, "r", encoding="utf-8") as f:
                seed = json.load(f)
            state = {
                **copy.deepcopy(seed),
                "active_plan": None,
                "candidate_plans": [],
                "events": [],
                "decisions": [],
                "disruptions": [],
                "baseline_snapshot": None,
                "latest_delta": None,
                "activity_log": [],
                "alerts_outbox": [],
                "enforce_carbon_budget": True,
                "updated_at": self._now(),
            }
            self._write(state)
            return state

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def get_dashboard(self) -> dict[str, Any]:
        state = self.get_state()
        vehicles = state.get("vehicles", [])
        orders = state.get("orders", [])
        active = state.get("active_plan") or {}

        active_vehicles = sum(1 for v in vehicles if v.get("status") == "active")
        broken = sum(1 for v in vehicles if v.get("status") == "breakdown")
        delivered = sum(1 for o in orders if o.get("status") == "delivered")
        pending = sum(1 for o in orders if o.get("status") in ("pending", "assigned", "in_transit"))
        at_risk = sum(1 for o in orders if o.get("status") == "at_risk")

        total_co2 = active.get("total_co2_kg", 0)
        carbon_budget = state.get("carbon_budget_kg", 45.0)

        alerts = []
        if broken:
            alerts.append({"level": "critical", "message": f"{broken} vehicle(s) in breakdown state"})
        if at_risk:
            alerts.append({"level": "warning", "message": f"{at_risk} deliveries at risk"})
        if total_co2 > carbon_budget:
            alerts.append({"level": "warning", "message": "Estimated CO₂e exceeds carbon budget"})

        return {
            "kpis": {
                "active_vehicles": active_vehicles,
                "broken_vehicles": broken,
                "delivered_orders": delivered,
                "pending_orders": pending,
                "at_risk_orders": at_risk,
                "total_distance_km": active.get("total_distance_km", 0),
                "total_cost_pkr": active.get("total_operating_cost_pkr", 0),
                "total_co2_kg": total_co2,
                "carbon_budget_kg": carbon_budget,
                "carbon_budget_used_pct": round((total_co2 / carbon_budget * 100) if carbon_budget else 0, 1),
            },
            "alerts": alerts,
            "latest_events": state.get("events", [])[-5:],
            "activity_log": list(reversed(state.get("activity_log", [])[-12:])),
            "depot": state.get("depot"),
            "updated_at": state.get("updated_at"),
        }

    def list_vehicles(self) -> list[dict[str, Any]]:
        return self.get_state().get("vehicles", [])

    def list_orders(self) -> list[dict[str, Any]]:
        return self.get_state().get("orders", [])

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any] | None:
        for v in self.list_vehicles():
            if v["id"] == vehicle_id:
                return v
        return None

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        for o in self.list_orders():
            if o["id"] == order_id:
                return o
        return None

    def add_vehicle(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            vehicle_id = _clean_label(payload.get("id"), "id", f"V{len(state['vehicles']) + 1}")
            if any(v.get("id") == vehicle_id for v in state["vehicles"]):
                raise ValueError(f"Vehicle id {vehicle_id} already exists.")
            engine_type = str(payload.get("engine_type", "petrol")).strip().lower()
            if engine_type not in {"petrol", "diesel", "hybrid", "electric"}:
                raise ValueError("engine_type must be petrol, diesel, hybrid, or electric.")
            vehicle = {
                "id": vehicle_id,
                "name": _clean_label(payload.get("name"), "name", "New Vehicle"),
                "engine_type": engine_type,
                "capacity_kg": int(_bounded_number(payload.get("capacity_kg", 400), "capacity_kg", 1, 100000)),
                "lat": _bounded_number(payload.get("lat", state["depot"]["lat"]), "lat", -90, 90),
                "lng": _bounded_number(payload.get("lng", state["depot"]["lng"]), "lng", -180, 180),
                "status": "active",
                "fuel_or_range_pct": int(_bounded_number(payload.get("fuel_or_range_pct", 100), "fuel_or_range_pct", 0, 100)),
                "cost_per_km": _bounded_number(payload.get("cost_per_km", 15.0), "cost_per_km", 0, 100000),
            }
            state["vehicles"].append(vehicle)
            state["updated_at"] = self._now()
            self._write(state)
            return vehicle

    def add_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            order_id = _clean_label(payload.get("id"), "id", f"O{len(state['orders']) + 1}")
            if any(o.get("id") == order_id for o in state["orders"]):
                raise ValueError(f"Order id {order_id} already exists.")
            priority = str(payload.get("priority", "normal")).strip().lower()
            if priority not in {"low", "normal", "high", "critical"}:
                raise ValueError("priority must be low, normal, high, or critical.")
            status = str(payload.get("status", "pending")).strip().lower()
            if status not in {"pending", "assigned", "in_transit", "at_risk", "delivered"}:
                raise ValueError("Invalid order status.")
            order = {
                "id": order_id,
                "customer": _clean_label(payload.get("customer"), "customer", "Customer"),
                "lat": _bounded_number(payload.get("lat"), "lat", -90, 90),
                "lng": _bounded_number(payload.get("lng"), "lng", -180, 180),
                "weight_kg": int(_bounded_number(payload.get("weight_kg", 50), "weight_kg", 1, 100000)),
                "priority": priority,
                "service_minutes": int(_bounded_number(payload.get("service_minutes", 10), "service_minutes", 0, 1440)),
                "deadline_minutes": int(_bounded_number(payload.get("deadline_minutes", 120), "deadline_minutes", 1, 10080)),
                "status": status,
                "assigned_vehicle": payload.get("assigned_vehicle"),
            }
            state["orders"].append(order)
            state["updated_at"] = self._now()
            self._write(state)
            return order

    def set_candidate_plans(self, plans: list[dict[str, Any]]) -> None:
        with self._lock:
            state = self._read()
            state["candidate_plans"] = plans
            state["updated_at"] = self._now()
            self._write(state)

    def apply_plan(self, plan_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            plan = next((p for p in state.get("candidate_plans", []) if p.get("id") == plan_id), None)
            if not plan and state.get("active_plan", {}).get("id") == plan_id:
                plan = state["active_plan"]
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")

            order_map = {o["id"]: o for o in state["orders"]}
            for route in plan.get("vehicle_routes", []):
                vid = route["vehicle_id"]
                for v in state["vehicles"]:
                    if v["id"] == vid and v["status"] != "breakdown":
                        v["status"] = "active"
                for oid in route.get("order_ids", []):
                    if oid in order_map:
                        order_map[oid]["assigned_vehicle"] = vid
                        order_map[oid]["status"] = "assigned"

            state["active_plan"] = plan
            # Capture baseline KPIs the first time a plan is applied (for before/after deltas)
            if not state.get("baseline_snapshot"):
                state["baseline_snapshot"] = self._plan_snapshot(plan, label="baseline")
            state["updated_at"] = self._now()
            self._write(state)
            return plan

    @staticmethod
    def _plan_snapshot(plan: dict[str, Any] | None, label: str = "current") -> dict[str, Any]:
        plan = plan or {}
        return {
            "label": label,
            "distance_km": plan.get("total_distance_km", 0),
            "cost_pkr": plan.get("total_operating_cost_pkr", 0),
            "co2_kg": plan.get("total_co2_kg", 0),
            "deliveries": plan.get("deliveries_assigned", 0),
            "mode": plan.get("mode"),
            "plan_id": plan.get("id"),
        }

    def capture_baseline(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            plan = state.get("active_plan")
            if not plan:
                raise ValueError("No active plan to snapshot")
            if force or not state.get("baseline_snapshot"):
                state["baseline_snapshot"] = self._plan_snapshot(plan, label="baseline")
                state["updated_at"] = self._now()
                self._write(state)
            return state["baseline_snapshot"]

    def compute_delta(self, after_plan: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            before = state.get("baseline_snapshot") or self._plan_snapshot(None, "baseline")
            after = self._plan_snapshot(after_plan or state.get("active_plan"), label="after")
            delta = {
                "before": before,
                "after": after,
                "distance_km": round((after["distance_km"] or 0) - (before["distance_km"] or 0), 2),
                "cost_pkr": round((after["cost_pkr"] or 0) - (before["cost_pkr"] or 0), 2),
                "co2_kg": round((after["co2_kg"] or 0) - (before["co2_kg"] or 0), 3),
                "deliveries": (after["deliveries"] or 0) - (before["deliveries"] or 0),
            }
            state["latest_delta"] = delta
            state["updated_at"] = self._now()
            self._write(state)
            return delta

    def set_carbon_budget(self, kg: float) -> float:
        with self._lock:
            state = self._read()
            state["carbon_budget_kg"] = float(kg)
            state["updated_at"] = self._now()
            self._write(state)
            return state["carbon_budget_kg"]

    def get_latest_delta(self) -> dict[str, Any] | None:
        return self.get_state().get("latest_delta")

    def log_activity(self, actor: str, action: str, detail: str = "") -> dict[str, Any]:
        with self._lock:
            state = self._read()
            entry = {
                "id": f"ACT-{uuid.uuid4().hex[:8]}",
                "timestamp": self._now(),
                "actor": actor or "Operator",
                "action": action,
                "detail": detail,
            }
            state.setdefault("activity_log", []).append(entry)
            state["activity_log"] = state["activity_log"][-80:]
            state["updated_at"] = self._now()
            self._write(state)
            return entry

    def push_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            entry = {
                "id": f"AL-{uuid.uuid4().hex[:8]}",
                "timestamp": self._now(),
                **alert,
            }
            state.setdefault("alerts_outbox", []).append(entry)
            state["alerts_outbox"] = state["alerts_outbox"][-40:]
            state["updated_at"] = self._now()
            self._write(state)
            return entry

    def list_alerts(self) -> list[dict[str, Any]]:
        return list(reversed(self.get_state().get("alerts_outbox", [])[-15:]))

    def set_carbon_enforcement(self, enabled: bool) -> bool:
        with self._lock:
            state = self._read()
            state["enforce_carbon_budget"] = bool(enabled)
            state["updated_at"] = self._now()
            self._write(state)
            return state["enforce_carbon_budget"]

    def log_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            event = {
                "id": f"EV-{uuid.uuid4().hex[:8]}",
                "type": event_type,
                "timestamp": self._now(),
                **payload,
            }
            state.setdefault("events", []).append(event)
            state["updated_at"] = self._now()
            self._write(state)
            return event

    def log_decision(
        self,
        trigger: str,
        alternatives: list[dict[str, Any]],
        selected: dict[str, Any],
        explanation: str,
        approval_status: str = "auto_applied",
    ) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            decision = {
                "id": f"DEC-{uuid.uuid4().hex[:8]}",
                "timestamp": self._now(),
                "trigger": trigger,
                "alternatives_evaluated": alternatives,
                "selected_plan": selected,
                "impact": {
                    "distance_km": selected.get("total_distance_km"),
                    "cost_pkr": selected.get("total_operating_cost_pkr"),
                    "co2_kg": selected.get("total_co2_kg"),
                    "deliveries_assigned": selected.get("deliveries_assigned"),
                },
                "explanation": explanation,
                "approval_status": approval_status,
            }
            state.setdefault("decisions", []).append(decision)
            state["updated_at"] = self._now()
            self._write(state)
            return decision

    def get_decisions(self) -> list[dict[str, Any]]:
        return self.get_state().get("decisions", [])

    def mark_vehicle_breakdown(self, vehicle_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            vehicle = next((v for v in state["vehicles"] if v["id"] == vehicle_id), None)
            if not vehicle:
                raise ValueError(f"Vehicle {vehicle_id} not found")
            vehicle["status"] = "breakdown"
            affected = []
            for o in state["orders"]:
                if o.get("assigned_vehicle") == vehicle_id and o.get("status") in ("assigned", "in_transit"):
                    o["status"] = "at_risk"
                    o["assigned_vehicle"] = None
                    affected.append(o["id"])
            state["updated_at"] = self._now()
            self._write(state)
            return {"vehicle_id": vehicle_id, "affected_orders": affected}

    def apply_road_penalty(self, lat: float, lng: float, radius_km: float = 2.0) -> dict[str, Any]:
        """Mark orders near a point as delayed/at_risk."""
        from carbon_cost_engine import haversine_km

        with self._lock:
            state = self._read()
            affected = []
            for o in state["orders"]:
                if o.get("status") in ("assigned", "pending", "in_transit"):
                    dist = haversine_km(lat, lng, o["lat"], o["lng"])
                    if dist <= radius_km:
                        o["status"] = "at_risk"
                        affected.append(o["id"])
            state.setdefault("disruptions", []).append(
                {"type": "road_blockage", "lat": lat, "lng": lng, "radius_km": radius_km, "affected": affected}
            )
            state["updated_at"] = self._now()
            self._write(state)
            return {"affected_orders": affected}

    def mark_low_range(self, vehicle_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            vehicle = next((v for v in state["vehicles"] if v["id"] == vehicle_id), None)
            if not vehicle:
                raise ValueError(f"Vehicle {vehicle_id} not found")
            vehicle["fuel_or_range_pct"] = min(vehicle.get("fuel_or_range_pct", 50), 15)
            vehicle["status"] = "range_warning"
            affected = [o["id"] for o in state["orders"] if o.get("assigned_vehicle") == vehicle_id]
            state["updated_at"] = self._now()
            self._write(state)
            return {"vehicle_id": vehicle_id, "affected_orders": affected}

    def get_at_risk_deliveries(self) -> list[dict[str, Any]]:
        return [o for o in self.list_orders() if o.get("status") == "at_risk"]

    def get_impact_summary(self) -> dict[str, Any]:
        from carbon_cost_engine import calculate_emissions_kg

        state = self.get_state()
        decisions = state.get("decisions", [])
        events = state.get("events", [])
        active = state.get("active_plan") or {}
        baseline = state.get("baseline_snapshot") or {}
        current_co2 = active.get("total_co2_kg", 0)
        baseline_co2 = baseline.get("co2_kg", 0)
        conventional_co2 = calculate_emissions_kg(active.get("total_distance_km", 0) or 0, "petrol")
        conventional_avoided = round(max(0, conventional_co2 - current_co2), 3)
        return {
            "km_planned": active.get("total_distance_km", 0),
            "estimated_cost_pkr": active.get("total_operating_cost_pkr", 0),
            "estimated_co2_kg": current_co2,
            "co2_avoided_vs_baseline_kg": conventional_avoided,
            "co2_avoided_vs_conventional_kg": conventional_avoided,
            "conventional_all_petrol_co2_kg": conventional_co2,
            "recovery_co2_delta_kg": round(current_co2 - baseline_co2, 3),
            "avoidance_baseline_label": "All-petrol fleet over the same planned distance",
            "deliveries_protected": active.get("deliveries_assigned", 0),
            "disruptions_resolved": sum(
                1
                for e in events
                if e.get("type")
                in ("breakdown", "urgent_order", "road_blockage", "range_warning", "carbon_budget_breach")
            ),
            "agent_actions": len(decisions),
            "disruption_history": events[-10:],
            "delta": state.get("latest_delta"),
            "baseline": baseline,
            "carbon_budget_kg": state.get("carbon_budget_kg", 45),
            "enforce_carbon_budget": state.get("enforce_carbon_budget", True),
            "impact_score": round(
                (active.get("deliveries_assigned", 0) or 0) * 10
                + conventional_avoided * 5
                + len(decisions) * 2,
                1,
            ),
        }
