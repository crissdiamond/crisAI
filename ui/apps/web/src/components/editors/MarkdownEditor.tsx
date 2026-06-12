import React, { useRef } from "react";
import { Editor as ToastEditor } from "@toast-ui/react-editor";
import "@toast-ui/editor/dist/toastui-editor.css";
import { CodeEditor } from "./CodeEditor.js";
import { joinFrontMatter, splitFrontMatter } from "./frontMatter.js";
import type { EditorProps } from "./types.js";

// Markdown WYSIWYG editor backed by Toast UI (decided in TODO-025 Phase 2).
//
// Toast UI has no front-matter awareness and normalises whitespace on
// getMarkdown(), so two carry-forward caveats from the Phase 2 decision are
// honoured here:
//   (a) The YAML front-matter block is split off and preserved verbatim. Toast
//       UI only ever sees the body; the front-matter block is edited (when at
//       all) through a separate CodeEditor over the *whole raw block*
//       (delimiters included), which guarantees a byte-stable join when the
//       user never touches it.
//   (b) Dirty-tracking: onChange is only forwarded to the parent in response to
//       a real user edit (Toast UI's onChange, or a front-matter edit). It is
//       never emitted on initial mount, so opening a file and saving without
//       editing leaves the bytes untouched.
//
// The incoming `value` is split exactly once, on first render. After that the
// front-matter and body are tracked in refs and recombined on every edit; the
// Toast UI editor is intentionally uncontrolled (initialValue only) so it owns
// the live body and we never feed normalised markdown back into it mid-session.

export function MarkdownEditor({ value, onChange, readOnly, path }: EditorProps) {
  const editorRef = useRef<ToastEditor>(null);

  // Split once on first render and hold the parts in refs. Refs (not state)
  // because Toast UI owns the live body via its own instance; re-rendering this
  // component must not reset the WYSIWYG editor.
  const initial = useRef<{ frontMatter: string; body: string } | null>(null);
  if (initial.current === null) {
    initial.current = splitFrontMatter(value);
  }
  const frontMatterRef = useRef(initial.current.frontMatter);
  const bodyRef = useRef(initial.current.body);

  const hasFrontMatter = initial.current.frontMatter.length > 0;

  // A real WYSIWYG/markdown edit: pull the new body from Toast UI and recombine
  // with the current (possibly edited) front-matter. Not called on mount.
  function handleBodyChange() {
    const instance = editorRef.current?.getInstance();
    if (!instance) return;
    const nextBody = instance.getMarkdown();
    bodyRef.current = nextBody;
    onChange(joinFrontMatter(frontMatterRef.current, nextBody));
  }

  // A real front-matter edit (the raw block, delimiters included) from the
  // CodeEditor; recombine with the current body.
  function handleFrontMatterChange(nextFrontMatter: string) {
    frontMatterRef.current = nextFrontMatter;
    onChange(joinFrontMatter(nextFrontMatter, bodyRef.current));
  }

  // Read-only files must not be editable. Toast UI's viewer mode is heavier than
  // needed and still front-matter unaware, so fall back to the read-only
  // markdown CodeEditor over the whole file — simple and guaranteed inert.
  if (readOnly) {
    return (
      <CodeEditor
        value={value}
        onChange={() => {}}
        path={path}
        language="markdown"
        readOnly
      />
    );
  }

  return (
    <div className="markdown-editor">
      {hasFrontMatter ? (
        <details className="markdown-frontmatter" open={false}>
          <summary className="markdown-frontmatter-summary">Front matter (YAML)</summary>
          <div className="markdown-frontmatter-body">
            <CodeEditor
              value={frontMatterRef.current}
              onChange={handleFrontMatterChange}
              path={path}
              language="yaml"
            />
          </div>
        </details>
      ) : null}
      <div className="markdown-toastui-host">
        <ToastEditor
          ref={editorRef}
          initialValue={initial.current.body}
          initialEditType="wysiwyg"
          hideModeSwitch={false}
          height="100%"
          useCommandShortcut
          onChange={handleBodyChange}
        />
      </div>
    </div>
  );
}
