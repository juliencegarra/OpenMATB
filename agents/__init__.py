# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from agents.abstract_agent import AbstractAgent
from agents.default_agent import DefaultAgent

AGENT_REGISTRY: dict[str, type[AbstractAgent]] = {
    "default": DefaultAgent,
    "supervisory": DefaultAgent,
}


def create_agent(name: str) -> AbstractAgent:
    if name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {name}")
    return AGENT_REGISTRY[name]()
