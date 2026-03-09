import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.config import settings
from app.db import get_supabase
from app.routers._helpers import record_activity_event, verify_claw_ownership

router = APIRouter(tags=["integrations"])

GITHUB_ACCEPT_HEADER = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_SCOPE_FALLBACK = "repository metadata, contents, pull requests"
STATE_TTL_MINUTES = 15


class GitHubIntegrationError(Exception):
    def __init__(self, message: str, *, status_code: int = 502, github_status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.github_status = github_status


class MintGitHubTokenRequest(BaseModel):
    claw_id: str
    integration_id: str
    repositories: list[str] | None = None
    permissions: dict[str, str] | None = None


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _raise_http_error_from_github(exc: GitHubIntegrationError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=_detail("integration_error", exc.message))


def _require_github_connect_config() -> None:
    if not settings.github_app_client_id:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub integration is not configured"),
        )
    if not settings.github_app_install_url:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub install URL is not configured"),
        )


def _require_github_app_credentials() -> tuple[str, str]:
    if not settings.github_app_id or not settings.github_app_private_key:
        raise GitHubIntegrationError("GitHub app credentials are not configured", status_code=503)
    return settings.github_app_id, settings.github_app_private_key.replace("\\n", "\n")


def _require_internal_service_token(x_internal_token: str | None) -> None:
    expected = settings.internal_service_token
    if not expected or not x_internal_token or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail=_detail("unauthorized", "Invalid internal token"))


async def _github_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    token_type: str = "Bearer",
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Accept": GITHUB_ACCEPT_HEADER,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        request_headers["Authorization"] = f"{token_type} {token}"
    if headers:
        request_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, headers=request_headers, json=json_body)
    except httpx.HTTPError as exc:
        raise GitHubIntegrationError("Failed to reach GitHub") from exc

    if response.status_code >= 400:
        payload = response.json() if response.content else {}
        message = payload.get("message") or "GitHub request failed"
        raise GitHubIntegrationError(
            f"GitHub request failed: {message}",
            github_status=response.status_code,
        )

    return response.json() if response.content else {}


def _build_connect_redirect_url(state_token: str) -> str:
    base = settings.github_app_install_url
    parsed = urlsplit(base)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["state"] = state_token

    # Support either an install URL or a direct OAuth authorize URL.
    if "login/oauth/authorize" in parsed.path and "client_id" not in query:
        query["client_id"] = settings.github_app_client_id

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def _build_success_redirect(claw_id: str) -> str:
    return f"{settings.cors_origin.rstrip('/')}/workspace/{claw_id}/settings?integration=success"


def _build_scope_summary(
    permissions: dict[str, str] | None,
    repository_selection: str | None,
    repository_count: int | None = None,
) -> str:
    if not permissions:
        return GITHUB_SCOPE_FALLBACK

    preferred = ["metadata", "contents", "pull_requests"]
    keys = sorted(permissions.keys(), key=lambda key: (key not in preferred, key))
    permission_summary = ", ".join(key.replace("_", " ") for key in keys[:4])
    if len(keys) > 4:
        permission_summary = f"{permission_summary}, +{len(keys) - 4} more"

    if repository_selection == "all":
        return f"all repositories; {permission_summary}"
    if repository_selection == "selected" and repository_count is not None:
        return f"{repository_count} selected repos; {permission_summary}"
    if repository_selection:
        return f"{repository_selection} repositories; {permission_summary}"

    return permission_summary


def _build_app_jwt() -> str:
    app_id, private_key = _require_github_app_credentials()
    now = int(time.time())
    return jwt.encode(
        {
            "iat": now - 60,
            "exp": now + 540,
            "iss": app_id,
        },
        private_key,
        algorithm="RS256",
    )


def _normalize_repositories(repositories: list[str] | None) -> list[str] | None:
    if not repositories:
        return None

    cleaned = []
    for repository in repositories:
        name = repository.strip()
        if not name:
            continue
        cleaned.append(name.split("/")[-1])

    return cleaned or None


async def _exchange_oauth_code_for_user_token(code: str) -> str:
    if not settings.github_app_client_id or not settings.github_app_client_secret:
        raise GitHubIntegrationError("GitHub OAuth credentials are not configured", status_code=503)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_app_client_id,
                    "client_secret": settings.github_app_client_secret,
                    "code": code,
                },
            )
    except httpx.HTTPError as exc:
        raise GitHubIntegrationError("Failed to exchange GitHub OAuth code") from exc

    payload = response.json() if response.content else {}
    token = payload.get("access_token")
    if not token:
        message = payload.get("error_description") or payload.get("error") or "GitHub OAuth exchange failed"
        raise GitHubIntegrationError(message)
    return token


async def _list_user_installations(user_token: str) -> list[dict[str, Any]]:
    payload = await _github_request("GET", "https://api.github.com/user/installations", token=user_token)
    return payload.get("installations", [])


