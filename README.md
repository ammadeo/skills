# ammadeo/skills

My own agent workflows, packaged as [Agent Skills](https://agentskills.io):
plain folders with a `SKILL.md`, so they work in Claude Code and in any
other agent that reads the format.

| Skill | What it does |
| --- | --- |
| [`orchestrate`](skills/orchestrate/SKILL.md) | Splits a task too big for one agent across subagents, then integrates their work and verifies it against real diffs. |
| [`review-pr`](skills/review-pr/SKILL.md) | Reviews one PR or a batch of related PRs with parallel read-only reviewers; posts reviews to GitHub only on request. |
| [`overseer-draft`](skills/overseer-draft/SKILL.md) | *Draft.* Reports the state of all your open PRs and agent sessions, grouped by who has to act next. |
| [`prototype`](skills/prototype/SKILL.md) | Builds a clickable throwaway demo of a feature idea with mocked data, plus a note of what is faked. |
| [`copywriting`](skills/copywriting/SKILL.md) | Rewrites headlines, buttons, landing pages and UI text in place, using only facts it finds in the repo. |
| [`daily-update`](skills/daily-update/SKILL.md) | Posts an end-of-day Slack update built from today's PRs and tickets, only after you approve the exact text. |
| [`critical-change`](skills/critical-change/SKILL.md) | Runs a high-risk change to a live system as a gated plan, prepare and execute flow, and reverses only on your word; starts only when you ask for it. |

Requirements: [`gh`](https://cli.github.com) signed in, for `review-pr`,
`overseer-draft` and `daily-update`; a Slack connector for `daily-update`.
Subagent support helps but is optional; without it the skills run the same
steps sequentially.

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
skills/<name>/assets/            files the skill copies or reads as examples
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

[MIT](LICENSE)
