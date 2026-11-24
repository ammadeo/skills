---
name: architecture-visualise
description: Draw how a feature or part of a codebase is put together as hand-laid SVG diagrams on one page, so a developer can see its structure, the pattern in use and its weak spots without reading the code. Use this skill when the user wants to see, map, diagram or visualise how something is wired, structured or composed; asks where a piece of logic lives, whether it is duplicated, or how the parts of a feature fit together; or wants to compare the structure before and after a pull request, branch or refactor, even if they never say "architecture" or "diagram" and only want to understand a feature before changing it. Two versions are drawn on the same grid, with a table of what behaves differently. It marks weak spots and stops there; it proposes a better design only when asked. Not for debugging a failing behaviour, for database schemas or UI mockups, or for designing a system that does not exist yet.
---

# Architecture visualise

A structure debugger. The reader is a developer who does not know this code
and does not want to. They will look at the diagram and, in a comparison, at
one table. They will skip almost everything else. So the diagram has to
carry the whole answer by itself:

- **the structure**: which units take part and how the answer travels
  between them;
- **the pattern**: named in plain words where the eye lands first ("two
  paths and a flag", "one list, one answer");
- **the weak spots**: marked on the drawing at the place where they are,
  each with a "?" the reader hovers or taps to see why.

You read the code so they do not have to. Two things decide whether the
page is usable, in this order:

1. **Nothing important is missing from the picture.** A tidy diagram that
   drops a rule, a flag or one of the ways the behaviour starts is useless to
   someone who will not open the code to find it.
2. **The picture is clear.** Only once it is complete.

## 1. Fix the question

Restate it in one sentence: which behaviour, and which version or versions.
The user names a behaviour ("pausing breaks"), not files; finding the files
is your job. If two readings are plausible, take the narrower one. Ask only
when you cannot tell which repository or which versions are meant.

Pin every version to a commit before reading anything:

- "current", "latest main/master": fetch, then use the remote tip of the
  default branch. The local checkout may be behind or dirty.
- A pull request: `gh pr view <n> --json title,state,isDraft,baseRefName,headRefOid,mergeCommit,files`,
  then `git fetch origin pull/<n>/head`.
- A pull request that is already merged: the branch tip now contains it, so
  "main vs the PR" would show nothing. Compare the commit just before it
  (`git rev-parse <mergeCommit>^1`) with the PR, and say so in the refs line.
- Read other versions without touching the user's checkout: `git show <sha>:<path>`,
  `git grep -n <pattern> <sha> -- <dir>`, or a detached worktree in a scratch
  directory that you remove afterwards. Never switch branches, stash or reset
  in their working tree.

## 2. Read the code

Start at the two ends of the behaviour: what sets it off (a user action, a
timer, an OS or network event) and where its effect shows (UI, a
notification, stored state). Search for the behaviour's own words, then
follow references both ways until you reach units that have nothing to do
with the question. Stop there.

Come away with five things, kept in your notes and not in files:

- **Units.** The classes, services, stores and outside systems the behaviour
  runs through, each with its path and its job in a few plain words.
- **Rules.** The facts that decide the outcome, each tied to the unit that
  applies it: timings and defaults ("held until the meeting ends plus 60 s",
  "asked again every 30 s"), orders of precedence, what wins a tie, what a
  flag means and when it is cleared, every separate way the behaviour can
  start.
- **The flow.** How the answer gets from where it starts to where it shows:
  who hands what to whom. Only what you saw in the code; an arrow you assume
  is an arrow that misleads.
- **Weak spots.** Places where the structure works against whoever changes it
  next. Look for these five, and check each one is real before you mark it:
  1. the same decision made in more than one place (the same condition
     derived again, the same answer rebuilt from copied state);
  2. a unit that names every variant (a `switch` over the kinds, a type check
     per implementation), so it must be edited whenever one is added;
  3. state that is copied, or a flag passed along through several units;
  4. two paths to the same effect that can disagree;
  5. something handled outside the pattern everything else follows.

  Code that looks alike but decides different things is not a weak spot.
  Leave it unmarked.
- **Situations** (comparisons only). The moments a user or developer would
  recognise ("camera on", "just after a call", "settings saved while
  stopped") and what each version does in them. Read these from the code,
  the diff, the tests and the pull request text.

For a large comparison, tracing each version can go to a read-only subagent
that returns these lists with `path:line`. Draw the diagrams yourself.

## 3. Draw

Read [references/diagram.md](references/diagram.md) and
[assets/example.html](assets/example.html) once before drawing: the first has
the grid, the marks and the measurements, the second is a complete page to
copy the markup from. What matters most:

- **Everything on your lists is in the picture.** Every way the behaviour
  starts, every unit that decides, every rule, every flag or copy of state,
  every place the effect shows. Leave out only wiring and helpers that have
  nothing to do with the question. Before you build, tick your units, rules
  and weak spots off against the drawing: one that is missing is a defect.
- **Rules go inside the boxes.** Under a unit's name, up to three short lines
  for what it applies: `meeting end + grace`, `asked again every 30 s`,
  `stopped, then meeting, then devices`. Arrows carry what travels.
- **When it does not fit, add a figure; never cut.** Up to about twelve boxes
  in the main figure, laid out left to right: what starts it, where it is
  decided, where it shows. A unit with more inside it than three lines (a
  loop, an order of precedence, a timeline) gets a small zoom figure of its
  own under the main one.
- **Name things for a stranger.** A box leads with what it is in plain words
  when the code name would not tell them ("Menu-bar icon"), with the code
  name small beneath it. Arrows are labelled with what travels along them.
- **Say the pattern in the picture.** The figure heading names it in a few
  plain words, lane labels name each path, and a dashed group with a caption
  shows what several units have in common ("all three are a PauseSource").
- **Mark weak spots where they are, with the why on hover.** Put
  `data-warn="…"` on the box, group or arrow where a weak spot is best seen.
  The page draws an amber "?" there and shows the text on hover, focus or
  tap. One per weak spot; name the other places it touches in the text. In
  a comparison, a weak spot that both versions have is marked in both.
  `data-tip="…"` does the same with a grey "?" for background that helps but
  is not needed to read the picture.
- **Hover text explains; it never carries the structure.** Every unit, rule
  and flag is readable without hovering. A rule that only shows in a tooltip
  counts as missing.
- **In a comparison, the same unit sits at the same coordinates in both
  diagrams.** Draw the units both versions share once and reuse them in the
  second figure. A unit that is gone leaves a gap. Tint what the second
  version removes in the first diagram and what it adds in the second. The
  reader flips between the two and sees only the change move.

Plan the grid before you write: list each unit with its column, row and box
size, check the longest label against the width table, then write the SVG
once.

## 4. Write the page body

Write one file, the page body, shaped like `assets/example.html`. The build
step adds the styles, arrowheads and the view switch, so do not write CSS or
scripts and do not open `assets/head.html`. The body has exactly these
parts:

1. **Title, one line of refs and the legend**: repository, versions and
   short commits.
2. **One figure per version**: a heading that names the pattern, the
   diagram, a caption of at most two sentences with the claim in bold first,
   and nothing under it. Zoom figures, when a unit needs one, follow the
   figure they belong to.
3. **The same situations in both versions** (comparisons only): a table with
   one row per situation and one column per version; mark rows that differ
   `class="diff"`. Include every situation that differs and two or three that
   do not, so the reader sees what stayed the same.
4. **Sources**, collapsed: one line per unit, starting with its `data-unit`
   name exactly, then a link to `path#Lline` at the pinned commit for every
   version it exists in. Link the line where the unit is declared; the build
   looks for the name there. End with what you did not trace and whether
   anything was run.

Nothing else. No summary paragraph, no rule tables, no review notes, no list
of changes: if it matters, it belongs in a diagram or the table. A
single-version page uses no tints and no shared group, its legend keeps only
the "?" entries, and its source links are labelled with the branch name.

A weak spot's hover text states what is there and what it costs, in one or
two plain sentences and under 240 characters: "The scheduler and the menu each work out whether
breaks are paused, from different inputs, so they can disagree." It does not
say what to do about it. Advice is a separate job; see section 6.

Write for someone who has not read the code and will not. No sentence should
need a file open to make sense.

## 5. Build, check and hand over

```bash
python3 scripts/build.py <body.html> -o <page.html> --repo <path to the checkout>
```

This is the whole validation, and it needs no browser. It checks the
drawing by geometry (labels that leave their box or collide, boxes that
overlap, arrows that float or cut through a box or a label, units that moved
between figures, "?" icons that cover a label or sit on a reused unit) and checks every source link against git (the file
exists at that commit and the unit's name is at that line). It writes the
page only when nothing fails. Fix what it lists and run it again.

The build cannot tell whether the picture is complete or true. That check is
yours, and it comes first: go down your units, rules and weak spots once
more and confirm each is drawn and each claim matches what you read.

Work in one pass: read, plan, write the body once, build, publish. Do not
open the page in a browser, take screenshots or render it some other way to
look at it, and do not reread files you have already read. The build
output is the evidence that the page is right.

Reply with the link and two sentences: the pattern, and the weak spots or
what changed. Do not paste the diagram into the chat.

This skill reads and reports. Do not edit the code you are mapping, and do
not comment on the pull request.

## 6. Suggestions, only when asked

Do not propose a different design unless the user asks for one ("how would
you improve this?", "what would you change?", "suggest a better structure").
When they do, read [references/suggestions.md](references/suggestions.md):
it covers what to suggest and how to add it to the figure as a second view
the reader can switch to. Until then the page marks weak spots and stops.

## On Claude Code

Publish the built page with the Artifact tool (icon `diagram`, a
one-sentence description of what the page shows). The built page already
follows the artifact page contract, both themes included, so this skill
needs no page-design guidance and no preview; load that guidance only if the
tool refuses to publish without it, and change nothing. Use `gh` for pull
requests and a scratch directory for the body file and any worktree.

In an agent without artifacts, hand over the built `.html` file where the
user can open it.
