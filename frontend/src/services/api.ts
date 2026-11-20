import type { ChatResponse, ConversationTurn, SourceStatistic } from "../types/api";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

type ApiErrorBody = { error?: { message?: string } };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(body.error?.message ?? "The service could not complete that request.");
  }
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  const text = await response.text();
  if (!text) {
    return undefined as unknown as T;
  }
  return JSON.parse(text) as T;
}

export const api = {
  chat: (question: string, conversationId: string) => request<ChatResponse>("/chat", {
    method: "POST", body: JSON.stringify({ question, conversation_id: conversationId }),
  }),
  sources: () => request<{ sources: SourceStatistic[]; total_chunks: number }>("/sources"),
  conversation: (id: string) => request<{ conversation_id: string; messages: ConversationTurn[] }>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
};
