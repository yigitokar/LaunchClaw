"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Approval } from "@launchclaw/types";
import { ShellCard } from "@launchclaw/ui";
import { approveApproval, denyApproval, listApprovals } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/time";

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function statusBadgeClass(status: string): string {
  return `run-badge run-badge--status-${status.replace(/_/g, "-")}`;
}

export default function WorkspaceApprovalsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const feedbackTimeoutRef = useRef<number | null>(null);

  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyApprovalId, setBusyApprovalId] = useState<string | null>(null);
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

  const fetchApprovalPage = useCallback(
    async (cursor: string | null) => listApprovals(clawId, { limit: 20, cursor }),
    [clawId],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadInitialApprovals() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchApprovalPage(null);
        if (cancelled) {
          return;
        }

        setApprovals(data.items);
        setNextCursor(data.next_cursor);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load approvals");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialApprovals();

    return () => {
      cancelled = true;
      if (feedbackTimeoutRef.current !== null) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, [fetchApprovalPage]);

  const handleResolve = async (approvalId: string, decision: "approved" | "denied") => {
    try {
      setBusyApprovalId(approvalId);
      setError(null);
      const updated =
        decision === "approved"
          ? await approveApproval(approvalId)
          : await denyApproval(approvalId);

      setApprovals((current) =>
        current.map((approval) => (approval.id === updated.id ? updated : approval)),
      );
      showStatusMessage(decision === "approved" ? "Approval approved" : "Approval denied");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update approval");
    } finally {
      setBusyApprovalId((current) => (current === approvalId ? null : current));
    }
  };

  const handleLoadMore = async () => {
    if (!nextCursor) {
      return;
    }

    try {
      setLoadingMore(true);
      setError(null);
      const data = await fetchApprovalPage(nextCursor);
      setApprovals((current) => [...current, ...data.items]);
      setNextCursor(data.next_cursor);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more approvals");
    } finally {
      setLoadingMore(false);
    }
  };

  const pendingApprovals = approvals.filter((approval) => approval.status === "pending");
  const resolvedApprovals = approvals.filter((approval) => approval.status !== "pending");

  return (
    <ShellCard
      title="Approvals"
      description="Review pending actions before LaunchClaw performs write-capable or destructive work."
    >
      {loading ? (
        <p className="muted">Loading approvals...</p>
      ) : approvals.length === 0 ? (
        <p className="muted">No approvals yet. Pending actions will appear here when a run needs your decision.</p>
      ) : (
        <div className="settings-stack">
          <section className="settings-section">
            <div className="settings-section-header">
              <div>
                <h3>Pending</h3>
                <p className="muted">Approve or deny actions that are waiting on your review.</p>
              </div>
              <span className="run-badge run-badge--trigger">{pendingApprovals.length} open</span>
            </div>

            {pendingApprovals.length === 0 ? (
              <p className="muted">No pending approvals.</p>
            ) : (
              <div className="run-list">
                {pendingApprovals.map((approval) => {
                  const isBusy = busyApprovalId === approval.id;

                  return (
                    <article className="run-card" key={approval.id}>
                      <div className="run-card-header">
                        <div className="run-badge-row">
                          <span className="run-badge run-badge--trigger">{formatLabel(approval.action_type)}</span>
                          <span className={statusBadgeClass(approval.status)}>{formatLabel(approval.status)}</span>
                        </div>
                        <time
                          className="activity-time"
                          dateTime={approval.requested_at}
                          title={formatDateTime(approval.requested_at)}
                        >
                          {formatRelativeTime(approval.requested_at)}
                        </time>
                      </div>

                      <p className="run-summary">
                        {approval.payload_summary || "No payload summary was provided for this approval request."}
                      </p>

                      <div className="run-meta">
                        <span>Requested {formatRelativeTime(approval.requested_at)}</span>
                        {approval.run_id ? <span>Run {approval.run_id}</span> : null}
                      </div>

                      <div className="integration-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => void handleResolve(approval.id, "denied")}
                          disabled={isBusy}
                        >
                          {isBusy ? "Working..." : "Deny"}
                        </button>
                        <button
                          className="editor-save"
                          type="button"
                          onClick={() => void handleResolve(approval.id, "approved")}
                          disabled={isBusy}
                        >
                          {isBusy ? "Working..." : "Approve"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <div className="section-divider" />

          <section className="settings-section">
            <div className="settings-section-header">
              <div>
                <h3>Resolved</h3>
                <p className="muted">Completed approval decisions stay visible for later review.</p>
              </div>
              <span className="run-badge run-badge--trigger">{resolvedApprovals.length} resolved</span>
            </div>

            {resolvedApprovals.length === 0 ? (
              <p className="muted">No resolved approvals yet.</p>
            ) : (
              <div className="run-list">
                {resolvedApprovals.map((approval) => (
                  <article className="run-card" key={approval.id}>
                    <div className="run-card-header">
                      <div className="run-badge-row">
                        <span className="run-badge run-badge--trigger">{formatLabel(approval.action_type)}</span>
                        <span className={statusBadgeClass(approval.status)}>{formatLabel(approval.status)}</span>
                      </div>
                      <time
                        className="activity-time"
                        dateTime={approval.resolved_at || approval.requested_at}
                        title={formatDateTime(approval.resolved_at || approval.requested_at)}
                      >
                        {formatRelativeTime(approval.resolved_at || approval.requested_at)}
                      </time>
                    </div>

                    <p className="run-summary">
                      {approval.payload_summary || "No payload summary was provided for this approval request."}
                    </p>

                    <div className="run-meta">
                      <span>Requested {formatRelativeTime(approval.requested_at)}</span>
                      {approval.resolved_at ? <span>Resolved {formatRelativeTime(approval.resolved_at)}</span> : null}
                      {approval.run_id ? <span>Run {approval.run_id}</span> : null}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {nextCursor ? (
        <div className="load-more-row">
          <button className="secondary-button" type="button" onClick={handleLoadMore} disabled={loadingMore}>
            {loadingMore ? "Loading..." : "Load more"}
          </button>
        </div>
      ) : null}

      {statusMessage ? <p className="settings-feedback">{statusMessage}</p> : null}
      {error ? <p className="status">{error}</p> : null}
    </ShellCard>
  );
}
