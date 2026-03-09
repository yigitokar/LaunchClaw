# LaunchClaw

Initial monorepo scaffold for LaunchClaw v1, based on the product, API, and architecture docs in [`/docs`](/Users/yigitokar/LaunchClaw/docs).

## Stack

- `apps/web`: Next.js app for the Launch Console and Workspace shell
- `apps/api`: FastAPI control-plane service
- `packages/types`: shared TypeScript enums and view models
- `packages/config`: shared frontend config/constants
- `packages/ui`: shared React UI primitives
- `services/*`: placeholders for provisioner, scheduler, and background workers

## Local setup

### Web

```bash
npm install
cp apps/web/.env.local.example apps/web/.env.local
npm run dev:web
```

The web app runs on `http://localhost:3000`.

### API

```bash
cd apps/api
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API runs on `http://localhost:8000`.

## Docs driving this scaffold

- [PRD](/Users/yigitokar/LaunchClaw/docs/PRD.md)
- [Architecture](/Users/yigitokar/LaunchClaw/docs/ARCHITECTURE.md)
- [API spec](/Users/yigitokar/LaunchClaw/docs/API.md)
- [Security notes](/Users/yigitokar/LaunchClaw/docs/SECURITY.md)
