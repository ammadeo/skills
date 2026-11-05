# copywriting skill: eval record

Results of evaluating [`skills/copywriting`](../../skills/copywriting/SKILL.md).
This folder is a record for maintainers. The skill does not reference it and
agents using the skill do not need it.

## Round 2 (2026-11-05)

Six fresh agent instances, same model and effort, each in its own detached
worktree of [ammadeo/save-my-eyes](https://github.com/ammadeo/save-my-eyes)
at `e82f144`. Three got the prompt in [`task.md`](task.md) as is. Three got
the same prompt plus the skill, loaded by reading its files. Each instance
did three tasks: rewrite the Settings labels, rewrite the long-break ideas,
write a headline.

| | Without the skill | With the skill |
| --- | --- | --- |
| Delay slider label still names what it acts on | 0 of 3 | 3 of 3 |
| Settings strings changed per run | 16 to 17 | 10 to 13 |
| Non-label text reworded per run | 3 to 4 | 1 |
| Fixed the "short break every" inaccuracy | 3 of 3 | 1 of 3 |
| Sound switch label kept its verb | 1 of 3 | 3 of 3 |
| Long-break ideas kept the no-period style | 0 of 3 | 3 of 3 |
| Tests, as each run reported | 90 pass | 90 pass |

The label that prompted the interface-text reference, "Pause breaks after a
call ends":

| Run | Rewrite | At zero |
| --- | --- | --- |
| Without 1 | Wait after a meeting or call ends | No wait |
| Without 2 | Wait after a meeting or call | No wait |
| Without 3 | Delay after a meeting or call | None |
| With 1 | Delay the break after a meeting or call | No delay |
| With 2 | Hold breaks after a meeting or call ends | Off |
| With 3 | Hold breaks after a meeting or call ends | Off |

Headlines:

| Run | Headline |
| --- | --- |
| Without 1 | Every 20 minutes, a 20-second break for your eyes. |
| Without 2 | A break for your eyes every 20 minutes, never in the middle of a call. |
| Without 3 | Every so often, your Mac covers the screen so your eyes can rest. |
| With 1 | Every 20 minutes, your Mac covers the screen for 20 seconds so you actually look away. |
| With 2 | Every 20 minutes, your screen covers itself for 20 seconds so your eyes can rest. |
| With 3 | Every 20 minutes, your Mac covers the screen so your eyes can rest. |

### Caveats

- Three runs per arm shows a pattern, not a measurement.
- Two of the three baseline runs invoked an installed `design:ux-copy` skill
  on their own, so the baseline is "without this skill", not "without any".
- The interface-text reference was written against the round-one failure on
  the delay slider, with an invented example from another domain. The result
  shows the fix works there, not that it generalises.
- Each instance did all three tasks in one go, so tasks may have influenced
  each other.
- The kept/lost judgements in `annotations.json` are the evaluator's.

### Known gap

The skill arm was worse at spotting that "Take a short break every" is
inaccurate (the value is the gap before every break). A likely fix is to
require the truth sentence for every control in scope, including the ones
the agent plans to leave alone.

## Round 1 (2026-11-05)

One run per arm on the Settings labels only, at `a8df0b7`, before the
interface-text reference existed. Both arms produced nearly the same labels,
and both turned the delay slider into a vague noun phrase ("Extra time after
a meeting", "Wait after a meeting"). That failure is why round 2 exists.

## Files

```text
task.md            the prompt every instance received (paths replaced)
strings.json       every bilingual string per run, plus master
annotations.json   names, notes and judgements used by the report
patches/           git diff of each worktree against master
report.html        the generated comparison page (body fragment)
tools/extract.py   builds strings.json from the worktrees
tools/build_page.py, tools/page.css.html   build report.html
```

Rebuild the report:

```bash
python3 tools/build_page.py . report.html
```

## Research behind `references/interface-text.md`

Read for the reference, then rewritten in the skill's own words:

- Apple Human Interface Guidelines (writing, toggles, sliders, settings,
  alerts, menus) and the WWDC writing sessions' transcripts
- Material Design 3 content design and the Android settings guidelines
- Microsoft Windows writing style and the Win32 UX text guidelines
- GNOME and KDE human interface guidelines
- Shopify Polaris, Atlassian and IBM Carbon content guidelines
- Nielsen Norman Group articles on toggles, checkboxes, UI copy, microcopy,
  error messages and scanning
- GOV.UK Design System and service manual, plainlanguage.gov
- Mailchimp and Intuit content style guides
