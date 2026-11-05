#!/usr/bin/env python3
"""Build the comparison page from run2/strings.json + run2/annotations.json."""
import html, json, os, sys

base = sys.argv[1]
out = sys.argv[2]
data = json.load(open(os.path.join(base, "strings.json")))
ann = json.load(open(os.path.join(base, "annotations.json")))
ARMS = [("base", "Without the skill", ["base-1", "base-2", "base-3"]),
        ("skill", "With the copywriting skill", ["skill-1", "skill-2", "skill-3"])]
RUNS = [r for _, _, rs in ARMS for r in rs]
master = data["master"]
e = html.escape


def val(run, key, lang="en"):
    return data.get(run, {}).get(key, {}).get(lang)


def cell(run, key):
    m, v = (master.get(key) or {}).get("en"), val(run, key)
    n = run.split("-")[1]
    if v is None:
        return f'<li class="gone"><span class="n">{n}</span><span class="t">removed</span></li>'
    if v == m:
        return f'<li class="kept"><span class="n">{n}</span><span class="t">kept as is</span></li>'
    pl = val(run, key, "pl") or ""
    plh = f'<span class="pl" lang="pl">{e(pl)}</span>' if pl else ""
    mark = ann.get("marks", {}).get(f"{run}|{key}")
    mk = f'<span class="mark {mark[0]}">{e(mark[1])}</span>' if mark else ""
    return f'<li><span class="n">{n}</span><span class="t"><span class="ui">{e(v)}</span>{plh}{mk}</span></li>'


def block(key):
    meta = ann["names"].get(key, {})
    m = master.get(key)
    was = (f'<p class="was"><span class="lab">On master</span><span class="ui">{e(m["en"])}</span>'
           f'<span class="pl" lang="pl">{e(m["pl"])}</span></p>') if m else '<p class="was"><span class="lab">On master</span><span class="none">not present</span></p>'
    cols = "".join(
        f'<div class="arm {a}"><h4>{e(title)}</h4><ul>{"".join(cell(r, key) for r in runs)}</ul></div>'
        for a, title, runs in ARMS)
    note = meta.get("note")
    noteh = f'<p class="note"><b>Key difference</b>{e(note)}</p>' if note else ""
    ctx = f'<span class="ctx">{e(meta["ctx"])}</span>' if meta.get("ctx") else ""
    flag = " flagged" if note else ""
    return (f'<article class="str{flag}" id="{e(key.replace(".", "-").replace("[", "-").replace("]", ""))}">'
            f'<header><h3>{e(meta.get("name", key))}</h3>{ctx}</header>{was}<div class="arms">{cols}</div>{noteh}</article>')


def changed_anywhere(key):
    m = (master.get(key) or {}).get("en")
    return any(val(r, key) != m for r in RUNS)


def section(sec):
    keys = [k for k in sec["keys"] if changed_anywhere(k)]
    body = "".join(block(k) for k in keys)
    return f'<section id="{sec["id"]}"><h2>{e(sec["title"])}</h2><p class="lede">{e(sec["lede"])}</p>{body}</section>'


