"use client";

export function ChatPanel({
  prompt,
  onPromptChange,
  onAsk,
  disabled,
  asking,
  transcript
}: {
  prompt: string;
  onPromptChange: (value: string) => void;
  onAsk: () => void;
  disabled: boolean;
  asking: boolean;
  transcript: Array<{ role: "user" | "assistant"; content: string }>;
}) {
  return (
    <section className="prompt-panel stack">
      <div>
        <h2>Ask your data</h2>
        <p className="muted">Get the result you need from the loaded dataset.</p>
      </div>
      <div className="chat-thread">
        {transcript.length === 0 ? (
          <p className="muted">Ask a question to start the conversation.</p>
        ) : (
          transcript.map((message, index) => (
            <div key={index} className={`chat-bubble ${message.role}`}>
              <span>{message.content}</span>
            </div>
          ))
        )}
      </div>
      <textarea
        rows={3}
        value={prompt}
        onChange={(event) => onPromptChange(event.target.value)}
        placeholder="What are the top 5 rows?"
      />
      <div className="toolbar">
        <button className="primary" onClick={onAsk} disabled={disabled || prompt.trim().length === 0}>
          {asking ? "Answering..." : "Ask Copilot"}
        </button>
      </div>
    </section>
  );
}
