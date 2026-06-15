from __future__ import annotations

import os
import struct
import tempfile
import unittest

from ableton_asd_parser.header import parse_header
from ableton_asd_parser.markers import parse_warp_markers
from ableton_asd_parser.parse import parse_asd


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _utf16(text: str) -> bytes:
    return _u32(len(text)) + text.encode("utf-16-le")


def _type_def(name: str, members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray()
    out.extend(bytes([0, len(name)]))
    out.extend(name.encode("ascii"))
    out.extend(_u32(len(members)))
    for member_name, type_ref in members:
        out.extend(_utf16(member_name))
        out.extend(type_ref)
    return bytes(out)


def _named_ref(name: str) -> bytes:
    return bytes([0, len(name)]) + name.encode("ascii")


def _build_minimal_asd() -> bytes:
    """Synthetic v6 ASD: header table + schema dictionary + instance region.

    Mirrors the real grammar (version header, type-def stream, then raw-value
    instance data containing tagged WarpMarker and SampleOverViewLevel records).
    """
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

    schema = bytearray()
    # Version header: 00 <len> SampleData <u32 version>
    schema.extend(_named_ref("SampleData"))
    schema.extend(_u32(6))
    # Type dictionary
    schema.extend(_type_def("SampleData", [("LoopStart", _named_ref("RemoteableDouble"))]))
    schema.extend(_type_def("RemoteableDouble", [("Value", bytes([0x17]))]))
    schema.extend(
        _type_def(
            "WarpMarker",
            [("SecTime", bytes([0x17])), ("BeatTime", bytes([0x17]))],
        )
    )
    schema.extend(
        _type_def("SampleOverViewLevel", [("InterleavedBinData", bytes([0x32]))])
    )

    instance = bytearray()
    # Instance region begins with raw values (no type-def pattern).
    instance.extend(struct.pack("<d", 0.0))  # LoopStart value
    instance.extend(struct.pack("<I", 2))  # warp marker list count
    instance.extend(_named_ref("WarpMarker"))
    instance.extend(_u32(0))
    instance.extend(struct.pack("<dd", 0.0, 0.0))
    instance.extend(_named_ref("WarpMarker"))
    instance.extend(_u32(1))
    instance.extend(struct.pack("<dd", 0.5, 1.0))
    instance.extend(_named_ref("SampleOverViewLevel"))
    instance.extend(struct.pack("<II", 2, 2))
    instance.extend(struct.pack("<ff", 0.25, -0.125))

    return bytes(header) + bytes(schema) + bytes(instance)


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
        self.assertEqual(set(info.property_names), {m.name for t in info.schema for m in t.members})


if __name__ == "__main__":
    unittest.main()
