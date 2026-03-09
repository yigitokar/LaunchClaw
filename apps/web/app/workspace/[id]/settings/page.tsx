"use client";

import { useParams } from "next/navigation";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/time";

type ClawDetail = {
  id: string;
  name: string;
  status: string;
  model_access_mode: string;
  created_at: string;
  updated_at: string;
};

type Schedule = {
  id: string;
  claw_id: string;
  name: string;
  schedule_expr: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
};

type ScheduleResponse = {
  items: Schedule[];
};

type ScheduleDraft = {
  name: string;
  schedule_expr: string;
};

type LifecycleActionKey = "pause" | "resume" | "restart" | "recover";

const LIFECYCLE_ACTIONS: Record<
  string,
  Array<{ action: LifecycleActionKey; label: string; message: string; tone: "primary" | "secondary" }>
> = {
  healthy: [
    { action: "pause", label: "Pause", message: "Claw paused", tone: "secondary" },
    { action: "restart", label: "Restart", message: "Restart requested", tone: "primary" },
  ],
  degraded: [
    { action: "pause", label: "Pause", message: "Claw paused", tone: "secondary" },
    { action: "restart", label: "Restart", message: "Restart requested", tone: "primary" },
  ],
  paused: [{ action: "resume", label: "Resume", message: "Resume requested", tone: "primary" }],
  failed: [{ action: "recover", label: "Recover", message: "Recovery requested", tone: "primary" }],
};

const EMPTY_SCHEDULE_FORM = {
  name: "",
  schedule_expr: "0 9 * * 1-5",
  enabled: true,
};

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function buildScheduleDrafts(items: Schedule[]): Record<string, ScheduleDraft> {
  return Object.fromEntries(items.map((item) => [item.id, { name: item.name, schedule_expr: item.schedule_expr }]));
}

