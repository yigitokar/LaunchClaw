# LaunchClaw v1 — API Specification

## Status

Draft v1

## Purpose

This document defines the external and internal API surface for LaunchClaw v1.

It covers:

- authentication assumptions
- public control-plane APIs
- workspace APIs
- lifecycle APIs
- GitHub integration APIs
- scheduling APIs
- approval APIs
- internal provisioning and runtime callback APIs
- response conventions
- error model

This is an implementation-oriented API spec for v1. It is not a generic long-term platform contract.

---

## 1. Conventions

## 1.1 Base paths

Public authenticated API:

```text
/api
````

Internal service-to-service API:

```text
/internal
```

## 1.2 Authentication

Public endpoints require an authenticated user session.

Recommended v1 model:

* browser authenticates via Supabase Auth
* frontend sends bearer token or session cookie to API
* API resolves current user
* API enforces ownership of all Claw-scoped resources

Internal endpoints must not be user-callable.
They should be protected by service credentials, network boundaries, or signed internal tokens.

## 1.3 Content type

All request and response bodies use JSON unless explicitly stated otherwise.

```http
Content-Type: application/json
```

## 1.4 Resource IDs

Use opaque IDs.

Examples:

* `user_...`
* `claw_...`
* `run_...`
* `approval_...`
* `integration_...`

UUIDs are fine internally even if public IDs later change format.

## 1.5 Timestamps

All timestamps must be ISO 8601 in UTC.

Example:

```json
{
  "created_at": "2026-03-09T20:15:13Z"
}
```

## 1.6 Pagination

List endpoints should support cursor pagination later, but v1 can start with limit/offset if needed.

Preferred shape:

```http
GET /api/claws/:id/runs?limit=20&cursor=...
```

Response shape:

```json
{
  "items": [],
  "next_cursor": null
}
```

## 1.7 Error envelope

All non-2xx responses should use a standard error shape.

```json
{
  "error": {
    "code": "not_found",
    "message": "Claw not found"
  }
}
```

Suggested error codes:

* `unauthorized`
* `forbidden`
* `not_found`
* `validation_error`
* `conflict`
* `rate_limited`
* `integration_error`
* `provisioning_error`
* `internal_error`

---

## 2. Auth and Current User

## 2.1 Get current user

```http
GET /api/me
```

### Response

```json
{
  "id": "user_123",
  "email": "yigit@example.com",
  "name": "Yigit",
  "billing": {
    "plan": "starter",
    "status": "active"
  }
}
```

---

## 3. Claws

## 3.1 Create Claw

Creates a new Claw and starts provisioning.

```http
POST /api/claws
```

### Request

```json
{
  "name": "My Claw",
  "preset_id": "preset_dev_assistant",
  "model_access_mode": "byok",
  "connect_github": true
}
```

### Validation rules

* `name` required, non-empty
* `preset_id` required
* `model_access_mode` must be `byok` or `managed`
* user may only have one active Claw in v1

### Response

```json
{
  "id": "claw_123",
  "name": "My Claw",
  "status": "creating",
  "preset_id": "preset_dev_assistant",
  "model_access_mode": "byok",
  "created_at": "2026-03-09T20:15:13Z"
}
```

### Failure cases

* user already has active Claw
* invalid preset
* missing model access configuration
* provisioning request creation failure

---

## 3.2 List current user's Claws

Even if v1 supports one active Claw, keep the API list-shaped.

```http
GET /api/claws
```

### Response

```json
{
  "items": [
    {
      "id": "claw_123",
      "name": "My Claw",
      "status": "healthy",
      "preset_id": "preset_dev_assistant",
      "last_active_at": "2026-03-09T20:20:00Z",
      "created_at": "2026-03-09T20:15:13Z"
    }
  ],
  "next_cursor": null
}
```

---

## 3.3 Get Claw

```http
GET /api/claws/:claw_id
```

### Response

```json
{
  "id": "claw_123",
  "name": "My Claw",
  "status": "healthy",
  "preset_id": "preset_dev_assistant",
  "runtime_provider": "fargate",
  "model_access_mode": "byok",
  "last_active_at": "2026-03-09T20:20:00Z",
  "created_at": "2026-03-09T20:15:13Z",
  "updated_at": "2026-03-09T20:20:00Z"
}
```

---

## 3.4 Update Claw metadata

Limited metadata updates only.

```http
PATCH /api/claws/:claw_id
```

### Request

```json
{
  "name": "Research Claw"
}
```

### Response

```json
{
  "id": "claw_123",
  "name": "Research Claw",
  "status": "healthy",
  "updated_at": "2026-03-09T20:22:01Z"
}
```

---

## 3.5 Pause Claw

```http
POST /api/claws/:claw_id/pause
```

### Response

```json
{
  "id": "claw_123",
  "status": "paused"
}
```

---

## 3.6 Resume Claw

```http
POST /api/claws/:claw_id/resume
```

### Response

```json
{
  "id": "claw_123",
  "status": "provisioning"
}
```

---

## 3.7 Restart Claw

```http
POST /api/claws/:claw_id/restart
```

### Response

```json
{
  "id": "claw_123",
  "status": "restarting"
}
```

---

## 3.8 Recover failed Claw

```http
POST /api/claws/:claw_id/recover
```

### Response

```json
{
  "id": "claw_123",
  "status": "provisioning"
}
```

---

## 4. Presets

## 4.1 List presets

```http
GET /api/presets
```

### Response

```json
{
  "items": [
    {
      "id": "preset_dev_assistant",
      "slug": "dev-assistant",
      "name": "Dev Assistant",
      "description": "Good default for code and GitHub work"
    }
  ]
}
```

## 4.2 Get preset

```http
GET /api/presets/:preset_id
```

### Response

```json
{
  "id": "preset_dev_assistant",
  "slug": "dev-assistant",
  "name": "Dev Assistant",
  "description": "Good default for code and GitHub work"
}
```

---

## 5. Workspace Files

## 5.1 List workspace files

```http
GET /api/claws/:claw_id/workspace/files
```

### Response

```json
{
  "items": [
    {
      "id": "wf_1",
      "path": "desired/mission.md",
      "kind": "mission",
      "is_desired_state": true,
      "version": 3,
      "updated_at": "2026-03-09T20:18:00Z"
    },
    {
      "id": "wf_2",
      "path": "desired/rules.md",
      "kind": "rules",
      "is_desired_state": true,
      "version": 1,
      "updated_at": "2026-03-09T20:18:00Z"
    }
  ]
}
```

## 5.2 Get file content

```http
GET /api/claws/:claw_id/workspace/files/content?path=desired/mission.md
```

### Response

```json
{
  "path": "desired/mission.md",
  "kind": "mission",
  "content": "# Mission\nReview PRs every morning.",
  "version": 3,
  "updated_at": "2026-03-09T20:18:00Z"
}
```

## 5.3 Update file content

Used for relatively raw desired-state editing.

```http
PUT /api/claws/:claw_id/workspace/files/content
```

### Request

```json
{
  "path": "desired/mission.md",
  "content": "# Mission\nReview PRs every morning and summarize blockers.",
  "base_version": 3
}
```

### Behavior

* only editable for approved file paths in v1
* optimistic concurrency check on `base_version`
* new version created on success

### Response

```json
{
  "path": "desired/mission.md",
  "version": 4,
  "updated_at": "2026-03-09T20:25:00Z"
}
```

### Failure cases

* invalid path
* edit not allowed for system-managed file
* version conflict

---

## 6. Runs

## 6.1 Create manual Run

```http
POST /api/claws/:claw_id/runs
```

### Request

```json
{
  "input": "Review open pull requests and summarize blockers."
}
```

### Response

```json
{
  "id": "run_123",
  "claw_id": "claw_123",
  "trigger_type": "manual",
  "status": "queued",
  "created_at": "2026-03-09T20:30:00Z"
}
```

## 6.2 List Runs

```http
GET /api/claws/:claw_id/runs?limit=20
```

### Response

```json
{
  "items": [
    {
      "id": "run_123",
      "trigger_type": "manual",
      "status": "succeeded",
      "approval_state": null,
      "started_at": "2026-03-09T20:30:05Z",
      "ended_at": "2026-03-09T20:31:10Z"
    }
  ],
  "next_cursor": null
}
```

## 6.3 Get Run detail

```http
GET /api/runs/:run_id
```

### Response

```json
{
  "id": "run_123",
  "claw_id": "claw_123",
  "trigger_type": "manual",
  "status": "succeeded",
  "approval_state": null,
  "input_summary": "Review open pull requests and summarize blockers.",
  "started_at": "2026-03-09T20:30:05Z",
  "ended_at": "2026-03-09T20:31:10Z",
  "token_usage": 8421,
  "cost_estimate": 0.17
}
```

## 6.4 Cancel Run

Useful if queued or waiting approval.

```http
POST /api/runs/:run_id/cancel
```

### Response

```json
{
  "id": "run_123",
  "status": "cancelled"
}
```

---

## 7. Artifacts

## 7.1 List artifacts for a Run

```http
GET /api/runs/:run_id/artifacts
```

### Response

```json
{
  "items": [
    {
      "id": "artifact_1",
      "kind": "report",
      "path": "artifacts/run_123/pr-summary.md",
      "size_bytes": 14293,
      "created_at": "2026-03-09T20:31:10Z"
    }
  ]
}
```

## 7.2 Get artifact metadata

```http
GET /api/artifacts/:artifact_id
```

### Response

```json
{
  "id": "artifact_1",
  "run_id": "run_123",
  "claw_id": "claw_123",
  "kind": "report",
  "path": "artifacts/run_123/pr-summary.md",
  "size_bytes": 14293,
  "download_url": null,
  "created_at": "2026-03-09T20:31:10Z"
}
```

A separate signed-download endpoint can be added later if needed.

---

## 8. Integrations

## 8.1 List integrations for a Claw

```http
GET /api/claws/:claw_id/integrations
```

### Response

```json
{
  "items": [
    {
      "id": "integration_123",
      "provider": "github",
      "status": "connected",
      "scope_summary": "repo metadata, pull requests, contents",
      "updated_at": "2026-03-09T20:19:00Z"
    }
  ]
}
```

## 8.2 Start GitHub connect flow

```http
POST /api/claws/:claw_id/integrations/github/connect
```

### Response

```json
{
  "redirect_url": "https://github.com/apps/launchclaw/installations/new"
}
```

## 8.3 GitHub callback

This is typically a browser redirect target or backend callback handler, depending on exact GitHub App flow.

```http
GET /api/integrations/github/callback
```

### Query params

* provider callback params
* installation or auth context
* optional state token

### Response

For browser flow, usually a redirect, not JSON.

## 8.4 Disconnect integration

```http
POST /api/claws/:claw_id/integrations/:integration_id/disconnect
```

### Response

```json
{
  "id": "integration_123",
  "status": "disconnected"
}
```

## 8.5 Refresh integration health

Optional but useful.

```http
POST /api/claws/:claw_id/integrations/:integration_id/refresh
```

### Response

```json
{
  "id": "integration_123",
  "status": "connected",
  "updated_at": "2026-03-09T20:40:00Z"
}
```

---

## 9. Secrets

## 9.1 Create or replace secret

```http
POST /api/claws/:claw_id/secrets
```

### Request

```json
{
  "provider": "openai",
  "label": "OPENAI_API_KEY",
  "value": "sk-..."
}
```

### Behavior

* create new secret metadata or replace existing one
* underlying secret stored in Secrets Manager or equivalent
* response must never echo the secret value
* if runtime needs restart after rotation, include signal in response

### Response

```json
{
  "id": "secret_123",
  "provider": "openai",
  "label": "OPENAI_API_KEY",
  "status": "active",
  "restart_required": true,
  "last_rotated_at": "2026-03-09T20:35:00Z"
}
```

## 9.2 List secret metadata

```http
GET /api/claws/:claw_id/secrets
```

### Response

```json
{
  "items": [
    {
      "id": "secret_123",
      "provider": "openai",
      "label": "OPENAI_API_KEY",
      "status": "active",
      "last_rotated_at": "2026-03-09T20:35:00Z"
    }
  ]
}
```

## 9.3 Revoke secret

```http
DELETE /api/claws/:claw_id/secrets/:secret_id
```

### Response

```json
{
  "id": "secret_123",
  "status": "revoked"
}
```

---

## 10. Scheduling

## 10.1 List schedules

```http
GET /api/claws/:claw_id/schedules
```

### Response

```json
{
  "items": [
    {
      "id": "schedule_123",
      "name": "Morning PR review",
      "schedule_expr": "0 9 * * 1-5",
      "enabled": true,
      "last_run_at": "2026-03-09T14:00:00Z",
      "next_run_at": "2026-03-10T14:00:00Z"
    }
  ]
}
```

## 10.2 Create schedule

```http
POST /api/claws/:claw_id/schedules
```

### Request

```json
{
  "name": "Morning PR review",
  "schedule_expr": "0 9 * * 1-5",
  "enabled": true
}
```

### Response

```json
{
  "id": "schedule_123",
  "name": "Morning PR review",
  "schedule_expr": "0 9 * * 1-5",
  "enabled": true,
  "last_run_at": null,
  "next_run_at": "2026-03-10T14:00:00Z"
}
```

## 10.3 Update schedule

```http
PUT /api/claws/:claw_id/schedules/:schedule_id
```

### Request

```json
{
  "name": "Weekday PR review",
  "schedule_expr": "0 10 * * 1-5",
  "enabled": true
}
```

### Response

```json
{
  "id": "schedule_123",
  "name": "Weekday PR review",
  "schedule_expr": "0 10 * * 1-5",
  "enabled": true,
  "next_run_at": "2026-03-10T15:00:00Z"
}
```

## 10.4 Toggle schedule

```http
POST /api/claws/:claw_id/schedules/:schedule_id/toggle
```

### Request

```json
{
  "enabled": false
}
```

### Response

```json
{
  "id": "schedule_123",
  "enabled": false
}
```

## 10.5 Trigger schedule immediately

Useful for testing.

```http
POST /api/claws/:claw_id/schedules/:schedule_id/run-now
```

### Response

```json
{
  "run_id": "run_456",
  "status": "queued"
}
```

---

## 11. Approvals

## 11.1 List approvals

```http
GET /api/claws/:claw_id/approvals
```

### Response

```json
{
  "items": [
    {
      "id": "approval_123",
      "run_id": "run_123",
      "action_type": "github_write",
      "payload_summary": "Create branch and open PR in repo foo/bar",
      "status": "pending",
      "requested_at": "2026-03-09T20:45:00Z"
    }
  ]
}
```

## 11.2 Get approval detail

```http
GET /api/approvals/:approval_id
```

### Response

```json
{
  "id": "approval_123",
  "claw_id": "claw_123",
  "run_id": "run_123",
  "action_type": "github_write",
  "payload_summary": "Create branch and open PR in repo foo/bar",
  "status": "pending",
  "requested_at": "2026-03-09T20:45:00Z",
  "resolved_at": null
}
```

## 11.3 Approve action

```http
POST /api/approvals/:approval_id/approve
```

### Response

```json
{
  "id": "approval_123",
  "status": "approved",
  "resolved_at": "2026-03-09T20:46:00Z"
}
```

## 11.4 Deny action

```http
POST /api/approvals/:approval_id/deny
```

### Response

```json
{
  "id": "approval_123",
  "status": "denied",
  "resolved_at": "2026-03-09T20:46:10Z"
}
```

---

## 12. Activity

## 12.1 List activity for a Claw

User-visible event feed, separate from raw logs.

```http
GET /api/claws/:claw_id/activity
```

### Response

```json
{
  "items": [
    {
      "id": "evt_1",
      "type": "claw_healthy",
      "summary": "Claw became healthy",
      "created_at": "2026-03-09T20:16:00Z"
    },
    {
      "id": "evt_2",
      "type": "run_started",
      "summary": "Manual run started",
      "created_at": "2026-03-09T20:30:05Z"
    }
  ],
  "next_cursor": null
}
```

Suggested event types:

* `claw_created`
* `claw_healthy`
* `claw_paused`
* `claw_restarted`
* `run_started`
* `run_succeeded`
* `run_failed`
* `schedule_triggered`
* `approval_requested`
* `approval_approved`
* `approval_denied`
* `integration_connected`
* `integration_degraded`
* `secret_rotated`

---

## 13. Billing

## 13.1 Get billing summary

```http
GET /api/billing/me
```

### Response

```json
{
  "provider": "stripe",
  "plan": "starter",
  "status": "active",
  "current_period_start": "2026-03-01T00:00:00Z",
  "current_period_end": "2026-04-01T00:00:00Z"
}
```

## 13.2 Create checkout session

```http
POST /api/billing/checkout
```

### Request

```json
{
  "plan": "starter"
}
```

### Response

```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

