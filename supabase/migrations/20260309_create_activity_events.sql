create table public.activity_events (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  run_id uuid references public.runs(id) on delete set null,
  type text not null,
  summary text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),

  constraint activity_events_type_check check (
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
      'run_failed',
      'run_started',
      'run_succeeded',
      'schedule_triggered',
      'secret_rotated'
    )
  )
);

create index activity_events_claw_created_idx on public.activity_events(claw_id, created_at desc);
create index activity_events_run_id_idx on public.activity_events(run_id);

alter table public.activity_events enable row level security;

create policy "activity_events_select" on public.activity_events
  for select using (public.claw_owner(claw_id) = auth.uid());
create policy "activity_events_insert" on public.activity_events
  for insert with check (public.claw_owner(claw_id) = auth.uid());
create policy "activity_events_update" on public.activity_events
  for update using (public.claw_owner(claw_id) = auth.uid());

insert into public.activity_events (claw_id, type, summary, metadata, created_at)
select
  id,
  'claw_created',
  'Claw created',
  jsonb_build_object(
    'status', status,
    'preset_id', preset_id,
    'model_access_mode', model_access_mode
  ),
  created_at
from public.claws;
