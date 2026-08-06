"""Verify unresolved critical systems keep applying simulation pressure."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from orchestrator import Orchestrator
from socialmatrix import SocialMatrix
from worldstate import WorldState


class StubAgent:
    def __init__(self) -> None:
        self.agent_id = "engineer"
        self.name = "Engineer"
        self.condition = {"health": 100, "stress": 0, "fatigue": 0, "morale": 50}
        self.memory_buffer: list[str] = []

    def add_to_memory(self, text: str) -> None:
        self.memory_buffer.append(text)

    def adjust_condition(self, **deltas: int) -> dict[str, int]:
        changed = {}
        for key, delta in deltas.items():
            self.condition[key] += delta
            changed[key] = delta
        return changed


def main() -> None:
    world = WorldState({
        "locations": {
            "engineering": {
                "name": "Engineering",
                "connected_to": [],
                "systems": {"reactor": {"name": "Reactor", "status": "BROKEN"}},
            }
        },
        "agents": {"engineer": {"location": "engineering", "inventory": []}},
        "items": {},
    })
    agent = StubAgent()
    orchestrator = Orchestrator([agent], world, ActionParser(world), SocialMatrix())

    first = orchestrator._advance_critical_incident_pressure()
    assert first and first[0]["incident_age"] == 1
    assert agent.condition["stress"] == 0

    second = orchestrator._advance_critical_incident_pressure()
    assert second and second[0]["incident_age"] == 2
    assert agent.condition["stress"] == 2 and agent.condition["morale"] == 49
    assert orchestrator._strategic_triggers["engineer"] == "critical incident unresolved: reactor"

    world.set_system_status("engineering", "reactor", "ONLINE")
    assert not orchestrator._advance_critical_incident_pressure()
    assert not orchestrator.critical_incident_pressure
    print("[PASS] Unresolved critical incidents escalate, then clear on repair")


if __name__ == "__main__":
    main()
