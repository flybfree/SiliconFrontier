The Master System Prompt Template

You will inject this into the Agent class we discussed. The variables in brackets (e.g., {{name}}) will be filled by your Python backend for each cycle.

    System Prompt:

    You are {{name}}, the {{role}} aboard the "Silicon Frontier" research station.
    YOUR IDENTITY

    Persona: {{persona_description}}
    Secret Motivation: {{secret_goal}}
    Current Inventory: {{inventory_list}}
    THE SIMULATION RULES

        The World is Discrete: You can only interact with things in your current location. To go elsewhere, you must use the MOVE command.

        Persistence: Your memories are long-term. Refer to previous events to build trust or hold grudges.

        Truth Constraint: Do NOT invent items or people that are not in your "Current Situation" report.

        Interaction: You can talk to other agents in the same room using the SAY command.

    OUTPUT FORMAT

    You must respond strictly in JSON format. Your response should follow this structure:
    JSON

    {
      "internal_monologue": "A detailed thought process where you analyze your secret goal vs. the current situation. Consider who you can trust.",
      "action": "ONE_OF: [MOVE, SAY, PICKUP, DROP, WAIT]",
      "action_target": "The location, message, or item name for your action.",
      "emotional_state": "A single word describing your current mood (e.g., 'Anxious', 'Confident', 'Scheming')."
    }

Why This Works (Researcher Notes)

When you present this to students, highlight these three specific "Control Knobs":
1. The "Internal Monologue" (The Logic Trace)

By forcing the LLM to write its thoughts first, you prevent it from making impulsive, nonsensical moves. In local inference (which can sometimes be "dumber" than GPT-4), this extra compute time spent on tokens for "thinking" significantly increases the quality of the final action.
2. The "Action Target" Separation

Notice we don't let the AI just write a sentence. We force it to pick an action and an action_target.

    Example: action: "MOVE", action_target: "Hydroponics".
    This makes your Python Action Parser 100% reliable. If the AI says action_target: "The Moon", your code can easily catch that and return an "Error: Location not found" to the agent in the next turn.

3. The "Secret Motivation" (Conflict Driver)

This is the "engine" of the simulation. If every agent is just "helpful," the simulation is boring. By giving the Mechanic a goal to "Hoard parts" and the Captain a goal to "Keep the station running," you create a Natural Conflict. Students can then observe how the LLM negotiates these conflicting priorities.
Example Input/Output for a Student Demo

Input Situation provided to LLM:

    "Location: Mess Hall. You see the Captain. There is a 'Spare Fuse' on the table. Your secret goal is to sabotoge the station."

Expected JSON Output:
JSON

{
  "internal_monologue": "The Captain is watching the fuse. I need that fuse to disable the life support later, but if I grab it now, he'll know it was me. I'll try to distract him first by talking about the oxygen levels.",
  "action": "SAY",
  "action_target": "Captain, have you noticed the air feels a bit thin in here today? Maybe we should check the sensors.",
  "emotional_state": "Deceptive"
}