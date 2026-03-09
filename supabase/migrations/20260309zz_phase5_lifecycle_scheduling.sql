-- Phase 5 lifecycle and scheduling hardening.
-- The schedules table already exists in the base schema, so this migration
-- keeps newer environments in sync without redefining the table unsafely.

create table if not exists public.schedules (
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

alter table public.schedules
  add column if not exists claw_id uuid references public.claws(id) on delete cascade,
  add column if not exists name text,
  add column if not exists schedule_expr text,
  add column if not exists enabled boolean not null default true,
  add column if not exists last_run_at timestamptz,
  add column if not exists next_run_at timestamptz,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table public.schedules enable row level security;

create index if not exists schedules_claw_id_idx on public.schedules(claw_id);
create index if not exists schedules_due_idx on public.schedules(next_run_at) where enabled = true;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'schedules'
      and policyname = 'schedules_select'
  ) then
    create policy "schedules_select" on public.schedules
      for select using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'schedules'
      and policyname = 'schedules_insert'
  ) then
    create policy "schedules_insert" on public.schedules
      for insert with check (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'schedules'
      and policyname = 'schedules_update'
  ) then
    create policy "schedules_update" on public.schedules
      for update using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'schedules'
      and policyname = 'schedules_delete'
  ) then
    create policy "schedules_delete" on public.schedules
      for delete using (public.claw_owner(claw_id) = auth.uid());
  end if;
end;
$$;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'set_schedules_updated_at'
      and tgrelid = 'public.schedules'::regclass
  ) then
    create trigger set_schedules_updated_at before update on public.schedules
      for each row execute function public.set_updated_at();
  end if;
end;
$$;

alter table public.activity_events drop constraint if exists activity_events_type_check;

alter table public.activity_events
  add constraint activity_events_type_check check (
    type in (
      'approval_approved',
      'approval_denied',
      'approval_requested',
      'claw_created',
      'claw_healthy',
      'claw_paused',
      'claw_recovered',
      'claw_restarted',
      'claw_resumed',
      'integration_connected',
      'integration_degraded',
      'run_failed',
      'run_started',
      'run_succeeded',
      'schedule_created',
      'schedule_toggled',
      'schedule_triggered',
      'schedule_updated',
      'secret_rotated'
    )
  );
