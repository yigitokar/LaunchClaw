import { ShellCard } from "@launchclaw/ui";

const fields = [
  ["Name", "Human-friendly Claw name"],
  ["Preset", "Initial seed config"],
  ["Model access mode", "BYOK or managed"],
  ["GitHub", "Optional connect step"],
];

export default function CreateClawPage() {
  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">Create Flow</span>
        <h1>Minimal create-Claw wizard shell</h1>
        <p>The UI is stubbed to the fields and order described in the PRD, ready for auth and API wiring.</p>
      </section>

      <ShellCard title="Wizard fields" description="These map directly to the documented v1 launch flow.">
        <div className="table-like">
          {fields.map(([label, description]) => (
            <div className="table-row" key={label}>
              <strong>{label}</strong>
              <span>{description}</span>
            </div>
          ))}
        </div>
      </ShellCard>
    </main>
  );
}

