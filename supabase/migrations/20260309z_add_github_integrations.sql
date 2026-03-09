alter table public.integrations
  add column if not exists provider text;

update public.integrations
set provider = 'github'
where provider is null;

alter table public.integrations
  alter column provider set default 'github';

alter table public.integrations
  alter column provider set not null;

alter table public.integrations
  add column if not exists github_installation_id bigint;

alter table public.integrations
  drop constraint if exists integrations_provider_check;

alter table public.integrations
  add constraint integrations_provider_check check (provider in ('github'));

create table if not exists public.integration_states (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  state_token text not null unique,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists integration_states_claw_id_idx on public.integration_states(claw_id);
create index if not exists integration_states_expires_at_idx on public.integration_states(expires_at);

alter table public.integration_states enable row level security;

drop policy if exists "integration_states_select" on public.integration_states;
create policy "integration_states_select" on public.integration_states
  for select using (auth.uid() = user_id);

drop policy if exists "integration_states_insert" on public.integration_states;
create policy "integration_states_insert" on public.integration_states
  for insert with check (auth.uid() = user_id);

drop policy if exists "integration_states_update" on public.integration_states;
create policy "integration_states_update" on public.integration_states
  for update using (auth.uid() = user_id);

drop policy if exists "integration_states_delete" on public.integration_states;
create policy "integration_states_delete" on public.integration_states
  for delete using (auth.uid() = user_id);

alter table public.activity_events
  drop constraint if exists activity_events_type_check;

alter table public.activity_events
  add constraint activity_events_type_check check (
    type in (
      'approval_approved',
      'approval_denied',
      'approval_requested',
      'claw_created',
      'claw_healthy',
      'claw_paused',
      'claw_restarted',
      'integration_connected',
      'integration_degraded',
      'integration_disconnected',
      'integration_refreshed',
      'run_failed',
      'run_started',
      'run_succeeded',
      'schedule_triggered',
      'secret_rotated'
    )
  );
