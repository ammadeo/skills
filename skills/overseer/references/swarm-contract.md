# swarm: the shared contract (spike)

This file is the single source of truth for the swarm repo layout, the work
file format, the `swarm` CLI and the JSON it emits. The CLI, the board and
the overseer skill are built against it independently. Change it only by
agreement; everything else may change freely.

## 1. The swarm repo

`$SWARM_HOME`, default `~/swarm`. Created by `swarm init`: a git repository
(initial commit) with

```
swarm.yml        settings (flat YAML)
decisions.md     the user's answers, D-ids
work/W<n>.md     one file per work item
runs.md          one line per overseer run
.swarm/          machine state (last-run marker); git-ignored
```

Every mutating CLI command ends with `git add -A && git commit -q -m "<cmd> <id>"`
in `$SWARM_HOME` (skipped when `auto_commit: false`). Concurrency: take an
exclusive lock on `$SWARM_HOME/.swarm/lock` around read-modify-write-commit,
so two sessions reporting at once do not corrupt a file or hit git's index
lock. Retry the lock for up to 10 s, then fail with exit 3.

### swarm.yml

```yaml
next_id: 1            # next W number
auto_commit: true
stuck_hours: 3        # working/fixing with no report/log for this long → stuck
owners: []            # GitHub owners passed to pr-status.sh --owner
repos: []             # GitHub repos passed to pr-status.sh --repo
bot_reviewer: ""      # login of a review bot, informational
expected_red: []      # "owner/repo: <regex over check names>" lines treated as expected failures
```

### decisions.md

```
# Decisions

## D1 (2026-10-29 14:05) W12: Keep the throttle per account or per IP?
Answer: A (per account) — <free text from `swarm answer`>
```

### runs.md

One line per overseer run: `- 2026-10-29 14:05  <summary>`.

## 2. The work file `work/W<n>.md`

YAML front matter, then fixed sections. Timestamps are local
`YYYY-MM-DD HH:MM`. Unknown front matter keys are preserved.

```markdown
---
id: W12
title: Rate-limit password resets
state: pr-open
role: builder            # builder | coordinator  (who owns the work)
owner: ""                # session id or a name; "" = not started
repo: acme/app
branch: feat/reset-throttle
pr: acme/app#5380        # "" when none
head: 9f1c2d3            # short sha the owner last reported
verified_main: 4a7b8c9   # main sha the owner merged in and built against
ci: success              # success | failure | pending | none   (written by scan)
threads_open: 0          # unresolved review threads               (scan)
review: APPROVED         # APPROVED | CHANGES_REQUESTED | REVIEW_REQUIRED | none (scan)
merged: false            # (scan)
needs: [W7]              # work ids this one waits for
state_before: ""         # the state to return to after needs-decision
created: 2026-10-29 10:00
updated: 2026-10-29 14:05
---
## Brief
<free text: goal, acceptance, scope limits; written by `swarm new`>

## Log
- 2026-10-29 14:05 builder: pushed fix for the thread on app/x.rb:42
- 2026-10-29 13:10 reviewer: 3 findings (1 medium, 2 low)

## Findings
<appended by `swarm findings`, newest block last, each block headed `### <timestamp> <who>`>

## Question
<present only while state is needs-decision>
Keep the throttle per account or per IP?
- A: per account (cost: one migration)
- B: per IP (cost: breaks shared-office logins)
Recommended: A

