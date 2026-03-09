export const appConfig = {
  name: "LaunchClaw",
  tagline: "Launch from the console, then mostly live inside the Claw.",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
} as const;

