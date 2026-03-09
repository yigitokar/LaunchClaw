# LaunchClaw v1 — Security

## Status

Draft v1

## Purpose

This document defines the security model for LaunchClaw v1.

It covers:

- trust boundaries
- threat model
- authentication and authorization
- runtime isolation
- network security
- secrets handling
- GitHub integration security
- approvals and guardrails
- audit logging
- operational security requirements
- incident response and recovery

This is a build document. It is intentionally specific.

---

## 1. Security Goals

LaunchClaw v1 must satisfy the following goals:

1. A compromise of one Claw should not imply compromise of another Claw.
2. A compromise of one Claw should not imply compromise of the control plane.
3. Sensitive credentials should be scoped narrowly and exposed for the shortest practical time.
4. Durable state must survive task replacement, restart, and recovery.
5. Sensitive actions with external side effects must be gated or auditable.
6. The system must favor revocability and recoverability over convenience.
7. Security posture must be understandable by engineering, not hidden in vendor defaults.

---

## 2. Non-Goals

v1 does **not** attempt to solve:

- zero-trust formal verification
- confidential computing / enclave-based execution
- customer-managed keys for every tenant path
- complete data residency controls
- enterprise RBAC beyond single-user ownership
- full policy-engine approvals
- browser isolation or arbitrary untrusted plugin execution
- provisioned email/phone identity systems

---

## 3. System Security Model

LaunchClaw has two primary planes:

### 3.1 Control plane

The control plane includes:

- web app
- API service
- database
- provisioner
- scheduler
- billing integration
- token broker / GitHub App credential handling
- audit/event services

The control plane is the source of truth for account state, Claw metadata, integration metadata, approvals, and lifecycle operations.

### 3.2 Runtime plane

The runtime plane is the Claw itself.

Each Claw runs as one isolated ECS task on AWS Fargate. Fargate workloads run in isolated environments; AWS documents that Fargate tasks do not share the operating system, Linux kernel, network interface, ephemeral storage, CPU, or memory with other tasks.[^aws-fargate-shared-model]

The runtime is treated as replaceable. It is **not** the source of truth for durable state.

### 3.3 Trust boundaries

Primary trust boundaries:

1. Browser ↔ control plane
2. Control plane ↔ AWS infrastructure APIs
3. Control plane ↔ runtime
4. Runtime ↔ GitHub
5. Runtime ↔ object storage
6. Control plane ↔ secrets systems

The runtime is less trusted than the control plane.

Consequence:

- control-plane secrets are never broadly shared with the runtime
- GitHub App private key remains in control plane only
- runtime receives short-lived and action-bounded credentials where possible
- runtime is denied infrastructure mutation privileges

---

## 4. Threat Model

### 4.1 Assets to protect

Highest-value assets:

- GitHub App private key
- user model API keys
- LaunchClaw-managed provider keys
- user workspace data
- Claw desired-state files
- GitHub installation mappings and installation tokens
- billing/customer identifiers
- audit trail integrity

### 4.2 Adversary classes

1. **External attacker** attempting account takeover, API abuse, or webhook forgery
2. **Compromised Claw runtime** attempting lateral movement or secret exfiltration
3. **Malicious or careless user** attempting abuse, excessive automation, or harmful integration use
4. **Compromised dependency/container image** executing inside runtime or control plane
5. **Misconfigured operator or deploy pipeline** leaking secrets or over-granting IAM

### 4.3 Main attack paths

1. Steal secrets from environment variables or logs
2. Use a compromised runtime to access infrastructure APIs
3. Forge GitHub webhook deliveries or callbacks
4. Abuse long-lived GitHub credentials to persist access
5. Use file editing or scheduling to create hidden unsafe behavior
6. Escalate from one Claw to another through shared storage, shared task roles, or shared services
7. Exfiltrate data through overly broad GitHub permissions or unrestricted outbound calls

---

## 5. Security Principles

