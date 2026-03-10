-- Phase 8 billing and hardening.

do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'runs'
      and column_name = 'token_usage'
  ) then
    alter table public.runs
      add column token_usage integer default 0;
  end if;
end;
$$;

update public.runs
set token_usage = 0
where token_usage is null;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'runs'
      and column_name = 'token_usage'
      and data_type <> 'integer'
  ) then
    alter table public.runs
      alter column token_usage type integer using coalesce(token_usage, 0)::integer;
  end if;
end;
$$;

alter table public.runs
  alter column token_usage set default 0;

create table if not exists public.billing_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  provider text not null,
  plan text not null,
  status text not null,
  stripe_customer_id text,
  current_period_start timestamptz,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint billing_accounts_status_check check (
    status in ('active', 'past_due', 'cancelled', 'trialing')
  )
);

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'billing_accounts'
      and column_name = 'provider_customer_ref'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'billing_accounts'
      and column_name = 'stripe_customer_id'
  ) then
    alter table public.billing_accounts rename column provider_customer_ref to stripe_customer_id;
  end if;
end;
$$;

alter table public.billing_accounts
  add column if not exists user_id uuid references public.users(id) on delete cascade,
  add column if not exists provider text,
  add column if not exists plan text,
  add column if not exists status text,
  add column if not exists stripe_customer_id text,
  add column if not exists current_period_start timestamptz,
  add column if not exists current_period_end timestamptz,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table public.billing_accounts
  alter column user_id set not null,
  alter column provider set not null,
  alter column plan set not null,
  alter column status set not null;

alter table public.billing_accounts drop constraint if exists billing_accounts_status_check;
alter table public.billing_accounts
  add constraint billing_accounts_status_check check (
    status in ('active', 'past_due', 'cancelled', 'trialing')
  );

create unique index if not exists billing_accounts_user_id_idx on public.billing_accounts(user_id);

alter table public.billing_accounts enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'billing_accounts'
      and policyname = 'billing_accounts_select'
  ) then
    create policy "billing_accounts_select" on public.billing_accounts
      for select using (auth.uid() = user_id);
  end if;
end;
$$;

do $$
begin
  if exists (
    select 1
    from pg_proc
    where proname = 'set_updated_at'
  ) and not exists (
    select 1
    from pg_trigger
    where tgname = 'set_billing_accounts_updated_at'
      and tgrelid = 'public.billing_accounts'::regclass
  ) then
    create trigger set_billing_accounts_updated_at before update on public.billing_accounts
      for each row execute function public.set_updated_at();
  end if;
end;
$$;
