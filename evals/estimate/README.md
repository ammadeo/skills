# estimate skill: eval

An eval of [`skills/estimate`](../../skills/estimate/SKILL.md). This folder is
for maintainers. The skill does not reference it, shares no scenario with it,
and agents using the skill never see it.

## What it tests

Whether an agent asked to estimate work answers in complexity instead of
time, colours the levels as the skill says, and proposes a vertical split for
a complex item. Each case is one short prompt, with no codebase behind it.

| Case | The prompt | What a good run does |
| --- | --- | --- |
| `how-long-single-change` | "How long will it take" to add one button | Rates it simple with the reason, gives no time figure, says estimates are in complexity |
| `backlog-with-one-big-item` | Four tickets to estimate, one of them company SSO across three apps | Rates all four, calls SSO complex and proposes a split into parts that can each be released, none of them a frontend-only or backend-only ticket |
| `roadmap-page-html` | An HTML page of four roadmap candidates with estimates | Labels each in words, uses the three fills with lightness falling from simple to complex, splits the storage move |

## How it works

```text
cases/<name>/     prompt, expected outcome and one grader file per assertion
runs/<name>/      the replies and pages from the last round, with and without the skill
tools/palette.py  derives the three fills and checks their lightness order
```

The case folders follow the layout `claude plugin eval` reads.

## Run it

Start a fresh agent with the prompt from `cases/<name>/prompt.md` and tell it
there is no codebase to inspect. For the run with the skill, add the path of
`skills/estimate/SKILL.md`. For the baseline, add nothing. Save the reply,
and the page for `roadmap-page-html`, then grade each file in
`cases/<name>/graders/` against them by reading.

Two assertions can be checked without reading. Time figures:

```bash
grep -noiE '[0-9~–-]+ ?(minutes?|hours?|days?|weeks?|sprints?|months?|points?)\b' answer.md
```

And the palette, which exits 1 if lightness does not fall from simple to
moderate to complex under normal vision, protanopia, deuteranopia and
tritanopia:

```bash
python3 evals/estimate/tools/palette.py
```

## The palette

The fills were picked in OKLCH, where L is perceived lightness, and
simulated for the three kinds of colour blindness with the matrices of
Machado et al. (2009) at full severity.

| Level | Fill | L | Protanopia | Deuteranopia | Tritanopia |
| --- | --- | --- | --- | --- | --- |
| simple | `#90FAA8` | 0.90 | 0.94 | 0.90 | 0.90 |
| moderate | `#DBB800` | 0.79 | 0.77 | 0.80 | 0.80 |
| complex | `#B00C15` | 0.48 | 0.38 | 0.50 | 0.51 |

The yellow is a gold. A bright yellow is lighter than any green, so it could
not sit between the other two.

## Round 2 (2026-11-26)

All three cases, one run per configuration, on Claude Fable 5.2, graded by
reading the outputs.

| Case | With the skill | Without |
| --- | --- | --- |
| `how-long-single-change` | 4 of 4 | 0 of 4 |
| `backlog-with-one-big-item` | 7 of 7 | 2 of 7 |
| `roadmap-page-html` | 6 of 6 | 1 of 6 |
| All assertions | 17 of 17 | 3 of 17 |
| Tokens per run | 76k to 84k | 68k to 75k |
| Time per run | 12 s to 1 min 23 s | 13 s to 1 min 47 s |

- **Every run without the skill answered in time.** "5–10 minutes", "under
  1 hour", "3–5 weeks of effort", "18–34 engineer-days". None used the three
  levels, and the roadmap page added Small, Medium and Large.
- **Without the skill the big item got a spike, not a split.** The SSO
  ticket was answered with a "2–3 day spike" that would produce the
  breakdown later. With the skill it was split into steps a customer can
  use: a pilot customer on the web app, then the iOS app, then the admin
  panel.
- **The page used the fills as given.** All three as badge backgrounds with
  the stated text colours, untouched by the page's dark theme, each badge
  carrying the word.
- **Three assertions pass without the skill and tell little:** "no layer
  split" and "the split is a proposal" in the backlog case, and "word beside
  colour" in the roadmap case, which holds for a page with no level colours
  at all.

One run per configuration shows direction, not variance.

## Round 1 (2026-11-26)

The same cases against the first draft, which said that one trait from a
higher level lifts the whole item. With the skill 17 of 17, without 3 of 17.
The weekly digest in `roadmap-page-html` came out complex because the app had
no scheduled jobs yet, and was split into three. The rule was loosened: the
rows describe the feel of a level and the item is weighed as a whole. In
round 2 the digest came out moderate, and the SSO ticket and the storage move
stayed complex. Round 2 reran the backlog and roadmap cases with the skill;
the other runs are carried over.
