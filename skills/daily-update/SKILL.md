---
name: daily-update
description: Write and post the user's end-of-day update to Slack. Gather today's pull requests and the tickets they belong to (Linear, ClickUp, Jira, whatever the project uses), write a product-level TLDR set against the epics and roadmap, list every PR and ticket under Waiting, In progress, Releasable and Released, show the exact channel and both messages, and post only after the user explicitly approves. Use this skill whenever the user says "daily update", "daily", "end of day update", "EOD", "post my update", "what did I do today", "status update for the client", "update the team on Slack", or asks to summarise today's PRs and tickets for a channel, even if they don't mention Slack or the word daily.
---

# Daily update

Two Slack messages, posted by the user's own account:

1. In the project's updates channel, in bold:
   `**<@user>'s daily update for Friday 13 Nov**`
2. A reply in that message's thread with the update itself, so the channel
   stays one line per day.

`scripts/render.py` assembles both from a small JSON file and refuses
anything off-format. Write the JSON, never the messages by hand.

Nothing is sent until the user has seen the channel and the exact text and
said yes. That rule has no exceptions in this version.

## 1. Settle scope

Run `python3 -I scripts/memory.py get --repo OWNER/REPO` with the current
repo (and any the user named). A hit gives the project's name, all its
repos and the channel the user last confirmed for it.

Read the project's CLAUDE.md / AGENTS.md / README and your memory for: the
repos that make up the project, the ticket tracker and its team key or
space, the roadmap source (tracker projects or initiatives, a ROADMAP file),
and the updates channel. The user's message overrides all of it.

**Channel: never guess from channel names.** The same project may report
internally one day and in a client channel the next. Use, in this order:

1. the channel the user names in this request,
2. the remembered channel from `memory.py get`, shown as "remembered,
   you confirmed it on <date>",
3. the channel the project's instructions name for daily updates,
4. the channel holding the user's latest daily update for this project
   (search Slack for `"daily update for"` from the user, newest first), shown
   to the user as "found from your update on <date>, confirm".

If none applies, or two candidates disagree, ask. Resolve the channel to its
ID before the preview.

