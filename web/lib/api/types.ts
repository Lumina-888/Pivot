export type ErrorCode =
  | "AUTH_INVALID_CREDENTIALS"
  | "AUTH_FORBIDDEN"
  | "RESOURCE_NOT_FOUND"
  | "RESOURCE_FORBIDDEN"
  | "IDEMPOTENCY_CONFLICT"
  | "UNSUPPORTED_EXTENSION"
  | "INVALID_FILE_SIGNATURE"
  | "UNSUPPORTED_SCAN_PDF"
  | "ENCRYPTED_FILE"
  | "CORRUPTED_FILE"
  | "RESOURCE_LIMIT"
  | "EXTERNAL_LLM_NOT_ALLOWED"
  | "PROVIDER_TIMEOUT"
  | "PROVIDER_RATE_LIMITED"
  | "PROVIDER_TEMPORARY_ERROR"
  | "RUN_CANCELLED"
  | "RUN_TIMEOUT"
  | "VERIFICATION_UNAVAILABLE"
  | "EXPORT_EXPIRED";

export type ErrorEnvelope = {
  code: ErrorCode | string;
  message: string;
  request_id: string;
  details?: Record<string, unknown>;
  retryable?: boolean;
};

export type LoginSuccess = {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  refresh_token_cookie?: boolean;
};

export type ScopeType = "global" | "document";

export type SseEnvelope = {
  run_id: string;
  message_id: string;
  seq: number;
  timestamp: string;
  stage: string;
  payload: Record<string, unknown>;
};
