// Advisory YAML validation for the CodeEditor's YAML mode.
//
// Parsing is delegated to the `yaml` package (zero-dep, browser-safe, ships its
// own types, and needs no Vite polyfill — chosen over js-yaml in TODO-025
// Phase 0). `parseDocument` collects every syntax error without throwing, which
// lets us surface multiple diagnostics at once. Validation is advisory only:
// the linter never blocks saving, it just annotates the gutter.

import { parseDocument } from "yaml";

/** A subset of CodeMirror's `Diagnostic` — kept local so this helper is
 *  unit-testable in node without importing the editor runtime. The shape is
 *  assignable to `@codemirror/lint`'s `Diagnostic`. */
export interface YamlDiagnostic {
  from: number;
  to: number;
  severity: "error";
  message: string;
}

/**
 * Resolves the absolute document offset of a 1-based `line` and `col`.
 * Defaults are derived from `text` so the helper is self-contained in tests;
 * the CodeMirror linter passes a resolver backed by the live document.
 */
export type PositionResolver = (line: number, col: number) => number;

function defaultResolver(text: string): PositionResolver {
  // Precompute the absolute offset at the start of each line (1-based index).
  const lineStarts: number[] = [0];
  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\n") {
      lineStarts.push(i + 1);
    }
  }
  return (line: number, col: number) => {
    const start = lineStarts[line - 1] ?? 0;
    // `col` is 1-based; clamp the result inside the document.
    const offset = start + Math.max(0, col - 1);
    return Math.min(offset, text.length);
  };
}

/**
 * Parses `text` as a YAML document and maps any syntax errors to diagnostics.
 *
 * Each error's character `pos` range is used when present; otherwise the error's
 * `linePos` is resolved to an offset via `resolve`. When neither is available
 * the diagnostic falls back to spanning the document start (from=0, to=0).
 *
 * Valid YAML yields an empty array. The function never throws — malformed input
 * surfaces as diagnostics, never an exception — so it is safe as a lint source.
 */
export function yamlDiagnostics(
  text: string,
  resolve: PositionResolver = defaultResolver(text)
): YamlDiagnostic[] {
  let errors: ReadonlyArray<{
    message: string;
    pos?: [number, number];
    linePos?: ReadonlyArray<{ line: number; col: number }>;
  }>;
  try {
    errors = parseDocument(text).errors;
  } catch {
    // parseDocument is designed not to throw, but guard defensively so a parser
    // edge case can never break the editor.
    return [];
  }

  return errors.map((error) => {
    let from = 0;
    let to = 0;
    if (Array.isArray(error.pos) && error.pos.length === 2) {
      [from, to] = error.pos;
    } else if (error.linePos && error.linePos.length > 0) {
      const start = error.linePos[0];
      from = resolve(start.line, start.col);
      const end = error.linePos[1] ?? start;
      to = resolve(end.line, end.col);
    }
    if (to < from) {
      to = from;
    }
    return {
      from,
      to,
      severity: "error" as const,
      message: error.message
    };
  });
}
