import Link from "next/link";
import { CLAW_STATUSES, WORKSPACE_TABS } from "@launchclaw/types";
import { ShellCard } from "@launchclaw/ui";

export default function HomePage() {
  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">LaunchClaw v1 scaffold</span>
        <h1>Control plane and workspace shell initialized from the project docs.</h1>
        <p>
          This repo now matches the proposed monorepo layout: Next.js web surface, FastAPI API service,
          shared packages, and service placeholders for provisioning and scheduling.
        </p>
        <nav className="nav-row">
          <Link className="nav-link" href="/app">
            Open Launch Console
          </Link>
          <Link className="nav-link" href="/app/create">
            Open Create Flow
          </Link>
          <Link className="nav-link" href="/workspace/demo-claw/work">
            Open Workspace
          </Link>
        </nav>
      </section>

      <section className="grid">
        <ShellCard
          title="Status model"
          description="Shared enums live in packages/types so the web app and future tooling can align on core state."
        >
          <div className="pill-row">
            {CLAW_STATUSES.slice(0, 5).map((status) => (
              <span className="pill" key={status}>
                {status}
              </span>
            ))}
          </div>
        </ShellCard>

        <ShellCard
          title="Workspace tabs"
          description="The workspace shell already maps to the v1 tabs described in the PRD."
        >
          <div className="pill-row">
            {WORKSPACE_TABS.map((tab) => (
              <span className="pill" key={tab}>
                {tab}
              </span>
            ))}
          </div>
        </ShellCard>
      </section>
    </main>
  );
}

