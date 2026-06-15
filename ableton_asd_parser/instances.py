from __future__ import annotations

import math
import struct

from .model import OverviewLevel, WarpMarker
from .reader import ByteReader
from .schema_types import SchemaGraph

_WARP_TAG = b"\x00\x0aWarpMarker"
_WARP_NAME_LEN = len("WarpMarker")
_OVERVIEW_TAG = b"\x00\x13SampleOverViewLevel"
_OVERVIEW_NAME_LEN = len("SampleOverViewLevel")
_SECTIME_MEMBER = struct.pack("<I", 7) + "SecTime".encode("utf-16-le")


def _is_sane_marker(seconds: float, beats: float) -> bool:
    if math.isnan(seconds) or math.isnan(beats):
        return False
    if math.isinf(seconds) or math.isinf(beats):
        return False
    if seconds < 0 or seconds > 86_400:
        return False
    if abs(beats) > 1e7:
        return False
    return True


def _looks_like_warp_type_def(data: bytes, body: int) -> bool:
    """A WarpMarker schema definition: <u32 memberCount><u32 7>'SecTime'."""
    return data[body + 4 : body + 4 + len(_SECTIME_MEMBER)] == _SECTIME_MEMBER


def _read_warp_marker(data: bytes, body: int) -> WarpMarker | None:
    if body + 20 > len(data):
        return None
    seconds, beats = struct.unpack_from("<dd", data, body + 4)
    if not _is_sane_marker(seconds, beats):
        return None
    return WarpMarker(seconds=seconds, beats=beats, offset=body - _WARP_NAME_LEN)


def parse_warp_markers(data: bytes, *, schema_end: int = 0) -> list[WarpMarker]:
    """Read warp-marker instances (``<u32 index><f64 sec><f64 beats>``).

    When ``schema_end`` is known, only the instance region is scanned, so the
    schema definition is never reached. Otherwise the lone schema definition is
    detected by its ``SecTime`` member layout and skipped.
    """
    markers: list[WarpMarker] = []
    search_from = max(schema_end, 0)
    while True:
        index = data.find(b"WarpMarker", search_from)
        if index < 0:
            break
        search_from = index + _WARP_NAME_LEN
        body = index + _WARP_NAME_LEN
        if _looks_like_warp_type_def(data, body):
            continue
        marker = _read_warp_marker(data, body)
        if marker is not None:
            markers.append(marker)

    deduped: list[WarpMarker] = []
    for marker in sorted(markers, key=lambda m: (m.seconds, m.beats, m.offset)):
        if deduped and abs(deduped[-1].seconds - marker.seconds) < 1e-9:
            if abs(deduped[-1].beats - marker.beats) < 1e-9:
                continue
        deduped.append(marker)
    return deduped


def parse_warp_markers_from_instance(
    data: bytes, graph: SchemaGraph
) -> list[WarpMarker]:
    return parse_warp_markers(data, schema_end=graph.schema_end)


def _finite_overview(offset: int, values: tuple[float, ...]) -> OverviewLevel | None:
    """Emit a level only if the declared layout decodes to all-finite floats.

    This is a well-formedness gate, not a value-range guess: if a record does
    not decode cleanly we skip it rather than surface corrupted (NaN/Inf) data.
    """
    if not values or any(not math.isfinite(v) for v in values):
        return None
    return OverviewLevel(offset=offset, sample_count=len(values), values=values)


def _read_overview_level(reader: ByteReader) -> OverviewLevel | None:
    offset = reader.pos
    if not reader.matches(_OVERVIEW_TAG):
        return None
    reader.pos += len(_OVERVIEW_TAG)
    version = reader.u32()
    if version == 2:
        float_count = reader.u32()
        if float_count <= 0 or float_count > 65_536:
            return None
        if reader.remaining < float_count * 4:
            return None
        values = struct.unpack(f"<{float_count}f", reader.bytes(float_count * 4))
        return _finite_overview(offset, tuple(values))
    if version == 1:
        char_count = reader.u32()
        if char_count < 1 or char_count > 64:
            return None
        reader.bytes(char_count * 2)
        byte_len = reader.u32()
        if byte_len <= 0 or byte_len % 4 != 0 or byte_len > 1_048_576:
            return None
        if reader.remaining < byte_len:
            return None
        values = struct.unpack(f"<{byte_len // 4}f", reader.bytes(byte_len))
        return _finite_overview(offset, tuple(values))
    return None


def parse_overview_levels_from_instance(
    data: bytes, graph: SchemaGraph
) -> list[OverviewLevel]:
    """Read tagged ``SampleOverViewLevel`` instances from the instance region.

    Records are read by their declared version layout. Files that inline a
    single overview level without a fresh tag are not separately enumerated.
    """
    levels: list[OverviewLevel] = []
    search_from = max(graph.schema_end, 0)
    while True:
        index = data.find(_OVERVIEW_TAG, search_from)
        if index < 0:
            break
        search_from = index + len(_OVERVIEW_TAG)
        level = _read_overview_level(ByteReader(data, index))
        if level is not None:
            levels.append(level)
    return levels
