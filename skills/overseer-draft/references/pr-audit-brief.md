# PR audit brief for read-only subagents

Use this only for PRs the status script left unclear or where thread content
matters. Give each subagent one to five PRs, read-only (`gh` reads only: no
comments, no reviews, no pushes, no merges, no reviewer requests). Ask for one
block per PR with exactly these fields so the blocks merge into one report:

1. Title, draft?, base, head, mergeable (MERGEABLE/CONFLICTING/UNKNOWN),
   mergeStateStatus, commits behind base.
2. CI rollup state plus names of failing and pending checks, each failing
   check marked "expected" or "real" against the known list below.
3. reviewDecision, who approved, requested reviewers still pending.
4. Review bots (for example Devin, CodeRabbit, Copilot): did one post a
   review, is it complete? Per bot thread: resolved?, did the author reply or
   fix (commit sha)? Counts: total / resolved / unresolved /
   unresolved-with-no-reply. Note commits pushed after the last bot review (a
   re-run may be due).
5. Human threads (non-bot, non-author): unresolved count and a one-line gist
   each.
6. Ball with: AUTHOR, REVIEWER (name), or READY TO MERGE.
7. Last activity and one line: what blocks merge.
8. Stacking: base is another PR's branch, or the description says it
   supersedes or follows another PR.

Hand the agent what keeps it from misreporting:

- The repo's known expected failures (checks that are red by design until
  some other change lands), if the user or the repo's CLAUDE.md / AGENTS.md
  lists them. Without such a list, every red check is real.
- How the repo's review bot reports "no findings" (some only flip a status
  check green and post nothing) and how a re-run is triggered, if known.
- The script's bucket and "why" for each PR, so it confirms or corrects them
  rather than starting from zero.