1. **Least privilege** for every IAM role, token, repo scope, and runtime capability
2. **Single tenant runtime**: one Claw per task, never multi-tenant runtime processes
3. **Control plane as security anchor**: the most sensitive credentials stay out of the runtime
4. **Short-lived credentials over long-lived credentials** wherever practical
5. **No direct public ingress to the runtime**
6. **Durable state outside the runtime**
7. **Deny by default** for integrations, actions, and writable surfaces
8. **Auditable mutations** for lifecycle changes, secret changes, approval decisions, and GitHub writes

---

## 6. Authentication and Authorization

### 6.1 User authentication

The browser authenticates through Supabase Auth or equivalent.

Requirements:

- authenticated session required for all user APIs except health and auth bootstrap endpoints
- API resolves user identity server-side
- session validation happens on every request or through trusted session middleware
- no runtime endpoint accepts browser-originated user auth directly

### 6.2 Resource authorization

All user-facing APIs must enforce ownership.

Rules:

- user may access only their own Claw and child resources
- unauthorized access to another user’s Claw should generally return `404`, not `403`, to reduce resource enumeration
- child resources are always verified through parent ownership, not only by resource ID

### 6.3 Internal service authentication

Internal endpoints must never rely on browser auth.

Allowed mechanisms:

- private network + service token
- mTLS in the future
- workload identity / signed service credentials

Minimum v1 requirement:

- internal endpoints accept only service authentication
- runtime heartbeats, approval polling, and status callbacks are not user-callable

---

## 7. Runtime Isolation

### 7.1 One task per Claw

Each Claw runs as exactly one ECS task on Fargate.

Requirements:

- no multi-Claw processes
- no shared writable filesystem across Claws
- no shared task role across all Claws if narrower roles are possible
- no shell or exec access exposed to end users in v1

AWS documents that task roles expose permissions to containers in the task, while the execution role is used by ECS/Fargate agents and is not directly accessible to containers.[^aws-task-role][^aws-exec-role]

### 7.2 Disposable runtime

The runtime may be restarted or replaced at any time.

Therefore:

- durable data must not rely on task-local disk
- repo clones and scratch state are ephemeral
- desired-state files and generated artifacts must live in durable storage

### 7.3 Isolation outcome target

A runtime compromise should, at worst, expose:

- the Claw’s own in-memory state
- the Claw’s currently injected secrets
- the Claw’s own workspace scope
- short-lived external credentials specifically minted for that Claw

A runtime compromise must **not** grant:

- access to another Claw’s workspace
- access to the GitHub App private key
- permission to create or destroy infrastructure
- direct database access with cross-user visibility
- broad AWS account access

---

## 8. Network Security

### 8.1 Public ingress

Only the web app, API, and explicit webhook endpoints are internet-facing.

The Claw runtime is **not** publicly reachable.

### 8.2 Runtime networking

Fargate tasks use `awsvpc` networking.[^aws-taskdef-awsvpc]

Requirements:

- run Claw tasks in private subnets
- do not assign public IPs unless explicitly justified and approved
- egress through NAT or controlled egress path
- security groups must deny all inbound except strictly necessary internal traffic
- outbound should be limited to required destinations where practical

### 8.3 Runtime-to-control-plane communication

Preferred v1 patterns:

- pull-based polling to API for work/approval state
- service-authenticated callbacks from runtime to API

Forbidden pattern in v1:

- direct browser-to-runtime connectivity

### 8.4 Webhook ingress

GitHub webhooks must terminate in the control plane only.

Requirements:

- use webhook secret
- verify `X-Hub-Signature-256`
- reject unsigned or invalidly signed requests
- store only minimal raw payload retention needed for debugging and audit

GitHub recommends verifying deliveries with the webhook secret and `X-Hub-Signature-256`.[^github-webhook-signature]

---

## 9. IAM Model

### 9.1 Separation of roles

Use separate IAM roles for different trust levels.

Minimum distinct roles:

