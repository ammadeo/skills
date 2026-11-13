#!/usr/bin/env bash
# gather-prs.sh: your pull requests for one day's update, in one GitHub call.
#
# Needs only the gh CLI (logged in). Read-only. Two searches in one GraphQL
# query: your open PRs, and your PRs merged on the given local day. Prints one
# compact JSON object per PR with a suggested section and ticket references.
# Works with bash 3.2 and later.
#
# Usage:
#   gather-prs.sh (--repo OWNER/REPO | --owner ORG)... [--date YYYY-MM-DD]
#                 [--ticket-prefix ABC]...
#
#   --repo OWNER/REPO   limit to a repository (repeatable; OR-ed)
#   --owner ORG         limit to an org or user (repeatable; OR-ed)
#   --date YYYY-MM-DD   the day being reported (default: today, local time)
#   --ticket-prefix ABC only report ticket IDs with this prefix (repeatable),
#                       e.g. the project's Linear team key
#   -h, --help          show this help
#
# Fields: repo, number, title, url, draft, merged, head, updatedAt,
# section (released | releasable | waiting | in_progress), hint (why),
# waitingOn (pending reviewers: login and name), ticketIds, ticketUrls,
# stale (draft untouched for 14+ days; usually leave it out),
# stack + stackPos (only on open PRs chained base-on-head with another of
# your open PRs: stack is "repo#<bottom PR number>", stackPos 1 is the bottom).
# Output is sorted by repo, then stack bottom to top.
#
# Section suggestions, first match wins:
#   released     merged on --date
#   in_progress  draft; or conflicts, failing CI, unresolved threads,
#                changes requested; or open with no reviewer requested
#   releasable   approved, CI green or none, merge state clean
#   waiting      approved but CI pending or merge blocked; or review pending
# They are suggestions: the ticket status or the user can overrule them.

usage() { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; }

quals=""
day=""
prefixes=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)  [ -n "$2" ] || { echo "--repo needs a value" >&2; exit 2; }
             quals="$quals repo:$2"; shift 2 ;;
    --owner) [ -n "$2" ] || { echo "--owner needs a value" >&2; exit 2; }
             quals="$quals owner:$2"; shift 2 ;;
    --date)  [ -n "$2" ] || { echo "--date needs a value" >&2; exit 2; }
             day="$2"; shift 2 ;;
    --ticket-prefix) [ -n "$2" ] || { echo "--ticket-prefix needs a value" >&2; exit 2; }
             prefixes="$prefixes,$(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1 (try -h)" >&2; exit 2 ;;
  esac
done

[ -n "$quals" ] || { echo "give at least one --repo or --owner (the project's repos)" >&2; exit 2; }
command -v gh >/dev/null 2>&1 || { echo "gh CLI not found" >&2; exit 1; }
[ -n "$day" ] || day=$(date +%Y-%m-%d)
case "$day" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) echo "--date must be YYYY-MM-DD" >&2; exit 2 ;;
esac
tz=$(date +%z | sed 's/\(..\)$/:\1/')
open_q="is:pr is:open author:@me archived:false$quals"
merged_q="is:pr is:merged author:@me archived:false merged:${day}T00:00:00${tz}..${day}T23:59:59${tz}$quals"
stale_before=$(date -v-14d +%Y-%m-%d 2>/dev/null || date -d '14 days ago' +%Y-%m-%d)

read -r -d '' FIELDS <<'EOF'
nodes { ... on PullRequest {
  number title url isDraft merged baseRefName headRefName body updatedAt
  mergeable mergeStateStatus reviewDecision
  repository { nameWithOwner }
  reviewRequests(first: 10) { nodes { requestedReviewer {
    __typename ... on User { login name } ... on Team { slug name } } } }
  reviewThreads(first: 100) { nodes { isResolved } }
  comments(first: 30) { nodes { body } }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } }
} }
EOF
GQL="query(\$o: String!, \$m: String!) {
  open: search(query: \$o, type: ISSUE, first: 50) { $FIELDS }
  merged: search(query: \$m, type: ISSUE, first: 50) { $FIELDS }
}"

