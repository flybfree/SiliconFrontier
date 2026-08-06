"""Checks same-turn replacement choices after environmental preemption."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from agent import FrontierAgent


def main() -> None:
    assert ActionParser.is_reconsiderable_failure(
        "SABOTAGE", "Failure: Someone else is here. Sabotage would be too obvious."
    )
    assert not ActionParser.is_reconsiderable_failure("SABOTAGE", "Failure: reactor_control is already broken.")
    assert not ActionParser.is_reconsiderable_failure("USE", "Failure: Someone else is here.")

    agent = FrontierAgent.__new__(FrontierAgent)
    agent.emotional_state = "Determined"
    captured: dict[str, str] = {}

    def choose_replacement(observation: str, snapshot: dict) -> dict:
        captured["observation"] = observation
        captured["snapshot"] = snapshot
        return {
            "action": "MOVE",
            "action_target": "storage_locker",
            "internal_monologue": "I will relocate and prepare instead.",
            "emotional_state": "Determined",
        }

    agent.think_and_act = choose_replacement
    replacement = agent.reconsider_action(
        "Engineering is occupied.",
        {"visible_agents": ["torres"]},
        "SABOTAGE",
        "reactor_control",
        "Failure: Someone else is here. Sabotage would be too obvious.",
    )
    assert replacement["action"] == "MOVE"
    assert replacement["action_target"] == "storage_locker"
    assert "Do not repeat the attempted action" in captured["observation"]
    assert "do not choose SABOTAGE this turn" in captured["observation"]
    print("[PASS] Preempted sabotage receives one informed alternative choice")


if __name__ == "__main__":
    main()
