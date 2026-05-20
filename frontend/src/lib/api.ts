export type AgentEvent =
  | { type: "text"; delta: string }
  | { type: "tool_use"; name: string; input: any }
  | { type: "tool_result"; name: string; result: any }
  | { type: "citation"; url: string; title: string; category?: string; snippet?: string }
  | { type: "done" }
  | { type: "error"; message: string };

export type ChatMessage = { role: "user" | "assistant"; content: string };

export async function streamChat(
  messages: ChatMessage[],
  onEvent: (evt: AgentEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const dataLines = frame
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart());
      if (!dataLines.length) continue;
      const payload = dataLines.join("\n");
      try {
        const evt = JSON.parse(payload) as AgentEvent;
        onEvent(evt);
      } catch {
        // ignore non-JSON frames
      }
    }
  }
}

export async function getStatus(): Promise<any> {
  const r = await fetch("/api/status");
  return r.json();
}

export async function startIngest(force = false): Promise<any> {
  const r = await fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force }),
  });
  return r.json();
}
