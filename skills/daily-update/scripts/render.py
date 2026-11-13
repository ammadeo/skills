#!/usr/bin/env python3
"""render.py: build and check the two Slack messages of a daily update.

Usage:  python3 -I render.py update.json

update.json:
{
  "user": "<@U02C132H4HH>",          Slack mention of the person reporting
  "attribution": true,               false when the posting tool already marks
                                     the message as sent by Claude (Slack connector)
  "model": "Opus 5.5",               your model name, for the attribution line
  "date": "2026-11-13",              optional, default today (local)
  "channel": "#proj-updates (C0123)",optional, shown in the preview
  "tracker": "Linear",               ticket software name, if tickets are used
  "people": {"<@U02C132H4HH>": "Amadeusz Chomiak", "<@U0123ABC>": "Jan Kowalski"},
                                     names for every mention, for the preview
  "tldr": "One to three sentences, product level, epics and roadmap.",
  "stacks": {"e2e": {"title": "E2E suite rebuild",
                     "note": "code review by <@U0123ABC>"}},   note optional
  "items": [
    {"section": "waiting|in_progress|releasable|released",
     "title": "PR or ticket name",
     "pr": "https://github.com/o/r/pull/1",     optional if ticket is given
     "ticket": "https://linear.app/...",        optional if pr is given
     "tracker": "ClickUp",                      optional per-item override
     "stack": "e2e",                            optional, key into "stacks"
     "note": "short; waiting needs who: <@U…> or @Name (here or on its stack)"}
  ]
}

Stacks: items sharing a "stack" key render together, bottom to top in input
order, under one header line, in the section of their least ready PR. When
every PR in a stack has the same note, it moves to the header (say a shared
reviewer once). A mention on the header must not repeat on its PRs.

Writes <json stem>.parent.txt and <json stem>.thread.txt (exact Slack text)
next to the JSON and prints a preview to stdout: Markdown that shows links as
links and mentions as names, to paste into the reply as is. Exits 1 with
every problem listed if anything breaks the format; warnings go to stderr.
"""
import datetime
import json
import os
import re
import sys

SECTIONS = [
    ("waiting", "Waiting"),
    ("in_progress", "In progress"),
    ("releasable", "Releasable"),
    ("released", "Released"),
]
READINESS = {"in_progress": 0, "waiting": 1, "releasable": 2, "released": 3}
SEP = " ∙ "
INDENT = "    "
PR_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/pull/\d+/?$")
URL_RE = re.compile(r"^https?://\S+$")
SLACK_MENTION_RE = re.compile(r"<@[UW][A-Z0-9]+>")
MENTION_RE = re.compile(r"<@[UW][A-Z0-9]+>|(?<![\w<])@\w[\w.-]*")
ID_RE = re.compile(r"#\d+|\b[A-Z][A-Z0-9]{1,9}-\d+\b|https?://")
TECH_RE = re.compile(r"^\s*(\[?[A-Za-z]+-\d+\]?\s*)?(chore|ci|build|refactor|test|tests|deps|docs|style|lint|bump)\b", re.I)
LIMIT = 5000  # Slack text element limit


def clean(s):
    return " ".join(str(s or "").split())


