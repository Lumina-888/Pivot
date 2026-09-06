import { api } from "../api/client";
import type { LoginSuccess } from "../api/types";

let accessToken: string | null = null;
let onInvalidated: (() => void) | undefined;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAuthInvalidationHandler(handler: (() => void) | undefined): void {
  onInvalidated = handler;
}

export async function login(
  username: string,
  password: string,
  fetcher?: typeof fetch,
): Promise<LoginSuccess> {
  const result = await api.post<LoginSuccess>("/auth/login", { username, password }, undefined, fetcher);
  accessToken = result.access_token;
  return result;
}

export async function refresh(fetcher?: typeof fetch): Promise<LoginSuccess> {
  const result = await api.post<LoginSuccess>("/auth/refresh", undefined, undefined, fetcher);
  accessToken = result.access_token;
  return result;
}

export async function logout(fetcher?: typeof fetch): Promise<void> {
  try {
    await api.post<void>("/auth/logout", undefined, accessToken ?? undefined, fetcher);
  } finally {
    accessToken = null;
    onInvalidated?.();
  }
}

export function invalidateSession(): void {
  accessToken = null;
  onInvalidated?.();
}

export function resetAuthForTests(): void {
  accessToken = null;
  onInvalidated = undefined;
}

// Refresh tokens stay on the server-owned HttpOnly cookie and must never enter JS storage.
