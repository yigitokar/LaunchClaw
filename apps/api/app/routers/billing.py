from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.services.scheduler import parse_timestamp, utc_now

router = APIRouter(tags=["billing"])

BILLING_SUMMARY_FIELDS = "provider, plan, status, stripe_customer_id, current_period_start, current_period_end"
COST_PER_1K_TOKENS = Decimal("0.0896")
SUPPORTED_PLANS = {"starter"}


class CheckoutRequest(BaseModel):
    plan: Literal["starter"]


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


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

    return {
        "provider": account["provider"],
        "plan": account["plan"],
        "status": account["status"],
        "current_period_start": account.get("current_period_start"),
        "current_period_end": account.get("current_period_end"),
    }


@router.post("/api/billing/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    stripe_secret_key = settings.stripe_secret_key.strip()
    if not stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail=_detail("billing_unavailable", "Stripe billing is not configured"),
        )

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
        .select("stripe_customer_id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    stripe.api_key = stripe_secret_key
    success_url = f"{settings.frontend_url.rstrip('/')}/billing?checkout=success"
    cancel_url = f"{settings.frontend_url.rstrip('/')}/billing?checkout=cancelled"

    checkout_params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": _stripe_price_id_for_plan(body.plan), "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": user_id,
        "metadata": {"user_id": user_id, "plan": body.plan},
    }

    billing_account = billing_result.data or {}
    stripe_customer_id = billing_account.get("stripe_customer_id")
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
