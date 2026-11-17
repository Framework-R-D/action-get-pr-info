"""Test PR metadata policy and the data-only handoff to inline API glue."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pr_metadata import (
    event_pr_number,
    prepare_snapshot,
    read_snapshot,
    validate_metadata,
    write_outputs,
)

SHA = "a" * 40
BASE = "b" * 40
ROOT = Path(__file__).parents[1]


class PrMetadataTests(unittest.TestCase):
    """Preserve PR outputs while keeping validation out of JavaScript."""

    def setUp(self) -> None:
        """Create sentinel-only event and metadata fixtures in a private workspace."""
        temporary = tempfile.TemporaryDirectory(prefix="pr-metadata-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.event = {"issue": {"number": 1, "pull_request": {}}}
        self.metadata = {
            "head": {"ref": "feature/test", "sha": SHA, "repo": {"full_name": "Fork/target"}},
            "base": {"sha": BASE, "repo": {"full_name": "Example/target"}},
        }

    def test_one_snapshot_preserves_all_existing_outputs(self) -> None:
        """The branch and immutable SHA remain separate and coherent."""
        self.assertEqual(
            validate_metadata(self.metadata, "Example/target"),
            {"ref": "feature/test", "sha": SHA, "repo": "Fork/target", "base_sha": BASE},
        )

    def test_malformed_or_deleted_head_metadata_is_rejected(self) -> None:
        """Reject every malformed field covered by the previous Node fixture."""
        for change in [
            {"ref": "feature\nsha=spoof"},
            {"sha": ""},
            {"sha": "0" * 40},
            {"repo": None},
            {"repo": {"full_name": "X/../target"}},
            {"ref": "x:refs/heads/main"},
        ]:
            metadata = copy.deepcopy(self.metadata)
            metadata["head"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_metadata(metadata, "Example/target")
        metadata = copy.deepcopy(self.metadata)
        metadata["base"]["repo"]["full_name"] = "Other/target"
        with self.assertRaises(ValueError):
            validate_metadata(metadata, "Example/target")

    def test_invalid_event_numbers_fail_before_request_preparation(self) -> None:
        """An authenticated comment alone cannot supply arbitrary API route values."""
        for number in [None, False, 0, -1, 1.5, "1\nspoof=true", 2**53]:
            with self.subTest(number=number), self.assertRaises(ValueError):
                prepare_snapshot(
                    self.root,
                    {"issue": {"number": number, "pull_request": {}}},
                    "issue_comment",
                    "Example/target",
                )
        with self.assertRaises(ValueError):
            event_pr_number({"issue": {"number": 1}}, "issue_comment")
        self.assertEqual(event_pr_number({"pull_request": {"number": 1}}, "pull_request"), 1)

    def test_handoff_paths_are_private_and_invocation_unique(self) -> None:
        """No PR-controlled value becomes a metadata destination."""
        first = prepare_snapshot(self.root, self.event, "issue_comment", "Example/target")
        second = prepare_snapshot(self.root, self.event, "issue_comment", "Example/target")
        self.assertNotEqual(first["path"], second["path"])
        snapshot = Path(first["path"])
        self.assertTrue(snapshot.parent.is_relative_to(self.root.resolve()))
        self.assertEqual(snapshot.parent.stat().st_mode & 0o777, 0o700)
        self.assertFalse(snapshot.exists())
        self.assertEqual(first["pr_number"], "1")

    def test_snapshot_symlinks_and_path_escapes_are_rejected(self) -> None:
        """Metadata consumption cannot read a replacement path outside its directory."""
        values = prepare_snapshot(self.root, self.event, "issue_comment", "Example/target")
        snapshot = Path(values["path"])
        victim = self.root / "victim.json"
        victim.write_text(json.dumps(self.metadata))
        snapshot.symlink_to(victim)
        with self.assertRaises(OSError):
            read_snapshot(snapshot, self.root)
        with self.assertRaises(ValueError):
            read_snapshot(self.root.parent / "metadata.json", self.root)

    def test_metadata_must_be_bounded_json_object(self) -> None:
        """Large files and non-object responses do not produce action outputs."""
        values = prepare_snapshot(self.root, self.event, "issue_comment", "Example/target")
        snapshot = Path(values["path"])
        for data in ["[]", "x" * (8 * 1024 * 1024 + 1)]:
            snapshot.write_text(data)
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                read_snapshot(snapshot, self.root)

    def test_output_injection_does_not_partially_publish(self) -> None:
        """Validate the entire output mapping before appending runner commands."""
        output = self.root / "outputs"
        output.write_text("existing=value\n")
        with self.assertRaises(ValueError):
            write_outputs(output, {"sha": SHA, "ref": "feature\rspoof=true"})
        self.assertEqual(output.read_text(), "existing=value\n")

    def test_cli_runs_without_node_and_consumes_one_snapshot(self) -> None:
        """Exercise the same Python entry points used around the tiny API step."""
        event = self.root / "event.json"
        event.write_text(json.dumps(self.event))
        prepared = self.root / "prepared"
        environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.root),
            "RUNNER_TEMP": str(self.root),
            "GITHUB_REPOSITORY": "Example/target",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_EVENT_PATH": str(event),
            "GITHUB_OUTPUT": str(prepared),
            "PYTHONPATH": str(self.root),
        }
        sentinel = self.root / "executed"
        (self.root / "sitecustomize.py").write_text(f"open({str(sentinel)!r}, 'w').close()\n")
        command = [sys.executable, "-I", str(ROOT / "pr_metadata.py")]
        result = subprocess.run(
            command + ["--prepare"], env=environment, cwd=self.root, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        values = dict(line.split("=", 1) for line in prepared.read_text().splitlines())
        snapshot = Path(values["path"])
        snapshot.write_text(json.dumps(self.metadata))
        output = self.root / "outputs"
        result = subprocess.run(
            command,
            cwd=self.root,
            capture_output=True,
            text=True,
            env=environment | {"GITHUB_OUTPUT": str(output), "METADATA_PATH": str(snapshot)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(sentinel.exists())
        self.assertFalse(snapshot.exists())
        self.assertEqual(
            dict(line.split("=", 1) for line in output.read_text().splitlines()),
            validate_metadata(self.metadata, "Example/target"),
        )

    def test_inline_glue_only_transports_metadata(self) -> None:
        """The SDK call serializes data and cannot publish unchecked public outputs."""
        action = (ROOT / "action.yaml").read_text()
        glue = action.split("    - name: Fetch PR metadata", 1)[1].split(
            "    - name: Validate PR metadata", 1
        )[0]
        self.assertEqual(glue.count("github.rest.pulls.get("), 1)
        self.assertIn("pull_number: Number(process.env.PR_NUMBER)", glue)
        self.assertIn("JSON.stringify({ head: pr.data.head, base: pr.data.base })", glue)
        self.assertIn("flag: 'wx'", glue)
        self.assertNotIn("core.setOutput", glue)
        self.assertNotIn("RegExp", glue)
        self.assertNotIn("pr_info.test.cjs", (ROOT / ".github/workflows/ci.yaml").read_text())


if __name__ == "__main__":
    unittest.main()
