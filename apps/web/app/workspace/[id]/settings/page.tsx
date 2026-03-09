import { ShellCard } from "@launchclaw/ui";

export default function WorkspaceSettingsPage() {
  return (
    <ShellCard
      title="Settings"
      description="Integration config, runtime lifecycle controls, and secret rotation will land here."
    >
      <div className="table-like">
        <div className="table-row">
          <strong>GitHub</strong>
          <span>Connect flow not implemented</span>
        </div>
        <div className="table-row">
          <strong>Lifecycle</strong>
          <span>Pause, resume, and restart pending API wiring</span>
        </div>
      </div>
    </ShellCard>
  );
}

