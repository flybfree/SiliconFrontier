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
    assert (full["action"], full["action_target"]) == ("CONCEAL", "Probe")

    assembly = validate(
        "Gather evidence.", {"action": "ASSEMBLE", "action_target": "probe"},
        {**base, "agent_inventory": [{"name": "Probe", "hidden": False}], "available_recipes": [{"id": "probe"}]},
    )
    assert (assembly["action"], assembly["action_target"]) == ("STOW", "Probe")

    unavailable_assembly = validate(
        "Gather evidence.", {"action": "ASSEMBLE", "action_target": "probe"},
        {**base, "available_recipes": [{"id": "probe", "materials_ready": False, "missing_materials": {"alloy": 2}}]},
    )
    assert unavailable_assembly["action"] == "WAIT"
    assert "alloy x2" in unavailable_assembly["validation_note"]

    ready = validate(
        "Gather evidence.", {"action": "USE", "action_target": "Scanner -> oxygen_generator"},
        {**base, "agent_inventory": [{"name": "Scanner", "inventory_slot": "visible", "use_effect": {"reveals": "baseline"}}]},
    )
    assert (ready["action"], ready["action_target"]) == ("READY", "Scanner")

    produce = validate(
        "Gather evidence.", {"action": "USE", "action_target": "Scanner -> oxygen_generator"},
        {**base, "agent_inventory": [{"name": "Scanner", "inventory_slot": "concealed", "use_effect": {"reveals": "baseline"}}]},
    )
    assert (produce["action"], produce["action_target"]) == ("PRODUCE", "Scanner")

    ready_with_hand = validate(
        "Gather evidence.", {"action": "READY", "action_target": "Scanner"},
        {**base, "agent_inventory": [
            {"name": "Wrench", "inventory_slot": "hand"},
            {"name": "Scanner", "inventory_slot": "visible", "use_effect": {"reveals": "baseline"}},
        ]},
    )
    assert (ready_with_hand["action"], ready_with_hand["action_target"]) == ("CONCEAL", "Wrench")

    conceal_visible = validate(
        "Gather evidence.", {"action": "CONCEAL", "action_target": "Scanner"},
        {**base, "agent_inventory": [{"name": "Scanner", "inventory_slot": "visible"}]},
    )
    assert (conceal_visible["action"], conceal_visible["action_target"]) == ("READY", "Scanner")

    inert = validate(
        "Gather evidence.", {"action": "USE", "action_target": "Sensor Array -> reactor_control"},
        {**base, "agent_inventory": [{"name": "Sensor Array", "inventory_slot": "hand"}]},
    )
    assert inert["action"] == "WAIT"

    critical_local = validate(
        "Keep the station functional.", {"action": "SAY", "action_target": "I am collecting more evidence."},
        {
            **base,
            "visible_systems": {"reactor_control": {"name": "Reactor Control", "status": "BROKEN", "required_tool_repair": "plasma_wrench"}},
            "agent_inventory": [{"name": "Plasma Wrench", "inventory_slot": "hand"}],
        },
    )
    assert (critical_local["action"], critical_local["action_target"]) == ("REPAIR", "reactor_control")

    critical_remote = validate(
        "Keep the station functional.", {"action": "WAIT", "action_target": ""},
        {
            **base,
            "current_location": {"id": "command_deck"},
            "known_systems": [{"system_id": "reactor_control", "name": "Reactor Control", "status": "BROKEN", "required_tool_repair": "plasma_wrench", "location_id": "engineering", "route": ["command_deck", "elevator_bay", "engineering"]}],
            "agent_inventory": [{"name": "Plasma Wrench", "inventory_slot": "hand"}],
        },
    )
    assert (critical_remote["action"], critical_remote["action_target"]) == ("MOVE", "elevator_bay")

    critical_demand = validate(
        "Keep the station functional.", {"action": "WAIT", "action_target": ""},
        {
            **base,
            "visible_systems": {"reactor_control": {"name": "Reactor Control", "status": "BROKEN", "required_tool_repair": "plasma_wrench"}},
            "visible_agent_inventory": {"engineer": [{"name": "Plasma Wrench", "slot": "hand"}]},
        },
    )
    assert (critical_demand["action"], critical_demand["action_target"]) == ("DEMAND", "plasma_wrench -> engineer")

    demand_with_full_hand = validate(
        "Keep the station functional.", {"action": "DEMAND", "action_target": "Plasma Wrench -> engineer"},
        {
            **base,
            "agent_inventory": [{"name": "Reactor Key", "inventory_slot": "hand"}],
            "visible_agents": ["engineer"],
            "visible_agent_inventory": {"engineer": [{"name": "Plasma Wrench", "slot": "hand"}]},
        },
    )
    assert (demand_with_full_hand["action"], demand_with_full_hand["action_target"]) == ("STOW", "Reactor Key")
    print("[PASS] Goal guard and inventory preflight correct invalid turns")


if __name__ == "__main__":
    main()
