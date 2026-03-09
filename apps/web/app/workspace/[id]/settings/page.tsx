"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";

type ClawDetail = {
  id: string;
  name: string;
  status: string;
  model_access_mode: string;
  created_at: string;
  updated_at: string;
};

export default function WorkspaceSettingsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [claw, setClaw] = useState<ClawDetail | null>(null);
  const [nameValue, setNameValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const loadClaw = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<ClawDetail>(`/api/claws/${clawId}`);
      setClaw(data);
      setNameValue(data.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, [clawId]);

  useEffect(() => {
    loadClaw();
  }, [loadClaw]);

  useEffect(() => {
    if (searchParams.get("integration") !== "success") {
      return;
    }

    router.replace(`/workspace/${clawId}/integrations?integration=success`);
  }, [clawId, router, searchParams]);

  const handleSaveName = async () => {
    if (!nameValue.trim()) return;
    try {
      setSaving(true);
      setError(null);
      setSaveMessage(null);
      const updated = await apiFetch<ClawDetail>(`/api/claws/${clawId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: nameValue.trim() }),
      });
      setClaw(updated);
      setSaveMessage("Saved");
      setTimeout(() => setSaveMessage(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <ShellCard title="Settings" description="Loading...">
        <p className="muted">Loading settings...</p>
      </ShellCard>
    );
  }

  if (!claw) {
    return (
      <ShellCard title="Settings" description="Could not load Claw settings.">
        {error && <p className="status">{error}</p>}
      </ShellCard>
    );
  }

  const isDirty = nameValue.trim() !== claw.name;

  return (
    <ShellCard title="Settings" description="Manage your Claw's configuration.">
      <div className="table-like">
        <div className="table-row">
          <strong>Name</strong>
          <div className="settings-name-row">
            <input
              className="settings-input"
              type="text"
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              maxLength={80}
            />
            <button className="editor-save" onClick={handleSaveName} disabled={saving || !isDirty}>
              {saving ? "Saving..." : "Save"}
            </button>
            {saveMessage && <span className="file-badge">{saveMessage}</span>}
          </div>
        </div>
        <div className="table-row">
          <strong>Status</strong>
          <span className="status">{claw.status}</span>
        </div>
        <div className="table-row">
          <strong>Model Access</strong>
          <span>{claw.model_access_mode}</span>
        </div>
        <div className="table-row">
          <strong>Created</strong>
          <span>{new Date(claw.created_at).toLocaleDateString()}</span>
        </div>
      </div>
      {error && <p className="status">{error}</p>}
    </ShellCard>
  );
}
