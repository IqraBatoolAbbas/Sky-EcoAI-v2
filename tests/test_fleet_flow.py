"""Smoke tests for fleet optimization and disruption recovery."""

from fleet_store import FleetStore
from fleet_optimizer import FleetOptimizer
from disruption_agent import DisruptionAgent


def test_optimize_assigns_all_orders():
    store = FleetStore()
    store.reset_demo()
    state = store.get_state()
    opt = FleetOptimizer()
    plan = opt.optimize_fleet(state["depot"], state["vehicles"], state["orders"], mode="green")
    assert plan["deliveries_assigned"] == 12
    assert plan["total_co2_kg"] > 0
    assert len(plan["vehicle_routes"]) >= 1


def test_breakdown_and_recovery_reassigns():
    store = FleetStore()
    store.reset_demo()
    state = store.get_state()
    opt = FleetOptimizer()
    plans = opt.compare_plans(opt.generate_all_modes(state["depot"], state["vehicles"], state["orders"]))
    store.set_candidate_plans(plans)
    store.apply_plan(plans[0]["id"])

    agent = DisruptionAgent(store)
    br = agent.simulate_breakdown()
    assert br["vehicle_id"]
    assert len(br["affected_orders"]) >= 1

    recovery = agent.generate_recovery_plans("breakdown")
    assert recovery["recommended_plan_id"]
    assert len(recovery["recovery_plans"]) == 3

    applied = agent.apply_recovery_plan(recovery["recommended_plan_id"])
    assert applied["plan"]["deliveries_assigned"] >= 1
