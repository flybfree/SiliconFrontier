"""
Test: agent SABOTAGE and REPAIR actions for system status changes.

Test 1 — no tool required:
  life_support_console (command_deck) — sabotage then repair without any item.

Test 2 — tool required:
  reactor_control (engineering) — sabotage requires nothing extra (just be alone),
  repair requires plasma_wrench in hand.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from worldstate import WorldState
from actionparser import ActionParser


# ---------------------------------------------------------------------------
# Minimal stub agent
# ---------------------------------------------------------------------------
class StubAgent:
    def __init__(self, agent_id: str, inventory: list[str] | None = None):
        self.agent_id = agent_id
        self.name = agent_id
        self._inventory = inventory or []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(label: str, success: bool, result: str, expect_success: bool):
    ok = success == expect_success
    status = PASS if ok else FAIL
    print(f"  [{status}] {label}")
    print(f"         result={result!r}")
    if not ok:
        print(f"         expected success={expect_success}, got {success}")


# ---------------------------------------------------------------------------
# Build world
# ---------------------------------------------------------------------------
world_data = {
    "locations": {
        "command_deck": {
            "name": "Command Deck",
            "connected_to": [],
            "status_effects": [],
            "systems": {
                "life_support_console": {
                    "name": "Life Support Console",
                    "status": "ONLINE",
                    "description": "Controls oxygen routing."
                    # no required_tool
                }
            }
        },
        "engineering": {
            "name": "Engineering",
            "connected_to": [],
            "status_effects": [],
            "systems": {
                "reactor_control": {
                    "name": "Reactor Control Array",
                    "status": "ONLINE",
                    "description": "Monitors and adjusts power core output.",
                    "required_tool": "plasma_wrench"
                }
            }
        }
    },
    "items": {
        "plasma_wrench": {
            "name": "Plasma Wrench",
            "location": "engineer_torres",   # in agent's possession (owner = agent_id)
            "owner": "engineer_torres",
            "portable": True
        },
        "hidden_log": {
            "name": "Hidden Log",
            "location": "command_deck",
            "owner": None,
            "portable": True,
            "hidden": True,
            "knowledge": "The reactor was accessed with an override code.",
            "on_read": {"force_drop": True}
        }
    },
    "agents": {
        "unit7": {"location": "command_deck"},
        "engineer_torres": {"location": "engineering"}
    },
    "relationships": {},
    "suspicions": {}
}

world = WorldState(world_data)
parser = ActionParser(world)

# unit7 is archetype=saboteur and starts in engineering for this test
# engineer_torres holds the plasma_wrench for the repair test
unit7 = StubAgent("unit7")
unit7.archetype = "saboteur"

engineer = StubAgent("engineer_torres", inventory=["plasma_wrench"])
engineer.archetype = "standard"

captain = StubAgent("captain_rao")
captain.archetype = "standard"

# Override _hand_items to use stub inventory
def _hand_items(agent_id):
    if agent_id == "engineer_torres":
        return [{"id": "plasma_wrench", "name": "Plasma Wrench"}]
    return []

parser._hand_items = _hand_items


# ---------------------------------------------------------------------------
# TEST 1 — life_support_console (no tool required)
# ---------------------------------------------------------------------------
print("\n=== TEST 1: life_support_console (no tool required) ===")

# 1a. SABOTAGE while alone — should succeed
ok, msg = parser._handle_sabotage(unit7, "life_support_console", {})
check("SABOTAGE life_support_console (alone, saboteur)", ok, msg, expect_success=True)
status_after = world.get_location_systems("command_deck")["life_support_console"]["status"]
print(f"         status after sabotage: {status_after}")

# 1b. SABOTAGE again (already BROKEN) — should fail
ok, msg = parser._handle_sabotage(unit7, "life_support_console", {})
check("SABOTAGE again (already broken)", ok, msg, expect_success=False)

# 1c. REPAIR without tool (none required) — should succeed
#     any agent can repair; use unit7 still in command_deck
ok, msg = parser._handle_repair(unit7, "life_support_console", {})
check("REPAIR life_support_console (no tool needed, any agent)", ok, msg, expect_success=True)
status_after = world.get_location_systems("command_deck")["life_support_console"]["status"]
print(f"         status after repair: {status_after}")

# 1d. REPAIR again (already ONLINE) — should fail
ok, msg = parser._handle_repair(unit7, "life_support_console", {})
check("REPAIR again (already online)", ok, msg, expect_success=False)


# ---------------------------------------------------------------------------
# TEST 2 — reactor_control (requires plasma_wrench)
# ---------------------------------------------------------------------------
print("\n=== TEST 2: reactor_control (requires plasma_wrench) ===")

# Move unit7 to engineering, move engineer_torres out so unit7 is alone
world._data["agents"]["unit7"]["location"] = "engineering"
world._data["agents"]["engineer_torres"]["location"] = "elevator_bay"

# 2a. SABOTAGE while alone — should succeed (sabotage does not check tool)
ok, msg = parser._handle_sabotage(unit7, "reactor_control", {})
check("SABOTAGE reactor_control (alone, saboteur)", ok, msg, expect_success=True)
status_after = world.get_location_systems("engineering")["reactor_control"]["status"]
print(f"         status after sabotage: {status_after}")

# Move engineer_torres back to engineering and unit7 away
world._data["agents"]["engineer_torres"]["location"] = "engineering"
world._data["agents"]["unit7"]["location"] = "command_deck"

# 2b. REPAIR without the wrench (simulated) — should fail
parser._hand_items = lambda _: []
ok, msg = parser._handle_repair(engineer, "reactor_control", {})
check("REPAIR reactor_control WITHOUT plasma_wrench", ok, msg, expect_success=False)

# 2c. REPAIR with the wrench — should succeed
parser._hand_items = _hand_items
ok, msg = parser._handle_repair(engineer, "reactor_control", {})
check("REPAIR reactor_control WITH plasma_wrench", ok, msg, expect_success=True)
status_after = world.get_location_systems("engineering")["reactor_control"]["status"]
print(f"         status after repair: {status_after}")


# ---------------------------------------------------------------------------
# TEST 3 — SABOTAGE blocked when another agent is present
# ---------------------------------------------------------------------------
print("\n=== TEST 3: SABOTAGE blocked when not alone ===")

# Put engineer_torres in command_deck alongside unit7, reset system to ONLINE
world._data["agents"]["engineer_torres"]["location"] = "command_deck"
world._data["agents"]["unit7"]["location"] = "command_deck"
world._data["locations"]["command_deck"]["systems"]["life_support_console"]["status"] = "ONLINE"

ok, msg = parser._handle_sabotage(unit7, "life_support_console", {})
check("SABOTAGE blocked (engineer_torres also in command_deck)", ok, msg, expect_success=False)


# ---------------------------------------------------------------------------
# TEST 4 — hidden information can be read and shown
# ---------------------------------------------------------------------------
print("\n=== TEST 4: READ/SHOW hidden information ===")

world._data["agents"]["unit7"]["location"] = "command_deck"
world._data["agents"]["engineer_torres"]["location"] = "command_deck"

ok, msg = parser.execute(unit7, {"action": "READ", "action_target": "Hidden Log"})
check("READ Hidden Log records a known fact", ok, msg, expect_success=True)
unit7_facts = world.get_known_facts("unit7")
print(f"         unit7 known facts: {list(unit7_facts)}")

ok, msg = parser.execute(unit7, {"action": "SHOW", "action_target": "Hidden Log -> engineer_torres"})
check("SHOW Hidden Log shares the known fact", ok, msg, expect_success=True)
engineer_facts = world.get_known_facts("engineer_torres")
print(f"         engineer_torres known facts: {list(engineer_facts)}")

shared = "item:hidden_log" in engineer_facts
status = PASS if shared else FAIL
print(f"  [{status}] engineer_torres received item:hidden_log")

print()
