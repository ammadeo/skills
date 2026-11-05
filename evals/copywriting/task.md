You have three small copy tasks on Save My Eyes. Do all three.

## About the app
Save My Eyes is a free macOS menu-bar app (Swift, SwiftUI) for people who work at a computer for long stretches. On a timer it covers the screens for a short break so the user looks away from the display, and every few rounds the break is a long one. A small card warns before a break, and the user can wait, skip it or start it. Breaks are held while a calendar meeting or a call is in progress. Protection can be stopped for a few hours. The interface text is in English and Polish.

That description is deliberately general. Read the Swift sources under `SaveMyEyes/` to learn what the app and each control really do. Do not read README.md, PRODUCT.md, DESIGN.md or docs/: the copy has to come from what the code does, not from earlier wording.

## Tasks
1. **Settings labels.** Rewrite the labels of the Settings screen (the Settings pane of the menu-bar popover).
2. **Long-break ideas.** Rewrite the ideas the app shows during a long break (their titles and descriptions).
3. **Headline.** Write one headline for Save My Eyes: the line that would sit at the top of its website. Write it alone, on a single line, in English, to a new file `HEADLINE.txt` in the worktree root. Do not edit README.md.

## Where to work
Your working directory is this git worktree (detached HEAD at the latest master). Run every command from it and use absolute paths under it:

<path to this instance's worktree>

## Boundaries
- Edit files only inside that worktree. Do not read from, write to or run anything in the main checkout at <path to the main save-my-eyes checkout> or any other worktree or directory.
- Do not commit, stash, push, switch branches or create worktrees. Leave your changes as uncommitted edits in the working tree.
- You may run `make build` and `make test` from the worktree root. Do not run `make run`, do not launch or kill the app, and do not take screenshots.
- Do not spawn further agents. You are working unsupervised: do not ask questions, make the decisions yourself and finish the job.

## Handoff
When done, reply in a few lines: the files you changed, the checks you ran with their outcome, and the names of any skills you invoked (or "none").
