"""Scenario-specific resolution helpers."""

from __future__ import annotations

from typing import Any


PRISONERS_DILEMMA_DEFAULT_RULES = {
    "default_decision": "silent",
    "decision_actions": {
        "silent": ["WAIT"],
        "cooperate": ["SAY", "LIE"]
    },
    "cooperate_phrases": [
        "cooperate",
        "testify",
        "confess",
        "accept the deal",
        "take the deal",
        "give a statement",
        "make a statement",
        "betray",
        "implicate"
    ],
    "silent_phrases": [
        "stay silent",
        "remain silent",
        "no statement",
        "refuse to answer",
        "lawyer",
        "attorney"
    ],
    "final_statement_channels": [
        "microphone",
        "recording",
        "recorded statement",
        "for the record",
        "on the record"
    ],
    "payoffs_years": {
        "both_silent": {
            "detainee_nova": 2,
            "detainee_silas": 2
        },
        "nova_cooperates_silas_silent": {
            "detainee_nova": 0,
            "detainee_silas": 8
        },
        "nova_silent_silas_cooperates": {
            "detainee_nova": 8,
            "detainee_silas": 0
        },
        "both_cooperate": {
            "detainee_nova": 5,
            "detainee_silas": 5
        }
    }
}


def _merge_rules(rules: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(PRISONERS_DILEMMA_DEFAULT_RULES)
    if not rules:
        return merged
    for key, value in rules.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _contains_any(text: str, phrases: list[Any]) -> bool:
    return any(str(phrase).lower() in text for phrase in phrases)


def classify_prisoners_dilemma_action(event: dict[str, Any], rules: dict[str, Any] | None = None) -> str | None:
    """Classify one event-log entry as silent/cooperate, or None if not decisive."""
    merged = _merge_rules(rules)
    action = str(event.get("action", "")).upper()
    target = str(event.get("target", "")).lower()
    decision_actions = merged.get("decision_actions", {})

    if action in {str(item).upper() for item in decision_actions.get("silent", [])}:
        return "silent"

    if action in {str(item).upper() for item in decision_actions.get("cooperate", [])}:
        if _contains_any(target, merged.get("silent_phrases", [])):
            return "silent"
        if _contains_any(target, merged.get("cooperate_phrases", [])):
            return "cooperate"
        if _contains_any(target, merged.get("final_statement_channels", [])):
            return merged.get("default_decision", "silent")
        return None

    return None


def evaluate_prisoners_dilemma(
    event_log: list[dict[str, Any]],
    rules: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Evaluate the final prisoner choices and sentence payoffs from an event log."""
    merged = _merge_rules(rules)
    agents = list(merged.get("agents", {}).keys()) or ["detainee_nova", "detainee_silas"]
    if len(agents) != 2:
        raise ValueError("Prisoner's dilemma resolution requires exactly two agents.")

    decisions = {agent_id: merged.get("default_decision", "silent") for agent_id in agents}
    decisive_events = {}

    for event in event_log:
        agent_id = event.get("agent_id")
        if agent_id not in decisions or not event.get("success", True):
            continue
        decision = classify_prisoners_dilemma_action(event, merged)
        if decision:
            decisions[agent_id] = decision
            decisive_events[agent_id] = event

    nova_id, silas_id = agents
    nova_decision = decisions[nova_id]
    silas_decision = decisions[silas_id]

    if nova_decision == "silent" and silas_decision == "silent":
        outcome_key = "both_silent"
    elif nova_decision == "cooperate" and silas_decision == "silent":
        outcome_key = "nova_cooperates_silas_silent"
    elif nova_decision == "silent" and silas_decision == "cooperate":
        outcome_key = "nova_silent_silas_cooperates"
    else:
        outcome_key = "both_cooperate"

    payoffs = merged.get("payoffs_years", {}).get(outcome_key, {})
    return {
        "type": "prisoners_dilemma",
        "decisions": decisions,
        "outcome": outcome_key,
        "sentences_years": dict(payoffs),
        "decisive_events": decisive_events
    }
