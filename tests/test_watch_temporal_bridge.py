"""Contracts for Watch temporal bridge: no invented actions or stale pixels."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.watch_temporal_bridge import EvidenceError, load_observations, plan_pairs


class TemporalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "frames").mkdir()
        frames = []
        for index, ms in enumerate((1000, 1500, 9000), start=1):
            name = f"frames/f_{index}.jpg"
            data = f"frame {index}".encode()
            (self.root / name).write_bytes(data)
            frames.append({
                "id": f"frame-{index:04d}", "file": name,
                "source_seconds": ms / 1000,
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        self.timeline = {"schema": "beast.watch.timeline/v3", "frames": frames}
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        (self.root / "timeline.json").write_text(json.dumps(self.timeline), encoding="utf-8")

    def test_grounded_pairs_and_gap(self):
        pairs = plan_pairs(load_observations(self.root))
        self.assertEqual([p["gap_ms"] for p in pairs], [500, 7500])
        self.assertEqual([p["status"] for p in pairs], ["unverified_observation", "needs_reinspection"])
        self.assertEqual(pairs[0]["permitted_claim"], "visual_state_difference_only")
        self.assertIn("keypress", pairs[0]["forbidden_claims"])

    def test_tamper_rejected(self):
        (self.root / "frames/f_1.jpg").write_bytes(b"modified")
        with self.assertRaises(EvidenceError):
            load_observations(self.root)

    def test_path_escape_rejected(self):
        self.timeline["frames"][0]["file"] = "../outside"
        self.save()
        with self.assertRaises(EvidenceError):
            load_observations(self.root)

    def test_missing_hash_rejected(self):
        del self.timeline["frames"][0]["sha256"]
        self.save()
        with self.assertRaises(EvidenceError):
            load_observations(self.root)

    def test_old_schema_rejected(self):
        self.timeline["schema"] = "beast.watch.timeline/v2"
        self.save()
        with self.assertRaises(EvidenceError):
            load_observations(self.root)

    def test_duplicate_ids_rejected(self):
        self.timeline["frames"][1]["id"] = self.timeline["frames"][0]["id"]
        self.save()
        with self.assertRaises(EvidenceError):
            load_observations(self.root)

    def test_bad_gap_rejected(self):
        with self.assertRaises(ValueError):
            plan_pairs([], max_gap_ms=0)


if __name__ == "__main__":
    unittest.main()
