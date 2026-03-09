"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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

type ScheduleFormState = {
  name: string;
  schedule_expr: string;
  enabled: boolean;
};

const EMPTY_SCHEDULE_FORM: ScheduleFormState = {
  name: "",
  schedule_expr: "",
  enabled: true,
};

function normalizeClawStatus(status: string): string {
  switch (status) {
    case "healthy":
      return "running";
    case "degraded":
    case "failed":
      return "error";
    default:
      return status;
  }
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function sortSchedules(items: Schedule[]): Schedule[] {
  return [...items].sort((left, right) => {
    if (left.enabled !== right.enabled) {
      return left.enabled ? -1 : 1;
    }

    if (left.next_run_at && right.next_run_at) {
      return new Date(left.next_run_at).getTime() - new Date(right.next_run_at).getTime();
    }

    if (left.next_run_at) {
      return -1;
    }

    if (right.next_run_at) {
      return 1;
    }

    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
  });
}

export default function WorkspaceSettingsPage() {
  const { id: clawId } = useParams<{ id: string }>();
  const [claw, setClaw] = useState<ClawDetail | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [nameValue, setNameValue] = useState("");
  const [newSchedule, setNewSchedule] = useState<ScheduleFormState>(EMPTY_SCHEDULE_FORM);
  const [editScheduleId, setEditScheduleId] = useState<string | null>(null);
  const [editSchedule, setEditSchedule] = useState<ScheduleFormState>(EMPTY_SCHEDULE_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [creatingSchedule, setCreatingSchedule] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleActionId, setScheduleActionId] = useState<string | null>(null);
  const [lifecycleAction, setLifecycleAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

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
      setSchedules(sortSchedules(scheduleData.items));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, [clawId]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

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

  const handleLifecycleAction = async (action: "pause" | "resume" | "restart" | "recover") => {
    if (action === "restart") {
      const confirmed = window.confirm("Restart this Claw now? Active work may be interrupted.");
      if (!confirmed) {
        return;
      }
    }

    try {
      setLifecycleAction(action);
      setError(null);
      const updated = await apiFetch<{ id: string; status: string }>(`/api/claws/${clawId}/${action}`, {
        method: "POST",
      });

      setClaw((current) => (current ? { ...current, status: updated.status } : current));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update lifecycle state");
    } finally {
      setLifecycleAction(null);
    }
  };

  const upsertSchedule = (updatedSchedule: Schedule) => {
    setSchedules((current) =>
      sortSchedules([
        updatedSchedule,
        ...current.filter((schedule) => schedule.id !== updatedSchedule.id),
      ]),
    );
  };

  const handleCreateSchedule = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newSchedule.name.trim() || !newSchedule.schedule_expr.trim()) {
      return;
    }

    try {
      setCreatingSchedule(true);
      setError(null);
      const created = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules`, {
        method: "POST",
        body: JSON.stringify({
          name: newSchedule.name.trim(),
          schedule_expr: newSchedule.schedule_expr.trim(),
          enabled: newSchedule.enabled,
        }),
      });
      upsertSchedule(created);
      setNewSchedule(EMPTY_SCHEDULE_FORM);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create schedule");
    } finally {
      setCreatingSchedule(false);
    }
  };

  const startEditingSchedule = (schedule: Schedule) => {
    setEditScheduleId(schedule.id);
    setEditSchedule({
      name: schedule.name,
      schedule_expr: schedule.schedule_expr,
      enabled: schedule.enabled,
    });
  };

  const handleSaveSchedule = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editScheduleId || !editSchedule.name.trim() || !editSchedule.schedule_expr.trim()) {
      return;
    }

    try {
      setSavingSchedule(true);
      setError(null);
      const updated = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules/${editScheduleId}`, {
        method: "PUT",
        body: JSON.stringify({
          name: editSchedule.name.trim(),
          schedule_expr: editSchedule.schedule_expr.trim(),
          enabled: editSchedule.enabled,
        }),
      });
      upsertSchedule(updated);
      setEditScheduleId(null);
      setEditSchedule(EMPTY_SCHEDULE_FORM);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update schedule");
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleToggleSchedule = async (schedule: Schedule) => {
    try {
      setScheduleActionId(schedule.id);
      setError(null);
      const updated = await apiFetch<Schedule>(`/api/claws/${clawId}/schedules/${schedule.id}/toggle`, {
        method: "POST",
        body: JSON.stringify({ enabled: !schedule.enabled }),
      });
      upsertSchedule(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to toggle schedule");
    } finally {
      setScheduleActionId(null);
    }
  };

  const handleDeleteSchedule = async (schedule: Schedule) => {
    const confirmed = window.confirm(`Delete the schedule "${schedule.name}"?`);
    if (!confirmed) {
      return;
    }

    try {
      setScheduleActionId(schedule.id);
      setError(null);
      await apiFetch<{ id: string; deleted: boolean }>(`/api/claws/${clawId}/schedules/${schedule.id}`, {
        method: "DELETE",
      });
      setSchedules((current) => current.filter((item) => item.id !== schedule.id));
      if (editScheduleId === schedule.id) {
        setEditScheduleId(null);
        setEditSchedule(EMPTY_SCHEDULE_FORM);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete schedule");
    } finally {
      setScheduleActionId(null);
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
  const normalizedStatus = normalizeClawStatus(claw.status);
  const canPause = normalizedStatus === "running";
  const canResume = normalizedStatus === "paused";
  const canRestart = normalizedStatus === "running" || normalizedStatus === "error";
  const canRecover = normalizedStatus === "error";

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
          <span className="status">{formatLabel(claw.status)}</span>
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
          <div className="settings-section-copy">
            <h2 className="settings-section-title">Lifecycle</h2>
            <p className="muted">Pause, resume, restart, or recover this Claw based on its current runtime state.</p>
          </div>
          <span className={`settings-status-badge settings-status-badge--${normalizedStatus}`}>
            {formatLabel(claw.status)}
          </span>
        </div>

        <div className="settings-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={() => void handleLifecycleAction("pause")}
            disabled={lifecycleAction !== null || !canPause}
          >
            {lifecycleAction === "pause" ? "Pausing..." : "Pause"}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void handleLifecycleAction("resume")}
            disabled={lifecycleAction !== null || !canResume}
          >
            {lifecycleAction === "resume" ? "Resuming..." : "Resume"}
          </button>
          <button
            className="secondary-button secondary-button--danger"
            type="button"
            onClick={() => void handleLifecycleAction("restart")}
            disabled={lifecycleAction !== null || !canRestart}
          >
            {lifecycleAction === "restart" ? "Restarting..." : "Restart"}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void handleLifecycleAction("recover")}
            disabled={lifecycleAction !== null || !canRecover}
          >
            {lifecycleAction === "recover" ? "Recovering..." : "Recover"}
          </button>
        </div>
      </section>

      <div className="section-divider" />

      <section className="settings-section">
        <div className="settings-section-copy">
          <h2 className="settings-section-title">Schedules</h2>
          <p className="muted">Manage recurring runs with UTC cron expressions.</p>
        </div>

        <form className="schedule-form" onSubmit={handleCreateSchedule}>
          <div className="schedule-form-grid">
            <label className="schedule-form-field">
              <span>Name</span>
              <input
                className="settings-input"
                type="text"
                value={newSchedule.name}
                onChange={(event) => setNewSchedule((current) => ({ ...current, name: event.target.value }))}
                maxLength={120}
                placeholder="Morning review"
              />
            </label>

            <label className="schedule-form-field">
              <span>Cron (UTC)</span>
              <input
                className="settings-input settings-input--mono"
                type="text"
                value={newSchedule.schedule_expr}
                onChange={(event) =>
                  setNewSchedule((current) => ({ ...current, schedule_expr: event.target.value }))
                }
                maxLength={120}
                placeholder="0 9 * * 1-5"
              />
            </label>

            <label className="schedule-toggle schedule-toggle--field">
              <input
                type="checkbox"
                checked={newSchedule.enabled}
                onChange={(event) => setNewSchedule((current) => ({ ...current, enabled: event.target.checked }))}
              />
              <span>Enabled</span>
            </label>
          </div>

          <div className="schedule-form-footer">
            <p className="muted">
              Use a standard 5-field cron expression like <code>0 9 * * 1-5</code>.
            </p>
            <button
              className="editor-save"
              type="submit"
              disabled={creatingSchedule || !newSchedule.name.trim() || !newSchedule.schedule_expr.trim()}
            >
              {creatingSchedule ? "Creating..." : "Create schedule"}
            </button>
          </div>
        </form>

        {schedules.length === 0 ? (
          <p className="muted">No schedules yet. Add one above to start recurring runs.</p>
        ) : (
          <div className="schedule-list">
            {schedules.map((schedule) => {
              const isEditing = editScheduleId === schedule.id;
              const isBusy = scheduleActionId === schedule.id || (savingSchedule && isEditing);

              return (
                <article className="schedule-card" key={schedule.id}>
                  {isEditing ? (
                    <form className="schedule-form schedule-form--inline" onSubmit={handleSaveSchedule}>
                      <div className="schedule-form-grid">
                        <label className="schedule-form-field">
                          <span>Name</span>
                          <input
                            className="settings-input"
                            type="text"
                            value={editSchedule.name}
                            onChange={(event) =>
                              setEditSchedule((current) => ({ ...current, name: event.target.value }))
                            }
                            maxLength={120}
                          />
                        </label>

                        <label className="schedule-form-field">
                          <span>Cron (UTC)</span>
                          <input
                            className="settings-input settings-input--mono"
                            type="text"
                            value={editSchedule.schedule_expr}
                            onChange={(event) =>
                              setEditSchedule((current) => ({ ...current, schedule_expr: event.target.value }))
                            }
                            maxLength={120}
                          />
                        </label>

                        <label className="schedule-toggle schedule-toggle--field">
                          <input
                            type="checkbox"
                            checked={editSchedule.enabled}
                            onChange={(event) =>
                              setEditSchedule((current) => ({ ...current, enabled: event.target.checked }))
                            }
                          />
                          <span>Enabled</span>
                        </label>
                      </div>

                      <div className="schedule-form-footer">
                        <p className="muted">Next run will be recalculated when you save.</p>
                        <div className="settings-actions">
                          <button
                            className="editor-save"
                            type="submit"
                            disabled={savingSchedule || !editSchedule.name.trim() || !editSchedule.schedule_expr.trim()}
                          >
                            {savingSchedule ? "Saving..." : "Save changes"}
                          </button>
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => setEditScheduleId(null)}
                            disabled={savingSchedule}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    </form>
                  ) : (
                    <>
                      <div className="schedule-card-header">
                        <div className="schedule-card-copy">
                          <div className="run-badge-row">
                            <span className={`settings-inline-badge ${schedule.enabled ? "settings-inline-badge--on" : ""}`}>
                              {schedule.enabled ? "Enabled" : "Disabled"}
                            </span>
                            <code>{schedule.schedule_expr}</code>
                          </div>
                          <h3 className="schedule-card-title">{schedule.name}</h3>
                        </div>

                        <label className="schedule-toggle">
                          <input
                            type="checkbox"
                            checked={schedule.enabled}
                            onChange={() => void handleToggleSchedule(schedule)}
                            disabled={isBusy}
                          />
                          <span>{schedule.enabled ? "On" : "Off"}</span>
                        </label>
                      </div>

                      <div className="schedule-meta">
                        <span>
                          Next run{" "}
                          {schedule.enabled && schedule.next_run_at
                            ? `${formatDateTime(schedule.next_run_at)} (${formatRelativeTime(schedule.next_run_at)})`
                            : "Disabled"}
                        </span>
                        <span>
                          Last run{" "}
                          {schedule.last_run_at
                            ? `${formatDateTime(schedule.last_run_at)} (${formatRelativeTime(schedule.last_run_at)})`
                            : "Pending"}
                        </span>
                      </div>

                      <div className="schedule-actions">
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => startEditingSchedule(schedule)}
                          disabled={isBusy}
                        >
                          Edit
                        </button>
                        <button
                          className="secondary-button secondary-button--danger"
                          type="button"
                          onClick={() => void handleDeleteSchedule(schedule)}
                          disabled={isBusy}
                        >
                          {scheduleActionId === schedule.id ? "Working..." : "Delete"}
                        </button>
                      </div>
                    </>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      {error && <p className="status">{error}</p>}
    </ShellCard>
  );
}
