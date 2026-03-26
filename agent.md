The Agent Class: The Logic Engine

This class is responsible for the heavy lifting. It takes the "objective" world state and translates it into a "subjective" prompt for the LLM.
Python

import openai
import json

class FrontierAgent:
    def __init__(self, agent_id, name, persona, secret_goal):
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.secret_goal = secret_goal
        self.inventory = []
        self.location = "mess_hall"
        self.memory_buffer = [] # Stores last 5 events
        
        # Point this to your local inference engine (e.g., LM Studio, Ollama, vLLM)
        self.client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

    def sense(self, world_data):
        """Filters the world JSON to only what this agent can see."""
        current_loc = world_data["locations"][self.location]
        visible_items = [item for item in world_data["items"].values() if item["location"] == self.location]
        
        # Create a situational string for the prompt
        observation = f"Location: {current_loc['name']}. {current_loc['description']}\n"
        observation += f"Items here: {', '.join([i['name'] for i in visible_items]) if visible_items else 'None'}\n"
        observation += f"Recent Events: {'. '.join(self.memory_buffer)}"
        return observation

    def think_and_act(self, observation):
        """The core LLM call: Sense -> Think -> Act"""
        system_prompt = f"""
        You are {self.name}. 
        Persona: {self.persona}
        Secret Goal: {self.secret_goal}
        
        RULES:
        1. Always output valid JSON.
        2. First, write your 'internal_monologue' reflecting on your goal.
        3. Then, choose ONE action: ["MOVE <location>", "SAY <message>", "PICKUP <item>", "WAIT"].
        """

        user_prompt = f"Current Situation:\n{observation}\n\nWhat do you do next?"

        response = self.client.chat.completions.create(
            model="local-model", # Replace with your local model name
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)