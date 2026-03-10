-- Phase 7 approvals and secrets.
-- Keep UUID foreign keys for claws/runs because the existing core schema still
-- uses UUID primary keys, while migrating approval/secret record IDs to text.

create table if not exists public.approvals (
  id text primary key,
  claw_id uuid not null references public.claws(id) on delete cascade,
  run_id uuid references public.runs(id) on delete set null,
  action_type text not null,
  payload_summary text,
  status text not null default 'pending',
  requested_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),

  constraint approvals_status_check check (status in ('pending', 'approved', 'denied'))
);

create table if not exists public.secrets (
  id text primary key,
  claw_id uuid not null references public.claws(id) on delete cascade,
  provider text not null,
  label text not null,
  encrypted_value text,
  status text not null default 'active',
  restart_required boolean not null default false,
  last_rotated_at timestamptz,
  created_at timestamptz not null default now(),

  constraint secrets_status_check check (status in ('active', 'revoked'))
);

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'approvals'
      and column_name = 'id'
      and data_type <> 'text'
  ) then
    alter table public.approvals alter column id drop default;
    alter table public.approvals alter column id type text using id::text;
  end if;
end;
$$;

alter table public.approvals
  add column if not exists claw_id uuid references public.claws(id) on delete cascade,
  add column if not exists run_id uuid references public.runs(id) on delete set null,
  add column if not exists action_type text,
  add column if not exists payload_summary text,
  add column if not exists status text not null default 'pending',
  add column if not exists requested_at timestamptz not null default now(),
  add column if not exists resolved_at timestamptz,
  add column if not exists created_at timestamptz not null default now();

update public.approvals
set created_at = coalesce(created_at, requested_at, now())
where created_at is null;

update public.approvals
set requested_at = coalesce(requested_at, created_at, now())
where requested_at is null;

update public.approvals
set status = 'denied'
where status not in ('pending', 'approved', 'denied');

update public.approvals
set id = 'approval_' || substr(replace(id, '-', ''), 1, 12)
where id !~ '^approval_[0-9a-f]{12}$';

alter table public.approvals drop constraint if exists approvals_status_check;
alter table public.approvals
  add constraint approvals_status_check check (status in ('pending', 'approved', 'denied'));

create index if not exists approvals_claw_id_idx on public.approvals(claw_id);
create index if not exists approvals_status_idx on public.approvals(status);
create index if not exists approvals_claw_requested_idx on public.approvals(claw_id, requested_at desc);

alter table public.approvals enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'approvals'
      and policyname = 'approvals_select'
  ) then
    create policy "approvals_select" on public.approvals
      for select using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'approvals'
      and policyname = 'approvals_insert'
  ) then
    create policy "approvals_insert" on public.approvals
      for insert with check (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'approvals'
      and policyname = 'approvals_update'
  ) then
    create policy "approvals_update" on public.approvals
      for update using (public.claw_owner(claw_id) = auth.uid());
  end if;
end;
$$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'secrets'
      and column_name = 'secret_ref'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'secrets'
      and column_name = 'encrypted_value'
  ) then
    alter table public.secrets rename column secret_ref to encrypted_value;
  end if;
end;
$$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'secrets'
      and column_name = 'id'
      and data_type <> 'text'
  ) then
    alter table public.secrets alter column id drop default;
    alter table public.secrets alter column id type text using id::text;
  end if;
end;
$$;

alter table public.secrets
  add column if not exists claw_id uuid references public.claws(id) on delete cascade,
  add column if not exists provider text,
  add column if not exists label text,
  add column if not exists encrypted_value text,
  add column if not exists status text not null default 'active',
  add column if not exists restart_required boolean not null default false,
  add column if not exists last_rotated_at timestamptz,
  add column if not exists created_at timestamptz not null default now();

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'secrets'
      and column_name = 'encrypted_value'
  ) then
    alter table public.secrets alter column encrypted_value drop not null;
  end if;
end;
$$;

update public.secrets
set restart_required = false
where restart_required is null;

update public.secrets
set status = 'revoked'
where status not in ('active', 'revoked');

update public.secrets
set id = 'secret_' || substr(replace(id, '-', ''), 1, 12)
where id !~ '^secret_[0-9a-f]{12}$';

alter table public.secrets drop constraint if exists secrets_status_check;
alter table public.secrets
  add constraint secrets_status_check check (status in ('active', 'revoked'));

create index if not exists secrets_claw_id_idx on public.secrets(claw_id);
create unique index if not exists secrets_claw_label_uidx on public.secrets(claw_id, label);

alter table public.secrets enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'secrets'
      and policyname = 'secrets_select'
  ) then
    create policy "secrets_select" on public.secrets
      for select using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'secrets'
      and policyname = 'secrets_insert'
  ) then
    create policy "secrets_insert" on public.secrets
      for insert with check (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'secrets'
      and policyname = 'secrets_update'
  ) then
    create policy "secrets_update" on public.secrets
      for update using (public.claw_owner(claw_id) = auth.uid());
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'secrets'
      and policyname = 'secrets_delete'
  ) then
    create policy "secrets_delete" on public.secrets
      for delete using (public.claw_owner(claw_id) = auth.uid());
  end if;
end;
$$;
