"""Validate PR event and snapshot data outside the GitHub API transport glue."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def validate_repository(value: str) -> str:
    """Require a repository identity safe for API routes and runner outputs."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value
    ):
        raise ValueError("Invalid repository")
    if value.split("/")[1] in {".", ".."}:
        raise ValueError("Invalid repository")
    return value


def event_pr_number(event: Mapping[str, Any], event_name: str) -> int:
    """Validate PR identity before allowing the inline API request to run."""
    if event_name == "issue_comment":
        issue = event.get("issue")
        if not isinstance(issue, Mapping) or not isinstance(issue.get("pull_request"), Mapping):
            raise ValueError("Comment is not on a pull request")
    record = event.get("issue", event.get("pull_request", event))
    number = record.get("number") if isinstance(record, Mapping) else None
    if type(number) is not int or not 1 <= number <= 2**53 - 1:
        raise ValueError("A positive PR number is required")
    return number


def prepare_snapshot(
    runner_temp: Path, event: Mapping[str, Any], event_name: str, repository: str
) -> dict[str, str]:
    """Reserve an invocation-unique private location for the metadata response."""
    validate_repository(repository)
    number = event_pr_number(event, event_name)
    if not runner_temp.is_absolute() or re.search(r"[\x00-\x1f\x7f]", str(runner_temp)):
        raise ValueError("Invalid runner temporary directory")
    root = runner_temp.resolve(strict=True)
    folder = Path(tempfile.mkdtemp(prefix="get-pr-info-", dir=root))
    return {"path": str(folder / "metadata.json"), "pr_number": str(number)}


def validate_metadata(metadata: Mapping[str, Any], repository: str) -> dict[str, str]:
    """Publish one coherent API snapshot only after every field is validated."""
    validate_repository(repository)
    head = metadata.get("head")
    base = metadata.get("base")
    if not isinstance(head, Mapping) or not isinstance(base, Mapping):
        raise ValueError("PR snapshot is missing")
    head_repo = head.get("repo")
    base_repo = base.get("repo")
    if not isinstance(head_repo, Mapping) or not isinstance(base_repo, Mapping):
        raise ValueError("PR repository identity is missing")
    head_repository = head_repo.get("full_name")
    if not isinstance(head_repository, str):
        raise ValueError("PR repository identity is missing")
    target_repo = validate_repository(head_repository)
    if base_repo.get("full_name") != repository:
        raise ValueError("PR base repository does not match the requested repository")
    sha = head.get("sha")
    base_sha = base.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == "0" * 40:
        raise ValueError("Invalid PR source SHA")
    if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ValueError("Invalid PR base SHA")
    ref = head.get("ref")
    if (
        not isinstance(ref, str)
        or not ref
        or re.search(r"[\x00-\x20\x7f~^:?*\[\\]", ref)
        or ".." in ref
        or "@{" in ref
        or ref.startswith("-")
        or ref.endswith(".")
        or any(
            not part or part.startswith(".") or part.endswith(".lock") for part in ref.split("/")
        )
    ):
        raise ValueError("Invalid PR branch")
    # Metadata resolution does not approve this repository or SHA for execution.
    return {"ref": ref, "sha": sha, "repo": target_repo, "base_sha": base_sha}


def read_snapshot(snapshot: Path, runner_temp: Path) -> Mapping[str, Any]:
    """Read bounded regular-file metadata without following a replacement symlink."""
    root = runner_temp.resolve(strict=True)
    parent = snapshot.parent.resolve(strict=True)
    if snapshot.name != "metadata.json" or parent == root or not parent.is_relative_to(root):
        raise ValueError("Metadata path escapes its runner temporary directory")
    descriptor = os.open(snapshot, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as response:
        if not stat.S_ISREG(os.fstat(response.fileno()).st_mode):
            raise ValueError("Metadata must be a regular file")
        body = response.read(8 * 1024 * 1024 + 1)
    if len(body) > 8 * 1024 * 1024:
        raise ValueError("Metadata response is too large")
    metadata = json.loads(body)
    if not isinstance(metadata, Mapping):
        raise ValueError("Metadata must be an object")
    return metadata


def write_outputs(output_path: Path, outputs: Mapping[str, str]) -> None:
    """Validate the complete output set before appending any runner commands."""
    for name, value in outputs.items():
        if (
            not re.fullmatch(r"[a-z][a-z0-9_-]*", name)
            or not isinstance(value, str)
            or re.search(r"[\x00-\x1f\x7f]", value)
        ):
            raise ValueError("Invalid action output")
    with output_path.open("a", encoding="utf-8") as output:
        output.write("".join(f"{name}={value}\n" for name, value in outputs.items()))


def main() -> None:
    """Prepare the API handoff or validate the already-fetched metadata snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    runner_temp = Path(os.environ["RUNNER_TEMP"])
    repository = os.environ["GITHUB_REPOSITORY"]
    output_path = Path(os.environ["GITHUB_OUTPUT"])
    if args.prepare:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        outputs = prepare_snapshot(runner_temp, event, os.environ["GITHUB_EVENT_NAME"], repository)
    else:
        snapshot = Path(os.environ["METADATA_PATH"])
        outputs = validate_metadata(read_snapshot(snapshot, runner_temp), repository)
        snapshot.unlink()
    write_outputs(output_path, outputs)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit(
            "PR metadata validation failed closed; verify event and snapshot data"
        ) from None