- API/control-plane runtime role
- provisioner role
- ECS task execution role
- ECS task role for Claw runtime
- optional scheduler role if separate service exists

### 9.2 Task execution role

The execution role is for ECS/Fargate platform needs such as pulling images, sending logs, and retrieving referenced secrets.[^aws-exec-role]

Requirements:

- execution role must not be reused as application role
- execution role permissions must be limited to agent/platform functions

### 9.3 Task role

The task role is for application code running inside the Claw container.[^aws-task-role]

Allowed capabilities should be narrow, e.g.:

- read/write only the Claw’s own storage prefix
- fetch only the Claw’s own work/approval context from API through service auth if needed
- no wildcard access to object storage buckets
- no permission to create ECS tasks, manage IAM, or call Secrets Manager broadly

### 9.4 Principle of explicit scoping

Policies must be scoped by concrete resource identifiers whenever feasible.

Avoid:

- `s3:*` on bucket `*`
- `secretsmanager:*` on `*`
- `iam:*` anywhere in task roles

---

## 10. Secrets Management

### 10.1 Secret classes

#### Class A: Control-plane root secrets

Examples:

- GitHub App private key
- database credentials
- Stripe secrets
- signing secrets
- service tokens

These must remain in the control plane only.

#### Class B: Per-user / per-Claw secrets

Examples:

- BYOK model keys
- repo-specific credentials if ever needed
- integration secrets scoped to one Claw

These may be injected into the runtime if required.

#### Class C: Short-lived minted credentials

Examples:

- GitHub installation access token
- session-scoped upload URLs

These should be preferred over long-lived credentials.

### 10.2 Storage requirements

Requirements:

- secrets stored in AWS Secrets Manager or equivalent secret store
- secrets never stored in plaintext in Postgres
- UI never re-displays a secret value after save
- secret metadata may be stored in Postgres
- every secret has ownership metadata and rotation timestamp

AWS recommends using Secrets Manager or Systems Manager Parameter Store for sensitive data rather than generic environment variables or S3 environment files.[^aws-secrets-ecs][^aws-env-file]

### 10.3 Injection model

v1 default:

- inject selected per-Claw secrets into the container environment at task start when necessary

Important caveat:

AWS documents that secrets injected as environment variables are loaded when the container starts, do not auto-refresh after rotation, and are accessible to applications, logs, and debugging tools inside the container.[^aws-secrets-env]

Therefore v1 policy is:

- rotation of any injected secret marks the Claw as `restart_required`
- rotation path must offer immediate restart
- secrets must never be copied into user-editable files
- runtime logs must never print secret values

### 10.4 Secret minimization

Requirements:

- inject only secrets that a given Claw actually needs
- do not inject the GitHub App private key into runtimes
- prefer brokered access for the most sensitive credentials

### 10.5 Future direction

Longer term, move high-risk secrets away from raw env-var injection toward one of:

- brokered API access
- just-in-time credential retrieval
- sign-only key vault model for app keys

---

## 11. GitHub Integration Security

### 11.1 Chosen model

Use a GitHub App as the primary GitHub integration model.

GitHub Apps can be installed on accounts and repositories, and installation access tokens can be scoped to selected repositories and permissions and expire after one hour.[^github-install-token][^github-install-auth]

This is better than depending on broad, long-lived personal access tokens.

### 11.2 Private key handling

The GitHub App private key is the most sensitive integration secret.

Requirements:

- stored only in control-plane secret store
- never shipped to browser
- never injected into Claw runtime
- never written to repo, image, or config file
- access restricted to token broker or control-plane module that mints installation tokens

GitHub explicitly describes the private key as the single most valuable secret for a GitHub App and recommends secure storage, ideally in a key vault, warning that environment-variable storage is weaker because anyone who gains access to the environment can read the key.[^github-private-key][^github-best-practices]

### 11.3 Installation tokens

Requirements:

- mint installation access tokens only in control plane
- scope tokens to required repositories where practical
- scope tokens to minimum permissions where practical
- do not cache tokens longer than necessary
- treat expired-token `401` responses as normal refresh events

