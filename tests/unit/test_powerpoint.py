from __future__ import annotations

import io
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from crisai.powerpoint import (
    extract_powerpoint_from_bytes,
    extract_powerpoint_from_path,
)


def _sample_pptx_bytes() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Integration Strategy"

    textbox = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(5), Inches(1))
    textbox.text_frame.text = "Strategic objectives and current challenges"

    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(2.5), Inches(5), Inches(1))
    table = table_shape.table
    table.cell(0, 0).text = "Theme"
    table.cell(0, 1).text = "Detail"
    table.cell(1, 0).text = "Roadmap"
    table.cell(1, 1).text = "Next steps"

    output = io.BytesIO()
    prs.save(output)
    return output.getvalue()


def test_extract_powerpoint_from_bytes_returns_slide_level_text_and_tables() -> None:
    extraction = extract_powerpoint_from_bytes(_sample_pptx_bytes())

    assert extraction.status == "partial_text"
    assert extraction.slide_count == 1
    assert extraction.coverage == ["slide_text", "tables"]
    assert "image_text_not_extracted" in extraction.limitations

    slide = extraction.slides[0]
    assert slide.title == "Integration Strategy"
    assert "Strategic objectives and current challenges" in slide.text
    assert slide.tables == [[["Theme", "Detail"], ["Roadmap", "Next steps"]]]


def test_extract_powerpoint_from_path_renders_extraction_header(tmp_path: Path) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(_sample_pptx_bytes())

    rendered = extract_powerpoint_from_path(path).to_text()

    assert "[PowerPoint extraction]" in rendered
    assert "coverage: slide_text, tables" in rendered
    assert "[Slide 1]" in rendered
    assert "Title: Integration Strategy" in rendered
    assert "Roadmap | Next steps" in rendered
