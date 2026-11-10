# Suggesting a better structure

Read this only when the user asks for improvements. The page already marks
the weak spots; a suggestion answers "what would you do about them?".

## What to suggest

One suggestion per weak spot, the smallest change that removes it. Start from
the kind of weak spot:

| Weak spot | Usual remedy | Do not suggest it when |
| --- | --- | --- |
| Same decision made in more than one place | One unit owns the decision; the others read its result | The copies answer different questions that only look alike |
| A unit names every variant | A shared contract the variants implement, handed to the unit as a list or injected | There are two variants and no third in sight |
| State copied, or a flag passed along | One owner of the state; others ask it or observe it | The copy is a deliberate snapshot (a value captured at a moment) |
| Two paths that can disagree | One path; the second consumer reads the first path's answer | The paths serve different timing or threading needs |
| Something handled outside the pattern | Bring it in as one more case of the pattern | Its lifecycle really differs from the other cases |

Name the pattern in words a developer would use at a whiteboard ("one list of
sources behind a protocol"), with the textbook name in brackets if it helps
(strategy, observer, dependency injection). Say what it costs: which units
change, what becomes harder. If the honest answer is "leave it", say that:
three similar lines are not yet a pattern, and a variant nobody has asked
for is not a reason to build for it.

Stay inside the question. Suggest for the feature that was drawn, not for
the rest of the app, and do not write the code unless asked.

## How to show it

Add a second view to the figure the suggestion applies to (the last figure,
in a comparison), so the reader can flip between what is there and what it
could be:

```html
<figure data-view="now">
<div class="fighead">
<h2>master: two paths and a flag</h2>
<div class="views" role="group" aria-label="View">
<button aria-pressed="true" data-view="now">As it is</button>
<button aria-pressed="false" data-view="next">Suggested</button>
</div>
</div>
```

- Keep every unit that survives at its coordinates, unmarked.
- Mark what the suggestion removes `data-only="now"` and what it adds
  `data-only="next"` with the `add` tint. Arrows that change are written once
  per view.
- An element whose weak spot the suggestion removes is written once per
  view: with `data-warn` in `data-only="now"`, without it in
  `data-only="next"`.
- Each thing the suggestion adds carries `data-tip`: the change and what it
  costs, in one or two sentences.

Run `scripts/build.py` again; it checks each view separately. In your reply,
give the suggestions in two or three sentences and say they are a proposal,
not something the code does today.
