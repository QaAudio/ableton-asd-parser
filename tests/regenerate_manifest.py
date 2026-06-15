#!/usr/bin/env python3
"""Rebuild tests/fixtures/manifest.json from the bundled .asd files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_asd_parser import parse_asd  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"


def main() -> int:
    entries = []
    for path in sorted(FIXTURES_DIR.glob("*.asd")):
        info = parse_asd(path)
        entries.append(
            {
                "file": path.name,
                "size": info.size,
                "version": info.version,
                "magic": info.magic,
                "frame_count": info.frame_count,
                "overview_bins": len(info.overview_positions),
                "warp_markers": len(info.warp_markers),
                "implied_tempo_bpm": info.implied_tempo_bpm(),
                "overview_levels": len(info.overview_levels),
                "schema_types_min": 5,
            }
        )

    MANIFEST_PATH.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
