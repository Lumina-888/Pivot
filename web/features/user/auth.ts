import { ApiError } from "../../lib/api/client";
import { login } from "../../lib/auth/session";

export const GENERIC_LOGIN_ERROR = "账号或密码错误";

export type LoginResult =
  | { ok: true; redirectTo: "/" }
  | { ok: false; message: string; code?: string };

export async function loginWithCredentials(
  username: string,
  password: string,
  fetcher?: typeof fetch,
): Promise<LoginResult> {
  const trimmed = username.trim();
  if (!trimmed || !password) {
    return { ok: false, message: "请输入用户名和密码" };
  }
  try {
    await login(trimmed, password, fetcher);
    return { ok: true, redirectTo: "/" };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ok: false, message: GENERIC_LOGIN_ERROR, code: error.envelope.code };
    }
    return { ok: false, message: GENERIC_LOGIN_ERROR };
  }
}
