"use client";

import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import type { Secret } from "@launchclaw/types";
import { ShellCard } from "@launchclaw/ui";
import { listSecrets, revokeSecret, upsertSecret } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/time";

const EMPTY_FORM = {
  provider: "github",
  label: "",
  value: "",
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function statusBadgeClass(status: string): string {
  return `run-badge run-badge--status-${status.replace(/_/g, "-")}`;
}

function sortSecrets(items: Secret[]): Secret[] {
  return [...items].sort((left, right) => {
    if (left.status !== right.status) {
      return left.status === "active" ? -1 : 1;
    }

    return right.created_at.localeCompare(left.created_at);
  });
}

export default function WorkspaceSecretsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const feedbackTimeoutRef = useRef<number | null>(null);

  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [formValues, setFormValues] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busySecretId, setBusySecretId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const showStatusMessage = useCallback((message: string) => {
    setStatusMessage(message);

    if (feedbackTimeoutRef.current !== null) {
      window.clearTimeout(feedbackTimeoutRef.current);
    }

    feedbackTimeoutRef.current = window.setTimeout(() => {
      setStatusMessage(null);
      feedbackTimeoutRef.current = null;
    }, 2500);
  }, []);

  const loadSecrets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listSecrets(clawId);
      setSecrets(sortSecrets(data.items));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load secrets");
    } finally {
      setLoading(false);
    }
  }, [clawId]);

  useEffect(() => {
    void loadSecrets();

    return () => {
      if (feedbackTimeoutRef.current !== null) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, [loadSecrets]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const provider = formValues.provider.trim();
    const label = formValues.label.trim();
    if (!provider || !label || !formValues.value.trim()) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const saved = await upsertSecret(clawId, {
        provider,
        label,
        value: formValues.value,
      });

      setSecrets((current) => sortSecrets([saved, ...current.filter((secret) => secret.id !== saved.id)]));
      setFormValues((current) => ({ ...current, label: "", value: "" }));
      showStatusMessage(saved.restart_required ? "Secret saved. Restart required." : "Secret saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save secret");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async (secretId: string) => {
    try {
      setBusySecretId(secretId);
      setError(null);
      const updated = await revokeSecret(clawId, secretId);
      setSecrets((current) =>
        sortSecrets(current.map((secret) => (secret.id === updated.id ? updated : secret))),
      );
      showStatusMessage(updated.restart_required ? "Secret revoked. Restart required." : "Secret revoked");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke secret");
    } finally {
      setBusySecretId((current) => (current === secretId ? null : current));
    }
  };

  const activeSecrets = secrets.filter((secret) => secret.status === "active");
  const revokedSecrets = secrets.filter((secret) => secret.status === "revoked");

  return (
    <ShellCard
      title="Secrets"
      description="Store provider credentials for this workspace. Values are accepted but never returned to the client."
    >
      {loading ? (
        <p className="muted">Loading secrets...</p>
      ) : (
        <div className="settings-stack">
          <form className="schedule-card schedule-form" onSubmit={handleSubmit}>
            <div className="settings-section-header">
              <div>
                <h3>Add Secret</h3>
                <p className="muted">Saving a secret rotates it immediately and may require a runtime restart.</p>
              </div>
              <button className="editor-save" type="submit" disabled={submitting || !formValues.label.trim() || !formValues.value.trim()}>
                {submitting ? "Saving..." : "Add Secret"}
              </button>
            </div>

            <div className="schedule-editor-grid">
              <label className="schedule-field">
                <span>Provider</span>
                <input
                  className="settings-input"
                  type="text"
                  value={formValues.provider}
                  onChange={(event) =>
                    setFormValues((current) => ({ ...current, provider: event.target.value }))
                  }
                  placeholder="github"
                  maxLength={80}
                />
              </label>

              <label className="schedule-field">
                <span>Label</span>
                <input
                  className="settings-input"
                  type="text"
                  value={formValues.label}
                  onChange={(event) =>
                    setFormValues((current) => ({ ...current, label: event.target.value }))
                  }
                  placeholder="repo_token"
                  maxLength={120}
                />
              </label>

              <label className="schedule-field">
                <span>Value</span>
                <input
                  className="settings-input"
                  type="password"
                  value={formValues.value}
                  onChange={(event) =>
                    setFormValues((current) => ({ ...current, value: event.target.value }))
                  }
                  placeholder="ghp_..."
                  autoComplete="off"
                />
              </label>
            </div>
          </form>

          <section className="settings-section">
            <div className="settings-section-header">
              <div>
                <h3>Active Secrets</h3>
                <p className="muted">Current secrets that LaunchClaw can use for provider access.</p>
              </div>
              <span className="run-badge run-badge--trigger">{activeSecrets.length} active</span>
            </div>

            {activeSecrets.length === 0 ? (
              <p className="muted">No active secrets yet.</p>
            ) : (
              <div className="integration-grid">
                {activeSecrets.map((secret) => {
                  const isBusy = busySecretId === secret.id;

                  return (
                    <article className="integration-card" key={secret.id}>
                      <div className="integration-header">
                        <div className="integration-title">
                          <div className="run-badge-row">
                            <span className="run-badge run-badge--trigger">{formatLabel(secret.provider)}</span>
                            <span className={statusBadgeClass(secret.status)}>{formatLabel(secret.status)}</span>
                            {secret.restart_required ? <span className="file-badge">restart required</span> : null}
                          </div>
                          <h3>{secret.label}</h3>
                        </div>
                        <div className="integration-actions">
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void handleRevoke(secret.id)}
                            disabled={isBusy}
                          >
                            {isBusy ? "Working..." : "Revoke"}
                          </button>
                        </div>
                      </div>

                      <p className="integration-summary">The stored value is not returned after save. Rotate by submitting the same label again.</p>

                      <div className="integration-meta-grid">
                        <div className="integration-meta-item">
                          <span>Last rotated</span>
                          <strong title={secret.last_rotated_at ? formatDateTime(secret.last_rotated_at) : undefined}>
                            {secret.last_rotated_at ? formatRelativeTime(secret.last_rotated_at) : "Pending"}
                          </strong>
                        </div>
                        <div className="integration-meta-item">
                          <span>Created</span>
                          <strong title={formatDateTime(secret.created_at)}>{formatDateTime(secret.created_at)}</strong>
                        </div>
                        <div className="integration-meta-item">
                          <span>Secret ID</span>
                          <strong>{secret.id}</strong>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {revokedSecrets.length ? (
            <>
              <div className="section-divider" />
              <section className="settings-section">
                <div className="settings-section-header">
                  <div>
                    <h3>Revoked</h3>
                    <p className="muted">Recently revoked secrets remain listed for auditability.</p>
                  </div>
                  <span className="run-badge run-badge--trigger">{revokedSecrets.length} revoked</span>
                </div>

                <div className="integration-grid">
                  {revokedSecrets.map((secret) => (
                    <article className="integration-card" key={secret.id}>
                      <div className="integration-header">
                        <div className="integration-title">
                          <div className="run-badge-row">
                            <span className="run-badge run-badge--trigger">{formatLabel(secret.provider)}</span>
                            <span className={statusBadgeClass(secret.status)}>{formatLabel(secret.status)}</span>
                            {secret.restart_required ? <span className="file-badge">restart required</span> : null}
                          </div>
                          <h3>{secret.label}</h3>
                        </div>
                      </div>

                      <div className="integration-meta-grid">
                        <div className="integration-meta-item">
                          <span>Last rotated</span>
                          <strong title={secret.last_rotated_at ? formatDateTime(secret.last_rotated_at) : undefined}>
                            {secret.last_rotated_at ? formatRelativeTime(secret.last_rotated_at) : "Pending"}
                          </strong>
                        </div>
                        <div className="integration-meta-item">
                          <span>Created</span>
                          <strong title={formatDateTime(secret.created_at)}>{formatDateTime(secret.created_at)}</strong>
                        </div>
                        <div className="integration-meta-item">
                          <span>Secret ID</span>
                          <strong>{secret.id}</strong>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </>
          ) : null}
        </div>
      )}

      {statusMessage ? <p className="settings-feedback">{statusMessage}</p> : null}
      {error ? <p className="status">{error}</p> : null}
    </ShellCard>
  );
}
