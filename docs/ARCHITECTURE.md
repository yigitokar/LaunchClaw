# LaunchClaw v1 — Architecture

## Status

Draft v1

## Purpose

This document defines the technical architecture for LaunchClaw v1.

It covers:

- system boundaries
- control plane vs runtime plane
- Fargate task model
- durable storage model
- GitHub integration architecture
- scheduling and approvals
- security boundaries
- operational flows

This document is intentionally implementation-oriented. It is not a product pitch.

---

## 1. System Overview

LaunchClaw has two major planes:

### Control plane

The control plane is responsible for:

- auth
- billing
- user and Claw records
- provisioning requests
- integration connection flows
- lifecycle actions
- schedule management
- approval management
- logs and activity aggregation

Primary components:

- Next.js web app
- API service
- Postgres
- provisioning service
- scheduler service
- object storage metadata layer

### Runtime plane

The runtime plane is responsible for:

- running one Claw
- executing work
- reading desired-state files
- producing outputs and artifacts
- requesting approvals when required
- interacting with GitHub under bounded credentials

Primary component:

- one ECS Fargate task per Claw

The runtime plane is deliberately thin. It should not become a second control plane.

---

## 2. High-Level Architecture

```text
[ Browser ]
    |
    v
[ Next.js Web App ]
    |
    v
[ API Service ]
    | \
    |  \
    |   +--> [ Postgres ]
    |   +--> [ S3 / Object Storage ]
    |   +--> [ Secrets Manager ]
    |   +--> [ Scheduler Service ]
    |   +--> [ Provisioner ]
    |
    +------------------------------+
                                   |
                                   v
                        [ ECS / Fargate Task per Claw ]
                                   |
                                   +--> GitHub API
                                   +--> S3 / Object Storage
                                   +--> API callbacks
````

The system should keep durable state in managed services and treat the Fargate task as replaceable. This matters because Fargate tasks use `awsvpc` networking and are designed around isolated task execution rather than being the durable system of record. AWS documents that Fargate tasks require `awsvpc` network mode, and that task IAM roles and task execution roles are separate concerns. ([AWS Documentation][1])

---

## 3. Runtime Decision

## Chosen runtime: ECS on Fargate

Each Claw runs as one isolated ECS task on AWS Fargate.

### Why Fargate

The architecture wants one runtime per Claw, minimal host management, and strong isolation boundaries. Fargate removes the need to manage EC2 hosts while still giving each task its own networking boundary via `awsvpc`. AWS’s documentation also distinguishes task roles, which are exposed to the application container, from execution roles, which are used by ECS/Fargate agents for image pulls, logs, and secret retrieval. That separation maps well to LaunchClaw’s security model. ([AWS Documentation][1])

### Why not rely on task-local state

Fargate ephemeral storage is not the source of truth for workspace state. The task should be restartable and replaceable without data loss. Durable state lives outside the task, in Postgres and object storage.

---

## 4. Component Breakdown

## 4.1 Web App

**Technology**: Next.js + React

Responsibilities:

* user auth entrypoints
* create-Claw flow
* billing and usage pages
* workspace UI
* files UI
* activity UI
* approvals UI
* GitHub connect/disconnect flows

The web app should call backend APIs only. It should not talk directly to AWS control APIs or GitHub token minting paths.

---

## 4.2 API Service

**Suggested technology**: Python + FastAPI

Responsibilities:

* authenticated API surface for web client
* CRUD for Claws, files, schedules, integrations, approvals
* orchestration entrypoint for provisioning
* lifecycle actions: pause, resume, restart, recover
* run creation and tracking
* artifact metadata registration
* GitHub integration state management
* approval state changes
* audit and activity event recording

The API service is the control-plane brain.

It should be stateless and horizontally scalable.

---

## 4.3 Postgres

**Suggested provider**: Supabase Postgres

Responsibilities:

* user records
* Claw metadata
* run metadata
* integration metadata
* schedule metadata
* approval metadata
* artifact metadata
* billing/account metadata
* event/audit records

Postgres is the system of record for product state.

It should not store large artifacts or large file blobs unless there is a very specific reason.

---

## 4.4 Object Storage

**Suggested provider**: S3

Responsibilities:

* desired-state file contents
* versioned file blobs
* generated artifacts
* logs snapshots if needed
* exported reports
* repo snapshots if retained

The DB stores metadata and references. S3 stores durable file content.

### Why S3 instead of local task disk

Task-local disk disappears with task replacement. Durable files and artifacts must survive pause, restart, or reprovisioning. ECS also supports using S3-backed environment files, but AWS explicitly warns that environment files are subject to S3 security considerations and recommends Secrets Manager or Parameter Store for sensitive data. Sensitive config must not be smuggled through generic env files. ([AWS Documentation][2])

---

## 4.5 Secrets Manager

**Suggested provider**: AWS Secrets Manager

Responsibilities:

* store per-Claw secrets
* store app secrets used by control plane
* support rotation/replacement
* provide runtime secret injection

### Important design note

For v1, Secrets Manager can be used to inject secrets into ECS containers, but AWS explicitly notes two important caveats:

* secret values injected as environment variables are only loaded at container start and do not auto-refresh after rotation
* applications, logs, and debugging tools inside the container can access environment variables ([AWS Documentation][3])

So the architecture should treat env-var injection as acceptable for v1 but imperfect. Any secret rotation that affects the runtime should trigger a restart or reprovision. Longer term, higher-risk credentials may need fetch-on-demand or brokered access.

---

## 4.6 Provisioner

**Suggested technology**: Python service or internal module with queue-backed workers

Responsibilities:

* accept a desired Claw spec
* materialize task definition inputs
* create or update ECS task launch request
* seed workspace files to object storage
* bind secret references
* register runtime metadata
* transition Claw state
* recover failed provisioning

The Provisioner should be idempotent. A repeated call with the same desired Claw spec should not create duplicate runtime state.

---

## 4.7 Scheduler

**Suggested technology**: small service or worker process

Responsibilities:

* periodically scan enabled schedules
* compute due work
* enqueue Runs
* update `last_run_at`
* update `next_run_at`

Scheduling should be minimal in v1. It exists to trigger simple recurring work, not to become a workflow orchestration engine.

---

## 4.8 Runtime Worker (Claw)

Each Claw task contains the runtime process that:

* loads desired-state files
* receives run requests
* executes work
* reads and writes workspace content
* talks to GitHub
* creates artifacts
* emits status and activity events
* requests approvals when required

This runtime should be single-tenant to the Claw.

It should not host multiple users or multiple Claws.

---

## 5. Fargate Task Model

## 5.1 One task per Claw

Each Claw maps to one Fargate task.

That task should have:

* one task definition family for Claw runtime
* one task IAM role
* one task execution role
* one ENI via `awsvpc`
* no public IP unless there is a very specific reason
* outbound access through NAT or controlled egress path if needed

AWS documents that Fargate requires `awsvpc` network mode, and that the task execution role is separate from the task role used by the application inside the container. ([AWS Documentation][1])

## 5.2 Task roles

### Task execution role

Used by ECS/Fargate infrastructure for:

* pulling image from ECR
* sending logs to CloudWatch
* retrieving referenced Secrets Manager values at start
* other ECS agent-level needs ([AWS Documentation][4])

### Task role

Used by the Claw runtime application itself for:

* reading and writing S3 workspace objects
* calling API callbacks if needed through AWS-authenticated channels
* reading any AWS resources that the application genuinely needs

The task role must be narrow.

Do not let the Claw runtime assume broad infra privileges.

## 5.3 Task sizing

Start with a conservative fixed task size for v1. Do not over-optimize early.

Suggested v1 approach:

* one standard size for all Claws
* maybe one larger internal debug size
* revisit dynamic sizing only after real usage data exists

## 5.4 Runtime lifecycle

### Create

* Claw record created
* Provisioner prepares workspace seed
* ECS task started
* task reports healthy
* Claw state becomes `healthy`

### Pause

* control plane requests stop
* runtime flushes state if needed
* ECS task stops
* Claw state becomes `paused`

### Resume

* control plane starts new task using same desired state
* task rehydrates from durable storage
* Claw state becomes `healthy`

### Restart

* controlled stop/start
* preserves durable state
* useful after secret rotation or bad runtime state

### Recover

* used when provisioning or runtime health fails
* may create a fresh task
* should not lose durable workspace state

---

## 6. Storage Model

## 6.1 Principle

Durable state lives outside the task.

The runtime is disposable.
The workspace is durable.

## 6.2 Data classes

### Class A: product metadata in Postgres

Examples:

* users
* claws
* runs
* schedules
* integrations
* approvals
* artifacts metadata

### Class B: file/blob data in object storage

Examples:

* `mission.md`
* `rules.md`
* generated reports
* repository snapshots if persisted
* exported artifacts
* raw output blobs

### Class C: ephemeral compute-local state

Examples:

* current cloned repo
* temp files
* scratch outputs
* transient caches

This state can be lost on restart.

## 6.3 Workspace layout

Recommended logical layout in object storage:

```text
s3://launchclaw-workspaces/{claw_id}/
  desired/
    profile.md
    mission.md
    rules.md
    schedule.yaml
    integrations.yaml
  artifacts/
    {run_id}/...
  outputs/
    {run_id}/...
  system/
    snapshots/
