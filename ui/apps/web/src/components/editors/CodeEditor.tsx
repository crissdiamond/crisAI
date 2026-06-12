import React from "react";
// Controlled value/onChange/extensions pattern copied from the
// @uiw/react-codemirror README: https://github.com/uiwjs/react-codemirror
import CodeMirror from "@uiw/react-codemirror";
import type { Extension } from "@uiw/react-codemirror";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { yaml } from "@codemirror/lang-yaml";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { linter, lintGutter } from "@codemirror/lint";
import type { Diagnostic } from "@codemirror/lint";
import { yamlDiagnostics } from "./yamlLint.js";
import type { EditorProps } from "./types.js";

// Advisory YAML linter: parses the document with the `yaml` package and maps
// any syntax errors to CodeMirror diagnostics. Positions are resolved against
// the live document so `linePos` line/col pairs become absolute offsets.
const yamlLinter = linter((view) => {
  const doc = view.state.doc;
  const resolve = (line: number, col: number) => {
    const docLine = line >= 1 && line <= doc.lines ? doc.line(line) : doc.line(1);
    return Math.min(docLine.from + Math.max(0, col - 1), doc.length);
  };
  return yamlDiagnostics(doc.toString(), resolve) as Diagnostic[];
});

export type CodeEditorLanguage = "json" | "yaml" | "markdown" | "python" | "plain";

function buildExtensions(language: CodeEditorLanguage): Extension[] {
  switch (language) {
    case "json":
      // JSON parse diagnostics surfaced inline via the lint gutter.
      return [json(), linter(jsonParseLinter()), lintGutter()];
    case "yaml":
      // YAML parse diagnostics surfaced inline (advisory; never blocks save).
      return [yaml(), yamlLinter, lintGutter()];
    case "markdown":
      return [markdown()];
    case "python":
      return [python()];
    case "plain":
    default:
      return [];
  }
}

interface CodeEditorProps extends EditorProps {
  language: CodeEditorLanguage;
}

export function CodeEditor({ value, onChange, readOnly, path, language }: CodeEditorProps) {
  const extensions = buildExtensions(language);
  return (
    <CodeMirror
      value={value}
      onChange={(next) => onChange(next)}
      extensions={extensions}
      readOnly={readOnly}
      editable={!readOnly}
      height="100%"
      aria-label={path ? `Edit ${path}` : "Workspace file editor"}
    />
  );
}
