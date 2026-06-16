import React, { useState, useRef, useEffect } from "react";

const APP_NAME = "ArmGenius";
const TAGLINE = "Natural language meets physical motion.";

const STARTER_COMMANDS = [
  "Wave hello!",
  "Point to the right",
  "Pick something up",
  "Bow to the judges",
];

// Human-readable labels for each action name
const ACTION_LABELS = {
  point_left: "pointing left",
  point_right: "pointing right",
  center: "centering",
  wave: "waving",
  grab: "grabbing",
  release: "releasing",
  bow: "bowing",
  none: null,
};

function ArmStatusBanner({ action }) {
  const label = ACTION_LABELS[action];
  if (!label) return null;

  return (
    <div className="slide-down flex items-center gap-2 text-xs font-medium text-[#276749] bg-[#f0fff4] border border-[#9ae6b4] rounded-lg px-3 py-2 mt-2">
      <span className="relative flex h-2 w-2">
        <span className="arm-ping absolute inline-flex h-full w-full rounded-full bg-[#38a169] opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38a169]" />
      </span>
      Arm executing: <span className="font-semibold">{label}</span>
    </div>
  );
}

function StarterChips({ onSelect, disabled }) {
  return (
    <div className="flex flex-wrap gap-2 px-6 pb-4 max-w-2xl mx-auto">
      {STARTER_COMMANDS.map((cmd) => (
        <button
          key={cmd}
          onClick={() => onSelect(cmd)}
          disabled={disabled}
          className="rounded-full border border-[var(--color-pine)] text-[var(--color-pine)] text-xs font-medium px-3 py-1.5 hover:bg-[var(--color-pine)] hover:text-white transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {cmd}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm ArmGenius. Tell me what to do and I'll move the arm. Try one of the commands below, or describe any action you'd like.",
      armAction: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState([]);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function sendMessage(text) {
    const trimmed = typeof text === "string" ? text.trim() : input.trim();
    if (!trimmed || loading) return;

    const userMsg = { role: "user", content: trimmed };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setLoading(true);
    setSources([]);

    // Build the messages array in the shape the backend expects
    const apiMessages = next.map(({ role, content }) => ({ role, content }));

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      setMessages([
        ...next,
        {
          role: "assistant",
          content: data.reply,
          armAction: data.arm_action || null,
        },
      ]);
      setSources(data.sources || []);
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content:
            "Couldn't reach the backend. Make sure Flask is running on port 5000 and your API key is set in backend/.env.",
          armAction: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleFormSubmit(e) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleChipClick(cmd) {
    sendMessage(cmd);
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[var(--color-line)] bg-white/80 backdrop-blur-sm sticky top-0 z-10 px-6 py-4">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <h1
              className="text-xl font-bold tracking-tight text-[var(--color-pine)]"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {APP_NAME}
            </h1>
            <p className="text-xs text-[var(--color-muted)] mt-0.5">{TAGLINE}</p>
          </div>
          {/* Visual badge */}
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-muted)] bg-[var(--color-surface-raised)] border border-[var(--color-line)] rounded-full px-3 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-pine-light)]" />
            LLM + Servo
          </div>
        </div>
      </header>

      {/* Message thread */}
      <main
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-6 space-y-4 max-w-2xl w-full mx-auto"
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div className={`max-w-[80%] ${m.role === "user" ? "" : "w-full"}`}>
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-[var(--color-pine)] text-white rounded-br-sm"
                    : "bg-white border border-[var(--color-line)] rounded-bl-sm text-[var(--color-ink)]"
                }`}
              >
                {m.content}
              </div>
              {/* Arm action status indicator for assistant messages */}
              {m.role === "assistant" && m.armAction && m.armAction !== "none" && (
                <ArmStatusBanner action={m.armAction} />
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-2 text-[var(--color-pine)]/70 text-sm pl-1">
            <span className="w-2 h-2 rounded-full bg-[var(--color-clay)] pulse-soft" />
            thinking…
          </div>
        )}

        {/* RAG sources */}
        {sources.length > 0 && (
          <div className="text-xs text-[var(--color-muted)] pl-1">
            Sources: {sources.join(", ")}
          </div>
        )}
      </main>

      {/* Starter command chips */}
      <StarterChips onSelect={handleChipClick} disabled={loading} />

      {/* Input bar */}
      <form
        onSubmit={handleFormSubmit}
        className="border-t border-[var(--color-line)] bg-white px-6 py-4 max-w-2xl w-full mx-auto flex gap-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Tell the arm what to do…"
          className="flex-1 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface-raised)] px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-pine-light)] focus:border-transparent transition-shadow"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-[var(--color-clay)] text-white px-5 py-2.5 text-sm font-semibold disabled:opacity-50 hover:bg-[var(--color-pine)] transition-colors duration-150"
        >
          Send
        </button>
      </form>
    </div>
  );
}