## 13.3 Get usage summary

```http
GET /api/usage/me
```

### Response

```json
{
  "current_period": {
    "runs": 18,
    "tokens": 143282,
    "estimated_cost": 12.84
  }
}
```

---

## 14. Health and Readiness

## 14.1 Public API health

```http
GET /api/health
```

### Response

```json
{
  "status": "ok"
}
```

This is for infrastructure health, not auth or user state.

---

## 15. Internal Provisioning APIs

These endpoints are service-to-service only.

## 15.1 Start provisioning

```http
POST /internal/provisioning/claws/:claw_id/start
```

### Request

```json
{
  "reason": "initial_create"
}
```

### Behavior

* resolve Claw desired state
* seed workspace
* resolve integration metadata
* bind secret references
* launch runtime task
* transition Claw state

### Response

```json
{
  "claw_id": "claw_123",
  "status": "provisioning"
}
```

## 15.2 Stop runtime

```http
POST /internal/provisioning/claws/:claw_id/stop
```

### Request

```json
{
  "reason": "pause"
}
```

## 15.3 Restart runtime

```http
POST /internal/provisioning/claws/:claw_id/restart
```

### Request

```json
{
  "reason": "secret_rotation"
}
```

## 15.4 Runtime heartbeat update

Used by runtime to report health.

