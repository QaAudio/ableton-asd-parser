from __future__ import annotations

import re
import struct

from .model import OverviewLevel

_KNOWN_TYPES = (
    b"SampleData",
    b"RemoteableDouble",
    b"RemoteableBool",
    b"RemoteableInt",
    b"RemoteableEnum",
    b"RemoteableList",
    b"RemoteableArray",
    b"RemoteableTimeSignature",
    b"UserFloat",
    b"WarpMarker",
    b"OnsetArray",
    b"OnsetEvent",
    b"OnSets",
    b"AufTaktData",
    b"SampleOverView",
    b"SampleOverViewLevel",
    b"List<SampleOverViewLevel>",
    b"TimeSignatureNumerator",
    b"TimeSignatureDenominator",
)


def scan_schema_types(data: bytes) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for token in _KNOWN_TYPES:
        index = 0
        while True:
            index = data.find(token, index)
            if index < 0:
                break
            name = token.decode("ascii")
            if name not in seen:
                seen.add(name)
                found.append(name)
            index += len(token)
    return sorted(found, key=lambda s: data.find(s.encode("ascii")))


def scan_property_names(data: bytes) -> list[str]:
    names: set[str] = set()
    for index in range(0, len(data) - 8):
        length = struct.unpack_from("<I", data, index)[0]
        if length < 1 or length > 48:
            continue
        end = index + 4 + length * 2
        if end > len(data):
            continue
        raw = data[index + 4 : end]
        if len(raw) % 2:
            continue
        try:
            text = raw.decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        text = text.rstrip("\x00")
        if not text or len(text) != length:
            continue
        if not text[0].isupper():
            continue
        if not all(ch.isalnum() or ch == "_" for ch in text):
            continue
        names.add(text)
    return sorted(names)


def parse_overview_levels(data: bytes) -> list[OverviewLevel]:
    """Best-effort decode of `SampleOverViewLevel` float payloads."""
    tag = b"SampleOverViewLevel"
    levels: list[OverviewLevel] = []
    search_from = 0

    while True:
        index = data.find(tag, search_from)
        if index < 0:
            break
        search_from = index + len(tag)

        cursor = index + len(tag)
        if cursor + 8 > len(data):
            continue

        count, byte_len = struct.unpack_from("<II", data, cursor)
        cursor += 8

        if count not in (1, 2) or byte_len == 0 or byte_len % 4 != 0 or byte_len > 4096:
            continue
        if cursor + byte_len > len(data):
            continue

        payload = data[cursor : cursor + byte_len]
        values = struct.unpack(f"<{byte_len // 4}f", payload)

        if not values:
            continue
        if not all(-1.5 <= value <= 1.5 for value in values):
            continue

        levels.append(
            OverviewLevel(
                offset=index,
                sample_count=len(values),
                values=tuple(float(v) for v in values),
            )
        )

    return levels


def scan_ascii_strings(data: bytes, min_length: int = 6) -> list[str]:
    pattern = re.compile(rb"[\x20-\x7e]{%d,}" % min_length)
    return sorted({match.group().decode("ascii") for match in pattern.finditer(data)})
