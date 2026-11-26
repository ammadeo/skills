Three of the four are ready to plan as they are; the SSO item is complex and should be split before it goes in. I estimate in complexity rather than time, and I judged these from your descriptions without reading the code.

| Item | Complexity | Why |
| --- | --- | --- |
| 1. Fix the typo in the password reset email subject | 🟢 simple | One string in one place, nothing else moves, ordinary release. |
| 2. Add a "last login" column to the admin users table | 🟢 simple | The API already returns `lastLoginAt`, so only the admin table changes. The one detail to settle is how to show users who have never logged in. |
| 3. Company SSO (SAML) login | 🔴 complex | Three apps change, login is the riskiest path to break, the identity providers are unknown, and the iOS part ships through an App Store release. |
| 4. Rate-limit the public search endpoint | 🟡 moderate | Known goal in one system, but the limits are a judgement call: what to key on (IP, session, API key), where to enforce it (edge or app), and how to avoid blocking real users behind a shared IP. |

## Proposed split for 3

Each slice can be released and checked on its own. Nothing changes in your tickets until you agree.

1. 🟡 moderate: **One pilot customer logs in to the web app through their identity provider, behind a flag.** Answers the open questions: which provider, and how SSO users are matched to existing email + password accounts. Depends on one customer telling you their provider, which is a question to ask, not something to build.
2. 🟡 moderate: **The same pilot customer logs in to the iOS app with SSO.** Reuses the server side from 1; the new parts are the browser-based login flow in the app and the App Store release. After 1.
3. 🟢 simple: **Admin panel users log in with SSO.** Same flow as the web app on a second surface. After 1.
4. 🟡 moderate: **An SSO connection for a new customer is set up from the admin panel** instead of by hand, so onboarding the next customer needs no deploy. After 1.
5. 🟡 moderate: **A company can require SSO, so password login is turned off for its users.** Needs a way back in for a customer whose provider is misconfigured. After 1, 2 and 3, so no surface is left without a way to log in.
6. 🟢 simple, per provider: **Each further identity provider is verified with the customer who uses it.** After 1; how many of these there are depends on what the first customers answer.

One question to settle while planning: is the admin panel used by your customers or only by your own staff? If it is staff only, slice 3 may not belong to this item at all.
