"""HTTP-level integration tests for the web app pipeline.

Tests verify the full request/response cycle through FastAPI's TestClient,
covering the /api/run (sync) and /api/run/start + /api/run/status (async)
endpoints. Agent execution is stubbed so no real LLM calls are made.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest

from crisai.apps.web import RunRequest, app


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
    monkeypatch.setattr("crisai.apps.web.load_history", lambda _: [])
    monkeypatch.setattr("crisai.apps.web.save_history", lambda *a: None)
    monkeypatch.setattr("crisai.apps.web.update_session_memory", lambda *a: None)
    monkeypatch.setattr("crisai.apps.web._trace_file_path", lambda: tmp_path / "trace.jsonl")
    monkeypatch.setattr("crisai.apps.web._list_session_names", lambda: ["default"])
    monkeypatch.setattr("crisai.apps.web._session_name_newest_by_mtime", lambda: None)
    monkeypatch.setattr("crisai.apps.web.configure_logging", lambda *a, **kw: None)
    monkeypatch.setattr("crisai.apps.web.load_settings", lambda: _make_settings(tmp_path))
    return _ASGITestClient()


class _ASGITestClient:
    """Small sync wrapper around httpx ASGITransport.

    Starlette's TestClient can hang with the current FastAPI/Starlette/AnyIO
    combination in this environment. This keeps the tests HTTP-level without
    relying on TestClient's blocking portal.
    """

    def get(self, url: str) -> httpx.Response:
        return asyncio.run(self._request("GET", url))

    def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        return asyncio.run(self._request("POST", url, json=json))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            return await async_client.request(method, url, **kwargs)


def _make_settings(tmp_path: Path):
    return type("S", (), {
        "workspace_dir": tmp_path / "workspace",
        "log_dir": str(tmp_path / "logs"),
        "registry_dir": str(tmp_path),
    })()


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
        "history": [],
        "current_session": "default",
        "task": None,
    }

    resp = client.get("/api/run/status/job-abc")

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert resp.json()["final_output"] == ""


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
