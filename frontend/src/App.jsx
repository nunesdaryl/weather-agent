import { useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
  const [messages, setMessages] = useState([]); // [{ role, content }]
  const [input, setInput] = useState("");

  async function send(e) {
    e.preventDefault();
    const history = [...messages, { role: "user", content: input }];
    setMessages(history);
    setInput("");
    // Ask the agent (backend at /api/chat)
    let answer;
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input, history: messages }),
      });
      answer = (await res.json()).answer;
    } catch {
      // server down, or it sent something that isn't JSON
    }
    setMessages([...history, { role: "assistant", content: answer ?? "Error: check the server" }]);
  }

  return (
    <div style={{ maxWidth: 600, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h2>🌤️ Weather Chat</h2>
      {messages.map((m, i) => (
        <p key={i} style={{ textAlign: m.role === "user" ? "right" : "left" }}>
          <b>{m.role === "user" ? "You:" : "Agent:"}</b> {m.content}
        </p>
      ))}
      <form onSubmit={send} style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="Weather in Paris?" style={{ flex: 1, padding: 8 }} />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
