"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";

type WorkspaceFile = {
  id: string;
  path: string;
  kind: string;
  is_desired_state: boolean;
  version: number;
  updated_at: string;
};

type FileContent = {
  path: string;
  kind: string;
  content: string;
  version: number;
  updated_at: string;
};

export default function WorkspaceFilesPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [editorValue, setEditorValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<{ items: WorkspaceFile[] }>(
        `/api/claws/${clawId}/workspace/files`,
      );
      setFiles(data.items);
      if (!selectedPath && data.items.length > 0) {
        setSelectedPath(data.items[0].path);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load files");
    } finally {
      setLoading(false);
    }
  }, [clawId, selectedPath]);

  const loadFileContent = useCallback(
    async (path: string) => {
      try {
        setError(null);
        const data = await apiFetch<FileContent>(
          `/api/claws/${clawId}/workspace/files/content?path=${encodeURIComponent(path)}`,
        );
        setFileContent(data);
        setEditorValue(data.content);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load file");
      }
    },
    [clawId],
  );

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  useEffect(() => {
    if (selectedPath) {
      loadFileContent(selectedPath);
    }
  }, [selectedPath, loadFileContent]);

  const handleSave = async () => {
    if (!fileContent || !selectedPath) return;
    try {
      setSaving(true);
      setError(null);
      setSaveMessage(null);
      const result = await apiFetch<{ path: string; version: number; updated_at: string }>(
        `/api/claws/${clawId}/workspace/files/content`,
        {
          method: "PUT",
          body: JSON.stringify({
            path: selectedPath,
            content: editorValue,
            base_version: fileContent.version,
          }),
        },
      );
      setFileContent((prev) => (prev ? { ...prev, version: result.version, updated_at: result.updated_at } : prev));
      setSaveMessage("Saved");
      setTimeout(() => setSaveMessage(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const selectedFile = files.find((f) => f.path === selectedPath);
  const isDirty = fileContent && editorValue !== fileContent.content;

  return (
    <ShellCard title="Files" description="View and edit your Claw's desired-state files.">
      {loading ? (
        <p className="muted">Loading files...</p>
      ) : (
        <div className="files-layout">
          <div className="file-list">
            {files.map((file) => (
              <button
                key={file.id}
                className={`file-item ${file.path === selectedPath ? "file-item--active" : ""}`}
                onClick={() => setSelectedPath(file.path)}
              >
                <code>{file.path}</code>
                {file.is_desired_state && <span className="file-badge">editable</span>}
              </button>
            ))}
            {files.length === 0 && <p className="muted">No files yet.</p>}
          </div>
          <div className="file-editor">
            {selectedPath && fileContent ? (
              <>
                <div className="editor-header">
                  <strong>{selectedPath}</strong>
                  <span className="muted">v{fileContent.version}</span>
                  {saveMessage && <span className="file-badge">{saveMessage}</span>}
                </div>
                <textarea
                  className="editor-textarea"
                  value={editorValue}
                  onChange={(e) => setEditorValue(e.target.value)}
                  readOnly={!selectedFile?.is_desired_state}
                  spellCheck={false}
                />
                {selectedFile?.is_desired_state && (
                  <div className="editor-footer">
                    <button className="editor-save" onClick={handleSave} disabled={saving || !isDirty}>
                      {saving ? "Saving..." : "Save"}
                    </button>
                  </div>
                )}
              </>
            ) : (
              <p className="muted">Select a file to view its contents.</p>
            )}
          </div>
        </div>
      )}
      {error && <p className="status">{error}</p>}
    </ShellCard>
  );
}