GitHub documents that installation tokens expire after one hour and can be scoped by repositories and permissions.[^github-install-token][^github-install-auth]

### 11.4 Permission minimization

Requirements:

- choose minimum app permissions needed for v1
- use `X-Accepted-GitHub-Permissions` and endpoint docs to verify required permissions during development
- separate read-only actions from write actions in code paths

GitHub’s permissions docs explicitly recommend minimum permissions and expose accepted permissions information in REST responses.[^github-permissions][^github-choose-perms]

### 11.5 Sensitive GitHub actions

The following GitHub actions are security-sensitive and should be approval-gated in v1 unless explicitly whitelisted:

- creating or updating refs
- pushing content changes
- opening pull requests from generated changes
- merging pull requests
- editing workflow files
- managing repo webhooks

### 11.6 Webhooks

Requirements:

- GitHub webhooks terminate in control plane only
- verify delivery signatures before processing
- reject replayed or obviously stale payloads where feasible
- keep webhook subscriptions minimal

GitHub documentation recommends subscribing only to necessary webhook events and verifying deliveries with the webhook secret.[^github-webhook-signature]

---

## 12. Workspace and File Security

### 12.1 Desired-state files

Desired-state files are editable but controlled.

Allowed v1 examples:

- `desired/profile.md`
- `desired/mission.md`
- `desired/rules.md`
- `desired/schedule.yaml`
- `desired/integrations.yaml`

Requirements:

- only approved paths are editable through public API
- reject path traversal and path normalization abuse
- writes are versioned
- file history is auditable

### 12.2 Prohibited configuration exposure

The following must never be user-editable as raw file content in v1:

- cloud credentials
- runtime provider credentials
- task definition internals
- task IAM policy content
- app private keys
- database credentials

### 12.3 Generated files

Generated outputs may be writable by the runtime but must remain scoped to the Claw’s own storage path.

### 12.4 Repo handling

GitHub repo clones are treated as ephemeral compute-local state unless explicitly persisted as artifacts.

Do not assume a repo clone is durable or canonical.

---

## 13. Scheduling and Automation Security

### 13.1 Minimal scheduling only

Scheduling is allowed in v1 but kept deliberately small.

Requirements:

- minimum interval guardrail to prevent abuse if needed
- enabled/disabled state explicit
- every scheduled execution becomes a Run with audit trail
- schedule edits are auditable

### 13.2 No hidden autonomy

A user must be able to see:

- what schedules exist
- when they will next run
- what they last ran

Avoid hidden agent loops.

---

## 14. Approval Model

### 14.1 Purpose

Approvals are the thin safety barrier for consequential actions in v1.

They are not a complete policy engine.

### 14.2 Minimal approval classes

At minimum, approval should be required for:

- destructive workspace action outside explicitly safe paths
- GitHub write actions that mutate external state and are not pre-approved
- merge/direct push if implemented

### 14.3 Approval flow requirements

Requirements:

- runtime pauses before action execution
- approval record created in control plane
- user decision recorded with actor and timestamp
- runtime resumes or aborts based on explicit decision
- timeout or expiry behavior defined

### 14.4 Approval auditability

Every approval record must include at least:

- action type
- user-visible payload summary
- linked run ID if present
- requester identity (the Claw)
- resolver identity (the user)
- timestamps
- final decision

---

## 15. Logging, Audit, and Observability

### 15.1 Separation of concerns

There are three distinct telemetry classes:

1. **Infrastructure/application logs**
2. **User-visible activity events**
3. **Audit events**

Do not treat them as interchangeable.

### 15.2 Audit events

Must be recorded for at least:

- Claw creation
- lifecycle actions: pause/resume/restart/recover
- secret create/replace/revoke
- GitHub integration connect/disconnect
- approval requested / approved / denied / expired
- schedule create/update/toggle
- desired-state file updates

### 15.3 Logging hygiene

