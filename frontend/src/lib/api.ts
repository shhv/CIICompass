const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "";

export type AgentEvent =
  | { type: "text"; delta: string }
  | { type: "tool_use"; name: string; input: any }
  | { type: "tool_result"; name: string; result: any }
  | { type: "citation"; url: string; title: string; category?: string; snippet?: string }
  | { type: "done" }
  | { type: "error"; message: string };

export type FileAttachment = { filename: string; media_type: string; data: string };

export type ChatMessage = { role: "user" | "assistant"; content: string; files?: FileAttachment[] };

export async function streamChat(
  messages: ChatMessage[],
  onEvent: (evt: AgentEvent) => void,
  signal?: AbortSignal,
  product: string = "cii"
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ messages, product }),
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
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

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

export async function getStatus(product: string = "cii"): Promise<any> {
  const r = await fetch(`${API_BASE}/api/status?product=${product}`);
  return r.json();
}

export async function sendFeedback(
  question: string,
  answer: string,
  vote: 1 | -1,
  comment?: string
): Promise<any> {
  const r = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, answer, vote, comment }),
  });
  return r.json();
}

export async function listFeedback(limit = 20, only?: "up" | "down"): Promise<any> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (only) q.set("only", only);
  const r = await fetch(`${API_BASE}/api/feedback/list?${q}`);
  return r.json();
}

export async function sendContact(
  name: string,
  email: string,
  message: string
): Promise<any> {
  const r = await fetch(`${API_BASE}/api/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, message }),
  });
  return r.json();
}

export async function startIngest(force = false, product = "cii"): Promise<any> {
  const r = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force, product }),
  });
  return r.json();
}
