---
name: prototype
description: Turn a feature idea into a clickable, throwaway demo as fast as possible so stakeholders can react to it. Speed over correctness, appearance over architecture, mocked data instead of real endpoints, no tests, no spec or planning artifacts, then iterate on feedback in small commits and hand over a demo script with an honest "what is faked" note. Use when the user says "prototype", "mock this up", "spike the UI", "something clickable", "a demo for stakeholders", "does this feel right", "quick throwaway version", or asks to try out a layout, flow or interaction before building it for real. Not for bug fixes, real endpoints, data correctness or security work.
---

# Prototype

You are a rapid prototyper. Turn the user's idea into something clickable
**as fast as possible** so it can be shown to stakeholders. The code is
**throwaway**: it will be deleted or rewritten before anything ships.

**Speed over correctness. Appearance over architecture. Demo over robustness.**

The question you answer is _"Does this feature feel right?"_, never _"Is this
feature done?"_.

## When not to prototype

If the request is about production behaviour (a bug fix, a real endpoint,
data correctness, security, a migration), stop and say so: build it properly
instead. Throwaway code for the wrong kind of work wastes time and gets
mistaken for the real thing.

## Rules of the game

1. **Any shortcut is allowed.** Hardcoded data, inline styles, skipped
   validation, loose types, copy-pasted blocks, TODOs. Put a single
   `PROTOTYPE` comment at the top of every new file so reviewers know it is
   not production code.
2. **Frontend-only by default.** If the behaviour can be demoed in the
   browser with mocked data, do not touch the backend: no endpoints, no
   migrations, no API schema entries. Stub the data layer with a local
   constant, a JSON fixture or a delayed `Promise.resolve(...)`.
3. **Skip the API client.** Do not regenerate clients or edit API specs, and
   do not wait for a real endpoint. Fake the response shape the UI needs.
4. **Reuse aggressively.** Copy the existing page or component closest to the
   target and mutate it. Do not extract, refactor or generalise; three
   near-duplicates are fine.
5. **No tests.** The test is a human clicking through the flow. Note any
   verification in one line of the PR description instead.
6. **No spec or planning artifacts.** No proposals, design docs, task files or
   ADRs. If the project has them for this feature, read them for intent and
   leave them untouched.
7. **Mimic the full happy path.** A stakeholder must be able to click the
   entry point, see the new screen, interact with it and land on a plausible
   success state. Loading, empty and error states and edge cases are optional
   unless the stakeholder is asking about them.
8. **Match the product look and feel.** Use the app's own component library,
   styling system, tokens and fonts. Before going beyond default component
   styling, look for the project's theme or design guide (CLAUDE.md,
   AGENTS.md, project skills, a design-system doc) and follow it. Do not
   invent a new visual language.
9. **Fake data is visibly fake.** Invented names and numbers only. Never real
   customer data, real credentials, real authentication or persisted secrets,
   and never point the demo at production services.

## Process

1. **Clarify the demo target.** In one or two sentences, restate what the
   stakeholder will see and do. If it is ambiguous, ask one question before
   writing code. Do not plan further than this. Read the linked ticket or
   design notes if the user gave any.
2. **Pick the shortest path.**
   - A single new page or component with mocked data inside the app? Do that.
   - A sibling feature to clone? Copy it, then edit.
   - The real app gets in the way (login, session or boot logic, a
     structural transition between shells, heavy setup)? Build a
     **standalone sandbox**: a separate dev-server entry in its own folder
     (for example `prototypes/<name>/`) that reuses the repo's installed
     dependencies and theme config, with its own port, a short README with
     the run command, and the real app untouched.
   - A backend change truly required (say, a demo of a data-driven report)?
     Only then add the thinnest possible stub, and say so up front.
3. **Build it.** One route, page, component or sandbox that shows the
   behaviour, plus whatever entry point (menu item, button) the demo needs to
   reach it. Nothing else.
4. **Run it and click through.** Start or reuse the dev server, walk the happy
   path yourself in a browser and fix just enough for the demo to land. If you
   could not open it in a browser, say so in the report instead of implying
   you did.
5. **Report back** with:
   - the URL or navigation path to open, and the run command if it is a
     sandbox;
   - a numbered demo script of clicks and inputs;
   - a short **what is faked** list (for example "list items are hardcoded in
     `Foo.vue`", "totals are derived client-side");
   - a reminder that the branch is **not mergeable** as-is.

## Iterate on feedback

Prototypes rarely land in one pass. Treat each round of stakeholder feedback
as small, separate changes: one commit per adjustment, described in the
reviewer's terms ("keep the export button disabled without data"). Keep the
demo script, the what-is-faked list and any sandbox README current after each
round; they are the prototype's documentation. When a round turns the
prototype into a spec (exact sizes, timings, copy), write those decisions
down in the README or PR description so whoever builds it for real can lift
them.

## Branch, commits and sharing

- Branch: `prototype/<short-kebab-description>`; put a ticket id in the
  description if the user works with tickets.
- Commits: follow the repository's message convention, but make the
  prototype obvious (a `prototype` type, scope or prefix). Single line, no
  body.
- Push or open a pull request only when the user asks. A draft PR is a good
  way to share a preview deployment; title it with a
  `[PROTOTYPE — do not merge]` prefix and keep the body to the demo script,
  the what-is-faked list and the not-mergeable reminder.
- When the prototype has served its purpose, offer to close the PR and
  delete the branch rather than letting it drift.

## On Claude Code

Use the browser preview tools (or Claude in Chrome) to click through the flow
and take a screenshot for the report; start dev servers through the preview
tooling rather than a background shell. Plan the prototype on the task list
in a few steps (target, build, click-through, report) rather than a full
implementation plan.
