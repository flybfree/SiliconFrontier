Design Document: The Silicon Frontier Framework

Project Goal: To create a sandbox for observing emergent social behaviors and decision-making logic in LLM-based agents within a constrained, verifiable environment.
1. System Architecture & Technical Stack

The system is designed as a "Stateful Orchestrator" that sits between a deterministic world database and a probabilistic inference engine.

    Inference Engine: Local OpenAI-compatible API (e.g., vLLM, Ollama, LM Studio).

    Logic Layer: Python 3.10+ (utilizing the openai Python library).

    State Management: JSON-based "Truth Table" (expandable to SQLite for long-term persistence).

    Observational Interface: Streamlit (Web UI) for real-time monitoring and student interaction.

2. The World Schema (Environmental Physics)

The simulation adheres to a strict "Logic vs. Truth" separation. The LLM handles the intent, but the code enforces the outcome.

    Locations: Nodes with descriptions and adjacency lists (where agents can move).

    Items: Unique objects with properties (portable, location, owner).

    Agents: Dynamic entities with a location, inventory, and status.

3. The Agent "Mind" (Cognitive Architecture)

Each agent operates on a Sense -> Think -> Act -> Reflect cycle. This architecture forces the LLM to process environmental data before committing to an action.
A. The Sense Phase

The orchestrator filters the global JSON state to provide the agent with a "Subjective View."

    Input: Current room description, visible items, and the last 5 turns of local events (the memory_buffer).

B. The Think/Act Phase (Master System Prompt)

The agent is governed by a System Prompt that mandates a Chain-of-Thought (CoT) process.

    Internal Monologue: Forced reasoning where the agent weighs its Secret Goal against current observations.

    Action Output: Strict JSON format choosing from a limited verb set: MOVE, SAY, PICKUP, DROP, WAIT.

C. The Reflection Phase (Memory Consolidation)

To overcome context window limitations, agents periodically summarize their memory_buffer into Long-Term Memory.

    Consolidation Logic: The LLM extracts key relationship changes and goal progress, discarding trivial "noise."

4. The Action Parser (Validation Layer)

This module acts as the "Dungeon Master." It prevents agents from hallucinating abilities or items.

    Validation: Checks if a target location is adjacent or if an item is actually present.

    Feedback: If an action fails, the system returns an error message to the agent (e.g., "Error: You cannot pick up the airlock door"). This forces the agent to adapt its strategy in the next turn.

5. Social Logic & Relationship Dynamics

The framework quantifies social interactions to track emergent alliances or rivalries.

    Relationship Matrix: A nested JSON object tracking Trust and Affinity scores (0-100) between all agents.

    Theory of Mind (ToM): The System Prompt asks agents to guess the motivations of others in their vicinity.

    Social Broadcasting: When an agent uses the SAY action, the message is automatically injected into the Sense phase of all agents in the same location.

6. Experimental Control (The "God Console")

For replication and classroom use, the framework includes a manual override layer:

    Environmental Injection: Introducing new variables (e.g., "The oxygen is failing").

    Memory Manipulation: Injecting specific "memories" or "rumors" into an agent's long-term storage to observe behavior shifts.

    Prompt Swapping: Changing an agent's Persona mid-simulation to test behavioral plasticity.

7. Summary of Logic flow

The simulation follows a standard update formula for relationship dynamics:
Tnew​=Told​+ΔT

Where ΔT is determined by a "Critic" LLM evaluating the social impact of the most recent interaction.
8. Replication Checklist

    Launch Local Inference: Ensure the OpenAI-compatible API is running on localhost.

    Initialize World State: Load the world_state.json.

    Deploy Agents: Instantiate the FrontierAgent class with unique personas.

    Execute Main Loop: Run the orchestrator with a set cycle_count.

    Audit Logs: Review the internal_monologue logs to verify the "Reasoning-to-Action" alignment.

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

Part III: Experimental Methodology

This section outlines how to measure, record, and analyze the "social physics" of the simulation.
1. Quantitative Data Tracking (The "Hard" Numbers)

Researchers should track numerical shifts in the WorldState and SocialMatrix to identify patterns of cooperation or conflict.
Metric	Calculation	Significance
Cooperation Index	Ratio of GIVE vs. DEMAND actions.	Measures the "altruism" of a specific model/persona.
Trust Volatility	The frequency and magnitude of ΔT changes.	Indicates how "forgiving" or "vengeful" an agent is.
Resource Centralization	Gini coefficient of item ownership over time.	Shows if one agent is effectively "winning" via hoarding.
Movement Entropy	Variety of rooms visited vs. total turns.	Measures the "curiosity" or goal-focus of the agent.
2. Qualitative Analysis (The "Soft" Logic)

Students should perform a Textual Audit of the internal_monologue logs. This is where they identify the difference between stated intent and actual behavior.

    Logic Alignment: Does the action logically follow the internal_monologue? (If not, this is a "Logic Gap" or a failure in the local LLM's reasoning).

    Deception Detection: Identifying turns where the internal_monologue reveals a goal (e.g., "I will lie to the Captain") that differs from the SAY action.

    Affective Shift: Tracking changes in the emotional_state variable in response to environmental stressors (e.g., a "Radiation Leak").

3. Controlled Variables (A/B Testing)

To run a proper experiment, students should change exactly one variable and observe the ripple effect across the society.

    The Persona Pivot: Run the same scenario twice. In Test A, the Mechanic is "Helpful." In Test B, the Mechanic is "Paranoid." Compare the final Trust scores of the Captain.

    The Scarcity Stressor: Run a scenario with 5 items, then run it again with only 1. Observe how "Civil" the SAY actions remain as resources vanish.

    The Model Comparison: Swap the local LLM (e.g., from Llama 3 to Mistral) while keeping all prompts identical to test "Model Bias" or "Reasoning Capability."

4. Standardized Observation Protocol

For replication, students must document each session using the following format:

    Initial Conditions: Snapshot of the starting WorldState JSON.

    Hypothesis: e.g., "The Robot will choose to save the items over the human agent."

    Timeline of Key Events: A log of pivotal turns (thefts, lies, or alliances).

    Final State Analysis: The end-of-simulation SocialMatrix and a summary of whether the hypothesis was proven.
	
	