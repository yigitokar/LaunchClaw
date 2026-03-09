alter table public.activity_events
  drop constraint activity_events_type_check;

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
      'schedule_deleted',
      'schedule_disabled',
      'schedule_enabled',
      'schedule_triggered',
      'schedule_updated',
      'secret_rotated'
    )
  );
