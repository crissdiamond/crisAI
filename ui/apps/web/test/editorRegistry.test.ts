import assert from "node:assert/strict";
import test from "node:test";
import { getEditorForPath } from "../src/components/editors/registry.js";
import { RawTextarea } from "../src/components/editors/RawTextarea.js";

// The heavy editors (CodeEditor, MarkdownEditor) are now returned as React.lazy
// wrappers, so the registry no longer hands back the underlying component
// references. Routing is therefore asserted structurally: each suffix resolves
// to a distinct, non-raw component, the same suffix family is stable, and only
// unknown types fall through to the eager RawTextarea fallback.

test("getEditorForPath routes .md to a dedicated (non-raw) editor", () => {
  const md = getEditorForPath("notes/x.md");
  const mdUpper = getEditorForPath("X.MD");
  assert.notEqual(md, RawTextarea);
  // Suffix matching is case-insensitive and stable for the same extension.
  assert.equal(md, mdUpper);
});

test("structured suffixes route to distinct editors; unknown falls back to raw", () => {
  const jsonEditor = getEditorForPath("config.json");
  const yamlEditor = getEditorForPath("config.yaml");
  const mdEditor = getEditorForPath("notes.md");

  // JSON / YAML resolve to dedicated (non-raw) wrappers.
  assert.notEqual(jsonEditor, RawTextarea);
  assert.notEqual(yamlEditor, RawTextarea);
  // Each structured type is distinct from the markdown editor and each other.
  assert.notEqual(jsonEditor, mdEditor);
  assert.notEqual(yamlEditor, mdEditor);
  assert.notEqual(jsonEditor, yamlEditor);
  // .yml is the same wrapper family as .yaml.
  assert.equal(getEditorForPath("config.yml"), yamlEditor);

  // Unknown suffix stays on the raw textarea fallback (eager, no lazy import).
  assert.equal(getEditorForPath("archive.bin"), RawTextarea);
});
