# Execute

Carry out the approved plan exactly, prove it worked, or put things back.
You add no judgment about what to change; the plan already made those calls.

## 1. Confirm every piece

Nothing changes in this step.

Run `check FILE --gate execute`. Closed: report what is missing and stop.

The document describes a past moment. Verify the present, read-only:

- every prepared PR: in the state the plan expects, approved, checks green,
  no commits since it was marked ready, no conflicts
- scripts and smoke checks exist at the revision the document names and
  their tests pass
- the facts the plan stands on still hold: versions, current config, the
  live state it measured
- nothing else is happening on the same systems: incidents, freezes, other
  people's deploys
- you hold the access every step and every reversal step needs, checked
  without using it (an identity or permission query, a dry run)
- every read-only smoke check passes on the system as it is now; record each
  with `set FILE S1 pass --baseline`
- it is the window the plan chose and the people it needs are around

Anything off: correct the document, tell the user, stop. Do not adapt on the
fly.

## 2. Final approval

Show the user, in one message:

- the numbered steps exactly as you will run them: what each does for users
  and what you will run
- the point of no return, if there is one
- the critical smoke checks, and this sentence: "If one of these fails I
  reverse at once without asking: <reversal summary>."
- every accepted risk or unknown that still has no mitigation
- anything that changed since they approved the plan
- how long it takes and what users may notice meanwhile

Ask for an explicit go. The approval is for this list, now. Approval of the
plan, a yes from an earlier session or a yes to something else does not
count. If they answer with a question or a condition, settle it and ask
again. On a yes: `approve FILE execute --by <their name>`. The script binds
the approval to the steps, the reversal and the smoke tests; editing any of
them voids it.

## 3. Run the steps

One at a time, in order. Say what you are about to do, do exactly what
`details` says, confirm `verify` by observing it (a command that exits 0 is
not proof), then `set FILE E1 done` and update the page.

- Only what the step says. No extra fix, no cleanup, no "while I am here".
- A permission prompt or a denial mid-step is a stop, not something to route
  around.
- Before a `no_return` step, stop and confirm once more with the user,
  showing the state so far.

`verify` fails, a command errors, or reality differs from the plan:
`set FILE E2 failed --note "<what you saw>"` and stop. Do not improvise a
fix: an unplanned fix on a half-changed system is a second critical change
with no plan at all. Then:

- the step is safe to repeat and the cause is plainly transient (a timeout,
  a lock): retry once
- otherwise reverse (section 5)
- unless the system is stable where it stands and users are unaffected: then
  hold, tell the user and let them choose between reversing and re-planning

## 4. Smoke tests

With all steps done, run every check, critical ones first, and record each:
`set FILE S1 pass` or `set FILE S1 fail --note "<what you saw>"`.

- A critical check fails: reverse now. Do not rerun it hoping, do not debug
  first, do not ask; the user approved exactly this in section 2. The one
  exception is a check that could not run at all (a tool error, not a
  verdict): retry it once, and treat a second non-verdict as a failure.
- A non-critical check fails: record what you saw, carry on, report it as a
  follow-up.
- Manual checks: do them in a browser if you have one, with the test
  accounts the plan names. Otherwise ask the user to do them and wait.

## 5. Reversal

Run `reversal.steps` in order and `set FILE V1 done` after each. Then run
the smoke checks again: the restored system has to match the baseline.
`finish FILE reverted --note "<why>"`.

Report what failed (what was observed, not a theory), that the system is
back and how you know, what was or was not lost, and what is still in place
(merged PRs that are switched off, copied data). Do not try the change
again. It goes back to plan with the failure as a new finding.

If a reversal step fails, stop and tell the user at once with the exact
state: what is reverted, what is not, what users see right now. That is an
incident and it is theirs to run.

## 6. Complete

`finish FILE completed`. It refuses while anything is pending. Report:

- the change is live and which checks passed, and any non-critical ones that
  failed
- what to watch over the next hours and days, and until when the way back
  stays open
- cleanup the plan deferred (removing the old path, flags), as later work
- the `improvements` list, as an offer. Start none of it.
