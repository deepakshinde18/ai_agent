import { fetchEventSource } from "@microsoft/fetch-event-source";

import { API_BASE_URL } from "./client";
import type {
  SseClarifyEvent,
  SseErrorEvent,
  SseRowsEvent,
  SseSessionEvent,
  SseTokenEvent,
} from "./types";

export interface InsightStreamCallbacks {
  onSession?: (data: SseSessionEvent) => void;
  onToken?: (data: SseTokenEvent) => void;
  onRows?: (data: SseRowsEvent) => void;
  onClarify?: (data: SseClarifyEvent) => void;
  onError?: (data: SseErrorEvent) => void;
  onDone?: () => void;
}

// Native EventSource can't set an Authorization header or POST a body, so we
// use fetch-event-source, which supports both while still parsing the
// standard text/event-stream wire format our backend emits.
export async function streamInsightQuery(
  query: string,
  sessionId: string | null,
  token: string,
  callbacks: InsightStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  await fetchEventSource(`${API_BASE_URL}/insights/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query, session_id: sessionId }),
    signal,
    openWhenHidden: true,
    async onopen(response) {
      if (!response.ok) {
        throw new Error(`Failed to open stream: ${response.status}`);
      }
    },
    onmessage(event) {
      if (!event.data) return;
      const data = JSON.parse(event.data);
      switch (event.event) {
        case "session":
          callbacks.onSession?.(data as SseSessionEvent);
          break;
        case "token":
          callbacks.onToken?.(data as SseTokenEvent);
          break;
        case "rows":
          callbacks.onRows?.(data as SseRowsEvent);
          break;
        case "clarify":
          callbacks.onClarify?.(data as SseClarifyEvent);
          break;
        case "error":
          callbacks.onError?.(data as SseErrorEvent);
          break;
        case "done":
          callbacks.onDone?.();
          break;
      }
    },
    onerror(err) {
      // Rethrow so fetch-event-source stops its built-in retry loop -- a
      // failed insight query should surface to the user, not retry silently.
      throw err;
    },
  });
}
