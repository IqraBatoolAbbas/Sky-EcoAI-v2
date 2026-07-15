"""Operational cost, fuel/energy, and estimated CO2 calculations for fleet plans."""

from __future__ import annotations

import math
from typing import Any

# grams CO2 per km by engine type (estimates — configurable conversion factors)
EMISSIONS_G_PER_KM = {
    "petrol": 192,
    "hybrid": 108,
    "electric": 48,
}

FUEL_OR_ENERGY_LABEL = {
    "petrol": "fuel",
    "hybrid": "fuel",
    "electric": "energy",
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def route_distance_km(stops: list[dict[str, float]]) -> float:
    """Sum haversine legs for ordered stops [{lat, lng}, ...]."""
    total = 0.0
    for i in range(len(stops) - 1):
        total += haversine_km(stops[i]["lat"], stops[i]["lng"], stops[i + 1]["lat"], stops[i + 1]["lng"])
    return round(total, 2)


def estimate_travel_minutes(distance_km: float, avg_speed_kmh: float = 32.0) -> float:
    return round((distance_km / avg_speed_kmh) * 60, 1)


def calculate_emissions_kg(distance_km: float, engine_type: str) -> float:
    g_per_km = EMISSIONS_G_PER_KM.get(engine_type, EMISSIONS_G_PER_KM["petrol"])
    return round((distance_km * g_per_km) / 1000.0, 3)


def calculate_operating_cost_pkr(distance_km: float, cost_per_km: float) -> float:
    return round(distance_km * cost_per_km, 2)


def summarize_vehicle_route(
    vehicle: dict[str, Any],
    stop_coords: list[dict[str, float]],
    order_count: int,
) -> dict[str, Any]:
    distance = route_distance_km(stop_coords)
    duration = estimate_travel_minutes(distance)
    co2_kg = calculate_emissions_kg(distance, vehicle.get("engine_type", "petrol"))
    cost = calculate_operating_cost_pkr(distance, vehicle.get("cost_per_km", 15.0))
    return {
        "vehicle_id": vehicle["id"],
        "vehicle_name": vehicle.get("name", vehicle["id"]),
        "engine_type": vehicle.get("engine_type", "petrol"),
        "order_count": order_count,
        "distance_km": distance,
        "duration_minutes": duration,
        "co2_kg": co2_kg,
        "operating_cost_pkr": cost,
        "stops": stop_coords,
    }


def summarize_plan(
    vehicle_routes: list[dict[str, Any]],
    mode: str,
    unassigned_orders: list[str] | None = None,
) -> dict[str, Any]:
    total_distance = sum(r["distance_km"] for r in vehicle_routes)
    total_cost = sum(r["operating_cost_pkr"] for r in vehicle_routes)
    total_co2 = sum(r["co2_kg"] for r in vehicle_routes)
    total_orders = sum(r["order_count"] for r in vehicle_routes)
    unassigned = unassigned_orders or []

    return {
        "mode": mode,
        "vehicle_routes": vehicle_routes,
        "total_distance_km": round(total_distance, 2),
        "total_operating_cost_pkr": round(total_cost, 2),
        "total_co2_kg": round(total_co2, 3),
        "total_co2_estimate_label": "Estimated CO₂e based on configured conversion factors",
        "deliveries_assigned": total_orders,
        "unassigned_orders": unassigned,
        "at_risk_count": len(unassigned),
        "score": round(total_cost + total_co2 * 50 + len(unassigned) * 500, 2),
    }


def compare_plans(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank plans; lower composite score is better."""
    ranked = sorted(plans, key=lambda p: p.get("score", float("inf")))
    for i, plan in enumerate(ranked):
        plan["rank"] = i + 1
    return ranked
