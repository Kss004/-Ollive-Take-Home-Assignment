import { notFound } from "next/navigation";

import { Chat } from "@/components/Chat";
import { getConversation } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  try {
    const conv = await getConversation(id);
    return <Chat conversationId={conv.id} initialMessages={conv.messages} />;
  } catch {
    notFound();
  }
}
