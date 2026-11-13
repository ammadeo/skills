import { useCallback, useEffect, useState } from "react";
import type { SwarmState } from "./types.ts";
import { Inbox } from "./Inbox.tsx";
import { Work } from "./Work.tsx";
import { Recent } from "./Recent.tsx";

export function App() {
  const [data, setData] = useState<SwarmState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState("");
  const [railOpen, setRailOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      const text = await res.text();
      if (!res.ok) {
        let msg = text || `HTTP ${res.status}`;
        try {
          msg = (JSON.parse(text) as { error?: string }).error ?? msg;
        } catch { /* plain text */ }
        throw new Error(msg);
      }
      setData(JSON.parse(text) as SwarmState);
      setError(null);
      setLoadedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    import.meta.hot?.on("swarm:update", load);
    return () => import.meta.hot?.off("swarm:update", load);
  }, [load]);

  const work = data?.work ?? [];
  const attention = work.filter((w) => w.state === "needs-decision" || w.state === "blocked" || w.stuck);
  const running = work.filter((w) => w.session_running).length;

  return (
    <div className="app">
      <header className="top">
        <h1>Swarm</h1>
        {data && (
          <p className="meta">
            <span>{data.home}</span>
            <span>{running} session{running === 1 ? "" : "s"} running</span>
            <span>state {data.generated}</span>
            <span>loaded {loadedAt}</span>
          </p>
        )}
      </header>

      {error && (
        <div className="alert" role="alert">
          <strong>Could not load the swarm state.</strong>
          {data && <span> Showing the last good state.</span>}
          <pre>{error}</pre>
        </div>
      )}

      {data && (
        <>
          <main className="pane inbox-pane">
            <Inbox items={attention} onChanged={load} />
            <Recent data={data} />
          </main>
          <aside className="pane work-pane" data-expanded={railOpen} aria-label="Active work">
            <Work work={work} expanded={railOpen} onToggle={() => setRailOpen((v) => !v)} />
          </aside>
        </>
      )}
      {!data && !error && <p className="muted">Loading…</p>}
    </div>
  );
}
