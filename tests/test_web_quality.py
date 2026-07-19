"""Regression tests for web, validation, and security quality fixes."""

from datetime import datetime, timezone

import pytest

import app as app_module
from auth_store import UserStore, ValidationError
from fleet_optimizer import FleetOptimizer
from fleet_store import FleetStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    isolated_users = UserStore(str(tmp_path / "users.json"))
    monkeypatch.setattr(app_module, "users", isolated_users)
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret", DEBUG=False)
    with app_module.app.test_client() as test_client:
        yield test_client, isolated_users


def _signup(client, email="quality@example.com"):
    return client.post("/api/signup", json={
        "name": "Quality Operator",
        "email": email,
        "password": "StrongPass1!",
    })


def test_security_headers_and_api_cache_policy(client):
    test_client, _ = client
    page = test_client.get("/")
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    api = test_client.get("/api/session")
    assert api.headers["Cache-Control"] == "no-store"


def test_private_route_optimizer_requires_login(client):
    test_client, _ = client
    response = test_client.post("/api/optimize", json={"source": "Lahore", "destination": "Kasur", "vehicle": "hybrid"})
    assert response.status_code == 401


def test_profile_update_keeps_public_user_dict_in_session(client):
    test_client, store = client
    assert _signup(test_client).status_code == 201
    response = test_client.post("/update_profile", data={"name": "Updated Operator"})
    assert response.status_code == 200
    assert response.get_json()["user"]["initials"] == "UO"
    session_user = test_client.get("/api/session").get_json()["user"]
    assert isinstance(session_user, dict)
    assert session_user["name"] == "Updated Operator"
    assert store.verify_user("quality@example.com", "StrongPass1!")["name"] == "Updated Operator"


def test_admin_delete_uses_canonical_user_store(client):
    test_client, store = client
    store.create_user("Delete Me", "delete@example.com", "StrongPass1!")
    with test_client.session_transaction() as session:
        session["admin"] = {"email": "admin@example.com", "name": "Admin"}
    response = test_client.post("/api/admin/users/delete@example.com/delete")
    assert response.status_code == 200
    with pytest.raises(ValidationError):
        store.verify_user("delete@example.com", "StrongPass1!")


def test_checkout_rejects_expired_card(client):
    test_client, _ = client
    assert _signup(test_client).status_code == 201
    expired_year = (datetime.now(timezone.utc).year - 1) % 100
    response = test_client.post("/api/premium/checkout", json={
        "name_on_card": "Quality Operator",
        "card_number": "4242424242424242",
        "expiry": f"12/{expired_year:02d}",
        "cvv": "123",
    })
    assert response.status_code == 400
    assert "expired" in response.get_json()["error"].lower()


def test_invalid_fleet_mode_returns_400(client):
    test_client, _ = client
    with test_client.session_transaction() as session:
        session["user"] = {"name": "Demo", "email": "demo@local", "plan": "pro"}
    response = test_client.post("/api/fleet/optimize", json={"mode": "fastest"})
    assert response.status_code == 400


def test_debug_route_is_hidden_when_debug_is_off(client):
    test_client, _ = client
    with test_client.session_transaction() as session:
        session["user"] = {"name": "Demo", "email": "demo@local", "plan": "pro"}
    assert test_client.get("/debug-routes").status_code == 404


def test_empty_optimizer_plan_still_has_identity():
    plan = FleetOptimizer().optimize_fleet(
        {"lat": 31.5, "lng": 74.3},
        [{"id": "V1", "status": "active", "capacity_kg": 100}],
        [],
        mode="green",
    )
    assert plan["id"].startswith("PLAN-")
    assert plan["label"] == "Green Plan"
    assert "score" in plan


def test_equal_plans_prefer_green_on_shared_comparison_scale():
    plans = [
        {"mode": mode, "total_co2_kg": 5, "total_operating_cost_pkr": 100, "total_distance_km": 20, "unassigned_orders": [], "score": score}
        for mode, score in (("economy", 1), ("green", 999), ("service", 10))
    ]
    ranked = FleetOptimizer().compare_plans(plans)
    assert ranked[0]["mode"] == "green"
    assert len({plan["comparison_score"] for plan in ranked}) == 1


def test_impact_uses_explicit_all_petrol_counterfactual(tmp_path):
    store = FleetStore(state_path=str(tmp_path / "fleet_state.json"))
    state = store.get_state()
    plan = FleetOptimizer().optimize_fleet(state["depot"], state["vehicles"], state["orders"], mode="green")
    store.set_candidate_plans([plan])
    store.apply_plan(plan["id"])
    summary = store.get_impact_summary()
    assert summary["co2_avoided_vs_conventional_kg"] > 0
    assert summary["conventional_all_petrol_co2_kg"] > summary["estimated_co2_kg"]
    assert "all-petrol" in summary["avoidance_baseline_label"].lower()


def test_fleet_store_validates_coordinates_and_duplicate_ids(tmp_path):
    store = FleetStore(state_path=str(tmp_path / "fleet_state.json"))
    with pytest.raises(ValueError, match="lat"):
        store.add_order({"customer": "Invalid", "lat": 100, "lng": 74.3})
    existing_id = store.list_vehicles()[0]["id"]
    with pytest.raises(ValueError, match="already exists"):
        store.add_vehicle({"id": existing_id, "name": "Duplicate"})
