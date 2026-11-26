---
name: estimate
description: Estimate work in complexity (simple, moderate, complex), never in time. Use this skill whenever you are about to say how big, how hard or how long a piece of work is, asked or unasked, sizing a ticket, feature, bug, refactor or migration, estimating a backlog or roadmap, writing an effort or size line into a plan, ticket, PR description or status update, or answering "how long will this take", "is this a big change", "can we fit this in", "what's the effort", "size these tickets", "how many points". It replaces hours, days, sprints and points with one of three levels and the reason for it, gives each level a colour that still reads for colour-blind people, and proposes a split into vertical slices when something is complex. Not for measured or operational numbers such as how long a script runs, what something costs or how much data there is.
---

# Estimate

Work is estimated in **complexity, not time**. A time figure from an agent is
a guess that gets read as a promise. Complexity says what planning needs to
know: how much is unknown, how much has to move together, and whether the
thing should be one ticket at all.

This skill governs the estimates you give. It does not ask you to add
estimates where nobody wanted one.

## No time

Give no hours, days, weeks, sprints, person-days or dates for work, and no
disguised ones ("a quick afternoon job", "a couple of sprints"). No points or
T-shirt sizes either: the three levels are the whole scale. When the user
asks "how long", answer with the level and say in a few words that estimates
here are in complexity.

Durations that are facts stay: how long a script or migration runs, a
timeout, a deadline the user gave.

## The three levels

| Level | What it tends to look like |
| --- | --- |
| **simple** | Known goal, no moving parts, one system changes, ordinary release. |
| **moderate** | Known goal, a few risks at most, some moving parts, the size of a typical ticket. |
| **complex** | Known unknowns, a coordinated release, several systems affected. Usually it should be split. |

The rows give the feel of each level; they are not checklists. Weigh the item
as a whole and pick the level it most resembles. One trait from a higher row
does not lift it on its own: familiar work with a single open detail or one
new piece is usually still moderate. Call it complex when the unknowns or the
coordination are most of the work. If the goal itself is unclear, give no
level and name the question that has to be answered first.

Give the reason in those terms: what is unknown, what moves, which systems
change, how it releases. One line. If you judged from a description without
reading the code or ticket, say so.

## Writing it

One item: `🟡 moderate: <reason>`. Several items: a table with the columns
Item, Complexity, Why. The word is always there; colour is added to it and
never stands alone.

| Level | Plain text | Fill | Text on the fill |
| --- | --- | --- | --- |
| simple | 🟢 | `#90FAA8` | `#111111` |
| moderate | 🟡 | `#DBB800` | `#111111` |
| complex | 🔴 | `#B00C15` | `#FFFFFF` |

Use the emoji where only text is possible (chat, Markdown, tickets, Slack)
and the fills wherever you control colour (HTML, SVG, charts, label colours).
The fills get darker with each level in perceived lightness (OKLCH L 0.90,
0.79, 0.48) and keep that order under protanopia, deuteranopia and
tritanopia, so someone who cannot tell the hues apart still reads light, mid,
dark. That only holds if you:

- use them as fills (badge, cell, node, bar), not as text or thin lines: the
  green is too light to read on white;
- keep all three as given, rather than nudging one to match a theme;
- where a tool offers only preset colours, take its nearest green, yellow and
  red and let the word carry the meaning.

## Complex: propose a split

Right after a complex estimate, propose how to split it. Each part is a
**vertical slice**: it cuts through every layer it needs (interface, API,
data) and ends in something that can be released and checked on its own.
Cut along the work and what it delivers:

- by step of the user's journey, or by case (the main path first, the rarer
  cases after);
- by market, provider, customer group or data set, one at a time;
- by unknown: a small slice that answers the open question, then the build;
- by release step: ship dark behind a flag, migrate, switch over, remove the
  old path.

Never cut by layer or discipline. A "frontend" ticket and a "backend" ticket
deliver nothing until both are done, so the coordination that made the item
complex is still there, now hidden between two tickets.

For each slice give a name that says what it delivers, its own level and
reason, and what it depends on. Slices should come out simple or moderate; if
one is still complex, split it again or say why it cannot be cut further. If
the item has no sensible split (a single cutover, say), say that instead of
inventing one. It is a proposal: change no tickets until the user agrees.

```text
🔴 complex: Invoices move to the new billing provider. Two systems change,
both must run side by side during the switch, tax handling there is unknown.

Proposed split
1. 🟡 moderate: One test customer is invoiced through the new provider behind
   a flag. Answers the tax question. Depends on nothing.
2. 🟢 simple: New customers are invoiced through the new provider. After 1.
3. 🟡 moderate: Existing customers are moved over in batches, with a way
   back per batch. After 2.
4. 🟢 simple: The old provider's code and credentials are removed. After 3.
```

## Before you send

- No time unit, date, points or T-shirt size is attached to any work.
- Every estimate is one of the three words, with its reason.
- Every complex item has a proposed split or a reason there is none, and no
  slice is named after a layer or a team.
