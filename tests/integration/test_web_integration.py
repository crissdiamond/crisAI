"""HTTP-level integration tests for the web app pipeline.

Tests verify the full request/response cycle through FastAPI's TestClient,
covering the /api/run (sync) and /api/run/start + /api/run/status (async)
endpoints. Agent execution is stubbed so no real LLM calls are made.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from crisai.apps.web import RunRequest, app
from crisai.orchestration.request_contract import infer_request_contract

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"


@dataclass
class _FakeDecision:
    intent: str = "design"
    mode: str = "single"
    agent: str = "design"
    needs_retrieval: bool = False
    needs_review: bool = False
    confidence: float = 1.0
    reason: str = "stub"


@pytest.fixture(autouse=True)
def _clear_jobs():
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS.clear()
    yield
    web_mod._RUN_JOBS.clear()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _ASGITestClient:
    """Return an ASGI test client with I/O side-effects suppressed."""
    monkeypatch.delenv("CRISAI_API_KEY", raising=False)  # ensure auth is disabled by default
    monkeypatch.setattr("crisai.apps.web.load_history", lambda _: [])
    monkeypatch.setattr("crisai.apps.web.save_history", lambda *a: None)
    monkeypatch.setattr("crisai.apps.web.update_session_memory", lambda *a: None)
    monkeypatch.setattr("crisai.apps.web._trace_file_path", lambda: tmp_path / "trace.jsonl")
    monkeypatch.setattr("crisai.apps.web._list_session_names", lambda: ["default"])
    monkeypatch.setattr("crisai.apps.web._session_name_newest_by_mtime", lambda: None)
    monkeypatch.setattr("crisai.apps.web.configure_logging", lambda *a, **kw: None)
    monkeypatch.setattr("crisai.apps.web.load_settings", lambda: _make_settings(tmp_path))
    monkeypatch.setattr(
        "crisai.apps.web._resolve_request_contract",
        lambda payload, decision: infer_request_contract(
            payload.message,
            current_mode=getattr(decision, "mode", "auto"),
            registry_dir=REGISTRY_DIR,
        ),
    )
    return _ASGITestClient()


class _ASGITestClient:
    """Small sync wrapper around httpx ASGITransport.

    Starlette's TestClient can hang with the current FastAPI/Starlette/AnyIO
    combination in this environment. This keeps the tests HTTP-level without
    relying on TestClient's blocking portal.
    """

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        return asyncio.run(self._request("GET", url, headers=headers))

    def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str] | None = None) -> httpx.Response:
        return asyncio.run(self._request("POST", url, json=json, headers=headers))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            return await async_client.request(method, url, **kwargs)


def _make_settings(tmp_path: Path):
    return type("S", (), {
        "workspace_dir": tmp_path / "workspace",
        "log_dir": str(tmp_path / "logs"),
        "registry_dir": str(tmp_path),
        "retrieval_checkpoint_enabled": True,
        "retrieval_checkpoint_max_redirects": 2,
    })()


class _DummyFuture:
    def __init__(self) -> None:
        self.value = None

    def done(self) -> bool:
        return self.value is not None

    def set_result(self, value: Any) -> None:
        self.value = value


# ---------------------------------------------------------------------------
# /api/run  (synchronous endpoint)
# ---------------------------------------------------------------------------


def test_sync_run_endpoint_returns_decision_and_output(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/run executes the workflow and returns decision + final_output."""
    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda _: _FakeDecision())

    async def _fake_run(**kwargs) -> str:
        return "stub output"

    monkeypatch.setattr("crisai.apps.web._run_with_routing", _fake_run)

    resp = client.post("/api/run", json={"message": "design a simple API"})

    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert body["final_output"] == "stub output"
    assert body["decision"]["intent"] == "design"
    assert body["current_session"] == "default"
    assert isinstance(body["history"], list)


def test_sync_run_endpoint_maps_runtime_error_to_500(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/run returns 500 when pipeline execution fails."""
    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda _: _FakeDecision())

    async def _boom(**kwargs) -> str:
        raise RuntimeError("pipeline exploded")

    monkeypatch.setattr("crisai.apps.web._run_with_routing", _boom)

    resp = client.post("/api/run", json={"message": "trigger failure"})

    assert resp.status_code == 500
    assert "pipeline exploded" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /api/run/start  (background job creation)
# ---------------------------------------------------------------------------


def test_run_start_returns_job_id_and_decision(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/run/start responds immediately with a job id."""
    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda _: _FakeDecision())

    async def _noop_run_job(job_id: str, payload: Any, decision: Any) -> None:
        from crisai.apps import web as web_mod
        web_mod._RUN_JOBS[job_id]["status"] = "completed"
        web_mod._RUN_JOBS[job_id]["final_output"] = "done"

    monkeypatch.setattr("crisai.apps.web._run_job", _noop_run_job)

    resp = client.post("/api/run/start", json={"message": "propose a design"})

    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert len(body["job_id"]) == 32  # uuid4().hex
    assert body["decision"]["intent"] == "design"
    assert isinstance(body["expected_tabs"], list)


