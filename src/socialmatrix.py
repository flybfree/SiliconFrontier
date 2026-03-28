"""
SocialMatrix - The Relational Database of Silicon Frontier

Tracks interpersonal dynamics between agents through Trust and Affinity scores,
enabling emergent social behaviors like alliances, rivalries, and grudges.
"""

import json
import copy
from typing import Any


class SocialMatrix:
    """
    Manages relationship scores between all agents in the simulation.

    Each agent pair has two dimensions:
    - Trust (0-100): How reliable is this agent? Do they keep promises?
    - Affinity (0-100): How much do I like this agent personally?

    Update formula: T_new = T_old + ΔT where ΔT ∈ [-10, +10]
    """

    def __init__(self, world_state=None):
        """Initialize the social matrix."""
        self._relationships: dict[str, dict[str, Any]] = {}
        self._suspicions: dict[str, dict[str, int]] = {}
        self._world_state = world_state

    def initialize_from_world(self, world_state) -> None:
        """Populate relationships from world state data."""
        self._world_state = world_state
        if hasattr(world_state, "relationships"):
            self._relationships = copy.deepcopy(world_state.relationships)
        if hasattr(world_state, "suspicions"):
            self._suspicions = copy.deepcopy(world_state.suspicions)

    @property
    def relationships(self) -> dict[str, dict[str, Any]]:
        return self._relationships

    @property
    def suspicions(self) -> dict[str, dict[str, int]]:
        return self._suspicions

    def ensure_agent_network(self, agent_ids: list[str]) -> None:
        """Ensure every agent has a neutral relationship entry for every other agent."""
        for agent_a in agent_ids:
            for agent_b in agent_ids:
                self.get_or_create_relationship(agent_a, agent_b)
                self.get_or_create_suspicion(agent_a, agent_b)

    def sync_to_world(self) -> None:
        """Mirror the active relationship matrix back into the world state."""
        if self._world_state is not None and hasattr(self._world_state, "_data"):
            self._world_state._data["relationships"] = copy.deepcopy(self._relationships)
            self._world_state._data["suspicions"] = copy.deepcopy(self._suspicions)

    def get_or_create_suspicion(self, agent_a: str, agent_b: str) -> tuple[str, str]:
        """Ensure a hidden suspicion entry exists for the observer-target pair."""
        if agent_a not in self._suspicions:
            self._suspicions[agent_a] = {}
        if agent_b not in self._suspicions:
            self._suspicions[agent_b] = {}

        if agent_b not in self._suspicions[agent_a]:
            self._suspicions[agent_a][agent_b] = 0
        if agent_a not in self._suspicions[agent_b]:
            self._suspicions[agent_b][agent_a] = 0

        return agent_a, agent_b

    def get_suspicion(self, agent_a: str, agent_b: str) -> int:
        """Get suspicion from one agent's perspective toward another."""
        self.get_or_create_suspicion(agent_a, agent_b)
        return int(self._suspicions.get(agent_a, {}).get(agent_b, 0))

    def update_suspicion(self, agent_a: str, agent_b: str, suspicion_delta: int) -> int:
        """Update suspicion for one observer-target pair."""
        agent_a, agent_b = self.get_or_create_suspicion(agent_a, agent_b)
        suspicion_delta = max(-20, min(20, suspicion_delta))
        current = self._suspicions[agent_a][agent_b]
        new_value = max(0, min(100, current + suspicion_delta))
        self._suspicions[agent_a][agent_b] = new_value
        return new_value

    def get_or_create_relationship(
        self,
        agent_a: str,
        agent_b: str
    ) -> tuple[str, str]:
        """
        Ensure a relationship entry exists for both agents.

        Returns:
            Tuple of (agent_a_key, agent_b_key) for the pair
        """
        # Create bidirectional entries if they don't exist
        if agent_a not in self._relationships:
            self._relationships[agent_a] = {}
        if agent_b not in self._relationships:
            self._relationships[agent_b] = {}

        if agent_b not in self._relationships[agent_a]:
            self._relationships[agent_a][agent_b] = {
                "trust": 50,      # Neutral starting trust
                "affinity": 50,   # Neutral starting affinity
                "notes": ""       # Human-readable relationship notes
            }

        if agent_a not in self._relationships[agent_b]:
            self._relationships[agent_b][agent_a] = {
                "trust": 50,
                "affinity": 50,
                "notes": ""
            }

        return agent_a, agent_b

    def get_scores(self, agent_a: str, agent_b: str) -> tuple[int, int]:
        """
        Get trust and affinity scores from agent_a's perspective of agent_b.

        Args:
            agent_a: The observer (who is judging)
            agent_b: The target (being judged)

        Returns:
            Tuple of (trust_score, affinity_score) or (None, None) if unknown
        """
        self.get_or_create_relationship(agent_a, agent_b)

        rel = self._relationships.get(agent_a, {}).get(agent_b, {})
        return rel.get("trust", 50), rel.get("affinity", 50)

    def update_scores(
        self,
        agent_a: str,
        agent_b: str,
        trust_delta: int,
        affinity_delta: int,
        notes: str = ""
    ) -> tuple[int, int]:
        """
        Update relationship scores with deltas.

        Args:
            agent_a: The observer (who is changing their feelings)
            agent_b: The target (whose behavior was observed)
            trust_delta: Change in trust (-10 to +10)
            affinity_delta: Change in affinity (-10 to +10)
            notes: Optional note about why scores changed

        Returns:
            Tuple of new (trust_score, affinity_score)
        """
        agent_a, agent_b = self.get_or_create_relationship(agent_a, agent_b)

        # Clamp deltas to valid range
        trust_delta = max(-10, min(10, trust_delta))
        affinity_delta = max(-10, min(10, affinity_delta))

        # Get current scores and apply changes
        old_trust = self._relationships[agent_a][agent_b]["trust"]
        old_affinity = self._relationships[agent_a][agent_b]["affinity"]

        new_trust = max(0, min(100, old_trust + trust_delta))
        new_affinity = max(0, min(100, old_affinity + affinity_delta))

        # Update relationship
        self._relationships[agent_a][agent_b]["trust"] = new_trust
        self._relationships[agent_a][agent_b]["affinity"] = new_affinity

        if notes:
            existing_notes = self._relationships[agent_a][agent_b].get("notes", "")
            new_entry = f"{agent_b}: ΔT={trust_delta:+d}, ΔA={affinity_delta:+d}. {notes}"
            if existing_notes:
                # Keep only the last 2 prior entries to prevent unbounded growth
                prior_entries = [e.strip() for e in existing_notes.split("[Turn]") if e.strip()]
                prior_entries = prior_entries[-2:]
                combined = " [Turn] ".join(prior_entries) + " [Turn] " + new_entry
            else:
                combined = new_entry
            self._relationships[agent_a][agent_b]["notes"] = combined

        return new_trust, new_affinity

    def get_relationship_summary(self, agent_id: str) -> list[dict[str, Any]]:
        """Get a summary of all relationships for an agent."""
        self.get_or_create_relationship(agent_id, agent_id)  # Ensure entry exists

        summaries = []
        for other_agent, rel_data in self._relationships.get(agent_id, {}).items():
            if other_agent == agent_id:
                continue
            summaries.append({
                "agent": other_agent,
                "trust": rel_data["trust"],
                "affinity": rel_data["affinity"],
                "notes": rel_data.get("notes", "")
            })

        # Sort by trust score (most trusted first)
        return sorted(summaries, key=lambda x: -x["trust"])

    def get_all_relationships(self) -> dict[str, dict[str, Any]]:
        """Get all relationships in the matrix."""
        return self._relationships

    def set_scores(
        self,
        agent_a: str,
        agent_b: str,
        trust: int,
        affinity: int,
        notes: str = ""
    ) -> None:
        """Directly set relationship scores (bypassing deltas)."""
        agent_a, agent_b = self.get_or_create_relationship(agent_a, agent_b)

        self._relationships[agent_a][agent_b]["trust"] = max(0, min(100, trust))
        self._relationships[agent_a][agent_b]["affinity"] = max(0, min(100, affinity))

        if notes:
            self._relationships[agent_a][agent_b]["notes"] = notes

    def get_trust_network(self) -> dict[str, list[tuple[str, int]]]:
        """
        Get a network view of trust relationships.

        Returns:
            Dict mapping agent_id to list of (other_agent, trust_score) tuples
        """
        network = {}
        for agent_a in self._relationships:
            network[agent_a] = [
                (agent_b, rel["trust"])
                for agent_b, rel in self._relationships.get(agent_a, {}).items()
                if agent_b != agent_a
            ]
        return network

    def to_json(self) -> str:
        """Serialize relationships to JSON."""
        return json.dumps(self._relationships, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SocialMatrix":
        """Load relationships from JSON string."""
        matrix = cls()
        matrix._relationships = json.loads(json_str)
        return matrix