```http
POST /internal/runtime/claws/:claw_id/heartbeat
```

### Request

```json
{
  "task_ref": "ecs-task-abc",
  "status": "healthy",
  "observed_at": "2026-03-09T20:40:00Z"
}
```

## 15.5 Runtime status update for Run

```http
POST /internal/runs/:run_id/status
```

### Request

```json
{
  "status": "running",
  "started_at": "2026-03-09T20:30:05Z"
}
```

Or later:

```json
{
  "status": "succeeded",
  "ended_at": "2026-03-09T20:31:10Z",
  "token_usage": 8421,
  "cost_estimate": 0.17
}
```

## 15.6 Register artifact

```http
POST /internal/runs/:run_id/artifacts
```

### Request

```json
{
  "kind": "report",
  "path": "artifacts/run_123/pr-summary.md",
  "storage_ref": "s3://launchclaw-workspaces/claw_123/artifacts/run_123/pr-summary.md",
  "size_bytes": 14293
}
```

## 15.7 Create approval request

```http
POST /internal/approvals
```

### Request

```json
{
  "claw_id": "claw_123",
  "run_id": "run_123",
  "action_type": "github_write",
  "payload_summary": "Create branch and open PR in repo foo/bar"
}
```

### Response

```json
{
  "id": "approval_123",
  "status": "pending"
}
```

