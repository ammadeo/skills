#!/usr/bin/env bash
# pr-status.sh: state of all your open pull requests in one GitHub call.
#
# Needs only the gh CLI (logged in). Runs one `gh api graphql` search for
# `is:pr is:open author:@me archived:false` (first 50 results) and does all
# shaping with gh's built-in --jq. Read-only. Works with bash 3.2 and later.
#
# Usage:
#   pr-status.sh [--owner ORG]... [--repo OWNER/REPO]... [--json]
#
#   --owner ORG        limit to an org or user (repeatable; OR-ed)
#   --repo OWNER/REPO  limit to a repository (repeatable; OR-ed)
#   --json             print a JSON array of per-PR objects instead of Markdown
#   -h, --help         show this help
#
# Buckets ("who holds the ball"), first match wins:
#   draft        isDraft
#   author       mergeable == CONFLICTING, or CI rollup FAILURE/ERROR, or
#                unresolved review threads > 0, or CHANGES_REQUESTED
#   ready        APPROVED, CI SUCCESS or no checks, and mergeStateStatus
#                CLEAN, HAS_HOOKS, or UNSTABLE with no failing checks
#   approved     APPROVED but not ready yet: CI pending, or merge state
#                BEHIND/BLOCKED/UNKNOWN (its "why" says which)
#   reviewer     review requests still pending
#   unrequested  everything else (no reviewer requested yet)
#
# Markdown output is grouped in this order: Ready to merge, Approved, not
# ready yet, Waiting on reviewer, Needs a reviewer requested, Ball with
# author, Draft.
# Unresolved threads are counted from the first 100 threads per PR; check
# names from the first 50 contexts of the last commit.

usage() { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; }

quals=""
mode="md"
while [ $# -gt 0 ]; do
  case "$1" in
    --owner) [ -n "$2" ] || { echo "--owner needs a value" >&2; exit 2; }
             quals="$quals owner:$2"; shift 2 ;;
    --repo)  [ -n "$2" ] || { echo "--repo needs a value" >&2; exit 2; }
             quals="$quals repo:$2"; shift 2 ;;
    --json)  mode="json"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1 (try -h)" >&2; exit 2 ;;
  esac
done

command -v gh >/dev/null 2>&1 || { echo "gh CLI not found" >&2; exit 1; }

search="is:pr is:open author:@me archived:false$quals"

read -r -d '' GQL <<'EOF'
query($q: String!) {
  search(query: $q, type: ISSUE, first: 50) {
    issueCount
    nodes {
      ... on PullRequest {
        number title url isDraft baseRefName headRefName
        mergeable mergeStateStatus reviewDecision updatedAt
        repository { nameWithOwner }
        reviewRequests(first: 10) { nodes { requestedReviewer {
          __typename
          ... on User { login }
          ... on Bot { login }
          ... on Mannequin { login }
          ... on Team { slug }
        } } }
        latestReviews(first: 10) { nodes { author { login } state } }
        reviewThreads(first: 100) { totalCount nodes { isResolved } }
        commits(last: 1) { nodes { commit { statusCheckRollup {
          state
          contexts(first: 50) { nodes {
            __typename
            ... on CheckRun { name conclusion }
            ... on StatusContext { context state }
          } }
        } } } }
      }
    }
  }
}
EOF

