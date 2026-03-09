# LaunchClaw v1 — Implementation PRD

## Status

Draft v1

## Summary

LaunchClaw lets a user launch a persistent AI worker called a **Claw**. Each Claw has its own isolated runtime, workspace, configuration, secrets, integrations, and activity history.

The product has two surfaces:

- **Launch Console**: control plane for signup, billing, create-flow, integrations, lifecycle, and recovery
- **Claw Workspace**: the day-to-day environment where the user works with the Claw

The design principle is:

> launch from the console, then mostly live inside the Claw

This v1 intentionally avoids building a full “digital employee” platform. It does not include provisioned Gmail, phone numbers, deep social identity, plugin marketplace, or multi-Claw team orchestration.

---

## Goals

### Product goals

- Let a user create one useful Claw quickly
- Make the Claw usable from its own workspace, not from a bloated admin dashboard
- Keep the runtime isolated and operationally simple
- Support one strong launch integration: **GitHub**
- Support minimal but non-zero scheduling
- Support minimal approvals for consequential actions
- Keep configuration relatively raw and inspectable rather than hiding too much state behind forms

### User goals

- Sign up and launch a working Claw in minutes
- Open the Claw Workspace immediately after launch
- Connect GitHub
- Run work manually
- See files, outputs, and activity
- Configure a few schedules
- Approve or deny a small class of sensitive actions
- Avoid managing servers or infrastructure

### Technical goals

- One isolated runtime per Claw
- No direct public ingress to Claw runtime
- Durable storage for workspace files and artifacts
- Per-Claw secret scoping
- Safe restart/pause/resume lifecycle
- Clear object model that can later support more runtimes or more integrations

---

## NonGoals

- No Gmail provisioning
- No phone number provisioning
- No WhatsApp / Signal / Discord
- No plugin marketplace
- No multi-agent orchestration
- No multi-user org/team model in v1
- No rich enterprise RBAC
- No broad approval framework
- No advanced scheduling DSL
- No fine-grained workflow builder
- No hidden “magic” config layer that users cannot inspect

---

## Product Principles

- The **Claw is the product**; the website is the control plane
- Prefer **file-first state** over hidden dashboard-only state
- Keep security boundaries real
- Optimize for **time to first useful Claw**
- Ship minimal operational surface area
- Prefer raw and legible over overdesigned and clever

---

## Scope

### In scope for v1

- Single-user accounts
- One active Claw per user
- Launch Console
- Claw Workspace
- Preset-based create flow
- BYOK or managed model access
- GitHub integration
- Minimal scheduling
- Minimal approval flow
- Files and artifacts
- Activity feed and logs
- Pause / resume / restart
- Billing shell
- Usage tracking shell

### Out of scope for v1

- Multiple active Claws per user
- Teams and orgs
- Multiple launch integrations
- Telegram-first experience
- Claw-generated identity stack
- Arbitrary plugin install
- Deep automation builder
- Marketplace or template store

---

## User Stories

### Signup and launch

As a new user, I can sign up, choose a preset, name my Claw, choose model access, optionally connect GitHub, and launch.

### Open workspace

As a user, after launch I land directly inside the Claw Workspace.

### Assign work

As a user, I can ask the Claw to do work and see outputs, logs, and generated artifacts.

### Connect GitHub

As a user, I can connect GitHub and see the connection health.

### Configure scheduling

As a user, I can set a small number of recurring jobs.

### Review approvals

As a user, I can approve or deny a small class of external or destructive actions.

### Manage lifecycle

As a user, I can pause, resume, restart, or recover the Claw from the Launch Console.

### Rotate secrets

As a user, I can replace secrets without seeing their prior values.

---

## UX Overview

## Surfaces

### 1. Launch Console

Primary responsibilities:

- auth and account entry
- create-Claw flow
- billing and usage
- integration connection and rotation
- lifecycle controls
- recovery
- link to open workspace

Main screens:

