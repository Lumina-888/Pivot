import { ChatWorkspace } from "../../../../../features/user/components/ChatWorkspace";

export default function ConversationPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { q?: string | string[]; scope?: string | string[]; document_id?: string | string[] };
}) {
  return <ChatWorkspace conversationId={params.id} searchParams={searchParams} />;
}
