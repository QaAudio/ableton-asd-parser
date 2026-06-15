from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class ByteReader:
    """Bounds-checked little-endian cursor over ASD bytes."""

    data: bytes
    pos: int = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def peek_u8(self) -> int:
        self._require(1)
        return self.data[self.pos]

    def u8(self) -> int:
        self._require(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def u16(self) -> int:
        self._require(2)
        value = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return value

    def u32(self) -> int:
        self._require(4)
        value = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return value

    def f32(self) -> float:
        self._require(4)
        value = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return value

    def f64(self) -> float:
        self._require(8)
        value = struct.unpack_from("<d", self.data, self.pos)[0]
        self.pos += 8
        return value

    def bytes(self, count: int) -> bytes:
        self._require(count)
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def ascii_pstr(self) -> str:
        length = self.u8()
        if length == 0:
            return ""
        raw = self.bytes(length)
        return raw.decode("ascii")

    def utf16_pstr(self) -> str:
        char_count = self.u32()
        if char_count == 0:
            return ""
        raw = self.bytes(char_count * 2)
        return raw.decode("utf-16-le")

    def matches(self, pattern: bytes) -> bool:
        if self.pos + len(pattern) > len(self.data):
            return False
        return self.data[self.pos : self.pos + len(pattern)] == pattern

    def find(self, pattern: bytes, start: int | None = None) -> int:
        if start is None:
            start = self.pos
        return self.data.find(pattern, start)

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self.data):
            raise ValueError(f"seek out of range: {pos}")
        self.pos = pos

    def _require(self, count: int) -> None:
        if self.pos + count > len(self.data):
            raise ValueError(
                f"ASD underrun at {self.pos:#x}: need {count} bytes, have {self.remaining}"
            )
