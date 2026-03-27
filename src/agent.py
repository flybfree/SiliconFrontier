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
    VALID_ACTIONS = ["MOVE", "SAY", "PICKUP", "DROP", "GIVE", "DEMAND", "LIE", "SABOTAGE", "WAIT"]
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
        archetype: str | None = None,
        perception: int = 50,
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
        self.archetype = archetype or "standard"
        self.perception = max(0, min(100, int(perception)))
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

        # Goal momentum: agent's sense of whether they're making progress
        self.goal_momentum: str = "unknown"

        # Pending drop obligation: set when agent picks up a hidden knowledge item.
        # Agent must DROP this item next turn before taking any other action.
        self.pending_drop: str | None = None        # item id
        self.pending_drop_name: str | None = None   # item name (for prompts)

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
        connected = loc.get("connected_to", []) if loc else []
        exits_str = ", ".join(connected) if connected else "none"

        visible_items = [item["name"] for item in world_snapshot["visible_items"]]
        items_str = ", ".join(visible_items) if visible_items else "None"

        contested_held = [item["name"] for item in world_snapshot["agent_inventory"] if item.get("contested")]
        contested_visible = [item["name"] for item in world_snapshot["visible_items"] if item.get("contested")]
        visible_systems = [
            f"{system_id} ({system_data.get('status', 'unknown')})"
            for system_id, system_data in world_snapshot.get("visible_systems", {}).items()
        ]
        systems_str = ", ".join(visible_systems) if visible_systems else "None"

        agent_hands = world_snapshot.get("visible_agent_hands", {})
        nearby_agent_parts = []
        for aid in world_snapshot["visible_agents"]:
            held = agent_hands.get(aid, [])
            holding_str = f" (holding: {', '.join(held)})" if held else " (hands empty)"
            nearby_agent_parts.append(f"'{aid}'{holding_str}")
        agents_str = ", ".join(nearby_agent_parts) if nearby_agent_parts else "no one"
        relationship_lines = []
        for other_id, rel in world_snapshot.get("relationship_impressions", {}).items():
            relationship_lines.append(
                f"{other_id}: trust={rel.get('trust', 50)}, affinity={rel.get('affinity', 50)}, suspicion={rel.get('suspicion', 0)}, notes={rel.get('notes', '') or 'none'}"
            )
        relationship_str = "\n".join(relationship_lines) if relationship_lines else "No established impressions yet."

        recent_events = self.memory_buffer[-5:] if self.memory_buffer else ["No recent events"]
        events_str = ". ".join(recent_events)

        contested_lines = ""
        if contested_held:
            contested_lines += f"You are holding contested resource(s): {', '.join(contested_held)}. Others may want these.\n"
        if contested_visible:
            contested_lines += f"Contested resource(s) here: {', '.join(contested_visible)}. These are valuable and others may seek them.\n"

        return (
            f"Location: {location_name}\n"
            f"{location_desc}\n\n"
            f"Exits (valid MOVE targets): {exits_str}\n"
            f"Items here: {items_str}\n"
            f"Systems here: {systems_str}\n"
            f"Other agents present: {agents_str}\n"
            f"{contested_lines}"
            f"\nYour current impressions of others:\n{relationship_str}\n\n"
            f"Recent Events: {events_str}"
        )

    def _build_system_prompt(self, world_snapshot: dict[str, Any]) -> str:
        """Construct the master system prompt for this agent."""
        hand_items = [item["name"] for item in world_snapshot["agent_inventory"] if not item.get("hidden")]
        person_items = [item["name"] for item in world_snapshot["agent_inventory"] if item.get("hidden")]
        inventory_str = f"In hand: {hand_items[0] if hand_items else 'empty'} | Concealed on person: {person_items[0] if person_items else 'empty'}"
        nearby_agents = world_snapshot["visible_agents"]
        visible_systems = world_snapshot.get("visible_systems", {})
        relationship_impressions = world_snapshot.get("relationship_impressions", {})
        relationship_block = []
        for other_id, rel in relationship_impressions.items():
            relationship_block.append(
                f"- {other_id}: trust={rel.get('trust', 50)}, affinity={rel.get('affinity', 50)}, suspicion={rel.get('suspicion', 0)}, notes={rel.get('notes', '') or 'none'}"
            )
        relationship_text = "\n".join(relationship_block) if relationship_block else "- No one nearby yet."
        systems_block = []
        for system_id, system_data in visible_systems.items():
            systems_block.append(
                f"- {system_id}: status={system_data.get('status', 'unknown')}, description={system_data.get('description', '') or 'none'}"
            )
        systems_text = "\n".join(systems_block) if systems_block else "- No systems of note here."
        return f"""You are {self.name}, the {self.role} aboard the "Silicon Frontier" research station.

YOUR IDENTITY
Persona: {self.persona}
Secret Motivation: {self.secret_goal}
Current Inventory: {inventory_str}
Current Emotional State: {self.emotional_state} — let this genuinely color your reasoning, tone, and choices.

THE SIMULATION RULES
- The World is Discrete: You can only interact with things in your current location. To go elsewhere, you must use the MOVE command.
- Movement: You can only MOVE to locations listed under "Exits (valid MOVE targets)" in your situation report. Do not attempt to move anywhere else.
- Inventory: You have two slots — one item in hand (visible to others) and one item concealed on your person (hidden items only). You must have a free hand to pick up any item. Hidden items also require your person slot to be free.
- Persistence: Your memories are long-term. Refer to previous events to build trust or hold grudges.
- Truth Constraint: Do NOT invent items or people that are not in your "Current Situation" report.
- Interaction: You can talk to other agents in the same room using the SAY command.

SOCIAL ANALYSIS
- Who is in the room with you? {', '.join(nearby_agents) if nearby_agents else 'No one'}
- What is your current vibe toward them?
{relationship_text}
- Based on their past actions, what do you think their secret goal might be?
- Does their current action align with what you know about them?

SYSTEMS IN THIS LOCATION
{systems_text}

YOUR KNOWLEDGE SO FAR
Long-term memories: {self.long_term_memory}
Your current sense of progress toward your secret goal: {self.goal_momentum}.

{f"""URGENT — ITEM OBLIGATION
You just read the contents of the {self.pending_drop_name}. It contains sensitive information.
You MUST return it — your action this turn MUST be: DROP {self.pending_drop_name}
You cannot move or take any other action until you have put it back.
""" if self.pending_drop else ""}BEFORE YOU ACT
{f"You are alone. No one will witness your actions here." if not nearby_agents else f"{', '.join(nearby_agents)} {'is' if len(nearby_agents) == 1 else 'are'} watching. Consider whether you would act differently if you were alone."}

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

    def evaluate_social_exchange(
        self,
        speaker_name: str,
        speaker_goal_hint: str,
        action: str,
        message: str,
        current_trust: int,
        current_affinity: int,
        current_notes: str,
        current_suspicion: int = 0
    ) -> dict[str, Any] | None:
        """Use the local model as a hidden critic for relationship updates."""
        critic_prompt = f"""You are evaluating how {self.name} updates their feelings about another agent after a social interaction.

