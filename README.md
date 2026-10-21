# ammadeo/skills

My own agent workflows, packaged as [Agent Skills](https://agentskills.io):
plain folders with a `SKILL.md`, so they work in Claude Code and in any
other agent that reads the format.

| Skill | What it does |
| --- | --- |
| [`orchestrate`](skills/orchestrate/SKILL.md) | Lead a task that is too big for one agent: split by deliverable and dependency, brief strong-model subagents with disjoint ownership, integrate and verify from real diffs. |
| [`review-pr`](skills/review-pr/SKILL.md) | Review one PR or a batch of related PRs (a rollout across repos) with parallel read-only reviewers, report at behaviour level, post comment/approve reviews on request. |
| [`overseer-draft`](skills/overseer-draft/SKILL.md) | *Draft.* Oversee your open PRs and agent sessions: one-call status report grouped by who holds the ball, session triage, routing fixes to the owning session, reviewer proposals, merges you name. |

Requirements: [`gh`](https://cli.github.com) signed in, for `review-pr` and
`overseer-draft`. Subagent support helps but is optional; without it the
skills run the same steps sequentially.

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
```

## License

MIT
