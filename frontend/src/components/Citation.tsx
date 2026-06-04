import { useState } from "react";

export type Citation = {
  url: string;
  title: string;
  category?: string;
  snippet?: string;
};

export function CitationChip({ index, url }: { index: number; url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1 mx-0.5 text-xs rounded-full bg-sky-100 hover:bg-sky-200 text-sky-700"
      title={url}
    >
      {index}
    </a>
  );
}

export function SourcesPanel({
  citations,
  pending,
}: {
  citations: Citation[];
  pending?: boolean;
}) {
  // Stay expanded while the answer is streaming so the user can watch sources
  // arrive. Once streaming finishes, collapse if the list is long (>2). The
  // user's explicit click wins from then on.
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const collapsible = citations.length > 2;
  const open = userOpen ?? (pending || !collapsible);
  if (!citations.length) return null;
  return (
    <div className="mt-6 pt-4 border-t border-slate-200">
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
          Sources ({citations.length})
        </button>
      ) : (
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
          Sources
        </div>
      )}
      {open && (
        <ol className="space-y-2.5 mt-3">
          {citations.map((c, i) => (
            <li key={c.url + i} className="text-sm leading-snug">
              <div className="flex items-start gap-2">
                <span className="text-slate-400 font-mono text-xs mt-0.5">[{i + 1}]</span>
                <div className="flex-1 min-w-0">
                  <a
                    className="text-sky-600 hover:underline font-medium"
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {c.title || c.url}
                  </a>
                  {c.category && (
                    <span className="ml-2 inline-block text-[10px] uppercase tracking-wide text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                      {c.category}
                    </span>
                  )}
                  {c.snippet && (
                    <div className="text-xs text-slate-500 mt-1 line-clamp-2">{c.snippet}</div>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
