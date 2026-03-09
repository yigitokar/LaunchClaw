import Link from "next/link";
import { appConfig } from "@launchclaw/config";
import { ShellCard } from "@launchclaw/ui";

const milestoneChecklist = [
  "Auth shell",
  "Create-Claw wizard",
  "Claw overview",
  "Billing placeholder",
];

export default function ConsolePage() {
  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">Launch Console</span>
        <h1>{appConfig.name}</h1>
        <p>{appConfig.tagline}</p>
        <nav className="nav-row">
          <Link className="nav-link" href="/app/create">
            Create a Claw
          </Link>
          <Link className="nav-link" href="/workspace/demo-claw/work">
            Open Demo Workspace
          </Link>
        </nav>
      </section>

      <section className="grid">
        <ShellCard title="Current state" description="This is a thin control-plane shell, not the full product yet.">
          <div className="table-like">
            <div className="table-row">
              <strong>Runtime provider</strong>
              <span>Fargate (planned)</span>
            </div>
            <div className="table-row">
              <strong>Auth</strong>
              <span>Supabase (planned)</span>
            </div>
            <div className="table-row">
              <strong>Billing shell</strong>
              <span className="status">Not implemented</span>
            </div>
          </div>
        </ShellCard>

        <ShellCard title="Milestone 1" description="Control-plane tasks pulled from the PRD checklist.">
          <ul>
            {milestoneChecklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </ShellCard>
      </section>
    </main>
  );
}

