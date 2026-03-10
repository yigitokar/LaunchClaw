"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { use } from "react";
import { WORKSPACE_TABS, type WorkspaceTab } from "@launchclaw/types";

const TAB_ICONS: Record<WorkspaceTab, string> = {
  work: "W",
  files: "F",
  activity: "A",
  integrations: "I",
  approvals: "AP",
  secrets: "SC",
  settings: "S",
};

export default function WorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const pathname = usePathname();

  const activeTab = WORKSPACE_TABS.find((tab) => pathname.includes(`/${tab}`)) || "work";

  return (
    <div className="workspace-layout">
      <aside className="workspace-sidebar">
        <div className="sidebar-header">
          <Link href="/dashboard" className="sidebar-back">
            &larr;
          </Link>
          <span className="sidebar-title">Workspace</span>
        </div>
        <nav className="sidebar-nav">
          {WORKSPACE_TABS.map((tab) => (
            <Link
              className={`sidebar-link ${activeTab === tab ? "sidebar-link--active" : ""}`}
              href={`/workspace/${id}/${tab}`}
              key={tab}
            >
              <span className="sidebar-icon">{TAB_ICONS[tab]}</span>
              <span className="sidebar-label">{tab}</span>
            </Link>
          ))}
        </nav>
      </aside>
      <main className="workspace-main">{children}</main>
    </div>
  );
}
