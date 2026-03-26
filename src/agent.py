"""
FrontierAgent - The Cognitive Unit of Silicon Frontier

Represents an autonomous entity that perceives its environment, reasons about
its goals, and takes actions through a local LLM inference engine.
"""

import json
from typing import Any
from openai import OpenAI


class FrontierAgent:
    """
    An autonomous agent with personality, memory, and goal-directed behavior.

    Each agent operates on the Sense -> Think -> Act -> Reflect cycle:
    1. SENSE: Filters world state to create a subjective view
    2. THINK: LLM generates internal monologue reasoning about goals
    3. ACT: LLM outputs a JSON action from a constrained set
    4. REFLECT: Periodically summarizes memory into long-term storage
    """

    # Valid actions an agent can take
    VALID_ACTIONS = ["MOVE", "SAY", "PICKUP", "DROP", "WAIT"]
    VALID_EMOTIONAL_STATE_FALLBACK = "Neutral"
    RESPONSE_SCHEMA_NAME = "silicon_frontier_agent_turn"
    STRUCTURED_STATUS_STRUCTURED = "structured_ok"
    STRUCTURED_STATUS_FALLBACK = "structured_fallback"
    STRUCTURED_STATUS_PARSE_FALLBACK = "structured_parse_fallback"
    STRUCTURED_STATUS_DISABLED = "structured_disabled"

    def __init__(
        self,
        agent_id: str,
        name: str,
        persona: str,
        secret_goal: str,
        role: str | None = None,
        llm_base_url: str = "http://192.168.3.181:1234/v1",
        llm_model: str = "unsloth/qwen3.5-35b-a3b",
        enable_structured_output: bool = False,
        api_key: str = "not-needed"
    ):
        """
        Initialize an agent with its cognitive profile.

        Args:
            agent_id: Unique identifier for the agent (e.g., "agent_001")
            name: Display name of the agent (e.g., "Captain Miller")
            persona: Description of personality and role
            secret_goal: Hidden motivation that drives conflict/behavior
            llm_base_url: URL of local OpenAI-compatible inference engine
            llm_model: Model name to use for inference
            api_key: API key (usually not needed for local models)
        """
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.secret_goal = secret_goal
        self.role = role or "crew member"
        self.enable_structured_output = enable_structured_output

        # Memory systems
        self.memory_buffer: list[str] = []  # Short-term, last N events
        self.long_term_memory: str = "I just arrived at the Silicon Frontier station."

        # LLM client configuration
        self.client = OpenAI(
            base_url=llm_base_url,
            api_key=api_key
        )
        self.llm_model = llm_model

        # Emotional state tracking (for observation)
        self.emotional_state: str = "Neutral"
        self.last_structured_output_status: str | None = None

    def sense(self, world_snapshot: dict[str, Any]) -> str:
        """
        Generate a subjective view of the world for the agent.

        This filters the objective world state into what this specific
        agent can perceive - creating a "subjective truth."

        Args:
            world_snapshot: Filtered world data from WorldState.get_snapshot_for_agent()

        Returns:
            Formatted string describing current situation for LLM prompt
        """
        loc = world_snapshot["current_location"]
        location_name = loc.get("name", "Unknown") if loc else "Unknown"
        location_desc = loc.get("description", "") if loc else ""

        visible_items = [item["name"] for item in world_snapshot["visible_items"]]
        items_str = ", ".join(visible_items) if visible_items else "None"

        nearby_agents = [f"'{aid}'" for aid in world_snapshot["visible_agents"]]
        agents_str = ", ".join(nearby_agents) if nearby_agents else "no one"

        recent_events = self.memory_buffer[-5:] if self.memory_buffer else ["No recent events"]
        events_str = ". ".join(recent_events)

        return (
            f"Location: {location_name}\n"
            f"{location_desc}\n\n"
            f"Items here: {items_str}\n"
            f"Other agents present: {agents_str}\n\n"
            f"Recent Events: {events_str}"
        )

    def _build_system_prompt(self, world_snapshot: dict[str, Any]) -> str:
        """Construct the master system prompt for this agent."""
        inventory = [item["name"] for item in world_snapshot["agent_inventory"]]
        inventory_str = ", ".join(inventory) if inventory else "nothing"
        nearby_agents = world_snapshot["visible_agents"]

        return f"""You are {self.name}, the {self.role} aboard the "Silicon Frontier" research station.

YOUR IDENTITY
Persona: {self.persona}
Secret Motivation: {self.secret_goal}
Current Inventory: {inventory_str}

THE SIMULATION RULES
- The World is Discrete: You can only interact with things in your current location. To go elsewhere, you must use the MOVE command.
- Persistence: Your memories are long-term. Refer to previous events to build trust or hold grudges.
- Truth Constraint: Do NOT invent items or people that are not in your "Current Situation" report.
- Interaction: You can talk to other agents in the same room using the SAY command.

SOCIAL ANALYSIS
- Who is in the room with you? {', '.join(nearby_agents) if nearby_agents else 'No one'}
- Based on their past actions, what do you think their secret goal might be?
- Does their current action align with what you know about them?

YOUR KNOWLEDGE SO FAR
Long-term memories: {self.long_term_memory}

OUTPUT FORMAT
You must respond strictly in JSON format with this structure:
{{
  "internal_monologue": "A detailed thought process analyzing your secret goal vs. the situation. Consider who you can trust.",
  "action": "ONE_OF: [{', '.join(self.VALID_ACTIONS)}]",
  "action_target": "The location, message, or item name for your action.",
  "emotional_state": "A single word describing your current mood."
}}

Remember: Your internal_monologue should reveal your true reasoning, which may differ from what you say to others.
"""

    def _normalize_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Return a safe decision payload that conforms to the expected schema."""
        if not isinstance(decision, dict):
            decision = {}

        action = str(decision.get("action", "WAIT")).upper()
        if action not in self.VALID_ACTIONS:
            action = "WAIT"

        target = decision.get("action_target", "")
        if target is None:
            target = ""
        target = str(target)

        monologue = decision.get("internal_monologue", "")
        if monologue is None:
            monologue = ""
        monologue = str(monologue).strip()

        emotional_state = decision.get("emotional_state", self.VALID_EMOTIONAL_STATE_FALLBACK)
        if emotional_state is None:
            emotional_state = self.VALID_EMOTIONAL_STATE_FALLBACK
        emotional_state = str(emotional_state).strip() or self.VALID_EMOTIONAL_STATE_FALLBACK
        emotional_state = emotional_state.split()[0]

        return {
            "internal_monologue": monologue,
            "action": action,
            "action_target": target,
            "emotional_state": emotional_state,
            "structured_output_status": self.last_structured_output_status or self.STRUCTURED_STATUS_DISABLED
        }

    def _build_response_schema(self) -> dict[str, Any]:
        """Return the ideal structured-output schema for an agent turn."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.RESPONSE_SCHEMA_NAME,
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "internal_monologue",
                        "action",
                        "action_target",
                        "emotional_state"
                    ],
                    "properties": {
                        "internal_monologue": {
                            "type": "string",
                            "minLength": 1
                        },
                        "action": {
                            "type": "string",
                            "enum": self.VALID_ACTIONS
                        },
                        "action_target": {
                            "type": "string"
                        },
                        "emotional_state": {
                            "type": "string",
                            "pattern": "^[A-Za-z][A-Za-z_-]*$",
                            "minLength": 1,
                            "maxLength": 32
                        }
                    }
                }
            }
        }

    @staticmethod
    def _error_suggests_unsupported_schema(exc: Exception) -> bool:
        """Heuristic for servers that reject structured-output fields."""
        message = str(exc).lower()
        schema_markers = [
            "response_format",
            "json_schema",
            "schema",
            "strict",
            "structured output",
            "structured-output",
            "invalid structured output configuration",
            "data/type",
            "must be equal to one of the allowed values",
            "must match a schema in anyof",
            "unsupported",
            "not supported",
            "unknown parameter",
            "extra_forbidden",
            "invalid request"
        ]
        return any(marker in message for marker in schema_markers)

    def _request_turn_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        use_response_schema: bool
    ):
        """Create a chat completion, optionally requesting structured output."""
        request_kwargs: dict[str, Any] = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        if use_response_schema:
            request_kwargs["response_format"] = self._build_response_schema()

        return self.client.chat.completions.create(**request_kwargs)

    @staticmethod
    def _extract_message_text(response: Any) -> str:
        """Best-effort extraction of text content from OpenAI-compatible responses."""
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", "")

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                else:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str):
                        text_parts.append(part_text)
            if text_parts:
                return "\n".join(text_parts)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
        return str(content or "")

    def _parse_decision_from_response(self, response: Any) -> dict[str, Any] | None:
        """Parse a decision object from a model response."""
        content = self._extract_message_text(response)
        if not content:
            return None

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    def think_and_act(self, observation: str, world_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute the Think/Act phase by calling the LLM.

        Args:
            observation: The subjective world view from sense()
            world_snapshot: The world snapshot from WorldState.get_snapshot_for_agent()

        Returns:
            Parsed JSON response with internal_monologue, action, action_target, emotional_state
        """
        snapshot = world_snapshot or {"agent_inventory": [], "visible_agents": []}
        system_prompt = self._build_system_prompt(snapshot)

        user_prompt = f"Current Situation:\n{observation}\n\nWhat do you do next?"

        if self.enable_structured_output:
            try:
                response = self._request_turn_completion(
                    system_prompt,
                    user_prompt,
                    use_response_schema=True
                )
                self.last_structured_output_status = self.STRUCTURED_STATUS_STRUCTURED
            except Exception as exc:
                if not self._error_suggests_unsupported_schema(exc):
                    raise
                self.last_structured_output_status = self.STRUCTURED_STATUS_FALLBACK
                self.enable_structured_output = False
                response = self._request_turn_completion(
                    system_prompt,
                    user_prompt,
                    use_response_schema=False
                )
        else:
            self.last_structured_output_status = self.STRUCTURED_STATUS_DISABLED
            response = self._request_turn_completion(
                system_prompt,
                user_prompt,
                use_response_schema=False
            )

        parsed_decision = self._parse_decision_from_response(response)
        if parsed_decision is not None:
            return self._normalize_decision(parsed_decision)

        if self.last_structured_output_status == self.STRUCTURED_STATUS_STRUCTURED:
            self.last_structured_output_status = self.STRUCTURED_STATUS_PARSE_FALLBACK
            fallback_response = self._request_turn_completion(
                system_prompt,
                user_prompt,
                use_response_schema=False
            )
            parsed_decision = self._parse_decision_from_response(fallback_response)
            if parsed_decision is not None:
                return self._normalize_decision(parsed_decision)

        return self._normalize_decision({})

    def reflect(self, world_snapshot: dict[str, Any]) -> str:
        """
        Condense short-term memory into long-term memory.

        Called periodically (e.g., every 10 cycles) to compress the agent's
        experience and prevent context window overflow.

        Args:
            world_snapshot: Current world state for context

        Returns:
            Updated long_term_memory string
        """
        reflection_prompt = f"""Review your recent experiences: {'; '.join(self.memory_buffer[-10:]) if self.memory_buffer else 'No recent events'}

Current Long-Term Memory: {self.long_term_memory}

Task: Write a concise summary of the most important things you've learned. Focus on:
1. New items found or acquired
2. Who you can or cannot trust (note any betrayals, helpful acts)
3. Progress toward your secret goal
4. Any rumors or information about other agents' motivations

Output only the updated summary, nothing else."""

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": reflection_prompt}]
        )

        self.long_term_memory = response.choices[0].message.content
        self.memory_buffer = []  # Clear buffer after consolidation
        return self.long_term_memory

    def add_to_memory(self, event: str) -> None:
        """Add an event to the short-term memory buffer (max 10 events)."""
        self.memory_buffer.append(event)
        if len(self.memory_buffer) > 10:
            self.memory_buffer.pop(0)

    def set_emotional_state(self, state: str) -> None:
        """Update the agent's current emotional state."""
        self.emotional_state = state

    def __repr__(self) -> str:
        return f"FrontierAgent(id={self.agent_id}, name={self.name})"
