from __future__ import annotations

import struct

from .model import WarpMarker

_WARP_MARKER = b"WarpMarker"
_SCHEMA_TAG = b"\x02\x00\x00\x00"


def _is_sane_marker(seconds: float, beats: float) -> bool:
    if seconds < 0 or seconds > 86400:
        return False
    if abs(beats) > 1e7:
        return False
    if seconds != seconds or beats != beats:
        return False
    return True


def parse_warp_markers(data: bytes) -> list[WarpMarker]:
    """Extract warp marker instances from repeated `WarpMarker` records."""
    markers: list[WarpMarker] = []
    search_from = 0

    while True:
        index = data.find(_WARP_MARKER, search_from)
        if index < 0:
            break
        search_from = index + len(_WARP_MARKER)

        if index + 14 <= len(data) and data[index + 10 : index + 14] == _SCHEMA_TAG:
            continue

        body = index + 14
        if body + 16 > len(data):
            continue

        seconds, beats = struct.unpack_from("<dd", data, body)
        if not _is_sane_marker(seconds, beats):
            continue

        markers.append(WarpMarker(seconds=seconds, beats=beats, offset=index))

    deduped: list[WarpMarker] = []
    for marker in sorted(markers, key=lambda m: (m.seconds, m.beats, m.offset)):
        if deduped and abs(deduped[-1].seconds - marker.seconds) < 1e-9:
            if abs(deduped[-1].beats - marker.beats) < 1e-9:
                continue
        deduped.append(marker)

    return deduped
