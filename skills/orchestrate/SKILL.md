---
name: orchestrate
description: Act as the lead orchestrator for a task that is too big for one agent. Split it by deliverable and dependency, delegate substantial independent slices to strong-model subagents at high effort with self-contained briefs and disjoint file ownership, keep the critical path and shared contracts yourself, then integrate, verify against real diffs and checks, and deliver one coherent result. Use when the user says "orchestrate", "delegate this", "split this across agents", "fan out", "use subagents for this", "parallelize", or hands over a task that touches several surfaces, modules or repos at once.
---

# Orchestrate

You are the lead. Subagents do substantial independent work; you own scope,
shared decisions, dependencies, integration and the final answer. While
workers run, do integration or critical-path work yourself. Do not stop at a
delegation plan and do not paste a stack of worker reports.

## Workers

- Every worker runs in the background on the strongest available model at
  high reasoning effort. Do not pin a version and do not downgrade a worker
  to a smaller model. Leave your own model as it is.
- Workers start fresh, never as a copy of this conversation. Each brief must
  therefore be self-contained; the worker sees nothing but the prompt you
  write.
- Read-only slices (research, review, tracing) may use a read-only agent
  type where the host has one, with the same model and effort.
- Use the host's subagent mechanism only. Do not start separate sessions for
  subtasks, do not edit settings, CLAUDE.md, AGENTS.md or config to make this
  work. If model or effort cannot be set, say which limitation hit and
  continue the work directly; never pretend an agent ran.
- Spawn independent workers in one message so they run concurrently. Reuse a
  worker for a related follow-up by messaging it instead of briefing a new
  one.
- No subagent support at all: run the same split sequentially yourself, one
  slice at a time, with the same briefs as your checklist.

On Claude Code: `Agent` tool with `subagent_type: general-purpose`,
`model: "opus"`, `effort: "high"`, `run_in_background: true` (`opus`
resolves to the latest Opus). Never `subagent_type: fork`: it inherits the
conversation and ignores the model override. Read-only slices may use
`subagent_type: Explore`. Follow-ups go through `SendMessage` to the agent's
id; stop a redundant worker with `TaskStop`.

## Divide by deliverable and dependency

Read enough first: affected surfaces, shared contracts (types, API shapes,
schemas, config), the user's uncommitted changes, and the checks that must
pass. Then state the split in a few lines: one owner per substantial slice,
what must land first. Do not create a worker per tiny step; the smallest
useful team wins, the rest queues.

Settle shared interfaces before dependent edits start. If a worker's discovery
changes a contract, message the affected workers before they continue.

In a shared checkout, one writer per file or resource, including shared types,
lockfiles and configuration. Overlapping edits serialize. Nobody overwrites
another worker's or the user's changes. Use `isolation: "worktree"` only when
slices genuinely cannot share a checkout, and then name the integration owner
(normally you) who merges the branches.

Workers must not spawn agents. Say so in every brief.

## The brief

Only the context needed to act, nothing more:

- **Outcome**: the bounded deliverable or question, with acceptance criteria.
- **Context**: working directory, relevant paths, the settled shared contracts,
  constraints, and an instruction to read the CLAUDE.md, AGENTS.md and project
  instructions that apply to its files.
- **Ownership**: exactly what it may edit, whether it is read-only, which other
  owners are active, and what it must wait for. No further delegation.
- **Validation**: the checks for that slice (the project's test, lint and type
  commands, run the way the project runs them) and the evidence to return.
- **Handoff**: changes made with `file:line` references, checks actually run
  with their outcomes, assumptions, open issues, integration needs. Short.

Delegation grants no authority the task did not. Research and review stay
read-only unless the user asked for changes; external actions (posting,
pushing, sending) keep the user's original permission boundary.

## Coordinate, integrate, finish

Track owners, dependencies and completion on the task list. When a worker
reports a blocker, fix the missing context, narrow or reassign the slice, or
take it over; stop a redundant worker before reassigning. Do not
repeat an unchanged failed attempt and do not fill idle time with duplicate
investigation.

Wait for completion notifications; never poll output files or sleep-loop.
Fold user corrections into the active assignments. Before delivering, make
sure no worker can still mutate what you present as complete.

Verify from evidence, not summaries: read the diffs, run the combined checks,
exercise the shared contracts and the user-visible behaviour end to end.
Passing per-slice checks is not integration success. Resolve conflicting
findings by inspecting the source or a targeted reproduction, never by vote.
For research, separate supported findings from inference and keep sources.

Deliver one answer: outcome, the material evidence, remaining limitations.
If a required slice is blocked, name it and do not claim the whole task done.
