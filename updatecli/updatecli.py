#!/usr/bin/env python3
"""Bump tool versions that workflows across the organization pin as an
action input, which no package manager reads.

    updatecli.py discover > targets.json        workflows that pin a tool
    updatecli.py repos targets.json             their repositories, comma-separated
    updatecli.py render targets.json DIR        one updatecli manifest per tool and repository
    updatecli.py release-notes targets.json     release notes on the pull requests updatecli opened

GitHub is reached through `gh`, which takes its token from GH_TOKEN.
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter
from pathlib import Path

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "femiwiki")
TOKEN = '{{ requiredEnv "UPDATECLI_GITHUB_TOKEN" }}'
SEMVER = {"kind": "semver"}


@dataclass(frozen=True)
class Tool:
    action: str
    source: dict
    upstream: str
    tag_prefix: str


TOOLS = {
    "biome": Tool(
        action="biomejs/setup-biome",
        source={
            "kind": "npm",
            "spec": {"name": "@biomejs/biome", "versionfilter": SEMVER},
        },
        upstream="biomejs/biome",
        tag_prefix="@biomejs/biome@",
    ),
    "rumdl": Tool(
        action="rvben/rumdl",
        source={
            "kind": "githubrelease",
            "spec": {
                "owner": "rvben",
                "repository": "rumdl",
                "token": TOKEN,
                "versionfilter": SEMVER,
            },
            "transformers": [{"trimprefix": "v"}],
        },
        upstream="rvben/rumdl",
        tag_prefix="v",
    ),
}


def pinned(action: str) -> str:
    """The action's step down to its version: input. Written for Go's regexp,
    which updatecli matches with, and read the same way by Python's."""
    return (
        rf"(uses: {re.escape(action)}@[^\n]*\n[ \t]+with:\n"
        r"(?:[ \t]+[a-z-]+:[^\n]*\n)*?[ \t]+version:[ \t]*)[^\s#]+"
    )


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def gh_api(path: str, raw: bool = False):
    out = gh(
        "api", path, *(["-H", "Accept: application/vnd.github.raw"] if raw else [])
    )
    return out if raw else json.loads(out)


def warn(message: str) -> None:
    print(f"::warning::{message}", file=sys.stderr)