def focus():
    f = ann["focus"]
    rows = ""
    for a, title, runs in ARMS:
        rows += f'<tr class="grp {a}"><th colspan="{len(f["slots"]) + 2}">{e(title)}</th></tr>'
        for r in runs:
            v = val(r, f["key"]) or ""
            z = val(r, f["zero_key"]) or ""
            chips = "".join(
                f'<td class="slot {"ok" if s in f["has"].get(r, []) else "no"}">{"kept" if s in f["has"].get(r, []) else "lost"}</td>'
                for s in f["slots"])
            rows += (f'<tr class="{a}"><td class="n">{r.split("-")[1]}</td>'
                     f'<td class="mock"><span class="row"><span class="ui">{e(v)}</span><span class="v">5 min.</span></span>'
                     f'<span class="zero">at zero: {e(z)}</span></td>{chips}</tr>')
    head = "".join(f"<th>{e(s)}</th>" for s in f["slots"])
    m = master[f["key"]]["en"]
    return (f'<section id="focus"><h2>{e(f["title"])}</h2><p class="lede">{e(f["lede"])}</p>'
            f'<p class="truth"><span class="lab">What the code does</span>{e(f["truth"])}</p>'
            f'<div class="scroll"><table class="focus"><thead><tr><th></th><th>Label as the slider row shows it</th>{head}</tr></thead>'
            f'<tbody><tr class="orig"><td class="n">now</td><td class="mock"><span class="row"><span class="ui">{e(m)}</span><span class="v">5 min.</span></span>'
            f'<span class="zero">at zero: {e(master[f["zero_key"]]["en"])}</span></td>'
            + "".join(f'<td class="slot {"ok" if s in f["has"]["master"] else "no"}">{"kept" if s in f["has"]["master"] else "lost"}</td>' for s in f["slots"])
            + f'</tr>{rows}</tbody></table></div><p class="after">{e(f["after"])}</p></section>')


def headlines():
    cols = ""
    for a, title, runs in ARMS:
        items = "".join(
            f'<li><span class="n">{r.split("-")[1]}</span><span class="t"><span class="hl">{e(val(r, "HEADLINE") or "(none written)")}</span>'
            f'<span class="hnote">{e(ann["headline_notes"].get(r, ""))}</span></span></li>' for r in runs)
        cols += f'<div class="arm {a}"><h4>{e(title)}</h4><ul>{items}</ul></div>'
    h = ann["headline"]
    return (f'<section id="headline"><h2>{e(h["title"])}</h2><p class="lede">{e(h["lede"])}</p>'
            f'<article class="str flagged"><div class="arms">{cols}</div><p class="note"><b>Key difference</b>{e(h["note"])}</p></article></section>')


def scorecard():
    s = ann["score"]
    head = "".join(f"<th>{e(c)}</th>" for c in s["cols"])
    rows = ""
    for a, title, runs in ARMS:
        rows += f'<tr class="grp {a}"><th colspan="{len(s["cols"]) + 1}">{e(title)}</th></tr>'
        for r in runs:
            rows += f'<tr class="{a}"><td class="n">{r.split("-")[1]}</td>' + "".join(f"<td>{e(str(c))}</td>" for c in s["rows"][r]) + "</tr>"
    return (f'<section id="score"><h2>{e(s["title"])}</h2><p class="lede">{e(s["lede"])}</p>'
            f'<div class="scroll"><table class="score"><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table></div></section>')


verdict = "".join(f'<li class="{v["kind"]}"><b>{e(v["head"])}</b><span>{e(v["body"])}</span></li>' for v in ann["verdict"])
method = "".join(f"<li>{e(m)}</li>" for m in ann["method"])
sections = "".join(section(s) for s in ann["sections"])
page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.css.html")).read()
body = f"""
<main>
<header class="top">
  <p class="eyebrow">{e(ann["eyebrow"])}</p>
  <h1>{e(ann["h1"])}</h1>
  <p class="sub">{e(ann["sub"])}</p>
  <div class="legend"><span class="key base">Without the skill, runs 1 to 3</span><span class="key skill">With the copywriting skill, runs 1 to 3</span>
  <label class="tog"><input type="checkbox" id="pl"> Show Polish strings</label></div>
</header>
<section id="verdict"><h2>Key differences</h2><ul class="verdict">{verdict}</ul></section>
{focus()}
{sections}
{headlines()}
{scorecard()}
<section id="method"><h2>How this was run</h2><ul class="method">{method}</ul></section>
</main>
<script>
const t = document.getElementById('pl');
t.addEventListener('change', () => document.body.classList.toggle('show-pl', t.checked));
</script>
"""
open(out, "w").write(page + body)
print("wrote", out, len(page + body), "bytes")
