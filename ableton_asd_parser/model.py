from __future__ import annotations

from dataclasses import dataclass, field

from .schema_types import SchemaType


@dataclass(frozen=True)
class WarpMarker:
    """Warp marker: audio seconds vs musical beats (1.1.1 grid)."""

    seconds: float
    beats: float
    offset: int

    def implied_bpm_after(self, previous: WarpMarker) -> float | None:
        delta_s = self.seconds - previous.seconds
        if delta_s <= 0:
            return None
        return (self.beats - previous.beats) / delta_s * 60.0


@dataclass(frozen=True)
class OverviewLevel:
    """One decoded `SampleOverViewLevel` float envelope chunk."""

    offset: int
    sample_count: int
    values: tuple[float, ...]


@dataclass
class AsdFile:
    path: str
    size: int
    version: int
    magic: str
    reserved: int
    overview_scale: int
    overview_positions: list[int] = field(default_factory=list)
    frame_count: int | None = None
    overview_bin_count: int | None = None
    footer_fields: list[int] = field(default_factory=list)
    warp_markers: list[WarpMarker] = field(default_factory=list)
    overview_levels: list[OverviewLevel] = field(default_factory=list)
    schema_types: list[str] = field(default_factory=list)
    property_names: list[str] = field(default_factory=list)
    schema: list[SchemaType] = field(default_factory=list)
    companion_wav: dict[str, int | float] | None = None
    structurally_parsed: bool = False
    parse_warnings: list[str] = field(default_factory=list)

    def implied_tempo_bpm(self) -> float | None:
        if len(self.warp_markers) < 2:
            return None
        return self.warp_markers[1].implied_bpm_after(self.warp_markers[0])
