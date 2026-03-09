import type { ReactNode } from "react";

type ShellCardProps = {
  title: string;
  description: string;
  children?: ReactNode;
};

export function ShellCard({ title, description, children }: ShellCardProps) {
  return (
    <section className="frame section">
      <h3>{title}</h3>
      <p className="muted">{description}</p>
      {children ? <div style={{ marginTop: 16 }}>{children}</div> : null}
    </section>
  );
}

