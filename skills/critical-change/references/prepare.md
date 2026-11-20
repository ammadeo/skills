# Prepare

Build every piece the plan needs and leave all of it switched off. When this
phase ends, executing the change means using what was prepared; nothing has
changed for users yet.

Start with `check FILE --gate prepare`. Closed: report what is missing and
stop. Nothing gets built against a plan the user has not approved.

Limits: nothing merged and no auto-merge, nothing released, deployed or
applied, and no script of this change run against a real environment. A
rehearsal on staging, if the plan has one, is an execution step.

## The building blocks

One `prep` item each. Keep every diff as small as the plan allows: reviewers
must be able to see the whole risk in it, so no refactors and no drive-by
fixes.

**Pull requests.** One per repo and concern. Each must be safe to merge on
its own, in any order, at any time before execution, with no effect on users
until the switch from the plan is used. In the description: the change it
belongs to, why it is safe to merge alone, and what turns it on. If a PR
cannot be made inert, do not force it: record the required merge order as an
execution step and tell the user.

**The switch.** The flag, config value or toggle exists, defaults to off,
and a test proves that off means today's behaviour.

**Scripts someone runs by hand.** Dry run by default, the real run needs an
explicit flag. Safe to run twice. Stop at the first error and say what was
left behind. Print what they change. Take the target as an argument, with no
production default. Unit-test them against fakes or fixtures, including the
failure branches (stopped halfway, run again). Never against a real
environment.

**The way back.** Whatever the reversal needs (a script, a config change, a
restore command) is prepared and tested like the forward path. An untested
reversal is a hope.

**Smoke checks.** One command per check, or one script that reports a
verdict per check ID, with a non-zero exit on failure. Run every read-only
check once now, against the untouched system, and record it:
`set FILE S1 pass --baseline`. A check that fails today is broken or has
found an existing problem; fix it or tell the user, because a failing
baseline blocks execution. Checks that write anything wait for execution.

## Working

Several repos or blocks: load `orchestrate`, one worker per block with
disjoint files, the limits above in every brief word for word. Review each
diff against the plan yourself: it does what its prep item says and nothing
else.

Mark a block when it is really ready (PR open with green checks, tests
passing), verified by you and not just reported by a worker:
`set FILE P1 done --ref <PR url>`. Now that real commands, paths and flag
names exist, put them into `details` and `how` in the document and `render`.

## When the plan turns out wrong

A new unknown, risk, step or ordering goes into the document first, under
the same rules as in the plan, and to the user right away, not at the end.
If it changes scope or the way back, stop and get their decision before
building further.

## Finish

Run `check FILE --gate execute` and report like a status: what is ready,
what is still missing (human reviews, open unknowns, decisions), and that
execution starts only on their final approval. Do not merge anything and do
not start executing.
