#!/usr/bin/env bash
# Write one updatecli manifest per tool and repository from the lines
# discover.sh printed: render.sh <targets> <directory>.
#
# Each manifest bumps the "version:" input of the tool's action in every
# workflow of that repository that uses it, so one pull request carries
# the tool to its latest release across the repository.
set -euo pipefail

targets=$1
out=$2
owner=${GITHUB_REPOSITORY_OWNER:?}
tools=$(dirname "$0")/tools.tsv
mkdir -p "$out"

source_spec() {
  local kind=$1 name=$2
  case $kind in
    npm)
      cat <<EOF
    kind: npm
    spec:
      name: '$name'
      versionfilter:
        kind: semver
EOF
      ;;
    githubrelease)
      cat <<EOF
    kind: githubrelease
    spec:
      owner: ${name%%/*}
      repository: ${name#*/}
      token: '{{ requiredEnv "UPDATECLI_GITHUB_TOKEN" }}'
      versionfilter:
        kind: semver
    transformers:
      - trimprefix: v
EOF
      ;;
    *)
      echo "render.sh: unknown source kind $kind" >&2
      exit 1
      ;;
  esac
}

cut -f1-3 "$targets" | sort -u | while IFS=$'\t' read -r tool repo branch; do
  IFS=$'\t' read -r _ action kind name _ _ < <(grep -P "^$tool\t" "$tools")
  {
    cat <<EOF
---
name: 'ci: bump $tool'
pipelineid: $tool

scms:
  default:
    kind: github
    spec:
      owner: $owner
      repository: $repo
      branch: $branch
      user: femiwiki-pat-owner[bot]
      email: 204444552+femiwiki-pat-owner[bot]@users.noreply.github.com
      token: '{{ requiredEnv "UPDATECLI_GITHUB_TOKEN" }}'

actions:
  default:
    kind: github/pullrequest
    scmid: default
    spec:
      labels:
        - dependencies

sources:
  release:
    name: Latest $tool release
EOF
    source_spec "$kind" "$name"
    echo
    echo 'targets:'
    i=0
    awk -F'\t' -v t="$tool" -v r="$repo" '$1 == t && $2 == r { print $4 }' "$targets" |
      while read -r path; do
        cat <<EOF
  workflow$i:
    name: 'ci: bump $tool to {{ source "release" }}'
    kind: file
    scmid: default
    sourceid: release
    spec:
      file: $path
      matchpattern: '(uses: $action@[^\n]*\n[ \t]+with:\n(?:[ \t]+[a-z-]+:[^\n]*\n)*?[ \t]+version:[ \t]*)[^\s#]+'
      replacepattern: '\${1}{{ source "release" }}'
EOF
        i=$((i + 1))
      done
  } > "$out/$tool-$repo.yaml"
done
