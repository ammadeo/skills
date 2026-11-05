---
name: copywriting
description: Write or improve the words people read before they decide to act, directly in a codebase. Covers headlines, taglines, hero and landing page sections, button and CTA labels, product descriptions, onboarding and empty-state text, emails, ads and store listings, wherever those strings live (components, templates, locale files, content files). Use this skill when a task asks for copy to be written, rewritten, shortened or made more convincing, even if it only says "make this sound better", "punch this up", "this is too wordy" or "nobody clicks this", and whenever you are about to write marketing or product text yourself while building a page or feature. Not for technical documentation, long-form articles, legal text, commit messages or translation.
---

# Copywriting

Copy has one job: answer the reader's "why should I care, right now?" before
they look away.

You work unsupervised. Decide, apply the edit and move on: no questions, no
menus of options, no placeholders left in the code. Change the words only;
facts, layout and scope stay as they are.

## 1. Get the inputs

Find these in the repository before writing: README and docs, pricing and
plan config, the feature's code (what it really does, its limits and
timings), existing pages, changelogs, stored reviews or testimonials.

- **Reader**: who they are, how much attention they have (a glance, a skim, a
  read), and whether they already know they have the problem.
- **Shift**: what they believe now, and what they should believe or do after
  reading.
- **Facts**: numbers, names, timings, what the product replaces, phrases
  customers really use. Specific copy is made of these.

Use only facts you found. Never invent a statistic, testimonial, customer
name or guarantee. When a fact is missing, write the most specific line that
is still true without it. "Loved by teams everywhere" with no customer data →
"Built for teams that ship every week", not a made-up count.

## 2. Diagnose

Test every line in scope. Rewrite only what fails.

| Test | The line fails when |
| --- | --- |
| Glance | its meaning is not clear within two seconds |
| Gain | the reader cannot tell what they get |
| Picture | you cannot picture it: abstract nouns, stacked adjectives |
| Proof | nobody could check it and call it true or false |
| Swap | a competitor could put their logo under it unchanged |
| Cut | a word, sentence or block can go with nothing lost, or it repeats something already said |
| Voice | you would not say it out loud to a friend |
| Doubt | an obvious hesitation is left unanswered where the reader has to act |

## 3. Rewrite

1. **Lead with the reader's gain.** Say what changes for them, not what the
   thing is. "Scheduling engine with calendar sync" → "Never double-book a
   meeting again."
2. **Literal before clever.** A stranger must be able to say what it is and
   who it is for. Wordplay only once that holds.
3. **Climb down to something concrete.** Ask "meaning what?" of each abstract
   phrase until you reach a number, an object or a scene. "Save time on
   reporting" → "Your monthly report in 4 minutes."
4. **Make claims checkable.** Swap each adjective for the evidence behind it.
   "Reliable hosting" → "99.99% uptime, every outage published."
5. **Say what only this product can say.** Put the real difference first, and
   name what it replaces.
6. **One idea per line.** "And" in a headline is a warning: keep the stronger
   half.
7. **Cut until it breaks.** Remove each word, then each sentence; keep the cut
   when the meaning survives. Say each thing once. Drop hedges ("helps you",
   "aims to", "one of the").
8. **Verbs and outcomes on every action.** A button names what the reader gets
   or what happens next, and how big it is. "Submit" → "Send my quote".
   "Learn more" → "Take the 2-minute tour".
9. **Reassure where they hesitate.** One short line at the action that answers
   the main doubt: cost, time, commitment, reversibility. "No card needed."
   "You can change this later." Only if the code makes it true.
10. **Put proof beside the claim.** A count, a named customer or a result that
    exists in the repository, next to the line it backs.
11. **One person talking to one person.** "You", contractions, short active
    sentences, the customer's own words. Rephrase whatever you would not say
    aloud.
12. **Promise modestly.** A small believable claim beats a grand one. Let the
    facts persuade.
13. **Make it easy to keep reading.** The first line earns the second.
    Paragraphs of one or two lines. Paired items share grammar and length.

Shorter is not the goal by itself. Cut the padding around the specific
detail, never the detail.

For a headline, tagline or main CTA, draft five candidates, keep the one that
passes the most tests and apply only that one.

## 4. Apply

1. Edit the strings where they live. Keep keys, variables, markup and
   format placeholders (`{name}`, `%s`, plural forms) intact.
2. Stay in scope: only the copy the task covers. Do not sweep the codebase.
3. Search for the old string. Update tests, snapshots, selectors that match
   on text, `aria-label`s and docs that repeat it, and other screens that use
   the same term, so one thing keeps one name.
4. Translations: follow the project's i18n process. If locale files are kept
   by hand in the repository, update them to the new meaning.
5. Check the fit: button and nav widths, title and meta description lengths,
   any documented character limit.
6. Run the checks that cover the changed files.

## Gotchas

- **Your default phrasing is the failure.** The first wording that comes to
  mind is the one every other page already uses. Reject: unlock, elevate,
  empower, supercharge, seamless, effortless, powerful, robust, cutting-edge,
  game-changing, world-class, "take X to the next level", "in today's
  fast-paced world", generic "Tired of ...?" openers, adjective triplets and
  exclamation marks. Replace them with a fact from the repository.
- **Interface text is not an ad.** Settings, labels, buttons, errors, empty
  states and status text exist so the reader can predict what happens. Read
  `references/interface-text.md` before changing any of them and follow it
  instead of step 3. A shorter label that says less is a regression.
- **Copy must match behaviour.** "Free", "instant", "no card needed" and
  "cancel anytime" are claims about the code. Verify them there, and leave
  regulated or legal wording alone.
- **Keep the voice.** Match the tone and language of the copy around it; do
  not restyle the brand.
- **Fixes collide.** A cut can remove the specific detail or break a matched
  pair. Run the tests in step 2 again on the result.

## References

- Read `references/interface-text.md` before you touch text that describes a
  control or the app's state (settings, labels, buttons, errors, status).
- Read `references/techniques.md` when a headline, tagline or ad line is
  still flat after step 3, or when you write one from a blank page.
- Read `references/landing-page.md` when you write or review a whole landing
  page or its first screen.
