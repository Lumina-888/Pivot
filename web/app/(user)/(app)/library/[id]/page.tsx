import { DocumentView } from "../../../../../features/user/components/DocumentView";

export default function DocumentPage({ params }: { params: { id: string } }) {
  return <DocumentView documentId={params.id} />;
}
