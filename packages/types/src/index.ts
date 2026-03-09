export const CLAW_STATUSES = [
  "creating",
  "provisioning",
  "healthy",
  "degraded",
  "paused",
  "restarting",
  "failed",
  "deleted",
] as const;

export type ClawStatus = (typeof CLAW_STATUSES)[number];

export const WORKSPACE_TABS = ["work", "files", "activity", "integrations", "settings"] as const;

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];
