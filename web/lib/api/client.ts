import type { ErrorEnvelope } from "./types";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly envelope: ErrorEnvelope;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.message);
    this.name = "ApiError";
    this.status = status;
    this.envelope = envelope;
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.request_id === "string"
  );
}

async function decodeError(response: Response): Promise<ErrorEnvelope> {
  try {
    const value: unknown = await response.json();
    if (isErrorEnvelope(value)) {
      return value;
    }
  } catch {
    // Non-JSON error bodies still map to a safe envelope.
  }
  return {
    code: "HTTP_ERROR",
    message: "请求失败，请稍后重试",
    request_id: response.headers.get("x-request-id") ?? "unknown",
    retryable: response.status >= 500,
  };
}

export type RequestOptions = RequestInit & {
  accessToken?: string;
  fetcher?: typeof fetch;
};

export async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const { accessToken, fetcher = fetch, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  if (requestInit.body && !(requestInit.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }
  const response = await fetcher(`${API_BASE}${path}`, {
    ...requestInit,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw new ApiError(response.status, await decodeError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.blob()) as T;
}

export const api = {
  get<T>(path: string, accessToken?: string, fetcher?: typeof fetch) {
    return request<T>(path, { method: "GET", accessToken, fetcher });
  },
  post<T>(path: string, body?: unknown, accessToken?: string, fetcher?: typeof fetch) {
    return request<T>(path, {
      method: "POST",
      accessToken,
      fetcher,
      body: body instanceof FormData || body === undefined ? body : JSON.stringify(body),
    });
  },
  patch<T>(path: string, body: unknown, accessToken?: string, fetcher?: typeof fetch) {
    return request<T>(path, {
      method: "PATCH",
      accessToken,
      fetcher,
      body: JSON.stringify(body),
    });
  },
};
