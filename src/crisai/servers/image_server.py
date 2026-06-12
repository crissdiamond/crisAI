from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from crisai.config import load_settings
from crisai.logging_utils import append_json_log_line, configure_mcp_framework_logging
from crisai.powerpoint import extract_slide_images
from crisai.vision import describe_image_blob
from crisai.workspace.safety import resolve_workspace_path

mcp = FastMCP("crisai-vision")

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = load_settings().log_dir / "vision_mcp.log"

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_DEFAULT_PROMPT = "Describe this image concisely."

_SUFFIX_TO_CONTENT_TYPE: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _configure_mcp_logging() -> None:
    configure_mcp_framework_logging(LOG_FILE, service_component="vision_mcp")


def log_event(message: str) -> None:
    append_json_log_line(
        LOG_FILE,
        message,
        logger_name="crisai.mcp.vision",
        service_component="vision_mcp",
    )


_configure_mcp_logging()
log_event(f"server_started root={ROOT}")


def _safe_path(relative_path: str) -> Path:
    return resolve_workspace_path(ROOT, relative_path)


@mcp.tool()
def describe_image(path: str, prompt: str = "") -> str:
    """Describe a standalone image file in the workspace using a vision model."""
    log_event(f"describe_image path={path}")
    file_path = _safe_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError(
            f"Unsupported image type: {suffix or 'no extension'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_IMAGE_SUFFIXES))}"
        )
    blob = file_path.read_bytes()
    content_type = _SUFFIX_TO_CONTENT_TYPE[suffix]
    return describe_image_blob(blob, content_type, prompt or _DEFAULT_PROMPT)


@mcp.tool()
def describe_powerpoint_slide_images(
    path: str,
    slide_numbers: list[int] | None = None,
    prompt: str = "",
) -> list[dict[str, Any]]:
    """Describe images embedded in a PowerPoint file, optionally restricted to specific slides.

    Args:
        path: Workspace-relative path to a .pptx file.
        slide_numbers: Slide numbers to process (1-based). Empty or None means all slides.
        prompt: Custom prompt for the vision model. Defaults to a brief description request.

    Returns:
        One entry per image: slide_number, image_index, content_type, description.
        Returns an empty list if no images are found.
    """
    log_event(f"describe_powerpoint_slide_images path={path} slides={slide_numbers}")
    file_path = _safe_path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")
    if file_path.suffix.lower() != ".pptx":
        raise ValueError(f"Expected a .pptx file, got: {file_path.suffix or 'no extension'}")

    images = extract_slide_images(file_path.read_bytes())

    if slide_numbers:
        slide_set = set(slide_numbers)
        images = [img for img in images if img["slide_number"] in slide_set]

    effective_prompt = prompt or _DEFAULT_PROMPT
    results: list[dict[str, Any]] = []
    for img in images:
        description = describe_image_blob(
            img["blob"],  # type: ignore[arg-type]
            img["content_type"],  # type: ignore[arg-type]
            effective_prompt,
        )
        results.append(
            {
                "slide_number": img["slide_number"],
                "image_index": img["image_index"],
                "content_type": img["content_type"],
                "description": description,
            }
        )
    return results


if __name__ == "__main__":
    mcp.run()
