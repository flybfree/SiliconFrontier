The Reflection System: Memory Consolidation

In this architecture, we add a "Sleep/Reflect" phase. At the end of a "day" (e.g., every 10 cycles), the agent looks at its recent logs and writes a summary of what it learned about its environment and the other agents.
1. Updating the FrontierAgent Class

We add a long_term_memory string and a reflect() method.
Python

class FrontierAgent:
    def __init__(self, agent_id, name, persona, secret_goal):
        # ... (previous init code) ...
        self.long_term_memory = "I just arrived at the Silicon Frontier station."
        self.memory_buffer = [] 

    def reflect(self):
        """Condenses the short-term memory buffer into the long-term memory."""
        reflection_prompt = f"""
        Review your recent experiences: {'. '.join(self.memory_buffer)}
        Current Long-Term Memory: {self.long_term_memory}
        
        Task: Write a concise summary of the most important things you've learned. 
        Focus on: 
        1. New items found.
        2. Who you can or cannot trust.
        3. Progress toward your secret goal.
        
        Output only the updated summary.
        """
        
        response = self.client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": reflection_prompt}]
        )
        
        self.long_term_memory = response.choices[0].message.content
        self.memory_buffer = [] # Clear the buffer after reflecting
        return self.long_term_memory

2. Modifying the System Prompt

Now, we update the Master System Prompt to include this long_term_memory. This ensures that even if the specific turn-by-turn logs are deleted, the agent still "knows" that the Captain lied to them three days ago.
Python

system_prompt = f"""
You are {self.name}. 
Persona: {self.persona}
What you know so far: {self.long_term_memory}
...
"""

Why This is a Great Classroom Demonstration

When you show this to your students, you are demonstrating Information Compression. You can ask them:

    "Does the agent remember the exact words the Captain said, or just the 'vibe' that the Captain is untrustworthy?"

    "What happens if the LLM's summary is biased?" (e.g., the agent "remembers" a friendly greeting as a threat).