## 15.8 Poll approval decision

Simple v1 approach.

```http
GET /internal/approvals/:approval_id
```

### Response

```json
{
  "id": "approval_123",
  "status": "approved"
}
```

Longer term this could be event-driven instead of polling.

---

## 16. Internal GitHub Token APIs

Keep app private key out of runtime.

## 16.1 Mint installation access token

```http
POST /internal/integrations/github/token
```

### Request

```json
{
  "claw_id": "claw_123",
  "integration_id": "integration_123",
  "repositories": ["foo/bar"],
  "permissions": {
    "contents": "write",
    "pull_requests": "write"
  }
}
```

### Response

```json
{
  "token": "ghs_...",
  "expires_at": "2026-03-09T21:35:00Z"
}
```

This endpoint is internal only.
The runtime may call it, or the control plane may proxy GitHub writes itself.

---

## 17. Ownership and Authorization Rules

## 17.1 Public API ownership checks

For every public endpoint scoped to a Claw or child resource:

* resolve current user
* verify resource belongs to current user
* otherwise return `404` or `403`

Recommended v1 behavior:
prefer `404` for non-owned resources to avoid leaking existence.

## 17.2 Internal API authorization

Internal calls must be authenticated separately from user auth.

Recommended v1 options:

* signed service token
* private network access only plus shared auth
* workload identity if deployed inside AWS

