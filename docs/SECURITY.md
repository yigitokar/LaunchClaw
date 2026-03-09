# LaunchClaw v1 — Security Notes

## Core boundaries

- one runtime per Claw
- no direct public ingress to runtime tasks
- durable state stored outside the runtime
- per-Claw secret scoping
- audit trail for lifecycle and approval actions

## v1 implementation posture

- prefer short-lived GitHub installation tokens over long-lived user PATs
- treat task-local disk as disposable
- keep task IAM roles narrow
- restart runtimes after secret rotation when using env-var injection
- require approvals for destructive or externally consequential actions
