# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from agents.abstract_agent import AbstractAgent
from agents.actr_agent import ACTRAgent
from agents.assisted_agent import AssistedAgent
from agents.carbonell_agent import CarbonellAgent, CarbonellRevisedAgent
from agents.cooperative_agent import CooperativeAgent
from agents.default_agent import DefaultAgent
from agents.humanlike_agent import HumanLikeAgent
from agents.stom_agent import STOMAgent

AGENT_REGISTRY: dict[str, type[AbstractAgent]] = {
    "default": DefaultAgent,
    "assisted": AssistedAgent,
    "cooperative": CooperativeAgent,
    "supervisory": DefaultAgent,
    "humanlike": HumanLikeAgent,
    "actr": ACTRAgent,
    "carbonell": CarbonellAgent,
    "carbonell_revised": CarbonellRevisedAgent,
    "stom": STOMAgent,
}


def create_agent(name: str) -> AbstractAgent:
    if name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {name}")
    return AGENT_REGISTRY[name]()
