#!/usr/bin/env python3
"""Battle-test .asd parsing over directory trees."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_asd_parser import parse_asd  # noqa: E402
from ableton_asd_parser.model import AsdFile  # noqa: E402


DEFAULT_ROOTS = [
    Path(r"C:\Users\corbe\Documents\Raven\lets ,qke so,e  noise Project\Samples"),
    Path(r"C:\Users\corbe\Documents\Raven\dark155 Project\Samples"),
]


def _is_clean_identifier(name: str) -> bool:
    if not name or not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(ch.isalnum() or ch == "_" or ch in "<>" for ch in name)


def _heuristic_flags(info: AsdFile) -> list[str]:
    """The 'clean parse' contract: structurally grounded, no garbage data."""
    flags: list[str] = []

    if not info.structurally_parsed:
        flags.append("not structurally parsed")
    if info.parse_warnings:
        flags.append(f"parse_warnings: {info.parse_warnings[:3]}")

    # property_names must be the schema-declared members (no brute-forced noise).
    schema_names = {m.name for t in info.schema for m in t.members}
    if set(info.property_names) != schema_names:
        flags.append("property_names != schema members")
    garbage = [n for n in info.property_names if not _is_clean_identifier(n)]
    if garbage:
        flags.append(f"garbage property names: {garbage[:5]}")

    # schema_types must be exactly the declared dictionary types.
    if set(info.schema_types) != {t.name for t in info.schema}:
        flags.append("schema_types != declared types")
    bad_types = [n for n in info.schema_types if not _is_clean_identifier(n)]
    if bad_types:
        flags.append(f"garbage schema types: {bad_types[:5]}")

    # Records must carry finite, plausible values (no value-range guessing).
    for marker in info.warp_markers:
        if not (math.isfinite(marker.seconds) and math.isfinite(marker.beats)):
            flags.append("non-finite warp marker")
            break
    tempo = info.implied_tempo_bpm()
    if tempo is not None and not (0 < tempo < 100_000):
        flags.append(f"implausible implied tempo: {tempo}")
    for level in info.overview_levels:
        if any(not math.isfinite(v) for v in level.values):
            flags.append("non-finite overview value")
            break

    return flags


def main() -> int:
    parser = argparse.ArgumentParser(description="Battle-test Ableton .asd parsing.")
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        default=DEFAULT_ROOTS,
        help="Directories to scan recursively for .asd files",
    )
    args = parser.parse_args()

    files: list[Path] = []
    for root in args.roots:
        if not root.is_dir():
            print(f"warning: skipping missing directory: {root}", file=sys.stderr)
            continue
        files.extend(sorted(root.rglob("*.asd")))

    if not files:
        print("error: no .asd files found", file=sys.stderr)
        return 1

    errors: list[tuple[Path, str]] = []
    flagged: list[tuple[Path, list[str]]] = []

    with_warp = 0
    with_overview = 0
    all_property_names: set[str] = set()
    all_type_names: set[str] = set()
    max_props = 0

    for path in files:
        try:
            info = parse_asd(path)
        except Exception as error:  # noqa: BLE001 - battle harness reports all failures
            errors.append((path, f"{type(error).__name__}: {error}"))
            continue

        if info.warp_markers:
            with_warp += 1
        if info.overview_levels:
            with_overview += 1
        all_property_names.update(info.property_names)
        all_type_names.update(info.schema_types)
        max_props = max(max_props, len(info.property_names))

        flags = _heuristic_flags(info)
        if flags:
            flagged.append((path, flags))

    print(f"Scanned {len(files)} .asd files across {len(args.roots)} roots")
    print(f"Parse errors: {len(errors)}")
    print(f"Heuristic flags: {len(flagged)}")
    print(
        f"Quality: files with warp markers={with_warp}, with overview levels={with_overview}"
    )
    print(
        f"Schema vocabulary: {len(all_type_names)} distinct types, "
        f"{len(all_property_names)} distinct property names, max props/file={max_props}"
    )

    for path, message in errors[:20]:
        print(f"ERROR {path.name}: {message}")
    if len(errors) > 20:
        print(f"... and {len(errors) - 20} more errors")

    for path, flags in flagged[:20]:
        print(f"FLAG {path.name}: {'; '.join(flags)}")
    if len(flagged) > 20:
        print(f"... and {len(flagged) - 20} more flagged files")

    return 1 if errors or flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
