import { ShellCard } from "@launchclaw/ui";

export default function WorkspaceActivityPage() {
  return (
    <ShellCard
      title="Activity"
      description="Lifecycle events, run history, approvals, and integration health will aggregate here."
    >
      <div className="table-like">
        <div className="table-row">
          <strong>Approvals</strong>
          <span>Pending backend implementation</span>
        </div>
        <div className="table-row">
          <strong>Logs feed</strong>
          <span>Pending backend implementation</span>
        </div>
      </div>
    </ShellCard>
  );
}

