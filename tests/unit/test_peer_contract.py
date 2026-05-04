from crisai.orchestration.peer_contract import infer_peer_run_contract, render_peer_run_contract


def test_infer_peer_run_contract_detects_artifact_delivery_intent():
    contract = infer_peer_run_contract(
        "Create files under workspace/context_staging/patterns and keep sources grounded."
    )
    assert contract.expected_output_type == "artifact_package"
    assert contract.must_create_or_update_files is True
    assert contract.must_ground_in_sources is True
    assert "execution_fidelity" in contract.acceptance_dimensions
    assert "evidence_grounding" in contract.acceptance_dimensions


def test_infer_peer_run_contract_detects_code_change_intent():
    contract = infer_peer_run_contract("Implement a fix and add tests for the parser module.")
    assert contract.expected_output_type == "code_change"
    assert contract.must_modify_code is True
    assert "execution_fidelity" in contract.acceptance_dimensions


def test_infer_peer_run_contract_detects_assessment_intent():
    contract = infer_peer_run_contract("Review and compare these two architecture options.")
    assert contract.expected_output_type == "assessment"
    assert contract.must_create_or_update_files is False
    assert contract.must_modify_code is False


def test_render_peer_run_contract_contains_focus_and_dimensions():
    contract = infer_peer_run_contract("Use intranet sources and produce grounded answer.")
    rendered = render_peer_run_contract(contract)
    assert "Expected output type:" in rendered
    assert "Acceptance dimensions:" in rendered
    assert "Author focus:" in rendered
    assert "Judge focus:" in rendered
