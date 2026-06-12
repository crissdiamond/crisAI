import React from "react";
import type { EditorProps } from "./types.js";

// Safe fallback for unknown file types: the original WorkspacePanel textarea
// extracted verbatim as an EditorProps component.
export function RawTextarea({ value, onChange, readOnly, path }: EditorProps) {
  return (
    <textarea
      aria-label={path ? `Edit ${path}` : "Workspace file editor"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={readOnly}
      spellCheck={false}
    />
  );
}