read -r -d '' JQ <<'EOF'
def oneof($xs): . as $v | any($xs[]; . == $v);
def failing:
  [ (.contexts.nodes // [])[]
    | select(
        (.__typename == "CheckRun" and ((.conclusion // "")
          | oneof(["FAILURE","TIMED_OUT","CANCELLED","ACTION_REQUIRED","STARTUP_FAILURE"])))
        or (.__typename == "StatusContext" and (.state | oneof(["FAILURE","ERROR"]))))
    | (.name // .context) ];
def classify:
  if .isDraft then {bucket: "draft", why: "draft"}
  else
    [ (if .mergeable == "CONFLICTING" then "merge conflicts" else empty end),
      (if (.ci | oneof(["FAILURE","ERROR"])) then
         "CI failing" + (if (.failingChecks | length) > 0
           then ": " + (.failingChecks[:3] | join(", "))
             + (if (.failingChecks | length) > 3 then ", ..." else "" end)
           else "" end)
       else empty end),
      (if .threadsUnresolved > 0 then "\(.threadsUnresolved) unresolved thread(s)" else empty end),
      (if .reviewDecision == "CHANGES_REQUESTED" then "changes requested" else empty end)
    ] as $a
    | if ($a | length) > 0 then {bucket: "author", why: ($a | join("; "))}
      elif .reviewDecision == "APPROVED"
        and (.ci | oneof(["SUCCESS","NONE"]))
        and ((.mergeStateStatus | oneof(["CLEAN","HAS_HOOKS"]))
             or (.mergeStateStatus == "UNSTABLE" and (.failingChecks | length) == 0))
        then {bucket: "ready", why: "approved, CI \(.ci | ascii_downcase), \(.mergeStateStatus | ascii_downcase)"}
      elif .reviewDecision == "APPROVED"
        then {bucket: "approved", why: "approved but CI \(.ci | ascii_downcase), merge state \(.mergeStateStatus | ascii_downcase)"}
      elif (.pendingReviewers | length) > 0
        then {bucket: "reviewer", why: "waiting on " + (.pendingReviewers | join(", "))}
      else {bucket: "unrequested", why: "no reviewer requested"
              + (if (.reviews | length) > 0 then " (has reviews, none pending)" else "" end)}
      end
  end;
def short: if length > 60 then .[:57] + "..." else . end;
def revs:
  ([ .pendingReviewers[] | "\(.) (requested)" ]
   + [ .reviews[] | "\(.author) (\(.state | ascii_downcase | sub("_"; " ")))" ]) as $r
  | if ($r | length) == 0 then "no reviewers" else $r | join(", ") end;
def row:
  "- [\(.repo)#\(.number)](\(.url)) \(.title | short) · CI \(.ci | ascii_downcase)"
  + " · threads \(.threadsUnresolved)/\(.threadsTotal)"
  + " · review \(.reviewDecision | if . == "REVIEW_REQUIRED" then "required" else ascii_downcase | sub("_"; " ") end)"
  + " · \(revs) · \(.why)";

.data.search as $s
| [ $s.nodes[] | select(.number != null)
    | (.commits.nodes[0].commit.statusCheckRollup) as $r
    | { repo: .repository.nameWithOwner, number, title, url, isDraft,
        base: .baseRefName, head: .headRefName,
        mergeable, mergeStateStatus,
        reviewDecision: (.reviewDecision // "NONE"),
        ci: ($r.state // "NONE"),
        failingChecks: ($r // {} | failing),
        pendingReviewers: [ .reviewRequests.nodes[].requestedReviewer
                            | select(. != null)
                            | (.login // ("team:" + (.slug // "?"))) ],
        reviews: [ .latestReviews.nodes[]
                   | {author: (.author.login // "ghost"), state} ],
        threadsTotal: .reviewThreads.totalCount,
        threadsUnresolved: ([ .reviewThreads.nodes[] | select(.isResolved | not) ] | length),
        updatedAt }
    | . + classify ]
  | sort_by(.updatedAt) | reverse
  | . as $prs
  | if MODE == "json" then $prs
    else
      [ ["ready","Ready to merge"], ["approved","Approved, not ready yet"],
        ["reviewer","Waiting on reviewer"],
        ["unrequested","Needs a reviewer requested"],
        ["author","Ball with author"], ["draft","Draft"] ] as $groups
      | ( "**\($prs | length) open PRs** · "
          + ([ $groups[] | . as $g
               | "\($g[1]) \([ $prs[] | select(.bucket == $g[0]) ] | length)" ]
             | join(" · "))
          + (if $s.issueCount > ($prs | length)
             then "\n\n_Showing \($prs | length) of \($s.issueCount); narrow with --owner or --repo._"
             else "" end) ) as $head
      | [ $head,
          ( $groups[] | . as $g
            | [ $prs[] | select(.bucket == $g[0]) ] as $rows
            | select(($rows | length) > 0)
            | "\n### \($g[1]) (\($rows | length))\n" + ([ $rows[] | row ] | join("\n")) ) ]
      | join("\n")
    end
EOF

JQ="def MODE: \"$mode\"; $JQ"

exec gh api graphql -f query="$GQL" -f q="$search" --jq "$JQ"
