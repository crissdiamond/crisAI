from __future__ import annotations


def _section(title: str, content: str) -> str:
    """Return a simple prompt section with a stable heading format."""
    return f"{title}:\n{content}".strip()


def build_discovery_prompt(message: str) -> str:
    """Build the runtime prompt for the discovery stage."""
    parts = [
        _section("User request", message),
        _section(
            "Task",
            "Inspect the available sources and retrieve the most relevant material for this request.",
        ),
    ]
    return "\n\n".join(parts)


def build_design_prompt(message: str, discovery_text: str) -> str:
    """Build the runtime prompt for the design stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section(
            "Task",
            "Produce the best possible architecture, design, or documentation response for the user's request.",
        ),
    ]
    return "\n\n".join(parts)


def build_review_prompt(message: str, discovery_text: str, design_text: str) -> str:
    """Build the runtime prompt for the review stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Draft design response", design_text),
        _section("Task", "Critically review the draft."),
    ]
    return "\n\n".join(parts)


def build_pipeline_final_prompt(
    message: str,
    discovery_text: str,
    design_text: str,
    review_text: str,
) -> str:
    """Build the runtime prompt for the pipeline final stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Draft design response", design_text),
        _section("Review feedback", review_text or "None."),
        _section("Task", "Produce the final answer to the user."),
        _section(
            "Handoff guidance",
            "Use the design output as the main body, improve it using the review feedback where relevant, and do not mention internal pipeline stages unless the user explicitly asked for them.",
        ),
    ]
    return "\n\n".join(parts)


def build_author_prompt(message: str, discovery_text: str) -> str:
    """Build the runtime prompt for the peer author stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Task", "Produce the best possible first draft for the user's request."),
    ]
    return "\n\n".join(parts)


def build_challenger_prompt(message: str, discovery_text: str, author_text: str) -> str:
    """Build the runtime prompt for the peer challenger stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Draft", author_text),
        _section("Task", "Critique the draft rigorously."),
    ]
    return "\n\n".join(parts)


def build_refiner_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
) -> str:
    """Build the runtime prompt for the peer refiner stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Original draft", author_text),
        _section("Challenge", challenger_text),
        _section("Task", "Refine the draft using the critique."),
    ]
    return "\n\n".join(parts)


def build_judge_prompt(
    message: str,
    discovery_text: str,
    challenger_text: str,
    refiner_text: str,
) -> str:
    """Build the runtime prompt for the peer judge stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Challenge", challenger_text),
        _section("Refined draft", refiner_text),
        _section("Task", "Decide whether the refined answer is good enough."),
    ]
    return "\n\n".join(parts)


def build_peer_final_prompt(
    message: str,
    discovery_text: str,
    author_text: str,
    challenger_text: str,
    refiner_text: str,
    judge_text: str,
) -> str:
    """Build the runtime prompt for the peer final stage."""
    parts = [
        _section("User request", message),
        _section("Discovery findings", discovery_text or "None."),
        _section("Original draft", author_text),
        _section("Challenge", challenger_text),
        _section("Refined draft", refiner_text),
        _section("Judge decision", judge_text),
        _section("Task", "Produce the final answer to the user."),
        _section(
            "Handoff guidance",
            "Use the refined draft as the main body, incorporate only improvements justified by the critique and judge decision, and do not mention internal peer stages unless the user explicitly asked for them.",
        ),
    ]
    return "\n\n".join(parts)
