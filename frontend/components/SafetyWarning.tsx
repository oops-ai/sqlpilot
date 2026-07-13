"use client";

import { SafetyResult } from "../lib/types";

export function SafetyWarning({ safety }: { safety: SafetyResult | null }) {
  if (!safety) {
    return <div className="status warning">Run a safety check before execution.</div>;
  }

  return (
    <div className={`status ${safety.risk_level}`}>
      <strong>{safety.risk_level.toUpperCase()}</strong>
      {safety.warnings.length > 0 ? (
        <ul>
          {safety.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : (
        <p>Query passed static safety checks for read-only execution.</p>
      )}
    </div>
  );
}
