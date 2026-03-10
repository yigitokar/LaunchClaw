-- Billing follow-ups after Phase 8.

update public.billing_accounts
set status = 'canceled'
where status = 'cancelled';

alter table public.billing_accounts drop constraint if exists billing_accounts_status_check;
alter table public.billing_accounts
  add constraint billing_accounts_status_check check (
    status in (
      'active',
      'trialing',
      'past_due',
      'canceled',
      'incomplete',
      'incomplete_expired',
      'unpaid',
      'paused'
    )
  );
