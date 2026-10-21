---
name: review-pr
description: Review one pull request or a batch of related pull requests (a rollout, migration, deploy or infra change across one or more repos) with parallel read-only reviewer subagents, then report at product/behaviour level and, when asked, post comment or approval reviews from the user's GitHub account. Use whenever the user pastes one or more PR links, gives a merge order, says "review this PR", "review these PRs", "what's blocking this deploy", "organize sub-agents to review", "approve the ones that are fine", or asks whether a set of PRs is safe to merge. Also use for a single infra PR when the user wants a technical review summarised for non-reviewers.
---

# Review PR

One PR or several, one outcome. The user wants to know what will break, in
plain terms, and then wants the PRs marked up so the authors can act.
Reviewer subagents are the technical reviewers; you are the editor who turns
their findings into a decision and, when asked, into GitHub reviews.

## 1. Pre-flight (one shell call)

```bash
gh auth status
gh api user --jq .login
for url in <PR urls>; do gh pr view "$url" --json number,title,state,author,reviewDecision,mergeable,headRefOid; done
```

Why: the user's list is a *claim* about state. In practice some "to merge" PRs
are already merged and some "already applied" ones are not. Record state before
delegating so the reviewers verify the premise instead of inheriting it. You
also cannot approve a PR you authored, so note which ones are the user's own.

## 2. Partition and spawn reviewers

Split by concern, not by PR count. A single small PR needs one reviewer, or
none if you can read the whole diff yourself. Typical cut for N PRs:

- one agent per tightly coupled pair (stacked PRs, same subsystem, same env)
- one agent per repo cluster for the rest
- **always one cross-cutting tracer** when there are several PRs, following
  the whole request path and merge sequence across repos (hostname → tunnel →
  gateway → route → service; image build → registry → manifest tag). The
  seams between PRs are where the real blockers live, and per-PR reviewers
  never see them.

Spawn all reviewers at once, in the background, on the strongest available
model. Each brief contains:

- Persona: lazy senior engineer. Hunt correctness and blocking problems
  first, over-engineering second (copied manifests that should share a base,
  config for constants, dead flexibility, hand-rolled scripts for native
  features). Super technical. Read-only, never post.
- Context: what the change is meant to achieve, the user's stated merge order
  and applied-state notes, and the related PRs it must read for consistency
  (give URLs).
- Tools: `gh pr view/diff/checks`, `gh api repos/<owner>/<repo>/pulls/<n>/{files,comments,reviews}`,
  shallow clone into a scratch directory (`git clone --depth 50`, then
  `git fetch origin pull/<n>/head:pr-<n>`) when the diff alone is not enough.
  Compare against the environment or code path that already works; every
  deviation needs a reason.
- A numbered checklist of the specific questions for that cluster. Be concrete
  (names, namespaces, ports, tags, CRDs, RBAC, sync ordering, secrets,
  cross-origin, breaking changes between versions, CI that only lints).
- Output contract, verbatim:

  > Return ONLY a findings list, ranked most severe first, with severity tag
  > per item: BLOCKING (must fix before merge), CRITICAL (will break something
  > after merge/apply), MINOR, NIT. Each finding: one or two lines, `file:line`
  > or PR number, what's wrong, what to do instead. Then a 2-line "merge order
  > verdict". If nothing blocking, say so explicitly. No essays.

Tell the user the reviewers are running and stop. Do not predict results.

## 3. Synthesise for the user

When all reports are in, write one message at product and behaviour level.
The reader decides whether to merge; they do not need YAML in prose.

Structure (bold lead per bullet, one or two sentences each):

- **Blocking**: will stop the change from working or is unsafe. Include
  missing manual steps the PRs cannot contain (DNS records, access policies,
  secrets, "wait for the build to finish").
- **Critical**: will break or mislead. Includes "applied but not merged"
  drift (next apply from main reverts live state) and wrong premises in the
  user's list.
- **Worth knowing**: behaviour changes, expected false alarms, restarts and
  when to schedule them.
- **Everything else checks out**: one short paragraph naming what was verified.
- **Recommended order**: numbered, only if it differs from the user's plan.
- Close with: minor/nit findings exist, full technical lists available.

Severity is yours to assign, not the agents'. Reviewers inflate; a process
gap (missing second approval) is not the same as a public API exposure.

Follow-up questions ("does this touch production?") get answered from the
findings plus a quick grep of the clones, not a new round of agents.

## 4. Post reviews (only when the user asks)

Reviews are outward-facing and land in other people's inboxes. Wait for an
explicit instruction, and if the user's count of comment-vs-approve does not
match yours, ask once which PRs they mean before posting.

Rules that fell out of practice:

- Only the **actionable** blocker gets a COMMENT-level review, with an inline
  comment on the line that introduces it. Everything else, including
  "critical" items whose fix is simply "merge soon", goes into an **APPROVE**
  whose body carries an "FYI, non-blocking" list. Authors read approvals;
  they argue with change requests.
- Approval bodies start with what was verified (name chains, versions,
  parity), then the preconditions before merging, then the FYI list. Keep the
  reviewers' `file:line` references; drop their prose.
- Build one JSON file per review in a scratch directory and post with
  `gh api -X POST repos/<owner>/<repo>/pulls/<n>/reviews --input file.json`.
  Omit `commit_id`: a short SHA is rejected with "invalid GitObjectID" and the
  default is the PR head anyway. Inline comments use
  `{"path", "line", "side": "RIGHT", "body"}` with the line number from the
  new side of the diff hunk; count it from the `@@ -a,b +c,d @@` header.
- Post all in one shell call, print `state` and `html_url` for each, and
  report them as links. If a call fails, confirm nothing was posted before
  retrying; duplicate reviews are noise the author has to dismiss.
- PRs that were outside the review scope get no review until they are
  reviewed. Say so.

## Pitfalls seen

- Lists of "already applied" infra PRs: unmerged means main is behind the
  cluster, and the next untargeted apply destroys live resources. Treat as
  critical every time, and name the exact resources.
- "Merge X before Y" claims: check whether X is already merged (squash merges
  leave stacked branches carrying duplicate commits; recommend squash).
- Mutable image tags (`latest`, `*-latest`) plus `IfNotPresent`: ask what
  moves the tag and what triggers a rollout.
- CI that is green but only lints or echoes: say explicitly that it proves
  nothing, so nobody treats the checkmark as validation.
- New public hostnames: check the access layer (an identity-aware proxy,
  OAuth proxy, allowlists) on every sibling hostname and the working
  environment. "It's public on staging too" is often stale; `curl -I` it.
- Parity with the working environment is the yardstick. Byte-identical copies
  are a nit; a missing path, env var or probe is a finding.

## On Claude Code

Reviewers: `Agent` tool, `subagent_type: general-purpose`, `model: "opus"`,
`run_in_background: true`, all in one message. Use the session scratchpad
directory for clones and review JSON. Other hosts: use whatever background
subagent mechanism exists, or review the PRs yourself in sequence.
