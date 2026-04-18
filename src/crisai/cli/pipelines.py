from __future__ import annotations

from pathlib import Path

import typer
from agents import Runner

from crisai.agents.factory import AgentFactory
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import append_trace

from .display import print_markdown, print_stage
from .prompt_builders import (
    build_author_prompt,
    build_challenger_prompt,
    build_design_prompt,
    build_discovery_prompt,
    build_judge_prompt,
    build_peer_final_prompt,
    build_pipeline_final_prompt,
    build_refiner_prompt,
    build_review_prompt,
)


def build_agent_servers(runtime: RuntimeManager, agent_spec, server_specs):
    servers = []
    for server_id in agent_spec.allowed_servers:
        spec = server_specs.get(server_id)
        if spec:
            servers.append(runtime.build_server(spec))
    return servers


async def run_single(message: str, agent_id: str, *, settings, server_specs, agent_specs) -> str:
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    if agent_id not in agent_specs:
        raise typer.BadParameter(f"Unknown agent_id: {agent_id}")

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    agent_spec = agent_specs[agent_id]
    servers = build_agent_servers(runtime, agent_spec, server_specs)

    async with MultiServerContext(servers) as active_servers:
        agent = factory.build_agent(agent_spec, active_servers)
        result = await Runner.run(agent, message)
        return str(result.final_output)


async def run_pipeline(message: str, verbose: bool, review: bool, *, settings, server_specs, agent_specs) -> str:
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    trace_file = settings.log_dir / "agent_trace.log"

    discovery_spec = agent_specs["discovery"]
    design_spec = agent_specs["design"]
    review_spec = agent_specs["review"]
    orchestrator_spec = agent_specs["orchestrator"]

    all_server_ids = sorted(
        {
            *discovery_spec.allowed_servers,
            *design_spec.allowed_servers,
            *review_spec.allowed_servers,
            *orchestrator_spec.allowed_servers,
        }
    )
    servers = [runtime.build_server(server_specs[sid]) for sid in all_server_ids if sid in server_specs]

    async with MultiServerContext(servers) as active_servers:
        append_trace(trace_file, "USER INPUT", message)

        if verbose:
            print_stage("Running Discovery Agent", "cyan")
        discovery_agent = factory.build_agent(discovery_spec, active_servers)
        discovery_result = await Runner.run(discovery_agent, build_discovery_prompt(message))
        discovery_text = str(discovery_result.final_output)
        append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
        if verbose:
            print_markdown("Discovery Agent", discovery_text)

        if verbose:
            print_stage("Running Design Agent", "green")
        design_agent = factory.build_agent(design_spec, active_servers)
        design_result = await Runner.run(design_agent, build_design_prompt(message, discovery_text))
        design_text = str(design_result.final_output)
        append_trace(trace_file, "DESIGN OUTPUT", design_text)
        if verbose:
            print_markdown("Design Agent", design_text)

        if review:
            if verbose:
                print_stage("Running Review Agent", "yellow")
            review_agent = factory.build_agent(review_spec, active_servers)
            review_result = await Runner.run(review_agent, build_review_prompt(message, discovery_text, design_text))
            review_text = str(review_result.final_output)
            append_trace(trace_file, "REVIEW OUTPUT", review_text)
            if verbose:
                print_markdown("Review Agent", review_text)
        else:
            review_text = "Review stage skipped because review is disabled."
            append_trace(trace_file, "REVIEW OUTPUT", review_text)
            if verbose:
                print_stage("Skipping Review Agent", "yellow")

        if verbose:
            print_stage("Running Orchestrator", "magenta")
        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_result = await Runner.run(
            orchestrator_agent,
            build_pipeline_final_prompt(message, discovery_text, design_text, review_text),
        )
        final_text = str(final_result.final_output)
        append_trace(trace_file, "FINAL OUTPUT", final_text)
        return final_text


