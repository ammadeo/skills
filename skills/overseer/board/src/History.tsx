import type { SwarmState } from "./types.ts";

export function History({ data, onReveal }: { data: SwarmState; onReveal: (id: string) => void }) {
  const Id = ({ id }: { id: string }) => (
    <button type="button" className="link id" onClick={() => onReveal(id)}>{id}</button>
  );
  const runs = data.runs.slice(-5).reverse();
  const decisions = [...data.decisions].reverse();
  return (
    <div className="history">
      <section>
        <h2>
          Changes since last run <span className="count">{data.changes.length}</span>
        </h2>
        {data.changes.length === 0 ? <p className="muted">Nothing changed.</p> : (
          <table>
            <tbody>
              {data.changes.map((c, i) => (
                <tr key={i}>
                  <td><Id id={c.id} /></td>
                  <td><span className={`badge kind-${c.kind}`}>{c.kind}</span></td>
                  <td>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section>
        <h2>
          Last runs <span className="count">{data.runs.length}</span>
        </h2>
        {runs.length === 0 ? <p className="muted">No runs yet.</p> : (
          <ul className="log">
            {runs.map((r, i) => (
              <li key={i}>
                <span className="muted">{r.ts}</span> {r.summary}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2>
          Decisions <span className="count">{data.decisions.length}</span>
        </h2>
        {decisions.length === 0 ? <p className="muted">No decisions yet.</p> : (
          <ul className="decisions">
            {decisions.map((d) => (
              <li key={d.id}>
                <div>
                  <b>{d.id}</b> <span className="muted">{d.ts}</span> <Id id={d.work} />
                </div>
                <div>{d.question}</div>
                <div className="answer">→ {d.answer}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