---

## 18. Validation Rules

## 18.1 Claw name

* required
* max length 80
* trimmed
* no control characters

## 18.2 Schedule expression

* required
* must parse under chosen cron parser
* enforce minimum interval in v1 if needed to prevent abuse

## 18.3 File path edits

* only allow edits in approved desired-state paths
* reject path traversal patterns
* normalize paths before storage

## 18.4 Secret labels

* required
* uppercase snake case preferred
* max length 120

---

## 19. Idempotency and Retries

## 19.1 Public APIs

For create-like operations that may be retried by client, support an idempotency key later if needed.

For v1, likely candidates:

* `POST /api/claws`
* `POST /api/billing/checkout`

## 19.2 Internal APIs

Provisioning operations must be idempotent.
A retried internal provisioning start must not create duplicate active runtime state for the same Claw.

---

## 20. Suggested HTTP Status Usage

* `200 OK` for standard success
* `201 Created` for created resources if desired
* `202 Accepted` for async lifecycle actions if not completed immediately
* `400 Bad Request` for malformed input
* `401 Unauthorized` for missing auth
* `403 Forbidden` for valid auth but forbidden action
* `404 Not Found` for absent or hidden resource
* `409 Conflict` for version conflict or active Claw conflict
* `422 Unprocessable Entity` for validation failures if preferred
* `429 Too Many Requests` for rate limits
* `500 Internal Server Error` for unexpected failures
* `503 Service Unavailable` for temporary backend failures

