import React, { useEffect, useState } from "react";
import {
  type UiWorkspaceFileRecord,
  type UiWorkspaceUploadTarget
} from "@crisai/contracts";
import { runtime } from "../lib/runtime.js";
import { fileToBase64, humanizeError } from "../lib/format.js";
import { getEditorForPath } from "./editors/registry.js";

export function WorkspaceBrowser({ session }: { session: string }) {
  const [roots, setRoots] = useState<Record<string, string>>({});
  const [rootName, setRootName] = useState("knowledge");
  const [files, setFiles] = useState<UiWorkspaceFileRecord[]>([]);
  const [filter, setFilter] = useState("");
  const [selectedPath, setSelectedPath] = useState("");
  const [content, setContent] = useState("");
  // The content as last loaded/saved; `content !== original` means dirty.
  const [original, setOriginal] = useState("");
  const [editable, setEditable] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [status, setStatus] = useState("Workspace ready.");
  const [uploadTarget, setUploadTarget] = useState<UiWorkspaceUploadTarget>("task_inputs");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  useEffect(() => {
    runtime
      .getWorkspaceRoots()
      .then((state) => {
        setRoots(state.roots);
        const firstRoot = Object.keys(state.roots)[0] ?? "knowledge";
        setRootName(firstRoot);
        return loadTree(firstRoot);
      })
      .catch((reason: unknown) => setStatus(humanizeError(reason)));
  }, []);

  async function loadTree(nextRoot = rootName) {
    const tree = await runtime.getWorkspaceTree(nextRoot);
    setRootName(tree.root);
    setFiles(tree.files);
    setSelectedPath("");
    setContent("");
    setOriginal("");
    setStatus(`${tree.files.length} files in ${tree.path}.`);
  }

  async function openFile(path: string, record?: UiWorkspaceFileRecord) {
    setLoadingFile(true);
    setSelectedPath(path);
    setEditable(record?.editable ?? true);
    try {
      const file = await runtime.getWorkspaceFile(path);
      setSelectedPath(file.path);
      setContent(file.content);
      setOriginal(file.content);
      setStatus(`Opened ${file.path}.`);
    } catch (reason: unknown) {
      setStatus(humanizeError(reason));
    } finally {
      setLoadingFile(false);
    }
  }

  async function saveFile() {
    if (!selectedPath) return;
    const result = await runtime.saveWorkspaceFile(selectedPath, content);
    if (result.saved) {
      // Mark clean: the saved content becomes the new baseline.
      setOriginal(content);
    }
    setStatus(result.saved ? `Saved ${result.path}.` : `Save did not complete for ${result.path}.`);
    await loadTree(rootName);
    setSelectedPath(result.path);
  }

  async function uploadSelectedFile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) return;
    const contentBase64 = await fileToBase64(uploadFile);
    const result = await runtime.uploadWorkspaceFile({
      target: uploadTarget,
      session,
      filename: uploadFile.name,
      content_base64: contentBase64
    });
    setStatus(`Uploaded ${result.path}.`);
    setUploadFile(null);
    await loadTree(uploadTarget === "task_inputs" ? "tasks" : "knowledge");
  }

  const visibleFiles = files.filter((file) => file.path.toLowerCase().includes(filter.toLowerCase()));

  const Editor = getEditorForPath(selectedPath);
  // Dirty when an editable file is open and its content diverges from baseline.
  const isDirty = selectedPath !== "" && editable && content !== original;
  const readOnly = !selectedPath || !editable;

  return (
    <section className="workspace-browser" aria-label="Workspace browser">
      <header>
        <p>{status}</p>
      </header>
      <div className="workspace-controls">
        <label>
          Folder
          <select value={rootName} onChange={(event) => void loadTree(event.target.value)}>
            {Object.entries(roots).map(([name, path]) => (
              <option key={name} value={name}>{name}: {path}</option>
            ))}
          </select>
        </label>
        <label>
          Filter
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Find files" />
        </label>
      </div>
      <details className="workspace-upload-disclosure">
        <summary className="workspace-upload-summary">Upload a file</summary>
        <form className="workspace-upload" onSubmit={uploadSelectedFile}>
          <label>
            Upload target
            <select
              value={uploadTarget}
              onChange={(event) => setUploadTarget(event.target.value as UiWorkspaceUploadTarget)}
            >
              <option value="task_inputs">Current task inputs</option>
              <option value="knowledge_intake">Knowledge intake</option>
            </select>
          </label>
          <label>
            Source file
            <input type="file" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" disabled={!uploadFile}>Upload</button>
        </form>
      </details>
      <div className="workspace-editor-grid">
        <div className="workspace-files">
          {visibleFiles.length === 0 ? <p>No files found.</p> : null}
          {visibleFiles.map((file) => (
            <button
              key={file.path}
              type="button"
              className={file.path === selectedPath ? "selected-file" : ""}
              disabled={!file.editable}
              onClick={() => void openFile(file.path, file)}
            >
              <span>{file.name}</span>
              <small>{file.path.slice(0, file.path.lastIndexOf("/") + 1)}</small>
            </button>
          ))}
        </div>
        <div className="workspace-editor">
          <p id="workspace-editor-path">
            {selectedPath || "No file selected."}
            {selectedPath && !editable ? (
              <span className="editor-state-note"> · read-only</span>
            ) : null}
            {isDirty ? (
              <span className="editor-state-note editor-dirty"> · Unsaved changes</span>
            ) : null}
          </p>
          <div className="workspace-editor-host">
            {loadingFile ? (
              <p className="editor-loading">Loading file…</p>
            ) : selectedPath ? (
              <React.Suspense fallback={<p className="editor-loading">Loading editor…</p>}>
                <Editor
                  value={content}
                  onChange={setContent}
                  path={selectedPath}
                  readOnly={readOnly}
                />
              </React.Suspense>
            ) : (
              <p className="editor-loading">Select a file to edit.</p>
            )}
          </div>
          <button type="button" disabled={!isDirty} onClick={() => void saveFile()}>Save</button>
        </div>
      </div>
    </section>
  );
}
