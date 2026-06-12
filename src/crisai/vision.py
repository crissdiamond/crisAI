"""Shared vision helpers: image description and PDF page rasterisation.

The vision model call and PDF-to-image rendering live here so both the vision
MCP server and the document reader can reuse one implementation. Rendering uses
``pypdfium2`` (a pure-Python wheel, no system binaries) and ``Pillow`` to encode
pages as PNG for the vision model.
"""
from __future__ import annotations

import base64
import io
import os
from collections.abc import Iterable

import openai
import pypdfium2 as pdfium

_DEFAULT_VISION_MODEL = "gpt-4o-mini"
_MAX_TOKENS = 500


def vision_model() -> str:
    """Return the configured vision model reference."""
    return os.getenv("CRISAI_VISION_MODEL", _DEFAULT_VISION_MODEL)


def describe_image_blob(blob: bytes, content_type: str, prompt: str) -> str:
    """Call the vision model with a base64-encoded image and return its description."""
    b64 = base64.b64encode(blob).decode("ascii")
    data_url = f"data:{content_type};base64,{b64}"
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model=vision_model(),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=_MAX_TOKENS,
    )
    return response.choices[0].message.content or ""


def render_pdf_pages_png(
    pdf_bytes: bytes, page_indices: Iterable[int], *, scale: float = 2.0
) -> dict[int, bytes]:
    """Render the requested 0-based PDF pages to PNG bytes.

    Args:
        pdf_bytes: Raw PDF file contents.
        page_indices: 0-based page indices to render.
        scale: Render scale; 2.0 keeps small text legible for the vision model.

    Returns:
        A mapping of page index to PNG bytes. Indices outside the document are
        skipped.
    """
    wanted = sorted({index for index in page_indices if index >= 0})
    if not wanted:
        return {}

    rendered: dict[int, bytes] = {}
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page_count = len(pdf)
        for index in wanted:
            if index >= page_count:
                continue
            bitmap = pdf[index].render(scale=scale)
            buffer = io.BytesIO()
            bitmap.to_pil().save(buffer, format="PNG")
            rendered[index] = buffer.getvalue()
    finally:
        pdf.close()
    return rendered
