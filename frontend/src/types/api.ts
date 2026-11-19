export type Citation = {
  label: string;
  title: string;
  source_name: string;
  source_url: string;
  snippet: string;
};

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  sources: Citation[];
  retrieved_count: number;
};

export type ConversationTurn = { role: "user" | "assistant"; content: string; created_at: string };
export type SourceStatistic = { source_name: string; chunk_count: number };
