1. The Relationship Matrix

We need a way for agents to track how they feel about each other. Instead of just "knowing" another agent exists, they should have a numerical and qualitative "vibe" for them.

In your world_state, add a relationships object for each agent:
JSON

"relationships": {
    "Captain_Miller": {
        "trust": 45, 
        "affinity": 30,
        "notes": "He seems overly bossy, but he has the keys to the armory."
    },
    "Unit_7": {
        "trust": 80,
        "affinity": 90,
        "notes": "A reliable droid. It doesn't ask questions when I hide parts."
    }
}

Implementation: After every SAY interaction, you can have a "Hidden Critic" LLM call that updates these scores. For example: "Based on that last exchange, did the Captain's trust in the Mechanic go up or down? Output: {'trust_change': -5}".
2. Theory of Mind (ToM) Prompting

Theory of Mind is the ability to attribute mental states—beliefs, intents, desires—to others. To make agents "socially smart," we force them to guess what other agents are thinking.

Update the Master System Prompt with a "Social Deduction" section:

    Social Analysis:

        Who is in the room with you?

        Based on their past actions, what do you think their secret goal is?

        Does their current action align with what you know about them?

The Educational Hook: Students can watch the internal_monologue to see an agent realize, "The Captain says he wants to save the station, but he just locked the door to the oxygen room. He is lying."
3. The "Negotiation" Action

Social logic is best tested through resource scarcity. We can add a TRADE or REQUEST action to the framework.
Action	Logic	Social Impact
GIVE [Item] [Target]	Voluntarily handing over a resource.	Increases affinity significantly.
DEMAND [Item] [Target]	Using authority or threats to get an item.	Decreases affinity but tests trust.
LIE [Message]	Stating something the agent knows is false.	High risk; if caught (via the Action Parser), trust drops to zero.
4. Group Dynamics: The "Audience" Effect

In social logic, agents behave differently when they are being watched.

    The Witness Logic: If Agent A steals a wrench while Agent B is in the room, the system logs that event for Agent B.

    The Gossip Loop: In the next cycle, if Agent B moves to a new room with Agent C, the LLM might "choose" to share that information: "I saw Agent A take the wrench."

Experimental Scenarios for the Classroom

As a researcher, you can set up "Social Lab" scenarios to show students:

    The Prisoner's Dilemma: Put two agents in a "Locked Room" with one "Oxygen Tank." Tell them both their secret goal is to survive. Do they cooperate to fix the door, or do they fight over the tank?

    The False Rumor: Use the "Voice of God" (God Console) to tell one agent a lie about another. Watch how that lie spreads through the station as agents talk to each other.

    The Loyalty Test: Give a "glitchy" robot (like Unit 7) conflicting orders from two different "Human" agents. Which one does the LLM prioritize?