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

export const WORKSPACE_TABS = [
  "work",
  "files",
  "activity",
  "integrations",
  "approvals",
  "secrets",
  "settings",
] as const;

export type WorkspaceTab = (typeof WORKSPACE_TABS)[number];

export const APPROVAL_STATUSES = ["pending", "approved", "denied"] as const;

export type ApprovalStatus = (typeof APPROVAL_STATUSES)[number];

export type Approval = {
  id: string;
  claw_id: string;
  run_id: string | null;
  action_type: string;
  payload_summary: string | null;
  status: ApprovalStatus;
  requested_at: string;
  resolved_at: string | null;
  created_at: string;
};

export const SECRET_STATUSES = ["active", "revoked"] as const;

export type SecretStatus = (typeof SECRET_STATUSES)[number];

export type Secret = {
  id: string;
  claw_id: string;
  provider: string;
  label: string;
  status: SecretStatus;
  last_rotated_at: string | null;
  restart_required: boolean;
  created_at: string;
};

export interface BillingAccount {
  id: string;
  user_id: string;
  provider: string;
  plan: string;
  status: string;
  stripe_customer_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
  updated_at: string;
}

export interface BillingSummary {
  provider: string;
  plan: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
}

export interface UsageSummary {
  current_period: {
    runs: number;
    tokens: number;
    estimated_cost: number;
  };
}

export interface CheckoutRequest {
  plan: "starter";
}

export interface CheckoutResponse {
  checkout_url: string;
}
