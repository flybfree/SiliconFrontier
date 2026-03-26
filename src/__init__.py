# Silicon Frontier - AI Agentic Simulation Framework
"""
A sandbox for observing emergent social behaviors and decision-making logic
in LLM-based agents within a constrained, verifiable environment.
"""

from .worldstate import WorldState
from .agent import FrontierAgent
from .actionparser import ActionParser
from .socialmatrix import SocialMatrix
from .orchestrator import Orchestrator

__version__ = "0.1.0"
__all__ = ["WorldState", "FrontierAgent", "ActionParser", "SocialMatrix", "Orchestrator"]
