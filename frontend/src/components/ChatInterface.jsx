import { useState, useEffect, useRef } from "react";
import { api } from "../api";

export default function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [input,    setInput]    = useState("");
  const [typing,   setTyping]   = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    api.chatHistory().then(setMessages).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing]);

  async function send() {
    const text = input.trim();
    if (!text || typing) return;
    setInput("");

    const userMsg = { role: "user", content: text, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setTyping(true);

    try {
      const { reply } = await api.chat(text);
      setMessages(prev => [...prev, {
        role: "assistant", content: reply, timestamp: new Date().toISOString()
      }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: "assistant", content: "⚠ Could not reach the AI — is the backend running?",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setTyping(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function fmtTime(ts) {
    if (!ts) return "";
    try { return new Date(ts).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" }); }
    catch { return ""; }
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Section 4 — Store AI Chat</div>
        <span style={{ fontSize: "0.68rem", color: "var(--muted)" }}>
          Ask anything · context and notes auto-saved
        </span>
      </div>
      <div className="card">
        <div className="chat-shell">
          <div className="chat-messages">
            {messages.length === 0 && (
              <div style={{ color: "var(--muted)", fontSize: "0.78rem", textAlign: "center", padding: "32px 0" }}>
                Start a conversation — ask about your data, log context, or get recommendations.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="msg-bubble">{m.content}</div>
                <div className="msg-ts">{fmtTime(m.timestamp)}</div>
              </div>
            ))}
            {typing && (
              <div className="msg assistant">
                <div className="msg-bubble chat-typing">Analysing your data…</div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chat-input-row">
            <textarea
              className="chat-input"
              rows={2}
              placeholder={'Ask a question or log context — e.g. "we changed the window display today" or "why was it slow on Tuesday?"'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKeyDown}
            />
            <button className="chat-send" onClick={send} disabled={typing || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
