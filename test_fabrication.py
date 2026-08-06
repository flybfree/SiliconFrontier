"""Validate deterministic in-world fabrication and agent-facing affordances."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from worldstate import WorldState


class StubAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def build_world() -> WorldState:
    return WorldState({
        "locations": {
            "workshop": {
                "name": "Workshop",
                "connected_to": [],
                "facilities": ["fabricator"],
                "systems": {"reactor_control": {"name": "Reactor Control", "status": "ONLINE"}},
            },
            "corridor": {"name": "Corridor", "connected_to": [], "systems": {}},
        },
        "agents": {"builder": {"location": "workshop", "inventory": []}},
        "items": {
            "alloy_stack": {"name": "Alloy Plates", "material_type": "alloy", "quantity": 2, "location": "workshop", "owner": None},
            "sensor": {"name": "Sensor Array", "material_type": "sensor", "quantity": 1, "location": "workshop", "owner": None},
        },
        "recipes": {
            "atmosphere_probe": {
                "name": "Improvised Atmosphere Probe",
                "facility": "fabricator",
                "materials": {"alloy": 2, "sensor": 1},
                "output": {
                    "name": "Improvised Atmosphere Probe",
                    "description": "A rough but useful environmental scanner.",
                    "tool": {"capabilities": ["inspect_reactor_control"], "durability": 3, "reliability": 0.65},
                    "use_effect": {"inspect_system": "reactor_control"},
                },
            }
        },
    })


def main() -> None:
    world = build_world()
    parser = ActionParser(world)
    builder = StubAgent("builder")

    snapshot = world.get_snapshot_for_agent("builder")
    check("Snapshot exposes local fabricator", snapshot["facilities"] == ["fabricator"])
    check("Snapshot exposes available recipe", snapshot["available_recipes"][0]["id"] == "atmosphere_probe")
    check("Snapshot marks recipe craftable when materials and hand are free", snapshot["available_recipes"][0]["craftable_now"])
    check("Snapshot reports no missing materials when recipe is craftable", not snapshot["available_recipes"][0]["missing_materials"])

    success, message = parser.execute(builder, {"action": "ASSEMBLE", "action_target": "atmosphere_probe"})
    check("Assembly succeeds with local facility and materials", success)
    check("Assembly feedback names output", "Improvised Atmosphere Probe" in message)
    crafted = world.find_items_by_owner("builder")
    check("Crafted tool enters builder inventory", len(crafted) == 1 and crafted[0]["recipe_id"] == "atmosphere_probe")
    check("Crafted tool retains declarative capability", crafted[0]["tool"]["capabilities"] == ["inspect_reactor_control"])
    check("Assembly consumes all material stacks", "alloy_stack" not in world.items and "sensor" not in world.items)

    snapshot = world.get_snapshot_for_agent("builder")
    recipe_status = snapshot["available_recipes"][0]
    check("Snapshot reports exhausted fabrication materials", recipe_status["missing_materials"] == {"alloy": 2, "sensor": 1})
    check("Snapshot does not advertise exhausted recipe as craftable", not recipe_status["craftable_now"])

    success, message = parser.execute(builder, {"action": "USE", "action_target": "Improvised Atmosphere Probe -> reactor_control"})
    check("Target-aware fabricated tool use succeeds", success)
    success, message = parser.execute(builder, {"action": "USE", "action_target": "Improvised Atmosphere Probe"})
    check("Target-aware fabricated tool requires a target", not success and "requires target" in message)
    success, message = parser.execute(builder, {"action": "USE", "action_target": "Improvised Atmosphere Probe -> corridor"})
    check("Target-aware fabricated tool rejects an invalid target", not success and "cannot target" in message)

    success, message = parser.execute(builder, {"action": "ASSEMBLE", "action_target": "atmosphere_probe"})
    check("Assembly refuses while hand is occupied", not success and "hand is full" in message)

    world.remove_item_from_agent_inventory("builder", crafted[0]["id"])
    success, message = parser.execute(builder, {"action": "ASSEMBLE", "action_target": "atmosphere_probe"})
    check("Assembly refuses when materials are exhausted", not success and "requires" in message)

    default_data = json.loads((Path(__file__).parent / "scenarios" / "default" / "world_state.json").read_text(encoding="utf-8"))
    material_types = {
        item["material_type"]
        for item in default_data["items"].values()
        if item.get("material_type")
    }
    recipes = default_data["recipes"]
    check("Default scenario has an overlapping fabrication catalog", len(recipes) >= 6)
    for recipe_id, recipe in recipes.items():
        check(f"{recipe_id} has a compatible facility", recipe["facility"] in {
            facility
            for location in default_data["locations"].values()
            for facility in location.get("facilities", [])
        })
        check(f"{recipe_id} uses defined materials", set(recipe["materials"]).issubset(material_types))
        check(f"{recipe_id} creates a declarative tool", bool(recipe["output"].get("tool", {}).get("capabilities")) and "use_effect" in recipe["output"])


if __name__ == "__main__":
    main()
