import { useEffect, useState } from "react";
import { getStatus, startIngest } from "../lib/api";

export function Sidebar() {
  const [status, setStatus] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      setStatus(await getStatus());
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const onReindex = async () => {
    setRefreshing(true);
    try {
      await startIngest(false);
    } finally {
      setRefreshing(false);
      load();
    }
  };

  return (
    <aside className="w-72 shrink-0 border-r border-slate-200 bg-white p-6 space-y-6">
      <div>
        <div className="text-lg font-semibold text-slate-900">CII Assistant</div>
        <div className="text-xs text-slate-500 mt-1">docs.oort.io knowledge base</div>
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
          Index
        </div>
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
          </div>
        ) : (
          <div className="text-slate-400 text-sm">loading…</div>
        )}
      </div>

      {status?.chunks_by_category && Object.keys(status.chunks_by_category).length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Categories
          </div>
          <ul className="space-y-1">
            {Object.entries(status.chunks_by_category).map(([k, v]) => (
              <li key={k} className="flex justify-between text-xs">
                <span className="text-slate-600">{k}</span>
                <span className="text-slate-400">{v as number}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
          Job
        </div>
        <div className="text-sm text-slate-700">
          {status?.job?.status ?? "idle"}
          {status?.job?.error && (
            <div className="text-rose-600 text-xs mt-1">{status.job.error}</div>
          )}
        </div>
      </div>

      <button
        onClick={onReindex}
        disabled={refreshing || status?.job?.status === "running"}
        className="w-full px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-sm font-medium transition"
      >
        {status?.job?.status === "running" ? "Indexing…" : "Re-index docs"}
      </button>
    </aside>
  );
}
