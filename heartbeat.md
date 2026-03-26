The Orchestrator: Managing the Heartbeat

In a classroom setting, you’ll want a central "Heartbeat" script. This loop iterates through every agent in the simulation, collects their choices, and updates the central World State.
The "Heartbeat" Loop Logic

    Iterate: For each agent in the agents list:

    Sense: Provide the agent with its local view of the JSON.

    Think/Act: Call the LLM.

    Validate: (Crucial Step) The Python script checks: "Is the agent trying to MOVE to a room that isn't connected?" If yes, the action fails and the agent "WAITS" instead.

    Broadcast: Update the memory_buffer of all agents in the same room so they "hear" what was said or "see" what was moved.

Experimental Considerations for Students

As an AI researcher, you can use this Python structure to demonstrate several key concepts:

    Prompt Sensitivity: Show students how changing one sentence in the Persona (e.g., from "You are helpful" to "You are paranoid") completely changes how the LLM interprets the same observation.

    Context Window Management: Explain how we "summarize" or "prune" the memory_buffer to prevent the agent from becoming confused by too much old information.

    Hallucination Control: Demonstrate how the JSON "Truth" prevents the agent from claiming they have an item they didn't actually PICKUP.