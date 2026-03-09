"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime, truncateText } from "@/lib/time";

type ActivityEvent = {
  id: string;
  type: string;
  summary: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

type ActivityResponse = {
  items: ActivityEvent[];
  next_cursor: string | null;
};

const EVENT_META: Record<string, { glyph: string; label: string }> = {
  approval_approved: { glyph: "AA", label: "Approval approved" },
  approval_denied: { glyph: "AD", label: "Approval denied" },
  approval_requested: { glyph: "AR", label: "Approval requested" },
  claw_created: { glyph: "CC", label: "Claw created" },
  claw_healthy: { glyph: "CH", label: "Claw healthy" },
  claw_paused: { glyph: "CP", label: "Claw paused" },
  claw_restarted: { glyph: "CR", label: "Claw restarted" },
  integration_connected: { glyph: "IC", label: "Integration connected" },
  integration_degraded: { glyph: "ID", label: "Integration degraded" },
  run_failed: { glyph: "RF", label: "Run failed" },
  run_started: { glyph: "RS", label: "Run started" },
  run_succeeded: { glyph: "RO", label: "Run succeeded" },
  schedule_triggered: { glyph: "ST", label: "Schedule triggered" },
  secret_rotated: { glyph: "SR", label: "Secret rotated" },
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "unknown";
  }

  if (typeof value === "string") {
    return truncateText(value, 44);
  }

  return String(value);
}

export default function WorkspaceActivityPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchActivityPage = useCallback(
    async (cursor: string | null) => {
      const params = new URLSearchParams({ limit: "20" });
      if (cursor) {
        params.set("cursor", cursor);
      }

      return apiFetch<ActivityResponse>(`/api/claws/${clawId}/activity?${params.toString()}`);
    },
    [clawId],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadInitialActivity() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchActivityPage(null);
        if (cancelled) {
          return;
        }

        setEvents(data.items);
        setNextCursor(data.next_cursor);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load activity");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialActivity();

    return () => {
      cancelled = true;
    };
  }, [fetchActivityPage]);

  const handleLoadMore = async () => {
    if (!nextCursor) {
      return;
    }

    try {
      setLoadingMore(true);
      setError(null);
      const data = await fetchActivityPage(nextCursor);
      setEvents((current) => [...current, ...data.items]);
      setNextCursor(data.next_cursor);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more activity");
    } finally {
      setLoadingMore(false);
    }
  };

  return (
    <ShellCard
      title="Activity"
      description="Track lifecycle changes, manual work, integrations, and other workspace events."
    >
      {loading ? (
        <p className="muted">Loading activity...</p>
      ) : events.length === 0 ? (
        <p className="muted">No activity yet. Run work or update your Claw to start the feed.</p>
      ) : (
        <div className="activity-feed">
          {events.map((event) => {
            const meta = EVENT_META[event.type] || { glyph: "EV", label: formatLabel(event.type) };
            const metadataEntries = Object.entries(event.metadata || {}).slice(0, 3);

            return (
              <article className="activity-card" key={event.id}>
                <div className="activity-icon" aria-hidden="true">
                  {meta.glyph}
                </div>
                <div className="activity-body">
                  <div className="activity-header">
                    <div className="activity-copy">
                      <span className="run-badge run-badge--trigger">{meta.label}</span>
                      <p className="activity-summary">{event.summary}</p>
                    </div>
                    <time className="activity-time" dateTime={event.created_at} title={formatDateTime(event.created_at)}>
                      {formatRelativeTime(event.created_at)}
                    </time>
                  </div>

                  {metadataEntries.length ? (
                    <div className="activity-meta-row">
                      {metadataEntries.map(([key, value]) => (
                        <span className="activity-meta-chip" key={`${event.id}-${key}`}>
                          {formatLabel(key)}: {formatMetadataValue(value)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
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
