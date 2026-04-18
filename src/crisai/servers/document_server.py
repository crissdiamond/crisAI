from __future__ import annotations

import logging
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import chardet
from docx import Document as DocxDocument
from mcp.server.fastmcp import FastMCP
from openpyxl import load_workbook
from pypdf import PdfReader
from pptx import Presentation


mcp = FastMCP("crisai-document-reader")

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = ROOT / "document_mcp.log"




def _configure_mcp_logging() -> None:
    """Keep MCP framework INFO logs out of the interactive CLI.

    Warnings and errors are still written to this server log file.
    """
    logger_names = [
        "mcp",
        "mcp.server",
        "mcp.server.fastmcp",
        "mcp.server.lowlevel",
        "mcp.server.lowlevel.server",
    ]

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.propagate = False

def log_event(message: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {message}\n")


_configure_mcp_logging()

log_event(f"server_started root={ROOT}")


def _safe_path(relative_path: str) -> Path:
    raw = (relative_path or ".").strip()

    if raw.startswith("/"):
        raw = raw.lstrip("/")
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/"):]

    candidate = (ROOT / raw).resolve()
    root = ROOT.resolve()

    if candidate != root and root not in candidate.parents:
        raise ValueError(
            f"Path escapes the workspace root. root={root} requested={relative_path} resolved={candidate}"
        )

    return candidate


def _detect_text_encoding(data: bytes) -> str:
    detected = chardet.detect(data)
    encoding = detected.get("encoding") or "utf-8"
    return encoding


def _read_text_like(file_path: Path) -> str:
    data = file_path.read_bytes()
    encoding = _detect_text_encoding(data)
    try:
        return data.decode(encoding)
    except Exception:
        return data.decode("utf-8", errors="replace")


def _read_docx(file_path: Path) -> str:
    doc = DocxDocument(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n\n".join(paragraphs)


def _read_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(f"[Page {i}]\n{text}")
    return "\n\n".join(pages)


def _read_pptx(file_path: Path) -> str:
    prs = Presentation(str(file_path))
    slides_out = []
    for idx, slide in enumerate(prs.slides, start=1):
        parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                text = shape.text.strip()
                if text:
                    parts.append(text)
        if parts:
            slides_out.append(f"[Slide {idx}]\n" + "\n".join(parts))
    return "\n\n".join(slides_out)


def _read_xlsx(file_path: Path, max_rows: int = 50, max_cols: int = 20) -> str:
    wb = load_workbook(filename=str(file_path), read_only=True, data_only=True)
    out = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        out.append(f"[Sheet: {sheet_name}]")
        row_count = 0

        for row in ws.iter_rows(values_only=True):
            if row_count >= max_rows:
                out.append("... truncated ...")
                break

            values = []
            for cell in row[:max_cols]:
                if cell is None:
                    values.append("")
                else:
                    values.append(str(cell))

            if any(v != "" for v in values):
                out.append(" | ".join(values))
                row_count += 1

        out.append("")

    return "\n".join(out).strip()


def _read_csv(file_path: Path, max_rows: int = 100) -> str:
    data = file_path.read_bytes()
    encoding = _detect_text_encoding(data)
    text = data.decode(encoding, errors="replace")

    reader = csv.reader(io.StringIO(text))
    rows = []
    for idx, row in enumerate(reader):
        if idx >= max_rows:
            rows.append(["... truncated ..."])
            break
        rows.append(row)

    return "\n".join(" | ".join(cell for cell in row) for row in rows)


@mcp.tool()
def read_document(path: str) -> str:
    """Read a document inside the workspace and extract text from common file formats."""
    log_event(f"read_document path={path}")
    file_path = _safe_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")

    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log"}:
        return _read_text_like(file_path)

    if suffix == ".csv":
        return _read_csv(file_path)

    if suffix == ".docx":
        return _read_docx(file_path)

    if suffix == ".pdf":
        return _read_pdf(file_path)

    if suffix == ".pptx":
        return _read_pptx(file_path)

    if suffix == ".xlsx":
        return _read_xlsx(file_path)

    raise ValueError(f"Unsupported document type: {suffix or 'no extension'}")


@mcp.tool()
def get_document_metadata(path: str) -> dict[str, str | int]:
    """Return basic metadata about a document inside the workspace."""
    log_event(f"get_document_metadata path={path}")
    file_path = _safe_path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"No such file: {file_path}")

    stat = file_path.stat()
    return {
        "path": str(file_path.relative_to(ROOT)),
        "name": file_path.name,
        "suffix": file_path.suffix.lower(),
        "size_bytes": stat.st_size,
    }


@mcp.tool()
def list_supported_document_files(subdir: str = ".") -> list[str]:
    """List supported readable document files under a workspace subdirectory."""
    log_event(f"list_supported_document_files subdir={subdir}")
    base = _safe_path(subdir)

    if not base.exists():
        return []

    supported = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log", ".csv", ".docx", ".pdf", ".pptx", ".xlsx"}

    return sorted(
        str(file_path.relative_to(ROOT))
        for file_path in base.rglob("*")
        if file_path.is_file() and file_path.suffix.lower() in supported
    )


if __name__ == "__main__":
    mcp.run()
