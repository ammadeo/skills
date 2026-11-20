#!/usr/bin/env python3
"""The change document of the critical-change skill: check it, render it, move it forward.

  change.py check   FILE [--gate plan|prepare|execute|complete]
  change.py render  FILE
  change.py set     FILE ID STATUS [--note TEXT] [--ref URL] [--baseline]
  change.py approve FILE plan|execute|revert --by NAME
  change.py finish  FILE completed|reverted [--note TEXT]

FILE is change.json. Every command that changes it re-renders change.html next
to it. Exit code 1 means: something is missing, the lines printed say what.
"""
import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

STAGES = ["Plan", "Preparation", "Execution", "Smoke test", "Completed"]
SEVERITIES = ["critical", "high", "medium", "low"]
LISTS = {"D": "decisions", "U": "unknowns", "R": "risks", "E": "steps", "P": "prep", "S": "smoke"}
STATUSES = {"P": ("todo", "done"), "E": ("pending", "done", "failed"),
            "V": ("pending", "done", "failed"), "S": ("pending", "pass", "fail")}


def rows(doc, key):
    return [x for x in (doc.get(key) or []) if isinstance(x, dict)]


def rev(doc):
    r = doc.get("reversal")
    return r if isinstance(r, dict) else {}


def rev_steps(doc):
    return [x for x in (rev(doc).get("steps") or []) if isinstance(x, dict)]


def has(x, key):
    v = x.get(key)
    return bool(v.strip()) if isinstance(v, str) else bool(v)


# ---------------------------------------------------------------- checks

def errors(doc):
    """Holes in the plan itself. Nothing renders or moves while these exist."""
    e = []
    for key, why in (("title", "name the change"),
                     ("summary", "what changes and why, in product terms"),
                     ("impact", "who notices what if this goes wrong")):
        if not has(doc, key):
            e.append(f"{key}: missing ({why})")
    if not (doc.get("scope") or {}).get("in"):
        e.append("scope.in: list what this change includes")

    seen = set()
    for prefix, key in list(LISTS.items()) + [("V", None)]:
        for i, x in enumerate(rev_steps(doc) if key is None else rows(doc, key)):
            id_ = x.get("id")
            if not isinstance(id_, str) or not re.fullmatch(prefix + r"\d+", id_):
                e.append(f"{key or 'reversal.steps'}[{i}]: id must look like {prefix}1")
            elif id_ in seen:
                e.append(f"{id_}: duplicate id")
            else:
                seen.add(id_)

    def need(x, keys):
        for k in keys:
            if not has(x, k):
                e.append(f"{x.get('id', '?')}: {k} is missing")

    for d in rows(doc, "decisions"):
        need(d, ("decision", "why"))

    for u in rows(doc, "unknowns"):
        need(u, ("question",))
        if u.get("status") == "answered":
            need(u, ("answer", "evidence"))
        elif u.get("status") == "open":
            need(u, ("blocked_by", "if_wrong", "admin_guide"))
        else:
            e.append(f"{u.get('id', '?')}: status must be answered or open")

    if not rows(doc, "risks"):
        e.append("risks: none listed. A change with no risks has not been planned")
    for r in rows(doc, "risks"):
        need(r, ("risk", "impact"))
        if r.get("severity") not in SEVERITIES:
            e.append(f"{r.get('id', '?')}: severity must be one of {', '.join(SEVERITIES)}")
        if r.get("status") == "mitigated":
            need(r, ("mitigation",))
        elif r.get("status") == "unmitigated":
            need(r, ("needs",))
        else:
            e.append(f"{r.get('id', '?')}: status must be mitigated or unmitigated")

    if not rows(doc, "steps"):
        e.append("steps: list the execution steps in order")
    for s in rows(doc, "steps"):
        need(s, ("action", "verify"))
        if not has(s, "revert") and s.get("no_return") is not True:
            e.append(f"{s.get('id', '?')}: say how to revert it, or set no_return: true")

    r = rev(doc)
    if not isinstance(r.get("possible"), bool) or not has(r, "summary"):
        e.append("reversal: needs possible (true/false) and a summary")
    elif r["possible"]:
        if not rev_steps(doc):
            e.append("reversal.steps: list the steps that take the system back")
        for v in rev_steps(doc):
            need(v, ("action",))

    if not rows(doc, "prep"):
        e.append("prep: list the building blocks to prepare (PRs, scripts, smoke checks, release switch)")
    for p in rows(doc, "prep"):
        need(p, ("item",))

    known = {x.get("id") for x in rows(doc, "risks") + rows(doc, "unknowns")}
    smoke = rows(doc, "smoke")
    if not smoke:
        e.append("smoke: no smoke tests")
    elif not any(s.get("critical") is True for s in smoke):
        e.append("smoke: no check is critical, so nothing would trigger the reversal")
    for s in smoke:
        need(s, ("check", "why", "how", "expect"))
        m = s.get("mitigates")
        if not isinstance(m, list) or not m:
            e.append(f"{s.get('id', '?')}: mitigates must name the risk it covers (R1, U2)")
        else:
            for ref in m:
                if ref not in known:
                    e.append(f"{s.get('id', '?')}: mitigates {ref}, which is not a risk or unknown here")
        if not isinstance(s.get("critical"), bool):
            e.append(f"{s.get('id', '?')}: critical must be true or false")
    return e


