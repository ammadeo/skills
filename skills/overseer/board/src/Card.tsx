import type { WorkItem } from "./types.ts";

interface Props {
  item: WorkItem;
  open: boolean;
  onToggle: () => void;
  stateOf: Map<string, string>;
  onReveal: (id: string) => void;
}

export function Card({ item: w, open, onToggle, stateOf, onReveal }: Props) {
  const last = w.log.at(-1);
  const hasPr = Boolean(w.pr);
  return (
    <article id={`card-${w.id}`} className={`card${w.stuck ? " stuck" : ""}${open ? " open" : ""}`}>
      <button type="button" className="card-head" onClick={onToggle} aria-expanded={open}>
        <span className="id">{w.id}</span>
        {w.stuck && <span className="badge stuck-badge">stuck</span>}
        {w.role === "coordinator" && <span className="badge">coordinator</span>}
        <span className="title">{w.title}</span>
      </button>

      <div className="row muted">
        <span>{w.repo}</span>
        {hasPr && (
          <a href={w.pr_url || undefined} target="_blank" rel="noreferrer">
            {w.pr.includes("#") ? `#${w.pr.split("#")[1]}` : w.pr}
          </a>
        )}
      </div>

      {(hasPr || w.ci !== "none") && (
        <div className="row">
          <span className={`badge ci-${w.ci}`}>ci {w.ci}</span>
          {w.review !== "none" && <span className={`badge review-${w.review}`}>{reviewLabel(w.review)}</span>}
          <span className={`badge${w.threads_open > 0 ? " warn" : ""}`}>
            {w.threads_open} thread{w.threads_open === 1 ? "" : "s"}
          </span>
        </div>
      )}

      <div className="row">
        <span className={`dot${w.session_running ? " on" : ""}`} title={w.session_running ? "session running" : "session not running"} />
        <span className="owner">{w.owner || "unassigned"}</span>
        {w.needs.length > 0 && (
          <span className="needs">
            needs{" "}
            {w.needs.map((id) => {
              const s = stateOf.get(id);
              const met = s === "done" || s === "archived";
              return (
                <button
                  type="button"
                  key={id}
                  className={`link needs-id${met ? " met" : ""}`}
                  title={s ?? "unknown item"}
                  onClick={() => onReveal(id)}
                >
                  {id}
                </button>
              );
            })}
          </span>
        )}
      </div>

      {last && (
        <p className="last" title={`${last.ts} ${last.who}`}>
          <span className="muted">{last.ts.slice(11) || last.ts} {last.who}:</span> {last.text}
        </p>
      )}

      {open && <Details w={w} />}
    </article>
  );
}

function Details({ w }: { w: WorkItem }) {
  return (
    <div className="details">
      <dl>
        <dt>branch</dt>
        <dd>{w.branch || "–"}</dd>
        <dt>head</dt>
        <dd>{w.head || "–"}</dd>
        <dt>verified_main</dt>
        <dd>{w.verified_main || "–"}</dd>
        <dt>session last</dt>
        <dd>{w.session_last || "–"}</dd>
        <dt>created</dt>
        <dd>{w.created}</dd>
        <dt>updated</dt>
        <dd>{w.updated}</dd>
      </dl>
      <h3>Brief</h3>
      {w.brief ? <pre className="md">{w.brief}</pre> : <p className="muted">empty</p>}
      <h3>Log</h3>
      {w.log.length === 0 ? <p className="muted">empty</p> : (
        <ul className="log">
          {w.log.map((l, i) => (
            <li key={i}>
              <span className="muted">{l.ts} {l.who}:</span> {l.text}
            </li>
          ))}
        </ul>
      )}
      {w.findings && (
        <>
          <h3>Findings</h3>
          <pre className="md">{w.findings}</pre>
        </>
      )}
      {w.question && (
        <>
          <h3>Question</h3>
          <p>{w.question.text}</p>
          <ul className="log">
            {w.question.options.map((o) => (
              <li key={o.key}>
                <b>{o.key}</b> {o.text}
                {o.key === w.question?.recommended && <span className="badge rec">recommended</span>}
              </li>
            ))}
          </ul>
          <h3>Answer</h3>
          {w.answer ? <p>{w.answer}</p> : <p className="muted">not answered yet</p>}
        </>
      )}
    </div>
  );
}

function reviewLabel(r: string) {
  return r === "APPROVED" ? "approved" : r === "CHANGES_REQUESTED" ? "changes requested" : r === "REVIEW_REQUIRED" ? "review required" : r;
}
