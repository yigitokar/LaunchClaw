"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface Preset {
  id: string;
  slug: string;
  name: string;
  description: string;
}

type Step = 1 | 2 | 3 | 4;

export default function CreateClawPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [presetId, setPresetId] = useState("");
  const [name, setName] = useState("");
  const [modelAccessMode, setModelAccessMode] = useState<"byok" | "managed">("byok");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ items: Preset[] }>("/api/presets")
      .then((data) => {
        setPresets(data.items);
        if (data.items.length > 0) setPresetId(data.items[0].id);
      })
      .catch((err) => setError(err.message));
  }, []);

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    try {
      const claw = await apiFetch<{ id: string }>("/api/claws", {
        method: "POST",
        body: JSON.stringify({
          name,
          preset_id: presetId,
          model_access_mode: modelAccessMode,
        }),
      });
      router.push(`/workspace/${claw.id}/work`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create Claw");
      setLoading(false);
    }
  }

  const selectedPreset = presets.find((p) => p.id === presetId);

  return (
    <main className="app-shell stack">
      <section className="hero">
        <span className="eyebrow">Create Flow</span>
        <h1>Create a new Claw</h1>
        <p>Step {step} of 4</p>
      </section>

      {error && (
        <div style={{ color: "var(--color-error, #ef4444)", padding: "0.75rem 1rem", background: "var(--color-error-bg, #fef2f2)", borderRadius: "0.5rem" }}>
          {error}
        </div>
      )}

      <div style={{ maxWidth: "32rem", margin: "0 auto", width: "100%" }}>
        {step === 1 && (
          <div className="stack">
            <h2>Select a preset</h2>
            <p style={{ opacity: 0.7 }}>Choose a starting configuration for your Claw.</p>
            {presets.map((preset) => (
              <label
                key={preset.id}
                style={{
                  display: "block",
                  padding: "1rem",
                  border: preset.id === presetId ? "2px solid var(--color-accent, #3b82f6)" : "1px solid var(--color-border, #333)",
                  borderRadius: "0.5rem",
                  cursor: "pointer",
                  background: preset.id === presetId ? "var(--color-accent-bg, rgba(59,130,246,0.1))" : "transparent",
                }}
              >
                <input
                  type="radio"
                  name="preset"
                  value={preset.id}
                  checked={preset.id === presetId}
                  onChange={() => setPresetId(preset.id)}
                  style={{ marginRight: "0.5rem" }}
                />
                <strong>{preset.name}</strong>
                <span style={{ opacity: 0.7, marginLeft: "0.5rem" }}>{preset.description}</span>
              </label>
            ))}
            <button className="nav-link" onClick={() => setStep(2)} disabled={!presetId}>
              Next
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <h2>Name your Claw</h2>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My Dev Assistant"
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "0.5rem",
                border: "1px solid var(--color-border, #333)",
                background: "var(--color-surface, #111)",
                color: "inherit",
                fontSize: "1rem",
              }}
            />
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="nav-link" onClick={() => setStep(1)}>Back</button>
              <button className="nav-link" onClick={() => setStep(3)} disabled={!name.trim()}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="stack">
            <h2>Model access mode</h2>
            <p style={{ opacity: 0.7 }}>How should your Claw access AI models?</p>
            {(["byok", "managed"] as const).map((mode) => (
              <label
                key={mode}
                style={{
                  display: "block",
                  padding: "1rem",
                  border: mode === modelAccessMode ? "2px solid var(--color-accent, #3b82f6)" : "1px solid var(--color-border, #333)",
                  borderRadius: "0.5rem",
                  cursor: "pointer",
                  background: mode === modelAccessMode ? "var(--color-accent-bg, rgba(59,130,246,0.1))" : "transparent",
                }}
              >
                <input
                  type="radio"
                  name="mode"
                  value={mode}
                  checked={mode === modelAccessMode}
                  onChange={() => setModelAccessMode(mode)}
                  style={{ marginRight: "0.5rem" }}
                />
                <strong>{mode === "byok" ? "Bring Your Own Key (BYOK)" : "Managed"}</strong>
                <span style={{ opacity: 0.7, display: "block", marginTop: "0.25rem", marginLeft: "1.5rem" }}>
                  {mode === "byok"
                    ? "Use your own API keys for model providers."
                    : "We handle model access for you (usage-based billing)."}
                </span>
              </label>
            ))}
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="nav-link" onClick={() => setStep(2)}>Back</button>
              <button className="nav-link" onClick={() => setStep(4)}>Next</button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="stack">
            <h2>Review &amp; Launch</h2>
            <div className="table-like">
              <div className="table-row">
                <strong>Preset</strong>
                <span>{selectedPreset?.name}</span>
              </div>
              <div className="table-row">
                <strong>Name</strong>
                <span>{name}</span>
              </div>
              <div className="table-row">
                <strong>Model Access</strong>
                <span>{modelAccessMode === "byok" ? "BYOK" : "Managed"}</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="nav-link" onClick={() => setStep(3)} disabled={loading}>
                Back
              </button>
              <button className="nav-link" onClick={handleSubmit} disabled={loading}>
                {loading ? "Creating..." : "Launch Claw"}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
