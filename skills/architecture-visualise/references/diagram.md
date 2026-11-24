# Drawing the diagram

Hand-written inline SVG, styled by the classes in `assets/head.html`. The
worked page in `assets/example.html` shows every mark in use; copy its
markup. Write final coordinates: no `transform`, no `<style>`, no `<defs>`
(arrowheads come from the page).

## Grid

- `viewBox="0 0 1000 H"`. Pick H to fit, leaving 16px free at every edge.
- Three to five columns, read left to right: what starts it, where it is
  decided, where it shows. With three columns, boxes are about 212 wide with
  180 between them; with four, about 180 wide with 80 between; with five,
  about 160 wide with 42 between.
- An arrow label needs 6.6 per character plus 16 of gap. When the gap is
  narrower, shorten the label to one word or move the detail into a box. An
  arrow shorter than 50 may go without a label.
- A box is 58 tall with a name and one line, and 16 taller for each extra
  line (74, 90, 106). Leave at least 22 between boxes in a column, so an
  arrow label fits between rows.
- Two paths fed by the same sources (one that acts, one that reports) are two
  lanes: stack them, give each a `lane` label, and put the shared sources in
  the first column spanning both.
- Decide every unit's x and y once. In a comparison both figures use the same
  coordinates for the same unit; a unit that is gone leaves its slot empty.

## Marks

| Mark | Markup | Use |
| --- | --- | --- |
| Unit | `<rect class="n" data-unit="Scheduler" x y width height/>` | One class, service, view or store. `data-unit` is its name in the code |
| Outside system | `<rect class="n ext" …/>` | OS API, server, SDK. Needs no `data-unit` and no source |
| Inner box | `<rect class="n in" …/>` | A flag, a piece of state or a nested type held inside a unit. Give it `data-unit` and a source when it is a named thing in the code |
| Group | `<rect class="grp" …/>` with a `cap` label above it | Units that share a contract or role: "all three are a PauseSource" |
| Arrow | `<path class="e" d="M212 69H372"/>` | The way the answer travels. Only `M L H V`, absolute. Starts and ends exactly on a box or group edge; a group's edge means "each of these", and an arrow may cross a group's border to reach one box inside. Two bends at most (`H V H`) |
| Dashed arrow | `class="e dash"` | A side route that bypasses the pattern |
| Weak spot | `data-warn="what is there and what it costs"` on a unit, group or arrow | The page adds an amber "?" at the box's top-right corner, or 18px along the arrow, and shows the text on hover, focus or tap |
| More detail | `data-tip="…"` on a unit, group or arrow | The same with a grey "?". For background only; rules stay visible in the box |

Tint with a second class: `gone` (removed by the second version, drawn in the
first figure) or `add` (new in the second version, drawn in the second). It
works on `n`, `grp` and `e`. Untinted means in both. A single-version page
uses no tints.

## Text

Every `<text>` takes one class. Widths are per character, so you can check a
label fits before writing it: the box's width minus 24.

| Class | Use | Size | Width per character |
| --- | --- | --- | --- |
| `t` | Unit name as in the code | 13 mono | 7.8 |
| `tp` | Unit name in plain words | 13 sans | 7.3 |
| `s` | Its job, and each rule it applies, one per line | 11.5 sans | 6.2 |
| `ms` | Code name under a plain name | 10.5 mono | 6.3 |
| `m` | Arrow label: what travels | 11 mono | 6.6 |
| `cap` | Group caption, small note | 11.5 sans | 6 |
| `lane` | Lane label, shown in capitals | 10.5 sans | 7.2 |

- In a box at `x y`: name at `x+12, y+24`, second line at `x+12, y+42`,
  further lines every 16.
- Label on a horizontal arrow: centred on it with `text-anchor="middle"`, 8
  above the line. On a vertical arrow: beside it, starting 8 to its right.
  Group caption: 10 above the group. Lane label: 10 above the lane's first
  box; when both land in the same place, the lane label goes one line higher.
  Type lane labels normally; the page shows them in capitals.
- `data-unit` is the bare name as declared in the code (`Scheduler`,
  `pauseProtection`), with no owner prefix, brackets or description.
- Lead with a plain name (`tp`) and put the code name beneath (`ms`) when the
  code name would not tell a stranger what the unit is. Otherwise the code
  name (`t`) with its job beneath (`s`).
- Labels never touch a box they do not belong to, another label, or an arrow.
- A "?" is a circle of radius 9. Keep 10px clear around it: no label at the
  top-right corner of a box that carries one, and none on the first 30px of
  an arrow that carries one.
- Hover text is plain text in the attribute, under 240 characters: no tags,
  `&amp;` for &, and `&quot;` for a double quote.
- An inner box is 44 tall, sits 12 in from its unit's sides, and takes a name
  (`t` or `ms`) at `y+18` and one line (`s`) at `y+34`.

## Sharing units between two figures

Wrap the units both versions share, with their text, in `<g id="both">` in
the first figure, and start the second figure's SVG with `<use href="#both"/>`.
They are then drawn once and cannot drift. Tinted units, arrows, groups,
anything with hover text (a reused unit cannot be hovered) and anything
whose text or size differs between versions stay outside
the group and are written per figure, at the same `x y`. A unit that is
renamed or rebuilt in the same slot is `gone` in the first figure and `add`
in the second. A group may grow or shrink between figures.

## Zoom figures

`<figure class="zoom">` after the figure it belongs to, with a heading that
starts "Zoom:" and names the unit. Use it for what does not fit in three
lines inside a box: the steps of a loop, an order of precedence, a timeline.
Its boxes are steps or states, need no `data-unit`, and may sit anywhere.

## A second view on one figure

A figure can hold two views that the reader switches between. Mark the
figure `data-view="now"`, put the switch from `references/suggestions.md` in
its heading row, and mark anything that belongs to one view only with
`data-only="now"` or `data-only="next"` (on the element or on a `<g>` around
several). Unmarked elements show in both. Used for a suggested design, where
the reader toggles between what is there and what it could be.
