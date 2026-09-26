import { useState } from "react";
import { createRoot } from "react-dom/client";

// The two agents behind /api/chat: same tool and model, different loop
const AGENTS = {
  loop: { title: "LangChain · hand-written loop", file: "agent.py", color: "#e6f4ea" },
  graph: { title: "LangGraph · create_agent", file: "agent_graph.py", color: "#ede7f6" },
};
const MODES = [
  ["loop", "LangChain"],
  ["graph", "LangGraph"],
  ["both", "Side by side"],
];

function Pane({ impl, messages }) {
  const { title, file, color } = AGENTS[impl];
  return (
    <section style={{ flex: "1 1 280px", minWidth: 0 }}>
      <div style={{ background: color, borderRadius: 6, padding: "6px 10px" }}>
        <b>{title}</b> <code style={{ fontSize: 12, color: "#555" }}>{file}</code>
      </div>
      {messages.map((m, i) => (
        <p key={i} style={{ textAlign: m.role === "user" ? "right" : "left",
                            color: m.pending ? "#888" : undefined }}>
          <b>{m.role === "user" ? "You:" : "Agent:"}</b> {m.content}
        </p>
      ))}
    </section>
  );
}

function App() {
  const [mode, setMode] = useState("both");
  // One conversation per agent, so each keeps its own history
  const [chats, setChats] = useState({ loop: [], graph: [] }); // { impl: [{ role, content }] }
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(impl, message) {
    const history = chats[impl];
    const asked = [...history, { role: "user", content: message }];
    setChats((c) => ({ ...c, [impl]: [...asked, { role: "assistant", content: "thinking…", pending: true }] }));
    // Ask the agent (backend at /api/chat); impl picks which one answers
    let answer;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, impl }),
      });
      answer = (await res.json()).answer;
    } catch {
      // server down, or it sent something that isn't JSON
    }
    setChats((c) => ({ ...c, [impl]: [...asked, { role: "assistant", content: answer ?? "Error: check the server" }] }));
  }

  async function send(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    await Promise.all((mode === "both" ? ["loop", "graph"] : [mode]).map((impl) => ask(impl, message)));
    setBusy(false);
  }

  const shown = mode === "both" ? ["loop", "graph"] : [mode];
  return (
    <div style={{ maxWidth: mode === "both" ? 1100 : 600, margin: "40px auto", padding: "0 16px",
                  fontFamily: "sans-serif" }}>
      <h2>🌤️ Weather Chat</h2>
      <div role="group" aria-label="Agent" style={{ display: "inline-flex", border: "1px solid #999",
                                                    borderRadius: 6, overflow: "hidden", marginBottom: 16 }}>
        {MODES.map(([value, label]) => (
          <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)}
                  style={{ padding: "6px 14px", border: "none", cursor: "pointer",
                           background: mode === value ? "#222" : "#fff",
                           color: mode === value ? "#fff" : "#222" }}>
            {label}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 24 }}>
        {shown.map((impl) => <Pane key={impl} impl={impl} messages={chats[impl]} />)}
      </div>
      <form onSubmit={send} style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Weather in Paris?" style={{ flex: 1, padding: 8 }} />
        <button type="submit" disabled={busy}>Send</button>
      </form>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
