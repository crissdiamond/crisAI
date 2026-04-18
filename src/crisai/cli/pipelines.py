from __future__ import annotations

import asyncio
import io
import logging
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import typer
from agents import Runner

from crisai.agents.factory import AgentFactory
from crisai.runtime import MultiServerContext, RuntimeManager
from crisai.tracing import append_trace

from .display import create_agent_live, print_agent_output, update_agent_live
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


_NOISY_LOGGERS = [
    "mcp",
    "mcp.server",
    "mcp.client",
    "server",
    "httpx",
    "httpcore",
    "openai",
    "agents",
    "asyncio",
    "uvicorn",
]


class _DropListToolsRequestFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "Processing request of type ListToolsRequest" not in message


_LOG_FILTER = _DropListToolsRequestFilter()


def _suppress_noisy_runtime_logs() -> tuple[dict[str, int], int]:
    previous: dict[str, int] = {}
    manager_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    for name in _NOISY_LOGGERS:
        logger = logging.getLogger(name)
        previous[name] = logger.level
        logger.setLevel(logging.CRITICAL)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(_LOG_FILTER)
    return previous, manager_disable


def _restore_noisy_runtime_logs(previous: dict[str, int], manager_disable: int) -> None:
    logging.disable(manager_disable)
    for name, level in previous.items():
        logging.getLogger(name).setLevel(level)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        try:
            handler.removeFilter(_LOG_FILTER)
        except Exception:
            pass


async def _run_agent_silently(agent, prompt: str) -> str:
    previous, manager_disable = _suppress_noisy_runtime_logs()
    result = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = await Runner.run(agent, prompt)
    finally:
        _restore_noisy_runtime_logs(previous, manager_disable)
    return str(result.final_output)


async def _run_agent_with_progress(agent_id: str, agent, prompt: str) -> str:
    live = create_agent_live(agent_id)
    tick = 0
    task = asyncio.create_task(_run_agent_silently(agent, prompt))
    with live:
        while not task.done():
            update_agent_live(live, agent_id, tick)
            await asyncio.sleep(0.2)
            tick += 1
        result = await task
        update_agent_live(live, agent_id, tick, done=True)
    return result


_FINAL_RECOMMENDATION_PATTERNS = [
    r"(?:^|\n)#+\s*Final recommendation\s*\n+(.*)$",
    r"(?:^|\n)\*\*Final recommendation\*\*\s*\n+(.*)$",
    r"(?:^|\n)Final recommendation\s*\n+(.*)$",
]


def _extract_final_recommendation(text: str) -> str:
    stripped = text.strip()
    for pattern in _FINAL_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, stripped, flags=re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted
    return stripped


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
        return await _run_agent_silently(agent, message)


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

        discovery_agent = factory.build_agent(discovery_spec, active_servers)
        discovery_text = await _run_agent_with_progress("discovery", discovery_agent, build_discovery_prompt(message))
        append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
        print_agent_output("discovery", discovery_text, verbose=verbose)

        design_agent = factory.build_agent(design_spec, active_servers)
        design_text = await _run_agent_with_progress("design", design_agent, build_design_prompt(message, discovery_text))
        append_trace(trace_file, "DESIGN OUTPUT", design_text)
        print_agent_output("design", design_text, verbose=verbose)

        if review:
            review_agent = factory.build_agent(review_spec, active_servers)
            review_text = await _run_agent_with_progress(
                "review", review_agent, build_review_prompt(message, discovery_text, design_text)
            )
            append_trace(trace_file, "REVIEW OUTPUT", review_text)
            print_agent_output("review", review_text, verbose=verbose)
        else:
            review_text = "Review stage skipped because review is disabled."
            append_trace(trace_file, "REVIEW OUTPUT", review_text)

        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_text = await _run_agent_with_progress(
            "orchestrator",
            orchestrator_agent,
            build_pipeline_final_prompt(message, discovery_text, design_text, review_text),
        )
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
            discovery_agent = factory.build_agent(discovery_spec, active_servers)
            discovery_text = await _run_agent_with_progress(
                "discovery", discovery_agent, build_discovery_prompt(message)
            )
            append_trace(trace_file, "DISCOVERY OUTPUT", discovery_text)
            print_agent_output("discovery", discovery_text, verbose=verbose)
        else:
            append_trace(trace_file, "DISCOVERY OUTPUT", "Discovery skipped because this peer task does not require retrieval.")

        author_agent = factory.build_agent(author_spec, active_servers)
        author_text = await _run_agent_with_progress(
            "design_author", author_agent, build_author_prompt(message, discovery_text or "None.")
        )
        append_trace(trace_file, "AUTHOR OUTPUT", author_text)
        print_agent_output("design_author", author_text, verbose=verbose)

        challenger_agent = factory.build_agent(challenger_spec, active_servers)
        challenger_text = await _run_agent_with_progress(
            "design_challenger",
            challenger_agent,
            build_challenger_prompt(message, discovery_text or "None.", author_text),
        )
        append_trace(trace_file, "CHALLENGER OUTPUT", challenger_text)
        print_agent_output("design_challenger", challenger_text, verbose=verbose)

        refiner_agent = factory.build_agent(refiner_spec, active_servers)
        refiner_text = await _run_agent_with_progress(
            "design_refiner",
            refiner_agent,
            build_refiner_prompt(message, discovery_text or "None.", author_text, challenger_text),
        )
        append_trace(trace_file, "REFINER OUTPUT", refiner_text)
        print_agent_output("design_refiner", refiner_text, verbose=verbose)

        judge_agent = factory.build_agent(judge_spec, active_servers)
        judge_text = await _run_agent_with_progress(
            "judge",
            judge_agent,
            build_judge_prompt(message, discovery_text or "None.", challenger_text, refiner_text),
        )
        append_trace(trace_file, "JUDGE OUTPUT", judge_text)
        print_agent_output("judge", judge_text, verbose=verbose)

        orchestrator_agent = factory.build_agent(orchestrator_spec, active_servers)
        final_text = await _run_agent_with_progress(
            "orchestrator",
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
        append_trace(trace_file, "FINAL OUTPUT", final_text)
        return _extract_final_recommendation(final_text)


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
