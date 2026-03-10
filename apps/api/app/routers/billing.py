from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal
from urllib.parse import quote_plus

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.services.scheduler import parse_timestamp, utc_now

router = APIRouter(tags=["billing"])

BILLING_SUMMARY_FIELDS = "provider, plan, status, stripe_customer_id, current_period_start, current_period_end"
COST_PER_1K_TOKENS = Decimal("0.0896")
SUPPORTED_PLANS = {"starter"}
MANAGEABLE_BILLING_STATUSES = {"active", "trialing", "past_due", "unpaid", "paused"}
SUPPORTED_BILLING_STATUSES = MANAGEABLE_BILLING_STATUSES | {"canceled", "incomplete", "incomplete_expired"}


class CheckoutRequest(BaseModel):
    plan: Literal["starter"]


class CheckoutSyncRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _normalize_billing_status(status: str | None) -> str:
    normalized = (status or "").strip().lower().replace("-", "_")
    if normalized == "cancelled":
        return "canceled"
    return normalized


def _field_value(resource: Any, field: str) -> Any:
    if isinstance(resource, dict):
        return resource.get(field)
    return getattr(resource, field, None)


def _resource_id(resource: Any) -> str | None:
    if isinstance(resource, str):
        return resource
    value = _field_value(resource, "id")
    return str(value) if value else None


def _stripe_timestamp_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        else:
            current = current.astimezone(timezone.utc)
        return current.isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    if isinstance(value, str):
        return parse_timestamp(value).isoformat()
    return None


def _calendar_month_window(reference: datetime) -> tuple[datetime, datetime]:
    start = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _billing_period_for_user(user_id: str) -> tuple[datetime, datetime]:
    result = (
        get_supabase()
        .table("billing_accounts")
        .select("current_period_start, current_period_end")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    account = result.data or {}
    start = account.get("current_period_start")
    end = account.get("current_period_end")
    if isinstance(start, str) and isinstance(end, str):
        return parse_timestamp(start), parse_timestamp(end)
    return _calendar_month_window(utc_now())


def _estimated_cost(tokens: int) -> float:
    amount = (Decimal(tokens) * COST_PER_1K_TOKENS / Decimal(1000)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return float(amount)


def _can_manage_subscription(status: str | None, stripe_customer_id: str | None) -> bool:
    return bool(stripe_customer_id) and _normalize_billing_status(status) in MANAGEABLE_BILLING_STATUSES


def _billing_summary_from_account(account: dict[str, Any]) -> dict[str, Any]:
    status = _normalize_billing_status(account.get("status"))
    stripe_customer_id = account.get("stripe_customer_id")
    return {
        "provider": account["provider"],
        "plan": account["plan"],
        "status": status,
        "current_period_start": account.get("current_period_start"),
        "current_period_end": account.get("current_period_end"),
        "can_manage_subscription": _can_manage_subscription(status, stripe_customer_id),
    }


def _configure_stripe() -> None:
    stripe_secret_key = settings.stripe_secret_key.strip()
    if not stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail=_detail("billing_unavailable", "Stripe billing is not configured"),
        )
    stripe.api_key = stripe_secret_key


def _billing_page_url(**params: str) -> str:
    base_url = f"{settings.frontend_url.rstrip('/')}/billing"
    filtered = {key: value for key, value in params.items() if value}
    if not filtered:
        return base_url
    query = "&".join(
        f"{quote_plus(key)}={quote_plus(value, safe='{}')}"
        for key, value in filtered.items()
    )
    return f"{base_url}?{query}"


def _stripe_price_id_for_plan(plan: str) -> str:
    if plan not in SUPPORTED_PLANS:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", f"Unsupported billing plan '{plan}'"),
        )

    price_id = settings.stripe_price_id_starter.strip()
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=_detail("billing_unavailable", "Stripe pricing is not configured"),
        )
    return price_id


def _retrieve_subscription(subscription_ref: Any) -> Any:
    subscription_id = _resource_id(subscription_ref)
    if not subscription_id:
        raise HTTPException(
            status_code=409,
            detail=_detail("billing_sync_failed", "Checkout session does not reference a subscription"),
        )

    if not isinstance(subscription_ref, str) and _field_value(subscription_ref, "status"):
        return subscription_ref

    try:
        return stripe.Subscription.retrieve(subscription_id)
    except Exception as exc:  # pragma: no cover - third-party API behavior
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", f"Failed to retrieve Stripe subscription: {exc}"),
        ) from exc


def _plan_for_checkout_session(session: Any) -> str:
    metadata = _field_value(session, "metadata") or {}
    plan = metadata.get("plan")
    if isinstance(plan, str) and plan in SUPPORTED_PLANS:
        return plan
    return "starter"


