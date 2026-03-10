# LaunchClaw Build Tracker

## Current Phase
Phase 7 — Approvals & Secrets

## Build Order (from PRD)

### Phase 1: Data Model & Auth Foundation ✅ (PR #1, merged 2026-03-09)
- [x] Set up Supabase project config (env vars, client libs)
- [x] Create DB migrations for all core tables (users, claws, presets, workspace_files, runs, integrations, secrets, schedules, approvals, artifacts, billing_accounts)
- [x] Add RLS policies for user-scoped access
- [x] Implement Supabase Auth in Next.js (sign up, sign in, session management)
- [x] Wire up /api/me to return real authenticated user

### Phase 2: Claw CRUD & Create Flow ✅ (PR #2, merged 2026-03-09)
- [x] POST /api/claws — create Claw endpoint
- [x] GET /api/claws — list user's Claws
- [x] GET /api/claws/:id — get Claw detail
- [x] PATCH /api/claws/:id — update Claw name
- [x] Build Create Claw wizard UI (preset selection, name, model access mode)
- [x] Build Claw overview card in Launch Console

### Phase 3: Workspace Shell & Files ✅ (PR #3, merged 2026-03-09)
- [x] Build workspace layout with sidebar nav (work/files/activity/settings tabs)
- [x] GET /api/claws/:id/workspace/files — list files
- [x] GET /api/claws/:id/workspace/files/content — get file content
- [x] PUT /api/claws/:id/workspace/files/content — update file (optimistic concurrency)
- [x] Build Files tab UI with editor
- [x] Build Settings tab UI

### Phase 4: Runs & Activity ✅ (implemented in earlier PRs, verified 2026-03-09)
- [x] POST /api/claws/:id/runs — create manual run
- [x] GET /api/claws/:id/runs — list runs
- [x] GET /api/runs/:id — run detail
- [x] Build Work tab UI (input + run history)
- [x] Build Activity tab UI (event feed)
- [x] GET /api/claws/:id/activity — activity feed endpoint

### Phase 5: Lifecycle & Scheduling ✅ (PR #5, open 2026-03-09)
- [x] POST pause/resume/restart/recover endpoints
- [x] Lifecycle state machine enforcement
- [x] CRUD for schedules
- [x] Schedule toggle endpoint
- [x] Scheduler service (scan due, create runs)
- [x] Scheduling UI in workspace settings

### Phase 6: GitHub Integration ✅ (PR #7, merged 2026-03-09)
- [x] GitHub App setup docs
- [x] POST /api/claws/:id/integrations/github/connect
- [x] GitHub OAuth callback handler
- [x] Integration status & disconnect
- [x] Internal token minting endpoint
- [x] Integrations tab in workspace

### Phase 7: Approvals & Secrets
- [ ] Approval CRUD endpoints
- [ ] Approve/deny flow
- [ ] Approval UI in workspace
- [ ] Secret create/revoke endpoints
- [ ] Secret management UI
- [ ] restart_required flag on rotation

### Phase 8: Billing & Hardening
- [ ] Stripe checkout session
- [ ] Billing summary endpoint
- [ ] Usage tracking
- [ ] Error handling polish
- [ ] Security checklist audit

## Completed Tasks
- Phase 1: Data Model & Auth Foundation — PR #1, merged 2026-03-09
- Phase 2: Claw CRUD & Create Flow — PR #2, merged 2026-03-09
- Phase 3: Workspace Shell & Files — PR #3, merged 2026-03-09
- Phase 5: Lifecycle & Scheduling — PR #5, merged 2026-03-09
- Phase 6: GitHub Integration — PR #7, merged 2026-03-09

## Notes
- FastAPI backend (apps/api) — Python
- Next.js frontend (apps/web) — TypeScript/React
- Supabase for auth + Postgres
- S3 for workspace file storage (later)
- All work done via PRs to main
