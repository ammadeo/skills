The page is saved as `roadmap.html`, a single self-contained file with no external dependencies. I have not opened it in a browser.

The four candidates come to 18–34 engineer-days in total. I estimated from your one-line descriptions without seeing the code, so these are ranges for one engineer who knows the codebase, not calendar time.

| Candidate | Estimate | Confidence |
|---|---|---|
| Dark mode for the dashboard | 2–4 days | High |
| Move file uploads to S3 (incl. ~40k existing files) | 8–15 days | Low to medium |
| "Duplicate project" action | 2–5 days | Medium |
| Weekly email digest | 6–10 days | Medium |

- **Dark mode:** it is small because the colours already come from CSS variables. The remaining work is the dark values, a switch, and a pass over charts and images.
- **S3 move:** copying 40k files takes hours. The effort is in the cutover and in making sure no file is lost.
- **Duplicate project:** the estimate depends on what a project contains. Attached files would tie it to the S3 move.
- **Weekly digest:** 2–4 days of it is adding scheduled jobs, which the app does not have yet. I assumed the app already sends email and already records project activity; if there is no activity log, add 3–5 days.

Beyond what you asked for, the page lists each estimate's assumptions, a suggested order (dark mode, S3, duplicate project, digest) and the questions that would narrow the ranges. Remove those sections if you only want the numbers.

Files are in the output folder:
- roadmap.html
