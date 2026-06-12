import React from "react";
import { CodeEditor } from "./CodeEditor.js";
import { MarkdownEditor } from "./MarkdownEditor.js";
import { RawTextarea } from "./RawTextarea.js";
import type { EditorComponent, EditorProps } from "./types.js";

// Each registry entry binds a fixed CodeMirror language. Small wrapper
// components fix the `language` prop so the registry can return a plain
// EditorComponent for every suffix.
const JsonEditor: EditorComponent = (props: EditorProps) =>
  React.createElement(CodeEditor, { ...props, language: "json" });
const YamlEditor: EditorComponent = (props: EditorProps) =>
  React.createElement(CodeEditor, { ...props, language: "yaml" });
const PythonEditor: EditorComponent = (props: EditorProps) =>
  React.createElement(CodeEditor, { ...props, language: "python" });
const PlainEditor: EditorComponent = (props: EditorProps) =>
  React.createElement(CodeEditor, { ...props, language: "plain" });

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
