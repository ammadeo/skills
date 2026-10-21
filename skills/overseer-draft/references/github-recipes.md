# GitHub recipes (gh CLI, read unless marked write)

Shell note: in zsh, unquoted `$var` does not word-split, so
`for pr in "a b"; do set -- $pr` behaves differently than in bash. Iterate
with `printf '%s\n' ... | while read -r repo num` instead; it works in both.

## All open PRs, bucketed (start here)
    scripts/pr-status.sh [--owner ORG]... [--repo ORG/REPO]... [--json]
One GraphQL search, Markdown grouped by who holds the ball. `--json` gives
per-PR objects (bucket, why, ci, failingChecks, threads, reviewers) for
further filtering with `gh`'s `--jq` or any JSON tool.

## Deep state of one PR (threads with content, all checks)
    gh api graphql -f query='{ repository(owner:"ORG", name:"REPO") {
      pullRequest(number:N) {
        isDraft mergeable mergeStateStatus reviewDecision baseRefName updatedAt
        reviewRequests(first:10){ nodes{ requestedReviewer{
          ... on User { login } ... on Team { slug } } } }
        latestReviews(first:10){ nodes{ author{login} state submittedAt } }
        reviewThreads(first:100){ nodes{ id isResolved path line
          comments(first:3){ nodes{ author{login} createdAt body } } } }
        commits(last:1){ nodes{ commit{ oid statusCheckRollup{ state
          contexts(first:60){ nodes{ ... on CheckRun { name conclusion status }
                                     ... on StatusContext { context state } } } } } } }
      } } }'
Filter unresolved threads with `select(.isResolved==false)`. Review bots
often prefix comments with an HTML comment header; strip it with
`gsub("<!--[^>]*-->";"")` before quoting.

## Same-minute merge check
    gh pr view URL --json reviewDecision,mergeable,mergeStateStatus,statusCheckRollup
plus the unresolved-thread count from the query above.

## Who to ask for review (approval history by repo)
    gh pr list --repo ORG/REPO --state merged --limit 80 \
      --search "merged:>=YYYY-MM-DD" --json number,author,reviews \
      --jq '.[] | .reviews[] | select(.state=="APPROVED") | .author.login' \
      | grep -v '\[bot\]' | sort | uniq -c | sort -rn
Per-area routing comes from which approver signed which of the user's own
merged PRs (add `--author @me`) and which files those PRs touched.

## Writes (only with the user's go-ahead)
- Request reviewer: `gh pr edit N --repo ORG/REPO --add-reviewer LOGIN`;
  fallback `gh api -X POST repos/ORG/REPO/pulls/N/requested_reviewers -f 'reviewers[]=LOGIN'`.
- Merge: check `gh api repos/ORG/REPO --jq '{allow_squash_merge,allow_merge_commit,allow_rebase_merge,delete_branch_on_merge}'`
  for the repo's merge style, then `gh pr merge N --repo ORG/REPO --squash`
  (or `--merge` / `--rebase`); fallback
  `gh api -X PUT repos/ORG/REPO/pulls/N/merge -f merge_method=squash`.
- Close with reason: `gh pr close N --repo ORG/REPO --comment "..."`.
- Reply to a review thread: `POST repos/ORG/REPO/pulls/N/comments/{id}/replies`;
  resolve via GraphQL `resolveReviewThread(input:{threadId})`.
