import { Building2, ChevronRight, Database, MessageSquarePlus, PanelLeftClose, Trash2 } from "lucide-react";
import { BrandMark } from "./BrandMark";
import type { SourceStatistic } from "../types/api";

type Props = {
  recent: { id: string; label: string }[];
  sources: SourceStatistic[];
  selectedId: string;
  onNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
  onClose?: () => void;
};

export function Sidebar({ recent, sources, selectedId, onNew, onOpen, onDelete, onClearAll, onClose }: Props) {
  return (
    <aside className="flex h-full w-[290px] shrink-0 flex-col border-r border-stone-200 bg-[#fcfbf8] p-5 max-md:absolute max-md:z-30 max-md:shadow-panel">
      <div className="flex items-center gap-3 px-1">
        <BrandMark />
        <div>
          <p className="font-serif text-lg leading-none text-ink">Atlas</p>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[.18em] text-gold-600">Property intelligence</p>
        </div>
        {onClose && (
          <button className="ml-auto rounded-lg p-2 text-stone-500 md:hidden" aria-label="Close navigation" onClick={onClose}>
            <PanelLeftClose size={18} />
          </button>
        )}
      </div>

      <button
        onClick={onNew}
        className="mt-6 flex shrink-0 items-center justify-center gap-2 rounded-xl bg-ink px-4 py-3 text-sm font-medium text-white transition hover:bg-stone-800 shadow-sm"
      >
        <MessageSquarePlus size={17} />New conversation
      </button>

      <section className="mt-6 flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between px-2 pb-2">
          <p className="text-[10px] font-bold uppercase tracking-[.16em] text-stone-400">Recent research</p>
          {recent.length > 0 && (
            <button
              onClick={onClearAll}
              className="text-[11px] font-medium text-stone-400 hover:text-red-600 transition"
              title="Clear all research history"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 pr-1 overscroll-contain">
          {recent.length === 0 ? (
            <p className="px-2 py-3 text-sm leading-5 text-stone-400">Your questions stay available in this browser.</p>
          ) : (
            recent.map(item => (
              <div
                key={item.id}
                className={`group flex w-full items-center gap-1.5 rounded-lg px-2 py-2 text-left text-sm transition ${
                  item.id === selectedId ? "bg-stone-100 text-ink font-medium" : "text-stone-600 hover:bg-stone-100"
                }`}
              >
                <button
                  onClick={() => onOpen(item.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                >
                  <Building2 size={15} className="shrink-0 text-gold-600" />
                  <span className="truncate">{item.label}</span>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(item.id);
                  }}
                  className="shrink-0 rounded p-1 text-stone-400 hover:text-red-600 transition opacity-0 group-hover:opacity-100 focus:opacity-100"
                  aria-label="Delete conversation"
                  title="Delete conversation"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="mt-4 shrink-0 rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-medium text-ink">
          <Database size={15} className="text-gold-600" />Indexed public sources
        </div>
        <div className="mt-3 space-y-2">
          {sources.length ? (
            sources.map(source => (
              <div className="flex justify-between text-xs text-stone-500" key={source.source_name}>
                <span>{source.source_name}</span>
                <span>{source.chunk_count} chunks</span>
              </div>
            ))
          ) : (
            <p className="text-xs leading-5 text-stone-400">Run ingestion to make public sources available.</p>
          )}
        </div>
      </section>
    </aside>
  );
}
