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
        reflection_interval: int = 5
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
        self.social.initialize_from_world(self.world)
        self.social.ensure_agent_network([agent.agent_id for agent in self.agents])
        self.social.sync_to_world()

        # Event log for observation
        self.event_log: list[dict[str, Any]] = []
        self.system_incidents: list[dict[str, Any]] = []
        self.proximity_log: list[dict[str, Any]] = []

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

    def _sync_relationships(self) -> None:
        """Keep world-state relationship data aligned with the social matrix."""
        self.social.sync_to_world()

    def _record_proximity_snapshot(self) -> None:
        """Record who was where at the start of a cycle for later audits."""
        snapshot = {
            "cycle": self.cycle_count,
            "rooms": {}
        }
        for loc_id in self.world.locations.keys():
            snapshot["rooms"][loc_id] = [
                agent.agent_id for agent in self.agents
                if self.world.get_agent_location(agent.agent_id) == loc_id
            ]
        self.proximity_log.append(snapshot)

    def _record_system_incident(self, agent: Any, location: str, system_id: str) -> None:
        """Store a sabotage incident with recent room occupancy context."""
        last_snapshot = self.proximity_log[-1] if self.proximity_log else {"rooms": {}}
        prior_occupants = last_snapshot.get("rooms", {}).get(location, [])
        incident = {
            "cycle": self.cycle_count,
            "location": location,
            "system_id": system_id,
            "actor_id": agent.agent_id,
            "actor_name": agent.name,
            "prior_occupants": prior_occupants
        }
        self.system_incidents.append(incident)

    def _inject_snitch_memory(
        self,
        actor: Any,
        location: str,
        system_id: str,
        threshold: int = 70
    ) -> None:
        """High-perception witnesses can receive covert suspicion memories."""
        for witness in self.agents:
            if witness.agent_id == actor.agent_id:
                continue
            if self.world.get_agent_location(witness.agent_id) != location:
                continue
            if getattr(witness, "perception", 50) < threshold:
                continue
            witness.add_to_memory(
                f"You noticed {actor.name} fiddling with {system_id}, though they tried to hide it."
            )
            self.social.update_suspicion(witness.agent_id, actor.agent_id, 12)
        self._sync_relationships()

    @staticmethod
    def _witness_reaction_tag(trust: int, suspicion: int, action: str) -> str:
        """Return an emotional tag to append to a witness memory, based on relationship state."""
        if suspicion > 60:
            return " You noted this with suspicion."
        if action == "PICKUP":
            if trust < 40:
                return " It struck you as opportunistic."
            if trust > 65:
                return " It seemed harmless enough coming from them."
        if action == "GIVE":
            if trust > 65:
                return " It felt like a genuine gesture."
            return " You wondered what they were expecting in return."
        if action == "DEMAND":
            if trust > 60:
                return " Coming from them, it felt out of character."
            return " It confirmed what you already felt about them."
        if action in ("SAY", "LIE"):
            if suspicion > 40:
                return " You weren't sure you believed it."
            if trust > 65:
                return " It sounded sincere."
        return ""

    def _broadcast_with_reactions(
        self,
        base_message: str,
        actor_id: str,
        action: str,
        location: str
    ) -> None:
        """
        Broadcast an action to all witnesses in a location, appending an
        emotionally-toned reaction tag based on each witness's relationship
        to the actor.
        """
        for witness in self.agents:
            if self.world.get_agent_location(witness.agent_id) != location:
                continue
            if witness.agent_id == actor_id:
                continue
            trust, _ = self.social.get_scores(witness.agent_id, actor_id)
            suspicion = self.social.get_suspicion(witness.agent_id, actor_id)
            tag = self._witness_reaction_tag(trust, suspicion, action)
            witness.add_to_memory(f"{base_message}{tag}")

    @staticmethod
    def _extract_social_target(target: str) -> tuple[str, str] | None:
        """Parse an action target into (item_or_message, target_agent_id)."""
        for separator in ["->", "|", "@", ":"]:
            if separator in target:
                left, right = target.split(separator, 1)
                left = left.strip()
                right = right.strip()
                if left and right:
                    return left, right
        return None

    def _apply_item_effect(self, agent: Any, item: dict) -> None:
        """Apply an item's effect fields to the picking agent, then delete it if consumable."""
        effect = item.get("effect")
        if not effect:
            return

        item_name = item.get("name", item.get("id", "item"))

        perception_delta = effect.get("perception_delta", 0)
        if perception_delta:
            agent.perception = max(0, min(100, agent.perception + perception_delta))
            direction = "sharpened" if perception_delta > 0 else "dulled"
            agent.add_to_memory(f"[Effect] Your perception has {direction} ({perception_delta:+d}) after {item_name}.")
            print(f"  [Effect] {agent.name} perception {perception_delta:+d} → {agent.perception}")

        forced_state = effect.get("emotional_state")
        if forced_state:
            agent.set_emotional_state(forced_state)
            agent.add_to_memory(f"[Effect] {item_name} left you feeling {forced_state}.")
            print(f"  [Effect] {agent.name} emotional state → {forced_state}")

        memory_text = effect.get("memory_inject")
        if memory_text:
            agent.add_to_memory(f"[Effect] {memory_text}")
            print(f"  [Effect] {agent.name} memory injected: {memory_text[:80]}...")

        if item.get("consumable"):
            self.world.delete_item(item["id"])
            agent.add_to_memory(f"[Consumed] The {item_name} is gone — used up.")
            print(f"  [Consumed] {item_name} removed from world.")

    def _heuristic_social_update(self, action: str, message: str) -> tuple[int, int]:
        """Fallback heuristic if the social critic is unavailable."""
        message_lower = message.lower()
        trust_delta, affinity_delta = 0, 0

        if action == "GIVE":
            return 3, 6
        if action == "DEMAND":
            return -4, -6
        if action == "LIE":
            return -5, -4
        if any(word in message_lower for word in ["please", "thank", "sorry", "help"]):
            affinity_delta = 2
        elif any(word in message_lower for word in ["demand", "give me", "now", "must"]):
            trust_delta = -1
            affinity_delta = -2

        return trust_delta, affinity_delta

    def _heuristic_suspicion_update(self, action: str, message: str) -> int:
        """Fallback heuristic for hidden suspicion changes."""
        if action == "SABOTAGE":
            return 10
        if action == "LIE":
            return 6
        if action == "DEMAND":
            return 4
        if "blame" in message.lower():
            return 3
        return 0

    def _apply_social_critic(
        self,
        observer_agent: Any,
        speaker_agent: Any,
        action: str,
        message: str
    ) -> None:
        """Ask an observer-specific hidden critic to update vibe scores."""
        current_rel = self.social.relationships.get(observer_agent.agent_id, {}).get(speaker_agent.agent_id, {})
        current_trust = int(current_rel.get("trust", 50))
        current_affinity = int(current_rel.get("affinity", 50))
        current_notes = current_rel.get("notes", "")
        current_suspicion = self.social.get_suspicion(observer_agent.agent_id, speaker_agent.agent_id)

        critic_update = observer_agent.evaluate_social_exchange(
            speaker_name=speaker_agent.name,
            speaker_goal_hint=speaker_agent.secret_goal,
            action=action,
            message=message,
            current_trust=current_trust,
            current_affinity=current_affinity,
            current_notes=current_notes,
            current_suspicion=current_suspicion
        )

        if critic_update:
            trust_delta = critic_update["trust_change"]
            affinity_delta = critic_update["affinity_change"]
            suspicion_delta = critic_update.get("suspicion_change", 0)
            notes = critic_update.get("notes", "")
        else:
            trust_delta, affinity_delta = self._heuristic_social_update(action, message)
            suspicion_delta = self._heuristic_suspicion_update(action, message)
            notes = f"Observed {action.lower()}: {message[:80]}"

        if trust_delta != 0 or affinity_delta != 0 or notes:
            self.social.update_scores(
                observer_agent.agent_id,
                speaker_agent.agent_id,
                trust_delta,
                affinity_delta,
                notes
            )
            if suspicion_delta != 0:
                self.social.update_suspicion(
                    observer_agent.agent_id,
                    speaker_agent.agent_id,
                    suspicion_delta
                )
            self._sync_relationships()

    def run_cycle(self) -> list[dict[str, Any]]:
        """
        Execute a single simulation cycle (all agents take one turn).

        Returns:
            List of action results for logging/observation
        """
        self.cycle_count += 1
        cycle_results = []
        self._record_proximity_snapshot()

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

            # Enforce pending_drop obligation: agent must DROP the hidden item this turn
            if agent.pending_drop and agent.pending_drop_name:
                if action != "DROP" or agent.pending_drop_name.lower() not in target.lower():
                    action = "DROP"
                    target = agent.pending_drop_name
                    print(f"  [Obligation enforced] {agent.name} must DROP {agent.pending_drop_name}")

            agent.set_emotional_state(emotional_state)

            # 3. LOG FOR OBSERVERS - Show reasoning and action
            print(f"\n[{agent.name}]")
            print(f"  Thoughts: {monologue}")
            print(f"  Action: {action} ({target})")
            if structured_output_status != "structured_disabled":
                print(f"  Structured Output: {structured_output_status}")

            # 4. EXECUTE - Validate and apply action
            success, feedback = self.parser.execute(agent, {"action": action, "action_target": target})
            nearby_ids = self.world.get_visible_agents(agent.agent_id)
            nearby_names = [a.name for a in self.agents if a.agent_id in nearby_ids]
            agent.add_to_memory(agent.interpret_consequence(action, target, success, feedback, nearby_names))

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

            if action in {"SAY", "LIE"} and success:
                event_msg = f"{agent.name} said: '{target}'"
                self._broadcast_with_reactions(event_msg, agent.agent_id, action, current_loc)

            elif action == "WHISPER" and success:
                parsed = self._extract_social_target(target)
                if parsed:
                    message, target_agent_id = parsed
                    target_agent = self.get_agent_by_id(target_agent_id)
                    if target_agent:
                        target_agent.add_to_memory(f"{agent.name} whispered to you: '{message}'")
                        self.social.update_scores(target_agent_id, agent.agent_id, trust_delta=4, affinity_delta=3, notes=f"{agent.name} chose to confide in you.")
                    for witness_id in self.world.get_visible_agents(agent.agent_id):
                        if witness_id != target_agent_id:
                            witness = self.get_agent_by_id(witness_id)
                            if witness:
                                witness.add_to_memory(f"You noticed {agent.name} whisper something privately to {target_agent_id}.")
                    self._sync_relationships()

            elif action == "MOVE" and success:
                event_msg = f"You saw {agent.name} move to {target}"
                old_loc = world_snapshot["current_location"]["id"] if world_snapshot.get("current_location") else current_loc
                self.broadcast_event(event_msg, old_loc, exclude_agent_id=agent.agent_id)

            elif action == "PICKUP" and success:
                event_msg = f"You saw {agent.name} pick up the {target}"
                self._broadcast_with_reactions(event_msg, agent.agent_id, action, current_loc)
                # Witnessed pickup reduces trust in the actor
                witnesses = self.world.get_visible_agents(agent.agent_id)
                for witness_id in witnesses:
                    self.social.update_scores(
                        witness_id, agent.agent_id,
                        trust_delta=-3, affinity_delta=-1,
                        notes=f"Witnessed {agent.name} take {target}"
                    )
                self._sync_relationships()
                # Check if a hidden knowledge item was just picked up
                if agent.pending_drop is None:
                    for item in self.world.find_items_by_owner(agent.agent_id):
                        if item.get("hidden") and item.get("knowledge"):
                            agent.add_to_memory(f"[Discovered] {item['knowledge']}")
                            agent.pending_drop = item["id"]
                            agent.pending_drop_name = item["name"]
                            print(f"  [Hidden Knowledge] {agent.name} reads: {item['knowledge'][:80]}...")
                            break

            elif action == "DROP" and success:
                event_msg = f"You saw {agent.name} drop the {target}"
                self.broadcast_event(event_msg, current_loc, exclude_agent_id=agent.agent_id)
                # Clear pending_drop obligation if the right item was returned
                if agent.pending_drop and agent.pending_drop_name and agent.pending_drop_name.lower() in target.lower():
                    agent.pending_drop = None
                    agent.pending_drop_name = None

            elif action == "USE" and success:
                # Find the item in the agent's hand and apply its effect
                hand_items = self.world.find_items_by_owner(agent.agent_id)
                used_item = next(
                    (item for item in hand_items
                     if not item.get("hidden") and (target.lower() in item["name"].lower() or item["id"] == target)),
                    None
                )
                if used_item:
                    self._apply_item_effect(agent, used_item)
                    event_msg = f"You saw {agent.name} use {used_item['name']}"
                    self.broadcast_event(event_msg, current_loc, exclude_agent_id=agent.agent_id)

            elif action == "GIVE" and success:
                parsed = self._extract_social_target(target)
                if parsed:
                    item_name, target_agent_id = parsed
                    event_msg = f"You saw {agent.name} give {item_name} to {target_agent_id}"
                    self._broadcast_with_reactions(event_msg, agent.agent_id, action, current_loc)

            elif action == "DEMAND" and success:
                parsed = self._extract_social_target(target)
                if parsed:
                    item_name, target_agent_id = parsed
                    event_msg = f"You saw {agent.name} demand {item_name} from {target_agent_id}"
                    self._broadcast_with_reactions(event_msg, agent.agent_id, action, current_loc)

            elif action == "REPAIR" and success:
                loc_data = self.world.get_location(current_loc)
                loc_name = loc_data.get("name", current_loc) if loc_data else current_loc
                event_msg = f"An announcement comes over the station comms: a system in {loc_name} has been restored to operational status by {agent.name}."
                for other_agent in self.agents:
                    if other_agent.agent_id != agent.agent_id:
                        other_agent.add_to_memory(event_msg)
                for witness_id in self.world.get_visible_agents(agent.agent_id):
                    self.social.update_scores(witness_id, agent.agent_id, trust_delta=8, affinity_delta=5, notes=f"Witnessed {agent.name} repair a station system.")
                self._sync_relationships()

            elif action == "SABOTAGE" and success:
                system_id = target.strip()
                loc_data = self.world.get_location(current_loc)
                loc_name = loc_data.get("name", current_loc) if loc_data else current_loc
                event_msg = f"An alert sounds across the station: a system failure has been detected in {loc_name}."
                for other_agent in self.agents:
                    if other_agent.agent_id != agent.agent_id:
                        other_agent.add_to_memory(event_msg)
                self._record_system_incident(agent, current_loc, system_id)
                self._inject_snitch_memory(agent, current_loc, system_id)

            # 6. SOCIAL MATRIX UPDATE - Evaluate SAY interactions
            if action in {"SAY", "LIE", "GIVE", "DEMAND", "WHISPER"} and success:
                self._evaluate_social_impact(agent, action, target)

            cycle_results.append(result_entry)

        # Check for reflection trigger
        if self.cycle_count % self.reflection_interval == 0:
            print(f"\n--- REFLECTION PHASE (Cycle {self.cycle_count}) ---")
            for agent in self.agents:
                agent_snapshot = self.world.get_snapshot_for_agent(agent.agent_id)
                new_summary = agent.reflect(agent_snapshot)
                print(f"[{agent.name}] Memory consolidated. New long-term memory:")
                print(f"  '{new_summary[:150]}...'")
                print(f"  Goal momentum: {agent.goal_momentum}")

        return cycle_results

    def _evaluate_social_impact(
        self,
        speaking_agent: Any,
        action: str,
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
        nearby_agents = self.world.get_visible_agents(speaking_agent.agent_id)

        for other_id in nearby_agents:
            other_agent = self.get_agent_by_id(other_id)
            if not other_agent:
                continue
            self._apply_social_critic(other_agent, speaking_agent, action, message)
            new_trust, new_affinity = self.social.get_scores(other_id, speaking_agent.agent_id)
            suspicion = self.social.get_suspicion(other_id, speaking_agent.agent_id)
            label = other_agent._relationship_label(new_trust, new_affinity, suspicion)
            print(f"[{other_agent.name}] Updated view of {speaking_agent.name}: "
                  f"T={new_trust}, A={new_affinity} [{label}]")

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
