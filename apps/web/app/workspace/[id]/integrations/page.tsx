"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/time";

type IntegrationItem = {
  id: string;
  claw_id: string;
  provider: string;
  status: string;
  external_account_ref: string | null;
  scope_summary: string | null;
  created_at: string;
  updated_at: string;
};

type IntegrationsResponse = {
  items: IntegrationItem[];
};

type ConnectResponse = {
  redirect_url: string;
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
  const feedbackTimeoutRef = useRef<number | null>(null);
  const handledCallbackStateRef = useRef(false);

  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [busyIntegrationId, setBusyIntegrationId] = useState<string | null>(null);
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

  const loadIntegrations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiFetch<IntegrationsResponse>(`/api/claws/${clawId}/integrations`);
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
    return () => {
      if (feedbackTimeoutRef.current !== null) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (handledCallbackStateRef.current || searchParams.get("github") !== "connected") {
      return;
    }

    handledCallbackStateRef.current = true;
    showStatusMessage("GitHub connected");
    router.replace(`/workspace/${clawId}/integrations`);
  }, [clawId, router, searchParams, showStatusMessage]);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      setError(null);
      const data = await apiFetch<ConnectResponse>(`/api/claws/${clawId}/integrations/github/connect`, {
        method: "POST",
      });
      window.location.assign(data.redirect_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start GitHub connect");
      setConnecting(false);
    }
  };

  const handleDisconnect = async (integrationId: string) => {
    try {
      setBusyIntegrationId(integrationId);
      setError(null);
      const updated = await apiFetch<IntegrationItem>(
        `/api/claws/${clawId}/integrations/${integrationId}/disconnect`,
        { method: "POST" },
      );
      setIntegrations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      showStatusMessage("GitHub disconnected");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to disconnect integration");
    } finally {
      setBusyIntegrationId((current) => (current === integrationId ? null : current));
    }
  };

  const handleRefresh = async (integrationId: string) => {
    try {
      setBusyIntegrationId(integrationId);
      setError(null);
      const updated = await apiFetch<IntegrationItem>(
        `/api/claws/${clawId}/integrations/${integrationId}/refresh`,
        { method: "POST" },
      );
      setIntegrations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      showStatusMessage("Integration refreshed");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh integration");
    } finally {
      setBusyIntegrationId((current) => (current === integrationId ? null : current));
    }
  };

  const hasConnectedGitHub = integrations.some(
    (integration) => integration.provider === "github" && integration.status === "connected",
  );

  return (
    <ShellCard title="Integrations" description="Connect GitHub so your Claw can work with repositories and pull requests.">
      <div className="settings-stack">
        <section className="integration-hero">
          <div>
            <h3>GitHub App</h3>
            <p className="muted">
              Install the LaunchClaw GitHub App to grant repository metadata, pull request, and contents access.
            </p>
          </div>
          <button className="editor-save" type="button" onClick={handleConnect} disabled={connecting || hasConnectedGitHub}>
            {connecting ? "Redirecting..." : hasConnectedGitHub ? "GitHub Connected" : "Connect GitHub"}
          </button>
        </section>

        {loading ? (
          <p className="muted">Loading integrations...</p>
        ) : integrations.length === 0 ? (
          <div className="integration-card">
            <div className="integration-header">
              <div>
                <h3>No integrations yet</h3>
                <p className="muted">Start the GitHub install flow to attach your first integration.</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="integration-grid">
            {integrations.map((integration) => {
              const installationId = integration.external_account_ref;
              const isBusy = busyIntegrationId === integration.id;
              const isConnected = integration.status === "connected";

              return (
                <article className="integration-card" key={integration.id}>
                  <div className="integration-header">
                    <div className="integration-title">
                      <div className="run-badge-row">
                        <span className="run-badge run-badge--trigger">{formatLabel(integration.provider)}</span>
                        <span className={statusBadgeClass(integration.status)}>{formatLabel(integration.status)}</span>
                      </div>
                      <h3>GitHub</h3>
                    </div>
                    <div className="integration-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => void handleRefresh(integration.id)}
                        disabled={isBusy}
                      >
                        {isBusy ? "Working..." : "Refresh"}
                      </button>
                      {isConnected ? (
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => void handleDisconnect(integration.id)}
                          disabled={isBusy}
                        >
                          Disconnect
                        </button>
                      ) : (
                        <button className="editor-save" type="button" onClick={handleConnect} disabled={connecting || isBusy}>
                          {connecting ? "Redirecting..." : "Reconnect"}
                        </button>
                      )}
                    </div>
                  </div>

                  <p className="integration-summary">{integration.scope_summary || "Awaiting granted repository scope."}</p>

                  <div className="integration-meta-grid">
                    <div className="integration-meta-item">
                      <span>Installation</span>
                      <strong>{installationId ? `#${installationId}` : "Pending"}</strong>
                    </div>
                    <div className="integration-meta-item">
                      <span>Last checked</span>
                      <strong title={formatDateTime(integration.updated_at)}>{formatRelativeTime(integration.updated_at)}</strong>
                    </div>
                    <div className="integration-meta-item">
                      <span>Record created</span>
                      <strong title={formatDateTime(integration.created_at)}>{formatDateTime(integration.created_at)}</strong>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {statusMessage ? <p className="settings-feedback">{statusMessage}</p> : null}
        {error ? <p className="status">{error}</p> : null}
      </div>
    </ShellCard>
  );
}
