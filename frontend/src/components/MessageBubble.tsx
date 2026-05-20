import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Citation, SourcesPanel } from "./Citation";

export type ToolCall = { name: string; input: any };

export function MessageBubble({
  role,
  content,
  citations,
  toolCalls,
  pending,
}: {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolCalls?: ToolCall[];
  pending?: boolean;
}) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} my-3`}>
      <div
        className={`max-w-[80ch] rounded-2xl px-4 py-3 ${
          isUser ? "bg-sky-700 text-white" : "bg-slate-900 border border-slate-800 text-slate-100"
        }`}
      >
        {toolCalls && toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {toolCalls.map((tc, i) => (
              <div key={i} className="text-xs text-slate-400 italic">
                ⚙ {tc.name}({JSON.stringify(tc.input).slice(0, 80)})
              </div>
            ))}
          </div>
        )}
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || (pending ? "…" : "")}</ReactMarkdown>
        </div>
        {!isUser && citations && <SourcesPanel citations={citations} />}
      </div>
    </div>
  );
}
