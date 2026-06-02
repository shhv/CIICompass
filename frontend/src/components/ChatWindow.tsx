import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent, type ChatMessage } from "../lib/api";
import { MessageBubble, type ToolCall } from "./MessageBubble";
import type { Citation } from "./Citation";
import { Composer } from "./Composer";

type UIMessage = ChatMessage & {
  citations?: Citation[];
  toolCalls?: ToolCall[];
  pending?: boolean;
  timestamp?: number; // ms since epoch; persisted in localStorage alongside message content
};

const HISTORY_KEY = "cii.chatHistory";

function loadHistory(): UIMessage[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as UIMessage[];
    return parsed.map((m) => (m.pending ? { ...m, pending: false } : m));
  } catch {
    return [];
  }
}

function saveHistory(msgs: UIMessage[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(msgs.filter((m) => !m.pending)));
  } catch {
    // Quota exceeded or private mode — fail silently
  }
}

export function ChatWindow({ onClearReady }: { onClearReady?: (fn: () => void) => void }) {
  const [messages, setMessages] = useState<UIMessage[]>(loadHistory);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  useEffect(() => {
    if (!onClearReady) return;
    onClearReady(() => {
      localStorage.removeItem(HISTORY_KEY);
      setMessages([]);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = async (text: string) => {
    // Stamp both messages at send time so timestamps survive localStorage round-trips
    const now = Date.now();
    const next: UIMessage[] = [
      ...messages,
      { role: "user", content: text, timestamp: now },
      { role: "assistant", content: "", citations: [], toolCalls: [], pending: true, timestamp: now },
    ];
    setMessages(next);
    setBusy(true);

    const history: ChatMessage[] = next
      .filter((m) => !m.pending)
      .map((m) => ({ role: m.role, content: m.content }));

    const update = (fn: (m: UIMessage) => UIMessage) =>
      setMessages((prev) => {
        const copy = [...prev];
        const idx = copy.length - 1;
        copy[idx] = fn(copy[idx]);
        return copy;
      });

    const onEvent = (evt: AgentEvent) => {
      if (evt.type === "text") {
        update((m) => ({ ...m, content: (m.content || "") + evt.delta }));
      } else if (evt.type === "tool_use") {
        update((m) => ({ ...m, toolCalls: [...(m.toolCalls || []), { name: evt.name, input: evt.input }] }));
      } else if (evt.type === "citation") {
        update((m) => {
          const list = m.citations || [];
          if (list.some((c) => c.url === evt.url)) return m;
          return {
            ...m,
            citations: [...list, { url: evt.url, title: evt.title, category: evt.category, snippet: evt.snippet }],
          };
        });
      } else if (evt.type === "done") {
        update((m) => ({ ...m, pending: false }));
      } else if (evt.type === "error") {
        update((m) => ({ ...m, content: (m.content || "") + `\n\n_Error: ${evt.message}_`, pending: false }));
      }
    };

    try {
      await streamChat(history, onEvent);
    } catch (e: any) {
      update((m) => ({ ...m, content: (m.content || "") + `\n\n_Error: ${e?.message || e}_`, pending: false }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50">
      <div className="flex-1 overflow-y-auto px-6">
        <div className="max-w-4xl mx-auto py-6">
          {messages.length === 0 && (
            <div className="text-center text-slate-500 mt-16">
              <div className="text-3xl font-semibold mb-3 text-slate-800">CII Assistant</div>
              <div className="text-base">
                Ask anything about the CII platform — config, APIs, releases, troubleshooting.
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble
              key={i}
              role={m.role}
              content={m.content}
              citations={m.citations}
              toolCalls={m.toolCalls}
              pending={m.pending}
              timestamp={m.timestamp}
              question={
                m.role === "assistant" && i > 0 && messages[i - 1].role === "user"
                  ? messages[i - 1].content
                  : undefined
              }
            />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
      <Composer onSend={send} disabled={busy} />
    </div>
  );
}
