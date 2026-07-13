export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface InsightRow {
  [column: string]: string | number | boolean | null;
}

export interface SseSessionEvent {
  session_id: string;
}

export interface SseTokenEvent {
  token: string;
}

export interface SseRowsEvent {
  rows: InsightRow[];
  row_count: number | null;
}

export interface SseClarifyEvent {
  message: string;
}

export interface SseErrorEvent {
  code: string;
  message: string;
}

export type InsightStreamState = {
  sessionId: string | null;
  narrative: string;
  rows: InsightRow[] | null;
  rowCount: number | null;
  clarification: string | null;
  error: string | null;
  streaming: boolean;
};
