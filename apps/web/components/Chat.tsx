"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  API_URL,
  cancelConversation,
  createConversation,
  type ConversationMessage,
} from "@/lib/api";
import { ProviderPicker, type Selection } from "./ProviderPicker";

type DisplayMsg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  partial?: boolean;
  cancelled?: boolean;
};

export function Chat({
  conversationId,
  initialMessages,
}: {
  conversationId: string | null;
  initialMessages: ConversationMessage[];
}) {
  const router = useRouter();
  const [convId, setConvId] = useState<string | null>(conversationId);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<DisplayMsg[]>(() =>
    initialMessages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        cancelled: (m.metadata as { cancelled?: boolean })?.cancelled === true,
      })),
  );
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const send = useCallback(async () => {
    if (!input.trim() || !selection || streaming) return;
    const userText = input.trim();
    setInput("");

    let id = convId;
    if (!id) {
      const conv = await createConversation({
        provider: selection.provider,
        model: selection.model,
        title: userText.slice(0, 60),
      });
      id = conv.id;
      setConvId(id);
      // update URL without reload
      window.history.replaceState(null, "", `/c/${id}`);
    }

    const userMsg: DisplayMsg = { id: crypto.randomUUID(), role: "user", content: userText };
    const assistantMsg: DisplayMsg = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      partial: true,
    };
    setMessages((m) => [...m, userMsg, assistantMsg]);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          conversation_id: id,
          provider: selection.provider,
          model: selection.model,
          message: userText,
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        // SSE frames are separated by blank lines
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const ev = parseSSE(frame);
          if (!ev) continue;
          if (ev.event === "token") {
            const delta = ev.data;
            setMessages((m) => {
              const last = m[m.length - 1];
              if (!last || last.role !== "assistant") return m;
              return [...m.slice(0, -1), { ...last, content: last.content + delta }];
            });
          } else if (ev.event === "done") {
            const parsed = safeJSON(ev.data);
            setMessages((m) => {
              const last = m[m.length - 1];
              if (!last || last.role !== "assistant") return m;
              return [
                ...m.slice(0, -1),
                { ...last, partial: false, cancelled: !!parsed?.cancelled },
              ];
            });
          } else if (ev.event === "error") {
            const parsed = safeJSON(ev.data);
            setMessages((m) => {
              const last = m[m.length - 1];
              if (!last || last.role !== "assistant") return m;
              return [
                ...m.slice(0, -1),
                { ...last, partial: false, content: last.content + `\n[error] ${parsed?.message ?? "unknown"}` },
              ];
            });
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        // surface non-abort errors
        setMessages((m) => {
          const last = m[m.length - 1];
          if (!last || last.role !== "assistant") return m;
          return [...m.slice(0, -1), { ...last, partial: false, content: last.content + `\n[error] ${(err as Error).message}` }];
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      // refresh server data for the conversations list
      router.refresh();
    }
  }, [convId, input, router, selection, streaming]);

  const cancel = useCallback(async () => {
    if (!convId) return;
    await cancelConversation(convId);
    abortRef.current?.abort();
  }, [convId]);

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <div className="text-xs uppercase tracking-wider text-zinc-500">
          {convId ? `conv ${convId.slice(0, 8)}` : "new conversation"}
        </div>
        <ProviderPicker value={selection} onChange={setSelection} />
      </div>

      <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="mt-24 text-center text-zinc-500">
            <p>Start a conversation.</p>
            <p className="mt-1 text-xs">Pick a provider above, then say hi.</p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`mb-4 flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-emerald-600 text-white"
                  : "bg-zinc-800 text-zinc-100"
              } ${m.partial ? "opacity-90" : ""}`}
            >
              {m.content || (m.partial ? "…" : "")}
              {m.cancelled && (
                <div className="mt-1 text-[10px] uppercase tracking-wider text-amber-300">
                  cancelled
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(); }}
        className="flex gap-2 border-t border-zinc-800 px-4 py-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={streaming}
          className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-emerald-500"
        />
        {streaming ? (
          <button
            type="button"
            onClick={cancel}
            className="rounded-lg border border-amber-500 px-3 py-2 text-sm font-medium text-amber-300 hover:bg-amber-500/10"
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || !selection}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Send
          </button>
        )}
      </form>
    </div>
  );
}

function parseSSE(frame: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

function safeJSON(text: string): Record<string, unknown> | null {
  try { return JSON.parse(text); } catch { return null; }
}