def test_api_v1_run_start_returns_shared_ui_state(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/v1/runs returns the shared UI contract state."""
    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda _: _FakeDecision())
    monkeypatch.setattr(
        "crisai.apps.web._agent_model_metadata",
        lambda agent_id: {
            "agent_id": agent_id,
            "model_ref": "openai_fast",
            "provider": "openai",
            "model_name": "gpt-5.4-mini",
        },
    )

    async def _noop_run_job(job_id: str, payload: Any, decision: Any) -> None:
        from crisai.apps import web as web_mod
        web_mod._RUN_JOBS[job_id]["status"] = "completed"
        web_mod._RUN_JOBS[job_id]["final_output"] = "done"

    monkeypatch.setattr("crisai.apps.web._run_job", _noop_run_job)

    resp = client.post("/api/v1/runs", json={"message": "propose a design"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == "ui_run_state_v1"
    assert body["decision"]["intent"] == "design"
    assert body["events"][0]["schema_version"] == "ui_event_v1"
    assert body["events"][0]["event_type"] == "run_created"
    assert body["events"][0]["metadata"]["model_ref"] == "openai_fast"
    assert body["events"][1]["event_type"] == "routing_decision"
    assert body["events"][1]["metadata"]["model_name"] == "gpt-5.4-mini"
    assert body["events"][2]["event_type"] == "task_contract"
    assert "Intent:" in body["events"][2]["content"]
    assert "```json" not in body["events"][2]["content"]


def test_run_start_rejects_concurrent_run(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/run/start returns 409 when another job is already running."""
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS["in-flight"] = {"status": "running"}

    resp = client.post("/api/run/start", json={"message": "another request"})

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# /api/run/status/{job_id}
# ---------------------------------------------------------------------------


def test_run_status_returns_running_while_job_in_progress(
    client: _ASGITestClient,
) -> None:
    """GET /api/run/status returns 'running' before the background task finishes."""
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS["job-abc"] = {
        "status": "running",
        "payload": RunRequest(message="x"),
        "decision": _FakeDecision(),
        "before_size": 0,
        "run_id": None,
        "stage_outputs": [],
        "final_output": "",
        "error": "",
        "checkpoint": None,
        "history": [],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/run/status/job-abc")

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert resp.json()["final_output"] == ""


def test_run_status_returns_checkpoint_payload(
    client: _ASGITestClient,
) -> None:
    """GET /api/run/status returns checkpoint data when a job is paused."""
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS["job-check"] = {
        "status": "checkpoint_waiting",
        "payload": RunRequest(message="x"),
        "decision": _FakeDecision(),
        "before_size": 0,
        "run_id": None,
        "stage_outputs": [],
        "final_output": "",
        "error": "",
        "checkpoint": {"evidence_brief": "read Deck.pptx"},
        "checkpoint_future": _DummyFuture(),
        "history": [],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/run/status/job-check")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "checkpoint_waiting"
    assert body["checkpoint"]["evidence_brief"] == "read Deck.pptx"


def test_run_checkpoint_submits_continue_decision(
    client: _ASGITestClient,
) -> None:
    """POST /api/run/checkpoint resumes a paused job."""
    from crisai.apps import web as web_mod

    future = _DummyFuture()
    web_mod._RUN_JOBS["job-check"] = {
        "status": "checkpoint_waiting",
        "checkpoint_future": future,
        "checkpoint": {"evidence_brief": "read Deck.pptx"},
    }

    resp = client.post("/api/run/checkpoint/job-check", json={"action": "continue"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "accepted", "action": "continue"}
    assert future.value.action == "continue"


def test_run_status_returns_completed_after_job_finishes(
    client: _ASGITestClient,
) -> None:
    """GET /api/run/status returns 'completed' once the job is done."""
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS["job-xyz"] = {
        "status": "completed",
        "payload": RunRequest(message="x"),
        "decision": _FakeDecision(),
        "before_size": 0,
        "run_id": None,
        "stage_outputs": [{"key": "design", "agent_id": "design", "content": "output"}],
        "final_output": "finished result",
        "error": "",
        "checkpoint": None,
        "history": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "finished result"}],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/run/status/job-xyz")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["final_output"] == "finished result"
    assert len(body["stage_outputs"]) == 1


def test_api_v1_run_state_maps_trace_rows_to_ui_events(
    client: _ASGITestClient,
    tmp_path: Path,
) -> None:
    """GET /api/v1/runs/{id} exposes trace-backed stage rows as UI events."""
    from crisai.apps import web as web_mod

    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        '{"run_id":"trace-run","event_type":"stage_output","stage":"DESIGN OUTPUT",'
        '"agent_id":"design","content":"Drafted recommendation.","timestamp":"t1"}\n',
        encoding="utf-8",
    )
    web_mod._RUN_JOBS["job-ui"] = {
        "status": "running",
        "payload": RunRequest(message="x"),
        "decision": _FakeDecision(mode="pipeline", agent="design"),
        "decision_data": {"mode": "pipeline", "agent": "design"},
        "before_size": 0,
        "run_id": "trace-run",
        "stage_outputs": [],
        "final_output": "",
        "error": "",
        "checkpoint": None,
        "events": [],
        "event_trace_keys": set(),
        "history": [],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/v1/runs/job-ui")

    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == "ui_run_state_v1"
    assert body["events"][0]["event_type"] == "stage_output"
    assert body["events"][0]["agent_id"] == "design"
    assert "drafted recommendation" in body["events"][0]["content"]


def test_run_status_returns_failed_on_pipeline_error(
    client: _ASGITestClient,
) -> None:
    """GET /api/run/status returns 'failed' with an error message."""
    from crisai.apps import web as web_mod

    web_mod._RUN_JOBS["job-err"] = {
        "status": "failed",
        "payload": RunRequest(message="x"),
        "decision": _FakeDecision(),
        "before_size": 0,
        "run_id": None,
        "stage_outputs": [],
        "final_output": "",
        "error": "pipeline crashed",
        "checkpoint": None,
        "history": [],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/run/status/job-err")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "pipeline crashed" in body["error"]


def test_run_status_404_for_unknown_job(client: _ASGITestClient) -> None:
    """GET /api/run/status returns 404 for an unknown job id."""
    resp = client.get("/api/run/status/no-such-job")
    assert resp.status_code == 404


def test_app_config_returns_retrieval_checkpoint_defaults(client: _ASGITestClient) -> None:
    """GET /api/config exposes web defaults for checkpoint controls."""
    resp = client.get("/api/config")

    assert resp.status_code == 200
    assert resp.json()["retrieval_checkpoint_enabled"] is True
    assert resp.json()["retrieval_checkpoint_max_redirects"] == 2


def test_api_v1_ui_theme_returns_shared_registry(client: _ASGITestClient, tmp_path: Path) -> None:
    """GET /api/v1/ui/theme exposes registry-backed shared UI tokens."""
    (tmp_path / "ui.yaml").write_text(
        """
schema_version: ui_theme_v1
default_theme: ucl_dark
themes:
  ucl_dark:
    palette:
      primary_dark: "#361a54"
surfaces:
  web:
    theme: ucl_dark
""",
        encoding="utf-8",
    )

    resp = client.get("/api/v1/ui/theme")

    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == "ui_theme_v1"
    assert body["themes"]["ucl_dark"]["palette"]["primary_dark"] == "#361a54"


def test_api_v1_sessions_list_returns_shared_session_state(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/v1/sessions exposes session state for shared UI clients."""
    monkeypatch.setattr("crisai.apps.web.load_history", lambda _: [("user", "hello")])

    resp = client.get("/api/v1/sessions")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sessions"] == ["default"]
    assert body["current_session"] == "default"
    assert body["history"] == [{"role": "user", "content": "hello"}]
    assert "memory" in body


def test_api_v1_sessions_create_sanitizes_name(client: _ASGITestClient) -> None:
    """POST /api/v1/sessions creates or selects a sanitized session."""
    resp = client.post("/api/v1/sessions", json={"session": "new task"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_session"] == "new_task"
    assert isinstance(body["history"], list)


def test_api_v1_workspace_read_and_save(
    client: _ASGITestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared UI workspace endpoints expose bounded read/save behaviour."""
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    path = workspace / "tasks/demo/artefacts/design.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Draft\n", encoding="utf-8")
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())

    roots_resp = client.get("/api/v1/workspace/roots")
    tree_resp = client.get("/api/v1/workspace/tree/tasks")
    file_resp = client.get("/api/v1/workspace/file?path=tasks/demo/artefacts/design.md")
    save_resp = client.post(
        "/api/v1/workspace/file",
        json={"path": "tasks/demo/artefacts/design.md", "content": "# Updated\n"},
    )

    assert roots_resp.status_code == 200
    assert roots_resp.json()["roots"]["tasks"] == "tasks"
    assert tree_resp.status_code == 200
    assert tree_resp.json()["files"][0]["path"] == "tasks/demo/artefacts/design.md"
    assert file_resp.status_code == 200
    assert file_resp.json()["content"] == "# Draft\n"
    assert save_resp.status_code == 200
    assert save_resp.json()["saved"] is True
    assert path.read_text(encoding="utf-8") == "# Updated\n"


def test_api_v1_workspace_upload_task_inputs_dedupes_names(
    client: _ASGITestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared UI upload stores files in the active task input folder."""
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())
    payload = {
        "target": "task_inputs",
        "session": "demo task",
        "filename": "Deck.pptx",
        "content_base64": base64.b64encode(b"deck").decode("ascii"),
    }

    first_resp = client.post("/api/v1/workspace/upload", json=payload)
    second_resp = client.post("/api/v1/workspace/upload", json=payload)

    assert first_resp.status_code == 200
    assert first_resp.json()["path"] == "tasks/demo_task/inputs/Deck.pptx"
    assert second_resp.status_code == 200
    assert second_resp.json()["path"] == "tasks/demo_task/inputs/Deck-1.pptx"
    assert (workspace / "tasks/demo_task/inputs/Deck.pptx").read_bytes() == b"deck"
    assert (workspace / "tasks/demo_task/inputs/Deck-1.pptx").read_bytes() == b"deck"


def test_api_v1_workspace_upload_rejects_disallowed_suffix(
    client: _ASGITestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared UI upload rejects executable or unknown source file types."""
    from crisai.apps import web as web_mod

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(web_mod, "load_settings", lambda: type("S", (), {"workspace_dir": workspace, "registry_dir": tmp_path})())

    resp = client.post(
        "/api/v1/workspace/upload",
        json={
            "target": "task_inputs",
            "session": "demo",
            "filename": "run.exe",
            "content_base64": base64.b64encode(b"not really").decode("ascii"),
        },
    )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Eviction does not remove running jobs
# ---------------------------------------------------------------------------


def test_eviction_preserves_running_job_after_start(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting a 21st job evicts old completed jobs but keeps the new running one."""
    from crisai.apps import web as web_mod

    for i in range(20):
        web_mod._RUN_JOBS[f"old-{i}"] = {"status": "completed"}

    monkeypatch.setattr("crisai.apps.web._resolve_decision", lambda _: _FakeDecision())

    async def _noop_run_job(job_id: str, payload: Any, decision: Any) -> None:
        pass  # job stays "running"

    monkeypatch.setattr("crisai.apps.web._run_job", _noop_run_job)

    resp = client.post("/api/run/start", json={"message": "new request"})
    assert resp.status_code == 200

    new_job_id = resp.json()["job_id"]
    assert new_job_id in web_mod._RUN_JOBS
    assert web_mod._RUN_JOBS[new_job_id]["status"] == "running"


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


def test_api_endpoint_accessible_without_key_when_auth_disabled(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRISAI_API_KEY unset → middleware no-op, endpoint reachable."""
    monkeypatch.delenv("CRISAI_API_KEY", raising=False)
    resp = client.get("/api/config")
    assert resp.status_code == 200


def test_api_endpoint_returns_401_without_header_when_key_set(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRISAI_API_KEY set, no Authorization header → 401 with WWW-Authenticate."""
    monkeypatch.setenv("CRISAI_API_KEY", "test-secret")
    resp = client.get("/api/config")
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_api_endpoint_returns_401_with_wrong_token(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrong Bearer token → 401."""
    monkeypatch.setenv("CRISAI_API_KEY", "test-secret")
    resp = client.get("/api/config", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_api_endpoint_accessible_with_correct_token(
    client: _ASGITestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correct Bearer token → request proceeds normally."""
    monkeypatch.setenv("CRISAI_API_KEY", "test-secret")
    resp = client.get("/api/config", headers={"Authorization": "Bearer test-secret"})
    assert resp.status_code == 200


def test_auth_middleware_uses_constant_time_compare() -> None:
    """Bearer comparison should use constant-time comparison."""
    import inspect

    from crisai.apps import web as web_mod

    source = inspect.getsource(web_mod._auth_middleware)
    assert "secrets.compare_digest" in source


