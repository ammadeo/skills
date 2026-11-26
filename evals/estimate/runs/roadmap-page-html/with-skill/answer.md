The page is saved as a single self-contained file, no external assets, readable on a phone and in dark mode:

roadmap.html

The estimates are in complexity, not time, so the page carries no hours, days or points. I judged from your one-line descriptions without reading the code, and the page says so.

| Item | Complexity | Why |
| --- | --- | --- |
| Dark mode for the dashboard | 🟢 simple | Every colour already comes from a CSS variable, so it is a second set of values and a switch. One system, ordinary release. |
| Move file uploads to S3, incl. ~40k existing files | 🔴 complex | Uploading, storing and downloading all change, old and new storage run side by side during the copy, and how stored file links and access rules carry over is unknown. |
| "Duplicate project" action | 🟡 moderate | Known goal in one system, but the copy has to cover everything a project owns, and what happens to files, members and history is still to be decided. |
| Weekly email digest | 🟡 moderate | The digest is ordinary work, but it brings the app's first scheduled job: somewhere to run, a guard against sending twice, an opt-out. Assumes the app already sends email. |

Proposed split for the S3 move (on the page too; a proposal, nothing to change in tickets until you agree):

1. 🟡 moderate: Uploads in one internal project are stored in and served from S3, behind a flag. Answers the links and access question. Depends on nothing.
2. 🟢 simple: Every new upload goes to S3. After 1.
3. 🟡 moderate: The roughly 40k existing files are moved in batches, with a way back per batch. After 2.
4. 🟢 simple: The old upload storage and its code path are removed. After 3.

Two things to check before you share it:

- If "duplicate project" also copies files, it touches the storage the S3 move is changing, so keep the two from overlapping.
- If the app does not send email yet, the digest has two new pieces rather than one and I would look at it again.
