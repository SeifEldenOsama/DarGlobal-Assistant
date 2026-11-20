import { Menu, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { MessageBubble } from "./components/MessageBubble";
import { Sidebar } from "./components/Sidebar";
import { useConversation } from "./hooks/useConversation";
import { api } from "./services/api";
import type { SourceStatistic } from "./types/api";

const suggestions = ["What amenities are publicly listed for AIDA?", "Which DarGlobal projects are in Saudi Arabia?", "Show public Wasalt listings in Jeddah with their published price."];

export default function App() {
  const conversation = useConversation();
  const [sources, setSources] = useState<SourceStatistic[]>([]);
  const [draft, setDraft] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollAnchor = useRef<HTMLDivElement>(null);
  useEffect(() => { api.sources().then(response => setSources(response.sources)).catch(() => setSources([])); }, []);
  useEffect(() => { scrollAnchor.current?.scrollIntoView({ behavior: "smooth" }); }, [conversation.messages, conversation.loading]);
  const submit = () => { conversation.send(draft); setDraft(""); };
  const pickSuggestion = (question: string) => setDraft(question);
  return <main className="flex h-[100dvh] overflow-hidden bg-paper text-ink">
    <div className={`${sidebarOpen ? "block" : "hidden"} md:block h-full shrink-0`}>
      <Sidebar
        recent={conversation.recent}
        sources={sources}
        selectedId={conversation.conversationId}
        onNew={() => { conversation.startNew(); setSidebarOpen(false); }}
        onOpen={(id) => { conversation.open(id); setSidebarOpen(false); }}
        onDelete={conversation.deleteConversation}
        onClearAll={conversation.clearAllHistory}
        onClose={() => setSidebarOpen(false)}
      />
    </div>
    <section className="flex min-w-0 flex-1 flex-col"><header className="flex h-18 items-center justify-between border-b border-stone-200 bg-paper/80 px-5 py-4 backdrop-blur"><button className="rounded-lg p-2 text-stone-600 md:hidden" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={20}/></button><div className="max-md:hidden"><p className="text-sm font-medium">Research workspace</p><p className="mt-0.5 text-xs text-stone-400">Answers are grounded in indexed public pages</p></div><div className="flex items-center gap-2 rounded-full border border-gold-400/35 bg-gold-400/10 px-3 py-1.5 text-xs font-medium text-gold-600"><span className="h-1.5 w-1.5 rounded-full bg-gold-500"/>Source-grounded</div></header>
      <div className="flex-1 overflow-y-auto"><div className="mx-auto max-w-3xl px-5 py-10 sm:px-8">{conversation.messages.length === 0 ? <Welcome onPick={pickSuggestion}/> : <div className="space-y-6">{conversation.messages.map(message => <MessageBubble key={message.id} message={message}/>)}</div>}{conversation.error && <div role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{conversation.error}</div>}<div ref={scrollAnchor}/></div></div>
      <ChatInput value={draft} onChange={setDraft} onSend={submit} disabled={conversation.loading}/>
    </section>
  </main>;
}

function Welcome({ onPick }: { onPick: (question: string) => void }) {
  return <div className="pt-8"><div className="inline-flex items-center gap-2 rounded-full bg-gold-400/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[.14em] text-gold-600"><Sparkles size={13}/>Atlas research assistant</div><h1 className="mt-6 max-w-xl font-serif text-4xl leading-tight text-ink sm:text-5xl">Real estate answers with evidence behind them.</h1><p className="mt-5 max-w-xl text-base leading-7 text-stone-500">Explore publicly available DarGlobal and Wasalt information. Every response is constrained to retrieved source material and includes direct links for verification.</p><div className="mt-10 grid gap-3 sm:grid-cols-3">{suggestions.map(question => <button key={question} onClick={() => onPick(question)} className="rounded-xl border border-stone-200 bg-white p-4 text-left text-sm leading-6 text-stone-600 shadow-sm transition hover:-translate-y-0.5 hover:border-gold-400 hover:shadow-md">{question}</button>)}</div></div>;
}