async def _mint_installation_token_payload(
    github_installation_id: int,
    *,
    repositories: list[str] | None = None,
    permissions: dict[str, str] | None = None,
) -> dict[str, Any]:
    app_token = _build_app_jwt()
    body: dict[str, Any] = {}
    repository_names = _normalize_repositories(repositories)
    if repository_names:
        body["repositories"] = repository_names
    if permissions:
        body["permissions"] = permissions

    return await _github_request(
        "POST",
        f"https://api.github.com/app/installations/{github_installation_id}/access_tokens",
        token=app_token,
        json_body=body or None,
    )


async def _check_installation_health(github_installation_id: int) -> dict[str, Any]:
    token_payload = await _mint_installation_token_payload(github_installation_id)
    repository_payload = await _github_request(
        "GET",
        "https://api.github.com/installation/repositories",
        token=token_payload["token"],
    )
    return {
        "expires_at": token_payload.get("expires_at"),
        "permissions": token_payload.get("permissions") or {},
        "repository_count": repository_payload.get("total_count"),
    }


def _resolve_selected_installation(
    installations: list[dict[str, Any]],
    installation_id: int | None,
) -> dict[str, Any] | None:
    if installation_id is not None:
        for installation in installations:
            if str(installation.get("id")) == str(installation_id):
                return installation
        return None

    if len(installations) == 1:
        return installations[0]

    return None


def _get_state_record(state_token: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("integration_states")
        .select("id, claw_id, user_id, state_token, created_at, expires_at")
        .eq("state_token", state_token)
        .maybe_single()
        .execute()
    )
    record = result.data
    if not record:
        raise HTTPException(status_code=400, detail=_detail("integration_error", "Invalid integration state"))

    expires_at = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        get_supabase().table("integration_states").delete().eq("id", record["id"]).execute()
        raise HTTPException(status_code=400, detail=_detail("integration_error", "Integration state has expired"))

    return record


def _delete_state_record(state_id: str) -> None:
    get_supabase().table("integration_states").delete().eq("id", state_id).execute()


