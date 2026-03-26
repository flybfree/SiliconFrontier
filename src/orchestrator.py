"""
Orchestrator - The Temporal Controller of Silicon Frontier

Manages the simulation heartbeat, coordinates agent turns, handles social
broadcasting, and maintains the global event log.
"""

import time
from typing import Any


class Orchestrator:
    """
    Central controller for the simulation loop.

    Manages:
    - Turn ordering and synchronization
    - Social broadcasting (agents hearing/seeing each other)
    - Event logging for observation
    - Reflection triggers (memory consolidation)
    """

    def __init__(
        self,
        agents: list,
        world_state,
        action_parser,
        social_matrix,
        reflection_interval: int = 10
    ):
        """
        Initialize the orchestrator.

        Args:
            agents: List of FrontierAgent instances
            world_state: WorldState instance (ground truth)
            action_parser: ActionParser instance for validation
            social_matrix: SocialMatrix instance for relationship tracking
            reflection_interval: Number of cycles before agent reflects/summarizes memory
        """
        self.agents = agents
        self.world = world_state
        self.parser = action_parser
        self.social = social_matrix
        self.reflection_interval = reflection_interval

        # Event log for observation
        self.event_log: list[dict[str, Any]] = []

        # Cycle counter
        self.cycle_count = 0

    def broadcast_event(self, message: str, location: str, exclude_agent_id: str | None = None) -> None:
        """
        Send an event to all agents in a specific room.

        Args:
            message: The event description to add to memory buffers
            location: Room ID where the event occurred
            exclude_agent_id: Optional agent to exclude (e.g., the actor)
        """
        for agent in self.agents:
            if self.world.get_agent_location(agent.agent_id) != location:
                continue
            if exclude_agent_id and agent.agent_id == exclude_agent_id:
                continue

            agent.add_to_memory(message)

    def get_agent_by_id(self, agent_id: str) -> Any | None:
        """Find an agent by their ID."""
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        return None

    @staticmethod
    def _build_self_memory(action: str, target: str, feedback: str) -> str:
        """Create a compact per-turn memory for the acting agent."""
        target_text = f" ({target})" if target else ""
        return f"You attempted {action}{target_text}. {feedback}"

    def run_cycle(self) -> list[dict[str, Any]]:
        """
        Execute a single simulation cycle (all agents take one turn).

        Returns:
            List of action results for logging/observation
        """
        self.cycle_count += 1
        cycle_results = []

        print(f"\n{'='*50}")
        print(f"CYCLE {self.cycle_count}")
        print(f"{'='*50}")

        for agent in self.agents:
            # 1. SENSE - Get current surroundings
            world_snapshot = self.world.get_snapshot_for_agent(agent.agent_id)
            observation = agent.sense(world_snapshot)

            # 2. THINK/ACT - Get LLM response
            decision = agent.think_and_act(observation, world_snapshot)

            # Extract action data with defaults
            action = decision.get("action", "WAIT").upper()
            target = decision.get("action_target", "")
            monologue = decision.get("internal_monologue", "")
            emotional_state = decision.get("emotional_state", "Neutral")
            structured_output_status = decision.get("structured_output_status", "unknown")

            agent.set_emotional_state(emotional_state)

            # 3. LOG FOR OBSERVERS - Show reasoning and action
            print(f"\n[{agent.name}]")
            print(f"  Thoughts: {monologue}")
            print(f"  Action: {action} ({target})")
            if structured_output_status != "structured_disabled":
                print(f"  Structured Output: {structured_output_status}")

            # 4. EXECUTE - Validate and apply action
            success, feedback = self.parser.execute(agent, {"action": action, "action_target": target})
            agent.add_to_memory(self._build_self_memory(action, target, feedback))

            print(f"  Result: {feedback}")

            # Log the event
            result_entry = {
                "cycle": self.cycle_count,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "action": action,
                "target": target,
                "success": success,
                "feedback": feedback,
                "monologue": monologue,
                "emotional_state": emotional_state,
                "structured_output_status": structured_output_status
            }
            self.event_log.append(result_entry)

            # 5. SOCIAL UPDATE - Broadcast to others in the room
            current_loc = self.world.get_agent_location(agent.agent_id)

            if action == "SAY" and success:
                event_msg = f"{agent.name} said: '{target}'"
                self.broadcast_event(event_msg, current_loc, exclude_agent_id=agent.agent_id)

            elif action == "MOVE" and success:
                event_msg = f"You saw {agent.name} move to {target}"
                # Broadcast from OLD location (where they were, captured before the move)
                old_loc = world_snapshot["current_location"]["id"] if world_snapshot.get("current_location") else current_loc
                self.broadcast_event(event_msg, old_loc, exclude_agent_id=agent.agent_id)

            elif action == "PICKUP" and success:
                event_msg = f"You saw {agent.name} pick up the {target}"
                self.broadcast_event(event_msg, current_loc, exclude_agent_id=agent.agent_id)
                # Witnessed theft reduces trust in the actor
                witnesses = self.world.get_visible_agents(agent.agent_id)
                for witness_id in witnesses:
                    self.social.update_scores(
                        witness_id, agent.agent_id,
                        trust_delta=-3, affinity_delta=-1,
                        notes=f"Witnessed {agent.name} take {target}"
                    )

            elif action == "DROP" and success:
                event_msg = f"You saw {agent.name} drop the {target}"
                self.broadcast_event(event_msg, current_loc, exclude_agent_id=agent.agent_id)

            # 6. SOCIAL MATRIX UPDATE - Evaluate SAY interactions
            if action == "SAY" and success:
                self._evaluate_social_impact(agent, target)

            cycle_results.append(result_entry)

        # Check for reflection trigger
        if self.cycle_count % self.reflection_interval == 0:
            print(f"\n--- REFLECTION PHASE (Cycle {self.cycle_count}) ---")
            for agent in self.agents:
                agent_snapshot = self.world.get_snapshot_for_agent(agent.agent_id)
                new_summary = agent.reflect(agent_snapshot)
                print(f"[{agent.name}] Memory consolidated. New long-term memory:")
                print(f"  '{new_summary[:150]}...'")

        return cycle_results

    def _evaluate_social_impact(
        self,
        speaking_agent: Any,
        message: str
    ) -> None:
        """
        Evaluate how a SAY action affects relationships.

        Uses the SocialMatrix to track changes in trust/affinity based on
        observed behavior. In a full implementation, this could use an LLM
        "Critic" to evaluate the social impact.

        For now, we apply neutral updates - agents don't change feelings
        just from talking (unless there's additional logic for threats,
        promises, etc.)
        """
        # Get all agents in the same room
        my_loc = self.world.get_agent_location(speaking_agent.agent_id)
        nearby_agents = self.world.get_visible_agents(speaking_agent.agent_id)

        for other_id in nearby_agents:
            other_agent = self.get_agent_by_id(other_id)
            if not other_agent:
                continue

            # Simple heuristic: friendly messages increase affinity slightly
            message_lower = message.lower()
            trust_delta, affinity_delta = 0, 0

            if any(word in message_lower for word in ["please", "thank", "sorry", "help"]):
                affinity_delta = 2
            elif any(word in message_lower for word in ["demand", "give me", "now", "must"]):
                trust_delta = -1
                affinity_delta = -2

            if trust_delta != 0 or affinity_delta != 0:
                new_trust, new_affinity = self.social.update_scores(
                    other_id, speaking_agent.agent_id,
                    trust_delta, affinity_delta,
                    f"Agent said: '{message[:50]}...'"
                )
                print(f"[{other_agent.name}] Updated view of {speaking_agent.name}: "
                      f"T={new_trust}, A={new_affinity}")

    def run_simulation(self, rounds: int, delay_seconds: float = 0.5) -> list[list[dict[str, Any]]]:
        """
        Run the full simulation for a specified number of rounds.

        Args:
            rounds: Number of cycles to execute
            delay_seconds: Sleep time between cycles (for readability/demo)

        Returns:
            List of cycle results (list per round)
        """
        all_results = []

        print(f"\n{'='*60}")
        print("🚀 STARTING SILICON FRONTIER SIMULATION")
        print(f"   Agents: {[a.name for a in self.agents]}")
        print(f"   Rounds: {rounds}")
        print(f"{'='*60}")

        for _ in range(rounds):
            cycle_results = self.run_cycle()
            all_results.append(cycle_results)

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        print(f"\n{'='*60}")
        print("SIMULATION COMPLETE")
        print(f"   Total cycles: {self.cycle_count}")
        print(f"   Events logged: {len(self.event_log)}")
        print(f"{'='*60}")

        return all_results

    def get_event_log(self) -> list[dict[str, Any]]:
        """Get the complete event log for analysis."""
        return self.event_log

    def get_relationship_snapshot(self) -> dict[str, dict[str, Any]]:
        """Get current relationship scores."""
        return self.social.get_all_relationships()

    def inject_event(self, message: str) -> None:
        """
        Inject a global event (God Console functionality).

        This allows external intervention in the simulation.

        Args:
            message: Event to broadcast to all agents
        """
        print(f"\n📢 [GOD CONSOLE] {message}")
        for agent in self.agents:
            agent.add_to_memory(message)

    def inject_memory(self, agent_id: str, memory_text: str) -> None:
        """
        Inject a false memory into an agent's long-term storage.

        Args:
            agent_id: Target agent
            memory_text: Memory to add
        """
        agent = self.get_agent_by_id(agent_id)
        if agent:
            agent.long_term_memory += f" [Injected] {memory_text}"
            print(f"[{agent.name}] Memory injected.")

    def set_agent_location(self, agent_id: str, location: str) -> bool:
        """Manually set an agent's location (God Console)."""
        return self.world.set_agent_location(agent_id, location)
