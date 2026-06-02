import { useEffect, useState } from "react";
import { getStatus, startIngest, listFeedback, sendContact } from "../lib/api";

function Section({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-slate-100 pb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 mb-2"
      >
        <span>{title}</span>
        <span className="text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}

function ContactForm() {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<null | { ok: boolean; text: string }>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || busy) return;
    setBusy(true);
    setStatus(null);
    try {
      const r = await sendContact("", "", message);
      if (r.ok) {
        setStatus({
          ok: true,
          text: r.sent
            ? "Thanks — your feedback was sent."
            : "Thanks — your feedback was logged (mail server not configured).",
        });
        setMessage("");
      } else {
        setStatus({ ok: false, text: r.error || "Failed to send." });
      }
    } catch (err: any) {
      setStatus({ ok: false, text: err?.message || "Network error." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-2">
      <textarea
        placeholder="What can we improve?"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={4}
        required
        className="w-full px-2 py-1.5 text-sm border border-slate-200 rounded-md focus:outline-none focus:border-sky-500 resize-none"
      />
      <button
        type="submit"
        disabled={busy || !message.trim()}
        className="w-full px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-medium transition"
      >
        {busy ? "Sending…" : "Send feedback"}
      </button>
      {status && (
        <div className={`text-xs ${status.ok ? "text-emerald-700" : "text-rose-700"}`}>
          {status.text}
        </div>
      )}
    </form>
  );
}

export function Sidebar({
  open,
  onToggle,
  onNewChat,
}: {
  open: boolean;
  onToggle: () => void;
  onNewChat?: () => void;
}) {
  const [status, setStatus] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [devMode, setDevMode] = useState<boolean>(() => {
    try {
      return localStorage.getItem("cii.devMode") === "1";
    } catch {
      return false;
    }
  });
  const [recent, setRecent] = useState<any[]>([]);

  const load = async () => {
    try {
      setStatus(await getStatus());
    } catch {
      // ignore
    }
    if (devMode) {
      try {
        const r = await listFeedback(20);
        setRecent(r.rows || []);
      } catch {
        // ignore
      }
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devMode]);

  useEffect(() => {
    try {
      localStorage.setItem("cii.devMode", devMode ? "1" : "0");
    } catch {
      // ignore
    }
  }, [devMode]);

  const onReindex = async () => {
    setRefreshing(true);
    try {
      await startIngest(false);
    } finally {
      setRefreshing(false);
      load();
    }
  };

  const running = status?.job?.status === "running";
  const fmt = (ts?: number) =>
    ts
      ? new Date(ts * 1000).toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";

  return (
    <aside
      className={`shrink-0 h-full bg-white border-r border-slate-200 transition-all duration-200 overflow-hidden ${
        open ? "w-80" : "w-14"
      }`}
    >
      <div className="h-14 flex items-center px-3 border-b border-slate-100">
        <button
          onClick={onToggle}
          aria-label="Toggle menu"
          className="inline-flex items-center justify-center w-9 h-9 rounded-lg hover:bg-slate-100 text-slate-700"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 6h18" strokeLinecap="round" />
            <path d="M3 12h18" strokeLinecap="round" />
            <path d="M3 18h18" strokeLinecap="round" />
          </svg>
        </button>
        {open && (
          <div className="ml-3 text-sm font-semibold text-slate-900 truncate">CII Assistant</div>
        )}
      </div>

      {open && (
        <div className="h-[calc(100%-3.5rem)] overflow-y-auto p-5 space-y-5">
          <button
            onClick={onNewChat}
            className="w-full text-left px-3 py-2 rounded hover:bg-gray-100 text-sm font-medium text-gray-700"
          >
            + New chat
          </button>

          <label className="flex items-center justify-between text-xs text-slate-600 cursor-pointer select-none">
            <span>Dev mode</span>
            <span className="relative inline-flex items-center">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={devMode}
                onChange={(e) => setDevMode(e.target.checked)}
              />
              <span className="w-9 h-5 bg-slate-200 rounded-full peer-checked:bg-sky-600 transition" />
              <span className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full transition peer-checked:translate-x-4" />
            </span>
          </label>

          <Section title="Re-indexing docs">
            <div className="text-sm text-slate-600 mb-2">
              Status:{" "}
              <span className="font-medium text-slate-900">{status?.job?.status ?? "idle"}</span>
            </div>
            {status?.job?.error && (
              <div className="text-rose-600 text-xs mb-2">{status.job.error}</div>
            )}
            <button
              onClick={onReindex}
              disabled={refreshing || running}
              className="w-full px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-medium transition"
            >
              {running ? "Indexing…" : "Re-index docs"}
            </button>
          </Section>

          <Section title="Send feedback">
            <ContactForm />
          </Section>

          {devMode && (
            <Section title="Index">
              {status ? (
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Pages</span>
                    <span className="font-medium text-slate-900">{status.pages ?? 0}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Chunks</span>
                    <span className="font-medium text-slate-900">{status.collection_size ?? 0}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Cached Q&amp;A</span>
                    <span className="font-medium text-slate-900">{status.qa_cache_size ?? 0}</span>
                  </div>
                </div>
              ) : (
                <div className="text-slate-400 text-sm">loading…</div>
              )}
            </Section>
          )}

          {devMode &&
            status?.chunks_by_category &&
            Object.keys(status.chunks_by_category).length > 0 && (
              <Section title="Categories">
                <ul className="space-y-1">
                  {Object.entries(status.chunks_by_category).map(([k, v]) => (
                    <li key={k} className="flex justify-between text-xs">
                      <span className="text-slate-600">{k}</span>
                      <span className="text-slate-400">{v as number}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

          {devMode && (
            <Section title="Recent thumbs" defaultOpen={false}>
              <a
                href={`${(import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000"}/api/feedback/export`}
                className="inline-block text-xs text-sky-600 hover:underline mb-2"
              >
                Download CSV
              </a>
              {recent.length === 0 ? (
                <div className="text-xs text-slate-400">No feedback yet.</div>
              ) : (
                <ul className="space-y-2">
                  {recent.map((r) => (
                    <li key={r.id} className="text-xs border border-slate-100 rounded-md p-2">
                      <div className="flex items-center justify-between">
                        <span className={r.vote === 1 ? "text-emerald-700" : "text-rose-700"}>
                          {r.vote === 1 ? "👍" : "👎"}
                        </span>
                        <span className="text-slate-400">{fmt(r.updated_at || r.created_at)}</span>
                      </div>
                      <div className="text-slate-700 mt-1 line-clamp-2">{r.question}</div>
                      {r.comment && (
                        <div className="text-slate-500 italic mt-1 line-clamp-3">"{r.comment}"</div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}
        </div>
      )}
    </aside>
  );
}