Requirements:

- secrets must be redacted from logs
- request bodies containing secrets must not be logged verbatim
- installation tokens must not be logged
- debug modes that expose env vars are forbidden in production

### 15.4 Heartbeats and health

Runtime should emit periodic heartbeats.

The control plane derives Claw health from:

- task lifecycle state
- recent heartbeat
- integration health
- latest run outcomes

---

## 16. Supply Chain and Build Security

### 16.1 Container images

Requirements:

- container images built from reviewed source
- pin base images where practical
- scan images in CI before release
- do not bake secrets into images
- separate dev and prod images if dev tooling materially increases attack surface

### 16.2 Dependencies

Requirements:

- lock dependency versions
- monitor known vulnerabilities
- remove unused dependencies aggressively

### 16.3 CI/CD

Requirements:

- CI secrets available only to jobs that need them
- production deploy credentials not exposed to pull-request jobs from untrusted forks
- build provenance and deployment logs retained

---

## 17. Data Protection and Retention

### 17.1 Data classes

#### Sensitive operational data

- secrets
- installation tokens
- internal service credentials

Retention: minimal, with secret values stored only in secret store.

#### User content

- desired-state files
- run inputs and outputs
- generated artifacts

Retention: product-defined; must be deletable by user or operator process.

#### Audit/security records

- lifecycle events
- approval decisions
- security-relevant changes

Retention: longer-lived than transient logs.

### 17.2 Encryption

Minimum expectation:

- TLS in transit for public endpoints
- cloud-managed encryption at rest for databases, object storage, and secret stores

### 17.3 Data deletion

Requirements:

- deleting a Claw eventually deletes or tombstones workspace metadata and secrets references
- deletion job must be idempotent
- audit records may be retained separately if required for security/integrity purposes

---

## 18. Abuse Prevention

### 18.1 Launch surface restrictions

v1 intentionally excludes the riskiest abuse surfaces:

- provisioned email accounts
- phone numbers
- broad messaging-channel automation
- arbitrary plugin marketplace

### 18.2 Rate and quota controls

Minimum requirements:

- rate limit public APIs
- limit Claw creation attempts
- minimum scheduling interval guardrail if abuse appears
- throttle repeated failed integration or webhook verification attempts

### 18.3 Kill switches

The control plane must support:

- pausing a Claw
- revoking an integration
- revoking or rotating secrets
- stopping token minting for a compromised installation

---

## 19. Incident Response and Recovery

### 19.1 Trigger conditions

Security incident triggers include:

- suspected secret leakage
- suspicious GitHub writes
- invalid webhook signature spikes
- unusual token minting activity
- runtime attempting forbidden actions
- cross-tenant access indicators

### 19.2 Immediate response actions

At minimum, operators must be able to:

- pause affected Claw
- revoke GitHub installation token path
- rotate compromised secrets
- restart or replace runtime
- preserve logs and audit trail

### 19.3 Recovery expectations

Because durable state is outside the runtime, recovering from runtime compromise should prefer:

1. revoke credentials
2. stop task
3. launch fresh task
4. rehydrate from durable state
5. verify integration health

---

## 20. Security Requirements by Component

### 20.1 Web app

Must:

- use authenticated sessions only
- avoid storing secrets in browser storage
- never expose internal service credentials
- display only secret metadata, not secret values

### 20.2 API service

Must:

- enforce authn/authz
- sanitize inputs
- redact secrets in logs
- validate file paths and approval transitions
- verify GitHub webhook signatures

### 20.3 Provisioner

Must:

- be idempotent
- use narrow infrastructure permissions
- never copy secrets into durable config files
- tag or identify tasks unambiguously by Claw

### 20.4 Runtime

Must:

- assume it is replaceable
- avoid logging secrets or full tokens
- request approval before sensitive external writes
- never store durable source of truth locally only
- never receive GitHub App private key

### 20.5 Scheduler

Must:

- create runs via control plane only
- not bypass approval or audit systems
- record due/triggered events