def _sync_billing_account_for_session(session: Any, user_id: str) -> dict[str, Any]:
    metadata = _field_value(session, "metadata") or {}
    session_user_id = _field_value(session, "client_reference_id") or metadata.get("user_id")
    session_user_id = str(session_user_id) if session_user_id is not None else None
    if session_user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=_detail("forbidden", "Checkout session does not belong to the current user"),
        )

    if _field_value(session, "mode") != "subscription":
        raise HTTPException(
            status_code=409,
            detail=_detail("billing_sync_failed", "Checkout session is not a subscription session"),
        )

    if _field_value(session, "status") != "complete":
        raise HTTPException(
            status_code=409,
            detail=_detail("billing_sync_failed", "Checkout session is not complete"),
        )

    subscription = _retrieve_subscription(_field_value(session, "subscription"))
    status = _normalize_billing_status(_field_value(subscription, "status"))
    if status not in SUPPORTED_BILLING_STATUSES:
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", f"Unsupported Stripe subscription status '{status}'"),
        )

    stripe_customer_id = _resource_id(_field_value(session, "customer")) or _resource_id(_field_value(subscription, "customer"))
    if not stripe_customer_id:
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", "Stripe checkout session did not return a customer reference"),
        )

    payload = {
        "user_id": user_id,
        "provider": "stripe",
        "plan": _plan_for_checkout_session(session),
        "status": status,
        "stripe_customer_id": stripe_customer_id,
        "current_period_start": _stripe_timestamp_to_iso(_field_value(subscription, "current_period_start")),
        "current_period_end": _stripe_timestamp_to_iso(_field_value(subscription, "current_period_end")),
    }
    result = (
        get_supabase()
        .table("billing_accounts")
        .upsert(payload, on_conflict="user_id")
        .execute()
    )
    account = (result.data or [payload])[0]
    return _billing_summary_from_account(account)


@router.get("/api/billing/me")
async def get_billing_summary(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("billing_accounts")
        .select(BILLING_SUMMARY_FIELDS)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    account = result.data
    if not account:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Billing account not found"))

    return _billing_summary_from_account(account)


@router.post("/api/billing/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    _configure_stripe()

    user_result = (
        get_supabase()
        .table("users")
        .select("email")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    billing_result = (
        get_supabase()
        .table("billing_accounts")
        .select("stripe_customer_id, status")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    billing_account = billing_result.data or {}
    stripe_customer_id = billing_account.get("stripe_customer_id")
    existing_status = _normalize_billing_status(billing_account.get("status"))
    if existing_status in MANAGEABLE_BILLING_STATUSES:
        if not stripe_customer_id:
            raise HTTPException(
                status_code=409,
                detail=_detail("billing_conflict", "Subscription is already active and cannot open a new checkout"),
            )

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=_billing_page_url(),
            )
        except Exception as exc:  # pragma: no cover - third-party API behavior
            raise HTTPException(
                status_code=502,
                detail=_detail("billing_error", f"Failed to create Stripe billing portal session: {exc}"),
            ) from exc

        portal_url = getattr(portal_session, "url", None)
        if not portal_url:
            raise HTTPException(
                status_code=502,
                detail=_detail("billing_error", "Stripe billing portal did not return a redirect URL"),
            )
        return {"checkout_url": portal_url}

    success_url = _billing_page_url(checkout="success", session_id="{CHECKOUT_SESSION_ID}")
    cancel_url = _billing_page_url(checkout="cancelled")

    checkout_params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": _stripe_price_id_for_plan(body.plan), "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id, "plan": body.plan},
    }
    if stripe_customer_id:
        checkout_params["customer"] = stripe_customer_id
    else:
        user = user_result.data or {}
        if user.get("email"):
            checkout_params["customer_email"] = user["email"]

    try:
        session = stripe.checkout.Session.create(**checkout_params)
    except Exception as exc:  # pragma: no cover - third-party API behavior
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", f"Failed to create Stripe checkout session: {exc}"),
        ) from exc

    checkout_url = getattr(session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", "Stripe checkout session did not return a checkout URL"),
        )

    return {"checkout_url": checkout_url}


@router.post("/api/billing/checkout/sync")
async def sync_checkout_session(
    body: CheckoutSyncRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    _configure_stripe()

    try:
        session = stripe.checkout.Session.retrieve(body.session_id)
    except Exception as exc:  # pragma: no cover - third-party API behavior
        raise HTTPException(
            status_code=502,
            detail=_detail("billing_error", f"Failed to retrieve Stripe checkout session: {exc}"),
        ) from exc

    return _sync_billing_account_for_session(session, user_id)


@router.get("/api/usage/me")
async def get_usage_summary(user_id: str = Depends(get_current_user_id)) -> dict[str, dict[str, float | int]]:
    period_start, period_end = _billing_period_for_user(user_id)
    claw_result = get_supabase().table("claws").select("id").eq("user_id", user_id).execute()
    claw_ids = [item["id"] for item in (claw_result.data or [])]
    if not claw_ids:
        return {
            "current_period": {
                "runs": 0,
                "tokens": 0,
                "estimated_cost": 0.0,
            }
        }

    result = (
        get_supabase()
        .table("runs")
        .select("id, token_usage")
        .in_("claw_id", claw_ids)
        .gte("created_at", period_start.isoformat())
        .lt("created_at", period_end.isoformat())
        .execute()
    )
    runs = result.data or []
    total_tokens = sum(int(run.get("token_usage") or 0) for run in runs)

    return {
        "current_period": {
            "runs": len(runs),
            "tokens": total_tokens,
            "estimated_cost": _estimated_cost(total_tokens),
        }
    }
