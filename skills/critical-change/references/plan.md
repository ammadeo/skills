# Plan

The phase that protects users. Everything later only carries out what is
decided here, so an edge case missed here stays missed.

Read-only, without exception: no code changes, branches, commits or PRs, no
writes to any environment, and no "harmless" command that changes state (a
restart, a cache clear, a test record, a dry run you cannot prove is
read-only). The only things you create are `change.json`, its page and
questions for the user. If answering a question seems to need a write, it is
an open unknown.

## 1. Frame it

Take what you can from the request and the repos, then ask the user only for
what you cannot find:

- what must be true afterwards, and why now
- who is affected if it goes wrong and how they would notice (`impact`)
- constraints: the window, tolerated downtime, freezes, who has to be around
- who carries out the change: you, or a person with you watching

Restate the change in two sentences and get a yes before the expensive part.

## 2. Map what exists

Work from sources of truth: code, infrastructure definitions, read-only
queries against the live system, dashboards, runbooks. Not from memory,
naming or what the ticket claims. For the thing being changed, find every:

- reader and writer: services, jobs, scripts, people with a console
- way in: DNS, load balancers, queues, schedulers, third-party webhooks
- copy of its state: caches, replicas, backups, search indexes, exports
- config value and secret that names it, in every environment
- alert, dashboard and runbook that assumes its current shape

Where the definition and the live state can differ (applied but not merged,
edits made by hand), look at the live state. Drift is a finding.

## 3. List unknowns and risks

Every question you cannot answer yet is an unknown. Every way users could be
hurt is a risk. Sweep these on purpose; each has sunk a change that looked
finished:

- requests, jobs and transactions in flight at the moment of the switch
- the time when old and new run side by side; old clients, cached pages,
  mobile apps that never update
- data written during the change, and data written after it if we go back
- caches, TTLs, connection pools and DNS that keep giving the old answer
- retries and duplicates: is every step and every message safe to repeat
- order between pieces: B lands before A, or A lands and B never does
- a step that stops halfway
- scheduled work that fires mid-change: cron, backups, autoscaling,
  certificate renewal, someone else's deploy
- limits: quotas, rate limits, disk, connection counts, lock time on big
  tables
- permissions and secrets the new path needs and the old one did not
- what monitoring will not show: failures that look like silence
- third parties: allowlists, webhooks, contracts pinned to the old shape
- load at the chosen time, and at peak if the change slips

Severity is about users. `critical`: many users blocked, data lost or
corrupted, or no way back. `high`: a feature broken or wrong data shown to
many. `medium`: degraded but working. `low`: only the team notices.

## 4. Research

Each unknown ends answered with evidence or declared open. Load
`orchestrate` and give one read-only worker per independent area (a repo, a
system, a cluster of questions). The brief carries the questions, where to
look, the read-only rule from the top of this file in full, and the return
format: answer, evidence, confidence, anything new it ran into. Check the
answers the plan hinges on yourself.

Evidence is something a reviewer can check again: `file:line`, a command
with its output, a link to the vendor's documentation. "It should" is not
evidence.

Access denied, or behaviour you cannot explain after a real attempt: stop
there and mark it `open` with

- `blocked_by`: what stopped you
- `if_wrong`: what happens to users if the hopeful assumption is false
- `admin_guide`: three to five steps someone with access can follow with no
  context: where to look, what to send back, which answer changes the plan

The page shows it at the top in red. Do not soften it and do not quietly
design around it. A risk nobody can mitigate yet gets `status: unmitigated`
and `needs` (the decision or work that would close it) and is shown the same
way.

## 5. Design the smallest change

- `steps`, in order. Each is one action with `verify` (something you can
  observe that proves it worked, checked before the next step) and `revert`
  (how to undo this step alone). A step that cannot be undone gets
  `no_return: true`; put it as late as possible.
- `by` on every step and every reversal step: `agent` or `human` (with
  `who`), as the user decided in section 1, or `script` when automation does
  it with nobody deciding in the moment.
- Prefer shapes where old and new both keep working: add before remove,
  write to both before reading from the new one, switch with a flag or
  config instead of a deploy, a small share of traffic before all of it.
- Separate "merged" from "live". Pick the mechanism that lets code land
  switched off (a flag, config, a manual sync or apply, a disabled job).
  Prepare depends on it.
- `prep` lists every building block prepare has to produce: each PR, each
  script, the smoke checks, the live monitor, the switch, whatever the way
  back needs.
- A choice a stakeholder would want a say in is a decision: what we chose
  and why, in their terms. If the choice is theirs to make, set
  `status: open` and put your recommendation in `why`.
- `scope.out` names what a reader would expect to be included and is not.
  Ideas the change makes possible go to `improvements`, not into the change.

## 6. The way back

`reversal` holds the steps that return users to today's behaviour, in order,
and `window` says until when that stays possible. Answer one question
explicitly in the summary: what happens to data written after the switch if
we go back. The reversal gets run under pressure, so write steps that need
no judgment.

No way back (`possible: false`) is a critical risk in itself. It needs a
replacement in `instead`: a restore from a backup that has really been
restored somewhere, a rehearsal on a copy, a partial rollout that limits who
is hit, a maintenance window users were told about. Without one the page
shows it as unmitigated, and that is the correct picture.

## 7. Smoke tests

Derive them from the risks, not from what is easy to check. For each risk
ask: if this happened, what is the fastest observation that would show it?
That observation is a check.

- `mitigates`: the risks or unknowns it watches. A check with no risk behind
  it does not belong; delete it.
- `why`: why this observation catches that risk, and what it would miss.
- `how` and `expect`: exact enough that another agent reaches the same
  verdict.
- `critical`: true when a failure means users are being hurt now or data is
  at risk. A critical failure stops the change and puts the reversal to
  the user at once. False when the
  failure can wait for a follow-up. Decide it here, calmly; nobody decides
  this well mid-change.
- `by`: who runs it. Aim for `script`: a command decides, the monitor runs
  it, and nobody has to judge under pressure. Use `agent` only when the
  verdict needs a reading or a comparison no script can make, and `human`
  (with `who`) only for what a person has to see for themselves. `check`
  warns about every test that is not a script's.

Check the old promises, not only the new path: what worked before and must
still work (existing sessions, existing data, neighbours on the same
resource). Every check must be able to fail; one that passes on a broken
system is worse than none. Prefer checks that can also run before the
change, so there is a baseline to compare with.

Heartbeats are optional, and most changes need none: the smoke tests carry
the verdict. Name one only for a signal you would act on between steps (is
it up, the error rate, what the way back depends on) that a dependable
read-only command can give every few seconds. Each one is another thing
that can fail on the day.

`check` warns about every critical or high risk without a smoke test. Add
one, or say in the risk's `mitigation` why none can exist.

## 8. Attack the plan

Before presenting, hand the document to one fresh read-only worker with this
brief: "This plan will be executed on a live system. Find what it missed: a
consumer that is not listed, a step that fails silently, a smoke test that
would pass while users are broken, a reversal that loses data, an assumption
without evidence. Findings only, most severe first." Fold in what holds up
as new unknowns, risks or checks. One round.

## 9. Check, render, present

Run `check` until it reports no errors, read the warnings, `render`, show
the page. Then tell the user, briefly:

- the change in two sentences
- risks without mitigation, first and plainly, with what each needs
- decisions waiting for them, with your recommendation
- who does what: which steps and tests a script runs, which are yours and
  which are theirs
- the request: approve the plan, or say what to change

On an explicit yes, record their decisions and run
`approve FILE plan --by <their name>`. Stop there. Preparation is a separate
phase that the user starts.
