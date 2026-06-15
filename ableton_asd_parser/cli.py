from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

from .parse import format_json, format_text, parse_asd


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="asd-dump",
        description="Inspect an Ableton Live .asd analysis sidecar file.",
    )
    parser.add_argument("asd_path", type=Path, help="Path to a .asd file")
    parser.add_argument(
        "--wav",
        type=Path,
        default=None,
        help="Companion audio file for cross-check (auto-detected when omitted)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    if not args.asd_path.is_file():
        print(f"error: not a file: {args.asd_path}", file=sys.stderr)
        return 1

    wav_path = args.wav
    if wav_path is None:
        candidate = Path(str(args.asd_path)[: -len(".asd")])
        if candidate.is_file():
            wav_path = candidate

    try:
        info = parse_asd(args.asd_path, wav_path=wav_path)
    except (OSError, ValueError, wave.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(format_json(info) if args.json else format_text(info))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
