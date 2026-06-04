import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";
import { Citation, SourcesPanel } from "./Citation";
import { sendFeedback } from "../lib/api";

function FeedbackBar({ question, answer }: { question: string; answer: string }) {
  const [vote, setVote] = useState<1 | -1 | 0>(0);
  const [busy, setBusy] = useState(false);
  const cast = async (v: 1 | -1) => {
    if (busy) return;
    let comment: string | undefined;
    if (v === -1) {
      const c = window.prompt("What went wrong? (optional — helps us improve)") ?? "";
      comment = c.trim() || undefined;
    }
    setBusy(true);
    try {
      await sendFeedback(question, answer, v, comment);
      setVote(v);
    } catch {
      // ignore
    } finally {
      setBusy(false);
    }
  };
  const base =
    "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs border transition-colors disabled:opacity-50";
  return (
    <div className="flex items-center gap-2 text-slate-500">
      <span className="text-xs">Was this helpful?</span>
      <button
        type="button"
        disabled={busy}
        onClick={() => cast(1)}
        className={`${base} ${
          vote === 1
            ? "bg-emerald-50 border-emerald-300 text-emerald-700"
            : "border-slate-200 hover:bg-slate-50"
        }`}
        aria-label="Thumbs up"
      >
        <span>👍</span>
        <span>Yes</span>
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => cast(-1)}
        className={`${base} ${
          vote === -1
            ? "bg-rose-50 border-rose-300 text-rose-700"
            : "border-slate-200 hover:bg-slate-50"
        }`}
        aria-label="Thumbs down"
      >
        <span>👎</span>
        <span>No</span>
      </button>
      {vote !== 0 && <span className="text-xs text-slate-400 ml-1">Thanks for the feedback.</span>}
    </div>
  );
}

export type ToolCall = { name: string; input: any };

// The model emits an in-answer `### References` section per the system prompt
// (see backend/app/agent/prompts.py). Split it from the body so we can collapse
// long lists; short lists (≤2) stay expanded.
function splitReferences(md: string): { body: string; refs: string | null; count: number } {
  // Match `### References` or `## References` at the start of a line.
  const m = md.match(/^\s*#{2,3}\s+References\s*$/im);
  if (!m || m.index === undefined) return { body: md, refs: null, count: 0 };
  const body = md.slice(0, m.index).trimEnd();
  const refsBlock = md.slice(m.index + m[0].length).trim();
  if (!refsBlock) return { body: md, refs: null, count: 0 };
  // Count non-empty lines that look like list/numbered entries.
  const count = refsBlock
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => /^(\[\d+\]|[-*]|\d+\.)/.test(l)).length;
  return { body, refs: refsBlock, count: count || refsBlock.split("\n").filter(Boolean).length };
}

