"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime, truncateText } from "@/lib/time";

type RunListItem = {
  id: string;
  claw_id: string;
  trigger_type: string;
  status: string;
  input_summary: string | null;
  approval_state: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
};

type RunDetail = RunListItem & {
  token_usage: number | null;
  cost_estimate: number | string | null;
  updated_at: string;
};

type RunsResponse = {
  items: RunListItem[];
  next_cursor: string | null;
};

type CreatedRun = {
  id: string;
};

function formatLabel(value: string | null | undefined): string {
  if (!value) {
    return "Pending";
  }

  return value.replace(/_/g, " ");
}

function formatCost(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Pending";
  }

  const amount = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(amount)) {
    return String(value);
  }

  return `$${amount.toFixed(4)}`;
}

function statusBadgeClass(status: string): string {
  return `run-badge run-badge--status-${status.replace(/_/g, "-")}`;
}

export default function WorkspaceWorkPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const [inputValue, setInputValue] = useState("");
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [runDetails, setRunDetails] = useState<Record<string, RunDetail>>({});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchRunsPage = useCallback(
    async (cursor: string | null) => {
      const params = new URLSearchParams({ limit: "20" });
      if (cursor) {
        params.set("cursor", cursor);
      }

      return apiFetch<RunsResponse>(`/api/claws/${clawId}/runs?${params.toString()}`);
    },
    [clawId],
  );

  const loadRunDetail = useCallback(async (runId: string) => {
    try {
      setDetailLoadingId(runId);
      setError(null);
      const detail = await apiFetch<RunDetail>(`/api/runs/${runId}`);
      setRunDetails((current) => ({ ...current, [runId]: detail }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run detail");
    } finally {
      setDetailLoadingId((current) => (current === runId ? null : current));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialRuns() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchRunsPage(null);
        if (cancelled) {
          return;
        }

        setRuns(data.items);
        setNextCursor(data.next_cursor);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load runs");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialRuns();

    return () => {
      cancelled = true;
    };
  }, [fetchRunsPage]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const nextInput = inputValue.trim();
    if (!nextInput) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const created = await apiFetch<CreatedRun>(`/api/claws/${clawId}/runs`, {
        method: "POST",
        body: JSON.stringify({ input: nextInput }),
      });

      const refreshed = await fetchRunsPage(null);
      setInputValue("");
      setRuns(refreshed.items);
      setNextCursor(refreshed.next_cursor);
      setExpandedRunId(created.id);
      void loadRunDetail(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create run");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLoadMore = async () => {
    if (!nextCursor) {
      return;
    }

    try {
      setLoadingMore(true);
      setError(null);
      const data = await fetchRunsPage(nextCursor);
      setRuns((current) => [...current, ...data.items]);
      setNextCursor(data.next_cursor);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more runs");
    } finally {
      setLoadingMore(false);
    }
  };

  const handleToggleRun = async (runId: string) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }

    setExpandedRunId(runId);
    if (!runDetails[runId]) {
      await loadRunDetail(runId);
    }
  };

  return (
    <ShellCard title="Work" description="Queue manual runs and inspect recent execution history.">
      <form className="run-form" onSubmit={handleSubmit}>
        <label className="run-form-label" htmlFor="manual-run-input">
          Manual run input
        </label>
        <textarea
          id="manual-run-input"
          className="run-input"
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="Review open pull requests and summarize blockers."
        />
        <div className="run-form-footer">
          <p className="muted">New runs are queued immediately and logged in the activity feed.</p>
          <button className="editor-save" type="submit" disabled={submitting || !inputValue.trim()}>
            {submitting ? "Queueing..." : "Run"}
          </button>
        </div>
      </form>

      <div className="section-divider" />

      {loading ? (
        <p className="muted">Loading runs...</p>
      ) : runs.length === 0 ? (
        <p className="muted">No runs yet. Submit a manual run to populate this queue.</p>
      ) : (
        <div className="run-list">
          {runs.map((run) => {
            const detail = runDetails[run.id];
            const isExpanded = expandedRunId === run.id;

            return (
              <article className={`run-card ${isExpanded ? "run-card--expanded" : ""}`} key={run.id}>
                <button className="run-card-toggle" type="button" onClick={() => void handleToggleRun(run.id)}>
                  <div className="run-card-header">
                    <div className="run-badge-row">
                      <span className="run-badge run-badge--trigger">{formatLabel(run.trigger_type)}</span>
                      <span className={statusBadgeClass(run.status)}>{formatLabel(run.status)}</span>
                      {run.approval_state ? (
                        <span className="run-badge run-badge--approval">{formatLabel(run.approval_state)}</span>
                      ) : null}
                    </div>
                    <span className="run-card-indicator">{isExpanded ? "Hide" : "Detail"}</span>
                  </div>

                  <p className="run-summary">{truncateText(run.input_summary || "No input summary available.", 160)}</p>

                  <div className="run-meta">
                    <span>Queued {formatRelativeTime(run.created_at)}</span>
                    <span>{formatDateTime(run.created_at)}</span>
                    {run.started_at ? <span>Started {formatRelativeTime(run.started_at)}</span> : null}
                    {run.ended_at ? <span>Ended {formatRelativeTime(run.ended_at)}</span> : null}
                  </div>
                </button>

                {isExpanded ? (
                  <div className="run-detail">
                    {detailLoadingId === run.id && !detail ? (
                      <p className="muted">Loading run detail...</p>
                    ) : (
                      <div className="run-detail-grid">
                        <div className="run-detail-item">
                          <span className="muted">Run ID</span>
                          <code>{run.id}</code>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Input</span>
                          <span>{detail?.input_summary || run.input_summary || "Pending"}</span>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Approval</span>
                          <span>{formatLabel(detail?.approval_state || run.approval_state)}</span>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Started</span>
                          <span>{formatDateTime(detail?.started_at || run.started_at)}</span>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Ended</span>
                          <span>{formatDateTime(detail?.ended_at || run.ended_at)}</span>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Token usage</span>
                          <span>{detail?.token_usage?.toLocaleString() ?? "Pending"}</span>
                        </div>
                        <div className="run-detail-item">
                          <span className="muted">Cost estimate</span>
                          <span>{formatCost(detail?.cost_estimate)}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      )}

      {nextCursor ? (
        <div className="load-more-row">
          <button className="secondary-button" type="button" onClick={handleLoadMore} disabled={loadingMore}>
            {loadingMore ? "Loading..." : "Load more"}
          </button>
        </div>
      ) : null}

      {error ? <p className="status">{error}</p> : null}
    </ShellCard>
  );
}
