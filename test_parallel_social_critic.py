"""Verify social-witness critics run concurrently but mutate state deterministically."""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from orchestrator import Orchestrator
from socialmatrix import SocialMatrix


class FakeWorld:
    relationships = {}
    suspicions = {}

    def get_visible_agents(self, _agent_id: str) -> list[str]:
        # Deliberately reverse the IDs; application should still be deterministic.
        return ["observer_b", "observer_a"]


class FakeAgent:
    def __init__(self, agent_id: str, tracker: dict, lock: threading.Lock):
        self.agent_id = agent_id
        self.name = agent_id
        self._tracker = tracker
        self._lock = lock

    def evaluate_social_exchange(self, **_kwargs):
        with self._lock:
            self._tracker["active"] += 1
            self._tracker["max_active"] = max(self._tracker["max_active"], self._tracker["active"])
        time.sleep(0.08)
        with self._lock:
            self._tracker["active"] -= 1
        return {"trust_change": 2, "affinity_change": 1, "suspicion_change": 0, "notes": "Observed cooperation."}

    @staticmethod
    def _relationship_label(_trust: int, _affinity: int, _suspicion: int) -> str:
        return "Neutral"


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> None:
    tracker = {"active": 0, "max_active": 0}
    lock = threading.Lock()
    speaker = FakeAgent("speaker", tracker, lock)
    observer_a = FakeAgent("observer_a", tracker, lock)
    observer_b = FakeAgent("observer_b", tracker, lock)
    social = SocialMatrix()
    orchestrator = Orchestrator(
        [speaker, observer_a, observer_b],
        FakeWorld(),
        action_parser=None,
        social_matrix=social,
        social_critic_max_workers=2,
    )

    orchestrator._evaluate_social_impact(speaker, "SAY", "Let's share supplies.")

    check("Witness critic requests overlap", tracker["max_active"] == 2)
    check("Witness updates are recorded as model critic work", all(
        event["source"] == "model" for event in orchestrator.social_critic_activity
    ))
    for observer_id in ("observer_a", "observer_b"):
        trust, affinity = social.get_scores(observer_id, "speaker")
        check(f"{observer_id} critic update applied", (trust, affinity) == (52, 51))


if __name__ == "__main__":
    main()
