import { useCallback, useEffect, useState } from "react";
import { STATES, type SwarmState } from "./types.ts";
import { NeedsYou } from "./NeedsYou.tsx";
import { Card } from "./Card.tsx";
import { History } from "./History.tsx";

export function App() {
  const [data, setData] = useState<SwarmState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      const text = await res.text();
      if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
      setData(JSON.parse(text) as SwarmState);
      setError(null);
      setLoadedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const onUpdate = () => {
      console.log("[swarm] swarm:update received, refetching");
      load();
    };
    import.meta.hot?.on("swarm:update", onUpdate);
    return () => import.meta.hot?.off("swarm:update", onUpdate);
  }, [load]);

  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const reveal = (id: string) => {
    setOpen((s) => new Set(s).add(id));
    if (id.startsWith("W") && data?.work.find((w) => w.id === id)?.state === "archived") setShowArchived(true);
    requestAnimationFrame(() => document.getElementById(`card-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  };

  const work = data?.work ?? [];
  const known = new Set<string>(STATES);
  const extra = [...new Set(work.map((w) => w.state).filter((s) => !known.has(s)))];
  const columns = [...STATES.filter((s) => s !== "archived" || showArchived), ...extra];
  const stateOf = new Map(work.map((w) => [w.id, w.state]));
  const count = (s: string) => work.filter((w) => w.state === s).length;

  return (
    <div className="app">
      <header className="top">
        <h1>Swarm board</h1>
        {data && (
          <span className="meta">
            {data.home} · generated {data.generated} · loaded {loadedAt}
          </span>
        )}
        <label className="toggle">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          show archived ({count("archived")})
        </label>
      </header>

      {error && (
        <div className="error" role="alert">
          <strong>Could not load /api/state</strong>
          {data && <span> (showing the last good state)</span>}
          <pre>{error}</pre>
        </div>
      )}

      {data && (
        <>
          <NeedsYou work={work} onReveal={reveal} />
          <main className="columns">
            {columns.map((s) => {
              const items = work.filter((w) => w.state === s);
              return (
                <section key={s} className={`column state-${s}${items.length ? "" : " empty"}`}>
                  <h2>
                    {s} <span className="count">{items.length}</span>
                  </h2>
                  {items.map((w) => (
                    <Card
                      key={w.id}
                      item={w}
                      open={open.has(w.id)}
                      onToggle={() => toggle(w.id)}
                      stateOf={stateOf}
                      onReveal={reveal}
                    />
                  ))}
                </section>
              );
            })}
          </main>
          <History data={data} onReveal={reveal} />
        </>
      )}
      {!data && !error && <p className="muted">Loading…</p>}
    </div>
  );
}
