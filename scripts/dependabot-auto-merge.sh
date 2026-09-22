#!/bin/bash
# Turns auto-merge on for the organization's open Dependabot pull requests.
#
# The repository setting only makes the feature available. GitHub still wants
# auto-merge turned on one pull request at a time, and nothing was doing that,
# so the pull requests sat open however green they were.
#
# Patch and minor updates are turned on here. A major update is left for a
# person to look at, and so is a commit that does not say which it is.
set -euo pipefail

ORG="${ORG:-femiwiki}"
SKIPPED_REPOSITORIES="${SKIPPED_REPOSITORIES:-}"

# A check that ran and did not fail. GitHub reports check runs and the older
# commit statuses in the same rollup, with a different shape each.
GREEN='
  [
    .statusCheckRollup[]?
    | if .__typename == "CheckRun" then
        .status == "COMPLETED"
          and (.conclusion == "SUCCESS" or .conclusion == "NEUTRAL" or .conclusion == "SKIPPED")
      else
        .state == "SUCCESS"
      end
  ]
  | all
'

failed=0

pulls="$(
  gh api --paginate -X GET search/issues \
    -f q="org:${ORG} is:pr is:open is:unlocked draft:false archived:false author:app/dependabot" \
    -F per_page=100 \
    --jq '.items[] | [(.repository_url | sub("^.*/repos/"; "")), .number] | @tsv'
)"

while IFS=$'\t' read -r repo number; do
  [ -n "$repo" ] || continue

  case " $SKIPPED_REPOSITORIES " in
  *" $repo "*)
    echo "$repo#$number: left out on purpose"
    continue
    ;;
  esac

  pull="$(gh pr view "$number" --repo "$repo" \
    --json autoMergeRequest,headRefOid,mergeStateStatus,statusCheckRollup)"

  if [ "$(jq -r '.autoMergeRequest != null' <<<"$pull")" = true ]; then
    echo "$repo#$number: auto-merge is already on"
    continue
  fi

  # Dependabot describes the update in its own commit message, which is the
  # only place to read it from outside the repository's own workflows. The
  # update type is there for a direct dependency; for an indirect one only the
  # sentence that names the versions is, and a grouped update has one of those
  # per dependency.
  head="$(jq -r '.headRefOid' <<<"$pull")"
  message="$(gh api "repos/$repo/commits/$head" --jq '.commit.message')"
  types="$(sed -n 's/^[[:space:]]*update-type: version-update:semver-//p' <<<"$message" | sort -u)"
  bumps="$(
    { grep -oE ' from v?[0-9][^ ]* to v?[0-9][^ ]*' <<<"$message" || true; } |
      sed -E 's/ from v?([0-9]+)[^ ]* to v?([0-9]+).*/\1 \2/' | sort -u
  )"

  if [ -z "$types" ] && [ -z "$bumps" ]; then
    echo "$repo#$number: the commit does not say what kind of update this is"
    continue
  fi
  if grep -qx major <<<"$types" || awk '$1 != $2 { s = 1 } END { exit !s }' <<<"$bumps"; then
    echo "$repo#$number: major update"
    continue
  fi

  case "$(jq -r '.mergeStateStatus' <<<"$pull")" in
  DIRTY)
    echo "$repo#$number: conflicts with its base branch"
    ;;
  UNKNOWN)
    echo "$repo#$number: GitHub has not finished testing the merge"
    ;;
  CLEAN)
    # Nothing is left to wait for, so GitHub refuses to queue a merge. These
    # repositories require no check, so look at the checks that did run.
    if [ "$(jq -r "$GREEN" <<<"$pull")" != true ]; then
      echo "$repo#$number: checks are not green"
      continue
    fi
    gh pr merge "$number" --repo "$repo" --squash
    echo "$repo#$number: merged"
    ;;
  *)
    gh pr merge "$number" --repo "$repo" --squash --auto || failed=1
    echo "$repo#$number: auto-merge is on"
    ;;
  esac
done <<<"$pulls"

exit "$failed"
