"""Focused checks for the optional strategic-reasoning review phase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestrator import Orchestrator


class _World:
    def get_snapshot_for_agent(self, agent_id: str) -> dict:
        return {"agent_id": agent_id}


class _Agent:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.name = agent_id.title()
        self.strategic_reasoning_model = "reasoning-test-model"
        self.strategic_plan: dict = {}
        self.last_strategic_review_cycle = None
        self.last_strategic_trigger = None

    def propose_strategy(self, _snapshot: dict, trigger: str) -> dict:
        return {
            "source": "model",
            "plan": {"goal": f"Respond to {trigger}", "subgoals": ["Coordinate"]},
        }

    def apply_strategic_plan(self, plan: dict, cycle: int, trigger: str) -> None:
        self.strategic_plan = plan
        self.last_strategic_review_cycle = cycle
        self.last_strategic_trigger = trigger


def main() -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.agents = [_Agent("alpha"), _Agent("bravo")]
    orchestrator.world = _World()
    orchestrator.cycle_count = 6
    orchestrator.strategic_review_interval = 6
    orchestrator.strategic_max_workers = 2
    orchestrator.strategic_activity = []
    orchestrator._strategic_triggers = {"bravo": "fabrication attempt blocked"}

    orchestrator._run_strategic_reviews()

    assert len(orchestrator.strategic_activity) == 2
    assert orchestrator.agents[0].last_strategic_trigger == "periodic strategic review"
    assert orchestrator.agents[1].last_strategic_trigger == "fabrication attempt blocked"
    assert orchestrator.agents[1].strategic_plan["goal"].startswith("Respond to")
    print("[PASS] Strategic reviews run in a bounded parallel phase and preserve explicit triggers")


if __name__ == "__main__":
    main()
