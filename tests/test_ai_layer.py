"""
AI-layer test suite for Sky.EcoAI.

Covers the parts of the codebase tests/test_fleet_flow.py doesn't touch:
  - rag_store.py      — TF-IDF retrieval relevance + live fleet snapshot text
  - genai_services.py — offline NL scenario parsing + impact narrative + ops alerts
  - fleet_copilot.py  — intent routing across the copilot's if/elif chain

Follows the same pattern as tests/test_fleet_flow.py: uses the real FleetStore
backed by data/fleet_state.json, and calls reset_demo() at the start of every
test that touches store state, so tests are independent of run order.

Two tests below (marked KNOWN GAP) intentionally pin down *current*, slightly
rough behavior rather than idealized behavior. They exist so a future fix
shows up as an intentional test update, not a silent regression.

Run with:
    pytest tests/test_ai_layer.py -v
"""

import pytest

from rag_store import RagStore
from genai_services import (
    parse_natural_scenario,
    generate_impact_narrative,
    generate_ops_alert,
)
from fleet_store import FleetStore
from disruption_agent import DisruptionAgent
from fleet_copilot import FleetCopilot


# ─────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def no_llm_keys(monkeypatch):
    """
    Force every test in this file down the deterministic offline path.
    Without this, a developer's local .env with GEMINI_API_KEY set would
    make these tests flaky (real network calls, non-deterministic text).
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def fresh_copilot():
    """A FleetCopilot wired to a freshly reset Lahore demo state."""
    store = FleetStore()
    store.reset_demo()
    agent = DisruptionAgent(store)
    rag = RagStore()
    copilot = FleetCopilot(store, agent, rag)
    return copilot, store


# ─────────────────────────────────────────────────────────────
# rag_store.py — retrieval relevance
# ─────────────────────────────────────────────────────────────

def test_rag_store_loads_knowledge_chunks():
    rag = RagStore()
    assert len(rag.chunks) > 0
    for chunk in rag.chunks:
        assert chunk["source"].endswith((".md", ".txt"))
        assert chunk["text"]
        assert chunk["tokens"]


def test_retrieve_carbon_budget_query_hits_relevant_docs():
    rag = RagStore()
    results = rag.retrieve("carbon budget estimated CO2e", top_k=3)
    assert results, "Expected at least one relevant chunk for a carbon-budget query"
    sources = {r["source"] for r in results}
    # Both operator_guide.md and judging_climate.md discuss carbon/CO2 estimates
    assert sources & {"operator_guide.md", "judging_climate.md"}


def test_retrieve_breakdown_recovery_query_hits_playbook():
    rag = RagStore()
    results = rag.retrieve("vehicle breakdown recovery plan", top_k=3)
    assert results
    sources = {r["source"] for r in results}
    assert "recovery_playbook.md" in sources


def test_retrieve_nonsense_query_returns_empty():
    rag = RagStore()
    results = rag.retrieve("qxzplorf nonexistent gibberish zzyx", top_k=5)
    assert results == []


def test_reload_returns_chunk_count():
    rag = RagStore()
    count = rag.reload()
    assert count == len(rag.chunks)
    assert count > 0


def test_live_fleet_facts_reports_kpis():
    store = FleetStore()
    store.reset_demo()
    rag = RagStore()
    snapshot = rag.live_fleet_facts(store)
    assert "Live fleet snapshot" in snapshot
    assert "Active vehicles:" in snapshot
    assert "Pending orders:" in snapshot
    assert "Est. CO2e:" in snapshot


def test_build_context_combines_live_state_and_docs():
    store = FleetStore()
    store.reset_demo()
    rag = RagStore()
    ctx = rag.build_context("carbon budget", store=store, top_k=3)
    assert ctx["chunk_count"] > 0
    assert "Live fleet snapshot" in ctx["context_text"]
    assert ctx["live_snapshot"]


# ─────────────────────────────────────────────────────────────
# genai_services.py — offline NL scenario parsing
# ─────────────────────────────────────────────────────────────

def test_parse_scenario_medical_keyword_produces_urgent_order():
    parsed = parse_natural_scenario("There's a medical emergency near Cantt")
    types = [a["type"] for a in parsed["actions"]]
    assert "urgent_order" in types
    assert parsed["generator"] == "offline structured intent parse"


def test_parse_scenario_breakdown_keyword():
    parsed = parse_natural_scenario("Our van broke down on the highway")
    types = [a["type"] for a in parsed["actions"]]
    assert types == ["breakdown"]


def test_parse_scenario_carbon_keyword():
    parsed = parse_natural_scenario("We are worried about our carbon budget this month")
    types = [a["type"] for a in parsed["actions"]]
    assert types == ["carbon_budget_breach"]


def test_parse_scenario_range_keyword():
    parsed = parse_natural_scenario("The EV battery is running low")
    types = [a["type"] for a in parsed["actions"]]
    assert types == ["range_warning"]


def test_parse_scenario_road_blockage_keyword():
    parsed = parse_natural_scenario("There's construction blocking the road")
    types = [a["type"] for a in parsed["actions"]]
    assert types == ["road_blockage"]
    action = next(a for a in parsed["actions"] if a["type"] == "road_blockage")
    assert action["radius_km"] == 2.5


def test_parse_scenario_unrecognized_text_defaults_to_breakdown():
    parsed = parse_natural_scenario("please check on the delivery status")
    assert parsed["actions"] == [{"type": "breakdown"}]
    assert "1 action" in parsed["summary"]


def test_parse_scenario_count_word_two_expands_urgent_orders():
    parsed = parse_natural_scenario("Two medical emergencies near Cantt")
    urgent = [a for a in parsed["actions"] if a["type"] == "urgent_order"]
    assert len(urgent) == 2
    assert urgent[0]["customer"] == "NL medical rush #1"
    assert urgent[1]["customer"] == "NL medical rush #2"


def test_parse_scenario_count_digit_three_expands_urgent_orders():
    parsed = parse_natural_scenario("3 urgent deliveries needed now")
    urgent = [a for a in parsed["actions"] if a["type"] == "urgent_order"]
    assert len(urgent) == 3


def test_parse_scenario_count_above_four_is_capped():
    """
    KNOWN GAP: parse_natural_scenario() caps expansion at 4 regardless of the
    number actually requested (min(n, 4) in genai_services.py). "5 medical
    emergencies" silently produces only 4 actions. This test pins the current
    behavior so a future fix (raising the cap, or warning the operator that
    the request was truncated) shows up as a deliberate test change rather
    than a silent regression.
    """
    parsed = parse_natural_scenario("5 medical emergencies incoming")
    urgent = [a for a in parsed["actions"] if a["type"] == "urgent_order"]
    assert len(urgent) == 4  # not 5 — current known limitation


def test_generate_impact_narrative_offline_uses_metric_template():
    summary = {
        "km_planned": 58.4,
        "estimated_co2_kg": 12.0,
        "co2_avoided_vs_baseline_kg": 42.0,
        "deliveries_protected": 9,
        "disruptions_resolved": 2,
        "agent_actions": 5,
    }
    result = generate_impact_narrative(summary, decisions=[])
    assert result["generator"] == "metric-grounded template"
    assert "Sky.EcoAI protected" in result["narrative"]
    assert "9 deliveries" in result["narrative"]
    assert result["sdg"]["primary"] == "SDG 13 — Climate Action"


def test_generate_impact_narrative_equivalents_math():
    summary = {
        "km_planned": 10,
        "estimated_co2_kg": 5,
        "co2_avoided_vs_baseline_kg": 42.0,
        "deliveries_protected": 1,
        "disruptions_resolved": 0,
        "agent_actions": 0,
    }
    result = generate_impact_narrative(summary, decisions=[])
    eq = result["equivalents"]
    assert eq["co2_avoided_kg"] == 42.0
    assert eq["trees_annual_uptake_est"] == round(42.0 / 21.0, 2)
    assert eq["fuel_liters_avoided_est"] == round(42.0 / 2.31, 1)


@pytest.mark.parametrize(
    "event_type,expected_fragment",
    [
        ("breakdown", "Vehicle unavailable"),
        ("urgent_order", "Urgent delivery inserted"),
        ("carbon_budget_breach", "exceeds carbon budget"),
        ("range_warning", "EV range critically low"),
        ("recovery_applied", "Recovery plan applied"),
        ("road_blockage", "Road penalty zone active"),
    ],
)
def test_generate_ops_alert_known_event_types(event_type, expected_fragment):
    alert = generate_ops_alert(event_type, "")
    assert expected_fragment in alert["body"]
    assert alert["severity"] == "simulated"
    assert set(alert["channels"]) == {"whatsapp", "email", "ops_banner"}


def test_generate_ops_alert_unknown_type_falls_back():
    alert = generate_ops_alert("some_new_event_type", "extra detail")
    assert alert["body"].startswith("Sky.EcoAI operations update.")
    assert "extra detail" in alert["body"]


def test_generate_ops_alert_truncates_long_detail():
    long_detail = "x" * 500
    alert = generate_ops_alert("breakdown", long_detail)
    # Function appends detail[:160] after the template text
    appended = alert["body"].split(" ", 4)[-1]  # crude split past the template prefix
    assert len(long_detail[:160]) == 160
    assert "x" * 160 in alert["body"]
    assert "x" * 161 not in alert["body"]


# ─────────────────────────────────────────────────────────────
# fleet_copilot.py — intent routing
# ─────────────────────────────────────────────────────────────

def test_answer_help_greeting_short_circuits_rag(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.answer_help("hi")
    assert resp["mode"] == "help"
    assert "Sky Assistant" in resp["reply"]
    assert resp["rag"]["sources"] == []


def test_answer_help_grounded_reply_for_operator_question(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.answer_help("What are the Economy Green and Service planning modes?")
    assert resp["mode"] == "help"
    assert resp["reply"]
    assert len(resp["rag"]["sources"]) >= 1


def test_process_message_optimize_generates_three_plans(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.process_message("optimize the fleet")
    tools_used = [t["tool"] for t in resp["tool_calls"]]
    assert "optimize_fleet" in tools_used
    plans_result = next(t["result"] for t in resp["tool_calls"] if t["tool"] == "optimize_fleet")
    assert len(plans_result["plans"]) == 3
    assert "Generated 3 plans" in resp["reply"]


def test_process_message_breakdown_requires_confirmation_first(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.process_message("simulate a breakdown")
    assert resp["pending_confirmation"] == "breakdown"
    assert resp["tool_calls"] == []
    assert "Confirm" in resp["reply"]


def test_process_message_confirmed_breakdown_executes_and_recovers(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.process_message(
        "simulate a breakdown", confirm_action=True, pending_action="breakdown"
    )
    tools_used = [t["tool"] for t in resp["tool_calls"]]
    assert "simulate_breakdown" in tools_used
    assert "generate_recovery" in tools_used
    assert "Confirmed: breakdown on" in resp["reply"]


def test_process_message_at_risk_lists_deliveries(fresh_copilot):
    copilot, store = fresh_copilot
    # Put a delivery at risk first so the count is non-trivial
    store.mark_vehicle_breakdown("V1")
    resp = copilot.process_message("which deliveries are at risk?")
    tools_used = [t["tool"] for t in resp["tool_calls"]]
    assert "get_at_risk_deliveries" in tools_used
    assert "at risk" in resp["reply"]


def test_process_message_impact_summary(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.process_message("give me an impact summary report")
    tools_used = [t["tool"] for t in resp["tool_calls"]]
    assert "generate_impact_summary" in tools_used
    assert "Impact:" in resp["reply"]


def test_process_message_unrecognized_input_falls_back_to_help(fresh_copilot):
    copilot, _ = fresh_copilot
    resp = copilot.process_message("asdkjhasd completely unrelated nonsense")
    assert resp["mode"] == "help"
    assert resp["pending_confirmation"] is None


def test_process_message_urgent_keyword_does_not_call_advertised_tool(fresh_copilot):
    """
    KNOWN GAP: 'insert_urgent_order' is listed in FleetCopilot.TOOL_DEFINITIONS
    as something the copilot can do, but the 'urgent' branch in
    process_message() only replies with instructions to use the Event Center —
    it never actually calls disruption.insert_urgent_order(). This test
    documents that gap so a future fix (wiring the tool call) is a deliberate,
    visible test change rather than an untracked behavior shift.
    """
    copilot, _ = fresh_copilot
    resp = copilot.process_message("I need an urgent order added")
    assert resp["tool_calls"] == []  # no tool actually invoked
    assert "insert_urgent_order" in resp["tools_available"]  # ...yet advertised
    assert "Event Center" in resp["reply"]