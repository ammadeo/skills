import type { WorkItem } from "./types.ts";

const ACTIVE = ["working", "fixing", "pr-open", "ready", "blocked", "needs-decision", "queued"] as const;
const FINISHED = ["done", "archived"] as const;

/** The compact right-hand pane: every item under its state, one line each, details on demand. */
interface Props {
  work: WorkItem[];
  expanded: boolean;
  onToggle: () => void;
}

export function Work({ work, expanded, onToggle }: Props) {
  const known = new Set<string>([...ACTIVE, ...FINISHED]);
  const extra = [...new Set(work.map((w) => w.state).filter((s) => !known.has(s)))];
  const groups = [...ACTIVE, ...extra].map((s) => [s, work.filter((w) => w.state === s)] as const).filter(([, ws]) => ws.length);
  const finished = work.filter((w) => FINISHED.includes(w.state as typeof FINISHED[number]));
  const active = work.length - finished.length;

  return (
    <section className="work" aria-labelledby="work-h">
      <header className="pane-head">
        <h2 id="work-h">Active work</h2>
        <span className="count">{active}</span>
        <button type="button" className="rail-toggle" aria-pressed={expanded} onClick={onToggle}>
          {expanded ? "Close" : "Open"}
        </button>
      </header>
      {groups.length === 0 && <p className="muted empty">No work in flight.</p>}
      {groups.map(([s, ws]) => (
        <section key={s} className={`group state-${s}`}>
          <h3>
            {s} <span className="count">{ws.length}</span>
          </h3>
          <ul className="plain">
            {ws.map((w) => <li key={w.id}><Row item={w} /></li>)}
          </ul>
        </section>
      ))}
      {finished.length > 0 && (
        <details className="group finished">
          <summary><h3>Finished <span className="count">{finished.length}</span></h3></summary>
          <ul className="plain">
            {finished.map((w) => <li key={w.id}><Row item={w} /></li>)}
          </ul>
        </details>
      )}
    </section>
  );
}

function Row({ item: w }: { item: WorkItem }) {
  const last = w.log.at(-1);
  const status = w.stuck ? "stuck" : w.session_running ? "running" : w.owner ? "idle" : "unassigned";
  return (
    <details className={`row status-${status}`}>
      <summary>
        <span className="line">
          <span className={`dot ${status}`} aria-hidden="true" />
          <code className="id">{w.id}</code>
          <span className="title">{w.title}</span>
          {w.ci === "failure" && <span className="tag bad">ci red</span>}
          {w.threads_open > 0 && <span className="tag warn">{w.threads_open} thread{w.threads_open === 1 ? "" : "s"}</span>}
          <span className="status muted">{status}</span>
        </span>
      </summary>
      <div className="row-body">
        {w.session_running && last && (
          <p className="now">
            <span className="muted">now:</span> {last.text}
          </p>
        )}
        <dl>
          <dt>repo</dt>
          <dd>{w.repo}{w.branch && <span className="muted"> · {w.branch}</span>}</dd>
          <dt>owner</dt>
          <dd>{w.owner || "unassigned"}{w.session_last && <span className="muted"> · last seen {w.session_last}</span>}</dd>
          {w.pr && (
            <>
              <dt>PR</dt>
              <dd>
                <a href={w.pr_url || undefined} target="_blank" rel="noreferrer">{w.pr}</a> · ci {w.ci} · {reviewLabel(w.review)} ·{" "}
                {w.threads_open} open thread{w.threads_open === 1 ? "" : "s"}
                {w.head && <span className="muted"> · head {w.head}</span>}
                {w.verified_main && <span className="muted"> · verified on {w.verified_main}</span>}
              </dd>
            </>
          )}
          {w.needs.length > 0 && (
            <>
              <dt>needs</dt>
              <dd>{w.needs.join(", ")}</dd>
            </>
          )}
          <dt>updated</dt>
          <dd>{w.updated}</dd>
        </dl>
        {w.log.length > 0 && (
          <>
            <h4>Log</h4>
            <ul className="plain log">
              {w.log.slice(-6).map((l, i) => (
                <li key={i}>
                  <span className="muted">{l.ts} {l.who}:</span> {l.text}
                </li>
              ))}
            </ul>
          </>
        )}
        {w.findings && (
          <>
            <h4>Findings</h4>
            <pre><code>{w.findings}</code></pre>
          </>
        )}
        {w.question && (
          <>
            <h4>Question</h4>
            <p>{w.question.text}</p>
            <p className="muted">{w.answer ? `Answered: ${w.answer}` : "Not answered yet."}</p>
          </>
        )}
        {w.brief && (
          <details className="brief">
            <summary>Brief</summary>
            <pre><code>{w.brief}</code></pre>
          </details>
        )}
      </div>
    </details>
  );
}

function reviewLabel(r: string) {
  return r === "APPROVED" ? "approved" : r === "CHANGES_REQUESTED" ? "changes requested" : r === "REVIEW_REQUIRED" ? "review required" : "no review";
}
