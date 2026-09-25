#!/usr/bin/env bash
# Append to each pull request updatecli opened the release notes of every
# release the bump crosses: release-notes.sh <targets>.
#
# updatecli knows the release it bumps to but not the version it replaces,
# which only the workflow on the default branch holds, so the range is read
# off the pull request's own diff.
set -euo pipefail

targets=$1
owner=${GITHUB_REPOSITORY_OWNER:?}
tools=$(dirname "$0")/tools.tsv
# A later run replaces what sits between these instead of adding a second
# block to a pull request updatecli keeps open.
open='<!-- femiwiki: release notes -->'
close='<!-- /femiwiki -->'
work=$(mktemp -d)

cut -f1-3 "$targets" | sort -u | while IFS=$'\t' read -r tool repo branch; do
  IFS=$'\t' read -r _ _ _ _ upstream prefix < <(grep -P "^$tool\t" "$tools")
  # updatecli names its branch after the base branch and the pipelineid.
  head="updatecli_${branch}_$tool"
  number=$(gh pr list -R "$owner/$repo" --head "$head" --state open \
    --json number --jq '.[0].number // empty')
  if [ -z "$number" ]; then
    echo "$repo: no open pull request from $head"
    continue
  fi

  diff=$(gh pr diff "$number" -R "$owner/$repo")
  old=$(sed -n 's/^-[[:space:]]*version:[[:space:]]*\([^[:space:]#]*\).*/\1/p' <<<"$diff" | head -n1)
  new=$(sed -n 's/^+[[:space:]]*version:[[:space:]]*\([^[:space:]#]*\).*/\1/p' <<<"$diff" | head -n1)
  if [ -z "$new" ]; then
    echo "$repo#$number: no version: line in the diff"
    continue
  fi

  gh api "repos/$upstream/releases?per_page=100" > "$work/releases.json"
  {
    echo "$open"
    echo
    echo "### Release notes"
    echo
    if [[ $old =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
      echo "[${prefix}${old}...${prefix}${new}](https://github.com/$upstream/compare/${prefix}${old}...${prefix}${new})"
    else
      echo "Pins $tool, which was \`$old\`."
    fi
    echo
    jq -r --arg p "$prefix" --arg old "$old" --arg new "$new" '
      def ver: split(".") | map(tonumber);
      def isver: test("^[0-9]+(\\.[0-9]+)*$");
      [ .[]
        | select((.draft or .prerelease) | not)
        | select(.tag_name | startswith($p))
        | .v = (.tag_name | ltrimstr($p))
        | select(.v | isver)
        | select((.v | ver) <= ($new | ver))
        | select(if ($old | isver) then (.v | ver) > ($old | ver) else .v == $new end)
      ]
      | sort_by(.v | ver) | reverse
      | .[]
      | "<details><summary><a href=\"\(.html_url)\">\(.tag_name)</a></summary>\n\n"
        + ((.body // "") | if length > 4000 then .[:4000] + "\n\n…" else . end)
        + "\n\n</details>\n"
    ' "$work/releases.json"
    echo "$close"
  } > "$work/notes.md"

  gh pr view "$number" -R "$owner/$repo" --json body --jq .body |
    awk -v o="$open" -v c="$close" '$0 == o { skip = 1 } !skip { print } $0 == c { skip = 0 }' \
      > "$work/body.md"
  # A pull request body holds 65536 characters.
  head -c 60000 "$work/notes.md" >> "$work/body.md"
  gh pr edit "$number" -R "$owner/$repo" --body-file "$work/body.md"
  echo "$repo#$number: release notes for $tool $old -> $new"
done
