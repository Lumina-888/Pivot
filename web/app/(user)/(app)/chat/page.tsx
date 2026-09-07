import { ChatWorkspace } from "../../../../features/user/components/ChatWorkspace";

export default function ChatPage({
  searchParams,
}: {
  searchParams: { q?: string | string[]; scope?: string | string[]; document_id?: string | string[] };
}) {
  return <ChatWorkspace searchParams={searchParams} />;
}
