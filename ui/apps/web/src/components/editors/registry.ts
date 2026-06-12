import React, { lazy } from "react";
import { RawTextarea } from "./RawTextarea.js";
import type { EditorComponent, EditorProps } from "./types.js";
import type { CodeEditorLanguage } from "./CodeEditor.js";

// Heavy editors are code-split via React.lazy so their bundles (CodeMirror and
// Toast UI, ~1.2MB combined) load on demand instead of inflating the initial
// chunk. The RawTextarea fallback stays eager — it is tiny and is the safe
// default for unknown types, so it must never depend on a deferred import.
//
// The CodeEditor module is loaded exactly once; every language wrapper renders
// the same lazy component with a fixed `language` prop, so json/yaml/py/plain
// all share a single async chunk rather than pulling CodeMirror four times.
const LazyCodeEditor = lazy(() =>
  import("./CodeEditor.js").then((m) => ({ default: m.CodeEditor }))
);
const MarkdownEditor = lazy(() =>
  import("./MarkdownEditor.js").then((m) => ({ default: m.MarkdownEditor }))
);

// Bind a fixed CodeMirror language so the registry can return a plain
// EditorComponent for every suffix. The component is the shared lazy CodeEditor.
function codeEditorFor(language: CodeEditorLanguage): EditorComponent {
  const Wrapper: EditorComponent = (props: EditorProps) =>
    React.createElement(LazyCodeEditor, { ...props, language });
  return Wrapper;
}

const JsonEditor = codeEditorFor("json");
const YamlEditor = codeEditorFor("yaml");
const PythonEditor = codeEditorFor("python");
const PlainEditor = codeEditorFor("plain");

function suffixOf(path: string): string {
  const lower = path.toLowerCase();
  const dot = lower.lastIndexOf(".");
  return dot === -1 ? "" : lower.slice(dot);
}

export function getEditorForPath(path: string): EditorComponent {
  switch (suffixOf(path)) {
    case ".json":
      return JsonEditor;
    case ".yaml":
    case ".yml":
      return YamlEditor;
    case ".py":
      return PythonEditor;
    case ".md":
      return MarkdownEditor;
    case ".txt":
    case ".log":
    case ".csv":
      return PlainEditor;
    default:
      return RawTextarea;
  }
}
