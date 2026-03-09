-- LaunchClaw v1 core schema migration
-- All tables, indexes, check constraints, RLS policies, and seed data.

-- =============================================================================
-- 1. TABLES
-- =============================================================================

-- users (synced from Supabase Auth; id matches auth.users.id)
create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text unique not null,
  name text,
  auth_provider text not null default 'email',
  billing_customer_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- presets
create table public.presets (
  id uuid primary key default gen_random_uuid(),
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

-- claws
create table public.claws (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null,
  preset_id uuid references public.presets(id),
  status text not null default 'creating',
  runtime_provider text not null default 'fargate',
  model_access_mode text not null,
  workspace_bucket_path text,
  current_task_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_active_at timestamptz,

  constraint claws_status_check check (
    status in ('creating','provisioning','healthy','degraded','paused','restarting','failed','deleted')
  ),
  constraint claws_model_access_mode_check check (
    model_access_mode in ('byok','managed')
  )
);

create index claws_user_id_idx on public.claws(user_id);

-- workspace_files
create table public.workspace_files (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  path text not null,
  kind text not null,
  content_type text,
  storage_ref text not null,
  version integer not null default 1,
  is_desired_state boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (claw_id, path),

  constraint workspace_files_kind_check check (
    kind in ('profile','mission','rules','schedule','integration_config','artifact','draft','output','misc')
  )
);

create index workspace_files_claw_id_idx on public.workspace_files(claw_id);

-- runs
create table public.runs (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  trigger_type text not null,
  status text not null default 'queued',
  input_summary text,
  started_at timestamptz,
  ended_at timestamptz,
  approval_state text,
  token_usage bigint,
  cost_estimate numeric(12, 4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint runs_trigger_type_check check (
    trigger_type in ('manual','schedule','integration_event','system')
  ),
  constraint runs_status_check check (
    status in ('queued','running','waiting_approval','succeeded','failed','cancelled')
  )
);

create index runs_claw_id_idx on public.runs(claw_id);
create index runs_status_idx on public.runs(status);

-- integrations
create table public.integrations (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  provider text not null,
  status text not null default 'pending',
  external_account_ref text,
  scope_summary text,
  config_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint integrations_provider_check check (provider in ('github')),
  constraint integrations_status_check check (
    status in ('pending','connected','degraded','disconnected','revoked')
  )
);

create index integrations_claw_id_idx on public.integrations(claw_id);

-- secrets
create table public.secrets (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  provider text not null,
  label text not null,
  secret_ref text not null,
  status text not null default 'active',
  last_rotated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint secrets_status_check check (status in ('active','revoked'))
);

create index secrets_claw_id_idx on public.secrets(claw_id);

-- schedules
create table public.schedules (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  name text not null,
  schedule_expr text not null,
  enabled boolean not null default true,
  last_run_at timestamptz,
  next_run_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index schedules_claw_id_idx on public.schedules(claw_id);

-- approvals
create table public.approvals (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  run_id uuid references public.runs(id) on delete set null,
  action_type text not null,
  payload_summary text,
  status text not null default 'pending',
  requested_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by_user_id uuid references public.users(id) on delete set null,

  constraint approvals_status_check check (
    status in ('pending','approved','denied','expired')
  )
);

create index approvals_claw_id_idx on public.approvals(claw_id);
create index approvals_status_idx on public.approvals(status);

-- artifacts
create table public.artifacts (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.runs(id) on delete cascade,
  claw_id uuid not null references public.claws(id) on delete cascade,
  kind text not null,
  path text not null,
  storage_ref text not null,
  size_bytes bigint,
  created_at timestamptz not null default now()
);

create index artifacts_run_id_idx on public.artifacts(run_id);
create index artifacts_claw_id_idx on public.artifacts(claw_id);

-- billing_accounts
create table public.billing_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  provider text not null,
  provider_customer_ref text not null,
  plan text not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint billing_accounts_status_check check (
    status in ('active','past_due','cancelled','trialing')
  )
);

create unique index billing_accounts_user_id_idx on public.billing_accounts(user_id);

-- =============================================================================
-- 2. ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all user-facing tables
alter table public.users enable row level security;
alter table public.claws enable row level security;
alter table public.workspace_files enable row level security;
alter table public.runs enable row level security;
alter table public.integrations enable row level security;
alter table public.secrets enable row level security;
alter table public.schedules enable row level security;
alter table public.approvals enable row level security;
alter table public.artifacts enable row level security;
alter table public.billing_accounts enable row level security;
alter table public.presets enable row level security;

-- Helper: get the claw owner for a given claw_id
create or replace function public.claw_owner(p_claw_id uuid)
returns uuid
language sql
stable
security definer
as $$
  select user_id from public.claws where id = p_claw_id;
$$;

-- users: users can read/update their own row
create policy "users_select_own" on public.users
  for select using (auth.uid() = id);
create policy "users_update_own" on public.users
  for update using (auth.uid() = id);
create policy "users_insert_own" on public.users
  for insert with check (auth.uid() = id);

-- presets: readable by all authenticated users
create policy "presets_select_authenticated" on public.presets
  for select using (auth.role() = 'authenticated');

-- claws: users can only access their own
create policy "claws_select_own" on public.claws
  for select using (auth.uid() = user_id);
create policy "claws_insert_own" on public.claws
  for insert with check (auth.uid() = user_id);
create policy "claws_update_own" on public.claws
  for update using (auth.uid() = user_id);
create policy "claws_delete_own" on public.claws
  for delete using (auth.uid() = user_id);

-- workspace_files: scoped through claw ownership
create policy "workspace_files_select" on public.workspace_files
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "workspace_files_insert" on public.workspace_files
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "workspace_files_update" on public.workspace_files
  for update using (public.claw_owner(claw_id) = auth.uid());
create policy "workspace_files_delete" on public.workspace_files
  for delete using (public.claw_owner(claw_id) = auth.uid());

-- runs
create policy "runs_select" on public.runs
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "runs_insert" on public.runs
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "runs_update" on public.runs
  for update using (public.claw_owner(claw_id) = auth.uid());

-- integrations
create policy "integrations_select" on public.integrations
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "integrations_insert" on public.integrations
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "integrations_update" on public.integrations
  for update using (public.claw_owner(claw_id) = auth.uid());

-- secrets
create policy "secrets_select" on public.secrets
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "secrets_insert" on public.secrets
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "secrets_update" on public.secrets
  for update using (public.claw_owner(claw_id) = auth.uid());
create policy "secrets_delete" on public.secrets
  for delete using (public.claw_owner(claw_id) = auth.uid());

-- schedules
create policy "schedules_select" on public.schedules
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "schedules_insert" on public.schedules
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "schedules_update" on public.schedules
  for update using (public.claw_owner(claw_id) = auth.uid());
create policy "schedules_delete" on public.schedules
  for delete using (public.claw_owner(claw_id) = auth.uid());

-- approvals
create policy "approvals_select" on public.approvals
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "approvals_update" on public.approvals
  for update using (public.claw_owner(claw_id) = auth.uid());

-- artifacts
create policy "artifacts_select" on public.artifacts
  for select using (public.claw_owner(claw_id) = auth.uid());

-- billing_accounts
create policy "billing_accounts_select" on public.billing_accounts
  for select using (auth.uid() = user_id);
create policy "billing_accounts_insert" on public.billing_accounts
  for insert with check (auth.uid() = user_id);
create policy "billing_accounts_update" on public.billing_accounts
  for update using (auth.uid() = user_id);

-- =============================================================================
-- 3. UPDATED_AT TRIGGER
-- =============================================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger set_users_updated_at before update on public.users
  for each row execute function public.set_updated_at();
create trigger set_presets_updated_at before update on public.presets
  for each row execute function public.set_updated_at();
create trigger set_claws_updated_at before update on public.claws
  for each row execute function public.set_updated_at();
create trigger set_workspace_files_updated_at before update on public.workspace_files
  for each row execute function public.set_updated_at();
create trigger set_runs_updated_at before update on public.runs
  for each row execute function public.set_updated_at();
create trigger set_integrations_updated_at before update on public.integrations
  for each row execute function public.set_updated_at();
create trigger set_secrets_updated_at before update on public.secrets
  for each row execute function public.set_updated_at();
create trigger set_schedules_updated_at before update on public.schedules
  for each row execute function public.set_updated_at();
create trigger set_billing_accounts_updated_at before update on public.billing_accounts
  for each row execute function public.set_updated_at();

-- =============================================================================
-- 4. AUTO-CREATE USER ROW ON SIGNUP
-- =============================================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.users (id, email, auth_provider)
  values (new.id, new.email, coalesce(new.raw_app_meta_data->>'provider', 'email'));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- =============================================================================
-- 5. SEED DATA
-- =============================================================================

insert into public.presets (slug, name, description, seed_profile_md, seed_mission_md, seed_rules_md)
values (
  'dev-assistant',
  'Dev Assistant',
  'Good default for code and GitHub work',
  '# Profile

You are a development assistant Claw. You help with code reviews, PR management, and development tasks.',
  '# Mission

Review open pull requests daily. Summarize blockers and suggest improvements.',
  '# Rules

- Always explain changes before making them.
- Never force-push to main.
- Request approval before merging PRs.
- Keep commit messages clear and concise.'
);