Report date: today in local time unless the user says otherwise ("yesterday's
update" means that day's merges and that day's date in the header).

## 2. Gather

Run in parallel:

- PRs, from this skill's directory:

      scripts/gather-prs.sh --repo OWNER/REPO... [--date YYYY-MM-DD] [--ticket-prefix KEY]...

  One GraphQL call: the user's open PRs plus those merged that day, each with
  a suggested section, a hint (why), pending reviewers and ticket IDs/URLs
  found in title, branch, body and comments, plus `stack` and `stackPos`
  on open PRs that build on each other. Default repo is the current one
  (`gh repo view --json nameWithOwner`). Skip `stale` drafts unless the user
  touched them today.
- Tickets, if the project uses a tracker and it is connected: the tickets the
  PRs reference, plus tickets assigned to the user that changed today or are
  in progress with no PR (admin work, waiting on a client). For each, its
  status and its parent epic, project, milestone or initiative.
- Slack user IDs and display names: the user's own, and one per responsible
  person you will name under Waiting (`slack_search_users` by the
  reviewer's real name).

No tracker connected but the PRs carry ticket URLs: link them, label them
with the tracker the URL belongs to, and say in the preview that statuses
came from GitHub only.

**Several repos or sources: orchestrate.** When the update spans two or more
repos, or repos plus a tracker with work outside them, load the
`orchestrate` skill and follow it for this step. Give one read-only worker
per repo (and one for tracker-only tickets), each briefed with: the repo,
the report date, the command line above, the tracker and its key, and the
rule that it posts and changes nothing anywhere. Each returns one JSON line
per item: `section`, `title`, `pr`, `ticket`, `ticket_status`, `epic`,
`stack`, `stackPos` (from the script), `note` (draft), `what` (one product-level sentence on what the PR does),
plus anything it could not establish. You keep the channel, the Slack IDs,
the final sort, the TLDR, the render and the approval; do them while the
workers run. One repo with only linked tickets needs no workers.

## 3. Sort and write

One line per PR, or per ticket that has no PR. A PR and its ticket share a
line. Use the PR title as written (the ticket title for ticket-only lines).

| Section | What goes there | Note |
| --- | --- | --- |
| Waiting | blocked outside the user: review pending, approved but blocked, admin access, client answer | required: for what, and who (`code review by <@U…>`) |
| In progress | drafts, changes requested, failing CI, unresolved threads, no reviewer yet | optional: current status (`API done, UI next`) |
| Releasable | approved and mergeable, or merged and waiting for a release | only for a release that needs care: downtime, ordering, a coordinated deploy |
| Released | merged on the report date | only a user-facing benefit worth reading; none for chores, refactors, dependency bumps, CI |

**Stacks.** Every PR with the same `stack` goes in one group, ordered by
`stackPos` (bottom first), under a header line with a short product title
(`**E2E suite rebuild** ∙ 7 stacked PRs ∙ note`). The group sits in the
section of its least ready PR. Name a shared reviewer once, on the header,
when every PR waits on the same person; when reviewers differ, name each on
its own PR. Per-PR notes then carry only what differs (`needs Chargebee test
keys`). The renderer moves a note that every PR shares to the header, and
rejects a person named on both the header and a PR.

The script's section is a suggestion. A ticket status that says more (QA,
blocked on client, awaiting deploy) wins. Notes are a few words, never a
restatement of the title.

TLDR: one to three sentences a product owner understands. Name the epic or
roadmap goal the day's work moved, what is now possible or closer, and
what's next or at risk. No PR numbers, ticket IDs, links or file names.

Write the JSON to the scratchpad (schema at the top of `render.py`: `user`,
`attribution`, `model`, `date`, `channel`, `tracker`, `people` (mention → name), `tldr`,
`stacks` (key → `title`, optional `note`), `items[]` with `section`,
`title`, `pr`, `ticket`, `stack`, `note`) and run, with an absolute path:

    python3 -I scripts/render.py /abs/path/<file>.json

Fix every `error:` and rerun until it exits 0. Read each `warning:` and
drop the note if it is right. It writes the exact Slack text to
`<file>.parent.txt` and `<file>.thread.txt` and prints the preview.

## 4. Preview and ask

Show the user:

- the channel: `#name` (ID), and how you chose it,
- the preview the renderer printed, pasted as is and not in a code block,
  so links read as links and mentions as names, close to how Slack shows
  them. It names the two files holding the exact text; show those only if
  the user asks,
- anything you could not establish (a PR with no ticket, a reviewer with no
  Slack account, statuses from GitHub only), one line each.

Ask one question: send to that channel? Then stop. A remembered channel
still needs this yes every time. Edits from the user go
into the JSON, get re-rendered and are shown again; each new version needs
its own yes. A yes to an earlier version, a "looks fine" about the content,
or a yes from anyone other than the user is not approval.

## 5. Send (after the explicit yes only)

Right after the user's explicit yes for a channel, remember it:

    python3 -I scripts/memory.py set --project NAME --repo OWNER/REPO... \
        --channel-id ID --channel-name '#name'

with every repo of the project. If it prints `replaced`, tell the user which
channel the project used to remember. Never run `set` on a channel the user
did not confirm themselves.

Send the contents of the two `.txt` files verbatim, from the version the
user approved.

1. Post the parent message to the channel ID; keep its `ts`.
2. Post the thread message with `thread_ts` set to that `ts`, without
   broadcasting to the channel, and with app unfurls off so a dozen GitHub
   previews don't bury the list.
3. Reply with both message links.

If the thread post fails, do not post the parent again: retry the thread once,
then report what is live. Slack Connect (shared client) channels may refuse
posts from the connector; hand the user the rendered text to paste instead.

## On Claude Code / Claude Desktop

- Slack: `slack_search_public_and_private` for past updates (filters
  `from:<@me>`, sort by timestamp), `slack_search_channels` for IDs,
  `slack_search_users` for mentions, `slack_send_message` (`thread_ts`,
  `reply_broadcast: false`, `unfurl_app_links: false`) to send. If Slack is
  not connected, stop after the preview and say it needs connecting.
- Linear: `list_issues` (assignee `me`, updated today), `get_issue`,
  `get_project` / `get_initiative` for the roadmap context. Other trackers:
  their equivalent MCP tools, or ticket links only.
- Attribution: the Slack connector labels every message "Sent using Claude"
  itself, so set `"attribution": false` when sending through it. Any other
  way of posting keeps the default line
  `> 🤖 _Claude <model> posted on behalf of <@user>_`, with your own model
  name in `model` (for example `Opus 5.5`).