async def run_peer_pipeline(message: str, verbose: bool, review: bool, *, settings, server_specs, agent_specs, needs_retrieval: bool = True) -> str:
    if not settings.openai_api_key:
        raise typer.BadParameter("OPENAI_API_KEY is not set.")

    required_agents = [
        "design_author",
        "design_challenger",
        "design_refiner",
        "judge",
        "orchestrator",
    ]
    if needs_retrieval:
        required_agents.insert(0, "discovery")
    missing = [agent_id for agent_id in required_agents if agent_id not in agent_specs]
    if missing:
        raise typer.BadParameter(
            f"Peer mode requires these agents in registry/agents.yaml: {', '.join(missing)}"
        )

    root_dir = Path.cwd()
    runtime = RuntimeManager(root_dir)
    factory = AgentFactory(root_dir)
    trace_file = settings.log_dir / "agent_trace.log"

    discovery_spec = agent_specs["discovery"]
    author_spec = agent_specs["design_author"]
    challenger_spec = agent_specs["design_challenger"]
    refiner_spec = agent_specs["design_refiner"]
    judge_spec = agent_specs["judge"]
    orchestrator_spec = agent_specs["orchestrator"]

    all_server_ids = set()
    if needs_retrieval:
        all_server_ids.update(discovery_spec.allowed_servers)
    all_server_ids.update(author_spec.allowed_servers)
    all_server_ids.update(challenger_spec.allowed_servers)
    all_server_ids.update(refiner_spec.allowed_servers)
    all_server_ids.update(judge_spec.allowed_servers)
    all_server_ids.update(orchestrator_spec.allowed_servers)
    servers = [runtime.build_server(server_specs[sid]) for sid in sorted(all_server_ids) if sid in server_specs]

    async with MultiServerContext(servers) as active_servers:
        append_trace(trace_file, "USER INPUT", message)

        discovery_text = ""
        if needs_retrieval:
            if verbose:
                print_stage("Running Discovery Agent", "cyan")
            discovery_agent = factory.build_agent(discovery_spec, active_servers)
            discovery_result = await Runner.run(discovery_agent, build_discovery_prompt(message))
            discovery_text = str(discovery_result.final_output)
            append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
            if verbose:
                print_markdown("Discovery Agent", discovery_text)
        else:
            append_trace(trace_file, "DISCOVERY OUTPUT", "Discovery skipped because this peer task does not require retrieval.")

        if verbose:
            print_stage("Running Design Author", "green")
        author_agent = factory.build_agent(author_spec, active_servers)
        author_result = await Runner.run(author_agent, build_author_prompt(message, discovery_text or "None."))
        author_text = str(author_result.final_output)
        append_trace(trace_file, "AUTHOR OUTPUT", author_text)
        if verbose:
            print_markdown("Design Author", author_text)

        if verbose:
            print_stage("Running Design Challenger", "yellow")
        challenger_agent = factory.build_agent(challenger_spec, active_servers)
        challenger_result = await Runner.run(
            challenger_agent,
            build_challenger_prompt(message, discovery_text or "None.", author_text),
        )
        challenger_text = str(challenger_result.final_output)
        append_trace(trace_file, "CHALLENGER OUTPUT", challenger_text)
        if verbose:
            print_markdown("Design Challenger", challenger_text)

        if verbose:
            print_stage("Running Design Refiner", "blue")
        refiner_agent = factory.build_agent(refiner_spec, active_servers)
        refiner_result = await Runner.run(
            refiner_agent,
            build_refiner_prompt(message, discovery_text or "None.", author_text, challenger_text),
        )
        refiner_text = str(refiner_result.final_output)
        append_trace(trace_file, "REFINER OUTPUT", refiner_text)
        if verbose:
            print_markdown("Design Refiner", refiner_text)

        if verbose:
            print_stage("Running Judge", "magenta")
        judge_agent = factory.build_agent(judge_spec, active_servers)
        judge_result = await Runner.run(
            judge_agent,
            build_judge_prompt(message, discovery_text or "None.", challenger_text, refiner_text),
        )
        judge_text = str(judge_result.final_output)
        append_trace(trace_file, "JUDGE OUTPUT", judge_text)
        if verbose:
            print_markdown("Judge", judge_text)

        if verbose:
            print_stage("Running Orchestrator", "white")
        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_result = await Runner.run(
            orchestrator_agent,
            build_peer_final_prompt(
                message,
                discovery_text or "None.",
                author_text,
                challenger_text,
                refiner_text,
                judge_text,
            ),
        )
        final_text = str(final_result.final_output)
        append_trace(trace_file, "FINAL OUTPUT", final_text)
        return final_text


from .peer_transcript import PeerRunResult, append_peer_message


def build_peer_run_result(
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
    final_text: str,
) -> PeerRunResult:
    transcript = []
    append_peer_message(transcript, "discovery", discovery_text)
    append_peer_message(transcript, "design_author", author_text)
    append_peer_message(transcript, "design_challenger", challenger_text)
    append_peer_message(transcript, "design_refiner", refiner_text)
    append_peer_message(transcript, "judge", judge_text)
    append_peer_message(transcript, "orchestrator", final_text)
    return PeerRunResult(final_text=final_text, transcript=transcript)
