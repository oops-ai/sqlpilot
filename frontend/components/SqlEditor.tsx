"use client";

import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export function SqlEditor({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="panel" style={{ minHeight: 360, padding: 0, overflow: "hidden" }}>
      <MonacoEditor
        height="360px"
        defaultLanguage="sql"
        theme="vs"
        value={value}
        onChange={(next) => onChange(next ?? "")}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          wordWrap: "on",
          automaticLayout: true
        }}
      />
    </div>
  );
}
