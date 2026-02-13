import type { SourceItem } from "../api/chat";

interface SourcesPanelProps {
  sources: SourceItem[];
}

export function SourcesPanel({ sources }: SourcesPanelProps) {
  return (
    <aside className="sources-column">
      <div className="sources-header">
        <h3>Sources Used</h3>
        <span>{sources.length} result(s)</span>
      </div>
      {sources.length === 0 && <p className="muted">Sources appear after assistant responses.</p>}
      {sources.map((source, index) => (
        <article key={`${source.source}-${index}`} className="source-card">
          <div className="source-card-head">
            <strong>{source.source}</strong>
            <small>{source.score > 0 ? `${(Math.max(0, 1 - source.score) * 100).toFixed(1)}%` : "BM25"}</small>
          </div>
          <p>{source.preview}</p>
        </article>
      ))}
    </aside>
  );
}
