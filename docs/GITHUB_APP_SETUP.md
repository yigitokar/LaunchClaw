# GitHub App Setup

## Create the App

1. Open GitHub Settings and create a new GitHub App for LaunchClaw.
2. Pick an app name and slug. The backend defaults to the slug `launchclaw`.
3. Generate a private key after the app is created and store it securely.

## Required Permissions

- Repository permissions:
  - Contents: `Read and write`
  - Pull requests: `Read and write`
  - Metadata: `Read-only`

## Callback and Install URLs

- Setup URL / callback URL:
  - Local development: `http://localhost:8000/api/integrations/github/callback`
  - Production: `https://api.your-domain.com/api/integrations/github/callback`
- Install flow target:
  - `https://github.com/apps/<app-slug>/installations/new`

## Webhooks

- Webhook URL:
  - Local placeholder: `http://localhost:8000/api/integrations/github/webhooks`
  - Production placeholder: `https://api.your-domain.com/api/integrations/github/webhooks`
- Webhook secret:
  - Generate and store one now even though webhook handling is still a placeholder.

## Environment Variables

Add these to the API environment:

```env
LAUNCHCLAW_GITHUB_APP_ID=123456
LAUNCHCLAW_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
LAUNCHCLAW_GITHUB_CLIENT_ID=Iv1.xxxxx
LAUNCHCLAW_GITHUB_CLIENT_SECRET=xxxxxxxx
```

Recommended supporting variables:

```env
LAUNCHCLAW_GITHUB_APP_SLUG=launchclaw
LAUNCHCLAW_CORS_ORIGIN=http://localhost:3000
LAUNCHCLAW_INTERNAL_SERVICE_TOKEN=replace-me
```

## Notes

- The current `/internal/integrations/github/token` endpoint returns a placeholder token. Real GitHub App installation token minting comes later.
- The callback currently redirects users back into the LaunchClaw workspace after GitHub finishes the install flow.
