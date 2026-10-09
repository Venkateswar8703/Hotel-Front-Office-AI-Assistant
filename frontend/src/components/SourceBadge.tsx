import type { RAGSource } from '../types';

interface SourceBadgeProps {
  sources: RAGSource[];
}

// ─── RAG Source Badge ─────────────────────────────────────────────────────────

export function SourceBadge({ sources }: SourceBadgeProps) {
  if (!sources || !Array.isArray(sources) || sources.length === 0) return null;

  return (
    <div className="mt-2 pt-2 border-t border-stone-100">
      <p className="text-[10px] font-semibold text-hotel-muted uppercase tracking-wider mb-1.5 flex items-center gap-1">
        <span>🏨</span> Verified Hotel Reference
      </p>
      <div className="flex flex-wrap gap-1.5">
        {sources.slice(0, 3).map((src, i) => {
          const label = src.document || src.category || src.source || 'Hotel Guide';
          const title = src.question ? `Q: ${src.question}` : `Source: ${label}`;

          return (
            <span
              key={i}
              className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-amber-50 border border-amber-200 rounded-full text-[10px] text-amber-800 font-medium"
              title={title}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
              {label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
