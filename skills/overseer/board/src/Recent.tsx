import type { SwarmState } from "./types.ts";

/** Collapsed history under the inbox: changes since the last run, decisions, runs. */
export function Recent({ data }: { data: SwarmState }) {
  const decisions = [...data.decisions].reverse().slice(0, 8);
  const runs = [...data.runs].reverse().slice(0, 5);
  return (
    <details className="recent">
      <summary>
        <h2>Recent</h2>
        <span className="muted">
          {data.changes.length} change{data.changes.length === 1 ? "" : "s"} since the last run · {data.decisions.length}{" "}
          decision{data.decisions.length === 1 ? "" : "s"}
        </span>
      </summary>
      <div className="recent-body">
        <section>
          <h3>Changes since the last run</h3>
          {data.changes.length === 0 ? <p className="muted">Nothing changed.</p> : (
            <ul className="plain">
              {data.changes.map((c, i) => (
                <li key={i}>
                  <code>{c.id}</code> <span className={`tag kind-${c.kind}`}>{c.kind}</span> {c.detail}
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h3>Decisions</h3>
          {decisions.length === 0 ? <p className="muted">No decisions yet.</p> : (
            <ul className="plain">
              {decisions.map((d) => (
                <li key={d.id}>
                  <code>{d.id}</code> <span className="muted">{d.ts} · {d.work}</span>
                  <div>{d.question}</div>
                  <div className="answer">{d.answer}</div>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h3>Overseer runs</h3>
          {runs.length === 0 ? <p className="muted">No runs yet.</p> : (
            <ul className="plain">
              {runs.map((r, i) => (
                <li key={i}>
                  <span className="muted">{r.ts}</span> {r.summary}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </details>
  );
}
