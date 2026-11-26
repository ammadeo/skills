---
tags: [estimate]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Make me a single-file HTML page I can share with the team: our Q1 candidates with an estimate for each. Save it as roadmap.html.

Candidates:
- Dark mode for the dashboard (all colours already come from CSS variables)
- Move file uploads from our own server to S3, including the roughly 40k existing files
- A "duplicate project" action in the project menu
- Weekly email digest of project activity (the app has no scheduled jobs yet)
