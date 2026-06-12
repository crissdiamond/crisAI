// Minimal local declaration for `@toast-ui/react-editor`, which ships no
// TypeScript types (the plan calls for this shim). The core `@toast-ui/editor`
// package *does* ship types, so the ref instance is typed against its
// `EditorCore`, giving `getInstance().getMarkdown()` a real signature. Only the
// props this codebase uses are declared; unknown props are permitted.
declare module "@toast-ui/react-editor" {
  import type { Component } from "react";
  import type { EditorCore } from "@toast-ui/editor";

  export interface ToastEditorProps {
    initialValue?: string;
    initialEditType?: "markdown" | "wysiwyg";
    previewStyle?: "tab" | "vertical";
    hideModeSwitch?: boolean;
    height?: string;
    useCommandShortcut?: boolean;
    onChange?: () => void;
    // Toast UI accepts many further options; allow them without widening the
    // typed surface this component relies on.
    [key: string]: unknown;
  }

  export class Editor extends Component<ToastEditorProps> {
    getInstance(): EditorCore;
  }
}
