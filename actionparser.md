The Action Parser Logic

The parser takes the JSON from the agent, validates it against the world_state, and returns a "System Feedback" message. This feedback is then fed back into the agent's memory so it knows if it succeeded or failed.
The execute_action Function
Python

def execute_action(agent, llm_json, world_state):
    action = llm_json.get("action")
    target = llm_json.get("action_target")
    
    # 1. Handle MOVE
    if action == "MOVE":
        current_room = world_state["locations"][agent.location]
        if target in current_room["connected_to"]:
            agent.location = target
            return f"Success: You moved to {target}."
        else:
            return f"Failure: {target} is not connected to your current location."

    # 2. Handle SAY (Broadcasting to the room)
    elif action == "SAY":
        # Add the message to the memory of everyone in the same room
        # We will handle the "hearing" logic in the main loop
        return f"Success: You said '{target}' to everyone in the room."

    # 3. Handle PICKUP
    elif action == "PICKUP":
        item_id = find_item_id_by_name(target, world_state)
        if item_id and world_state["items"][item_id]["location"] == agent.location:
            if world_state["items"][item_id]["portable"]:
                world_state["items"][item_id]["location"] = agent.agent_id
                agent.inventory.append(item_id)
                return f"Success: You are now holding the {target}."
            return f"Failure: The {target} is too heavy to move."
        return f"Failure: The {target} is not in this room."

    # 4. Handle WAIT
    elif action == "WAIT":
        return "You waited patiently for the next cycle."

    return "Failure: Unknown action or invalid syntax."