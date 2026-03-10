import type {
  Approval,
  ApprovalStatus,
  BillingSummary,
  CheckoutResponse,
  Secret,
  UsageSummary,
} from "@launchclaw/types";
import { createClient } from "@/lib/supabase/client";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

export type ApprovalListResponse = {
  items: Approval[];
  next_cursor: string | null;
};

export type ApprovalListParams = {
  limit?: number;
  cursor?: string | null;
  status?: ApprovalStatus;
};

export type SecretListResponse = {
  items: Secret[];
};

export type UpsertSecretPayload = {
  provider: string;
  label: string;
  value: string;
};

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function buildQueryString(params: Record<string, string | number | null | undefined>): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }

    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Not authenticated");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message =
      body?.error?.message ||
      body?.detail?.message ||
      body?.detail ||
      res.statusText;
    const code = body?.error?.code || body?.detail?.code;
    throw new ApiError(message, res.status, code);
  }

  return res.json();
}

export function listApprovals(clawId: string, params: ApprovalListParams = {}): Promise<ApprovalListResponse> {
  return apiFetch<ApprovalListResponse>(
    `/api/claws/${clawId}/approvals${buildQueryString({
      limit: params.limit ?? 20,
      cursor: params.cursor,
      status: params.status,
    })}`,
  );
}

export function getApproval(approvalId: string): Promise<Approval> {
  return apiFetch<Approval>(`/api/approvals/${approvalId}`);
}

export function approveApproval(approvalId: string): Promise<Approval> {
  return apiFetch<Approval>(`/api/approvals/${approvalId}/approve`, { method: "POST" });
}

export function denyApproval(approvalId: string): Promise<Approval> {
  return apiFetch<Approval>(`/api/approvals/${approvalId}/deny`, { method: "POST" });
}

export function listSecrets(clawId: string): Promise<SecretListResponse> {
  return apiFetch<SecretListResponse>(`/api/claws/${clawId}/secrets`);
}

export function upsertSecret(clawId: string, payload: UpsertSecretPayload): Promise<Secret> {
  return apiFetch<Secret>(`/api/claws/${clawId}/secrets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function revokeSecret(clawId: string, secretId: string): Promise<Secret> {
  return apiFetch<Secret>(`/api/claws/${clawId}/secrets/${secretId}`, { method: "DELETE" });
}

export function getBillingSummary(): Promise<BillingSummary> {
  return apiFetch<BillingSummary>("/api/billing/me");
}

export function createCheckoutSession(plan: "starter"): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>("/api/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export function getUsageSummary(): Promise<UsageSummary> {
  return apiFetch<UsageSummary>("/api/usage/me");
}
