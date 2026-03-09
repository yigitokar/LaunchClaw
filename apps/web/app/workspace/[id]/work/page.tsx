import { ShellCard } from "@launchclaw/ui";

export default function WorkspaceWorkPage() {
  return (
    <ShellCard
      title="Work"
      description="Manual runs will be created here once the API and run orchestration endpoints are wired."
    >
      <div className="table-like">
        <div className="table-row">
          <strong>Run input</strong>
          <span>Not implemented</span>
        </div>
        <div className="table-row">
          <strong>Run queue</strong>
          <span>Not implemented</span>
        </div>
      </div>
    </ShellCard>
  );
}

