"""Regression tests against real Ableton .asd fixtures shipped in tests/fixtures/."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ableton_asd_parser import parse_asd

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"


def _load_manifest() -> list[dict]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("manifest.json must contain a list")
    return payload


class RealFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = _load_manifest()
        cls.fixture_paths = sorted(FIXTURES_DIR.glob("*.asd"))
        manifest_names = {entry["file"] for entry in cls.manifest}
        fixture_names = {path.name for path in cls.fixture_paths}
        missing_manifest = fixture_names - manifest_names
        missing_files = manifest_names - fixture_names
        if missing_manifest or missing_files:
            raise unittest.SkipTest(
                "fixtures/ and manifest.json are out of sync: "
                f"missing manifest entries={sorted(missing_manifest)!r}, "
                f"missing files={sorted(missing_files)!r}. "
                "Run: python tests/regenerate_manifest.py"
            )

    def test_fixture_count(self) -> None:
        self.assertGreaterEqual(len(self.manifest), 10)

    def test_all_manifest_entries(self) -> None:
        for entry in self.manifest:
            with self.subTest(file=entry["file"]):
                path = FIXTURES_DIR / entry["file"]
                self.assertTrue(path.is_file(), f"missing fixture: {path.name}")

                info = parse_asd(path)

                self.assertEqual(info.size, entry["size"])
                self.assertEqual(info.version, entry["version"])
                self.assertEqual(info.magic, entry["magic"])
                self.assertEqual(info.frame_count, entry["frame_count"])
                self.assertEqual(len(info.overview_positions), entry["overview_bins"])
                self.assertEqual(len(info.warp_markers), entry["warp_markers"])
                self.assertEqual(len(info.overview_levels), entry["overview_levels"])
                self.assertGreaterEqual(len(info.schema_types), entry["schema_types_min"])
                self.assertIn("SampleData", info.schema_types)
                self.assertTrue(info.structurally_parsed)
                self.assertEqual(
                    set(info.property_names),
                    {member.name for schema_type in info.schema for member in schema_type.members},
                )

                if entry.get("implied_tempo_bpm") is not None:
                    tempo = info.implied_tempo_bpm()
                    self.assertIsNotNone(tempo)
                    self.assertAlmostEqual(tempo, entry["implied_tempo_bpm"], places=3)

                if info.overview_positions and info.frame_count is not None:
                    self.assertLess(info.overview_positions[0], info.frame_count)
                    self.assertLessEqual(info.overview_positions[-1], info.frame_count)
                    for prev, curr in zip(
                        info.overview_positions,
                        info.overview_positions[1:],
                    ):
                        self.assertLess(prev, curr)


if __name__ == "__main__":
    unittest.main()
