"""Tool functions for the orchestrator agent using OpenAI Agents SDK."""

import asyncio
import json
import logging
from typing import Any

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from keystone_agent.agents.specialists import SPECIALIST_CONFIGS, build_specialist_agent
from keystone_agent.storage.session import DynamoDBSession


class SpecialistRequestInput(BaseModel):
    """Input for specialist agent tools."""

    request_text: str = Field(..., description="The user's request or question")
    mode: str = Field(default="review", description="Mode: review, decide, audit, creative")
    context: str = Field(default="", description="Additional context (project history, options, etc.)")


class AllSpecialistsInput(BaseModel):
    """Input for running all specialists in parallel."""

    request_text: str = Field(..., description="The user's request or question")
    mode: str = Field(default="review", description="Mode: review, decide, audit, creative")
    orchestrator_guidance: str = Field(
        default="",
        description="Orchestrator's analysis of the user's plan: current phase, stated next steps, risks they've acknowledged, what to evaluate NOW vs what's deferred"
    )
    project_history: str = Field(default="", description="Previous board decisions summary")
    option_a: str = Field(default="", description="Option A for decide mode")
    option_b: str = Field(default="", description="Option B for decide mode")


async def run_specialist_agent(agent: Agent, input_data: SpecialistRequestInput) -> dict[str, Any]:
    """
    Run a specialist agent and return its output.

    Args:
        agent: The specialist Agent instance
        input_data: Input for the specialist

    Returns:
        Dict with specialist output or error info
    """
    try:
        result = await Runner.run(
            starting_agent=agent,
            input=json.dumps(input_data.model_dump()),
            max_turns=3,
        )

        # Extract the final output
        if result.final_output:
            if hasattr(result.final_output, "model_dump"):
                output = result.final_output.model_dump()
            else:
                output = result.final_output
            output["agent_name"] = agent.name
            return output

        return {
            "failed": True,
            "agent_name": agent.name,
            "error": "No output from specialist",
        }

    except Exception as e:
        return {
            "failed": True,
            "agent_name": agent.name,
            "error": str(e)[:200],
        }


def make_specialist_tool(agent: Agent, config):
    """
    Create a function tool that wraps a specialist agent.

    Args:
        agent: The specialist Agent instance
        config: SpecialistConfig with metadata

    Returns:
        A function tool for the orchestrator
    """

    @function_tool(
        name_override=f"consult_{config.codename.lower()}",
        description_override=f"Consult {config.codename} ({config.role}): {config.description}",
    )
    async def specialist_tool(input: SpecialistRequestInput) -> str:
        result = await run_specialist_agent(agent, input)
        return json.dumps(result)

    return specialist_tool


def build_specialist_tools() -> tuple[list, dict[str, Agent]]:
    """
    Build all specialist agents and their corresponding tools.

    Returns:
        Tuple of (list of tools, dict mapping codename to Agent)
    """
    tools = []
    agents: dict[str, Agent] = {}

    for config in SPECIALIST_CONFIGS:
        agent = build_specialist_agent(config)
        agents[config.codename] = agent
        tool = make_specialist_tool(agent, config)
        tools.append(tool)

    return tools, agents


def build_run_all_specialists_tool(agents: dict[str, Agent]):
    """
    Build a tool that runs all specialists in parallel.

    Args:
        agents: Dict mapping codename to Agent instance

    Returns:
        Function tool for parallel specialist execution
    """

    @function_tool(
        name_override="run_all_specialists",
        description_override="Run all 7 specialist board members in parallel and return their combined analysis as a dict.",
    )
    async def run_all_specialists_tool(input: AllSpecialistsInput) -> str:
        """Execute all specialists in parallel and aggregate results."""

        logger.debug(
            "run_all_specialists called: mode=%s, guidance_length=%d, request=%s...",
            input.mode,
            len(input.orchestrator_guidance or ""),
            input.request_text[:100],
        )

        # Build context string
        # NOTE: project_history is NOT passed to specialists to avoid anchoring bias
        # History should only inform the orchestrator's final synthesis
        context_parts = []
        if input.orchestrator_guidance:
            context_parts.append(f"ORCHESTRATOR GUIDANCE:\n{input.orchestrator_guidance}")
        if input.option_a:
            context_parts.append(f"Option A: {input.option_a}")
        if input.option_b:
            context_parts.append(f"Option B: {input.option_b}")

        context_str = "\n".join(context_parts)

        specialist_input = SpecialistRequestInput(
            request_text=input.request_text,
            mode=input.mode,
            context=context_str,
        )

        logger.debug("Specialists context: %s", context_str or "(EMPTY)")

        # Run all specialists in parallel
        tasks = [run_specialist_agent(agent, specialist_input) for agent in agents.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        outputs: dict[str, Any] = {}
        for codename, result in zip(agents.keys(), results):
            if isinstance(result, Exception):
                outputs[codename] = {
                    "failed": True,
                    "agent_name": codename,
                    "error": str(result)[:200],
                }
            else:
                outputs[codename] = result

        return json.dumps(outputs)

    return run_all_specialists_tool


async def get_project_history(project_id: str, limit: int = 5) -> list[dict]:
    """
    Retrieve recent board decisions for a project.

    Args:
        project_id: The project identifier
        limit: Maximum number of decisions to return

    Returns:
        List of past decision summaries
    """
    return await DynamoDBSession.get_project_history(project_id, limit)


def format_history_for_context(history: list[dict]) -> str:
    """Format project history as a context string."""
    if not history:
        return ""

    lines = []
    for h in history[:5]:
        date = h.get("created_at", "N/A")[:10]
        verdict = h.get("verdict", "N/A")
        confidence = h.get("confidence", 0)
        summary = h.get("request_summary", "")[:50]
        lines.append(f"- {date}: {verdict.upper()} ({confidence:.0%}) - {summary}...")

    return "\n".join(lines)
