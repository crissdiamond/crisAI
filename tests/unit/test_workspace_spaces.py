from __future__ import annotations

from crisai.workspace.spaces import WorkspaceSpaces, load_workspace_spaces


def test_default_corpora_include_current_roots_without_aliases():
    spaces = WorkspaceSpaces()

    corpora = spaces.effective_knowledge_corpora()

    assert corpora[0].id == "approved_knowledge"
    assert corpora[0].root == "knowledge"
    assert corpora[0].aliases == ()
    assert corpora[1].root == "knowledge_staging"
    assert corpora[1].aliases == ()
    assert spaces.canonicalize_workspace_path("workspace/knowledge/patterns/a.md") == "knowledge/patterns/a.md"
    assert spaces.canonicalize_workspace_path("knowledge_staging/patterns/a.md") == "knowledge_staging/patterns/a.md"


def test_load_workspace_spaces_supports_named_custom_corpora(tmp_path):
    (tmp_path / "workspace_spaces.yaml").write_text(
        """
version: 1
workspace_spaces:
  knowledge_root: enterprise_knowledge
  knowledge_staging_root: enterprise_knowledge_drafts
  tasks_root: work_items
  knowledge_corpora:
    - id: approved_enterprise_knowledge
      label: Approved enterprise knowledge
      root: enterprise_knowledge
      role: approved
      access: read
      aliases:
        - knowledge
      staging_root: enterprise_knowledge_drafts
      retrieval_priority: 5
      validation_profile: strict
    - id: draft_enterprise_knowledge
      label: Draft enterprise knowledge
      root: enterprise_knowledge_drafts
      role: staging
      access: read_write
      aliases:
        - knowledge_staging
      promotion_target: enterprise_knowledge
      retrieval_priority: 20
""",
        encoding="utf-8",
    )

    spaces = load_workspace_spaces(tmp_path)

    assert spaces.knowledge_root == "enterprise_knowledge"
    assert spaces.tasks_root == "work_items"
    assert spaces.writable_roots == ("outputs", "scratch", "enterprise_knowledge_drafts", "work_items")
    assert [corpus.id for corpus in spaces.effective_knowledge_corpora()] == [
        "approved_enterprise_knowledge",
        "draft_enterprise_knowledge",
    ]
    assert spaces.canonical_root_for("knowledge") == "enterprise_knowledge"
    assert spaces.canonicalize_workspace_path("workspace/knowledge/reference/a.md") == "enterprise_knowledge/reference/a.md"
    assert (
        spaces.canonicalize_workspace_path("knowledge_staging/patterns/a.md")
        == "enterprise_knowledge_drafts/patterns/a.md"
    )
    assert "knowledge" in spaces.all_read_roots()
    assert "enterprise_knowledge" in spaces.all_read_roots()