def discover() -> list[dict]:
    """Every workflow that pins a tool's version through its action. A use of
    the action without a version: input has nothing to bump and is warned about."""
    repos = json.loads(
        gh(
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
    )
    targets = []
    for repo in repos:
        if not repo["defaultBranchRef"]:
            continue  # empty repository
        name, branch = repo["name"], repo["defaultBranchRef"]["name"]
        try:
            files = gh_api(
                f"repos/{OWNER}/{name}/contents/.github/workflows?ref={branch}"
            )
        except subprocess.CalledProcessError:
            continue  # no workflows
        for f in files:
            if not f["name"].endswith((".yml", ".yaml")):
                continue
            body = gh_api(
                f"repos/{OWNER}/{name}/contents/{f['path']}?ref={branch}", raw=True
            )
            for tool, spec in TOOLS.items():
                if f"uses: {spec.action}@" not in body:
                    continue
                if re.search(pinned(spec.action), body):
                    targets.append(
                        {
                            "tool": tool,
                            "repo": name,
                            "branch": branch,
                            "path": f["path"],
                        }
                    )
                else:
                    warn(
                        f"{name}/{f['path']} uses {spec.action} without a version: input, so it is left alone"
                    )
    return targets


def groups(targets: list[dict]):
    """(tool, repo, branch) and the workflow paths under it."""
    key = itemgetter("tool", "repo", "branch")
    for (tool, repo, branch), items in groupby(sorted(targets, key=key), key=key):
        yield tool, repo, branch, [t["path"] for t in items]


def manifest(tool: str, repo: str, branch: str, paths: list[str]) -> dict:
    """One pull request carrying the tool to its latest release in every
    workflow of the repository that pins it."""
    spec = TOOLS[tool]
    title = f'ci: bump {tool} to {{{{ source "release" }}}}'
    return {
        "name": f"ci: bump {tool}",
        "pipelineid": tool,
        "scms": {
            "default": {
                "kind": "github",
                "spec": {
                    "owner": OWNER,
                    "repository": repo,
                    "branch": branch,
                    "user": "femiwiki-pat-owner[bot]",
                    "email": "204444552+femiwiki-pat-owner[bot]@users.noreply.github.com",
                    "token": TOKEN,
                },
            }
        },
        "actions": {
            "default": {
                "kind": "github/pullrequest",
                "scmid": "default",
                "spec": {"labels": ["dependencies"]},
            }
        },
        "sources": {"release": {"name": f"Latest {tool} release", **spec.source}},
        "targets": {
            f"workflow{i}": {
                "name": title,
                "kind": "file",
                "scmid": "default",
                "sourceid": "release",
                "spec": {
                    "file": path,
                    "matchpattern": pinned(spec.action),
                    "replacepattern": '${1}{{ source "release" }}',
                },
            }
            for i, path in enumerate(paths)
        },
    }


def to_yaml(value, indent: int = 0) -> str:
    """Block YAML with every string single-quoted. updatecli runs its
    templates over the text before parsing it and writes {{ source "..." }}
    back with double quotes, which a double-quoted (or JSON) string would not
    survive."""
    pad = "  " * indent
    if isinstance(value, dict):
        return "".join(
            f"{pad}{k}:\n{to_yaml(v, indent + 1)}"
            if isinstance(v, (dict, list))
            else f"{pad}{k}: {to_yaml(v)}\n"
            for k, v in value.items()
        )
    if isinstance(value, list):
        return "".join(
            f"{pad}-\n{to_yaml(v, indent + 1)}"
            if isinstance(v, (dict, list))
            else f"{pad}- {to_yaml(v)}\n"
            for v in value
        )
    return "'" + str(value).replace("'", "''") + "'"


def render(targets: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for tool, repo, branch, paths in groups(targets):
        (out / f"{tool}-{repo}.yaml").write_text(
            to_yaml(manifest(tool, repo, branch, paths))
        )


def version(text: str) -> tuple[int, ...] | None:
    return (
        tuple(map(int, text.split("."))) if re.fullmatch(r"\d+(\.\d+)*", text) else None
    )


# A later run replaces what sits between these instead of adding a second
# block to a pull request updatecli keeps open.
OPEN, CLOSE = "<!-- femiwiki: release notes -->", "<!-- /femiwiki -->"


def notes(tool: str, old: str, new: str, releases: list[dict]) -> str:
    """The release notes of every release after old up to new, newest first.
    When old is not a version, as for a first pin from `latest`, only new's."""
    spec = TOOLS[tool]
    lo, hi = version(old), version(new)
    crossed = []
    for r in releases:
        if (
            r["draft"]
            or r["prerelease"]
            or not r["tag_name"].startswith(spec.tag_prefix)
        ):
            continue
        v = version(r["tag_name"].removeprefix(spec.tag_prefix))
        if v and v <= hi and (v > lo if lo else v == hi):
            crossed.append((v, r))
    lines = [OPEN, "", "### Release notes", ""]
    if lo:
        base, head = spec.tag_prefix + old, spec.tag_prefix + new
        lines += [
            f"[{base}...{head}](https://github.com/{spec.upstream}/compare/{base}...{head})",
            "",
        ]
    else:
        lines += [f"Pins {tool}, which was `{old}`.", ""]
    for _, r in sorted(crossed, key=lambda c: c[0], reverse=True):
        body = r["body"] or ""
        if len(body) > 4000:
            body = body[:4000] + "\n\n…"
        lines += [
            f'<details><summary><a href="{r["html_url"]}">{r["tag_name"]}</a></summary>',
            "",
            body,
            "",
            "</details>",
            "",
        ]
    lines.append(CLOSE)
    return "\n".join(lines)


def release_notes(targets: list[dict]) -> None:
    """Add to each pull request updatecli opened the notes of the releases it
    crosses. updatecli knows the release it bumps to but not the version it
    replaces, so the range is read off the pull request's diff."""
    for tool, repo, branch, _ in groups(targets):
        slug = f"{OWNER}/{repo}"
        # updatecli names its branch after the base branch and the pipelineid.
        head = f"updatecli_{branch}_{tool}"
        prs = json.loads(
            gh(
                "pr",
                "list",
                "-R",
                slug,
                "--head",
                head,
                "--state",
                "open",
                "--json",
                "number",
            )
        )
        if not prs:
            print(f"{slug}: no open pull request from {head}")
            continue
        number = str(prs[0]["number"])
        diff = gh("pr", "diff", number, "-R", slug)
        old = re.search(r"^-\s*version:\s*([^\s#]+)", diff, re.MULTILINE)
        new = re.search(r"^\+\s*version:\s*([^\s#]+)", diff, re.MULTILINE)
        if not new:
            print(f"{slug}#{number}: no version: line in the diff")
            continue
        old, new = (old[1] if old else ""), new[1]
        block = notes(
            tool,
            old,
            new,
            gh_api(f"repos/{TOOLS[tool].upstream}/releases?per_page=100"),
        )
        body = json.loads(gh("pr", "view", number, "-R", slug, "--json", "body"))[
            "body"
        ]
        kept = re.sub(
            rf"\n*{re.escape(OPEN)}.*?(?:{re.escape(CLOSE)}|\Z)",
            "",
            body,
            flags=re.DOTALL,
        )
        # A pull request body holds 65536 characters.
        gh("pr", "edit", number, "-R", slug, "--body", (kept + "\n\n" + block)[:65000])
        print(f"{slug}#{number}: release notes for {tool} {old} -> {new}")


def main(argv: list[str]) -> None:
    match argv:
        case ["discover"]:
            json.dump(discover(), sys.stdout, indent=2)
        case ["repos", targets]:
            print(
                ",".join(
                    sorted({t["repo"] for t in json.loads(Path(targets).read_text())})
                )
            )
        case ["render", targets, out]:
            render(json.loads(Path(targets).read_text()), Path(out))
        case ["release-notes", targets]:
            release_notes(json.loads(Path(targets).read_text()))
        case _:
            sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
