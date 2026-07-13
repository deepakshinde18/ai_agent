import { useRef, useState } from "react";

import { streamInsightQuery } from "../api/sse";
import type { InsightStreamState } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { DataTable } from "../components/DataTable";
import { NarrativeStream } from "../components/NarrativeStream";
import { QueryInput } from "../components/QueryInput";

const initialState: InsightStreamState = {
  sessionId: null,
  narrative: "",
  rows: null,
  rowCount: null,
  clarification: null,
  error: null,
  streaming: false,
};

export function InsightPage() {
  const { email, token, logout } = useAuth();
  const [state, setState] = useState<InsightStreamState>(initialState);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function handleSubmit(query: string) {
    if (!token) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLastQuery(query);
    setState((prev) => ({
      ...prev,
      narrative: "",
      rows: null,
      rowCount: null,
      clarification: null,
      error: null,
      streaming: true,
    }));

    try {
      await streamInsightQuery(
        query,
        state.sessionId,
        token,
        {
          onSession: (data) => setState((prev) => ({ ...prev, sessionId: data.session_id })),
          onToken: (data) =>
            setState((prev) => ({ ...prev, narrative: prev.narrative + data.token })),
          onRows: (data) =>
            setState((prev) => ({ ...prev, rows: data.rows, rowCount: data.row_count })),
          onClarify: (data) => setState((prev) => ({ ...prev, clarification: data.message })),
          onError: (data) => setState((prev) => ({ ...prev, error: data.message })),
          onDone: () => setState((prev) => ({ ...prev, streaming: false })),
        },
        controller.signal,
      );
    } catch {
      setState((prev) => ({
        ...prev,
        streaming: false,
        error: prev.error ?? "Connection to the agent was lost. Please try again.",
      }));
    }
  }

  function handleNewConversation() {
    abortRef.current?.abort();
    setState(initialState);
    setLastQuery(null);
  }

  return (
    <div className="insight-page">
      <header className="insight-header">
        <div>
          <h1>Insight Agent</h1>
          <span className="signed-in-as">{email}</span>
        </div>
        <div className="header-actions">
          <button type="button" onClick={handleNewConversation} className="secondary">
            New conversation
          </button>
          <button type="button" onClick={logout} className="secondary">
            Log out
          </button>
        </div>
      </header>

      <QueryInput onSubmit={handleSubmit} disabled={state.streaming} />

      {lastQuery && <p className="last-query">"{lastQuery}"</p>}

      {state.clarification && <p className="clarify-message">{state.clarification}</p>}
      {state.error && <p className="form-error">{state.error}</p>}

      <NarrativeStream narrative={state.narrative} streaming={state.streaming} />
      {state.rows && <DataTable rows={state.rows} rowCount={state.rowCount} />}
    </div>
  );
}