- `/app`
- `/app/create`
- `/app/billing`
- `/app/settings`
- `/app/claw/:id/overview`

### 2. Claw Workspace

Primary responsibilities:

- work with the Claw
- inspect files and outputs
- review activity
- approve/deny actions
- edit raw-ish config
- inspect integration state

Main screens:

- `/workspace/:id/work`
- `/workspace/:id/files`
- `/workspace/:id/activity`
- `/workspace/:id/integrations`
- `/workspace/:id/settings`

---

## Onboarding Flow

1. User signs up
2. User enters Launch Console
3. User clicks **Create Claw**
4. User selects preset
5. User enters Claw name
6. User selects model access mode
   - BYOK
   - Managed
7. User optionally connects GitHub
8. User clicks **Launch**
9. Provisioning starts
10. User is redirected to Claw Workspace when healthy

Deferred until after launch:

- advanced schedules
- extra integrations
- avatar customization
- advanced rules editing
- multiple approval policies

---

## Functional Requirements

## FR1. Claw creation

The system must let a user create one Claw from a preset.

Inputs:

- `name`
- `preset_id`
- `model_access_mode`
- optional GitHub connection

Output:

- provisioned Claw record
- runtime task launched
- workspace seeded
- initial status set

## FR2. Workspace state model

Each Claw must have a workspace with two classes of files:

### Desired-state files

Editable by user and control plane:

- `profile.md`
- `mission.md`
- `rules.md`
- `schedule.yaml`
- `integrations.yaml`

### Working-state files

Produced during operation:

- drafts
- outputs
- reports
- repo clones / workspace artifacts
- logs metadata

The system should allow raw editing for desired-state files with minimal guardrails.

## FR3. GitHub integration

The system must support connecting a GitHub account or installation to a Claw.

Minimum capabilities:

- connect/disconnect
- health status
- store integration metadata
- allow Claw to read/write only through allowed scopes
- support approval gate for sensitive actions

The first version does not need a full GitHub app surface. It can start with a narrower capability model.

## FR4. Scheduling

The system must support minimal scheduling.

Minimum scope:

- create a named schedule
- enable/disable a schedule
- define one cron-like expression or simple recurrence
- trigger a Run from the schedule
- show `last_run_at` and `next_run_at`

No complex workflow chaining in v1.

## FR5. Approvals

The system must support minimal approvals.

Approval-required action classes in v1:

- destructive filesystem action outside allowed workspace zones
- external write action through GitHub that is not explicitly whitelisted
- optionally: PR merge or direct push if supported in first GitHub cut

Approval UX:

- pending approval item appears in workspace/activity
- user can approve or deny
- action is either executed or cancelled
- approval result is logged

No policy engine in v1.

## FR6. Lifecycle controls

The system must support:

- pause
- resume
- restart

These actions are initiated from Launch Console and reflected in Workspace state.

## FR7. Logging and activity

The system must expose:

- Claw status
- run history
- lifecycle events
- schedule events
- approval events
- integration health events

## FR8. Secret management

The system must support per-Claw secrets.

Requirements:

- create
- replace
- revoke
- never reveal after save
- scope to one Claw
- inject only needed secrets into runtime

## FR9. Billing and usage shell

The system must maintain enough product structure for billing and usage even if monetization details evolve later.

Requirements:

- store billing customer
- store plan
- show current usage summary
- show model access mode
- support future metering

---

## Non-Functional Requirements

### Security

- one runtime per Claw
- no shared filesystem across Claws
- no public inbound access to runtime
- per-Claw secret scoping
- audit trail for lifecycle and approval actions

### Reliability

- idempotent provisioning
- restartable runtime
- recoverable from failed provisioning
- activity logs persisted centrally

### Performance

- launch flow should feel responsive
- workspace should open before every noncritical background sync finishes
- status should refresh near-real-time or on short polling

### Operability

- logs centralized
- provisioning observable
- runtime health visible
- failure states explicit

