// Browser → NEXT_PUBLIC_CHAT_API_URL (e.g. http://localhost:8000)
// Server (SSR inside docker network) → CHAT_API_URL (e.g. http://chat-api:8000)
export const API_URL =
  typeof window === "undefined"
    ? process.env.CHAT_API_URL ||
      process.env.NEXT_PUBLIC_CHAT_API_URL ||
      "http://chat-api:8000"
    : process.env.NEXT_PUBLIC_CHAT_API_URL || "http://localhost:8000";

export type Provider = {
  name: string;
  models: string[];
};

export type ProvidersResponse = {
  default: { provider: string; model: string };
  providers: Provider[];
};

export type Conversation = {
  id: string;
  title: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sequence: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type ConversationWithMessages = Conversation & {
  messages: ConversationMessage[];
};

export async function fetcher<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} on ${path}`);
  return (await res.json()) as T;
}

export async function createConversation(input: {
  title?: string;
  provider?: string;
  model?: string;
}): Promise<Conversation> {
  return fetcher<Conversation>("/conversations", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listConversations(): Promise<Conversation[]> {
  return fetcher<Conversation[]>("/conversations");
}

export async function getConversation(id: string): Promise<ConversationWithMessages> {
  return fetcher<ConversationWithMessages>(`/conversations/${id}`);
}

export async function cancelConversation(id: string): Promise<void> {
  await fetch(`${API_URL}/conversations/${id}/cancel`, { method: "POST" });
}

export async function archiveConversation(id: string): Promise<void> {
  await fetch(`${API_URL}/conversations/${id}/archive`, { method: "POST" });
}

export async function getProviders(): Promise<ProvidersResponse> {
  return fetcher<ProvidersResponse>("/providers");
}
