This is a small change: about 5–10 minutes if I make it here, or 1–2 hours for a developer including review and a manual check. I haven't looked at the code, so that is based on your description alone.

The work is one button next to the existing link, a click handler calling `navigator.clipboard.writeText(link)`, and a short "Copied" confirmation. No backend change is needed, since the link is already on the page.

It would grow to roughly half a day if any of these apply:

- **No existing button, icon or toast to reuse:** the confirmation and styling would have to be built from scratch.
- **The page is served over plain HTTP or inside an iframe:** the clipboard API is blocked there and needs a fallback.
- **The team requires automated tests for UI changes:** clipboard access has to be mocked, which adds 30–60 minutes.
- **The settings page has several variants:** a separate mobile layout or role-based views each need the button placed and checked.

If you point me at the team settings page, I can confirm which of these apply and make the change.