---

## Entity Model

## User

Represents an account holder.

Fields:

- `id`
- `email`
- `name`
- `auth_provider`
- `billing_customer_id`
- `created_at`
- `updated_at`

## Claw

Main product entity.

Fields:

- `id`
- `user_id`
- `name`
- `preset_id`
- `status`
- `runtime_provider`
- `model_access_mode`
- `workspace_bucket_path`
- `current_task_ref`
- `created_at`
- `updated_at`
- `last_active_at`

### Claw status enum

- `creating`
- `provisioning`
- `healthy`
- `degraded`
- `paused`
- `restarting`
- `failed`
- `deleted`

## Preset

Template used to seed a Claw.

Fields:

- `id`
- `slug`
- `name`
- `description`
- `seed_profile_md`
- `seed_mission_md`
- `seed_rules_md`
- `default_schedule_yaml`
- `default_integrations_yaml`
- `is_active`
- `created_at`
- `updated_at`

## WorkspaceFile

Logical file entry.

Fields:

- `id`
- `claw_id`
- `path`
- `kind`
- `content_type`
- `storage_ref`
- `version`
- `is_desired_state`
- `created_at`
- `updated_at`

### Workspace file kind enum

- `profile`
- `mission`
- `rules`
- `schedule`
- `integration_config`
- `artifact`
- `draft`
- `output`
- `misc`

## Run

Unit of work.

Fields:

- `id`
- `claw_id`
- `trigger_type`
- `status`
- `input_summary`
- `started_at`
- `ended_at`
- `approval_state`
- `token_usage`
- `cost_estimate`
- `created_at`
- `updated_at`

### Run trigger enum

- `manual`
- `schedule`
- `integration_event`
- `system`

### Run status enum

- `queued`
- `running`
- `waiting_approval`
- `succeeded`
- `failed`
- `cancelled`

## Integration

Connected external system.

Fields:

- `id`
- `claw_id`
- `provider`
- `status`
- `external_account_ref`
- `scope_summary`
- `config_json`
- `created_at`
- `updated_at`

### Integration provider enum

- `github`

### Integration status enum

- `pending`
- `connected`
- `degraded`
- `disconnected`
- `revoked`

## Secret

Per-Claw secret metadata.

Fields:

- `id`
- `claw_id`
- `provider`
- `label`
- `secret_ref`
- `status`
- `last_rotated_at`
- `created_at`
- `updated_at`

## Schedule

Recurring trigger.

Fields:

- `id`
- `claw_id`
- `name`
- `schedule_expr`
- `enabled`
- `last_run_at`
- `next_run_at`
- `created_at`
- `updated_at`

## Approval

Minimal approval entity.

Fields:

- `id`
- `claw_id`
- `run_id`
- `action_type`
- `payload_summary`
- `status`
- `requested_at`
- `resolved_at`
- `resolved_by_user_id`

### Approval status enum

- `pending`
- `approved`
- `denied`
- `expired`

## Artifact

Durable output.

Fields:

- `id`
- `run_id`
- `claw_id`
- `kind`
- `path`
- `storage_ref`
- `size_bytes`
- `created_at`

## BillingAccount

Minimal billing shell.

Fields:

- `id`
- `user_id`
- `provider`
- `provider_customer_ref`
- `plan`
- `status`
- `created_at`
- `updated_at`

---

## State Machines

## Claw lifecycle

`creating -> provisioning -> healthy`

Possible transitions:

- `healthy -> paused`
- `paused -> healthy`
- `healthy -> restarting -> healthy`
- `provisioning -> failed`
- `healthy -> degraded`
- `degraded -> restarting`
- `failed -> provisioning` via recovery

## Run lifecycle

`queued -> running -> succeeded`
`queued -> running -> failed`
`queued -> running -> waiting_approval -> running -> succeeded`
`queued -> cancelled`

## Approval lifecycle

