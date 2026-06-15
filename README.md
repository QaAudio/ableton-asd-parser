# ableton-asd-parser

Read Ableton Live **`.asd`** analysis sidecars — the hidden files Live creates next to audio samples (`kick.wav.asd`, `vocal.aif.asd`, …).

Ableton uses them to cache waveform overviews, warp markers, loop points, and other clip metadata so samples load quickly without re-analysis. The format is proprietary and undocumented. This project reverse-engineers the **Live 11+ v6** layout and exposes a small Python library plus a CLI inspector.

> **Read-only.** This tool inspects existing files. It does not write or modify `.asd` sidecars.

---

## Install

```bash
git clone https://github.com/QaAudio/ableton-asd-parser.git
cd ableton-asd-parser
pip install -e .
```

No runtime dependencies beyond the Python standard library.

---

## CLI

```bash
# Human-readable summary (auto-detects companion .wav / .aif when present)
asd-dump "/path/to/sample.wav.asd"

# Machine-readable output
asd-dump "/path/to/sample.wav.asd" --json

# Explicit audio file for cross-check
asd-dump "/path/to/sample.wav.asd" --wav "/path/to/sample.wav"
```

Without installing, run as a module from the repo root:

```bash
python -m ableton_asd_parser "/path/to/sample.wav.asd"
```

### Example output

```
File: sample.wav.asd
Size: 9752 bytes

[Header]
  version:         6
  magic:           'I/103'
  overview_scale:  65536 (0x10000)
  overview_bins:   100
  frame_count:     92496

[Companion WAV]
  sample_rate: 44100
  frames: 92496
  frame_count matches ASD: yes

[Warp markers] (2)
  [0] @0xd0a  sec=0.000000000  beats=2.756462548
  [1] @0xd2a  sec=0.012500000  beats=2.787712548
        implied BPM after previous: 150.000
  first-segment tempo: 150.000 BPM
```

---

## Python API

```python
from ableton_asd_parser import parse_asd, format_json

info = parse_asd("sample.wav.asd", wav_path="sample.wav")

print(info.version)          # 6
print(info.frame_count)      # 92496
print(info.warp_markers)     # [WarpMarker(seconds=0.0, beats=2.756…, offset=3338), …]
print(info.implied_tempo_bpm())  # 150.0

print(format_json(info))
```

### Types

| Symbol | Description |
|--------|-------------|
| `AsdFile` | Parsed sidecar: header, markers, overview levels, schema scan |
| `WarpMarker` | `(seconds, beats)` pair at a file offset |
| `OverviewLevel` | Decoded `SampleOverViewLevel` float envelope chunk |

---

## What gets parsed

| Region | Contents |
|--------|----------|
| **Header** | Version byte, `I` marker, overview table length, scale factor |
| **Overview index** | Monotonic audio frame indices for waveform preview bins |
| **Schema graph** | Type tags (`RemoteableDouble`, `WarpMarker`, `SampleData`, …) and UTF-16 property names |
| **Warp markers** | Audio time vs musical beat pairs; tempo derivable between consecutive markers |
| **Overview levels** | Normalized float envelopes used for fast waveform display |

Many typed property **values** (loop points, warp on/off, tempo detection) are identified by name but not fully decoded yet — contributions welcome.

---

## Format notes (v6)

```
 offset  field
 ─────────────────────────────────────────
 0       u8   version (6)
 1       u8   'I' (0x49)
 2       u16  overview_table_slots (bin count + 2)
 4       u32  reserved (0)
 8       u32  overview_scale (often 65536)
 14      u32[] overview frame indices + terminal frame count
 …       footer + typed binary schema (Live 11+)
```

Schema entries use ASCII type names (`WarpMarker`, `RemoteableDouble`, …). Warp marker **instances** store two little-endian `float64` values after a fixed header; schema templates use the tag `WarpMarker\x02\x00\x00\x00` and are skipped.

Tested against **12 bundled real fixtures** (short clips through ~8.5k overview bins) plus additional samples during development.

---

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite includes:

- **Synthetic unit tests** — minimal hand-built v6 blobs (`test_parser.py`)
- **Real fixtures** — 12 Live-recorded `.asd` sidecars in `tests/fixtures/` (~2 MB), validated via `tests/fixtures/manifest.json`

After adding or replacing fixtures, refresh the manifest:

```bash
python tests/regenerate_manifest.py
```

---

## Prior art

- [DBraun/AbletonParsing](https://github.com/DBraun/AbletonParsing) — Live 9/10 warp marker heuristics; partially overlaps with newer files.
- Community notes on `.asd` files as analysis caches (tempo, warp, loop metadata).

---

## Status

Experimental reverse-engineering project. Ableton may change the binary layout in future Live versions. If something breaks on your files, please open an issue with the Live version and a minimal `.asd` sample.