function ReferencesBlock({
  refs,
  count,
  pending,
}: {
  refs: string;
  count: number;
  pending?: boolean;
}) {
  // Stay open while streaming so refs visibly appear, then collapse on done.
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const collapsible = count > 2;
  const open = userOpen ?? (pending || !collapsible);
  return (
    <div className="mt-8 pt-4 border-t border-slate-200">
      {collapsible ? (
        <button
          onClick={() => setUserOpen(!open)}
          className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 transition"
          aria-expanded={open}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transition-transform ${open ? "rotate-90" : ""}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          References ({count})
        </button>
      ) : (
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
          References
        </div>
      )}
      {open && (
        <div className="mt-3 prose prose-sm prose-slate max-w-none prose-p:my-1 prose-li:my-1 prose-a:text-sky-600">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{refs}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

// Shows time only for today's messages; adds date prefix for older persisted messages
function fmtTime(ts: number) {
  const d = new Date(ts);
  const isToday = d.toDateString() === new Date().toDateString();
  return isToday
    ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ToolCallsBlock({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [open, setOpen] = useState(false);
  if (!toolCalls.length) return null;
  return (
    <div className="mb-4 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-700"
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>
          {toolCalls.length} tool call{toolCalls.length > 1 ? "s" : ""}
        </span>
      </button>
      {open && (
        <ul className="mt-2 ml-4 space-y-1 text-slate-500">
          {toolCalls.map((tc, i) => (
            <li key={i} className="font-mono break-all">
              <span className="text-sky-600">{tc.name}</span>
              <span className="text-slate-400">
                ({JSON.stringify(tc.input).slice(0, 160)})
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MessageBubble({
  role,
  content,
  citations,
  toolCalls,
  pending,
  question,
  timestamp,
}: {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolCalls?: ToolCall[];
  pending?: boolean;
  question?: string;
  timestamp?: number;
}) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  // Copy button: writes raw markdown to clipboard; briefly shows "✓ Copied" then resets
  const copyContent = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} my-6`}>
      <div
        className={
          isUser
            ? "max-w-[70ch] rounded-2xl px-4 py-3 bg-sky-600 text-white whitespace-pre-wrap shadow-sm"
            : "max-w-[80ch] w-full rounded-2xl px-6 py-5 bg-white border border-slate-200 text-slate-900 shadow-sm"
        }
      >
        {!isUser && toolCalls && <ToolCallsBlock toolCalls={toolCalls} />}
        {isUser ? (
          content
        ) : (
          <div
            className="prose prose-slate prose-base max-w-none
              prose-headings:text-slate-900 prose-headings:font-bold prose-headings:tracking-tight
              [&_h1]:mt-10 [&_h1]:mb-4 [&_h1]:text-2xl
              [&_h2]:mt-10 [&_h2]:mb-4 [&_h2]:text-xl
              [&_h3]:mt-10 [&_h3]:mb-4 [&_h3]:text-lg [&_h3]:text-slate-900 [&_h3]:font-semibold
              [&_h3:first-child]:mt-0 [&_h2:first-child]:mt-0 [&_h1:first-child]:mt-0
              prose-p:text-slate-700 prose-p:leading-7 prose-p:my-5
              prose-strong:text-slate-900
              prose-a:text-sky-600 prose-a:font-medium prose-a:no-underline hover:prose-a:underline
              prose-code:text-rose-600 prose-code:bg-slate-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-medium prose-code:text-sm prose-code:before:content-none prose-code:after:content-none
              prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-pre:rounded-lg prose-pre:p-4 prose-pre:my-5
              prose-li:text-slate-700 prose-li:my-2 prose-li:leading-7
              prose-ul:my-5 prose-ol:my-5 prose-ul:pl-6 prose-ol:pl-6 prose-ul:space-y-2 prose-ol:space-y-2
              prose-blockquote:border-l-sky-500 prose-blockquote:text-slate-600 prose-blockquote:not-italic prose-blockquote:my-5
              prose-hr:border-slate-200 prose-hr:my-8
              prose-table:text-sm prose-th:bg-slate-50 prose-table:my-5"
          >
            {(() => {
              const { body, refs, count } = splitReferences(content);
              const md = body || (pending ? "_thinking…_" : "");
              return (
                <>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
                  {refs && <ReferencesBlock refs={refs} count={count} pending={pending} />}
                </>
              );
            })()}
          </div>
        )}
        {!isUser && citations && <SourcesPanel citations={citations} pending={pending} />}
        {!isUser && !pending && content && (
          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center gap-2 text-slate-500">
            <button
              onClick={copyContent}
              className="text-xs text-slate-400 hover:text-slate-600 transition mr-auto"
              title="Copy response"
            >
              {copied ? "✓ Copied" : "Copy"}
            </button>
            {question && <FeedbackBar question={question} answer={content} />}
          </div>
        )}
      </div>
      {/* Timestamp rendered below the bubble; right-aligned for user, left for assistant */}
      {timestamp && (
        <div className={`text-[11px] text-slate-400 mt-1 px-1 ${isUser ? "text-right" : ""}`}>
          {fmtTime(timestamp)}
        </div>
      )}
    </div>
  );
}