def warnings(doc):
    w = []
    covered = {ref for s in rows(doc, "smoke") for ref in (s.get("mitigates") or [])}
    for r in rows(doc, "risks"):
        if r.get("severity") in ("critical", "high") and r.get("id") not in covered:
            w.append(f"{r.get('id')} ({r.get('severity')}) has no smoke check: add one or say in its mitigation why none can exist")
    if not (doc.get("scope") or {}).get("out"):
        w.append("scope.out is empty: say what you deliberately left out")
    if rev(doc).get("possible") and not has(rev(doc), "window"):
        w.append("reversal.window is empty: say until when going back stays possible")
    for s in rows(doc, "smoke"):
        if not s.get("manual") and s.get("baseline") not in ("pass", "fail"):
            w.append(f"{s.get('id')} has never run against the current system (no baseline)")
    return w


def loud(doc):
    """Risks nobody has mitigated: open unknowns, unmitigated risks, no way back."""
    out = []
    for u in rows(doc, "unknowns"):
        if u.get("status") == "open":
            out.append({"id": u.get("id"), "title": u.get("question", ""), "why": u.get("blocked_by", ""),
                        "cost": u.get("if_wrong", ""), "guide": u.get("admin_guide"),
                        "accepted_by": u.get("accepted_by")})
    for r in rows(doc, "risks"):
        if r.get("status") == "unmitigated":
            out.append({"id": r.get("id"), "title": r.get("risk", ""), "why": r.get("needs", ""),
                        "cost": r.get("impact", ""), "guide": r.get("admin_guide"),
                        "accepted_by": r.get("accepted_by")})
    r = rev(doc)
    if r.get("possible") is False and not has(r, "instead"):
        out.append({"id": "reversal", "title": "This change cannot be reversed and nothing replaces the way back",
                    "why": "Fill reversal.instead: a restore that has been tested, a partial rollout, a rehearsal",
                    "cost": r.get("summary", ""), "guide": None, "accepted_by": r.get("accepted_by")})
    return out


