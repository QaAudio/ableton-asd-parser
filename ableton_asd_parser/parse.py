from __future__ import annotations

import json
import wave
from pathlib import Path

from .header import parse_header
from .markers import parse_warp_markers
from .model import AsdFile
from .schema import parse_overview_levels, scan_property_names, scan_schema_types


def read_wav_info(path: str | Path) -> dict[str, int | float]:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        return {
            "sample_rate": rate,
            "channels": handle.getnchannels(),
            "sample_width_bytes": handle.getsampwidth(),
            "frames": frames,
            "duration_seconds": frames / rate if rate else 0.0,
        }


def parse_asd(path: str | Path, *, wav_path: str | Path | None = None) -> AsdFile:
    data = Path(path).read_bytes()
    header = parse_header(data)

    companion: dict[str, int | float] | None = None
    if wav_path is not None:
        companion = read_wav_info(wav_path)

    return AsdFile(
        path=str(path),
        size=len(data),
        version=header.version,
        magic=header.magic,
        reserved=header.reserved,
        overview_scale=header.overview_scale,
        overview_positions=list(header.overview_positions),
        frame_count=header.frame_count,
        overview_bin_count=header.overview_bin_count,
        footer_fields=list(header.footer_fields),
        warp_markers=parse_warp_markers(data),
        overview_levels=parse_overview_levels(data),
        schema_types=scan_schema_types(data),
        property_names=scan_property_names(data),
        companion_wav=companion,
    )


def format_text(info: AsdFile) -> str:
    lines: list[str] = []
    lines.append(f"File: {info.path}")
    lines.append(f"Size: {info.size} bytes")
    lines.append("")
    lines.append("[Header]")
    lines.append(f"  version:         {info.version}")
    lines.append(f"  magic:           {info.magic!r}")
    lines.append(f"  overview_scale:  {info.overview_scale} (0x{info.overview_scale:x})")
    lines.append(f"  overview_bins:   {len(info.overview_positions)}")
    lines.append(f"  frame_count:     {info.frame_count}")
    if info.overview_bin_count is not None:
        lines.append(f"  bin_count field: {info.overview_bin_count}")
    if info.footer_fields:
        lines.append(f"  footer u32s:     {info.footer_fields}")

    if info.companion_wav:
        lines.append("")
        lines.append("[Companion WAV]")
        for key, value in info.companion_wav.items():
            lines.append(f"  {key}: {value}")
        wav_frames = info.companion_wav.get("frames")
        if isinstance(wav_frames, int) and info.frame_count is not None:
            match = "yes" if wav_frames == info.frame_count else "NO"
            lines.append(f"  frame_count matches ASD: {match}")

    lines.append("")
    lines.append(f"[Warp markers] ({len(info.warp_markers)})")
    for index, marker in enumerate(info.warp_markers):
        lines.append(
            f"  [{index}] @{marker.offset:#x}  sec={marker.seconds:.9f}  beats={marker.beats:.9f}"
        )
        if index > 0:
            bpm = marker.implied_bpm_after(info.warp_markers[index - 1])
            if bpm is not None:
                lines.append(f"        implied BPM after previous: {bpm:.3f}")

    tempo = info.implied_tempo_bpm()
    if tempo is not None:
        lines.append(f"  first-segment tempo: {tempo:.3f} BPM")

    lines.append("")
    lines.append(f"[Overview levels] ({len(info.overview_levels)})")
    for level in info.overview_levels:
        preview = ", ".join(f"{value:.5f}" for value in level.values[:8])
        suffix = " ..." if len(level.values) > 8 else ""
        lines.append(
            f"  @{level.offset:#x}  {level.sample_count} floats: {preview}{suffix}"
        )

    lines.append("")
    lines.append(f"[Schema types] ({len(info.schema_types)})")
    lines.append("  " + ", ".join(info.schema_types))

    lines.append("")
    lines.append(f"[Property names] ({len(info.property_names)})")
    chunk = info.property_names[:20]
    lines.append("  " + ", ".join(chunk))
    if len(info.property_names) > 20:
        lines.append(f"  ... and {len(info.property_names) - 20} more")

    return "\n".join(lines)


def format_json(info: AsdFile) -> str:
    payload = {
        "path": info.path,
        "size": info.size,
        "header": {
            "version": info.version,
            "magic": info.magic,
            "reserved": info.reserved,
            "overview_scale": info.overview_scale,
            "overview_positions": info.overview_positions,
            "frame_count": info.frame_count,
            "overview_bin_count": info.overview_bin_count,
            "footer_fields": info.footer_fields,
        },
        "companion_wav": info.companion_wav,
        "warp_markers": [
            {
                "offset": marker.offset,
                "seconds": marker.seconds,
                "beats": marker.beats,
            }
            for marker in info.warp_markers
        ],
        "implied_tempo_bpm": info.implied_tempo_bpm(),
        "overview_levels": [
            {
                "offset": level.offset,
                "sample_count": level.sample_count,
                "values": list(level.values),
            }
            for level in info.overview_levels
        ],
        "schema_types": info.schema_types,
        "property_names": info.property_names,
    }
    return json.dumps(payload, indent=2)
