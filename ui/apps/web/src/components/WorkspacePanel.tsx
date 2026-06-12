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
    setStatus(`${tree.files.length} files in ${tree.path}.`);
  }

  async function openFile(path: string) {
    const file = await runtime.getWorkspaceFile(path);
    setSelectedPath(file.path);
    setContent(file.content);
    setStatus(`Opened ${file.path}.`);
  }

  async function saveFile() {
    if (!selectedPath) return;
    const result = await runtime.saveWorkspaceFile(selectedPath, content);
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
      <div className="workspace-editor-grid">
        <div className="workspace-files">
          {visibleFiles.length === 0 ? <p>No files found.</p> : null}
          {visibleFiles.map((file) => (
            <button
              key={file.path}
              type="button"
              className={file.path === selectedPath ? "selected-file" : ""}
              disabled={!file.editable}
              onClick={() => void openFile(file.path)}
            >
              <span>{file.name}</span>
              <small>{file.path.slice(0, file.path.lastIndexOf("/") + 1)}</small>
            </button>
          ))}
        </div>
        <div className="workspace-editor">
          <p id="workspace-editor-path">{selectedPath || "No file selected."}</p>
          <Editor
            value={content}
            onChange={setContent}
            path={selectedPath}
            readOnly={!selectedPath}
          />
          <button type="button" disabled={!selectedPath} onClick={() => void saveFile()}>Save</button>
        </div>
      </div>
    </section>
  );
}
