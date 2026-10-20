"""Fail-closed publication guards; no network, git writes or uploads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import publish_release


class ReleaseGuards(unittest.TestCase):
    def test_wrong_account_stops_before_reading_or_uploading(self):
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            return json.dumps({"login": "synthetic-other-account", "id": 123}) if args[1:] == ["api", "user"] else ""
        with patch.object(publish_release, "run", side_effect=command), patch.object(publish_release, "public_source_check") as scan:
            with self.assertRaisesRegex(RuntimeError, "Wrong GitHub account"):
                publish_release.publish("fake-gh", Path("absent-report"), Path("unused-stage"))
            scan.assert_not_called()
        self.assertEqual([c[1:] for c in calls], [["auth", "status"], ["api", "user"]])

    def test_changed_asset_blocks_before_any_remote_mutation(self):
        calls = []
        def command(args, **kwargs):
            calls.append(args)
            return json.dumps({"login": "Stigliz81", "id": 123}) if args[1:] == ["api", "user"] else ""
        with tempfile.TemporaryDirectory() as data:
            folder = Path(data)
            report = folder / "VERIFICATION.json"
            report.write_text(json.dumps({"release_gate": {"passed": True, "repository": publish_release.REPO,
                                                          "version": publish_release.APP_VERSION, "assets": {}}}))
            (folder / (publish_release.PACKAGE_STEM + "-Windows-portabel.zip")).write_bytes(b"synthetic changed payload")
            with patch.object(publish_release, "run", side_effect=command), patch.object(publish_release, "public_source_check"):
                with self.assertRaisesRegex(RuntimeError, "changed release asset"):
                    publish_release.publish("fake-gh", report, folder / "stage")
            self.assertFalse((folder / "stage").exists())
        self.assertEqual([c[1:] for c in calls], [["auth", "status"], ["api", "user"]])
