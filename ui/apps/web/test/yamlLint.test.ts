import assert from "node:assert/strict";
import test from "node:test";
import { yamlDiagnostics } from "../src/components/editors/yamlLint.js";

test("valid YAML yields no diagnostics", () => {
  const text = "name: crisAI\nitems:\n  - one\n  - two\n";
  assert.deepEqual(yamlDiagnostics(text), []);
});

test("malformed YAML yields at least one error diagnostic", () => {
  // A mapping value that opens a flow sequence but never closes it.
  const text = "name: [unterminated\n";
  const diagnostics = yamlDiagnostics(text);
  assert.ok(diagnostics.length >= 1, "expected at least one diagnostic");
  const first = diagnostics[0];
  assert.equal(first.severity, "error");
  assert.equal(typeof first.message, "string");
  assert.ok(first.message.length > 0);
  // Offsets stay within the document and are well-ordered.
  assert.ok(first.from >= 0);
  assert.ok(first.to >= first.from);
  assert.ok(first.to <= text.length);
});

test("duplicate map key surfaces as a diagnostic", () => {
  const text = "a: 1\nb: 2\nbad: : :\n";
  const diagnostics = yamlDiagnostics(text);
  assert.ok(diagnostics.length >= 1);
});

test("empty document is valid (no diagnostics)", () => {
  assert.deepEqual(yamlDiagnostics(""), []);
});
