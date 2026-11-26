import { type FormEvent, useId, useState } from "react";
import type { ApiResult } from "./api.ts";
import { post, submitOnModEnter } from "./api.ts";
import type { WorkItem } from "./types.ts";

interface Props {
  items: WorkItem[];
  onChanged: () => void;
}

/** The decision inbox: everything waiting on the user, plus a form to queue new work. */
export function Inbox({ items, onChanged }: Props) {
  const questions = items.filter((w) => w.state === "needs-decision" && w.question);
  const others = items.filter((w) => !(w.state === "needs-decision" && w.question));
  return (
    <section className="inbox" aria-labelledby="inbox-h">
      <header className="pane-head">
        <h2 id="inbox-h">Needs you</h2>
        <span className="count">{items.length}</span>
      </header>
      {items.length === 0 && <p className="muted empty">Nothing waits on you.</p>}
      {questions.map((w) => <Question key={w.id} item={w} onChanged={onChanged} />)}
      {others.map((w) => <Attention key={w.id} item={w} onChanged={onChanged} />)}
      <NewTask onChanged={onChanged} />
    </section>
  );
}

function Context({ item: w }: { item: WorkItem }) {
  // The latest progress line, skipping the ask itself (already shown as the question).
  const last = [...w.log].reverse().find((l) => !l.text.startsWith("ask:")) ?? w.log.at(-1);
  return (
    <>
      <header className="ask-head">
        <code className="id">{w.id}</code>
        <h3>{w.title}</h3>
        <span className="muted">{w.repo}</span>
        {w.role === "coordinator" && <span className="tag">coordinator</span>}
        {w.pr && (
          <a href={w.pr_url || undefined} target="_blank" rel="noreferrer">{w.pr.replace(/^.*#/, "#")}</a>
        )}
      </header>
      {last && (
        <p className="context">
          <span className="muted">{last.ts} {last.who}:</span> {last.text}
        </p>
      )}
      {w.brief && (
        <details className="brief">
          <summary>Brief</summary>
          <pre><code>{w.brief}</code></pre>
        </details>
      )}
    </>
  );
}

/** Shows the result of a write: success, or the command to run when the board cannot write. */
function Outcome({ r }: { r: ApiResult | null }) {
  if (!r) return <output aria-live="polite" />;
  if (r.ok) return <output aria-live="polite" className="ok">✓ sent</output>;
  return (
    <output aria-live="polite" className="fail">
      <span>✕ {r.error}</span>
      {r.command && <code>{r.command}</code>}
    </output>
  );
}

function Question({ item: w, onChanged }: { item: WorkItem; onChanged: () => void }) {
  const q = w.question!;
  const uid = useId();
  const [pick, setPick] = useState(q.recommended || "");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ApiResult | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const answer = pick ? (text ? `${pick}: ${text}` : pick) : text;
    if (!answer) return;
    setBusy(true);
    const r = await post("answer", { id: w.id, text: answer });
    setBusy(false);
    setResult(r);
    if (r.ok) {
      setText("");
      onChanged();
    }
  };

  return (
    <article className="ask">
      <Context item={w} />
      <form onSubmit={submit} className="reply">
        <p className="question">{q.text}</p>
        <fieldset className="options">
          <legend className="visually-hidden">Options</legend>
          {q.options.map((o) => (
            <label key={o.key} className="option">
              <input type="radio" name={`${uid}-opt`} value={o.key} checked={pick === o.key} onChange={() => setPick(o.key)} />
              <b>{o.key}</b> <span>{o.text}</span>
              {o.key === q.recommended && <span className="rec">recommended</span>}
            </label>
          ))}
          <label className="option">
            <input type="radio" name={`${uid}-opt`} value="" checked={pick === ""} onChange={() => setPick("")} />
            <span>Something else (say what below)</span>
          </label>
        </fieldset>
        <label htmlFor={`${uid}-text`}>Reply</label>
        <textarea
          id={`${uid}-text`}
          name="text"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={submitOnModEnter}
          required={pick === ""}
          placeholder="Another idea, or a follow-up question"
        />
        <footer className="actions">
          <button type="submit" disabled={busy}>{busy ? "Sending…" : "Send answer"}</button>
          <span className="hint">⌘↵ to send</span>
          <Outcome r={result} />
        </footer>
      </form>
    </article>
  );
}

function Attention({ item: w, onChanged }: { item: WorkItem; onChanged: () => void }) {
  const uid = useId();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ApiResult | null>(null);
  const why = w.state === "blocked" ? "Blocked" : w.stuck ? "Stuck: no report for a while" : w.state;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    const r = await post("log", { id: w.id, text: text.trim() });
    setBusy(false);
    setResult(r);
    if (r.ok) {
      setText("");
      onChanged();
    }
  };

  return (
    <article className={`ask attention state-${w.state}${w.stuck ? " stuck" : ""}`}>
      <Context item={w} />
      <form onSubmit={submit} className="reply">
        <p className="question">
          <span className="why">{why}</span>
          {w.owner ? <span className="muted"> · {w.owner}{w.session_running ? ", running" : ", idle"}</span> : <span className="muted"> · unassigned</span>}
        </p>
        <label htmlFor={`${uid}-text`}>Note to the owner</label>
        <textarea
          id={`${uid}-text`}
          name="text"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={submitOnModEnter}
          required
          placeholder="Relayed by the overseer on its next run"
        />
        <footer className="actions">
          <button type="submit" disabled={busy}>{busy ? "Sending…" : "Add note"}</button>
          <span className="hint">⌘↵ to send</span>
          <Outcome r={result} />
        </footer>
      </form>
    </article>
  );
}

function NewTask({ onChanged }: { onChanged: () => void }) {
  const uid = useId();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ApiResult | null>(null);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setBusy(true);
    const r = await post("new", {
      title: String(fd.get("title") ?? ""),
      repo: String(fd.get("repo") ?? ""),
      role: String(fd.get("role") ?? "builder"),
      brief: String(fd.get("brief") ?? ""),
    });
    setBusy(false);
    setResult(r);
    if (r.ok) {
      form.reset();
      onChanged();
    }
  };

  return (
    <details className="new-task">
      <summary><h3>Queue new work</h3></summary>
      <form onSubmit={submit} className="reply">
        <label htmlFor={`${uid}-title`}>Title</label>
        <input id={`${uid}-title`} name="title" type="text" required maxLength={120} autoComplete="off" />
        <label htmlFor={`${uid}-repo`}>Repository <span className="muted">owner/name</span></label>
        <input id={`${uid}-repo`} name="repo" type="text" required pattern="[\w.\-]+/[\w.\-]+" autoComplete="off" autoCapitalize="off" spellCheck={false} />
        <fieldset className="options row">
          <legend>Run as</legend>
          <label className="option"><input type="radio" name="role" value="builder" defaultChecked /> <span>builder (one repo, one PR)</span></label>
          <label className="option"><input type="radio" name="role" value="coordinator" /> <span>coordinator (several surfaces)</span></label>
        </fieldset>
        <label htmlFor={`${uid}-brief`}>Brief <span className="muted">goal, acceptance, what not to touch</span></label>
        <textarea id={`${uid}-brief`} name="brief" rows={5} onKeyDown={submitOnModEnter} />
        <footer className="actions">
          <button type="submit" disabled={busy}>{busy ? "Queuing…" : "Queue it"}</button>
          <span className="hint">⌘↵ to send</span>
          <Outcome r={result} />
        </footer>
      </form>
    </details>
  );
}
