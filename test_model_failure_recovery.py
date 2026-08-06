"""Checks that transient LLM failures do not stop the simulation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent import FrontierAgent


class _FailingCompletions:
    def create(self, **_kwargs):
        raise ConnectionError("test endpoint temporarily unavailable")


class _FailingClient:
    chat = type("_Chat", (), {"completions": _FailingCompletions()})()


def _agent() -> FrontierAgent:
    agent = FrontierAgent.__new__(FrontierAgent)
    agent.name = "Test Agent"
    agent.persona = "A careful tester"
    agent.secret_goal = "Keep the test world stable"
    agent.long_term_memory = "Known stable memory."
    agent.memory_buffer = ["A recent event"]
    agent.goal_momentum = "stalled"
    agent.emotional_state = "Neutral"
    agent.enable_structured_output = False
    agent.llm_base_url = "http://action.example/v1"
    agent.llm_model = "action-model"
    agent.client = _FailingClient()
    agent.strategic_reasoning_base_url = "http://strategic.example/v1"
    agent.strategic_reasoning_model = "strategic-model"
    agent.strategic_client = _FailingClient()
    agent.last_model_error = None
    agent.last_reflection_result = None
    return agent


def main() -> None:
    agent = _agent()
    agent._build_system_prompt = lambda _snapshot: "system prompt"
    decision = agent.think_and_act("observation", {"agent_inventory": [], "visible_agents": []})
    assert decision["action"] == "WAIT"
    assert decision["structured_output_status"] == FrontierAgent.STRUCTURED_STATUS_MODEL_FALLBACK
    assert agent.last_model_error["role"] == "action"
    assert agent.last_model_error["endpoint"] == "http://action.example/v1"

    memory = agent.reflect({})
    assert memory == "Known stable memory."
    assert agent.last_reflection_result["source"] == "fallback"
    assert agent.last_reflection_result["role"] == "reflection"
    assert agent.last_reflection_result["endpoint"] == "http://strategic.example/v1"
    print("[PASS] Action and reflection model failures safely fall back with diagnostics")


if __name__ == "__main__":
    main()
