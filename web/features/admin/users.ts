import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { AdminUser, AdminUserList, UserStatus } from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function listAdminUsers(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminUserList> {
  return api.get<AdminUserList>("/admin/users", token(accessToken), fetcher);
}

export async function createAdminUser(
  input: { username: string; initial_password: string },
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminUser> {
  return api.post<AdminUser>(
    "/admin/users",
    { username: input.username.trim(), initial_password: input.initial_password },
    token(accessToken),
    fetcher,
  );
}

export async function setUserStatus(
  userId: string,
  status: UserStatus,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminUser> {
  return api.patch<AdminUser>(
    `/admin/users/${encodeURIComponent(userId)}`,
    { status },
    token(accessToken),
    fetcher,
  );
}

export async function disableUser(
  userId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminUser> {
  return setUserStatus(userId, "disabled", accessToken, fetcher);
}

export async function enableUser(
  userId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminUser> {
  return setUserStatus(userId, "active", accessToken, fetcher);
}
