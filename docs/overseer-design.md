# Overseer: product design

Status: direction agreed, nothing built. This document is the product-level
design for the next version of the `overseer-draft` skill. Technical details
(file formats, command syntax, the board's stack) come in a later document.

## The problem

Today's overseer is a snapshot tool. Every run starts from zero: it queries
GitHub, lists sessions, reports and forgets. Three things follow from that:

- the user re-explains decisions and context on every run;
- a status board, when one exists, is rewritten by the model each time, which
  is slow and expensive in tokens;
- the overseer has to read other sessions' transcripts to learn what they did,
  which only works on hosts that expose transcripts and costs even more.

## What the overseer becomes

A personal coordinator for a swarm of agent sessions. It never does research
or feature work itself. It knows the true state of all work in flight, routes
each piece to whoever owns it, and keeps the user's attention on the few
decisions only they can make.

Four shifts from the current skill:

1. **Memory across runs.** A small local git repository (the *swarm repo*)
   holds everything: work items, who owns them, decisions the user has made,
   open questions, a log of every run. Git gives the history for free.
2. **Agents report in; the overseer reads the board.** Every session in the
   swarm reports through one standard command-line tool (`swarm`) into the
   swarm repo. The overseer never reads transcripts; it reads what changed in
   the repo since its last run.
3. **A board, not a chat report.** A local board renders the swarm repo and
   is the main way the overseer communicates status and asks for input. The
   model never writes the board's UI; it only changes data.
4. **The overseer is a run, not a resident session.** Each run starts fresh,
   loads a compact view of the swarm repo, acts on what changed, commits and
   ends. Nothing accumulates, so nothing has to be cleared.

## The swarm

Every agent in the system has a role and follows the same reporting contract.

| Role | Does | Started by |
| --- | --- | --- |
| **overseer** | reads what changed, routes work, starts other roles, archives finished sessions, keeps the user's decision queue short | the user |
| **coordinator** | runs the `orchestrate` skill for one piece of work that is too large for a single session; reports only done, blocked or a question | the overseer |
| **builder** | one piece of work in one repository, through to a pull request | the overseer or a coordinator |
| **reviewer** | reviews a builder's pull request with the `review-pr` skill, read-only; its findings go onto the work item | the overseer |

The reporting contract is three verbs every brief carries: report a state
change, log a line of progress, ask the user a question. Sessions never edit
the swarm repo's files directly.

## Principles

- **Decision inbox.** The overseer exists to keep one short list: the
  decisions only the user can make. Each question comes with options, the
  cost of each, and a recommendation. One question at a time.
- **Route, don't do.** Fixes go to the session that owns the pull request.
  Large new work goes to a coordinator. The overseer intervenes directly only
  when something looks stuck: a work item unchanged for too long while its
  session is idle.
- **Independent review.** Every change is reviewed by a different session
  from the one that built it, before it is called ready.
- **Ready means ready.** Anything the overseer calls ready has been checked
  against the current head commit, has no open or unanswered conversation,
  and has been built with the base branch merged in. Session claims are
  verified, never taken on faith.
- **Clean up after merges.** A session whose task is finished (usually a
  merged pull request) is archived automatically if its worktree has nothing
  uncommitted or unpushed; otherwise the user is asked.
- **Local and personal.** The swarm repo and the board live on the user's
  machine. There is no shared link and no service.
- **Platform agnostic.** The skill is written in terms of a few abstract
  actions (list, message, start and archive sessions) plus the `swarm`
  command line. Each host gets a short mapping; on a host without session
  tools the overseer still runs as a pull-request overseer.

## What the user experiences

1. Open the board. It shows work by state, with a "needs you" area on top:
   each open question with its options and the recommendation.
2. Answer a question with one command (or, later, in the board). The answer
   is recorded as a decision and relayed to the session that asked.
3. Start an overseer run when sitting down to the work. It reports in one
   line what changed and what is waiting, then ends. The board has the rest.
4. Hand new work to the overseer in plain words. It creates a work item,
   writes the brief and starts a builder or a coordinator.

## Out of scope for now

- Running the overseer on a schedule (it runs when the user starts it).
- Remembering granted permissions so the overseer asks less over time.
- A learning loop that turns misses into new checks.
- Tracking work that has no repository or pull request.
- Sharing the board with other people.

## Open questions

- Answering questions directly in the board, rather than on the command
  line, depends on what each host allows. Command line first.
- The boundary between a coordinator's `orchestrate` run and the overseer's
  own routing will be settled by using it.

## Implementation direction (decided, detailed later)

- `swarm` is a single TypeScript command-line tool, no MCP server, living
  inside the skill for now.
- The board is a small local web app with hot reload, rendering the swarm
  repo's files.
- Loosely informed by multi-session orchestrator setups and by
  markdown-in-git task trackers such as Backlog.md and Beads; not a copy of
  any of them.
