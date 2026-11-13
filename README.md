# ammadeo/skills

My own agent workflows, packaged as [Agent Skills](https://agentskills.io):
plain folders with a `SKILL.md`, so they work in Claude Code and in any
other agent that reads the format.

| Skill | What it does |
| --- | --- |
| [`orchestrate`](skills/orchestrate/SKILL.md) | Lead a task that is too big for one agent: split by deliverable and dependency, brief strong-model subagents with disjoint ownership, integrate and verify from real diffs. |
| [`review-pr`](skills/review-pr/SKILL.md) | Review one PR or a batch of related PRs (a rollout across repos) with parallel read-only reviewers, report at behaviour level, post comment/approve reviews on request. |
| [`overseer-draft`](skills/overseer-draft/SKILL.md) | *Draft.* Oversee your open PRs and agent sessions: one-call status report grouped by who holds the ball, session triage, routing fixes to the owning session, reviewer proposals, merges you name. |
| [`prototype`](skills/prototype/SKILL.md) | Turn an idea into a clickable throwaway demo fast: mocked data, no tests or specs, iterate on stakeholder feedback, hand over a demo script and a what-is-faked note. |
| [`copywriting`](skills/copywriting/SKILL.md) | Write or sharpen the words people read before they act (headlines, buttons, landing pages, emails, UI text): find what is long, vague or interchangeable, rewrite it specific and benefit-first from facts in the repo, and apply it in place without supervision. |
| [`daily-update`](skills/daily-update/SKILL.md) | Post your end-of-day update to Slack: today's PRs matched to their tickets, a product-level TLDR against the epics and roadmap, items grouped Waiting / In progress / Releasable / Released, sent as a one-line channel post plus a thread to the channel you last confirmed for that project, only after you approve the exact text. |
| [`architecture-visualise`](skills/architecture-visualise/SKILL.md) | See how a feature is put together without reading its code: hand-laid SVG diagrams of the units involved and how the answer travels between them, the pattern named in the picture and the weak spots marked on it. Compares two versions, such as main against a pull request, on the same grid with a table of what behaves differently. Suggests a better structure only when asked, as a view you can switch to. |

Requirements: [`gh`](https://cli.github.com) signed in, for `review-pr`,
`overseer-draft`, `daily-update` and pull-request comparisons in
`architecture-visualise`; a Slack connector for `daily-update`. Subagent
support helps but is optional; without it the skills run the same steps
sequentially. `architecture-visualise` builds and checks its page with
Python 3.

## Install

### Claude Code (plugin, skills appear as `ammadeo:<skill>`)

```text
/plugin marketplace add ammadeo/skills
/plugin install ammadeo@ammadeo
```

### Any agent (Claude Code, Codex, Cursor, OpenCode, ...)

```bash
npx skills add ammadeo/skills
```

### Manually

Copy a folder from `skills/` into your agent's skills directory, for example
`~/.claude/skills/` for Claude Code. Each skill is self-contained.

## Layout

```text
.claude-plugin/plugin.json       Claude Code plugin manifest
.claude-plugin/marketplace.json  makes this repo its own plugin marketplace
skills/<name>/SKILL.md           the skill (frontmatter: name, description)
skills/<name>/references/        extra docs the skill loads on demand
skills/<name>/scripts/           helper scripts the skill runs
skills/<name>/assets/            templates the skill fills in
evals/<name>/                    eval records for a skill (not loaded by agents)
```

## Credits

`copywriting` distils, in its own words, ideas from Harry Dry's
[Marketing Examples](https://marketingexamples.com/) and his
[copywriting masterclass](https://www.youtube.com/watch?v=TUMjnmfsPeM). Its
interface-text reference draws on the platform and UX-writing guidance
listed in [`evals/copywriting`](evals/copywriting/README.md), which also
records how the skill was evaluated.

## License

MIT
