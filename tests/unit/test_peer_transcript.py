from __future__ import annotations

from crisai.cli.peer_transcript import PeerMessage, PeerRunResult, append_peer_message, make_peer_message, peer_speakers


def test_make_peer_message_trims_content_and_defaults_role_and_step() -> None:
    msg = make_peer_message("design_author", "  Draft proposal  ")
    assert isinstance(msg, PeerMessage)
    assert msg.speaker == "design_author"
    assert msg.role == "design_author"
    assert msg.step == "design_author"
    assert msg.content == "Draft proposal"


def test_append_peer_message_skips_empty_content() -> None:
    transcript: list[PeerMessage] = []
    append_peer_message(transcript, "judge", "   ")
    assert transcript == []


def test_peer_speakers_returns_transcript_order() -> None:
    transcript: list[PeerMessage] = []
    append_peer_message(transcript, "retrieval_planner", "Found three docs")
    append_peer_message(transcript, "design_author", "Drafted proposal")
    append_peer_message(transcript, "judge", "Looks good")
    assert peer_speakers(transcript) == ["retrieval_planner", "design_author", "judge"]


def test_peer_run_result_holds_final_text_and_transcript() -> None:
    transcript = [make_peer_message("orchestrator", "Final answer")]
    result = PeerRunResult(final_text="Final answer", transcript=transcript)
    assert result.final_text == "Final answer"
    assert result.transcript == transcript
