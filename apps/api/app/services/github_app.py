import json
from typing import Any
from urllib import error, request

import jwt
from fastapi import HTTPException

from app.config import settings
from app.services.scheduler import utc_now

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _github_app_id() -> str:
    app_id = settings.github_app_id.strip()
    if not app_id:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub App ID is not configured"),
        )
    return app_id


def _github_private_key() -> str:
    private_key = settings.github_app_private_key.strip()
    if not private_key:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub App private key is not configured"),
        )
    return private_key.replace("\\n", "\n")


def require_github_app_credentials() -> None:
    _github_app_id()
    _github_private_key()


def _github_app_jwt() -> str:
    now = int(utc_now().timestamp())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": _github_app_id(),
    }
    try:
        token = jwt.encode(payload, _github_private_key(), algorithm="RS256")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=_detail("integration_error", "GitHub App credentials are invalid"),
        ) from exc
    return str(token)


def _github_api_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_github_app_jwt()}",
        "User-Agent": "LaunchClaw",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = request.Request(
        f"{GITHUB_API_BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with request.urlopen(req, timeout=15) as response:
            raw_body = response.read().decode("utf-8")
            return response.status, json.loads(raw_body) if raw_body else {}
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            payload = {}
        return exc.code, payload
    except error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=_detail("integration_error", f"GitHub API request failed: {exc.reason}"),
        ) from exc


def get_github_app_installation(installation_id: str) -> dict[str, Any]:
    status_code, payload = _github_api_request("GET", f"/app/installations/{installation_id}")
    if status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=_detail("validation_error", "GitHub installation could not be verified"),
        )
    if status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=502,
            detail=_detail("integration_error", f"GitHub installation lookup failed: {message or status_code}"),
        )

    app_slug = payload.get("app_slug")
    expected_slug = settings.github_app_slug.strip()
    if expected_slug and app_slug and app_slug != expected_slug:
        raise HTTPException(
            status_code=409,
            detail=_detail("integration_error", "Verified installation belongs to a different GitHub App"),
        )

    return payload


def mint_github_installation_token(
    installation_id: str,
    repositories: list[str],
    permissions: dict[str, str],
) -> dict[str, str]:
    request_body: dict[str, Any] = {}
    if repositories:
        request_body["repositories"] = repositories
    if permissions:
        request_body["permissions"] = permissions

    status_code, payload = _github_api_request(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        body=request_body,
    )
    if status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise HTTPException(
            status_code=502,
            detail=_detail("integration_error", f"GitHub token mint failed: {message or status_code}"),
        )

    token = payload.get("token")
    expires_at = payload.get("expires_at")
    if not isinstance(token, str) or not isinstance(expires_at, str):
        raise HTTPException(
            status_code=502,
            detail=_detail("integration_error", "GitHub token mint returned an invalid response"),
        )

    return {"token": token, "expires_at": expires_at}
