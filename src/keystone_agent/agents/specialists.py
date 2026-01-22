"""Specialist agent definitions using OpenAI Agents SDK.

Each specialist is an Agent that:
- Has a specific role/codename
- Uses a dedicated system prompt
- Returns structured output via Pydantic schema
"""

from dataclasses import dataclass
from typing import Type

from agents import Agent, ModelSettings
from pydantic import BaseModel

from keystone_agent.config import settings
from keystone_agent.schemas import BoardMemberOutput, ProductPuristOutput
from keystone_agent.utils.prompt_loader import load_prompt


@dataclass
class SpecialistConfig:
    """Configuration for a specialist agent."""

    codename: str
    role: str
    prompt_file: str
    output_schema: Type[BaseModel]
    description: str


# Specialist configurations
SPECIALIST_CONFIGS: list[SpecialistConfig] = [
    SpecialistConfig(
        codename="Lynx",
        role="product_operator",
        prompt_file="product_operator",
        output_schema=BoardMemberOutput,
        description="User pain, UX friction, adoption, retention",
    ),
    SpecialistConfig(
        codename="Wildfire",
        role="growth_distribution",
        prompt_file="growth_distribution",
        output_schema=BoardMemberOutput,
        description="Acquisition loops, channels, spread mechanics",
    ),
    SpecialistConfig(
        codename="Bedrock",
        role="systems_architecture",
        prompt_file="systems_architecture",
        output_schema=BoardMemberOutput,
        description="Simplest stable system, maintainability, cost",
    ),
    SpecialistConfig(
        codename="Leverage",
        role="capital_allocator",
        prompt_file="capital_allocator",
        output_schema=BoardMemberOutput,
        description="ROI of time, leverage, compounding decisions",
    ),
    SpecialistConfig(
        codename="Sentinel",
        role="risk_reality",
        prompt_file="risk_reality",
        output_schema=BoardMemberOutput,
        description="Blind spots, over-optimism, hidden complexity",
    ),
    SpecialistConfig(
        codename="Prism",
        role="creative_director",
        prompt_file="creative_director",
        output_schema=BoardMemberOutput,
        description="Positioning, narrative, differentiation",
    ),
    SpecialistConfig(
        codename="Razor",
        role="product_purist",
        prompt_file="product_purist",
        output_schema=ProductPuristOutput,
        description="Focus, simplicity, taste, ruthless cuts",
    ),
]


def build_specialist_agent(config: SpecialistConfig) -> Agent:
    """
    Build a specialist Agent from config.

    Args:
        config: Specialist configuration

    Returns:
        Configured Agent instance
    """
    try:
        system_prompt = load_prompt(config.prompt_file)
    except FileNotFoundError:
        system_prompt = f"You are {config.codename}, the {config.role}. {config.description}"

    return Agent(
        name=config.codename,
        instructions=system_prompt,
        model=settings.specialist_model,
        output_type=config.output_schema,
        model_settings=ModelSettings(
            reasoning={"effort": "low"},
        ),
    )


def build_all_specialists() -> dict[str, Agent]:
    """
    Build all specialist agents.

    Returns:
        Dict mapping codename to Agent instance
    """
    return {config.codename: build_specialist_agent(config) for config in SPECIALIST_CONFIGS}


def get_specialist_config(codename: str) -> SpecialistConfig | None:
    """Get specialist config by codename."""
    for spec in SPECIALIST_CONFIGS:
        if spec.codename == codename:
            return spec
    return None


def get_specialist_by_role(role: str) -> SpecialistConfig | None:
    """Get specialist config by role."""
    for spec in SPECIALIST_CONFIGS:
        if spec.role == role:
            return spec
    return None
