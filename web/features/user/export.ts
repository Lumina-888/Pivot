import { ApiError, api } from "../../lib/api/client";
import type { ErrorEnvelope } from "../../lib/api/types";
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

function asErrorEnvelope(value: unknown): ErrorEnvelope | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (typeof record.code !== "string" || typeof record.message !== "string") {
    return null;
  }
  return {
    code: record.code,
    message: record.message,
    request_id: typeof record.request_id === "string" ? record.request_id : "",
    retryable: typeof record.retryable === "boolean" ? record.retryable : false,
  };
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const match = /filename\*=UTF-8''([^;]+)/i.exec(header) ?? /filename="?([^";]+)"?/i.exec(header);
  if (!match) {
    return null;
  }
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export async function downloadExportFile(
  url: string,
  accessToken?: string,
  fetcher: typeof fetch = fetch,
): Promise<{ blob: Blob; filename: string }> {
  // Since ND-GAP-04 the signed download consumer also requires the
  // session bearer token, which a plain navigation cannot attach.
  // Fetch the bytes with the token and let the caller save the blob.
  const bearer = token(accessToken);
  const response = await fetcher(url, {
    headers: bearer ? { Authorization: `Bearer ${bearer}` } : {},
  });
  if (!response.ok) {
    const envelope = asErrorEnvelope(await response.json().catch(() => null));
    if (envelope) {
      throw new ApiError(response.status, envelope);
    }
    throw new Error(`download failed: ${response.status}`);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("content-disposition")) ?? "export",
  };
}
