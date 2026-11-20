import { Check, Copy, ExternalLink, Sparkles } from "lucide-react";
import { useState } from "react";
import type { Message } from "../hooks/useConversation";

export function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  if (message.role === "user") return <div className="flex justify-end"><div className="max-w-[78%] rounded-2xl rounded-br-sm bg-ink px-4 py-3 text-sm leading-6 text-white shadow-sm">{message.content}</div></div>;
  if (message.pending) return <div className="flex items-center gap-3 py-2 text-sm text-stone-500"><span className="grid h-7 w-7 place-items-center rounded-full bg-gold-400/20 text-gold-600"><Sparkles size={14}/></span><span className="inline-flex gap-1"><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-gold-500 [animation-delay:-.3s]"/><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-gold-500 [animation-delay:-.15s]"/><i className="h-1.5 w-1.5 animate-bounce rounded-full bg-gold-500"/></span></div>;
  const copy = async () => { await navigator.clipboard.writeText(message.content); setCopied(true); window.setTimeout(() => setCopied(false), 1600); };
  const cleanContent = message.content
    .replace(/\*{3,}/g, "")
    .replace(/\*\*([^\*\n]+)\*\*/g, "$1")
    .replace(/\*{2,}/g, "");

  return <div className="group max-w-[88%] rounded-2xl rounded-tl-sm border border-stone-200 bg-white px-5 py-4 shadow-sm"><div className="whitespace-pre-wrap text-sm leading-7 text-stone-700">{cleanContent}</div>
    <div className="mt-4 flex flex-wrap gap-2">{message.sources?.map(source => <a key={`${source.label}-${source.source_url}`} href={source.source_url} target="_blank" rel="noreferrer" title={source.snippet} className="inline-flex items-center gap-1.5 rounded-full border border-gold-400/40 bg-gold-400/10 px-3 py-1.5 text-xs font-medium text-gold-600 transition hover:bg-gold-400/20">[{source.label}] {source.source_name}<ExternalLink size={11}/></a>)}</div>
    <button onClick={copy} className="mt-3 inline-flex items-center gap-1.5 text-xs text-stone-400 opacity-100 transition hover:text-stone-700 md:opacity-0 md:group-hover:opacity-100">{copied ? <Check size={13}/> : <Copy size={13}/>}{copied ? "Copied" : "Copy response"}</button>
  </div>;
}
