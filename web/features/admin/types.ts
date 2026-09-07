export type Role = "admin" | "user";
export type UserStatus = "active" | "disabled";

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

export type DocumentActionResponse = {
  document_id: string;
  accepted: boolean;
};

export type AdminUser = {
  user_id: string;
  username: string;
  role: Role;
  status: UserStatus;
  created_at: string;
  updated_at?: string;
};

export type AdminUserList = {
  items: AdminUser[];
  pagination: Record<string, unknown> | null;
};

export type AdminTaskInfo = {
  task_id: string;
  entity_type: string;
  entity_id: string;
  attempt: number;
  state: string;
  retryable: boolean;
  created_at: string;
};

export type AdminTaskList = {
  items: AdminTaskInfo[];
  pagination: Record<string, unknown> | null;
};

export type AuditEventInfo = {
  audit_event_id: string;
  actor: string;
  action: string;
  target: string;
  result: string;
  request_id?: string | null;
  run_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export type AuditEventList = {
  items: AuditEventInfo[];
  pagination: Record<string, unknown> | null;
};

export type AuditQuery = {
  actor?: string;
  action?: string;
};

export type PageStatus = "loading" | "ready" | "empty" | "error" | "forbidden";
