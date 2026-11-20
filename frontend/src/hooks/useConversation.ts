import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../services/api";
import type { Citation, ConversationTurn } from "../types/api";

export type Message = { id: string; role: "user" | "assistant"; content: string; sources?: Citation[]; pending?: boolean };
type RecentConversation = { id: string; label: string };

const storageKey = "atlas-recent-conversations";
const newId = (): string => crypto.randomUUID();

function readRecent(): RecentConversation[] {
  try { return JSON.parse(localStorage.getItem(storageKey) ?? "[]") as RecentConversation[]; }
  catch { return []; }
}

export function useConversation() {
  const [conversationId, setConversationId] = useState<string>(newId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [recent, setRecent] = useState<RecentConversation[]>(readRecent);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { localStorage.setItem(storageKey, JSON.stringify(recent.slice(0, 50))); }, [recent]);

  const startNew = useCallback(() => {
    setConversationId(newId()); setMessages([]); setError(null);
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setRecent(current => current.filter(item => item.id !== id));
    api.deleteConversation(id).catch(() => {});
    if (id === conversationId) {
      setConversationId(newId());
      setMessages([]);
      setError(null);
    }
  }, [conversationId]);

  const clearAllHistory = useCallback(() => {
    const ids = recent.map(r => r.id);
    setRecent([]);
    localStorage.removeItem(storageKey);
    ids.forEach(id => api.deleteConversation(id).catch(() => {}));
    setConversationId(newId());
    setMessages([]);
    setError(null);
  }, [recent]);

  const send = useCallback(async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;
    setError(null); setLoading(true);
    const userMessage: Message = { id: newId(), role: "user", content: trimmed };
    const pendingId = newId();
    setMessages(current => [...current, userMessage, { id: pendingId, role: "assistant", content: "", pending: true }]);
    try {
      const response = await api.chat(trimmed, conversationId);
      setMessages(current => current.map(message => message.id === pendingId
        ? { id: pendingId, role: "assistant", content: response.answer, sources: response.sources } : message));
      setRecent(current => [{ id: conversationId, label: trimmed.slice(0, 46) }, ...current.filter(item => item.id !== conversationId)]);
    } catch (reason) {
      setMessages(current => current.filter(message => message.id !== pendingId));
      setError(reason instanceof Error ? reason.message : "Unable to reach the assistant.");
    } finally { setLoading(false); }
  }, [conversationId, loading]);

  const open = useCallback(async (id: string) => {
    if (id === conversationId) return;
    setError(null); setLoading(true);
    try {
      const response = await api.conversation(id);
      setConversationId(response.conversation_id);
      setMessages(response.messages.map((item: ConversationTurn, index) => ({
        id: `${id}-${index}`, role: item.role, content: item.content,
      })));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load that conversation."); }
    finally { setLoading(false); }
  }, [conversationId]);

  return useMemo(() => ({
    conversationId, messages, recent, loading, error, send, open, startNew,
    deleteConversation, clearAllHistory,
  }), [conversationId, messages, recent, loading, error, send, open, startNew, deleteConversation, clearAllHistory]);
}
