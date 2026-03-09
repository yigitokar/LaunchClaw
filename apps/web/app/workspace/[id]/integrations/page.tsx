"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/time";

type IntegrationItem = {
  id: string;
  provider: string;
  status: string;
  scope_summary: string | null;
  updated_at: string;
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function statusBadgeClass(status: string): string {
  return `run-badge run-badge--status-${status.replace(/_/g, "-")}`;
}

export default function WorkspaceIntegrationsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const handledSuccessParam = useRef(false);
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadIntegrations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiFetch<{ items: IntegrationItem[] }>(`/api/claws/${clawId}/integrations`);
      setIntegrations(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, [clawId]);

  useEffect(() => {
    void loadIntegrations();
  }, [loadIntegrations]);

  useEffect(() => {
    if (handledSuccessParam.current || searchParams.get("integration") !== "success") {
      return;
    }

    handledSuccessParam.current = true;
    setSuccessMessage("GitHub connected");
    router.replace(`/workspace/${clawId}/integrations`);
  }, [clawId, router, searchParams]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timeout = window.setTimeout(() => setSuccessMessage(null), 3000);
    return () => window.clearTimeout(timeout);
  }, [successMessage]);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      setError(null);
      const data = await apiFetch<{ redirect_url: string }>(
        `/api/claws/${clawId}/integrations/github/connect`,
        { method: "POST" },
      );
      window.location.assign(data.redirect_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start GitHub connection");
      setConnecting(false);
    }
  };

  const handleDisconnect = async (integrationId: string) => {
    const key = `disconnect:${integrationId}`;
    try {
      setActionKey(key);
      setError(null);
      const updated = await apiFetch<{ id: string; status: string }>(
        `/api/claws/${clawId}/integrations/${integrationId}/disconnect`,
        { method: "POST" },
      );
      setIntegrations((current) =>
        current.map((integration) =>
          integration.id === integrationId ? { ...integration, status: updated.status } : integration,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to disconnect integration");
    } finally {
      setActionKey(null);
    }
  };

  const handleRefresh = async (integrationId: string) => {
    const key = `refresh:${integrationId}`;
    try {
      setActionKey(key);
      setError(null);
      const updated = await apiFetch<{ id: string; status: string; updated_at: string }>(
        `/api/claws/${clawId}/integrations/${integrationId}/refresh`,
        { method: "POST" },
      );
      setIntegrations((current) =>
        current.map((integration) =>
          integration.id === integrationId
            ? {
                ...integration,
                status: updated.status,
                updated_at: updated.updated_at,
              }
            : integration,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh integration");
    } finally {
      setActionKey(null);
    }
  };

  return (
    <ShellCard
      title="Integrations"
      description="Connect GitHub and monitor the current health of workspace integrations."
    >
      {successMessage ? <div className="integration-toast">{successMessage}</div> : null}

      <div className="integration-toolbar">
        <p className="muted">GitHub installs are tracked per Claw and can be refreshed without leaving the workspace.</p>
        <button className="editor-save" type="button" onClick={handleConnect} disabled={connecting}>
          {connecting ? "Redirecting..." : "Connect GitHub"}
        </button>
      </div>

      <div className="section-divider" />

      {loading ? (
        <p className="muted">Loading integrations...</p>
      ) : integrations.length === 0 ? (
        <p className="muted">No integrations connected yet. Start with GitHub to give this Claw repository access.</p>
      ) : (
        <div className="integration-list">
          {integrations.map((integration) => (
            <article className="integration-card" key={integration.id}>
              <div className="integration-card-header">
                <div className="activity-copy">
                  <div className="run-badge-row">
                    <span className="run-badge run-badge--trigger">{formatLabel(integration.provider)}</span>
                    <span className={statusBadgeClass(integration.status)}>{formatLabel(integration.status)}</span>
                  </div>
                  <p className="integration-summary">
                    {integration.scope_summary || "GitHub App installation is connected to this workspace."}
                  </p>
                </div>
                <time className="activity-time" dateTime={integration.updated_at} title={formatDateTime(integration.updated_at)}>
                  Updated {formatRelativeTime(integration.updated_at)}
                </time>
              </div>

              <div className="integration-actions">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleRefresh(integration.id)}
                  disabled={actionKey !== null}
                >
                  {actionKey === `refresh:${integration.id}` ? "Refreshing..." : "Refresh"}
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleDisconnect(integration.id)}
                  disabled={actionKey !== null}
                >
                  {actionKey === `disconnect:${integration.id}` ? "Disconnecting..." : "Disconnect"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {error ? <p className="status">{error}</p> : null}
    </ShellCard>
  );
}