```

The control plane should treat desired-state files as versioned records. Every update should either create a new blob version or at least a new content hash.

## 6.4 File editing model

For v1, desired-state files are relatively raw.

The UI can offer form helpers later, but the underlying truth should remain file-based and inspectable.

That makes the system easier to debug and easier to move between presets.

---

## 7. Network Model

## 7.1 Control-plane ingress

Public traffic enters through the web app and API only.

No direct public ingress to Claw runtimes.

## 7.2 Runtime networking

Each Fargate task gets its own ENI under `awsvpc`. AWS documents this as the required Fargate network mode. ([AWS Documentation][1])

Recommended v1 pattern:

* private subnets for Claw tasks
* no public IP for Claw tasks
* NAT or controlled egress path for outbound access
* security groups scoped tightly
* allow outbound HTTPS
* do not expose inbound ports to the internet

## 7.3 Runtime-to-control-plane communication

Two acceptable v1 patterns:

### Pattern A: pull-based

The runtime polls the API for pending work and reports status back.

This is operationally simple and avoids inbound connectivity.

### Pattern B: queue-based

The control plane enqueues work and the runtime consumes it through a queue.

This is cleaner long-term but adds another subsystem.

For v1, pull-based or simple queue-based are both fine. The key is: no direct browser-to-runtime path.

---

## 8. GitHub Integration Architecture

GitHub is the first launch integration.

## 8.1 Recommended auth model: GitHub App

Use a GitHub App, not broad personal access tokens as the primary long-term model.

Why:

* installation tokens are short-lived
* access can be limited to installed repositories
* permissions are explicit
* org installation is easier to reason about than arbitrary PAT sprawl

GitHub documents that installation access tokens expire after one hour, can be scoped to specific repositories, and can optionally request a subset of the app’s granted permissions. ([GitHub Docs][5])

## 8.2 Connection flow

Recommended flow:

1. User clicks “Connect GitHub”
2. User is redirected to GitHub App install/authorize flow
3. GitHub redirects back to LaunchClaw
4. Control plane stores installation metadata
5. Control plane associates installation with the Claw
6. Runtime never stores the app private key
7. Runtime receives short-lived installation access tokens minted by the control plane or a token broker

This is better than storing long-lived user PATs inside every Claw.

## 8.3 Token model

There are two credential layers:

### App credential

The GitHub App private key is stored only in the control plane secrets layer.

### Installation token

A short-lived installation token is minted for a specific installation and optionally limited to selected repositories and permissions. GitHub documents both the repository scoping and permission scoping of installation access tokens. ([GitHub Docs][5])

## 8.4 Permission scope for v1

Start narrow.

Likely minimum set, depending on exact features:

* repository metadata read
* contents read/write if file changes or branch creation are needed
* pull requests read/write if PR creation is needed
* webhooks read/write only if repo webhooks are managed directly
* workflows permission only if touching `.github/workflows`

GitHub recommends choosing minimum permissions and exposes accepted permissions information via headers when permissions are insufficient. ([GitHub Docs][6])

## 8.5 How the runtime gets GitHub access

Preferred v1 pattern:

* runtime asks control plane for GitHub access for a specific action
* control plane validates Claw and integration mapping
* control plane mints or retrieves a fresh installation token
* control plane returns a short-lived token or executes the GitHub operation on behalf of runtime

Even better long-term pattern:

* runtime sends signed action requests
* control plane is the only GitHub writer for sensitive operations

For v1, it is acceptable for the runtime to use short-lived installation tokens, but the app private key must remain outside the runtime.

## 8.6 Webhooks

There are two webhook categories:

### GitHub → LaunchClaw webhook

Used for installation events and optionally repo events.

This should terminate in the control plane, not in the runtime.

### LaunchClaw-managed repo hooks

Optional in v1.

If webhooks are used, the control plane should create and verify them. GitHub documents webhook-related permissions separately under repository or organization webhook permissions. ([GitHub Docs][6])

---

## 9. Scheduling Architecture

## 9.1 v1 scheduling requirements

Minimal but non-zero scheduling means:

* named schedule
* enable/disable
* cron-like expression or simple recurrence
* due job detection
* run creation
* visible last/next run

## 9.2 Design

A scheduler service periodically scans enabled schedules and enqueues Runs.

Simple loop:

1. fetch due schedules
2. create Run records
3. mark next execution time
4. notify runtime or place work in queue

Do not embed scheduling logic only inside the Claw task. Scheduling is a control-plane concern.

---

## 10. Approval Architecture

## 10.1 Principle

Approvals are minimal in v1.

They are not a full policy engine.

## 10.2 Trigger model

When runtime encounters an action requiring approval:

1. runtime pauses action execution
2. runtime creates approval request via API
3. backend stores approval record
4. UI surfaces pending item
5. user approves or denies
6. backend returns decision
7. runtime resumes or cancels

## 10.3 Candidate approval classes for v1

Good v1 candidates:

* destructive workspace action outside safe area
* external write to GitHub that is more sensitive than reading
* merge/direct push if implemented

Avoid trying to policy-engineer everything in v1.

---

## 11. Observability and Operations

## 11.1 Logs

Need at least three log streams:

* control-plane application logs
* provisioning logs
* per-Claw runtime logs

CloudWatch is fine for v1. ECS task execution roles support logging through the `awslogs` driver and related ECS logging paths. ([AWS Documentation][4])

## 11.2 Activity events

Persist user-visible activity separately from raw logs.

Examples:

* Claw created
* task healthy
* schedule triggered
* run started
* approval requested
* GitHub integration degraded
* task restarted

## 11.3 Health model

A Claw health state should be derived from:

* task running/healthy
* recent heartbeat
* last run outcome
* integration health
* provisioning state

Recommended states:

* creating
* provisioning
* healthy
* degraded
* paused
* restarting
* failed

---

## 12. Security Model

## 12.1 Core rules

* one runtime per Claw
* no shared filesystem across Claws
* no public inbound access to runtimes
* app private keys stay in control plane
* per-Claw secret scoping
* task role is narrow
* execution role is separate from task role
* durable state is outside runtime
* all lifecycle and approval actions are auditable

## 12.2 Secret injection caveat

ECS secret injection via env vars is acceptable for v1, but AWS explicitly notes that those values are visible to applications and debugging tools in the container and do not auto-refresh after rotation. Therefore:

* do not assume secret rotation is live
* restart after rotation where necessary
* avoid putting very broad credentials into every runtime if a brokered model can be used instead ([AWS Documentation][3])

## 12.3 Task IAM

Use least privilege.

The task role should only have access to:

* its own workspace prefix in S3
* exactly the AWS APIs it truly needs
* perhaps nothing beyond S3 and narrow callback permissions

The runtime should not be able to create infrastructure.

---

## 13. Failure Modes and Recovery

## 13.1 Provisioning failure

If provisioning fails:

* store failure reason
* mark Claw `failed`
* allow user-triggered recover
* make Provisioner idempotent

## 13.2 Runtime crash

If runtime task dies:

* detect through ECS/task health or heartbeat loss
* mark `degraded` or `failed`
* allow restart
* optionally auto-restart later

## 13.3 Secret rotation mismatch

If a secret changes and runtime still uses old env var:

* mark runtime restart required
* provide UI signal
* restart task

## 13.4 GitHub token expiry

GitHub installation tokens expire after one hour by design. Token refresh must be automatic through the control plane or token broker. ([GitHub Docs][5])

---

## 14. Suggested Internal Service Boundaries

Recommended internal modules/services:

* `api`: public authenticated API
* `provisioner`: runtime provisioning and lifecycle
* `scheduler`: due schedule executor
* `token-broker`: GitHub installation token minting
* `runtime`: Claw process image
* `audit`: shared event persistence utilities

For v1, `token-broker` can be a module inside the API service. It does not need to be a separate deployable service unless traffic or security boundaries force it.

---

## 15. Recommended Build Sequence

1. Postgres schema and enums
2. API skeleton
3. Claw creation flow
4. Provisioner and Fargate task startup
5. S3-backed workspace files
6. runtime heartbeat and logs
7. manual Runs
8. GitHub App integration
9. scheduler
10. approvals
11. restart/recover hardening

---

## 16. Explicit v1 Tradeoffs

These are deliberate.

We are choosing:

* Fargate over EC2 for lower ops burden
* durable state outside runtime
* GitHub App over PAT-first design
* short-lived installation tokens over broad long-lived repo credentials
* raw-ish file editing over fully abstracted dashboard config
* minimal scheduling over workflow-engine complexity
* minimal approvals over policy-engine complexity

---

## 17. Future Evolutions

Likely future upgrades:

* runtime abstraction supporting EC2 pools later
* multi-Claw accounts
* org/team model
* more integrations
* richer approval policies
* partial move from env-var secret injection to brokered secret access
* runtime queue model instead of polling
* richer file/version UX

```

::contentReference[oaicite:14]{index=14}
```

[1]: https://docs.aws.amazon.com/en_us/AmazonECS/latest/developerguide/task_definition_parameters.html?utm_source=chatgpt.com "Amazon ECS task definition parameters for Fargate - Amazon Elastic Container Service"
[2]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/use-environment-file.html?utm_source=chatgpt.com "Pass environment variables to an Amazon ECS container - Amazon Elastic Container Service"
[3]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html?utm_source=chatgpt.com "Pass Secrets Manager secrets through Amazon ECS environment variables - Amazon Elastic Container Service"
[4]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html?utm_source=chatgpt.com "Amazon ECS task execution IAM role - Amazon Elastic Container Service"
[5]: https://docs.github.com/en/rest/apps/apps?utm_source=chatgpt.com "REST API endpoints for GitHub Apps - GitHub Docs"
[6]: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps?utm_source=chatgpt.com "Permissions required for GitHub Apps - GitHub Docs"
