"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { appConfig } from "@launchclaw/config";
import { ShellCard } from "@launchclaw/ui";
import { apiFetch } from "@/lib/api";

interface Claw {
  id: string;
  name: string;
  status: string;
  preset_id: string;
  last_active_at: string | null;
  created_at: string;
}

export default function ConsolePage() {
  const [claws, setClaws] = useState<Claw[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: Claw[] }>("/api/claws")
      .then((data) => setClaws(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

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
          <Link className="nav-link" href="/billing">
            Billing
          </Link>
        </nav>
      </section>

      <section className="grid">
        {loading && (
          <ShellCard title="Loading" description="Fetching your Claws...">
            <p>Please wait...</p>
          </ShellCard>
        )}

        {error && (
          <ShellCard title="Error" description="Something went wrong.">
            <p style={{ color: "var(--color-error, #ef4444)" }}>{error}</p>
          </ShellCard>
        )}

        {!loading && !error && claws.length === 0 && (
          <ShellCard title="No Claws yet" description="Get started by creating your first Claw.">
            <nav className="nav-row">
              <Link className="nav-link" href="/app/create">
                Create a Claw
              </Link>
            </nav>
          </ShellCard>
        )}

        {!loading &&
          !error &&
          claws.map((claw) => (
            <ShellCard key={claw.id} title={claw.name} description={`Status: ${claw.status}`}>
              <div className="table-like">
                <div className="table-row">
                  <strong>Status</strong>
                  <span className="status">{claw.status}</span>
                </div>
                <div className="table-row">
                  <strong>Last active</strong>
                  <span>{claw.last_active_at ? new Date(claw.last_active_at).toLocaleString() : "Never"}</span>
                </div>
                <div className="table-row">
                  <strong>Created</strong>
                  <span>{new Date(claw.created_at).toLocaleString()}</span>
                </div>
              </div>
              <nav className="nav-row" style={{ marginTop: "0.75rem" }}>
                <Link className="nav-link" href={`/workspace/${claw.id}/work`}>
                  Open Workspace
                </Link>
              </nav>
            </ShellCard>
          ))}
      </section>
    </main>
  );
}
