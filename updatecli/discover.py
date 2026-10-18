#!/usr/bin/env python3
"""Print the values bump.yaml renders from: the tools, every workflow in the
organization that pins one, and every workflow that pins a reusable workflow of
this repository.
GitHub is reached through `gh`, which takes its token from GH_TOKEN."""

import json
import os
import re
import subprocess
import sys

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "femiwiki")


def version_input(action: str, lead: str = "") -> str:
    """The action's step down to its version: input, and lead, which the pin
    keeps in front of the version."""
    return (
        rf"(uses: {re.escape(action)}@[^\n]*\n[ \t]+with:\n"
        r"(?:[ \t]+[a-z-]+:[^\n]*\n)*?[ \t]+version:[ \t]*"
        rf"{re.escape(lead)})[^\s#]+"
    )


# uses: what shows a workflow installs the tool. pattern: the pinned version,
# right after group 1; updatecli matches it with Go's regexp, which reads it the
# same as Python's. repository: where the releases are, tagged
# "<prefix><version>".
TOOLS = {
    "biome": {
        "uses": r"uses: biomejs/setup-biome@",
        "pattern": version_input("biomejs/setup-biome"),
        "repository": "biomejs/biome",
        "prefix": "@biomejs/biome@",
    },
    "golangci-lint": {
        "uses": r"uses: golangci/golangci-lint-action@",
        "pattern": version_input("golangci/golangci-lint-action", "v"),
        "repository": "golangci/golangci-lint",
        "prefix": "v",
    },
    "rumdl": {
        "uses": r"uses: rvben/rumdl@",
        "pattern": version_input("rvben/rumdl"),
        "repository": "rvben/rumdl",
        "prefix": "v",
    },
    "yamllint": {
        "uses": r"\byamllint==",
        "pattern": r"(--spec yamllint==)[^\s]+",
        "repository": "adrienverge/yamllint",
        "prefix": "v",
    },
    # Installed by shivammathur/setup-php's tools: input.
    "parallel-lint": {
        "uses": r"tools:[^\n]*\bparallel-lint\b",
        "pattern": r"(tools:[^\n]*\bparallel-lint:)[^\s,]+",
        "repository": "php-parallel-lint/PHP-Parallel-Lint",
        "prefix": "v",
    },
}


# A call of one of this repository's reusable workflows, pinned to a commit; the
# commit is group 2. A branch or tag ref is left alone.
SHARED = rf"(uses: {OWNER}/\.github/\.github/workflows/[^@\s]+@)([0-9a-f]{{40}})\b"


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


targets = []
pins = []
repos = gh(
    "repo",
    "list",
    OWNER,
    "--no-archived",
    "--source",
    "--limit",
    "1000",
    "--json",
    "name,defaultBranchRef",
)
for repo in json.loads(repos):
    if not repo["defaultBranchRef"]:
        continue  # empty repository
    name, branch = repo["name"], repo["defaultBranchRef"]["name"]
    try:
        files = json.loads(
            gh("api", f"repos/{OWNER}/{name}/contents/.github/workflows?ref={branch}")
        )
    except subprocess.CalledProcessError:
        continue  # no workflows
    paths = {tool: [] for tool in TOOLS}
    pinned = {}
    for f in files:
        if not f["name"].endswith((".yml", ".yaml")):
            continue
        raw = gh(
            "api",
            f"repos/{OWNER}/{name}/contents/{f['path']}?ref={branch}",
            "-H",
            "Accept: application/vnd.github.raw",
        )
        if shas := {m[1] for m in re.findall(SHARED, raw)}:
            pinned[f["path"]] = shas
        for tool, spec in TOOLS.items():
            if re.search(spec["pattern"], raw):
                paths[tool].append(f["path"])
            elif re.search(spec["uses"], raw):
                print(
                    f"::warning::{name}/{f['path']} installs {tool} with no pinned version to bump",
                    file=sys.stderr,
                )
    targets += [
        {"tool": t, "repo": name, "branch": branch, "paths": p}
        for t, p in paths.items()
        if p
    ]
    if pinned:
        pins.append(
            {
                "repo": name,
                "branch": branch,
                "paths": list(pinned),
                "shas": sorted(set().union(*pinned.values())),
            }
        )

json.dump(
    {
        "owner": OWNER,
        "tools": TOOLS,
        "targets": targets,
        "shared": {"pattern": SHARED},
        "pins": pins,
    },
    sys.stdout,
    indent=2,
)
