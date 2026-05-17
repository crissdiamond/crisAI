# hcom Review Template

Use this shape for Claude or peer review responses.

```text
Reviewer role: <role>
Review target: <agent/task/bundle>
Verdict: <approve | approve-with-fixes | revise | blocked>

Findings:
- <severity>: <issue, file/path if applicable, reason>

Suggested fixes:
- <specific change>

Checks recommended:
- <command or scenario>

UI review, when applicable:
- Shared styling: <uses shared contract | local style justified | issue>
- Layout bounds: <stable | overflow risk | issue>
- Variable output: <scrolls/clips/truncates | issue>
- Checkpoint UX: <clear user decision | exposes internals | issue>
- Cross-surface consistency: <Gem/web aligned | divergence justified | issue>
- Viewports checked: <narrow/mobile, normal/desktop, or not checked>

Memory update:
- <what should be recorded in Claude memory MCP>
```
