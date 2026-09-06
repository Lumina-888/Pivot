import type { SseEnvelope } from "../api/types";

export const SSE_EVENTS = [
  "run_started",
  "stage",
  "token",
  "citation",
  "warning",
  "completed",
  "uncertain",
  "refused",
  "failed",
  "cancelled",
] as const;

export type SseEventName = (typeof SSE_EVENTS)[number];
export type StreamStatus = "connecting" | "reconnecting" | "open" | "closed" | "error";
export type StreamEvent = { type: SseEventName; id?: string; data: SseEnvelope };
export type StreamOptions = {
  url: string;
  token?: string;
  lastEventId?: number;
  signal?: AbortSignal;
  onStatus?: (status: StreamStatus) => void;
  onEvent: (event: StreamEvent) => void;
  fetcher?: typeof fetch;
};

const TERMINAL_EVENTS = new Set<SseEventName>(["completed", "uncertain", "refused", "failed", "cancelled"]);

export function isSseEnvelope(value: unknown): value is SseEnvelope {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.run_id === "string" &&
    candidate.run_id.length > 0 &&
    typeof candidate.message_id === "string" &&
    candidate.message_id.length > 0 &&
    Number.isInteger(candidate.seq) &&
    (candidate.seq as number) >= 1 &&
    typeof candidate.timestamp === "string" &&
    typeof candidate.stage === "string" &&
    candidate.stage.length > 0 &&
    !!candidate.payload &&
    typeof candidate.payload === "object"
  );
}

function isSseEventName(value: string | undefined): value is SseEventName {
  return SSE_EVENTS.includes(value as SseEventName);
}

export async function connectSse(options: StreamOptions): Promise<void> {
  const fetcher = options.fetcher ?? fetch;
  const headers = new Headers({ Accept: "text/event-stream" });
  if (options.token) {
    headers.set("authorization", `Bearer ${options.token}`);
  }
  if (options.lastEventId !== undefined) {
    headers.set("Last-Event-ID", String(options.lastEventId));
  }
  options.onStatus?.(options.lastEventId === undefined ? "connecting" : "reconnecting");

  let response: Response;
  try {
    response = await fetcher(options.url, {
      headers,
      credentials: "include",
      signal: options.signal,
    });
  } catch (error) {
    options.onStatus?.("error");
    throw error;
  }

  if (!response.ok || !response.body) {
    options.onStatus?.("error");
    throw new Error(`SSE connection failed (${response.status})`);
  }

  options.onStatus?.("open");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName: string | undefined;
  let eventId: string | undefined;
  let dataLines: string[] = [];
  let lastSeq = options.lastEventId ?? 0;
  let terminalSeen = false;

  const resetFrame = () => {
    eventName = undefined;
    eventId = undefined;
    dataLines = [];
  };

  const dispatch = () => {
    if (!dataLines.length) {
      resetFrame();
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(dataLines.join("\n"));
    } catch {
      resetFrame();
      return;
    }
    if (!isSseEnvelope(parsed) || parsed.seq <= lastSeq || !isSseEventName(eventName) || terminalSeen) {
      resetFrame();
      return;
    }
    lastSeq = parsed.seq;
    if (TERMINAL_EVENTS.has(eventName)) {
      terminalSeen = true;
    }
    options.onEvent({ type: eventName, id: eventId, data: parsed });
    resetFrame();
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line === "") {
          dispatch();
          continue;
        }
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("id:")) {
          eventId = line.slice(3).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
    }
    dispatch();
    options.onStatus?.("closed");
  } catch (error) {
    if (options.signal?.aborted) {
      options.onStatus?.("closed");
      return;
    }
    options.onStatus?.("error");
    throw error;
  }
}
