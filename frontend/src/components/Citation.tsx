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
      className="inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1 mx-0.5 text-xs rounded-full bg-sky-700 hover:bg-sky-600 text-white"
      title={url}
    >
      {index}
    </a>
  );
}

export function SourcesPanel({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Sources</div>
      <ol className="space-y-2">
        {citations.map((c, i) => (
          <li key={c.url + i} className="text-sm">
            <span className="text-slate-500 mr-2">[{i + 1}]</span>
            <a className="text-sky-400 hover:underline" href={c.url} target="_blank" rel="noreferrer">
              {c.title || c.url}
            </a>
            {c.category && <span className="ml-2 text-xs text-slate-500">{c.category}</span>}
            {c.snippet && <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{c.snippet}</div>}
          </li>
        ))}
      </ol>
    </div>
  );
}
