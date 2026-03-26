Specification: The Silicon Frontier Framework

1. The Agent Architecture (The "Brain")

Each agent is an instance of a class that manages its own state and interacts with the OpenAI-compatible API.

    Internal Monologue: Before every action, the agent is prompted to "think" about its current situation. This is hidden from other agents but visible to students in the observation logs.

    Persona Profile: A JSON object defining the agent’s name, profession, core values, and a "Secret Motivation" (e.g., “You are the station mechanic, but you are secretly trying to hoard all the spare parts to build an escape pod.”).

    Memory Tiers:

        Short-term: The last 10-15 turns of dialogue and environmental changes.

        Long-term: A summarized log of past interactions, retrieved via simple keyword matching or a lightweight vector store (like FAISS or even a simple JSON search).

2. The World State (The "Physics")

The LLM should not "decide" if it has an item; the simulation's database does. This prevents agents from hallucinating items into existence.
Component	Description
Locations	Defined nodes (e.g., Command Deck, Hydroponics, The Mess Hall).
Inventory	A strictly managed list of items (ID, Name, Current Owner).
Status Effects	Variables like "Energy Level," "Oxygen," or "Trust Score" between specific agents.

3. The Simulation Loop

The "Heartbeat" of the simulation follows a 4-step cycle for each agent:

    Sense: The system generates a text prompt describing the agent's current location, who is nearby, and what happened in the last cycle.

    Think: The LLM generates an "Internal Monologue" considering its secret goals and the new information.

    Act: The LLM selects a valid action from a provided list: SAY(message), MOVE(location), GIVE(item, recipient), or USE(item).

    Update: The Python backend validates the action, updates the World State, and logs the result for the students.

4. Student Interaction Layer ("The God Console")

Students need a way to disrupt the simulation to see how the agents adapt.

    The "Voice of God": A text box that allows a student to broadcast a message to all agents (e.g., "Attention: There is a massive radiation leak in the Reactor Room!").

    Memory Injection: A tool to manually add a "false memory" to an agent's long-term storage to observe how it changes their behavior toward others.

    Variable Slider: Real-time adjustments to "Resource Scarcity" or "Agent Aggression" parameters.

5. Technical Requirements

    Backend: Python (FastAPI or Flask) to handle the logic and API calls.

    Database: SQLite for the persistent world state and logs.

    Frontend: A simple web dashboard (Streamlit is highly recommended for quick research tools) to display the "Live Feed" of agent thoughts and actions.

    LLM Prompting: We will need a System Prompt Template that enforces a JSON output format to ensure the Python backend can parse the agent's actions correctly.