`pending -> approved`
`pending -> denied`
`pending -> expired`

---

## API Surface

## Auth

Handled primarily through Supabase auth. Backend trusts authenticated session or service token.

---

## Claws

### `POST /api/claws`

Create a Claw.

Request:
```json
{
  "name": "My Claw",
  "preset_id": "preset_dev_assistant",
  "model_access_mode": "byok",
  "connect_github": true
}
````

Response:

```json
{
  "id": "claw_123",
  "status": "creating"
}
```

### `GET /api/claws/:id`

Get Claw summary.

### `POST /api/claws/:id/pause`

Pause a Claw.

### `POST /api/claws/:id/resume`

Resume a Claw.

### `POST /api/claws/:id/restart`

Restart a Claw.

### `POST /api/claws/:id/recover`

Retry recovery/provisioning flow.

---

## Workspace

### `GET /api/claws/:id/workspace/files`

List workspace files.

### `GET /api/claws/:id/workspace/files/content?path=mission.md`

Get file content.

### `PUT /api/claws/:id/workspace/files/content`

Update file content.

Request:

```json
{
  "path": "mission.md",
  "content": "# Mission\n..."
}
```

### `POST /api/claws/:id/workspace/run`

Trigger a manual Run.

Request:

```json
{
  "input": "Review the open PRs in the repo and summarize blockers."
}
```

Response:

```json
{
  "run_id": "run_123",
  "status": "queued"
}
```

---

## Runs

### `GET /api/claws/:id/runs`

List runs.

### `GET /api/runs/:run_id`

Get run detail.

### `GET /api/runs/:run_id/artifacts`

List artifacts.

---

## Integrations

### `POST /api/claws/:id/integrations/github/connect`

Start GitHub connect flow.

### `POST /api/claws/:id/integrations/:integration_id/disconnect`

Disconnect GitHub integration.

### `GET /api/claws/:id/integrations`

List integrations.

---

## Secrets

### `POST /api/claws/:id/secrets`

Create or replace secret.

Request:

```json
{
  "provider": "openai",
  "label": "OPENAI_API_KEY",
  "value": "sk-..."
}
```

Response:

```json
{
  "id": "secret_123",
  "status": "active"
}
```

### `DELETE /api/claws/:id/secrets/:secret_id`

Revoke secret.

---

## Scheduling

### `GET /api/claws/:id/schedules`

List schedules.

### `POST /api/claws/:id/schedules`

Create schedule.

Request:

```json
{
  "name": "Morning PR review",
  "schedule_expr": "0 9 * * 1-5",
  "enabled": true
}
```

### `PUT /api/claws/:id/schedules/:schedule_id`

Update schedule.

### `POST /api/claws/:id/schedules/:schedule_id/toggle`

Enable or disable schedule.

---

## Approvals

### `GET /api/claws/:id/approvals`

List pending and recent approvals.

### `POST /api/approvals/:approval_id/approve`

Approve action.

### `POST /api/approvals/:approval_id/deny`

Deny action.

---

## Billing

### `GET /api/billing/me`

Get billing summary.

### `POST /api/billing/checkout`

Create checkout session.

---

## Internal / Service APIs

These are backend-only and not public client APIs.

### `POST /internal/provisioning/claws/:id/start`

Provision runtime, seed workspace, inject secrets, mark state.

### `POST /internal/provisioning/claws/:id/stop`

Stop runtime.

### `POST /internal/provisioning/claws/:id/restart`

Restart runtime.

### `POST /internal/runs/:run_id/status`

Push run status updates.

### `POST /internal/approvals`

Create pending approval record.

---

## DB Schema Draft

## users

```sql
create table users (
  id uuid primary key,
  email text unique not null,
  name text,
  auth_provider text not null,
  billing_customer_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## presets

```sql
create table presets (
  id uuid primary key,
  slug text unique not null,
  name text not null,
  description text,
  seed_profile_md text,
  seed_mission_md text,
  seed_rules_md text,
  default_schedule_yaml text,
  default_integrations_yaml text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## claws

```sql
create table claws (
  id uuid primary key,
  user_id uuid not null references users(id) on delete cascade,
  name text not null,
  preset_id uuid references presets(id),
  status text not null,
  runtime_provider text not null default 'fargate',
  model_access_mode text not null,
  workspace_bucket_path text,
  current_task_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_active_at timestamptz
);

create index claws_user_id_idx on claws(user_id);
```

## workspace_files

```sql
create table workspace_files (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  path text not null,
  kind text not null,
  content_type text,
  storage_ref text not null,
  version integer not null default 1,
  is_desired_state boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (claw_id, path)
);

create index workspace_files_claw_id_idx on workspace_files(claw_id);
```

## runs

```sql
create table runs (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  trigger_type text not null,
  status text not null,
  input_summary text,
  started_at timestamptz,
  ended_at timestamptz,
  approval_state text,
  token_usage bigint,
  cost_estimate numeric(12, 4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index runs_claw_id_idx on runs(claw_id);
create index runs_status_idx on runs(status);
```

## integrations

```sql
create table integrations (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  provider text not null,
  status text not null,
  external_account_ref text,
  scope_summary text,
  config_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index integrations_claw_id_idx on integrations(claw_id);
```

## secrets

```sql
create table secrets (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  provider text not null,
  label text not null,
  secret_ref text not null,
  status text not null default 'active',
  last_rotated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index secrets_claw_id_idx on secrets(claw_id);
```

## schedules

```sql
create table schedules (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  name text not null,
  schedule_expr text not null,
  enabled boolean not null default true,
  last_run_at timestamptz,
  next_run_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index schedules_claw_id_idx on schedules(claw_id);
```

## approvals

```sql
create table approvals (
  id uuid primary key,
  claw_id uuid not null references claws(id) on delete cascade,
  run_id uuid references runs(id) on delete set null,
  action_type text not null,
  payload_summary text,
  status text not null,
  requested_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by_user_id uuid references users(id) on delete set null
);

create index approvals_claw_id_idx on approvals(claw_id);
create index approvals_status_idx on approvals(status);
```

## artifacts

```sql
create table artifacts (
  id uuid primary key,
  run_id uuid not null references runs(id) on delete cascade,
  claw_id uuid not null references claws(id) on delete cascade,
  kind text not null,
  path text not null,
  storage_ref text not null,
  size_bytes bigint,
  created_at timestamptz not null default now()
);

create index artifacts_run_id_idx on artifacts(run_id);
create index artifacts_claw_id_idx on artifacts(claw_id);
```

## billing_accounts

```sql
create table billing_accounts (
  id uuid primary key,
  user_id uuid not null references users(id) on delete cascade,
  provider text not null,
  provider_customer_ref text not null,
  plan text not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index billing_accounts_user_id_idx on billing_accounts(user_id);
```

---

## Architecture

## Control plane

* Next.js + React frontend
* Supabase auth
* Postgres for product state
* API service for orchestration, integrations, usage, and lifecycle
* Stripe for billing shell

## Runtime plane

* one ECS Fargate task per Claw
* no direct public ingress to task
* API/provisioning service mediates lifecycle
* secrets injected per Claw
* logs shipped centrally

## Durable storage

* S3-compatible object storage for workspace files and artifacts
* DB stores metadata, paths, versions, and indexes
* do not rely on task-local disk for durability

## Scheduling subsystem

* simple scheduler service or queue worker
* reads schedules
* enqueues Runs
* updates `last_run_at` and `next_run_at`

## Approval subsystem

* runtime emits approval request to backend
* backend persists approval
* workspace surfaces pending item
* user resolution is sent back to backend
* backend notifies runtime / unblocks run

---

## Security Notes

* no public inbound access to Claw runtime
* one runtime per Claw
* secrets scoped per Claw
* secrets never re-shown after save
* desired-state files are editable, but sensitive system config should remain controlled
* all lifecycle and approval actions should be auditable
* GitHub actions that mutate external state should be minimally approval-gated

---

## Open Product Decisions

These are intentionally unresolved enough to avoid blocking build, but narrow enough to code around.

### Presets

Presets must be easy to add and change. v1 should not overfit to one “perfect preset.”

### GitHub permissions model

Need to decide the minimal scope and exact write capabilities for launch.

### Scheduling UX

Need to decide whether to expose raw cron first or a simpler recurrence UI that compiles to cron-like expressions.

### Minimal approval triggers

Need final list of actions that require approval in v1.

### Workspace rawness

Current direction: keep it fairly raw. Desired-state files should be visible and editable, not overly abstracted.

---

## Milestone Checklist

## Milestone 0 — Repo foundation

* [ ] monorepo or repo layout chosen
* [ ] shared types package created
* [ ] env var strategy defined
* [ ] local dev setup documented

## Milestone 1 — Control plane shell

* [ ] auth implemented
* [ ] app shell created
* [ ] create-Claw wizard UI created
* [ ] billing placeholder created
* [ ] claw overview card created

## Milestone 2 — Data model and backend core

* [ ] core DB tables created
* [ ] API skeleton created
* [ ] claw creation endpoint works
* [ ] state enums and transitions implemented
* [ ] audit/event logging baseline added

## Milestone 3 — Provisioning

* [ ] provisioning service created
* [ ] Fargate task launch works
* [ ] workspace seeding works
* [ ] secret injection works
* [ ] health state updates work
* [ ] pause/resume/restart endpoints work

## Milestone 4 — Workspace

* [ ] workspace shell created
* [ ] Work tab created
* [ ] Files tab created
* [ ] Activity tab created
* [ ] Settings tab created
* [ ] raw desired-state file editing works

## Milestone 5 — Runs and artifacts

* [ ] manual run trigger works
* [ ] run state updates work
* [ ] artifact metadata persistence works
* [ ] logs/activity feed visible in UI

## Milestone 6 — GitHub integration

* [ ] GitHub connect flow works
* [ ] integration status visible
* [ ] runtime can access GitHub under allowed scope
* [ ] disconnect and reconnect flow works

## Milestone 7 — Scheduling

* [ ] create schedule
* [ ] enable/disable schedule
* [ ] scheduler triggers runs
* [ ] last/next run visible

## Milestone 8 — Minimal approvals

* [ ] approval entity and API created
* [ ] runtime can pause for approval
* [ ] pending approvals visible in workspace
* [ ] approve/deny flow works
* [ ] approved action resumes correctly

## Milestone 9 — Hardening

* [ ] provisioning retry path works
* [ ] failed state recovery works
* [ ] secret rotation tested
* [ ] restart semantics tested
* [ ] observability dashboard baseline added

---

## Suggested Repo Layout

```text
/apps
  /web                # Next.js app for Launch Console + Workspace
  /api                # Python API service
/services
  /provisioner        # runtime provisioning and lifecycle
  /scheduler          # minimal schedule executor
  /worker             # optional async jobs
/packages
  /types              # shared schemas / enums
  /config             # shared config helpers
  /ui                 # shared UI components
/docs
  PRD.md
  ARCHITECTURE.md
  API.md
  SECURITY.md
```

---

## First Build Order

1. data model
2. create-Claw API
3. Fargate provisioning path
4. workspace shell
5. manual runs
6. file editing
7. GitHub integration
8. scheduling
9. approvals
10. billing hardening

---

## Definition of Done for v1

LaunchClaw v1 is done when a new user can:

* sign up
* create one Claw
* choose BYOK or managed model access
* connect GitHub
* launch into a working workspace
* trigger manual work
* see files, outputs, and activity
* define at least one recurring schedule
* approve or deny at least one sensitive action class
* pause, resume, and restart the Claw

```


