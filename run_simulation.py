#!/usr/bin/env python3
"""
Silicon Frontier - Main Simulation Entry Point

Run a complete simulation with the configured agents and world state.
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class _Tee:
    """Mirror all writes to both the original stream and a log file."""

    def __init__(self, stream, log_path: Path):
        self._stream = stream
        self._file = open(log_path, "w", encoding="utf-8")

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        self._file.close()

    # Proxy any other attribute access to the underlying stream
    def __getattr__(self, name):
        return getattr(self._stream, name)


def _start_logging(scenario: str) -> _Tee | None:
    """Redirect stdout to both terminal and a timestamped log file."""
    log_dir = data_path("logs")
    log_dir.mkdir(exist_ok=True)
    slug = Path(scenario).name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{timestamp}_{slug}.log"
    tee = _Tee(sys.stdout, log_path)
    sys.stdout = tee
    print(f"Logging to: {log_path}")
    return tee


def _stop_logging(tee: _Tee | None) -> None:
    if tee is not None:
        sys.stdout = tee._stream
        tee.close()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
from app_paths import data_path, ensure_runtime_dirs

ensure_runtime_dirs()
os.chdir(data_path())

from worldstate import WorldState
from agent import FrontierAgent, RogueAgent
from actionparser import ActionParser
from socialmatrix import SocialMatrix
from orchestrator import Orchestrator
from configloader import (
    load_agent_configuration,
    build_agent_instances,
    load_item_library,
    load_scenario_manifest,
    load_relationship_presets,
    resolve_item_placements,
    resolve_relationship_presets,
)


def load_config(
    config_dir: str = "scenarios/default",
    llm_base_url: str = "http://192.168.3.181:1234/v1",
    llm_model: str = "unsloth/qwen3.5-35b-a3b"
) -> tuple[WorldState, list[FrontierAgent]]:
    """Load world state and agent configurations from JSON files."""
    config_path = Path(config_dir)

    # Load and resolve world state
    import json as _json
    with open(config_path / "world_state.json", "r") as f:
        world_data = _json.load(f)
    item_library = load_item_library()
    resolve_item_placements(world_data, item_library)

    agent_definitions, simulation_slots = load_agent_configuration(config_path)

    presets = load_relationship_presets()
    resolve_relationship_presets(simulation_slots, world_data, presets)

    world_state = WorldState(world_data)
    agent_instances = build_agent_instances(agent_definitions, simulation_slots)

    # Initialize agents from config
    agents = []
    for agent_cfg in agent_instances:
        agent_cls = RogueAgent if agent_cfg.get("archetype") == "saboteur" else FrontierAgent
        agent = agent_cls(
            agent_id=agent_cfg["agent_id"],
            name=agent_cfg["name"],
            persona=agent_cfg["persona"],
            secret_goal=agent_cfg["secret_goal"],
            role=agent_cfg.get("role"),
            archetype=agent_cfg.get("archetype"),
            perception=agent_cfg.get("perception", 50),
            condition=agent_cfg.get("condition"),
            llm_base_url=llm_base_url,
            llm_model=llm_model
        )

        # Set starting location and inventory
        world_state.register_agent(agent.agent_id, agent_cfg["starting_location"])
        for item_id in agent_cfg.get("inventory", []):
            world_state.add_item_to_agent_inventory(agent.agent_id, item_id)

        agent.definition_id = agent_cfg.get("definition_id")
        agent.slot_id = agent_cfg.get("slot_id")
        agents.append(agent)

    return world_state, agents


def run_demo_simulation(
    rounds: int = 10,
    delay_seconds: float = 0.3,
    config_dir: str = "scenarios/default",
    llm_base_url: str = "http://localhost:1234/v1",
    llm_model: str = "local-model"
) -> tuple[list[list[dict]], dict]:
    """
    Run a complete demo simulation.

    Args:
        rounds: Number of cycles to run
        delay_seconds: Sleep between cycles (set to 0 for fast execution)
        llm_base_url: URL of local LLM inference engine
        llm_model: Model name to use

    Returns:
        Tuple of (all_cycle_results, final_relationships)
    """
    print("\n" + "="*60)
    print("🚀 SILICON FRONTIER - DEMO SIMULATION")
    print("="*60)

    # Load configuration
    world_state, agents = load_config(config_dir=config_dir, llm_base_url=llm_base_url, llm_model=llm_model)
    scenario_manifest = load_scenario_manifest(config_dir)

    print(f"\n📍 World loaded: {len(world_state.locations)} locations, "
          f"{len(world_state.items)} items")
    print(f"👥 Agents initialized: {[a.name for a in agents]}")

    # Initialize components
    action_parser = ActionParser(world_state)
    social_matrix = SocialMatrix()
    orchestrator = Orchestrator(
        agents=agents,
        world_state=world_state,
        action_parser=action_parser,
        social_matrix=social_matrix,
        reflection_interval=5,  # Reflect every 5 cycles
        progression_config=scenario_manifest.get("progression"),
        resolution_config=scenario_manifest.get("resolution_rules")
    )

    # Run simulation
    all_results = orchestrator.run_simulation(rounds=rounds, delay_seconds=delay_seconds)

    # Print final state summary
    print("\n" + "="*60)
    print("📊 FINAL STATE SUMMARY")
    print("="*60)

    for agent in agents:
        loc = world_state.get_agent_location(agent.agent_id)
        inventory = [item["name"] for item in world_state.find_items_by_owner(agent.agent_id)]
        print(f"\n{agent.name}:")
        print(f"  Location: {loc}")
        print(f"  Inventory: {', '.join(inventory) if inventory else 'empty'}")

    # Print relationships
    print("\n🤝 RELATIONSHIP MATRIX:")
    for agent in agents:
        summary = orchestrator.get_relationship_snapshot().get(agent.agent_id, {})
        print(f"\n{agent.name}'s view of others:")
        for other_id, rel_data in summary.items():
            if other_id == agent.agent_id:
                continue
            trust = rel_data["trust"]
            affinity = rel_data["affinity"]
            status = "trusted" if trust > 70 else "distrusted" if trust < 30 else "neutral"
            print(f"  {other_id}: T={trust} ({status}), A={affinity}")

    return all_results, orchestrator.get_relationship_snapshot()


def run_quick_test(
    rounds: int = 5,
    config_dir: str = "scenarios/default",
    llm_base_url: str = "http://192.168.3.181:1234/v1",
    llm_model: str = "unsloth/qwen3.5-35b-a3b"
) -> None:
    """Run a quick test without delays (for automated testing)."""
    run_demo_simulation(
        rounds=rounds,
        delay_seconds=0,
        config_dir=config_dir,
        llm_base_url=llm_base_url,
        llm_model=llm_model
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Silicon Frontier simulation")
    parser.add_argument(
        "--rounds", "-r",
        type=int,
        default=10,
        help="Number of simulation cycles (default: 10)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.3,
        help="Delay between cycles in seconds (default: 0.3, use 0 for fast mode)"
    )
    parser.add_argument(
        "--config-dir", "-c",
        type=str,
        default="scenarios/default",
        help="Configuration directory containing world_state.json and agent config files (default: scenarios/default)"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default="http://192.168.3.181:1234/v1",
        help="LLM inference engine URL (default: http://192.168.3.181:1234/v1)"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="unsloth/qwen3.5-35b-a3b",
        help="Model name to use (default: unsloth/qwen3.5-35b-a3b)"
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable log file output (print to terminal only)"
    )

    args = parser.parse_args()

    tee = None if args.no_log else _start_logging(args.config_dir)
    try:
        run_demo_simulation(
            rounds=args.rounds,
            delay_seconds=args.delay,
            config_dir=args.config_dir,
            llm_base_url=args.url,
            llm_model=args.model
        )
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _stop_logging(tee)
