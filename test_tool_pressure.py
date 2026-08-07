"""Verify tool pressure causes deterministic scenario state transitions."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from orchestrator import Orchestrator
from socialmatrix import SocialMatrix
from worldstate import WorldState


class StubAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.name = agent_id
        self.memory_buffer: list[str] = []

    def add_to_memory(self, text: str) -> None:
        self.memory_buffer.append(text)


def main() -> None:
    world = WorldState({
        "locations": {
            "engineering": {
                "name": "Engineering",
                "connected_to": [],
                "status_effects": [],
                "systems": {"reactor_control": {"name": "Reactor", "status": "ONLINE"}},
            }
        },
        "agents": {"unit7": {"location": "engineering", "inventory": []}},
        "items": {},
    })
    agent = StubAgent("unit7")
    orchestrator = Orchestrator(
        [agent], world, ActionParser(world), SocialMatrix(),
        progression_config={
            "enabled": True,
            "stalled_actions": [],
            "progress_actions": [],
            "thresholds": [{
                "id": "reactor_degraded",
                "after_stall_score": 2,
                "system_updates": [{"location": "engineering", "system_id": "reactor_control", "status": "DEGRADED"}],
            }],
        },
    )
    fired = orchestrator._update_progression_pressure(
        agent, "USE", "Improvised Reactor Probe -> reactor_control", True, {"pressure_delta": 2},
    )
    assert fired and fired[0]["target"] == "reactor_degraded"
    assert world.get_location_systems("engineering")["reactor_control"]["status"] == "DEGRADED"
    world.set_system_status("engineering", "reactor_control", "BROKEN")
    orchestrator._apply_progression_effects({
        "system_updates": [{"location": "engineering", "system_id": "reactor_control", "status": "DEGRADED"}],
    })
    assert world.get_location_systems("engineering")["reactor_control"]["status"] == "BROKEN"
    print("[PASS] Tool pressure deterministically degrades the configured system")


if __name__ == "__main__":
    main()
