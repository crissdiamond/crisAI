from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_ROOT = ROOT / "src" / "crisai" / "cli" / "text"


def test_help_file_exists_and_is_not_empty() -> None:
    help_file = TEXT_ROOT / "help.md"
    assert help_file.exists(), f"Missing help file: {help_file}"
    content = help_file.read_text(encoding="utf-8").strip()
    assert content, "help.md is empty"


def test_pipeline_prompt_files_exist_and_are_not_empty() -> None:
    files = [
        TEXT_ROOT / "pipeline" / "discovery.md",
        TEXT_ROOT / "pipeline" / "design.md",
        TEXT_ROOT / "pipeline" / "review.md",
        TEXT_ROOT / "pipeline" / "final.md",
    ]

    for file_path in files:
        assert file_path.exists(), f"Missing pipeline text file: {file_path}"
        content = file_path.read_text(encoding="utf-8").strip()
        assert content, f"{file_path.name} is empty"


def test_peer_prompt_files_exist_and_are_not_empty() -> None:
    files = [
        TEXT_ROOT / "peer" / "discovery.md",
        TEXT_ROOT / "peer" / "author.md",
        TEXT_ROOT / "peer" / "challenger.md",
        TEXT_ROOT / "peer" / "refiner.md",
        TEXT_ROOT / "peer" / "judge.md",
        TEXT_ROOT / "peer" / "final.md",
    ]

    for file_path in files:
        assert file_path.exists(), f"Missing peer text file: {file_path}"
        content = file_path.read_text(encoding="utf-8").strip()
        assert content, f"{file_path.name} is empty"
