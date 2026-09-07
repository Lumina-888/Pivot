import { ApiError, api } from "../../lib/api/client";
import { getAccessToken } from "../../lib/auth/session";
import type { ExportCreated, ExportFormat, ExportStatus } from "./types";

const INTERNAL_HOST_MARKERS = ["minio", ":9000", "s3.amazonaws.com"];

function token(explicit?: string): string | undefined {
  return explicit ?? getAccessToken() ?? undefined;
}

export function isInternalStorageUrl(url: string | null | undefined): boolean {
  if (!url) {
    return false;
  }
  const lower = url.toLowerCase();
  return INTERNAL_HOST_MARKERS.some((marker) => lower.includes(marker));
}

export function downloadUrlForReady(status: ExportStatus): string | null {
  if (status.state !== "ready") {
    return null;
  }
  const url = status.download_url ?? null;
  if (!url || isInternalStorageUrl(url)) {
    return null;
  }
  return url;
}

export async function createConversationExport(
  sourceId: string,
  format: ExportFormat,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<ExportCreated> {
  return api.post<ExportCreated>(
    "/exports",
    { source_type: "conversation", source_id: sourceId, format },
    token(accessToken),
    fetcher,
  );
}

export async function getExportStatus(
  exportId: string,
  accessToken?: string,
  fetcher?: typeof fetch,
): Promise<ExportStatus> {
  try {
    return await api.get<ExportStatus>(`/exports/${encodeURIComponent(exportId)}`, token(accessToken), fetcher);
  } catch (error) {
    if (error instanceof ApiError && error.envelope.code === "EXPORT_EXPIRED") {
      return {
        export_id: exportId,
        state: "expired",
        download_url: null,
        expires_at: new Date(0).toISOString(),
      };
    }
    throw error;
  }
}

export async function requestReadyDownload(input: {
  sourceId: string;
  format: ExportFormat;
  accessToken?: string;
  fetcher?: typeof fetch;
  poll?: (exportId: string) => Promise<ExportStatus>;
}): Promise<{ created: ExportCreated; status: ExportStatus; downloadUrl: string | null }> {
  const created = await createConversationExport(input.sourceId, input.format, input.accessToken, input.fetcher);
  const status = input.poll
    ? await input.poll(created.export_id)
    : await getExportStatus(created.export_id, input.accessToken, input.fetcher);
  return { created, status, downloadUrl: downloadUrlForReady(status) };
}