def plan_hash(doc):
    """What the final approval covers. Changing any of it voids the approval."""
    pick = lambda x, keys: {k: x.get(k) for k in keys}
    core = {
        "scope": doc.get("scope"),
        "steps": [pick(s, ("id", "action", "details", "verify", "revert", "no_return")) for s in rows(doc, "steps")],
        "reversal": [pick(rev(doc), ("possible", "summary", "instead")),
                     [pick(v, ("id", "action", "details")) for v in rev_steps(doc)]],
        "smoke": [pick(s, ("id", "check", "mitigates", "how", "expect", "critical")) for s in rows(doc, "smoke")],
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def rev_hash(doc):
    """What the confirmation of a reversal covers: the reversal steps as they stood."""
    core = [[v.get("id"), v.get("action"), v.get("details")] for v in rev_steps(doc)]
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def approved(doc, what):
    a = (doc.get("approvals") or {}).get(what)
    if not isinstance(a, dict) or not a.get("by"):
        return False
    return what == "plan" or a.get("hash") == (rev_hash(doc) if what == "revert" else plan_hash(doc))


def blockers(doc, gate):
    """What stands between the document and a gate. Gates stack."""
    b = list(errors(doc))
    b += [f"{d.get('id')}: decision still open: {d.get('decision', '')}"
          for d in rows(doc, "decisions") if d.get("status") == "open"]
    if gate == "plan":
        return b
    if not approved(doc, "plan"):
        b.append("the user has not approved the plan")
    if gate == "prepare":
        return b
    b += [f"{p.get('id')} not ready: {p.get('item', '')}" for p in rows(doc, "prep") if p.get("status") != "done"]
    b += [f"{x['id']} has no mitigation and nobody accepted it: {x['title']}" for x in loud(doc) if not x["accepted_by"]]
    b += [f"{s.get('id')} fails on the system as it is today, so it proves nothing after the change"
          for s in rows(doc, "smoke") if s.get("baseline") == "fail"]
    if gate == "execute":
        return b
    if gate == "run":
        if not approved(doc, "execute"):
            had = (doc.get("approvals") or {}).get("execute")
            b.append("steps, reversal or smoke tests changed after the final approval: show the user and ask again"
                     if had else "the user has not given the final approval")
        return b
    # complete
    b += [f"{s.get('id')} not done: {s.get('action', '')}" for s in rows(doc, "steps") if s.get("status") != "done"]
    for s in rows(doc, "smoke"):
        if s.get("status") not in ("pass", "fail"):
            b.append(f"{s.get('id')} has not run: {s.get('check', '')}")
        elif s.get("status") == "fail" and s.get("critical"):
            b.append(f"{s.get('id')} is critical and failed")
    return b


def progress(doc):
    """(done per stage, index of the current stage or None, index of the failed stage or None, reverted)."""
    steps, smoke, prep = rows(doc, "steps"), rows(doc, "smoke"), rows(doc, "prep")
    state = (doc.get("outcome") or {}).get("state")
    done = [False] * 5
    done[0] = not blockers(doc, "prepare")
    done[1] = done[0] and bool(prep) and all(p.get("status") == "done" for p in prep)
    done[2] = done[1] and bool(steps) and all(s.get("status") == "done" for s in steps)
    crit_fail = any(s.get("status") == "fail" and s.get("critical") for s in smoke)
    done[3] = done[2] and not crit_fail and all(s.get("status") in ("pass", "fail") for s in smoke)
    done[4] = done[3] and state == "completed"
    current = done.index(False) if False in done else None
    failed = 2 if any(s.get("status") == "failed" for s in steps) else 3 if crit_fail else None
    if state == "reverted":
        failed, current = (current if failed is None else failed), None
    return done, current, failed, state == "reverted"


def next_up(doc):
    """One heading and the list of what is missing before the next stage."""
    done, current, failed, reverted = progress(doc)
    if reverted:
        return "Reverted. The change is not in place.", []
    if failed is not None:
        what = "A step failed." if failed == 2 else "A critical smoke test failed."
        left = [f"{v.get('id')} {v.get('action', '')}" for v in rev_steps(doc) if v.get("status") != "done"]
        if approved(doc, "revert"):
            return f"{what} The user confirmed the reversal. Steps left:", left
        return (f"{what} Stop. Tell the user what broke, what it means for users and whether this "
                "reversal still fits, then ask before running it:"), left
    if current is None:
        return "Completed.", []
    if current == 0:
        b = blockers(doc, "plan")
        return ("Before the plan can be approved:", b) if b else ("Plan is complete. Ask the user to approve it.", [])
    if current == 1 or (current == 2 and not approved(doc, "execute")):
        b = blockers(doc, "run" if (doc.get("approvals") or {}).get("execute") else "execute")
        return ("Before execution:", b) if b else ("Everything is ready. Ask the user for the final approval.", [])
    if current == 2:
        return "Executing. Steps left:", [f"{s.get('id')} {s.get('action', '')}" for s in rows(doc, "steps") if s.get("status") != "done"]
    if current == 3:
        return "Smoke tests left:", [f"{s.get('id')} {s.get('check', '')}" for s in rows(doc, "smoke") if s.get("status") not in ("pass", "fail")]
    return "All checks are in. Mark it: finish FILE completed", []


def report(doc):
    done, current, failed, reverted = progress(doc)
    stage = "Reverted" if reverted else "Completed" if current is None else STAGES[current]
    out = [doc.get("title") or "(untitled change)", f"Stage: {stage}"]
    head, lines = next_up(doc)
    out.append(head)
    out += [f"  - {x}" for x in lines]
    risks = loud(doc)
    if risks:
        out.append(f"Risks without mitigation: {len(risks)}")
        for x in risks:
            tag = f"accepted by {x['accepted_by']}" if x["accepted_by"] else "NOT ACCEPTED"
            out.append(f"  - {x['id']} ({tag}): {x['title']}")
    failed_soft = [s for s in rows(doc, "smoke") if s.get("status") == "fail" and not s.get("critical")]
    if failed_soft:
        out.append("Non-critical smoke tests that failed (follow up, no reversal):")
        out += [f"  - {s.get('id')} {s.get('check', '')}" for s in failed_soft]
    w = warnings(doc) if current in (0, 1) else []
    if w:
        out.append("Warnings:")
        out += [f"  - {x}" for x in w]
    return "\n".join(out)


# ---------------------------------------------------------------- page

CSS = """
/* Layout: one reading column. Stepper, then anything unmitigated, then the product-level story; technical detail folds. */
:root{--bg:#f3f5f8;--surface:#fff;--ink:#16202b;--muted:#5a6776;--line:#d2d9e1;--accent:#2457a6;
--ok:#1c7445;--ok-bg:#dff1e6;--warn:#8f5600;--warn-bg:#fbeed3;--crit:#b3261e;--crit-bg:#fbe4e1;
--sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;--mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e141a;--surface:#172029;--ink:#dee5ec;--muted:#96a3b0;--line:#2c3844;--accent:#8ab4f8;--ok:#7fd0a0;--ok-bg:#17342a;--warn:#f0b354;--warn-bg:#3a2c12;--crit:#ff8a80;--crit-bg:#42201d;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0e141a;--surface:#172029;--ink:#dee5ec;--muted:#96a3b0;--line:#2c3844;--accent:#8ab4f8;--ok:#7fd0a0;--ok-bg:#17342a;--warn:#f0b354;--warn-bg:#3a2c12;--crit:#ff8a80;--crit-bg:#42201d;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:16px/1.55 var(--sans);padding-block:2.5rem 4rem;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
main{display:grid;gap:2.5rem;max-width:46rem;margin-inline:auto}
main>*{min-width:0}
header,section{display:grid;gap:.9rem}
h1{font-size:1.8rem;line-height:1.15;font-weight:600;margin:0;text-wrap:balance}
h2{font-size:1.2rem;line-height:1.25;font-weight:600;margin:0;text-wrap:balance}
p,ul,ol{margin:0}
ul,ol{padding-left:1.2rem;display:grid;gap:.25rem}
a{color:var(--accent);text-underline-offset:3px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
code{font:.86em var(--mono);overflow-wrap:anywhere}
.now{color:var(--muted)}
.now b{color:var(--ink);font-weight:600}
.stepper{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:.5rem}
.stepper svg{display:block;width:100%;min-width:30rem;height:auto}
.sl{stroke:var(--line);stroke-width:2}
.sl.ok{stroke:var(--ok)}
.sn{fill:var(--surface);stroke:var(--line);stroke-width:2}
.sn.done{fill:var(--ok);stroke:var(--ok)}
.sn.now{stroke:var(--accent);stroke-width:3}
.sn.bad{fill:var(--crit);stroke:var(--crit)}
.sd{fill:var(--accent)}
.sm{fill:none;stroke:var(--surface);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}
.st{font:500 13px var(--sans);fill:var(--muted);text-anchor:middle}
.st.done,.st.now{fill:var(--ink)}
.st.now{font-weight:600}
.st.bad{fill:var(--crit);font-weight:600}
.loud{border:2px solid var(--crit);background:var(--crit-bg);border-radius:8px;padding:1rem 1.1rem}
.loud h2{color:var(--crit)}
.rows{display:grid;list-style:none;padding:0;gap:0;border-top:1px solid var(--line)}
.rows>li{display:grid;grid-template-columns:2.4rem minmax(0,1fr) auto;gap:.2rem .6rem;align-items:start;padding:.75rem 0;border-bottom:1px solid var(--line)}
.loud .rows,.loud .rows>li{border-color:var(--crit)}
.loud .rows>li:last-child{border-bottom:0;padding-bottom:0}
.id{font:600 .8rem/1.9 var(--mono);color:var(--muted)}
.body{display:grid;gap:.35rem;min-width:0}
.body>b{font-weight:600}
.k{color:var(--muted)}
.pill{font:600 .72rem/1 var(--sans);letter-spacing:.03em;text-transform:uppercase;padding:.32rem .5rem;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap;margin-top:.2rem}
.pill.ok{color:var(--ok);background:var(--ok-bg);border-color:transparent}
.pill.warn{color:var(--warn);background:var(--warn-bg);border-color:transparent}
.pill.crit{color:var(--crit);background:var(--crit-bg);border-color:transparent}
.loud .pill.crit{background:var(--surface)}
details{font-size:.92rem}
summary{cursor:pointer;color:var(--muted);width:fit-content}
details>*:not(summary){margin-top:.4rem}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:1rem 2rem}
.cols h3{font:600 .78rem var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 .4rem}
.log{font:.8rem/1.6 var(--mono);color:var(--muted)}
.rows>li>span:empty{display:none}
@media (max-width:34rem){.rows>li{grid-template-columns:2.4rem minmax(0,1fr)}.rows>li>.pill{grid-column:2;justify-self:start;margin-top:0}}
"""


def fmt(s):
    s = html.escape(str(s or ""), quote=True)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', s)
    return s.replace("\n", "<br>")


def block(v, ordered=False):
    if isinstance(v, list):
        tag = "ol" if ordered else "ul"
        return f"<{tag}>" + "".join(f"<li>{fmt(x)}</li>" for x in v) + f"</{tag}>"
    return f"<p>{fmt(v)}</p>" if v else ""


def fold(v, label="Technical detail"):
    return f"<details><summary>{label}</summary>{block(v)}</details>" if v else ""


def line(label, v):
    return f'<p><span class="k">{label}:</span> {fmt(v)}</p>' if v else ""


def pill(text, kind=""):
    return f'<span class="pill {kind}">{html.escape(text)}</span>'


def row(id_, body, tag=""):
    return f'<li><span class="id">{html.escape(str(id_ or ""))}</span><div class="body">{body}</div>{tag or "<span></span>"}</li>'


def section(title, inner, cls=""):
    return f'<section{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}><h2>{title}</h2>{inner}</section>' if inner else ""


def listing(items):
    return f'<ul class="rows">{"".join(items)}</ul>' if items else ""


def stepper(doc):
    done, current, failed, reverted = progress(doc)
    xs, y, r = [60 + 120 * i for i in range(5)], 30, 14
    out, said = [], []
    for i in range(4):
        out.append(f'<line class="sl{" ok" if done[i] and done[i + 1] or (done[i] and current == i + 1) else ""}" '
                   f'x1="{xs[i] + r}" y1="{y}" x2="{xs[i + 1] - r}" y2="{y}"/>')
    for i, name in enumerate(STAGES):
        state = "bad" if failed == i else "done" if done[i] else "now" if current == i else "todo"
        if reverted and i == 4:
            state, name = "bad", "Reverted"
        x = xs[i]
        out.append(f'<circle class="sn {state}" cx="{x}" cy="{y}" r="{r}"/>')
        if state == "done":
            out.append(f'<polyline class="sm" points="{x - 6},{y + 1} {x - 2},{y + 5} {x + 6},{y - 4}"/>')
        elif state == "bad":
            out.append(f'<path class="sm" d="M{x - 5} {y - 5}l10 10M{x + 5} {y - 5}l-10 10"/>')
        elif state == "now":
            out.append(f'<circle class="sd" cx="{x}" cy="{y}" r="5"/>')
        out.append(f'<text class="st {state}" x="{x}" y="{y + 36}">{name}</text>')
        said.append(f"{name}: " + {"bad": "failed", "done": "done", "now": "in progress", "todo": "not started"}[state])
    return (f'<div class="stepper"><svg viewBox="0 0 600 82" role="img" aria-label="{html.escape("; ".join(said))}">'
            + "".join(out) + "</svg></div>")


def page(doc):
    head, lines = next_up(doc)
    now = f'<p class="now"><b>{html.escape(head)}</b></p>' + (block(lines) if lines else "")

    risks_loud = []
    for x in loud(doc):
        body = f"<b>{fmt(x['title'])}</b>" + line("If we are wrong", x["cost"]) + line("Why it is open", x["why"])
        if x["guide"]:
            body += '<p class="k">What an admin can do to close it:</p>' + block(x["guide"], ordered=True)
        tag = pill(f"accepted by {x['accepted_by']}", "warn") if x["accepted_by"] else pill("no mitigation", "crit")
        risks_loud.append(row(x["id"], body, tag))

    decisions = [row(d.get("id"), f"<b>{fmt(d.get('decision'))}</b>{block(d.get('why'))}{fold(d.get('details'))}",
                     pill("needs your call", "warn") if d.get("status") == "open" else "")
                 for d in rows(doc, "decisions")]

    scope = doc.get("scope") or {}
    scope_html = ""
    if scope.get("in") or scope.get("out"):
        scope_html = ('<div class="cols"><div><h3>In this change</h3>' + block(scope.get("in") or []) +
                      '</div><div><h3>Deliberately left out</h3>' + block(scope.get("out") or []) + "</div></div>")

    prep = [row(p.get("id"), f"<b>{fmt(p.get('item'))}</b>" + line("Where", p.get("ref")) + block(p.get("note")),
                pill("ready", "ok") if p.get("status") == "done" else pill("to do"))
            for p in rows(doc, "prep")]

    step_pill = {"done": pill("done", "ok"), "failed": pill("failed", "crit")}
    steps = [row(s.get("id"),
                 f"<b>{fmt(s.get('action'))}</b>" + line("We know it worked when", s.get("verify")) +
                 (line("To undo", s.get("revert")) if has(s, "revert") else '<p class="k">No way back after this step.</p>') +
                 block(s.get("note")) + fold(s.get("details")),
                 step_pill.get(s.get("status"), pill("no return", "warn") if s.get("no_return") else pill("pending")))
             for s in rows(doc, "steps")]

    r = rev(doc)
    reversal = block(r.get("summary")) + line("Possible until", r.get("window")) + line("Instead of a way back", r.get("instead"))
    reversal += listing([row(v.get("id"), f"<b>{fmt(v.get('action'))}</b>" + block(v.get("note")) + fold(v.get("details")),
                             step_pill.get(v.get("status"), "")) for v in rev_steps(doc)])
    if r.get("possible") is False:
        reversal = f'<p>{pill("cannot be reversed", "crit")}</p>' + reversal

    smoke = []
    for s in rows(doc, "smoke"):
        st = s.get("status")
        tag = pill("passed", "ok") if st == "pass" else pill("failed", "crit" if s.get("critical") else "warn") if st == "fail" \
            else pill("critical", "crit") if s.get("critical") else pill("non-critical")
        kind = "Critical: a failure stops the change and the reversal is put to you at once." if s.get("critical") else "Non-critical: a failure is recorded and followed up."
        body = (f"<b>{fmt(s.get('check'))}</b>" + line("Covers", ", ".join(s.get("mitigates") or [])) + block(s.get("why")) +
                f'<p class="k">{kind}{" Checked by hand." if s.get("manual") else ""}</p>' + block(s.get("note")) +
                fold([f"Run: {s.get('how', '')}", f"Expect: {s.get('expect', '')}",
                      f"On the system before the change: {s.get('baseline') or 'not run'}"], "How it runs"))
        smoke.append(row(s.get("id"), body, tag))

    covered = {}
    for s in rows(doc, "smoke"):
        for ref in s.get("mitigates") or []:
            covered.setdefault(ref, []).append(s.get("id"))
    sev_kind = {"critical": "crit", "high": "warn"}
    risks = [row(x.get("id"),
                 f"<b>{fmt(x.get('risk'))}</b>" + line("What users would see", x.get("impact")) +
                 line("How we prevent it", x.get("mitigation")) + line("Still needed", x.get("needs") if x.get("status") == "unmitigated" else "") +
                 line("Watched by", ", ".join(covered.get(x.get("id"), []))) + fold(x.get("details")),
                 pill(str(x.get("severity")), sev_kind.get(x.get("severity"), "")))
             for x in rows(doc, "risks")]

    unknowns = [row(u.get("id"), f"<b>{fmt(u.get('question'))}</b>" + block(u.get("answer")) + fold(u.get("evidence"), "Evidence"),
                    pill("answered", "ok"))
                for u in rows(doc, "unknowns") if u.get("status") == "answered"]

    log = "".join(f"<div>{html.escape(str(x.get('at', '')))}  {fmt(x.get('event'))}</div>" for x in rows(doc, "log"))

    parts = [
        '<meta charset="utf-8">', '<meta name="claude:viewport-fit-sides" content="cover">',
        f"<title>{html.escape(str(doc.get('title')))}</title>",
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap">',
        f"<style>{CSS}</style>", "<main>",
        f"<header><h1>{html.escape(str(doc.get('title')))}</h1>{stepper(doc)}{now}</header>",
        section("Risks without mitigation", listing(risks_loud), "loud"),
        section("What changes", block(doc.get("summary")) + line("If it goes wrong", doc.get("impact")) + line("When", doc.get("window"))),
        section("Key decisions", listing(decisions)),
        section("Scope", scope_html),
        section("Preparation", listing(prep)),
        section("Execution steps", listing(steps)),
        section("Way back", reversal),
        section("Smoke tests", listing(smoke)),
        section("Risks", listing(risks)),
        section("Questions we answered", listing(unknowns)),
        section("Further improvement ideas", (block(doc.get("improvements")) and
                '<p class="k">Not part of this change. Worth a look once it has settled.</p>' + block(doc.get("improvements")))),
        section("Log", f'<details><summary>Approvals and events</summary><div class="log">{log}</div></details>' if log else ""),
        "</main>",
    ]
    return "\n".join(p for p in parts if p).encode("ascii", "xmlcharrefreplace").decode()


# ---------------------------------------------------------------- commands

def load(path):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        sys.exit(f"error: cannot read {path}: {err}")
    if not isinstance(doc, dict):
        sys.exit("error: the change file must be a JSON object")
    return doc


def save(path, doc, event=None):
    if event:
        doc.setdefault("log", []).append({"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "event": event})
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render(path, doc)


def render(path, doc):
    out = Path(path).with_suffix(".html")
    out.write_text(page(doc), encoding="utf-8")
    return out


def fail(lines, head):
    print(head)
    for x in lines:
        print(f"  - {x}")
    sys.exit(1)


def find(doc, id_):
    for x in rev_steps(doc) if id_.startswith("V") else rows(doc, LISTS.get(id_[:1], "")):
        if x.get("id") == id_:
            return x
    sys.exit(f"error: no item {id_} in this change")


def cmd_check(a):
    doc = load(a.file)
    print(report(doc))
    if a.gate:
        b = blockers(doc, "run" if a.gate == "execute" and (doc.get("approvals") or {}).get("execute") else a.gate)
        if b:
            fail(b, f"Gate {a.gate}: closed")
        print(f"Gate {a.gate}: open")
    elif errors(doc):
        sys.exit(1)


def cmd_render(a):
    doc = load(a.file)
    e = errors(doc)
    if e:
        fail(e, "Not rendered. The plan has holes:")
    for w in warnings(doc):
        print(f"warning: {w}")
    print(render(a.file, doc))


def cmd_set(a):
    doc = load(a.file)
    kind = a.id[:1]
    if kind not in STATUSES:
        sys.exit("error: set works on P (prep), E (steps), V (reversal steps) and S (smoke) items; edit the JSON for the rest")
    x = find(doc, a.id)
    if a.baseline:
        if kind != "S" or a.status not in ("pass", "fail"):
            sys.exit("error: --baseline goes with a smoke check and pass or fail")
        x["baseline"] = a.status
    else:
        if a.status not in STATUSES[kind]:
            sys.exit(f"error: {a.id} can be {', '.join(STATUSES[kind])}")
        gate = {"P": "prepare", "E": "run"}.get(kind)
        if kind == "S":
            if any(s.get("status") != "done" for s in rows(doc, "steps")):
                sys.exit("error: the change has not run yet. A result from before it is a baseline: add --baseline")
        elif gate and a.status != "pending":
            b = blockers(doc, gate)
            if b:
                fail(b, f"{a.id} not changed. Still missing:")
        if kind == "E" and a.status == "done":
            before = rows(doc, "steps")[:rows(doc, "steps").index(x)]
            if any(s.get("status") != "done" for s in before):
                sys.exit(f"error: steps run in order and an earlier one is not done ({a.id} not changed)")
        if kind == "V" and a.status != "pending" and not approved(doc, "revert"):
            had = (doc.get("approvals") or {}).get("revert")
            sys.exit("error: " + ("the reversal steps changed after the user confirmed them: show the new steps and ask again"
                                  if had else "the user has not confirmed the reversal (approve FILE revert --by NAME)")
                     + f" ({a.id} not changed)")
        x["status"] = a.status
    if a.note:
        x["note"] = a.note
    if a.ref:
        x["ref"] = a.ref
    save(a.file, doc, f"{a.id} {'baseline ' if a.baseline else ''}{a.status}" + (f": {a.note}" if a.note else ""))
    print(report(doc))


def cmd_approve(a):
    doc = load(a.file)
    if a.what == "revert":
        b = [] if (doc.get("approvals") or {}).get("execute") else ["nothing has been executed, so there is nothing to reverse"]
    else:
        b = blockers(doc, a.what)
    if b:
        fail(b, f"Not recorded. Before the {a.what} approval:")
    entry = {"by": a.by, "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    if a.what != "plan":
        entry["hash"] = rev_hash(doc) if a.what == "revert" else plan_hash(doc)
    doc.setdefault("approvals", {})[a.what] = entry
    save(a.file, doc, f"{a.what} approved by {a.by}")
    print(report(doc))


def cmd_finish(a):
    doc = load(a.file)
    if a.state == "completed":
        b = blockers(doc, "complete")
        if b:
            fail(b, "Not completed:")
    else:
        left = [f"{v.get('id')} {v.get('action', '')}" for v in rev_steps(doc) if v.get("status") != "done"]
        if left:
            fail(left, "Not marked reverted. Reversal steps left:")
    doc["outcome"] = {"state": a.state, "note": a.note or ""}
    save(a.file, doc, a.state + (f": {a.note}" if a.note else ""))
    print(report(doc))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("file"); c.add_argument("--gate", choices=("plan", "prepare", "execute", "complete")); c.set_defaults(fn=cmd_check)
    c = sub.add_parser("render"); c.add_argument("file"); c.set_defaults(fn=cmd_render)
    c = sub.add_parser("set"); c.add_argument("file"); c.add_argument("id"); c.add_argument("status")
    c.add_argument("--note"); c.add_argument("--ref"); c.add_argument("--baseline", action="store_true"); c.set_defaults(fn=cmd_set)
    c = sub.add_parser("approve"); c.add_argument("file"); c.add_argument("what", choices=("plan", "execute", "revert")); c.add_argument("--by", required=True); c.set_defaults(fn=cmd_approve)
    c = sub.add_parser("finish"); c.add_argument("file"); c.add_argument("state", choices=("completed", "reverted")); c.add_argument("--note"); c.set_defaults(fn=cmd_finish)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
