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

export function SourcesPanel({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="mt-6 pt-4 border-t border-slate-200">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
        Sources
      </div>
      <ol className="space-y-2.5">
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
    </div>
  );
}
