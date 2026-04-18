from __future__ import annotations

from datetime import datetime
from pathlib import Path


def append_trace(log_file: Path, stage: str, content: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 100}\n")
        f.write(f"{datetime.now().isoformat()} | {stage}\n")
        f.write(f"{'-' * 100}\n")
        f.write(content.strip())
        f.write("\n")
