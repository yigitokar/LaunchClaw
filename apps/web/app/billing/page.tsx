"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { BillingSummary, UsageSummary } from "@launchclaw/types";
import { ShellCard } from "@launchclaw/ui";
import { ApiError, createCheckoutSession, getBillingSummary, getUsageSummary, syncCheckoutSession } from "@/lib/api";
import { formatDateTime } from "@/lib/time";

function formatCost(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

function formatStatus(status: string): string {
  return status.replace(/_/g, " ");
}

function statusBadgeClass(status: string): string {
  return `run-badge run-badge--status-${status.replace(/_/g, "-")}`;
}

export default function BillingPage() {
  const searchParams = useSearchParams();
  const checkoutState = searchParams.get("checkout");
  const checkoutSessionId = searchParams.get("session_id");
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [billingMissing, setBillingMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const shouldSyncCheckout = checkoutState === "success" && Boolean(checkoutSessionId);

    async function loadBillingState() {
      try {
        setLoading(true);
        setError(null);
        setNotice(checkoutState === "cancelled" ? "Stripe checkout was cancelled before completion." : null);

        const billingRequest = shouldSyncCheckout && checkoutSessionId
          ? syncCheckoutSession(checkoutSessionId)
          : getBillingSummary();

        const [billingResult, usageResult] = await Promise.allSettled([billingRequest, getUsageSummary()]);
        if (cancelled) {
          return;
        }

        if (billingResult.status === "fulfilled") {
          setBilling(billingResult.value);
          setBillingMissing(false);
          if (shouldSyncCheckout) {
            setNotice("Subscription synced from your completed Stripe checkout.");
          }
        } else if (billingResult.reason instanceof ApiError && billingResult.reason.status === 404) {
          setBilling(null);
          setBillingMissing(true);
        } else {
          setError(
            billingResult.status === "rejected" && billingResult.reason instanceof Error
              ? billingResult.reason.message
              : "Failed to load billing",
          );
        }

        if (usageResult.status === "fulfilled") {
          setUsage(usageResult.value);
        } else {
          setError((current) =>
            current ||
            (usageResult.reason instanceof Error ? usageResult.reason.message : "Failed to load usage summary"),
          );
        }

        if (checkoutState === "success" && !checkoutSessionId) {
          setError((current) => current || "Stripe redirect did not include a checkout session ID.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadBillingState();

    return () => {
      cancelled = true;
    };
  }, [checkoutSessionId, checkoutState]);

  const handleBillingAction = async () => {
    try {
      setUpgrading(true);
      setError(null);
      const { checkout_url } = await createCheckoutSession("starter");
      window.location.assign(checkout_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start checkout");
      setUpgrading(false);
    }
  };

  const actionLabel = billing?.can_manage_subscription ? "Manage subscription" : "Upgrade";

  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">Billing</span>
        <h1>Plan, status, and current-period usage.</h1>
        <p>Review your active subscription state and open a Stripe checkout session when you need to upgrade.</p>
        <nav className="nav-row">
          <Link className="nav-link" href="/app">
            Back to console
          </Link>
        </nav>
      </section>

      <section className="grid">
        <ShellCard title="Current plan" description="Subscription provider, plan state, and billing window.">
          {loading ? (
            <p className="muted">Loading billing...</p>
          ) : billing ? (
            <div className="table-like">
              <div className="table-row">
                <strong>Provider</strong>
                <span>{billing.provider}</span>
              </div>
              <div className="table-row">
                <strong>Plan</strong>
                <span>{billing.plan}</span>
              </div>
              <div className="table-row">
                <strong>Status</strong>
                <span className={statusBadgeClass(billing.status)}>{formatStatus(billing.status)}</span>
              </div>
              <div className="table-row">
                <strong>Current period start</strong>
                <span>{formatDateTime(billing.current_period_start)}</span>
              </div>
              <div className="table-row">
                <strong>Current period end</strong>
                <span>{formatDateTime(billing.current_period_end)}</span>
              </div>
            </div>
          ) : (
            <p className="muted">
              {billingMissing ? "No billing account exists yet. Start checkout to create one." : "Billing data is unavailable."}
            </p>
          )}

          <div className="nav-row" style={{ marginTop: "0.75rem", paddingBottom: 0 }}>
            <button className="editor-save" type="button" onClick={handleBillingAction} disabled={upgrading}>
              {upgrading ? "Redirecting..." : actionLabel}
            </button>
          </div>
        </ShellCard>

        <ShellCard title="Current usage" description="Runs, token volume, and estimated cost for the active billing period.">
          {loading && !usage ? (
            <p className="muted">Loading usage...</p>
          ) : usage ? (
            <div className="table-like">
              <div className="table-row">
                <strong>Runs</strong>
                <span>{usage.current_period.runs.toLocaleString()}</span>
              </div>
              <div className="table-row">
                <strong>Tokens</strong>
                <span>{usage.current_period.tokens.toLocaleString()}</span>
              </div>
              <div className="table-row">
                <strong>Estimated cost</strong>
                <span>{formatCost(usage.current_period.estimated_cost)}</span>
              </div>
            </div>
          ) : (
            <p className="muted">Usage data is unavailable.</p>
          )}
        </ShellCard>
      </section>

      {notice ? (
        <ShellCard title="Status" description="Recent billing state from Stripe.">
          <p className="muted">{notice}</p>
        </ShellCard>
      ) : null}

      {error ? (
        <ShellCard title="Error" description="One or more billing calls failed.">
          <p className="status">{error}</p>
        </ShellCard>
      ) : null}
    </main>
  );
}
