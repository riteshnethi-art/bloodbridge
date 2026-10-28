import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, CheckCircle2, Send, UserRound } from "lucide-react";
import { api } from "../api";
import { Badge, Button, Card, ErrorText, Notice } from "../components/ui";
import type { AssistantProposal, AssistantResponse } from "../types";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  response?: AssistantResponse;
}

const FIELD_LABELS: Record<string, string> = {
  blood_group: "blood group", city: "city", hospital: "hospital", units: "units",
  urgency: "urgency", needed_by: "time", requester_name: "name",
  contact_value: "contact", notes: "notes",
};

export default function Assistant() {
  const [sessionId] = useState(() => `web-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<string | null>(null);
  const [waDemo, setWaDemo] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return; // React StrictMode runs effects twice in dev
    startedRef.current = true;
    api<AssistantResponse>("/api/assistant/message", {
      body: { session_id: sessionId, message: "start" },
    }).then((r) => {
      setMode(r.mode);
      setMessages([{ role: "assistant", text: r.reply, response: r }]);
    }).catch((err) => setError(err instanceof Error ? err.message : "Assistant unavailable"));
    api<{ demo: boolean }>("/api/whatsapp/status")
      .then((s) => setWaDemo(s.demo))
      .catch(() => setWaDemo(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError("");
    setInput("");
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    try {
      const r = await api<AssistantResponse>("/api/assistant/message", {
        body: { session_id: sessionId, message: trimmed },
      });
      setMessages((m) => [...m, { role: "assistant", text: r.reply, response: r }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Message failed");
    } finally {
      setBusy(false);
    }
  };

  const last = [...messages].reverse().find((m) => m.role === "assistant")?.response;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Bridge Assistant</h1>
          <p className="text-sm text-stone-600">Conversational blood-request intake - step by step, with your explicit confirmation.</p>
        </div>
        {mode && (
          <Badge tone={mode === "deterministic_demo" ? "amber" : "green"}>
            {mode === "deterministic_demo" ? "Demo mode (deterministic)" : "AI enhanced"}
          </Badge>
        )}
      </div>

      {waDemo && (
        <div className="mb-3">
          <Notice kind="info">
            This WhatsApp-style chat runs inside BloodBridge (Demo Mode). When the official
            WhatsApp Business Cloud API is configured, the same assistant works over WhatsApp -
            until then nothing is sent to any external network.
          </Notice>
        </div>
      )}

      <Card className="flex h-[32rem] flex-col overflow-hidden">
        <div className="flex-1 space-y-3 overflow-y-auto bg-stone-50 p-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${m.role === "user" ? "bg-stone-200 text-stone-600" : "bg-brand-600 text-white"}`}>
                {m.role === "user" ? <UserRound size={14} /> : <Bot size={14} />}
              </span>
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${m.role === "user" ? "bg-brand-600 text-white" : "border border-stone-200 bg-white text-stone-800"}`}>
                {m.text}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-white"><Bot size={14} /></span>
              <div className="rounded-2xl border border-stone-200 bg-white px-3.5 py-2.5 text-sm text-stone-400">typing...</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Proposal card */}
        {last?.proposal && !last.done && (
          <div className="border-t border-stone-200 bg-white p-3">
            <div className="rounded-lg border border-brand-200 bg-brand-50/50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">Request ready to submit</p>
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-stone-700">
                {Object.entries(last.proposal as AssistantProposal).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-stone-400">{FIELD_LABELS[k] ?? k}: </span>
                    <span className="font-medium">{String(v) || "-"}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => send("__approve__")}>
                  <CheckCircle2 size={14} /> Approve & submit
                </Button>
                {["blood_group", "units", "urgency", "needed_by"].map((f) => (
                  <Button key={f} size="sm" variant="ghost" onClick={() => send(`edit ${FIELD_LABELS[f]}`)}>
                    edit {FIELD_LABELS[f]}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Quick chips */}
        {last && last.chips.length > 0 && !last.done && (
          <div className="flex flex-wrap gap-1.5 border-t border-stone-100 px-3 pt-2">
            {last.chips.map((c) => (
              <button key={c} className="rounded-full border border-stone-300 bg-white px-3 py-1 text-xs text-stone-700 hover:bg-stone-100"
                      onClick={() => send(c)} disabled={busy}>
                {c}
              </button>
            ))}
          </div>
        )}

        {error && <div className="px-3 pt-2"><ErrorText>{error}</ErrorText></div>}

        {last?.done && last.request_public_id && (
          <div className="border-t border-stone-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
            Request {last.request_public_id} submitted.{" "}
            <Link className="font-semibold underline" to={`/requests/${last.request_public_id}/matches`}>
              View potential donors
            </Link>{" "}
            · <Link className="underline" to="/dashboard/requester">My requests</Link>
          </div>
        )}

        <form className="flex gap-2 border-t border-stone-200 bg-white p-3"
              onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <input
            className="input-base"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={last?.awaiting === "confirm" ? "Type 'confirm' to submit, or 'edit city'..." : "Type your answer..."}
            disabled={busy}
          />
          <Button type="submit" loading={busy} aria-label="Send">
            <Send size={16} />
          </Button>
        </form>
      </Card>

      <p className="mt-3 text-xs text-stone-500">{last?.disclaimer}</p>
    </div>
  );
}