For lifecycle operations like pause/restart/recover, `202 Accepted` is arguably cleaner if state transition is asynchronous.

---

## 21. Webhook Endpoints

## 21.1 GitHub webhook receiver

If GitHub App events are used:

```http
POST /api/webhooks/github
```

### Responsibilities

* verify webhook signature
* process installation events
* optionally process repo events if enabled
* update integration metadata
* enqueue any downstream work

This endpoint belongs to the control plane only.

---

## 22. Event Model

User-visible activity feed should be built from typed events.

Suggested canonical event payload shape:

```json
{
  "id": "evt_123",
  "claw_id": "claw_123",
  "type": "run_started",
  "summary": "Manual run started",
  "metadata": {
    "run_id": "run_123"
  },
  "created_at": "2026-03-09T20:30:05Z"
}
```

This should be append-only.

---

## 23. Minimal OpenAPI Direction

You do not need full OpenAPI before building, but all new endpoints should be designed so they can be described in OpenAPI cleanly.

Recommended repo path later:

```text
/docs/openapi.yaml
```

---

## 24. v1 API Priorities

The first APIs to implement should be:

1. `POST /api/claws`
2. `GET /api/claws/:claw_id`
3. `POST /api/claws/:claw_id/restart`
4. `GET /api/claws/:claw_id/workspace/files`
5. `PUT /api/claws/:claw_id/workspace/files/content`
6. `POST /api/claws/:claw_id/runs`
7. `GET /api/claws/:claw_id/runs`
8. `POST /api/claws/:claw_id/integrations/github/connect`
9. `POST /api/claws/:claw_id/schedules`
10. `GET /api/claws/:claw_id/approvals`
11. `POST /api/approvals/:approval_id/approve`

---

## 25. Definition of API-Complete for v1

The API layer is v1-complete when a frontend can:

* authenticate a user
* create one Claw
* observe provisioning and health state
* view and edit desired-state files
* trigger manual work
* inspect run history and artifacts
* connect GitHub
* create and toggle schedules
* review and resolve approvals
* pause, resume, restart, and recover the Claw
* view usage and billing summary

