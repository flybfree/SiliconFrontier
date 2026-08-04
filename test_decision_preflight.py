"""Focused checks for goal-alignment and inventory preflight corrections."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent import FrontierAgent


def validate(goal: str, decision: dict, snapshot: dict) -> dict:
    agent = FrontierAgent.__new__(FrontierAgent)
    agent.secret_goal = goal
    return agent._validate_decision_against_telemetry(decision, snapshot)


def main() -> None:
    system = {"reactor_control": {"name": "Reactor Control Array", "status": "ONLINE"}}
    base = {"visible_systems": system, "agent_inventory": [], "available_recipes": []}

    protected = validate(
        "Keep the station functional and identify threats.",
        {"action": "SABOTAGE", "action_target": "reactor_control"}, base,
    )
    assert protected["action"] == "WAIT"

    disruptive = validate(
        "Make systems offline without being caught.",
        {"action": "SABOTAGE", "action_target": "reactor_control"}, base,
    )
    assert disruptive["action"] == "SABOTAGE"

    visible_slot = validate(
        "Gather evidence.", {"action": "PICKUP", "action_target": "Wire Spools"},
        {**base, "agent_inventory": [{"name": "Probe", "hidden": False}]},
    )
    assert visible_slot["action"] == "PICKUP"

    full = validate(
        "Gather evidence.", {"action": "PICKUP", "action_target": "Wire Spools"},
        {**base, "agent_inventory": [{"name": "Probe", "hidden": False}, {"name": "Cells", "inventory_slot": "visible"}]},
    )
    assert full["action"] == "WAIT"

    assembly = validate(
        "Gather evidence.", {"action": "ASSEMBLE", "action_target": "probe"},
        {**base, "agent_inventory": [{"name": "Probe", "hidden": False}], "available_recipes": [{"id": "probe"}]},
    )
    assert (assembly["action"], assembly["action_target"]) == ("STOW", "Probe")

    ready = validate(
        "Gather evidence.", {"action": "USE", "action_target": "Scanner -> oxygen_generator"},
        {**base, "agent_inventory": [{"name": "Scanner", "inventory_slot": "visible"}]},
    )
    assert (ready["action"], ready["action_target"]) == ("READY", "Scanner")
    print("[PASS] Goal guard and inventory preflight correct invalid turns")


if __name__ == "__main__":
    main()
