# LaunchClaw v1 Security Checklist Audit

This audit maps directly to `docs/SECURITY.md`, Section 21, using the current repository state on March 10, 2026.

## Must be true before launch

| Checklist item | Status | Notes |
| --- | --- | --- |
| one Fargate task per Claw | Not yet | No ECS/Fargate task definitions or provisioning code are present in the repo yet. This is an infra deliverable. |
| runtime has no public ingress | Not yet | The runtime plane networking model is documented, but no subnet, security group, or load balancer configuration exists in the repo. |
| task role and execution role are separate | Not yet | No AWS IAM or ECS task-role configuration exists in code or infra manifests. |
| task role scoped narrowly | Not yet | Same gap as above; this requires AWS IAM policy work outside the current app code. |
| GitHub App private key stored only in control plane secret store | Not yet | The API expects `LAUNCHCLAW_GITHUB_APP_PRIVATE_KEY` in process config (`apps/api/app/config.py`), but there is no secret-store integration in the repo. |
| installation tokens are minted server-side only | Implemented in app code | GitHub installation tokens are exposed only through `/internal/integrations/github/token` and require internal service auth (`apps/api/app/routers/internal.py`). The token is still a stub rather than a real GitHub mint call. |
| webhook signatures are verified with `X-Hub-Signature-256` | Not yet | There is no GitHub webhook endpoint or signature verification flow in the current codebase. |
| secret values never returned from API after save | Implemented in app code | Secret write and list responses serialize metadata only and omit `encrypted_value` (`apps/api/app/routers/secrets.py`). |
| secret rotation marks runtime restart required when applicable | Implemented in app code | Secret upsert/revoke sets `restart_required` based on current Claw status (`apps/api/app/routers/secrets.py`). |
| desired-state file edits restricted to approved paths | Not yet | File writes are limited to rows marked `is_desired_state`, but there is no explicit allowlist of approved paths (`apps/api/app/routers/workspace_files.py`). |
| approval flow exists for selected sensitive actions | Implemented in app code | Approval listing, detail, approve, and deny flows exist and are user-scoped (`apps/api/app/routers/approvals.py`). |
| audit log exists for lifecycle, secrets, schedules, approvals, and file edits | Partially implemented | Lifecycle, secrets, schedules, approvals, integrations, and runs write activity events. File edits do not currently emit audit events (`apps/api/app/routers/_helpers.py`, `apps/api/app/routers/workspace_files.py`). |
| logs redact secrets and tokens | Not yet | There is no centralized logging/redaction layer or filter for sensitive fields. |
| deleting or pausing a Claw actually stops access paths | Not yet | Pause/restart/recover update database status and write activity logs, but there is no runtime enforcement path wired to infra (`apps/api/app/routers/lifecycle.py`). |
| container images are scanned in CI | Not yet | No CI workflow or image-scanning pipeline exists in the repo. |

## Should be true soon after launch

| Checklist item | Status | Notes |
| --- | --- | --- |
| stronger egress controls | Not yet | Requires VPC, NAT, or egress-proxy controls in runtime infrastructure. |
| anomaly detection on token minting and webhook failures | Not yet | No alerting, metrics, or anomaly detection hooks exist for these events. |
| brokered access for highest-risk credentials | Not yet | The repo has an internal token-minting pattern for GitHub, but no general broker service for high-risk credentials. |
| incident runbook tested in staging | Not yet | No staging validation or documented runbook execution evidence is present in the repo. |

## Summary

Implemented application-level controls are strongest around ownership checks, approvals, secret response hygiene, and activity logging for several mutation paths. The major remaining gaps are infra-backed isolation, GitHub webhook verification, logging redaction, and runtime enforcement that status changes actually cut off execution paths.

The Fargate, IAM, network, and CI/image-scanning items should be treated as infrastructure work rather than API or UI gaps.
