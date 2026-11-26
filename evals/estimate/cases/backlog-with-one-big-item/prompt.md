---
tags: [estimate]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Can you estimate these for planning tomorrow?

1. Fix the typo in the subject of the password reset email
2. Add a "last login" column to the admin users table (the API already returns lastLoginAt)
3. Let customers log in with their company SSO (SAML). We have the web app, the iOS app and the admin panel, all on our own email + password login today. We don't know yet which identity providers the first customers use.
4. Rate-limit the public search endpoint, we got scraped last week
