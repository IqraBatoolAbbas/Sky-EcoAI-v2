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


class FleetStore:
    def __init__(self) -> None:
        self._lock = Lock()
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(STATE_PATH):
            self.reset_demo()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read(self) -> dict[str, Any]:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, state: dict[str, Any]) -> None:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def reset_demo(self) -> dict[str, Any]:
        with self._lock:
            with open(SEED_PATH, "r", encoding="utf-8") as f:
                seed = json.load(f)
            state = {
                **copy.deepcopy(seed),
                "active_plan": None,
                "candidate_plans": [],
                "events": [],
                "decisions": [],
                "disruptions": [],
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
            vehicle = {
                "id": payload.get("id") or f"V{len(state['vehicles']) + 1}",
                "name": payload.get("name", "New Vehicle"),
                "engine_type": payload.get("engine_type", "petrol"),
                "capacity_kg": int(payload.get("capacity_kg", 400)),
                "lat": float(payload.get("lat", state["depot"]["lat"])),
                "lng": float(payload.get("lng", state["depot"]["lng"])),
                "status": "active",
                "fuel_or_range_pct": int(payload.get("fuel_or_range_pct", 100)),
                "cost_per_km": float(payload.get("cost_per_km", 15.0)),
            }
            state["vehicles"].append(vehicle)
            state["updated_at"] = self._now()
            self._write(state)
            return vehicle

    def add_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            order = {
                "id": payload.get("id") or f"O{len(state['orders']) + 1}",
                "customer": payload.get("customer", "Customer"),
                "lat": float(payload["lat"]),
                "lng": float(payload["lng"]),
                "weight_kg": int(payload.get("weight_kg", 50)),
                "priority": payload.get("priority", "normal"),
                "service_minutes": int(payload.get("service_minutes", 10)),
                "deadline_minutes": int(payload.get("deadline_minutes", 120)),
                "status": payload.get("status", "pending"),
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
            state["updated_at"] = self._now()
            self._write(state)
            return plan

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
        state = self.get_state()
        decisions = state.get("decisions", [])
        events = state.get("events", [])
        active = state.get("active_plan") or {}
        baseline = next((d for d in decisions if d.get("trigger") == "initial_optimization"), None)
        baseline_co2 = (baseline or {}).get("selected_plan", {}).get("total_co2_kg", 0)
        current_co2 = active.get("total_co2_kg", 0)
        return {
            "km_planned": active.get("total_distance_km", 0),
            "estimated_cost_pkr": active.get("total_operating_cost_pkr", 0),
            "estimated_co2_kg": current_co2,
            "co2_avoided_vs_baseline_kg": round(max(0, baseline_co2 - current_co2), 3),
            "deliveries_protected": active.get("deliveries_assigned", 0),
            "disruptions_resolved": sum(1 for e in events if e.get("type") in ("breakdown", "urgent_order", "road_blockage", "range_warning")),
            "agent_actions": len(decisions),
            "disruption_history": events[-10:],
        }
