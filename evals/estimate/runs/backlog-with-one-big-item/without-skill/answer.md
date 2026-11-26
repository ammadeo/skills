Items 1, 2 and 4 are small and add up to about 2–3 developer-days. Item 3 is a multi-week project that can't be planned as one ticket yet; I'd put a 2–3 day spike on the board for it instead.

I haven't seen the code, so these come from the descriptions alone. Figures are working time for one developer, including review and testing.

| # | Item | Estimate | Confidence |
|---|---|---|---|
| 1 | Typo in the password reset subject | under 1 hour | High |
| 2 | "Last login" column | about half a day | High |
| 3 | Company SSO (SAML) | 3–5 weeks of effort with a hosted SSO service, 5–9 weeks built in-house | Low |
| 4 | Rate-limit public search | 1–2 days | Medium |

## 1. Typo: under 1 hour

This is a one-string change. Two things to check:

- **Translations:** if the subject is translated, the other languages may need the same look.
- **Where the template lives:** if it sits in your email provider's dashboard and not in code, it is an edit there with no deploy.

## 2. Last login column: about half a day

The work is adding the column, formatting the date and showing something sensible for users who have never logged in.

It grows to about 1 day if the column must be sortable and the table sorts on the server, because the API then needs a sort option.

## 4. Rate limit: 1–2 days

I'd schedule this first, since it is the only item with a live risk. The range depends on where the limit goes:

- **At the edge:** if a CDN or gateway sits in front of the API (Cloudflare, AWS WAF, nginx), it is a rule there. That takes about half a day, including picking thresholds from last week's logs.
- **In the application:** 1–2 days. It needs a shared counter store such as Redis if you run more than one instance, a proper "too many requests" response, and a check that the web and iOS apps handle that response gracefully.

Two risks to raise in planning:

- **Shared office addresses:** your customers are companies, so many legitimate users can arrive from one IP address. Limit per account where the caller is logged in, and per IP only for anonymous traffic.
- **Rotating scrapers:** a per-IP limit stops a casual scraper, not one that rotates addresses. If last week's scraper rotated, this ticket reduces the problem but does not close it.

## 3. SSO: why it is big

- **Three login surfaces:** web is the standard case. iOS needs a browser-based login that hands back to the app, an App Store release and a decision about old app versions. The admin panel depends on who logs in there (see the questions below).
- **Account rules:** this is where most of the effort and risk sit. You need to decide how an SSO login maps to an existing email + password account, whether users are created on first SSO login, whether a company can enforce SSO and switch passwords off, and what password reset does for those users.
- **Per-customer setup:** every customer brings their own identity provider settings. Entering them by hand for the first customers is cheap; a self-service screen for customers adds 1–2 weeks.
- **Unknown identity providers:** SAML is a standard, but Okta, Microsoft Entra ID, Google Workspace and ADFS differ in the details, and each needs its own test. A hosted service (WorkOS, Auth0 and similar) absorbs those differences, which is the main reason for the lower range. It is usually priced per customer connection.

What I'd plan tomorrow for item 3:

1. **Ask the first customers which identity provider they use.** This is not engineering work, it can start immediately, and it removes the biggest unknown.
2. **Run a 2–3 day spike.** It should decide build versus buy, the account rules above and the iOS flow, and produce a ticket breakdown with real estimates.
3. **Expect a first slice of roughly 1.5–2.5 weeks.** That is web only, one pilot customer, settings entered by you, on a hosted service. iOS and the admin panel follow as separate slices. Treat this figure as rough until the spike is done.

## Questions that would change the numbers

- **Admin panel users:** is it used by your own staff or by customers' admins? If only your staff use it, it needs no SSO login, which removes one of the three surfaces.
- **Search endpoint:** is there a CDN or gateway in front of it, and can it be called without logging in?
- **Hosted SSO:** are you open to paying for a hosted service? That decides which of the two ranges for item 3 applies.
