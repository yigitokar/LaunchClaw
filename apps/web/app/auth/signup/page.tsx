"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signUp({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    setSuccess(true);
    setLoading(false);
  }

  if (success) {
    return (
      <main className="app-shell stack" style={{ maxWidth: 400, margin: "4rem auto" }}>
        <h1>Check your email</h1>
        <p>We sent a confirmation link to <strong>{email}</strong>.</p>
        <Link href="/auth/login">Back to login</Link>
      </main>
    );
  }

  return (
    <main className="app-shell stack" style={{ maxWidth: 400, margin: "4rem auto" }}>
      <h1>Create your account</h1>
      <form onSubmit={handleSubmit} className="stack">
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {error && <p style={{ color: "var(--color-error, red)" }}>{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Creating account..." : "Sign up"}
        </button>
      </form>
      <p>
        Already have an account? <Link href="/auth/login">Log in</Link>
      </p>
    </main>
  );
}
