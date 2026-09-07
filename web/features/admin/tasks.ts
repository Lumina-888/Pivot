import { api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { AdminTaskList } from "./types";

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export async function listAdminTasks(
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<AdminTaskList> {
  return api.get<AdminTaskList>("/admin/tasks", token(accessToken), fetcher);
}
