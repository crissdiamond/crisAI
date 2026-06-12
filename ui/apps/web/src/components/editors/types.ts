import type React from "react";

export interface EditorProps {
  value: string;
  onChange: (next: string) => void;
  readOnly?: boolean;
  path: string;
}

export type EditorComponent = React.ComponentType<EditorProps>;
