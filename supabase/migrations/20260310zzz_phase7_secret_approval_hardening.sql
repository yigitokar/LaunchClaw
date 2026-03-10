-- Harden Phase 7 secrets and approval activity support.

update public.secrets
set provider = lower(trim(provider))
where provider is not null;

drop index if exists public.secrets_claw_label_uidx;
create unique index if not exists secrets_claw_provider_label_uidx
  on public.secrets(claw_id, provider, label);

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
      'integration_connect_started',
      'integration_connected',
      'integration_degraded',
      'integration_disconnected',
      'integration_refreshed',
      'run_failed',
      'run_started',
      'run_succeeded',
      'schedule_created',
      'schedule_toggled',
      'schedule_triggered',
      'schedule_updated',
      'secret_rotated',
      'secret_revoked'
    )
  );
