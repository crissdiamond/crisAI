import assert from "node:assert/strict";
import test from "node:test";
import { getEditorForPath } from "../src/components/editors/registry.js";
import { MarkdownEditor } from "../src/components/editors/MarkdownEditor.js";
import { RawTextarea } from "../src/components/editors/RawTextarea.js";

test("getEditorForPath routes .md to the Toast UI MarkdownEditor", () => {
  assert.equal(getEditorForPath("notes/x.md"), MarkdownEditor);
  assert.equal(getEditorForPath("X.MD"), MarkdownEditor);
});

test("structured suffixes stay on CodeMirror wrappers, unknown falls back to raw", () => {
  // .json / .yaml resolve to dedicated (non-Markdown, non-raw) wrappers.
  const jsonEditor = getEditorForPath("config.json");
  const yamlEditor = getEditorForPath("config.yaml");
  assert.notEqual(jsonEditor, MarkdownEditor);
  assert.notEqual(jsonEditor, RawTextarea);
  assert.notEqual(yamlEditor, MarkdownEditor);
  assert.notEqual(yamlEditor, RawTextarea);
  assert.equal(getEditorForPath("config.yml"), yamlEditor);

  // Unknown suffix stays on the raw textarea fallback.
  assert.equal(getEditorForPath("archive.bin"), RawTextarea);
});
