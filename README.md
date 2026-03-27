# Silicon Frontier

A local multi-agent LLM simulation. Agents sense their environment, reason internally, take one action per turn, and reflect on outcomes. The simulation runs against any OpenAI-compatible inference server.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/UI-Streamlit-red) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Each simulation cycle:

1. An agent receives a filtered view of the world — their location, visible items, nearby agents, and their own memory.
2. The LLM returns internal reasoning, one action, and an emotional state.
3. The action is validated against the world state and executed.
4. Social scores update, memories are written, and witnesses react.

Agents accumulate memory, track goal momentum, and change their behavior based on emotional state, audience, and trust relationships. Two saboteur archetypes and multiple investigator roles are included.

---

## Requirements

- Python 3.10+
- An OpenAI-compatible local or remote inference server (LM Studio, Ollama, vLLM, etc.)

```bash
pip install -r requirements.txt
```

---

## Quick start

### Terminal

```bash
python run_simulation.py --rounds 10 --url http://localhost:1234/v1 --model your-model-name
```

Load a specific scenario:

```bash
python run_simulation.py --config-dir scenarios/cascade_failure --rounds 20 --delay 0
```

### Dashboard

```bash
streamlit run dashboard.py
```

Set the API URL and config directory in the sidebar, click **Initialize Simulation**, then run cycles.

---

## Included scenarios

| Scenario | Agents | Concept |
|---|---|---|
| `data/` (default) | 4 | Station crew with one saboteur and hidden evidence items |
| `scenarios/prisoners_dilemma` | 2 | Two detainees with sealed plea deals and no direct communication |
| `scenarios/cascade_failure` | 8 | Dual saboteurs, 11 locations, 5 hidden forensic evidence items |

Scenarios can also be loaded as dashboard saves from `saves/`.

---

## Agent behavior mechanics

**Inventory** — each agent holds at most two items: one in hand (visible to others) and one concealed on their person (hidden items only).

**Hidden items** — picking up a `hidden: true` item injects its `knowledge` text into the agent's memory and places them under a one-turn drop obligation, forcing them to stay in place.

**Contested items** — `contested: true` items remind agents they are valued resources that others may be competing for.

**Goal momentum** — after every reflection phase, agents assess their own progress as `advancing`, `stalled`, or `setback`. This feeds back into subsequent prompts.

**Emotional state** — a single-word emotional state carries forward turn to turn and colors the agent's reasoning and tone.

**Audience awareness** — agents are told who is watching before each turn, priming divergent public and private behavior.

**Witness reactions** — broadcasts for social actions are emotionally toned per observer based on their current trust and suspicion toward the actor.

**Sabotage alerts** — when a system is sabotaged, all agents on the station receive a notification regardless of location.

---

## Project layout

```
run_simulation.py          CLI entry point
dashboard.py               Streamlit dashboard
src/
  agent.py                 Agent cognition, prompting, memory, LLM calls
  orchestrator.py          Simulation loop, event broadcast, reflection
  actionparser.py          Action validation and execution
  worldstate.py            World state storage and snapshot helpers
  socialmatrix.py          Trust, affinity, and suspicion tracking
data/
  world_state.json         Default locations, items, and systems
  agent_definitions.json   Reusable agent definitions
  simulation_agents.json   Active simulation slots
scenarios/
  prisoners_dilemma/       2-agent game theory scenario
  cascade_failure/         8-agent dual-saboteur scenario
saves/                     Dashboard save files
```

---

## Configuration

The simulation loads from any directory containing three files:

- `world_state.json` — locations, items, sabotagable systems
- `agent_definitions.json` — reusable agent definitions with personas and secret goals
- `simulation_agents.json` — active slots that assign definitions to starting positions

See [USER_MANUAL.md](USER_MANUAL.md) for full configuration reference, item flags, rogue agent setup, and dashboard controls.

---

## Dashboard features

- Run single or batched cycles
- Inspect agent memory, emotional state, and inventory per turn
- Edit agent persona, secret goal, and location live
- Relationship matrix with trust, affinity, and notes per observer-target pair
- World state editor for locations, items, and systems
- God Console for direct intervention (broadcast, memory inject, relocate, persona swap)
- Save and load full simulation state
- Export current state as a reusable scenario directory
