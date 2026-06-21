#!/usr/bin/env python3
import argparse
from pathlib import Path


XOR_KEY = 0xAA


def pack_data_ssb(src: Path, dst: Path) -> None:
    data = bytearray(src.read_bytes())
    for i, value in enumerate(data):
        data[i] = value ^ XOR_KEY

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack SaiSys SCRIPT_resource/DATA.SSB back to encrypted DATA.SSB."
    )
    parser.add_argument(
        "src",
        nargs="?",
        type=Path,
        default=Path("SCRIPT_resource") / "DATA.SSB",
        help="decrypted DATA.SSB path",
    )
    parser.add_argument(
        "dst",
        nargs="?",
        type=Path,
        default=Path("SCRIPT") / "DATA.SSB",
        help="packed DATA.SSB output path",
    )
    args = parser.parse_args()

    if not args.src.is_file():
        raise SystemExit(f"missing input file: {args.src}")

    pack_data_ssb(args.src, args.dst)
    print(f"packed {args.src} -> {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
