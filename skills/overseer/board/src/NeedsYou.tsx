import { useState } from "react";
import type { WorkItem } from "./types.ts";

export function NeedsYou({ work, onReveal }: { work: WorkItem[]; onReveal: (id: string) => void }) {
  const open = work.filter((w) => w.question && w.answer == null);
  return (
    <section className="needs-you">
      <h2>
        Needs you <span className="count">{open.length}</span>
      </h2>
      {open.length === 0 ? <p className="muted">No open questions.</p> : (
        <div className="questions">
          {open.map((w) => <QuestionCard key={w.id} item={w} onReveal={onReveal} />)}
        </div>
      )}
    </section>
  );
}

function QuestionCard({ item, onReveal }: { item: WorkItem; onReveal: (id: string) => void }) {
  const q = item.question!;
  const [pick, setPick] = useState(q.recommended || q.options[0]?.key || "");
  const cmd = `swarm answer ${item.id} "${pick}"`;
  return (
    <article className="question">
      <header>
        <button type="button" className="link id" onClick={() => onReveal(item.id)}>{item.id}</button>
        <span className="title">{item.title}</span>
        <span className="muted">{item.repo}</span>
      </header>
      <p className="qtext">{q.text}</p>
      <ul className="options">
        {q.options.map((o) => (
          <li key={o.key}>
            <button
              type="button"
              className={`option${o.key === pick ? " picked" : ""}`}
              onClick={() => setPick(o.key)}
              title="Use this option in the answer command"
            >
              <b>{o.key}</b> {o.text}
              {o.key === q.recommended && <span className="badge rec">recommended</span>}
            </button>
          </li>
        ))}
      </ul>
      <CopyLine text={cmd} />
    </article>
  );
}

export function CopyLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="copyline">
      <code>{text}</code>
      <button type="button" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
    </div>
  );
}
