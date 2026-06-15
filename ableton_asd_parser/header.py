from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class HeaderInfo:
    version: int
    magic: str
    overview_table_slots: int
    reserved: int
    overview_scale: int
    overview_positions: tuple[int, ...]
    frame_count: int | None
    overview_bin_count: int | None
    footer_fields: tuple[int, ...]
    schema_start: int


def _find_schema_start(data: bytes) -> int:
    """Locate the root `SampleData` schema type definition."""
    marker = b"\x00\x0aSampleData"
    index = data.find(marker)
    if index >= 0:
        return index
    fallback = data.find(b"SampleData")
    return fallback if fallback >= 0 else len(data)


def parse_header(data: bytes) -> HeaderInfo:
    if len(data) < 14:
        raise ValueError(f"ASD too small ({len(data)} bytes)")

    version = data[0]
    if data[1] != ord("I"):
        raise ValueError(
            f"Unexpected ASD marker byte {data[1]:#02x} (expected 'I' / 0x49)"
        )

    overview_table_slots = struct.unpack_from("<H", data, 2)[0]
    magic = f"I/{overview_table_slots}"

    reserved, overview_scale = struct.unpack_from("<II", data, 4)
    schema_start = _find_schema_start(data)

    table_len = overview_table_slots - 2
    if table_len < 1:
        raise ValueError(f"Invalid overview table slot count: {overview_table_slots}")

    table_end = 14 + table_len * 4
    if table_end > len(data):
        raise ValueError(
            f"Overview table overruns file ({table_end} bytes needed, {len(data)} available)"
        )

    table_values = list(struct.unpack_from(f"<{table_len}I", data, 14))
    overview_positions = tuple(table_values[:-1])
    frame_count = table_values[-1]

    overview_bin_count: int | None = None
    footer: list[int] = []
    tail_start = table_end
    if tail_start + 16 <= len(data) and tail_start < schema_start:
        z0, z1, bin_count, field4 = struct.unpack_from("<IIII", data, tail_start)
        footer.extend([z0, z1, bin_count, field4])
        if bin_count == len(overview_positions):
            overview_bin_count = bin_count
        tail_start += 16
        while tail_start + 4 <= len(data) and tail_start < schema_start:
            footer.append(struct.unpack_from("<I", data, tail_start)[0])
            tail_start += 4

    return HeaderInfo(
        version=version,
        magic=magic,
        overview_table_slots=overview_table_slots,
        reserved=reserved,
        overview_scale=overview_scale,
        overview_positions=overview_positions,
        frame_count=frame_count,
        overview_bin_count=overview_bin_count,
        footer_fields=tuple(footer),
        schema_start=schema_start,
    )
