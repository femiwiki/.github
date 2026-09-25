#!/usr/bin/env python3
"""Print the values bump.yaml renders from: the tools, and every workflow in
the organization that pins one.
GitHub is reached through `gh`, which takes its token from GH_TOKEN."""

import json
import os
import re
import subprocess
import sys

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "femiwiki")


def version_input(action: str) -> str:
    """The action's step down to its version: input."""
    return (
        rf"(uses: {re.escape(action)}@[^\n]*\n[ \t]+with:\n"
        r"(?:[ \t]+[a-z-]+:[^\n]*\n)*?[ \t]+version:[ \t]*)[^\s#]+"
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
    "rumdl": {
        "uses": r"uses: rvben/rumdl@",
        "pattern": version_input("rvben/rumdl"),
        "repository": "rvben/rumdl",
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


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


targets = []
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
    for f in files:
        if not f["name"].endswith((".yml", ".yaml")):
            continue
        raw = gh(
            "api",
            f"repos/{OWNER}/{name}/contents/{f['path']}?ref={branch}",
            "-H",
            "Accept: application/vnd.github.raw",
        )
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

json.dump({"owner": OWNER, "tools": TOOLS, "targets": targets}, sys.stdout, indent=2)
