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
- every read-only smoke check passes on the system as it is now; record
  them in one call: `set FILE S1 pass S2 pass S3 pass --baseline`
- it is the window the plan chose and the people it needs are around

Anything off: correct the document, tell the user, stop. Do not adapt on the
fly.

## 2. Start the dashboard

Start the monitor as a background process, `monitor.py serve CONFIG`, then
run `monitor.py status CONFIG`. Go on only when it reports that it is up
and, if the change has heartbeats, that every one is green on the untouched
system. Red or missing here means the baseline is off: stop as in section 1.

Give the user the address and have them open it. From here until the change
is completed or reverted this is where they watch, and the page is not
republished. The script refuses to record the first step while the monitor
is down, running in demo mode, or not green.

## 3. Final approval

Show the user, in one message:

- the numbered steps exactly as they will run: what each does for users,
  what is run, and who does it
- who runs each smoke test: a script, you, or them by name
- the point of no return, if there is one
- the critical smoke checks, and this sentence: "If one of these fails I
  stop, tell you what broke and whether the planned reversal still fits,
  and reverse on your word: <reversal summary>."
- every accepted risk or unknown that still has no mitigation
- anything that changed since they approved the plan
- how long it takes and what users may notice meanwhile
- the dashboard's address, and the request to confirm it is open and live

Ask for an explicit go. The approval is for this list, now. Approval of the
plan, a yes from an earlier session or a yes to something else does not
count. If they answer with a question or a condition, settle it and ask
again. On a yes: `approve FILE execute --by <their name>`. The script binds
the approval to the steps, the reversal and the smoke tests; editing any of
them voids it.

## 4. Run the steps

One at a time, in order: do exactly what `details` says, confirm `verify` by
observing it (a command that exits 0 is not proof), then `set FILE E1 done`.
The line it prints is your update to the user. Pass it on as it is and go to
the next step; while everything matches the plan, that line is all you say.

If the change has heartbeats, glance at the monitor after every step:
`monitor.py status CONFIG` prints one line and exits 1 when a critical check
is red. A red critical heartbeat at any moment counts like a failed critical
smoke test: section 6.

The monitor is a window, not a dependency. If it dies mid-change, say so in
one line, carry on with the plan and run the remaining checks yourself;
restart it only if that is quick.

- Only what the step says. No extra fix, no cleanup, no "while I am here".
- Only the steps that are yours. A step that belongs to a person: tell them
  it is their turn, wait, then confirm `verify` yourself and record it. A
  step a script does: start it or wait for it as `details` says.
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
- otherwise handle it like a failed critical check: section 6

## 5. Smoke tests

With all steps done, every check runs, critical ones first, each by its
owner. `monitor.py run CONFIG` runs all the tests a script owns, and the user
sees each result land on the dashboard. The ones that are yours you run
yourself. Running a check and recording it stay two commands. Record the
ones that pass together, `set FILE S1 pass S2 pass S3 pass`, and pass on the
line it prints. A failure gets a call of its own with what you saw:
`set FILE S4 fail --note "<what you saw>"`.

- A critical check fails: stop there and go to section 6. Do not rerun it
  hoping and do not start fixing. The one exception is a check that could
  not run at all (a tool error, not a verdict): retry it once, and treat a
  second non-verdict as a failure.
- A non-critical check fails: record what you saw, carry on, report it as a
  follow-up.
- A test that belongs to a person is theirs: ask and wait. They answer with
  the Pass and Fail buttons on their row of the dashboard, which
  `monitor.py status CONFIG` then shows, or in the conversation. Either way
  you record it with `set`, in their words. Do not do the test for them,
  even where you could.

## 6. When it fails

The user is watching and the reversal is their call. Your job is to put the
facts in front of them within the first minute and keep the reversal ready.

1. Record it: `set FILE S1 fail --note "<what you saw>"`, or the failed
   step.
2. In the same message, start one read-only diagnostics worker in the
   background and do not wait for it. Its brief: the check that failed with
   expected and observed, the steps run so far, where to look (logs,
   metrics, the state of everything those steps touched), the remaining
   read-only smoke checks to run, and a few minutes at most. It returns
   what is broken, how widely and since when, whether it is getting worse,
   and anything in the current state that would make a reversal step fail
   or lose data. It changes nothing.
3. Tell the user at once, in a few lines:
   - what broke: the check, expected against observed
   - what that means for users right now, taken from the risk the check
     covers
   - whether the planned reversal applies. Walk `reversal.steps` against
     where the system really is: which steps ran, whether the `window` is
     still open, what was written since the switch, whether a point of no
     return was crossed. Answer "applies as written", "applies with this
     change: ..." or "does not apply because ...".
   - the question: reverse now?
4. Work through the reversal with the user while the worker runs. When it
   reports, relay it in two or three lines, starting with anything that
   changes the answer on the reversal. Going back does not need the root
   cause: if the user says go before the worker is done, go.
5. If the reversal needs adjusting, edit `reversal.steps` in the document
   and show the new steps before asking. Fix forward only if the user asks
   for exactly that, and then as a new step written into the document.

On the user's explicit yes: `approve FILE revert --by <their name>`. The
script binds it to the reversal steps as they stand; editing them voids it.
If they decide not to reverse, put the decision and their name in the
failed item's note. The change then stays open, never completed, until that
check passes or the change is reversed.

## 7. Reversal

Run `reversal.steps` in order and `set FILE V1 done` after each. Then run
the smoke checks again: the restored system has to match the baseline.
`finish FILE reverted --note "<why>"`, and publish the page once with that state.

Report what failed (what was observed, not a theory), that the system is
back and how you know, what was or was not lost, and what is still in place
(merged PRs that are switched off, copied data). Do not try the change
again. It goes back to plan with the failure as a new finding.

If a reversal step fails, stop and tell the user at once with the exact
state: what is reverted, what is not, what users see right now. That is an
incident and it is theirs to run.

## 8. Complete

`finish FILE completed`. It refuses while anything is pending. Publish the
page once now, with the final state, and leave the monitor running until
the user says the watch is over. Report:

- the change is live and which checks passed, and any non-critical ones that
  failed
- what to watch over the next hours and days, and until when the way back
  stays open
- cleanup the plan deferred (removing the old path, flags), as later work
- the `improvements` list, as an offer. Start none of it.