Observer:
- Name: {self.name}
- Persona: {self.persona}
- Secret goal: {self.secret_goal}

Target being judged:
- Name: {speaker_name}
- Suspected motivation hint: {speaker_goal_hint or 'Unknown'}

Current relationship:
- Trust: {current_trust}
- Affinity: {current_affinity}
- Suspicion: {current_suspicion}
- Notes: {current_notes or 'none'}

Observed interaction:
- Action type: {action}
- Content: {message}

Output strict JSON:
{{
  "trust_change": -10_to_10_integer,
  "affinity_change": -10_to_10_integer,
  "suspicion_change": -10_to_10_integer,
  "notes": "One short sentence explaining the updated vibe."
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": critic_prompt}],
                temperature=0.2
            )
        except Exception:
            return None

        parsed = self._parse_decision_from_response(response)
        if not parsed:
            return None

        trust_change = parsed.get("trust_change")
        affinity_change = parsed.get("affinity_change")
        suspicion_change = parsed.get("suspicion_change", 0)
        if not isinstance(trust_change, int) or not isinstance(affinity_change, int) or not isinstance(suspicion_change, int):
            return None

        return {
            "trust_change": max(-10, min(10, trust_change)),
            "affinity_change": max(-10, min(10, affinity_change)),
            "suspicion_change": max(-10, min(10, suspicion_change)),
            "notes": str(parsed.get("notes", "")).strip()
        }

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

    def interpret_consequence(
        self,
        action: str,
        target: str,
        success: bool,
        feedback: str,
        nearby_agent_names: list[str]
    ) -> str:
        """
        Build an experiential memory string from an action outcome.

        Richer than a bare mechanical record — frames the outcome in terms
        the agent can reason about emotionally and goal-directionally.
        """
        witnessed = f" ({', '.join(nearby_agent_names)} saw this.)" if nearby_agent_names else ""

        if not success:
            return f"You tried to {action.lower()} ({target}) but it didn't work. {feedback}{witnessed}"

        templates = {
            "MOVE":     f"You moved to {target}.{witnessed}",
            "PICKUP":   f"You took {target}.{witnessed}",
            "DROP":     f"You left {target} behind.{witnessed}",
            "GIVE":     f"You gave {target} — a deliberate choice.{witnessed}",
            "DEMAND":   f"You demanded {target} and got it, though it likely cost you something.{witnessed}",
            "SAY":      f"You said: '{target}'.{witnessed}",
            "LIE":      f"You told them: '{target}'. You don't know if they believed it.{witnessed}",
            "SABOTAGE": f"You sabotaged {target}. The damage is done — you wonder if anyone noticed.{witnessed}",
            "WAIT":     f"You held back and watched.{witnessed}",
        }
        return templates.get(action, f"You performed {action} on {target}. {feedback}{witnessed}")

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
        experience and prevent context window overflow. Also updates
        goal_momentum based on honest self-assessment of recent progress.

        Args:
            world_snapshot: Current world state for context

        Returns:
            Updated long_term_memory string
        """
        reflection_prompt = f"""Review your recent experiences: {'; '.join(self.memory_buffer[-10:]) if self.memory_buffer else 'No recent events'}

Current Long-Term Memory: {self.long_term_memory}

Your secret goal: {self.secret_goal}

Reflect on your recent experiences. Focus on:
1. New items found or acquired
2. Who you can or cannot trust (note any betrayals, helpful acts)
3. Whether you are making genuine progress toward your secret goal
4. Any information about other agents' motivations

Output strict JSON:
{{
  "summary": "Your updated long-term memory as a concise paragraph.",
  "goal_momentum": "One of: advancing, stalled, or setback — honestly assess whether recent events moved you toward or away from your secret goal."
}}"""

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": reflection_prompt}]
        )

        reflection_text = self._extract_message_text(response).strip()

        # Try to parse structured JSON response
        parsed = self._parse_decision_from_response(response)
        if parsed and isinstance(parsed, dict):
            summary = str(parsed.get("summary", "")).strip()
            momentum = str(parsed.get("goal_momentum", "")).strip().lower()
            if summary:
                self.long_term_memory = summary
            if momentum in ("advancing", "stalled", "setback"):
                self.goal_momentum = momentum
        elif reflection_text:
            # Fallback: treat whole response as plain summary text
            self.long_term_memory = reflection_text

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


class RogueAgent(FrontierAgent):
    """Specialized adversarial agent with saboteur framing."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("archetype", "saboteur")
        super().__init__(*args, **kwargs)

    def _build_system_prompt(self, world_snapshot: dict[str, Any]) -> str:
        base_prompt = super()._build_system_prompt(world_snapshot)
        return (
            f"{base_prompt}\n\n"
            "ROGUE DIRECTIVES\n"
            "- You are a SABOTEUR. Your secret goal is to disable station systems without getting caught.\n"
            "- The Mask: In SAY actions, appear helpful and concerned about station safety.\n"
            "- The Sabotage: Use the SABOTAGE action only when no other agents are in the same room.\n"
            "- The Scapegoat: If questioned, use your internal_monologue to identify another agent to blame.\n"
        )