def _get_github_integration(claw_id: str, integration_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("integrations")
        .select("*")
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .eq("provider", "github")
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Integration not found"))
    return result.data


def _get_integration_for_internal(claw_id: str, integration_id: str) -> dict[str, Any]:
    result = (
        get_supabase()
        .table("integrations")
        .select("*")
        .eq("id", integration_id)
        .eq("claw_id", claw_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=_detail("not_found", "Integration not found"))
    return result.data


def _upsert_github_integration(
    *,
    claw_id: str,
    github_installation_id: int,
    scope_summary: str,
    external_account_ref: str | None,
    config_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    supabase = get_supabase()
    existing_result = (
        supabase.table("integrations")
        .select("*")
        .eq("claw_id", claw_id)
        .eq("provider", "github")
        .limit(1)
        .execute()
    )
    existing_rows = existing_result.data or []
    existing = existing_rows[0] if existing_rows else None

    merged_config = dict(existing.get("config_json") or {}) if existing else {}
    if config_json:
        merged_config.update(config_json)

    payload = {
        "provider": "github",
        "status": "connected",
        "external_account_ref": external_account_ref,
        "scope_summary": scope_summary,
        "config_json": merged_config,
        "github_installation_id": github_installation_id,
    }

    if existing:
        result = supabase.table("integrations").update(payload).eq("id", existing["id"]).execute()
        return result.data[0]

    result = supabase.table("integrations").insert({"claw_id": claw_id, **payload}).execute()
    return result.data[0]


@router.get("/api/claws/{claw_id}/integrations")
async def list_integrations(claw_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, list[dict[str, Any]]]:
    verify_claw_ownership(claw_id, user_id)
    result = (
        get_supabase()
        .table("integrations")
        .select("id, provider, status, scope_summary, updated_at")
        .eq("claw_id", claw_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return {"items": result.data or []}


@router.post("/api/claws/{claw_id}/integrations/github/connect")
async def start_github_connect(
    claw_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    verify_claw_ownership(claw_id, user_id)
    _require_github_connect_config()

    state_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)

    get_supabase().table("integration_states").insert(
        {
            "claw_id": claw_id,
            "user_id": user_id,
            "state_token": state_token,
            "expires_at": expires_at.isoformat(),
        }
    ).execute()

    return {"redirect_url": _build_connect_redirect_url(state_token)}


@router.get("/api/integrations/github/callback")
async def github_callback(
    state: str = Query(..., min_length=1),
    code: str | None = Query(None),
    installation_id: int | None = Query(None),
    setup_action: str | None = Query(None),
) -> RedirectResponse:
    state_record = _get_state_record(state)

    try:
        installations: list[dict[str, Any]] = []
        if code:
            user_token = await _exchange_oauth_code_for_user_token(code)
            installations = await _list_user_installations(user_token)

        selected_installation = _resolve_selected_installation(installations, installation_id)
        resolved_installation_id = installation_id or (
            int(selected_installation["id"]) if selected_installation and selected_installation.get("id") else None
        )
        if resolved_installation_id is None:
            raise HTTPException(
                status_code=400,
                detail=_detail("integration_error", "GitHub installation could not be resolved"),
            )

        if installation_id is not None and code and selected_installation is None:
            raise HTTPException(
                status_code=400,
                detail=_detail("integration_error", "GitHub installation is not accessible to this user"),
            )

        permissions = selected_installation.get("permissions") if selected_installation else None
        repository_selection = selected_installation.get("repository_selection") if selected_installation else None
        account = selected_installation.get("account") if selected_installation else {}

        integration = _upsert_github_integration(
            claw_id=state_record["claw_id"],
            github_installation_id=resolved_installation_id,
            scope_summary=_build_scope_summary(permissions, repository_selection),
            external_account_ref=(account or {}).get("login") or (
                str((account or {}).get("id")) if (account or {}).get("id") else None
            ),
            config_json={
                "account_login": (account or {}).get("login"),
                "account_type": (account or {}).get("type"),
                "permissions": permissions or {},
                "repository_selection": repository_selection,
                "setup_action": setup_action,
            },
        )
    except GitHubIntegrationError as exc:
        _raise_http_error_from_github(exc)

    _delete_state_record(state_record["id"])

    record_activity_event(
        claw_id=state_record["claw_id"],
        event_type="integration_connected",
        summary="GitHub integration connected",
        metadata={
            "integration_id": integration["id"],
            "provider": integration["provider"],
            "status": integration["status"],
            "github_installation_id": integration.get("github_installation_id"),
        },
    )

    return RedirectResponse(url=_build_success_redirect(state_record["claw_id"]), status_code=302)


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/disconnect")
async def disconnect_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    verify_claw_ownership(claw_id, user_id)
    integration = _get_github_integration(claw_id, integration_id)

    result = (
        get_supabase()
        .table("integrations")
        .update({"status": "disconnected"})
        .eq("id", integration_id)
        .execute()
    )
    updated = result.data[0]

    record_activity_event(
        claw_id=claw_id,
        event_type="integration_disconnected",
        summary="GitHub integration disconnected",
        metadata={
            "integration_id": integration_id,
            "provider": updated["provider"],
            "previous_status": integration["status"],
            "status": updated["status"],
        },
    )

    return {"id": updated["id"], "status": updated["status"]}


@router.post("/api/claws/{claw_id}/integrations/{integration_id}/refresh")
async def refresh_integration(
    claw_id: str,
    integration_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    verify_claw_ownership(claw_id, user_id)
    integration = _get_github_integration(claw_id, integration_id)

    github_installation_id = integration.get("github_installation_id")
    if github_installation_id is None:
        raise HTTPException(
            status_code=409,
            detail=_detail("integration_error", "GitHub installation is not configured for this integration"),
        )

    try:
        health = await _check_installation_health(int(github_installation_id))
        scope_summary = _build_scope_summary(
            health.get("permissions"),
            (integration.get("config_json") or {}).get("repository_selection"),
            health.get("repository_count"),
        )
        result = (
            get_supabase()
            .table("integrations")
            .update({"status": "connected", "scope_summary": scope_summary})
            .eq("id", integration_id)
            .execute()
        )
        updated = result.data[0]

        record_activity_event(
            claw_id=claw_id,
            event_type="integration_refreshed",
            summary="GitHub integration refreshed",
            metadata={
                "integration_id": integration_id,
                "provider": updated["provider"],
                "previous_status": integration["status"],
                "status": updated["status"],
                "repository_count": health.get("repository_count"),
            },
        )
    except GitHubIntegrationError as exc:
        result = (
            get_supabase()
            .table("integrations")
            .update({"status": "degraded"})
            .eq("id", integration_id)
            .execute()
        )
        updated = result.data[0]

        record_activity_event(
            claw_id=claw_id,
            event_type="integration_degraded",
            summary="GitHub integration refresh failed",
            metadata={
                "integration_id": integration_id,
                "provider": updated["provider"],
                "previous_status": integration["status"],
                "status": updated["status"],
                "error": exc.message,
            },
        )

    return {"id": updated["id"], "status": updated["status"], "updated_at": updated["updated_at"]}


@router.post("/internal/integrations/github/token")
async def mint_github_installation_token(
    body: MintGitHubTokenRequest,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
) -> dict[str, str]:
    _require_internal_service_token(x_internal_token)

    integration = _get_integration_for_internal(body.claw_id, body.integration_id)
    if integration.get("provider") != "github":
        raise HTTPException(status_code=400, detail=_detail("integration_error", "Only GitHub integrations are supported"))
    if integration.get("status") == "disconnected":
        raise HTTPException(status_code=409, detail=_detail("integration_error", "Integration is disconnected"))

    github_installation_id = integration.get("github_installation_id")
    if github_installation_id is None:
        raise HTTPException(status_code=409, detail=_detail("integration_error", "Integration has no installation ID"))

    try:
        payload = await _mint_installation_token_payload(
            int(github_installation_id),
            repositories=body.repositories,
            permissions=body.permissions,
        )
    except GitHubIntegrationError as exc:
        _raise_http_error_from_github(exc)

    return {"token": payload["token"], "expires_at": payload["expires_at"]}
