import { ApiError } from "../../lib/api/client";

export function isAdminForbidden(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403 && error.envelope.code === "AUTH_FORBIDDEN";
}

export function pageStatusFromError(error: unknown): "forbidden" | "error" {
  return isAdminForbidden(error) ? "forbidden" : "error";
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.envelope.message : fallback;
}
