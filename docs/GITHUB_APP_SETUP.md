# GitHub App Setup

## Create the App

1. Open GitHub Settings, then Developer settings, then GitHub Apps, and create a new app.
2. Pick an app name and slug. LaunchClaw uses the slug for the install URL.
3. Set the app's Setup URL to the LaunchClaw API callback so GitHub returns the browser to LaunchClaw after install.
4. If you plan to replace the placeholder token endpoint later, generate a private key and keep the App ID.

## Required Permissions

- Repository metadata: `Read-only`
- Contents: `Read and write`
- Pull requests: `Read and write`

## Callback and Install URLs

- Setup URL:
  - Local development: `http://localhost:8000/api/integrations/github/callback`
  - Production: `https://api.your-domain.com/api/integrations/github/callback`
- GitHub install URL:
  - `https://github.com/apps/<app-slug>/installations/new`

## Environment Variables

Current Phase 6 requires these API env vars:

```env
LAUNCHCLAW_GITHUB_APP_SLUG=launchclaw
LAUNCHCLAW_GITHUB_APP_STATE_SECRET=replace-me-with-a-long-random-value
LAUNCHCLAW_CORS_ORIGIN=http://localhost:3000
LAUNCHCLAW_INTERNAL_SERVICE_TOKEN=replace-me
```

Optional future GitHub App token-minting vars:

```env
LAUNCHCLAW_GITHUB_APP_ID=123456
LAUNCHCLAW_GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
LAUNCHCLAW_GITHUB_CLIENT_ID=Iv1.xxxxx
LAUNCHCLAW_GITHUB_CLIENT_SECRET=xxxxxxxx
```

## Notes

- The callback stores the `installation_id` on the existing `integrations` row and then redirects to `/workspace/:id/integrations`.
- `/internal/integrations/github/token` currently returns a fake `ghs_...` token. Real installation token minting comes later.
