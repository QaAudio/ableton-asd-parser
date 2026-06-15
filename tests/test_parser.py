from __future__ import annotations

import os
import struct
import tempfile
import unittest

from ableton_asd_parser.header import parse_header
from ableton_asd_parser.markers import parse_warp_markers
from ableton_asd_parser.parse import parse_asd


def _build_minimal_asd() -> bytes:
    """Synthetic v6 ASD with header table, schema tags, and two warp markers."""
    header = bytearray(438)
    header[0] = 6
    header[1] = ord("I")
    struct.pack_into("<H", header, 2, 7)
    struct.pack_into("<I", header, 8, 65536)

    positions = [1000, 5000, 10000, 20000]
    frame_count = 92496
    cursor = 14
    for value in positions:
        struct.pack_into("<I", header, cursor, value)
        cursor += 4
    struct.pack_into("<I", header, cursor, frame_count)
    cursor += 4
    struct.pack_into("<IIII", header, cursor, 0, 0, len(positions), 4)

    schema = b"SampleData\x13\x00\x00\x00\x00\nSampleData$"
    schema += b"RemoteableDouble"
    schema += struct.pack("<I", 9)
    schema += "LoopStart".encode("utf-16-le")
    schema += struct.pack("<d", 0.0)

    marker_one = b"WarpMarker" + b"\x00" * 4 + struct.pack("<dd", 0.0, 0.0)
    marker_two = b"WarpMarker" + b"\x00" * 4 + struct.pack("<dd", 0.5, 1.0)

    overview = (
        b"SampleOverViewLevel"
        + struct.pack("<II", 1, 8)
        + struct.pack("<ff", 0.25, -0.125)
    )

    return bytes(header) + schema + b"\x00" * 200 + marker_one + marker_two + overview


class AsdParserTests(unittest.TestCase):
    def test_parse_minimal_fixture(self) -> None:
        data = _build_minimal_asd()
        header = parse_header(data)
        self.assertEqual(header.version, 6)
        self.assertEqual(header.magic, "I/7")
        self.assertEqual(header.overview_positions, (1000, 5000, 10000, 20000))
        self.assertEqual(header.frame_count, 92496)
        self.assertEqual(header.overview_bin_count, 4)

        markers = parse_warp_markers(data)
        self.assertEqual(len(markers), 2)
        self.assertAlmostEqual(markers[0].seconds, 0.0)
        self.assertAlmostEqual(markers[1].seconds, 0.5)
        self.assertAlmostEqual(markers[1].implied_bpm_after(markers[0]) or 0.0, 120.0)

    def test_skips_warp_marker_schema_entry(self) -> None:
        blob = (
            b"WarpMarker\x02\x00\x00\x00"
            + b"\xff" * 16
            + b"WarpMarker"
            + b"\x00" * 4
            + struct.pack("<dd", 1.0, 2.0)
        )
        markers = parse_warp_markers(blob)
        self.assertEqual(len(markers), 1)
        self.assertAlmostEqual(markers[0].seconds, 1.0)

    def test_parse_asd_roundtrip_fields(self) -> None:
        data = _build_minimal_asd()
        with tempfile.NamedTemporaryFile(suffix=".asd", delete=False) as handle:
            handle.write(data)
            path = handle.name
        try:
            info = parse_asd(path)
        finally:
            os.unlink(path)

        self.assertEqual(info.version, 6)
        self.assertGreaterEqual(len(info.schema_types), 2)
        self.assertIn("LoopStart", info.property_names)
        self.assertEqual(len(info.warp_markers), 2)
        self.assertEqual(len(info.overview_levels), 1)


if __name__ == "__main__":
    unittest.main()
