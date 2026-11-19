import { ArrowUp } from "lucide-react";
import { KeyboardEvent, useRef } from "react";

type Props = { value: string; onChange: (value: string) => void; onSend: () => void; disabled: boolean };

export function ChatInput({ value, onChange, onSend, disabled }: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSend(); }
  };
  return <div className="border-t border-stone-200 bg-paper/95 px-4 pb-5 pt-4 backdrop-blur"><div className="mx-auto max-w-3xl rounded-2xl border border-stone-300 bg-white p-2 shadow-lg shadow-stone-900/[.04] focus-within:border-gold-500 focus-within:ring-4 focus-within:ring-gold-400/10"><textarea ref={textarea} value={value} disabled={disabled} onChange={event => onChange(event.target.value)} onKeyDown={keyDown} rows={1} placeholder="Ask about a project, amenities, location, or published price…" className="block max-h-36 min-h-11 w-full resize-none bg-transparent px-3 py-2 text-sm leading-6 text-ink outline-none placeholder:text-stone-400 disabled:opacity-60"/><div className="flex items-center justify-between px-2 pb-1"><span className="text-[11px] text-stone-400">Enter to send <span className="mx-1">·</span> Shift + Enter for a new line</span><button type="button" aria-label="Send question" onClick={onSend} disabled={disabled || !value.trim()} className="grid h-8 w-8 place-items-center rounded-lg bg-ink text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"><ArrowUp size={16}/></button></div></div></div>;
}