## Answer
<present after `swarm answer`: `A — <text>`; the Question section stays for history>
```

### States

```
queued          created, nobody started it
working         owner is on it
blocked         owner cannot continue (reason in the last Log line)
needs-decision  a Question is open for the user
pr-open         a PR exists and is ready for review
fixing          findings or review comments are being addressed
ready           swarm ready passed; waits for the user to merge
done            merged (or closed on purpose)
archived        done and the owning session archived
```

Allowed by anyone with `swarm report`; `needs-decision` is set only by
`swarm ask`, `ready` only by `swarm ready`.

## 3. CLI

Invocation: `deno run -A <skill>/scripts/swarm.ts <command> …`. `swarm init`
prints a one-line alias the user can add to their shell. Global flags:
`--home DIR` (overrides `$SWARM_HOME`), `--who NAME` (default: `$SWARM_WHO`,
else the role field of the work item, else "unknown"), `--json` where noted.
Exit codes: 0 ok, 1 check failed (ready/changes with `--fail-on`), 2 usage, 3 lock.

| Command | Effect |
| --- | --- |
| `init [--home DIR]` | create the repo and files above; idempotent |
| `new "<title>" --repo OWNER/NAME [--role builder\|coordinator] [--needs W1,W2] [--brief-file F]` | allocate the next id, write the file (Brief from the file or stdin, else empty), print `W<n>` |
| `brief W12 --role builder\|coordinator\|reviewer` | print the full brief to hand to a session: the role template from `<skill>/references/roles/<role>.md` with `{{id}}`, `{{title}}`, `{{repo}}`, `{{branch}}`, `{{pr}}`, `{{home}}`, `{{swarm}}` (the CLI invocation) filled in, followed by the work file's Brief section |
| `report W12 key=value …` | set front matter fields: state, owner, role, branch, pr, head, verified_main, needs (comma list); appends `- <ts> <who>: report state=…` to Log; refuses `needs-decision`/`ready`/`archived` (use ask/ready/archive) |
| `log W12 "<text>"` | append a Log line |
| `ask W12 "<question>" --option "A: …" [--option …] [--recommend A]` | write Question, remember `state_before`, set state needs-decision |
| `answer W12 "<text>"` | write Answer, append D-entry to decisions.md, restore `state_before`, Log line |
| `findings W12 [< file]` | append a Findings block from stdin; state pr-open → fixing |
| `scan [--sessions FILE] [--pr-status CMD]` | run `pr-status.sh --json` (default: `<skill>/scripts/pr-status.sh`, with owners/repos from swarm.yml) and copy `ci`, `threads_open`, `review`, `merged` onto work items matched by `pr`, or by `repo`+`branch` when `pr` is empty (then also set `pr`). `--sessions FILE` is a JSON array of `{sessionId,title,branch,isRunning,lastActivityAt,prNumber,prState,isArchived}`: match `owner` to `sessionId`, store `session_running` and `session_last` in front matter. Merged → state done. Log nothing; only front matter changes. |
| `changes [--json] [--since REF]` | events since the last run marker (`.swarm/last-run`, a commit sha; default: initial commit): per work item, compare the file then and now. Event kinds: `new`, `started`, `pr-opened`, `went-red`, `went-green`, `new-findings`, `asked`, `answered`, `blocked`, `ready`, `merged`, `pushed` (`head` changed while `pr` is set; the overseer starts a reviewer on it when the state is pr-open), `stuck` (state working/fixing and last Log/updated older than stuck_hours), `unanswered` (needs-decision, no Answer yet; emitted every run). Text: one line each `W12  went-red     acme/app#5380 ci=failure (was success)`. |
| `status [--overseer] [--json]` | plain: a table of work items (id, state, role, repo, pr, ci, threads, owner, updated). `--overseer`: the compact run context: counts by state, then "Needs you" (open questions, full text), then "Changes since last run" (= changes), then the table, then the last 3 runs. `--json`: the full state object (§4). |
| `ready W12` | pass only if: pr set; `ci: success`; `threads_open: 0`; review not CHANGES_REQUESTED; `head` equals the PR's current head (ask `gh pr view --json headRefOid`); the PR body contains `Verification at <head>`; `verified_main` equals the base branch's current sha (`gh api repos/O/R/commits/<base>` → sha), or `--allow-behind N` commits. On pass set state ready; on fail print each unmet condition and exit 1. |
| `done W12` / `archive W12` | set the state; archive requires done |
| `run-done "<summary>"` | append to runs.md, commit, write the commit sha to `.swarm/last-run` |
| `board` | start the board (`deno run -A npm:vite` in `<skill>/board` with `SWARM_HOME` exported) and print its URL |

## 4. `status --json` shape (the board reads exactly this)

```json
{
  "home": "/Users/me/swarm",
  "generated": "2026-10-29 14:05",
  "config": { "next_id": 13, "stuck_hours": 3, "owners": [], "repos": [] },
  "work": [
    {
      "id": "W12", "title": "…", "state": "pr-open", "role": "builder", "owner": "local_…",
      "repo": "acme/app", "branch": "…", "pr": "acme/app#5380", "pr_url": "https://github.com/acme/app/pull/5380",
      "head": "9f1c2d3", "verified_main": "4a7b8c9", "ci": "success", "threads_open": 0,
      "review": "APPROVED", "merged": false, "needs": ["W7"], "created": "…", "updated": "…",
      "session_running": false, "session_last": "",
      "brief": "…markdown…",
      "log": [ { "ts": "2026-10-29 14:05", "who": "builder", "text": "…" } ],
      "findings": "…markdown…",
      "question": { "text": "…", "options": [ { "key": "A", "text": "…" } ], "recommended": "A" },
      "answer": "A — …",
      "stuck": false
    }
  ],
  "changes": [ { "id": "W12", "kind": "went-red", "detail": "ci=failure (was success)" } ],
  "decisions": [ { "id": "D1", "ts": "…", "work": "W12", "question": "…", "answer": "…" } ],
  "runs": [ { "ts": "…", "summary": "…" } ]
}
```

`question` and `answer` are `null` when absent; `log` is oldest first.

## 5. The board

A Vite + React app in `<skill>/board`, run with Deno (`deno run -A npm:vite`).
A Vite plugin (dev server middleware) serves `GET /api/state` by running
`deno run -A ../scripts/swarm.ts status --json --home $SWARM_HOME` and
returning its stdout, watches `$SWARM_HOME/work`, `decisions.md` and
`runs.md` and sends a `swarm:update` custom HMR event on change; the client
refetches on that event. `SWARM_STATE_FIXTURE=<file>` makes the middleware
serve that JSON instead (for development without the CLI). Read-only: the
board never writes to the swarm repo in the spike.

Layout: a "Needs you" strip on top (every open question with options and the
recommendation, plus the `swarm answer` command to copy), then columns by
state in the order of §2, cards showing id, title, repo, PR link, CI, threads,
review, owner (running or not), last log line, a stuck marker. Below: changes
since the last run, the last runs, the decisions.

## 6. Reporting contract (pasted into every role brief)

```
Swarm reporting (binding). Your work item is {{id}}. Use the CLI, never edit the files:
  {{swarm}} report {{id}} state=<working|blocked|pr-open|fixing> [pr=owner/repo#n] [head=<sha7>] [verified_main=<sha7>] [branch=…]
  {{swarm}} log {{id}} "<one line of progress>"            at every milestone, at least hourly while working
  {{swarm}} ask {{id}} "<question>" --option "A: … (cost)" --option "B: … (cost)" --recommend A
      then stop and wait; the answer arrives as a message or in `{{swarm}} status`
Report state=pr-open with pr= and head= as soon as the PR exists; state=fixing while addressing findings;
after every push report head= and, once you have merged the base branch in and built, verified_main=.
Never set ready, done or archived yourself.
```
