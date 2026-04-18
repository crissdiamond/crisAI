from __future__ import annotations

import asyncio

import typer
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory

from crisai.config import load_settings
from crisai.registry import Registry

from .chat_session import cli_history_file, open_session
from .commands import parse_chat_command
from .display import console, print_help, print_history
from .pipelines import run_peer_pipeline, run_pipeline, run_single

app = typer.Typer(help="crisAI CLI")


def load_registry():
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    server_specs = {s.id: s for s in registry.load_servers() if s.enabled}
    agent_specs = {a.id: a for a in registry.load_agents()}
    return settings, registry, server_specs, agent_specs


@app.command("list-servers")
def list_servers() -> None:
    settings = load_settings()
    registry = Registry(settings.registry_dir)
    servers = registry.load_servers()

    console.print(f"Registry dir: {settings.registry_dir}")
    console.print(f"Loaded servers: {len(servers)}")

    for spec in servers:
        console.print(
            f"{spec.id} | enabled={spec.enabled} | transport={spec.transport} | tags={','.join(spec.tags)}"
        )


@app.command("list-agents")
def list_agents() -> None:
    _, _, _, agent_specs = load_registry()
    console.print(f"Loaded agents: {len(agent_specs)}")
    for spec in agent_specs.values():
        console.print(f"{spec.id} | model={spec.model} | servers={','.join(spec.allowed_servers)}")


@app.command()
def ask(
    message: str = typer.Option(..., "--message", "-m"),
    agent_id: str = typer.Option("orchestrator", "--agent"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible discovery/design/review/orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: discovery -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    settings, _, server_specs, agent_specs = load_registry()

    async def _run() -> None:
        if peer:
            text = await run_peer_pipeline(
                message,
                verbose,
                review,
                settings=settings,
                server_specs=server_specs,
                agent_specs=agent_specs,
            )
        elif pipeline:
            text = await run_pipeline(
                message,
                verbose,
                review,
                settings=settings,
                server_specs=server_specs,
                agent_specs=agent_specs,
            )
        else:
            text = await run_single(
                message,
                agent_id,
                settings=settings,
                server_specs=server_specs,
                agent_specs=agent_specs,
            )

        from rich.markdown import Markdown
        console.print(Markdown(text))

    asyncio.run(_run())


@app.command()
def chat(
    agent_id: str = typer.Option("orchestrator", "--agent"),
    session: str = typer.Option("default", "--session", "-s", help="Persistent chat session name."),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run the visible discovery/design/review/orchestrator pipeline."),
    peer: bool = typer.Option(False, "--peer", help="Run the peer workflow: discovery -> author -> challenger -> refiner -> judge -> orchestrator."),
    review: bool = typer.Option(False, "--review/--no-review", help="Review is off by default. Use --review to enable it."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Interactive chat loop for crisAI.
    Commands:
      /exit            quit
      /mode single     use single-agent mode
      /mode pipeline   use pipeline mode
      /mode peer       use peer mode
      /review on       enable review
      /review off      disable review
      /clear           clear conversation history
      /agent <id>      set single-agent target
      /help            show commands
    """
    settings, _, server_specs, agent_specs = load_registry()

    chat_session = open_session(session)
    current_mode = "peer" if peer else "pipeline" if pipeline else "single"
    current_agent = agent_id
    current_review = review

    console.print("[bold green]crisAI interactive chat[/bold green]")
    console.print(f"Session: [bold]{chat_session.name}[/bold]")
    console.print(f"Mode: [bold]{current_mode}[/bold] | Agent: [bold]{current_agent}[/bold]")
    console.print(f"Review: [bold]{'on' if current_review else 'off'}[/bold]")
    console.print(f"Loaded history entries: [bold]{len(chat_session.history)}[/bold]")
    console.print("Type /help for commands.\n")

    async def _dispatch(user_input: str) -> str:
        chat_input = chat_session.build_chat_input(user_input)

        if current_mode == "peer":
            return await run_peer_pipeline(
                chat_input,
                verbose,
                current_review,
                settings=settings,
                server_specs=server_specs,
                agent_specs=agent_specs,
            )
        if current_mode == "pipeline":
            return await run_pipeline(
                chat_input,
                verbose,
                current_review,
                settings=settings,
                server_specs=server_specs,
                agent_specs=agent_specs,
            )
        return await run_single(
            chat_input,
            current_agent,
            settings=settings,
            server_specs=server_specs,
            agent_specs=agent_specs,
        )

    while True:
        try:
            user_input = prompt(
                "> ",
                history=FileHistory(str(cli_history_file())),
                auto_suggest=AutoSuggestFromHistory(),
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nExiting.")
            break

        if not user_input:
            continue

        command = parse_chat_command(user_input)
        if command.handled:
            if command.action == "exit":
                break
            if command.action == "help":
                print_help()
                continue
            if command.action == "clear":
                chat_session.clear()
                console.print(
                    f"[yellow]Conversation history cleared for session '{chat_session.name}'.[/yellow]"
                )
                continue
            if command.action == "history":
                print_history(chat_session.history)
                continue
            if command.action == "switch_session":
                chat_session.switch(str(command.value))
                console.print(f"[green]Switched to session '{chat_session.name}'.[/green]")
                console.print(f"[green]Loaded history entries: {len(chat_session.history)}[/green]")
                continue
            if command.action == "set_mode":
                current_mode = str(command.value)
                console.print(f"[green]Mode set to {current_mode}[/green]")
                continue
            if command.action == "set_review":
                current_review = bool(command.value)
                console.print(f"[green]Review {'enabled' if current_review else 'disabled'}.[/green]")
                continue
            if command.action == "set_agent":
                current_agent = str(command.value)
                console.print(f"[green]Single-agent target set to {current_agent}[/green]")
                continue
            if command.action == "invalid":
                console.print(f"[red]{command.message}[/red]")
                continue

        async def _run() -> str:
            return await _dispatch(user_input)

        try:
            text = asyncio.run(_run())
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        from rich.markdown import Markdown
        console.print()
        console.print(Markdown(text))
        console.print()

        chat_session.append_user_message(user_input)
        chat_session.append_assistant_message(text)
        chat_session.save()


if __name__ == "__main__":
    app()
