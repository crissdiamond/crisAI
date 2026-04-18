from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Provide lightweight fallbacks so tests can run even when optional runtime
# dependencies are not fully installed in the test environment.
try:
    import agents  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - fallback only
    agents_mod = types.ModuleType("agents")

    class Agent:  # noqa: D401
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class Runner:
        @staticmethod
        async def run(agent, message):  # pragma: no cover - should be monkeypatched in tests
            raise NotImplementedError("Stub Runner.run should be monkeypatched in tests")

    agents_mod.Agent = Agent
    agents_mod.Runner = Runner
    sys.modules["agents"] = agents_mod

try:
    import agents.mcp  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - fallback only
    mcp_mod = types.ModuleType("agents.mcp")

    class MCPServerStdio:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def create_static_tool_filter(*, allowed_tool_names=None):
        return allowed_tool_names

    mcp_mod.MCPServerStdio = MCPServerStdio
    mcp_mod.create_static_tool_filter = create_static_tool_filter
    sys.modules["agents.mcp"] = mcp_mod
