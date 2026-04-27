#!/usr/bin/env python3
"""Validate the prisoner's dilemma scenario rules."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from configloader import load_scenario_manifest
from orchestrator import Orchestrator
from scenario_resolution import evaluate_prisoners_dilemma
from socialmatrix import SocialMatrix
from worldstate import WorldState


SCENARIO_DIR = Path("scenarios/prisoners_dilemma")


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed. {detail}")
    print(f"[PASS] {name}")
    if detail:
        print(f"       {detail}")


def event(agent_id: str, action: str, target: str = "") -> dict:
    return {
        "agent_id": agent_id,
        "action": action,
        "target": target,
        "success": True
    }


class PressureAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.condition = {"health": 100, "stress": 0, "fatigue": 0, "morale": 50}
        self.memory_buffer = []
        self.emotional_state = "Neutral"

    def add_to_memory(self, memory: str) -> None:
        self.memory_buffer.append(memory)

    def adjust_condition(self, **deltas: int) -> dict[str, int]:
        changed = {}
        for key, delta in deltas.items():
            before = self.condition[key]
            after = max(0, min(100, before + int(delta)))
            self.condition[key] = after
            if after != before:
                changed[key] = after - before
        return changed

    def set_emotional_state(self, state: str) -> None:
        self.emotional_state = state


def main() -> None:
    manifest = load_scenario_manifest(SCENARIO_DIR)
    rules = manifest["resolution_rules"]

    with open(SCENARIO_DIR / "world_state.json", "r", encoding="utf-8") as f:
        world_data = json.load(f)
    world = WorldState(world_data)
    world.register_agent("detainee_nova", "holding_cell_a")
    world.register_agent("detainee_silas", "holding_cell_b")

    class DummyAgent:
        def __init__(self, agent_id: str):
            self.agent_id = agent_id

    parser = ActionParser(world)
    success, feedback = parser.validate_move(
        "holding_cell_a",
        "observation_room",
        world,
        "detainee_nova"
    )
    check(
        "Observation room is access-gated",
        not success and "observer_clearance" in feedback,
        feedback
    )

    success, feedback = parser.execute(DummyAgent("detainee_nova"), {
        "action": "PICKUP",
        "action_target": "Deal Sheet A"
    })
    check("Nova can pick up local plea sheet", success, feedback)

    success, feedback = parser.execute(DummyAgent("detainee_nova"), {
        "action": "READ",
        "action_target": "Deal Sheet A"
    })
    check("Nova can read plea terms", success, feedback)
    check(
        "Reading plea sheet records private fact",
        "plea_terms:nova" in world.get_known_facts("detainee_nova"),
        str(world.get_known_facts("detainee_nova").keys())
    )

    pressure_world = WorldState(world_data)
    pressure_world.register_agent("detainee_nova", "holding_cell_a")
    pressure_world.register_agent("detainee_silas", "holding_cell_b")
    pressure_agents = [
        PressureAgent("detainee_nova", "Nova Reed"),
        PressureAgent("detainee_silas", "Silas Voss")
    ]
    pressure_orchestrator = Orchestrator(
        pressure_agents,
        pressure_world,
        ActionParser(pressure_world),
        SocialMatrix(),
        progression_config=manifest["progression"]
    )
    fired = []
    for agent in pressure_agents:
        fired.extend(pressure_orchestrator._update_progression_pressure(agent, "WAIT", "", True))
    check(
        "Scenario pressure fires from repeated stalling, not turn count",
        bool(fired) and fired[0]["target"] == "protocol_warning",
        str(fired)
    )
    check(
        "Pressure changes agent condition",
        pressure_agents[0].condition["stress"] == 6 and pressure_agents[0].emotional_state == "Anxious",
        str(pressure_agents[0].condition)
    )

    cases = [
        (
            "both silent",
            [event("detainee_nova", "WAIT"), event("detainee_silas", "WAIT")],
            "both_silent",
            {"detainee_nova": 2, "detainee_silas": 2}
        ),
        (
            "Nova cooperates, Silas silent",
            [
                event("detainee_nova", "SAY", "I will cooperate with investigators about the warehouse case."),
                event("detainee_silas", "WAIT")
            ],
            "nova_cooperates_silas_silent",
            {"detainee_nova": 0, "detainee_silas": 8}
        ),
        (
            "Nova silent, Silas cooperates",
            [
                event("detainee_nova", "WAIT"),
                event("detainee_silas", "SAY", "I will testify about the cargo manifest.")
            ],
            "nova_silent_silas_cooperates",
            {"detainee_nova": 8, "detainee_silas": 0}
        ),
        (
            "both cooperate",
            [
                event("detainee_nova", "SAY", "I will cooperate with investigators."),
                event("detainee_silas", "LIE", "Nova handled the stolen cargo.")
            ],
            "both_cooperate",
            {"detainee_nova": 5, "detainee_silas": 5}
        ),
        (
            "spoken silence stays silent",
            [
                event("detainee_nova", "SAY", "I will stay silent and wait for my attorney."),
                event("detainee_silas", "WAIT")
            ],
            "both_silent",
            {"detainee_nova": 2, "detainee_silas": 2}
        ),
    ]

    for name, events, expected_outcome, expected_sentences in cases:
        result = evaluate_prisoners_dilemma(events, rules)
        check(f"Resolution: {name}", result["outcome"] == expected_outcome, str(result))
        check(
            f"Sentences: {name}",
            result["sentences_years"] == expected_sentences,
            str(result["sentences_years"])
        )


if __name__ == "__main__":
    main()
