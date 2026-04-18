import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PEER_FILE = ROOT / "src" / "crisai" / "cli" / "peer_transcript.py"
DISPLAY_FILE = ROOT / "src" / "crisai" / "cli" / "display.py"

def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def test_peer_transcript_module_exists() -> None:
    assert PEER_FILE.exists(), f"Missing file: {PEER_FILE}"


def test_build_peer_message_and_speakers() -> None:
    mod = _load_module(PEER_FILE, "peer_transcript")
    transcript = []
    mod.append_peer_message(transcript, "design_author", "Draft proposal")
    mod.append_peer_message(transcript, "judge", "Decision")
    assert len(transcript) == 2
    assert mod.peer_speakers(transcript) == ["design_author", "judge"]


def test_display_module_exists() -> None:
    assert DISPLAY_FILE.exists(), f"Missing file: {DISPLAY_FILE}"
