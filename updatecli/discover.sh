#!/usr/bin/env bash
# Print every workflow in the organization that pins the version of a tool
# listed in tools.tsv, one "<tool> <repository> <default branch> <path>" line
# each, tab-separated. A workflow that uses the action without a version:
# input has nothing to bump and gets a warning instead.
set -euo pipefail

owner=${GITHUB_REPOSITORY_OWNER:?}
tools=$(dirname "$0")/tools.tsv

gh repo list "$owner" --no-archived --source --limit 1000 \
  --json name,defaultBranchRef \
  --jq '.[] | select(.defaultBranchRef != null) | "\(.name)\t\(.defaultBranchRef.name)"' |
  while IFS=$'\t' read -r repo branch; do
    { gh api "repos/$owner/$repo/contents/.github/workflows?ref=$branch" \
        --jq '.[] | select(.name | test("\\.ya?ml$")) | .path' 2>/dev/null || true; } |
      while read -r path; do
        body=$(gh api "repos/$owner/$repo/contents/$path?ref=$branch" \
          -H 'Accept: application/vnd.github.raw')
        while IFS=$'\t' read -r tool action _; do
          grep -q "uses: $action@" <<<"$body" || continue
          # The same shape render.sh's matchpattern looks for.
          if grep -Pzq "uses: $action@[^\n]*\n[ \t]+with:\n(?:[ \t]+[a-z-]+:[^\n]*\n)*?[ \t]+version:" <<<"$body"; then
            printf '%s\t%s\t%s\t%s\n' "$tool" "$repo" "$branch" "$path"
          else
            echo "::warning::$repo/$path uses $action without a version: input, so updatecli leaves it alone" >&2
          fi
        done < <(grep -v '^#' "$tools")
      done
  done
