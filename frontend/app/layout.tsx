import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "AI SQL Copilot",
  description: "Developer-focused SQL copilot workbench"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
