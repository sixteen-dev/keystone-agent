"""Orchestrator agent (Keystone) that coordinates all specialists."""

from agents import Agent, ModelSettings

from keystone_agent.agents.tools import (
    build_run_all_specialists_tool,
    build_specialist_tools,
)
from keystone_agent.config import settings
from keystone_agent.schemas import BoardFinalOutput
from keystone_agent.utils.prompt_loader import load_prompt


def build_orchestrator_agent() -> tuple[Agent, dict[str, Agent]]:
    """
    Build the orchestrator agent with all specialist tools.

    Returns:
        Tuple of (orchestrator Agent, dict of specialist Agents)
    """
    # Build specialist tools and agents
    specialist_tools, specialist_agents = build_specialist_tools()

    # Build the run_all_specialists tool
    run_all_tool = build_run_all_specialists_tool(specialist_agents)

    # Load orchestrator prompt
    try:
        system_prompt = load_prompt("orchestrator")
    except FileNotFoundError:
        system_prompt = (
            "You are Keystone, the Board Orchestrator. "
            "Your job is to coordinate all specialist board members, "
            "synthesize their inputs, and produce a final verdict. "
            "Always use run_all_specialists to get comprehensive feedback."
        )

    # All tools: individual specialists + run_all
    all_tools = specialist_tools + [run_all_tool]

    orchestrator = Agent(
        name="Keystone",
        instructions=system_prompt,
        model=settings.orchestrator_model,
        tools=all_tools,
        output_type=BoardFinalOutput,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            reasoning={"effort": "medium"},
        ),
    )

    return orchestrator, specialist_agents
