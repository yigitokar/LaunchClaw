import { ShellCard } from "@launchclaw/ui";

const desiredFiles = ["profile.md", "mission.md", "rules.md", "schedule.yaml", "integrations.yaml"];

export default function WorkspaceFilesPage() {
  return (
    <ShellCard
      title="Files"
      description="Desired-state file editing is planned around the raw file model described in the docs."
    >
      <ul>
        {desiredFiles.map((file) => (
          <li key={file}>
            <code>{file}</code>
          </li>
        ))}
      </ul>
    </ShellCard>
  );
}

