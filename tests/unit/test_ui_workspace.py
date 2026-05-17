from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_ui_workspace_defines_react_and_ink_clients() -> None:
    package = _load_json("ui/package.json")

    assert package["private"] is True
    assert "apps/*" in package["workspaces"]
    assert package["scripts"]["dev:web"] == "npm run build:contracts && npm --workspace @crisai/web run dev"
    assert package["scripts"]["dev:gem"] == "npm run build:contracts && npm --workspace @crisai/gem run dev"


def test_ui_apps_depend_on_shared_contract_package() -> None:
    web = _load_json("ui/apps/web/package.json")
    gem = _load_json("ui/apps/gem/package.json")

    assert web["dependencies"]["@crisai/contracts"] == "0.1.0"
    assert gem["dependencies"]["@crisai/contracts"] == "0.1.0"
    assert "react" in web["dependencies"]
    assert "ink" in gem["dependencies"]
    assert "eventsource" in gem["dependencies"]
    assert gem["scripts"]["test"] == "tsx --test test/*.test.ts"


def test_contract_client_targets_v1_runtime_api() -> None:
    client_source = (ROOT / "ui/packages/contracts/src/index.ts").read_text(encoding="utf-8")

    assert "/api/v1/runs" in client_source
    assert "/api/v1/ui/theme" in client_source
    assert "/api/v1/sessions" in client_source
    assert "/api/v1/workspace" in client_source
    assert "listSessions" in client_source
    assert "createSession" in client_source
    assert "getWorkspaceTree" in client_source
    assert "saveWorkspaceFile" in client_source
    assert "uploadWorkspaceFile" in client_source
    assert "/api/v1/workspace/upload" in client_source
    assert "apiToken" in client_source
    assert "setApiToken" in client_source
    assert "authorization" in client_source
    assert "subscribeWithFetch" in client_source
    assert "EventSource" in client_source


def test_ui_clients_share_stage_theme_checkpoint_and_session_helpers() -> None:
    contract_source = (ROOT / "ui/packages/contracts/src/index.ts").read_text(encoding="utf-8")
    web_source = (ROOT / "ui/apps/web/src/main.tsx").read_text(encoding="utf-8")
    gem_source = (ROOT / "ui/apps/gem/src/index.tsx").read_text(encoding="utf-8")
    gem_view_model_source = (ROOT / "ui/apps/gem/src/viewModel.ts").read_text(encoding="utf-8")

    assert "deriveStageSummaries" in contract_source
    assert "stage_delta" in contract_source
    assert "cssVariablesForSurface" in contract_source
    assert "isCheckpointWaiting" in contract_source
    assert "deriveStageSummaries(events" in web_source
    assert "cssVariablesForSurface(theme, \"web\")" in web_source
    assert "runtime.listSessions" in web_source
    assert "HistoryPanel" in web_source
    assert "WorkspaceBrowser" in web_source
    assert "runtime.getWorkspaceTree" in web_source
    assert "runtime.uploadWorkspaceFile" in web_source
    assert "latestLiveStageEvent" in web_source
    assert "streaming-card" in web_source
    assert "workspace-upload" in web_source
    assert "fileToBase64" in web_source
    assert "VITE_CRISAI_API_KEY" in web_source
    assert "localStorage.getItem(apiKeyStorageKey)" in web_source
    assert "runtime.setApiToken" in web_source
    assert "deriveStageSummaries(events" in gem_source
    assert "latestLiveStageEvent" in gem_source
    assert "commandHistory" in gem_source
    assert "buildStatusMetrics" in gem_source
    assert "CRISAI_GEM_WIDTH" in gem_source
    assert "CRISAI_GEM_HEIGHT" in gem_source
    assert "gemTerminalThemeFromPalette(palette)" in gem_source
    assert "buildEventLines(events, error, outputPanelWidth, notice)" in gem_source
    assert "ScrollPane lines={panelLines}" in gem_source
    assert "checkpointDecisionLines().map" in gem_source
    assert "decision needed" in gem_source
    assert "Review retrieved sources" in gem_view_model_source
    assert "resolveViewportDimension" in gem_source
    assert "resolveStageSidebarWidth" in gem_source
    assert "minimumStageSidebarWidth" in gem_view_model_source
    assert "maximumStageSidebarWidth" in gem_view_model_source
    assert "stageSidebarWidth" in gem_source
    assert "StageItem" in gem_source
    assert "stdout?.columns" in gem_source
    assert "stdout?.rows" in gem_source
    assert "minimumGemWidth" in gem_view_model_source
    assert "minimumGemHeight" in gem_view_model_source
    assert "promptPanelHeight" in gem_source
    assert "tokens:${statusMetrics.tokens}" in gem_source
    assert "event.event_type !== \"stage_delta\"" in gem_view_model_source
    assert "/redirect <guidance>" in gem_source
    assert "/session <name>" in gem_source
    assert "formatRuntimeError" in gem_source
    assert "Start it in another terminal with './start api'" in gem_source
    assert "CRISAI_API_KEY" in gem_source
    assert "CRISAI_API_TOKEN" in gem_source