export default function WorkspaceSettingsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const feedbackTimeoutRef = useRef<number | null>(null);

  const [claw, setClaw] = useState<ClawDetail | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [scheduleDrafts, setScheduleDrafts] = useState<Record<string, ScheduleDraft>>({});
  const [nameValue, setNameValue] = useState("");
  const [newSchedule, setNewSchedule] = useState(EMPTY_SCHEDULE_FORM);
  const [loading, setLoading] = useState(true);
  const [savingName, setSavingName] = useState(false);
  const [lifecycleAction, setLifecycleAction] = useState<LifecycleActionKey | null>(null);
  const [creatingSchedule, setCreatingSchedule] = useState(false);
  const [updatingScheduleId, setUpdatingScheduleId] = useState<string | null>(null);
  const [togglingScheduleId, setTogglingScheduleId] = useState<string | null>(null);
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

  const syncSchedule = useCallback((updated: Schedule) => {
    setSchedules((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setScheduleDrafts((current) => ({
      ...current,
      [updated.id]: { name: updated.name, schedule_expr: updated.schedule_expr },
    }));
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [clawData, scheduleData] = await Promise.all([
        apiFetch<ClawDetail>(`/api/claws/${clawId}`),
        apiFetch<ScheduleResponse>(`/api/claws/${clawId}/schedules`),
      ]);

      setClaw(clawData);
      setNameValue(clawData.name);
      setSchedules(scheduleData.items);
      setScheduleDrafts(buildScheduleDrafts(scheduleData.items));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, [clawId]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    return () => {
      if (feedbackTimeoutRef.current !== null) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, []);

  const handleSaveName = async () => {
    const nextName = nameValue.trim();
    if (!nextName) {
      return;
    }

    try {
      setSavingName(true);
      setError(null);
      const updated = await apiFetch<ClawDetail>(`/api/claws/${clawId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: nextName }),
      });
      setClaw(updated);
      setNameValue(updated.name);
      showStatusMessage("Name saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save name");
    } finally {
      setSavingName(false);
    }
  };

  const handleLifecycleAction = async (action: LifecycleActionKey, message: string) => {
    try {
      setLifecycleAction(action);
      setError(null);
      const updated = await apiFetch<{ id: string; status: string }>(`/api/claws/${clawId}/${action}`, {
        method: "POST",
      });
      setClaw((current) => (current ? { ...current, status: updated.status } : current));
      showStatusMessage(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update lifecycle");
    } finally {
      setLifecycleAction(null);
    }
  };

  const handleCreateSchedule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const payload = {
      name: newSchedule.name.trim(),
      schedule_expr: newSchedule.schedule_expr.trim(),
      enabled: newSchedule.enabled,
    };
    if (!payload.name || !payload.schedule_expr) {
      return;
    }

    try {
      setCreatingSchedule(true);
      setError(null);
      const created = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setSchedules((current) => [created, ...current]);
      setScheduleDrafts((current) => ({
        ...current,
        [created.id]: { name: created.name, schedule_expr: created.schedule_expr },
      }));
      setNewSchedule(EMPTY_SCHEDULE_FORM);
      showStatusMessage("Schedule added");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create schedule");
    } finally {
      setCreatingSchedule(false);
    }
  };

  const handleUpdateSchedule = async (schedule: Schedule) => {
    const draft = scheduleDrafts[schedule.id] ?? { name: schedule.name, schedule_expr: schedule.schedule_expr };
    const payload = {
      name: draft.name.trim(),
      schedule_expr: draft.schedule_expr.trim(),
      enabled: schedule.enabled,
    };
    if (!payload.name || !payload.schedule_expr) {
      return;
    }

    try {
      setUpdatingScheduleId(schedule.id);
      setError(null);
      const updated = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules/${schedule.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      syncSchedule(updated);
      showStatusMessage("Schedule updated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update schedule");
    } finally {
      setUpdatingScheduleId((current) => (current === schedule.id ? null : current));
    }
  };

  const handleToggleSchedule = async (schedule: Schedule) => {
    try {
      setTogglingScheduleId(schedule.id);
      setError(null);
      const updated = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules/${schedule.id}/toggle`, {
        method: "POST",
        body: JSON.stringify({ enabled: !schedule.enabled }),
      });
      syncSchedule(updated);
      showStatusMessage(updated.enabled ? "Schedule enabled" : "Schedule disabled");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to toggle schedule");
    } finally {
      setTogglingScheduleId((current) => (current === schedule.id ? null : current));
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
        {error ? <p className="status">{error}</p> : null}
      </ShellCard>
    );
  }

  const availableActions = LIFECYCLE_ACTIONS[claw.status] || [];
  const isNameDirty = nameValue.trim() !== claw.name;

  return (
    <ShellCard title="Settings" description="Manage lifecycle actions and scheduled work for this Claw.">
      <div className="settings-stack">
        <div className="table-like">
          <div className="table-row">
            <strong>Name</strong>
            <div className="settings-name-row">
              <input
                className="settings-input"
                type="text"
                value={nameValue}
                onChange={(event) => setNameValue(event.target.value)}
                maxLength={80}
              />
              <button className="editor-save" onClick={handleSaveName} disabled={savingName || !isNameDirty}>
                {savingName ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
          <div className="table-row">
            <strong>Status</strong>
            <span className="file-badge">{formatLabel(claw.status)}</span>
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

        <div className="section-divider" />

        <section className="settings-section">
          <div className="settings-section-header">
            <div>
              <h3>Lifecycle</h3>
              <p className="muted">Available actions depend on the current runtime state.</p>
            </div>
            <span className="run-badge run-badge--trigger">{formatLabel(claw.status)}</span>
          </div>

          {availableActions.length ? (
            <div className="settings-actions">
              {availableActions.map((item) => (
                <button
                  key={item.action}
                  className={item.tone === "primary" ? "editor-save" : "secondary-button"}
                  type="button"
                  onClick={() => handleLifecycleAction(item.action, item.message)}
                  disabled={lifecycleAction !== null}
                >
                  {lifecycleAction === item.action ? `${item.label}...` : item.label}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">No lifecycle actions are available while this Claw is {formatLabel(claw.status)}.</p>
          )}
        </section>

        <div className="section-divider" />

        <section className="settings-section">
          <div className="settings-section-header">
            <div>
              <h3>Schedules</h3>
              <p className="muted">Create cron-based runs, update them inline, and toggle execution on or off.</p>
            </div>
          </div>

          <form className="schedule-form" onSubmit={handleCreateSchedule}>
            <label className="schedule-field">
              <span>Name</span>
              <input
                className="settings-input"
                type="text"
                value={newSchedule.name}
                onChange={(event) => setNewSchedule((current) => ({ ...current, name: event.target.value }))}
                maxLength={120}
                placeholder="Morning PR review"
              />
            </label>

            <label className="schedule-field">
              <span>Cron expression</span>
              <input
                className="settings-input"
                type="text"
                value={newSchedule.schedule_expr}
                onChange={(event) => setNewSchedule((current) => ({ ...current, schedule_expr: event.target.value }))}
                placeholder="0 9 * * 1-5"
              />
            </label>

            <label className="settings-checkbox">
              <input
                type="checkbox"
                checked={newSchedule.enabled}
                onChange={(event) => setNewSchedule((current) => ({ ...current, enabled: event.target.checked }))}
              />
              <span>Enabled on create</span>
            </label>

            <div className="schedule-form-actions">
              <p className="muted">Use standard cron syntax, for example <code>0 9 * * 1-5</code>.</p>
              <button
                className="editor-save"
                type="submit"
                disabled={creatingSchedule || !newSchedule.name.trim() || !newSchedule.schedule_expr.trim()}
              >
                {creatingSchedule ? "Adding..." : "Add Schedule"}
              </button>
            </div>
          </form>

          {schedules.length === 0 ? (
            <p className="muted">No schedules yet. Add one to trigger queued runs automatically.</p>
          ) : (
            <div className="schedule-list">
              {schedules.map((schedule) => {
                const draft = scheduleDrafts[schedule.id] ?? {
                  name: schedule.name,
                  schedule_expr: schedule.schedule_expr,
                };
                const isDraftDirty =
                  draft.name.trim() !== schedule.name || draft.schedule_expr.trim() !== schedule.schedule_expr;

                return (
                  <article className="schedule-card" key={schedule.id}>
                    <div className="schedule-card-header">
                      <div className="schedule-card-title">
                        <strong>{schedule.name}</strong>
                        <span className="file-badge">{schedule.enabled ? "Enabled" : "Disabled"}</span>
                      </div>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => handleToggleSchedule(schedule)}
                        disabled={togglingScheduleId === schedule.id}
                      >
                        {togglingScheduleId === schedule.id
                          ? "Updating..."
                          : schedule.enabled
                            ? "Disable"
                            : "Enable"}
                      </button>
                    </div>

                    <div className="schedule-editor-grid">
                      <label className="schedule-field">
                        <span>Name</span>
                        <input
                          className="settings-input"
                          type="text"
                          value={draft.name}
                          onChange={(event) =>
                            setScheduleDrafts((current) => ({
                              ...current,
                              [schedule.id]: {
                                ...draft,
                                name: event.target.value,
                              },
                            }))
                          }
                          maxLength={120}
                        />
                      </label>

                      <label className="schedule-field">
                        <span>Cron expression</span>
                        <input
                          className="settings-input"
                          type="text"
                          value={draft.schedule_expr}
                          onChange={(event) =>
                            setScheduleDrafts((current) => ({
                              ...current,
                              [schedule.id]: {
                                ...draft,
                                schedule_expr: event.target.value,
                              },
                            }))
                          }
                        />
                      </label>
                    </div>

                    <div className="schedule-meta-grid">
                      <div className="schedule-meta-item">
                        <span>Last run</span>
                        <strong>{formatDateTime(schedule.last_run_at)}</strong>
                      </div>
                      <div className="schedule-meta-item">
                        <span>Next run</span>
                        <strong>{formatDateTime(schedule.next_run_at)}</strong>
                      </div>
                      <div className="schedule-meta-item">
                        <span>Relative next run</span>
                        <strong>{schedule.enabled ? formatRelativeTime(schedule.next_run_at) : "Disabled"}</strong>
                      </div>
                    </div>

                    <div className="schedule-card-footer">
                      <p className="muted">
                        {schedule.enabled
                          ? `Queued automatically when due. Last updated ${formatRelativeTime(schedule.updated_at)}.`
                          : "Disabled schedules stay saved but will not create runs."}
                      </p>
                      <button
                        className="editor-save"
                        type="button"
                        onClick={() => handleUpdateSchedule(schedule)}
                        disabled={updatingScheduleId === schedule.id || !isDraftDirty}
                      >
                        {updatingScheduleId === schedule.id ? "Saving..." : "Save Changes"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {statusMessage ? <p className="settings-feedback">{statusMessage}</p> : null}
        {error ? <p className="status">{error}</p> : null}
      </div>
    </ShellCard>
  );
}
