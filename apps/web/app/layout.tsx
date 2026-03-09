import type { Metadata } from "next";
import type { ReactNode } from "react";
import { appConfig } from "@launchclaw/config";
import "./globals.css";

export const metadata: Metadata = {
  title: `${appConfig.name} v1`,
  description: appConfig.tagline,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

