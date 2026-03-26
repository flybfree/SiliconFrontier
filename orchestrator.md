The Silicon Frontier: The Orchestrator Script

This script assumes you have the FrontierAgent class and the execute_action logic we developed earlier.
Python

import time
import json

# --- INITIAL WORLD STATE ---
world_state = {
    "locations": {
        "mess_hall": {"name": "Mess Hall", "description": "The social hub.", "connected_to": ["command_deck", "hydroponics"]},
        "command_deck": {"name": "Command Deck", "description": "The bridge.", "connected_to": ["mess_hall"]},
        "hydroponics": {"name": "Hydroponics", "description": "The farm.", "connected_to": ["mess_hall"]}
    },
    "items": {
        "wrench_01": {"name": "Plasma Wrench", "location": "mess_hall", "portable": True, "description": "A heavy tool."}
    }
}

# --- INITIALIZE AGENTS ---
agents = [
    FrontierAgent("A1", "Captain Miller", "Strict, focused on safety.", "Protect the station at all costs."),
    FrontierAgent("A2", "Unit 7", "A quirky, slightly glitchy robot.", "Collect shiny objects.")
]

def broadcast_event(message, location, exclude_agent_id=None):
    """Sends a message to the memory of all agents in a specific room."""
    for agent in agents:
        if agent.location == location and agent.agent_id != exclude_agent_id:
            agent.memory_buffer.append(message)
            # Keep memory buffer short for local LLM context windows
            if len(agent.memory_buffer) > 5:
                agent.memory_buffer.pop(0)

# --- THE MAIN SIMULATION LOOP ---
def run_simulation(rounds=5):
    print("🚀 Starting Silicon Frontier Simulation...")
    
    for r in range(1, rounds + 1):
        print(f"\n--- CYCLE {r} ---")
        
        for agent in agents:
            # 1. SENSE: Get current surroundings
            observation = agent.sense(world_state)
            
            # 2. THINK/ACT: Get LLM response
            print(f"[{agent.name}] is thinking...")
            decision = agent.think_and_act(observation)
            
            # 3. LOG FOR STUDENTS: Show the 'Internal Monologue'
            print(f" > Thoughts: {decision['internal_monologue']}")
            print(f" > Action: {decision['action']} ({decision.get('action_target')})")
            
            # 4. EXECUTE: Update the physical world
            result = execute_action(agent, decision, world_state)
            print(f" > Result: {result}")
            
            # 5. SOCIAL UPDATE: If they spoke, tell others in the room
            if decision['action'] == "SAY":
                event_msg = f"{agent.name} said: '{decision['action_target']}'"
                broadcast_event(event_msg, agent.location, exclude_agent_id=agent.agent_id)
            
            # 6. OBSERVATIONAL UPDATE: If they moved or picked up an item
            elif decision['action'] in ["MOVE", "PICKUP"]:
                event_msg = f"You saw {agent.name} perform: {decision['action']} {decision['action_target']}"
                broadcast_event(event_msg, agent.location, exclude_agent_id=agent.agent_id)

        # Slow down for readability in a live demo
        time.sleep(2)

if __name__ == "__main__":
    run_simulation()