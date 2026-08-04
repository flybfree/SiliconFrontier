The Silicon Frontier: JSON World State

A flat, hierarchical JSON structure is easiest for a Python backend to parse and for an LLM to "read" as part of its system prompt. Here is how we should structure the primary components:
1. Locations Node

This defines the physical boundaries. Each location is a "node" that agents can move between. We include descriptions so the LLM knows what the environment "looks" like.
JSON

{
  "locations": {
    "command_deck": {
      "name": "Command Deck",
      "description": "The high-tech nerve center of the station. Views of the gas giant below are visible through reinforced windows.",
      "connected_to": ["mess_hall", "elevator_bay"],
      "status_effects": []
    },
    "hydroponics_bay": {
      "name": "Hydroponics Bay",
      "description": "Densely packed with oxygen-producing ferns and nutrient vats. It's humid and smells of wet earth.",
      "facilities": ["bio_lab"],
      "connected_to": ["mess_hall"],
      "status_effects": ["high_humidity"]
    }
  }
}

2. Items Node

To prevent hallucinations, items are unique objects. They aren't just strings; they are entities with properties.
JSON

{
  "items": {
    "id_card_001": {
      "name": "Security ID Card",
      "location": "command_deck",
      "owner": null,
      "description": "A plastic card with a faded photo. It grants access to restricted zones.",
      "portable": true
    },
    "nutrient_vat": {
      "name": "Industrial Nutrient Vat",
      "location": "hydroponics_bay",
      "owner": null,
      "description": "A massive, immovable tank filled with green sludge.",
      "portable": false
    }
  }
}

3. Fabrication Node

Facilities, finite material stacks, and recipes create in-world tool-making without allowing the model to execute arbitrary code. A recipe consumes its declared materials only at a compatible facility and produces an item with declarative capabilities.

```json
{
  "recipes": {
    "atmosphere_sampler": {
      "facility": "bio_lab",
      "materials": {"sensor_array": 1, "power_cell": 1, "wire_spool": 1},
      "output": {
        "name": "Atmosphere Sampler",
        "tool": {"capabilities": ["inspect_oxygen_generator"], "durability": 2},
        "use_effect": {"inspect_system": "oxygen_generator"}
      }
    }
  }
}
```

Materials are normal item entries with `material_type` and `quantity`, so they can be moved, traded, concealed, or contested before assembly.

4. Agents Node (The Initial State)

This tracks the dynamic state of the agents, including their current location and what they believe they are doing.
Key	Purpose
Current Location	Determines what "Sense" data the agent receives.
Inventory	A list of item IDs currently held by the agent. Each carried item also has a runtime `inventory_slot`: `hand`, `visible`, or `concealed`. Only hand and visible items are exposed to co-located agents.
Current Goal	A high-level directive that guides the LLM's decision-making.
Memory Buffer	A temporary list of the last few events perceived.
Implementation Philosophy: "The Truth Table"

When the simulation runs, we will pass a subset of this JSON to the LLM.

    The Agent does not see the whole file. * It only sees the description of its current location, the items present there, its own inventory, local facilities, and recipes usable at those facilities.

    Researcher Note: By keeping the state in a clean JSON format, you can easily export "snapshots" of the simulation. This is invaluable for students to analyze why a specific behavior emerged at a specific timestamp.
