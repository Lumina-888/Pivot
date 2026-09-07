export type ScopeType = "global" | "document";

export type DocumentSummary = {
  document_id: string;
  title: string;
  space?: string;
  tags?: string[];
  classification?: string;
  created_at: string;
  current_version?: {
    version_id: string;
    version_label?: string;
    state?: string;
  } | null;
};

export type DocumentList = {
  items: DocumentSummary[];
  pagination: Record<string, unknown> | null;
};

export type DocumentVersionInfo = {
  version_id: string;
  document_id: string;
  version_label: string;
  state: string;
  current: boolean;
  content_sha256?: string;
  effective_from?: string | null;
  effective_to?: string | null;
  created_at?: string;
};

export type DocumentDetail = {
  document_id: string;
  title: string;
  space?: string;
  tags?: string[];
  classification?: string;
  created_by?: string;
  created_at: string;
  deleted_at?: string | null;
  versions?: DocumentVersionInfo[];
};

export type SearchResultItem = {
  document_id: string;
  title: string;
  space?: string;
  snippet?: string;
  version_id?: string;
  updated_at?: string;
};

export type SearchResponse = {
  items: SearchResultItem[];
  pagination: Record<string, unknown> | null;
};

export type ConversationSummary = {
  conversation_id: string;
  owner_id: string;
  title: string;
  scope_type: ScopeType;
  scope_document_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type ConversationList = {
  items: ConversationSummary[];
  pagination: Record<string, unknown> | null;
};

export type Message = {
  message_id: string;
  conversation_id: string;
  sender: string;
  content: string;
  status: string;
  run_id?: string | null;
  created_at: string;
};

export type MessageList = {
  items: Message[];
};

export type RunCreated = {
  run_id: string;
  message_id: string;
  initial_state: Record<string, unknown>;
  request_id: string;
};

export type ExportFormat = "markdown" | "docx";

export type ExportCreated = {
  export_id: string;
  state: "requested";
};

export type ExportStatus = {
  export_id: string;
  state: string;
  download_url?: string | null;
  expires_at: string;
};

export type CitationView = {
  citation_id?: string;
  document_id?: string;
  title?: string;
  locator?: string;
  snippet?: string;
};

export type ChatStatus =
  | "idle"
  | "loading"
  | "answered"
  | "uncertain"
  | "refused"
  | "failed"
  | "cancelled";

export type ChatViewState = {
  conversationId: string | null;
  runId: string | null;
  messageId: string | null;
  question: string;
  answer: string;
  status: ChatStatus;
  stage: string;
  citations: CitationView[];
  evidenceOpen: boolean;
  selectedCitation: CitationView | null;
  errorMessage: string | null;
  scopeType: ScopeType;
  scopeDocumentId: string | null;
};

export type ResolvedScope = {
  scope_type: ScopeType;
  scope_document_id?: string;
};
