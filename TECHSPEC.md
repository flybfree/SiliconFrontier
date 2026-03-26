Part II: Technical Specifications & Object Model

This section documents the core objects within the implementation and their specific roles in maintaining the integrity of the simulation.
1. The FrontierAgent Object (The Cognitive Unit)

The FrontierAgent is the primary class representing an autonomous entity. It encapsulates both the state and the interface to the LLM.

    Key Attributes:

        agent_id / name: Unique identifiers for tracking in logs.

        persona / secret_goal: String-based anchors that dictate the LLM’s personality and drive conflict.

        memory_buffer: A list of short-term logs (ephemeral).

        long_term_memory: A condensed summary of past cycles (persistent).

    Design Role: It acts as a "Subjective Filter." It takes the objective world and converts it into a narrative prompt, ensuring the AI only reacts to what it "knows" or "sees," rather than the entire database.

2. The WorldState Schema (The Physical Truth)

The WorldState is a nested dictionary (or JSON file) that acts as the "Ground Truth."

    Structure:

        locations: A dictionary where keys are Room IDs and values contain descriptions and adjacency lists.

        items: A dictionary of objects, their properties (e.g., is_portable), and their current location_id (which could be a room or an agent’s ID).

    Design Role: It provides the "Physics Engine." By keeping items and locations in a strictly defined structure, the system prevents "hallucinated objects." If an item isn't in the WorldState dictionary, it doesn't exist, regardless of what the LLM claims.

3. The ActionParser (The System Arbiter)

The ActionParser is a functional module (or a static method) that validates and executes the JSON commands returned by the agents.

    Workflow:

        Input: Takes the Agent Object and the JSON output from the LLM.

        Validation: Checks if the requested action_target is valid (e.g., "Is Room B actually connected to Room A?").

        Update: If valid, it modifies the WorldState (e.g., changing an item's location from "Room A" to "Agent_01").

    Design Role: It enforces "Deterministic Boundaries." It ensures that the probabilistic nature of the LLM is always checked against the hard rules of the simulation code.

4. The Orchestrator (The Temporal Controller)

The Orchestrator is the main loop or "Pulse" of the simulation.

    Logic Flow:

        Synchronization: Ensures turns are taken in order (or handled in parallel "threads" for advanced experiments).

        Social Broadcasting: When an agent acts, the Orchestrator identifies which other agents are in the same room and injects that event into their memory_buffer.

    Design Role: It manages "Causality." It ensures that if Agent A steals a wrench in front of Agent B, Agent B actually perceives that event before their next turn.

5. The SocialMatrix (The Relational Database)

A specialized data structure that tracks interpersonal variables.

    Variables:

        Trust: A numerical value (0–100) representing reliability.

        Affinity: A numerical value (0–100) representing how much an agent likes another.

    Update Formula: Tn+1​=Tn​+ΔT
    where ΔT is a value between −10 and +10 determined by the perceived "helpfulness" or "deception" of the last interaction.

    Design Role: It creates "Long-term Social Consequences." It allows students to observe how one bad interaction (a lie or a theft) can permanently alter the AI's future cooperation patterns.

System Integration Map
Object	Input	Output	Functional Goal
Agent	World Fragment	Action JSON	Decision-making & Reasoning
WorldState	Action Parser Update	State Snapshot	Maintaining Ground Truth
ActionParser	Action JSON	Result String	Physics & Logic Enforcement
Orchestrator	Agent List	Social Broadcast	Turn Management & Perception
Reflector	Memory Buffer	Summary String	Context Window Compression