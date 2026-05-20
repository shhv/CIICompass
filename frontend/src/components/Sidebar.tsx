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
    <aside className="w-72 shrink-0 border-r border-slate-800 bg-slate-950 p-4 space-y-4">
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Index</div>
        <div className="text-sm text-slate-200">
          {status ? (
            <>
              <div>{status.pages ?? 0} pages</div>
              <div>{status.collection_size ?? 0} chunks</div>
            </>
          ) : (
            <div className="text-slate-500">loading…</div>
          )}
        </div>
      </div>
      {status?.chunks_by_category && (
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Categories</div>
          <ul className="text-xs space-y-0.5">
            {Object.entries(status.chunks_by_category).map(([k, v]) => (
              <li key={k} className="flex justify-between text-slate-300">
                <span>{k}</span>
                <span className="text-slate-500">{v as number}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Job</div>
        <div className="text-sm text-slate-300">
          {status?.job?.status ?? "idle"}
          {status?.job?.error && <div className="text-rose-400 text-xs">{status.job.error}</div>}
        </div>
      </div>
      <button
        onClick={onReindex}
        disabled={refreshing || status?.job?.status === "running"}
        className="w-full px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-400 text-white text-sm"
      >
        {status?.job?.status === "running" ? "Indexing…" : "Re-index docs"}
      </button>
    </aside>
  );
}