---

## 21. Security Checklist for v1 Launch

### Must be true before launch

- [ ] one Fargate task per Claw
- [ ] runtime has no public ingress
- [ ] task role and execution role are separate
- [ ] task role scoped narrowly
- [ ] GitHub App private key stored only in control plane secret store
- [ ] installation tokens are minted server-side only
- [ ] webhook signatures are verified with `X-Hub-Signature-256`
- [ ] secret values never returned from API after save
- [ ] secret rotation marks runtime restart required when applicable
- [ ] desired-state file edits restricted to approved paths
- [ ] approval flow exists for selected sensitive actions
- [ ] audit log exists for lifecycle, secrets, schedules, approvals, and file edits
- [ ] logs redact secrets and tokens
- [ ] deleting or pausing a Claw actually stops access paths
- [ ] container images are scanned in CI

### Should be true soon after launch

- [ ] stronger egress controls
- [ ] anomaly detection on token minting and webhook failures
- [ ] brokered access for highest-risk credentials
- [ ] incident runbook tested in staging

---

## 22. Explicit Tradeoffs

These are intentional v1 choices:

1. Secrets may be injected as env vars for v1 even though this is not ideal; restart-on-rotation is mandatory because secrets do not auto-refresh.[^aws-secrets-env]
2. We prioritize short-lived GitHub installation tokens over storing broad PATs in each runtime.[^github-install-token]
3. We accept a raw-ish file editing model for desired-state files, but only on allowlisted paths.
4. We choose minimal approvals rather than a large policy engine.
5. We exclude Gmail/phone identity surfaces because they enlarge abuse and trust risk too early.

---

## 23. Open Security Questions

These are real follow-up questions, not blockers for the doc.

1. How tight should outbound egress controls be in v1?
2. Should GitHub writes happen in runtime with short-lived tokens, or be proxied through the control plane for all mutations?
3. Do we want separate task roles per Claw, or one narrow shared role plus Claw-scoped API authorization?
4. What minimum schedule interval should we enforce to prevent abuse?
5. How long should audit events be retained versus user-visible activity logs?

---

## 24. References

[^aws-task-role]: AWS, *Amazon ECS task IAM role*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html
[^aws-exec-role]: AWS, *Amazon ECS task execution IAM role*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
[^aws-taskdef-awsvpc]: AWS, *Amazon ECS task definition parameters*. https://docs.aws.amazon.com/en_us/AmazonECS/latest/developerguide/task_definition_parameters.html
[^aws-fargate-shared-model]: AWS, *AWS shared responsibility model for Amazon ECS*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-shared-model.html
[^aws-secrets-env]: AWS, *Pass Secrets Manager secrets through Amazon ECS environment variables*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html
[^aws-secrets-ecs]: AWS, *Pass sensitive data to an Amazon ECS container*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data.html
[^aws-env-file]: AWS, *Pass environment variables to an Amazon ECS container*. https://docs.aws.amazon.com/AmazonECS/latest/developerguide/use-environment-file.html
[^github-install-token]: GitHub, *REST API endpoints for GitHub Apps*. https://docs.github.com/en/rest/apps/apps
[^github-install-auth]: GitHub, *Authenticating as a GitHub App installation*. https://docs.github.com/enterprise-cloud@latest/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation
[^github-private-key]: GitHub, *Managing private keys for GitHub Apps*. https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
[^github-best-practices]: GitHub, *Best practices for creating a GitHub App*. https://docs.github.com/en/enterprise-server@3.15/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app
[^github-permissions]: GitHub, *Permissions required for GitHub Apps*. https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps
[^github-choose-perms]: GitHub, *Choosing permissions for a GitHub App*. https://docs.github.com/en/enterprise-server@3.15/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
[^github-webhook-signature]: GitHub, *Troubleshooting webhooks*. https://docs.github.com/en/webhooks/testing-and-troubleshooting-webhooks/troubleshooting-webhooks