read -r -d '' JQ <<'EOF'
def oneof($xs): . as $v | any($xs[]; . == $v);
def ids:
  [ scan("(?i)\\b([a-z][a-z0-9]{1,9}-[0-9]{1,6})\\b") | .[0] | ascii_upcase
    | select((split("-")[0]) | oneof(["UTF","SHA","ISO","RFC","HTTP","TLS","ES","WCAG","CVE","GPT","V"]) | not)
    | select(PREFIXES == [] or ((split("-")[0]) | oneof(PREFIXES))) ];
def urls:
  [ scan("https?://(?:linear\\.app|app\\.clickup\\.com|[a-z0-9-]+\\.atlassian\\.net|app\\.asana\\.com|github\\.com/[^/ ]+/[^/ ]+/issues)/[^\\s)>\\]\"]+") ];
def suggest:
  if .merged then {section: "released", hint: "merged"}
  elif .isDraft then {section: "in_progress", hint: "draft"}
  else
    [ (if .mergeable == "CONFLICTING" then "merge conflicts" else empty end),
      (if (.ci | oneof(["FAILURE","ERROR"])) then "CI failing" else empty end),
      (if .unresolved > 0 then "\(.unresolved) unresolved thread(s)" else empty end),
      (if .reviewDecision == "CHANGES_REQUESTED" then "changes requested" else empty end)
    ] as $a
    | if ($a | length) > 0 then {section: "in_progress", hint: ($a | join("; "))}
      elif .reviewDecision == "APPROVED" and (.ci | oneof(["SUCCESS","NONE"]))
           and (.mergeStateStatus | oneof(["CLEAN","HAS_HOOKS","UNSTABLE"]))
        then {section: "releasable", hint: "approved, CI \(.ci | ascii_downcase)"}
      elif .reviewDecision == "APPROVED"
        then {section: "waiting", hint: "approved; CI \(.ci | ascii_downcase), merge state \(.mergeStateStatus | ascii_downcase)"}
      elif (.waitingOn | length) > 0
        then {section: "waiting", hint: "review pending"}
      else {section: "in_progress", hint: "open, no reviewer requested"}
      end
  end;

[ [ .data.open.nodes[], .data.merged.nodes[] ] | unique_by(.url) | .[]
| select(.number != null)
| { repo: .repository.nameWithOwner, number, title, url, draft: .isDraft, merged,
    base: .baseRefName, head: .headRefName, updatedAt,
    mergeable, mergeStateStatus,
    reviewDecision: (.reviewDecision // "NONE"),
    ci: (.commits.nodes[0].commit.statusCheckRollup.state // "NONE"),
    unresolved: ([ .reviewThreads.nodes[] | select(.isResolved | not) ] | length),
    waitingOn: [ .reviewRequests.nodes[].requestedReviewer | select(. != null)
                 | if .__typename == "Team" then "team:\(.slug)"
                   else (.login + (if (.name // "") != "" then " (\(.name))" else "" end)) end ],
    text: ([.title, .headRefName, (.body // "")] + [ .comments.nodes[].body ] | join("\n")) }
| . + suggest
| . + { ticketIds: (.text | ids | unique), ticketUrls: (.text | urls | unique),
        stale: (.draft and .updatedAt < STALE) }
| del(.text, .mergeable, .mergeStateStatus, .reviewDecision, .ci, .unresolved)
| if (.waitingOn | length) == 0 then del(.waitingOn) else . end ]
| [ .[] | select(.merged | not) ] as $open
| def chain($p):
    (first($open[] | select(.repo == $p.repo and .head == $p.base)) // null) as $up
    | if $up == null then [$p.number] else chain($up) + [$p.number] end;
  [ .[] | if .merged then . else (chain(.)) as $c | . + {_root: $c[0], _pos: ($c | length)} end ]
| (reduce (.[] | select(._root != null) | "\(.repo)#\(._root)") as $k ({}; .[$k] += 1)) as $size
| [ .[] | ("\(.repo)#\(._root)") as $k
    | (if ._root != null and $size[$k] > 1 then . + {stack: $k, stackPos: ._pos} else . end)
    | del(._root, ._pos) ]
| sort_by([.repo, (.stack // "~"), (.stackPos // 0), .number]) | .[]
EOF

plist=$(printf '%s' "${prefixes#,}" | sed 's/[^,][^,]*/"&"/g')
JQ="def PREFIXES: [${plist}]; def STALE: \"${stale_before}\"; $JQ"

exec gh api graphql -f query="$GQL" -f o="$open_q" -f m="$merged_q" --jq "$JQ"
