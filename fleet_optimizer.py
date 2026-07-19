"""Multi-vehicle route optimization using Google OR-Tools with planning modes."""

from __future__ import annotations

import math
import os
import uuid
from typing import Any

from carbon_cost_engine import (
    compare_plans as rank_comparable_plans,
    haversine_km,
    summarize_plan,
    summarize_vehicle_route,
)
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

MODE_WEIGHTS = {
    "economy": {"cost": 1.0, "distance": 0.3, "emissions": 0.1, "lateness": 0.2},
    "green": {"cost": 0.2, "distance": 0.3, "emissions": 1.0, "lateness": 0.2},
    "service": {"cost": 0.3, "distance": 0.2, "emissions": 0.2, "lateness": 1.0},
}


def _build_distance_matrix(locations: list[tuple[float, float]]) -> list[list[int]]:
    """OR-Tools expects integer distances; scale km to metres."""
    n = len(locations)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            km = haversine_km(locations[i][0], locations[i][1], locations[j][0], locations[j][1])
            matrix[i][j] = int(km * 1000)
    return matrix


def _mode_cost_coeff(mode: str, vehicle: dict[str, Any]) -> float:
    w = MODE_WEIGHTS.get(mode, MODE_WEIGHTS["economy"])
    engine = vehicle.get("engine_type", "petrol")
    emission_factor = {"petrol": 1.0, "hybrid": 0.56, "electric": 0.25}.get(engine, 1.0)
    return w["cost"] * vehicle.get("cost_per_km", 15) + w["emissions"] * emission_factor * 8


def _finalize_plan(plan: dict[str, Any], mode: str) -> dict[str, Any]:
    plan["id"] = f"PLAN-{uuid.uuid4().hex[:8]}"
    plan["label"] = {"economy": "Economy Plan", "green": "Green Plan", "service": "Service Plan"}[mode]
    weights = MODE_WEIGHTS[mode]
    plan["score"] = round(
        plan["total_operating_cost_pkr"] * weights["cost"]
        + plan["total_co2_kg"] * 100 * weights["emissions"]
        + plan["total_distance_km"] * weights["distance"]
        + len(plan.get("unassigned_orders", [])) * 1000 * weights["lateness"],
        2,
    )
    plan["objective_score"] = plan["score"]
    return plan


class FleetOptimizer:
    def __init__(self, search_seconds: float | None = None) -> None:
        configured = search_seconds if search_seconds is not None else os.environ.get("SKY_OPTIMIZER_SECONDS", "0.5")
        try:
            self.search_seconds = max(0.1, min(float(configured), 10.0))
        except (TypeError, ValueError):
            self.search_seconds = 0.5

    def optimize_fleet(
        self,
        depot: dict[str, Any],
        vehicles: list[dict[str, Any]],
        orders: list[dict[str, Any]],
        mode: str = "economy",
    ) -> dict[str, Any]:
        if mode not in MODE_WEIGHTS:
            raise ValueError(f"Unknown optimization mode: {mode}")
        active_vehicles = [v for v in vehicles if v.get("status") in ("active", "range_warning")]
        pending_orders = [o for o in orders if o.get("status") in ("pending", "at_risk", "assigned")]

        if not active_vehicles:
            return _finalize_plan(summarize_plan([], mode, [o["id"] for o in pending_orders]), mode)
        if not pending_orders:
            return _finalize_plan(summarize_plan([], mode, []), mode)

        locations = [(depot["lat"], depot["lng"])]
        order_index_map: list[str | None] = [None]
        demands = [0]
        for o in pending_orders:
            locations.append((o["lat"], o["lng"]))
            order_index_map.append(o["id"])
            demands.append(int(o.get("weight_kg", 1)))

        dist_matrix = _build_distance_matrix(locations)
        num_vehicles = len(active_vehicles)
        capacities = [int(v.get("capacity_kg", 400)) for v in active_vehicles]

        manager = pywrapcp.RoutingIndexManager(len(locations), num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index: int, to_index: int) -> int:
            f = manager.IndexToNode(from_index)
            t = manager.IndexToNode(to_index)
            return dist_matrix[f][t]

        # Mode-aware per-vehicle cost: Green penalizes high-emission vehicles,
        # Economy favors cheaper operating cost, Service uses raw distance.
        vehicle_cost_indices = []
        for vehicle in active_vehicles:
            coeff = _mode_cost_coeff(mode, vehicle)

            def make_cb(c=coeff):
                def cb(from_index: int, to_index: int) -> int:
                    f = manager.IndexToNode(from_index)
                    t = manager.IndexToNode(to_index)
                    return int(dist_matrix[f][t] * c)
                return cb

            vehicle_cost_indices.append(routing.RegisterTransitCallback(make_cb()))

        for v_idx, cb_idx in enumerate(vehicle_cost_indices):
            routing.SetArcCostEvaluatorOfVehicle(cb_idx, v_idx)

        def demand_callback(from_index: int) -> int:
            return demands[manager.IndexToNode(from_index)]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            capacities,
            True,
            "Capacity",
        )

        # Prefer high-priority orders via drop penalty
        penalty = 500000 if mode == "service" else 800000
        for node in range(1, len(locations)):
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        # The Lahore MVP is small; one second is enough and keeps the guided
        # optimize + recovery loop presentation-friendly. Override for larger fleets.
        whole_seconds = int(self.search_seconds)
        search_params.time_limit.seconds = whole_seconds
        search_params.time_limit.nanos = int((self.search_seconds - whole_seconds) * 1_000_000_000)

        solution = routing.SolveWithParameters(search_params)

        vehicle_routes: list[dict[str, Any]] = []
        unassigned: list[str] = list(order_index_map[1:])  # assume all unassigned until proven

        if solution:
            assigned_set: set[str] = set()
            for v_idx, vehicle in enumerate(active_vehicles):
                index = routing.Start(v_idx)
                route_nodes: list[int] = [0]
                order_ids: list[str] = []
                while not routing.IsEnd(index):
                    index = solution.Value(routing.NextVar(index))
                    node = manager.IndexToNode(index)
                    if node != 0:
                        route_nodes.append(node)
                        oid = order_index_map[node]
                        if oid:
                            order_ids.append(oid)
                            assigned_set.add(oid)

                if len(route_nodes) <= 1:
                    continue

                stop_coords = [{"lat": locations[n][0], "lng": locations[n][1]} for n in route_nodes]
                # return to depot
                stop_coords.append({"lat": depot["lat"], "lng": depot["lng"]})

                summary = summarize_vehicle_route(vehicle, stop_coords, len(order_ids))
                summary["order_ids"] = order_ids
                summary["polyline_coords"] = [[s["lat"], s["lng"]] for s in stop_coords]
                vehicle_routes.append(summary)

            unassigned = [oid for oid in order_index_map[1:] if oid and oid not in assigned_set]

        plan = summarize_plan(vehicle_routes, mode, unassigned)
        return _finalize_plan(plan, mode)

    def generate_all_modes(
        self,
        depot: dict[str, Any],
        vehicles: list[dict[str, Any]],
        orders: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        plans = []
        for mode in ("economy", "green", "service"):
            plans.append(self.optimize_fleet(depot, vehicles, orders, mode=mode))
        return plans

    def compare_plans(self, plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return rank_comparable_plans(plans)