def main(path):
    errors, warnings = [], []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read {path}: {e}")

    user = clean(data.get("user"))
    if not re.fullmatch(SLACK_MENTION_RE, user):
        errors.append('user: must be a Slack mention like "<@U02C132H4HH>"')
    attribution = data.get("attribution", True) is not False
    model = clean(data.get("model"))
    if attribution and (not model or "claude" in model.lower()):
        errors.append('model: your model name without "Claude", e.g. "Opus 5.5"')
    try:
        day = datetime.date.fromisoformat(data["date"]) if data.get("date") else datetime.date.today()
    except ValueError:
        errors.append("date: must be YYYY-MM-DD")
        day = datetime.date.today()

    tldr = clean(data.get("tldr"))
    if not tldr:
        errors.append("tldr: missing")
    else:
        if len(tldr) > 450:
            errors.append(f"tldr: {len(tldr)} chars, keep it under 450 (one to three sentences)")
        if ID_RE.search(tldr):
            errors.append("tldr: no PR numbers, ticket IDs or links; say what changed for the product")
        if len(re.findall(r"[.!?](\s|$)", tldr)) > 3:
            errors.append("tldr: more than three sentences")

    default_tracker = clean(data.get("tracker"))
    stacks = data.get("stacks") or {}
    items = data.get("items") or []
    if not items:
        errors.append("items: nothing to report")

    # Validate items and build their lines (without list markers).
    rows, seen = [], set()
    for i, it in enumerate(items, 1):
        sec = it.get("section")
        title = clean(it.get("title")).rstrip(".")
        where = f'item {i} "{title[:40]}"'
        if sec not in READINESS:
            errors.append(f"{where}: section must be one of {', '.join(READINESS)}")
            continue
        if not title:
            errors.append(f"{where}: title missing")
        pr, ticket = clean(it.get("pr")), clean(it.get("ticket"))
        tracker = clean(it.get("tracker")) or default_tracker
        note = clean(it.get("note"))
        stack = clean(it.get("stack"))
        if not pr and not ticket:
            errors.append(f"{where}: needs a pr or a ticket link")
        if pr and not PR_RE.match(pr):
            errors.append(f"{where}: pr must be a github.com pull request URL")
        if ticket and not URL_RE.match(ticket):
            errors.append(f"{where}: ticket must be a URL")
        if ticket and not tracker:
            errors.append(f"{where}: ticket given but no tracker name (top-level or per item)")
        key = pr or "ticket:" + ticket  # a ticket may span several PRs
        if key in seen:
            errors.append(f"{where}: {pr or ticket} is listed twice")
        seen.add(key)
        if stack and stack not in stacks:
            errors.append(f'{where}: stack "{stack}" is not defined in "stacks"')
            stack = ""
        if stack and not pr:
            errors.append(f"{where}: only PRs can be in a stack")
        for text in (title, note):
            if SEP.strip() in text:
                errors.append(f"{where}: '∙' is the separator, don't use it in titles or notes")
        if len(note) > 90:
            errors.append(f"{where}: note is {len(note)} chars, keep it under 90")
        if sec == "released" and note and TECH_RE.match(title):
            warnings.append(f"{where}: looks technical; a released note must name a user-facing benefit, else drop it")
        rows.append(dict(where=where, sec=sec, title=title, pr=pr, ticket=ticket,
                         tracker=tracker, note=note, stack=stack))

    # Stacks: section, shared note, mention rules.
    groups = {}
    for r in rows:
        if r["stack"]:
            groups.setdefault(r["stack"], []).append(r)
    stack_info = {}
    for key, members in groups.items():
        cfg = stacks.get(key) or {}
        title = clean(cfg.get("title")).rstrip(".")
        snote = clean(cfg.get("note"))
        where = f'stack "{key}"'
        if len(members) < 2:
            errors.append(f"{where}: has one PR; drop the stack key")
        if not title:
            errors.append(f"{where}: needs a short product title")
        notes = {m["note"] for m in members}
        if not snote and len(notes) == 1 and "" not in notes:
            snote = notes.pop()  # same note on every PR: say it once
            for m in members:
                m["note"] = ""
        for m in members:
            if m["note"] == snote:
                m["note"] = ""
        if len(snote) > 90:
            errors.append(f"{where}: note is {len(snote)} chars, keep it under 90")
        shared = set(MENTION_RE.findall(snote))
        for m in members:
            twice = shared & set(MENTION_RE.findall(m["note"]))
            if twice:
                errors.append(f"{m['where']}: {', '.join(sorted(twice))} is already on the stack header; drop it here")
        sec = min((m["sec"] for m in members), key=READINESS.get)
        stack_info[key] = dict(title=title, note=snote, sec=sec, n=len(members))

    for r in rows:
        if r["sec"] == "waiting":
            snote = stack_info.get(r["stack"], {}).get("note", "")
            if not MENTION_RE.search(r["note"] + " " + snote):
                errors.append(f"{r['where']}: waiting needs the responsible person (<@U…> or @Name) in its note or its stack's note")

    def line(r):
        parts = [r["title"]]
        if r["pr"]:
            parts.append(f"[GitHub]({r['pr']})")
        if r["ticket"]:
            parts.append(f"[{r['tracker']}]({r['ticket']})")
        if r["note"]:
            parts.append(r["note"])
        return SEP.join(parts)

    sections = {k: [] for k, _ in SECTIONS}
    placed = set()
    for r in rows:
        if not r["stack"]:
            sections[r["sec"]].append("- " + line(r))
        elif r["stack"] not in placed:
            placed.add(r["stack"])
            s = stack_info[r["stack"]]
            head = [f"**{s['title']}**", f"{s['n']} stacked PRs"] + ([s["note"]] if s["note"] else [])
            block = ["- " + SEP.join(head)]
            block += [INDENT + "- " + line(m) for m in groups[r["stack"]]]
            sections[s["sec"]].append("\n".join(block))

    parent = f"**{user}'s daily update for {day.strftime('%A')} {day.day} {day.strftime('%b')}**"
    blocks = [f"> 🤖 _Claude {model} posted on behalf of {user}_"] if attribution else []
    blocks.append(f"**TLDR**\n{tldr}")
    for key, label in SECTIONS:
        if sections[key]:
            blocks.append(f"**{label}**\n" + "\n".join(sections[key]))
    thread = "\n\n".join(blocks)
    if len(thread) > LIMIT:
        errors.append(f"thread: {len(thread)} chars, Slack allows {LIMIT}; shorten notes or the TLDR")

    people = {k: clean(v) for k, v in (data.get("people") or {}).items()}
    unnamed = sorted(set(SLACK_MENTION_RE.findall(parent + thread)) - set(people))
    if unnamed:
        warnings.append("people: no name for " + ", ".join(unnamed) + "; the preview shows the raw ID")

    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    if errors:
        print("\n".join("error: " + e for e in errors), file=sys.stderr)
        sys.exit(1)

    stem = os.path.splitext(path)[0]
    for suffix, text in (("parent", parent), ("thread", thread)):
        with open(f"{stem}.{suffix}.txt", "w", encoding="utf-8") as f:
            f.write(text)

    def named(text):
        return SLACK_MENTION_RE.sub(lambda m: f"@{people[m.group(0)]}" if m.group(0) in people else m.group(0), text)

    def quoted(text):
        return "\n".join(("> " + l) if l else ">" for l in named(text).split("\n"))

    out = []
    if data.get("channel"):
        out.append(f"**Channel:** {clean(data['channel'])}\n")
    out += ["**Channel message**", quoted(parent), "", "**Thread reply**", quoted(thread), "",
            f"_Exact text: {stem}.parent.txt and {stem}.thread.txt ({len(thread)} of {LIMIT} chars)._"]
    print("\n".join(out))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    main(sys.argv[1])
