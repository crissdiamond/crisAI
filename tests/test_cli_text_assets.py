from pathlib import Path

from crisai.cli import main


def test_help_markdown_exists_and_loads() -> None:
    text = main._load_cli_text("help.md")
    assert "/list servers" in text
    assert "/list agents" in text


def test_pipeline_discovery_template_renders_message() -> None:
    rendered = main._render_cli_text("pipeline/discovery.md", message="Find integration docs")
    assert "Find integration docs" in rendered
    assert "Never guess file paths" in rendered


def test_peer_final_template_renders_all_context() -> None:
    rendered = main._render_cli_text(
        "peer/final.md",
        message="Test",
        discovery_text="Discovery",
        author_text="Author",
        challenger_text="Challenge",
        refiner_text="Refined",
        judge_text="Accept",
    )
    assert "Discovery" in rendered
    assert "Refined" in rendered
    assert "Accept" in rendered


def test_cli_text_directory_exists() -> None:
    text_dir = main._cli_text_dir()
    assert text_dir.exists()
    assert (text_dir / "pipeline" / "design.md").exists()
