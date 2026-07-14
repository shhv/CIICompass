import { useEffect, useRef, useState } from "react";
import { streamChat, type AgentEvent, type ChatMessage, type FileAttachment } from "../lib/api";
import { MessageBubble, type ToolCall } from "./MessageBubble";
import type { Citation } from "./Citation";
import { Composer } from "./Composer";

type UIMessage = ChatMessage & {
  citations?: Citation[];
  toolCalls?: ToolCall[];
  pending?: boolean;
  timestamp?: number;
  hasFiles?: boolean;
  filePreviews?: { filename: string; preview?: string }[];
};

const HISTORY_KEY_PREFIX = "cii.chatHistory";

function historyKey(product: string): string {
  return product === "cii" ? HISTORY_KEY_PREFIX : `${HISTORY_KEY_PREFIX}.${product}`;
}

function loadHistory(product: string): UIMessage[] {
  try {
    const raw = localStorage.getItem(historyKey(product));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as UIMessage[];
    return parsed.map((m) => (m.pending ? { ...m, pending: false } : m));
  } catch {
    return [];
  }
}

function saveHistory(msgs: UIMessage[], product: string) {
  try {
    // Strip file data from localStorage to avoid bloat
    const stripped = msgs.filter((m) => !m.pending).map((m) => {
      const { files, ...rest } = m;
      return rest;
    });
    localStorage.setItem(historyKey(product), JSON.stringify(stripped));
  } catch {
    // Quota exceeded or private mode — fail silently
  }
}

export function ChatWindow({ onClearReady, product }: { onClearReady?: (fn: () => void) => void; product: "cii" | "duo" }) {
  const [messages, setMessages] = useState<UIMessage[]>(() => loadHistory(product));
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(loadHistory(product));
  }, [product]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    saveHistory(messages, product);
  }, [messages, product]);

  useEffect(() => {
    if (!onClearReady) return;
    onClearReady(() => {
      localStorage.removeItem(historyKey(product));
      setMessages([]);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product]);

  const send = async (text: string, files?: FileAttachment[]) => {
    const now = Date.now();
    const userMsg: UIMessage = {
      role: "user",
      content: text,
      timestamp: now,
      ...(files && { files, hasFiles: true, filePreviews: files.map((f) => ({ filename: f.filename })) }),
    };
    const next: UIMessage[] = [
      ...messages,
      userMsg,
      { role: "assistant", content: "", citations: [], toolCalls: [], pending: true, timestamp: now },
    ];
    setMessages(next);
    setBusy(true);

    const history: ChatMessage[] = next
      .filter((m) => !m.pending)
      .map((m) => ({ role: m.role, content: m.content, ...(m.files && { files: m.files }) }));

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
      await streamChat(history, onEvent, undefined, product);
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
              <div className="text-3xl font-semibold mb-3 text-slate-800">
                Security DocPilot
              </div>
              <div className="text-base">
                {product === "duo"
                  ? "Ask anything about Duo Security — MFA, admin panel, integrations, troubleshooting."
                  : "Ask anything about the CII platform — config, APIs, releases, troubleshooting."}
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
              filePreviews={m.filePreviews}
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
