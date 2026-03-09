import Link from "next/link";
import type { ReactNode } from "react";
import { WORKSPACE_TABS } from "@launchclaw/types";

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">Workspace</span>
        <h1>{id}</h1>
        <p>Thin workspace shell with the tabs defined in the PRD.</p>
      </section>

      <nav className="nav-row">
        {WORKSPACE_TABS.map((tab) => (
          <Link className="nav-link" href={`/workspace/${id}/${tab}`} key={tab}>
            {tab}
          </Link>
        ))}
      </nav>

      {children}
    </main>
  );
}

