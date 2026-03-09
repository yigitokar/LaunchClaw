-- Phase 6 GitHub integration compatibility.
-- Keep the existing integrations table aligned with the API contract by
-- ensuring a metadata JSONB column exists for installation details.

create table if not exists public.integrations (
  id uuid primary key default gen_random_uuid(),
  claw_id uuid not null references public.claws(id) on delete cascade,
  provider text not null,
  status text not null default 'pending',
  external_account_ref text,
  scope_summary text,
  config_json jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.integrations
  add column if not exists claw_id uuid references public.claws(id) on delete cascade,
  add column if not exists provider text,
  add column if not exists status text not null default 'pending',
  add column if not exists external_account_ref text,
  add column if not exists scope_summary text,
  add column if not exists config_json jsonb not null default '{}'::jsonb,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

update public.integrations
set metadata = coalesce(metadata, '{}'::jsonb)
  || coalesce(config_json, '{}'::jsonb)
  || case
    when external_account_ref is not null
      and not (coalesce(metadata, '{}'::jsonb) ? 'installation_id')
    then jsonb_build_object('installation_id', external_account_ref)
    else '{}'::jsonb
  end;

alter table public.integrations enable row level security;

create index if not exists integrations_claw_id_idx on public.integrations(claw_id);

do $$
begin
  alter table public.integrations drop constraint if exists integrations_provider_check;
  alter table public.integrations drop constraint if exists integrations_status_check;

  alter table public.integrations
    add constraint integrations_provider_check check (provider in ('github'));

  alter table public.integrations
    add constraint integrations_status_check check (
      status in ('pending','connected','degraded','disconnected','revoked')
    );
exception
  when duplicate_object then null;
end;
$$;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'integrations'
      and policyname = 'integrations_select'
  ) then
    create policy "integrations_select" on public.integrations
      for select using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'integrations'
      and policyname = 'integrations_insert'
  ) then
    create policy "integrations_insert" on public.integrations
      for insert with check (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'integrations'
      and policyname = 'integrations_update'
  ) then
    create policy "integrations_update" on public.integrations
      for update using (public.claw_owner(claw_id) = auth.uid());
  end if;
end;
$$;

do $$
begin
  if not exists (
    select 1
    from pg_trigger
    where tgname = 'set_integrations_updated_at'
      and tgrelid = 'public.integrations'::regclass
  ) then
    create trigger set_integrations_updated_at before update on public.integrations
      for each row execute function public.set_updated_at();
  end if;
end;
$$;
