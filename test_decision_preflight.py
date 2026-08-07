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

    capacity_release = validate(
        "Keep the station functional.", {"action": "PICKUP", "action_target": "Repair Tool"},
        {
            **base,
            "visible_items": [{"id": "repair_tool", "name": "Repair Tool", "tool": {"capabilities": ["inspect_reactor_control"]}}],
            "agent_inventory": [
                {"name": "Scrap", "inventory_slot": "hand"},
                {"name": "Reactor Key", "inventory_slot": "visible"},
                {"name": "Evidence Log", "inventory_slot": "concealed", "knowledge": "Tampering record."},
            ],
        },
    )
    assert (capacity_release["action"], capacity_release["action_target"]) == ("DROP", "Scrap")

    shared_capacity_release = validate(
        "Keep the station functional.", {"action": "PICKUP", "action_target": "Repair Tool"},
        {
            **base,
            "visible_items": [{"id": "repair_tool", "name": "Repair Tool", "tool": {"capabilities": ["inspect_reactor_control"]}}],
            "visible_agents": ["engineer"],
            "visible_agent_hands": {"engineer": []},
            "relationship_impressions": {"engineer": {"trust": 80}},
            "agent_inventory": [
                {"name": "Scrap", "inventory_slot": "hand"},
                {"name": "Reactor Key", "inventory_slot": "visible"},
                {"name": "Evidence Log", "inventory_slot": "concealed", "knowledge": "Tampering record."},
            ],
        },
    )
    assert (shared_capacity_release["action"], shared_capacity_release["action_target"]) == ("GIVE", "Scrap -> engineer")

    protected_capacity = validate(
        "Keep the station functional.", {"action": "PICKUP", "action_target": "Repair Tool"},
        {
            **base,
            "visible_items": [{"id": "repair_tool", "name": "Repair Tool", "tool": {"capabilities": ["inspect_reactor_control"]}}],
            "agent_inventory": [
                {"name": "Oxygen Scanner", "inventory_slot": "hand", "tool": {"capabilities": ["inspect_oxygen_generator"]}},
                {"name": "Reactor Key", "inventory_slot": "visible"},
                {"name": "Evidence Log", "inventory_slot": "concealed", "knowledge": "Tampering record."},
            ],
        },
    )
    assert protected_capacity["action"] == "WAIT"

    stow_to_conceal = validate(
        "Gather evidence.", {"action": "STOW", "action_target": "Probe"},
        {
            **base,
            "agent_inventory": [
                {"name": "Probe", "inventory_slot": "hand"},
                {"name": "Cells", "inventory_slot": "visible"},
            ],
        },
    )
    assert (stow_to_conceal["action"], stow_to_conceal["action_target"]) == ("CONCEAL", "Probe")

    repeated_use_agent = FrontierAgent.__new__(FrontierAgent)
    repeated_use_agent.secret_goal = "Keep the station functional."
    repeated_use_agent.completed_effects = {"USE:data module -> secure_terminal": "completed"}
    repeated_use = repeated_use_agent._validate_decision_against_telemetry(
        {"action": "USE", "action_target": "Data Module -> secure_terminal"},
        {**base, "agent_inventory": [{"name": "Data Module", "inventory_slot": "hand", "use_effect": {"memory_inject": "audit"}}]},
    )
    assert repeated_use["action"] == "WAIT"
    assert "already produced" in repeated_use["validation_note"]

    directed_repeat = repeated_use_agent._validate_decision_against_telemetry(
        {"action": "USE", "action_target": "Data Module -> secure_terminal"},
        {
            **base,
            "current_location": {"id": "command_deck", "connected_to": ["elevator_bay"]},
            "known_map": {"elevator_bay": {"explored": False}},
            "agent_inventory": [{"name": "Data Module", "inventory_slot": "hand", "use_effect": {"memory_inject": "audit"}}],
        },
    )
    assert (directed_repeat["action"], directed_repeat["action_target"]) == ("MOVE", "elevator_bay")
    assert "explore an unvisited exit" in directed_repeat["validation_note"]

    witnessed_sabotage = validate(
        "Make systems offline without being caught.", {"action": "SABOTAGE", "action_target": "reactor_control"},
        {
            **base,
            "visible_agents": ["engineer"],
            "current_location": {"id": "engineering", "connected_to": ["hydroponics_bay"]},
        },
    )
    assert (witnessed_sabotage["action"], witnessed_sabotage["action_target"]) == ("MOVE", "hydroponics_bay")

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

    invalid_tool_target = validate(
        "Keep the station functional.", {"action": "USE", "action_target": "Oxygen Scanner -> life_support_console"},
        {**base, "agent_inventory": [{"name": "Oxygen Scanner", "inventory_slot": "hand", "tool": {"capabilities": ["inspect_oxygen_generator"]}, "use_effect": {"inspect_system": "oxygen_generator"}}]},
    )
    assert invalid_tool_target["action"] == "WAIT"
    assert "oxygen_generator" in invalid_tool_target["validation_note"]

    routed_tool_target = validate(
        "Keep the station functional.", {"action": "USE", "action_target": "Plasma Wrench -> wire_spools"},
        {
            **base,
            "current_location": {"id": "storage_locker"},
            "known_systems": [{"system_id": "reactor_control", "name": "Reactor Control", "status": "ONLINE", "location_id": "engineering", "route": ["storage_locker", "engineering"]}],
            "agent_inventory": [{"name": "Plasma Wrench", "inventory_slot": "hand", "tool": {"capabilities": ["inspect_reactor_control"]}, "use_effect": {"inspect_system": "reactor_control"}}],
        },
    )
    assert (routed_tool_target["action"], routed_tool_target["action_target"]) == ("MOVE", "engineering")

    invalid_show = validate(
        "Keep the station functional.", {"action": "SHOW", "action_target": "Oxygen Scanner -> engineer"},
        {**base, "visible_agents": ["engineer"], "agent_inventory": [{"name": "Oxygen Scanner", "inventory_slot": "hand"}]},
    )
    assert invalid_show["action"] == "WAIT"

    conceal_with_full_person_slot = validate(
        "Keep the station functional.", {"action": "CONCEAL", "action_target": "Plasma Wrench"},
        {
            **base,
            "agent_inventory": [
                {"name": "Plasma Wrench", "inventory_slot": "hand"},
                {"name": "Oxygen Scanner", "inventory_slot": "concealed"},
            ],
        },
    )
    assert (conceal_with_full_person_slot["action"], conceal_with_full_person_slot["action_target"]) == ("STOW", "Plasma Wrench")

    critical_local = validate(
        "Keep the station functional.", {"action": "SAY", "action_target": "I am collecting more evidence."},
        {
            **base,
            "visible_systems": {"reactor_control": {"name": "Reactor Control", "status": "BROKEN", "required_tool_repair": "plasma_wrench"}},
            "agent_inventory": [{"name": "Plasma Wrench", "inventory_slot": "hand"}],
        },
    )
    assert (critical_local["action"], critical_local["action_target"]) == ("REPAIR", "reactor_control")

    preventive_local = validate(
        "Keep the station functional.", {"action": "SAY", "action_target": "I should collect more evidence first."},
        {
            **base,
            "visible_systems": {"reactor_control": {"name": "Reactor Control", "status": "DEGRADED", "required_tool_repair": "plasma_wrench"}},
            "agent_inventory": [{"name": "Plasma Wrench", "inventory_slot": "hand"}],
        },
    )
    assert (preventive_local["action"], preventive_local["action_target"]) == ("REPAIR", "reactor_control")

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
