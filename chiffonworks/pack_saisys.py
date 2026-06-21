#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


XOR_KEY = 0xAA


def xor_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(src.read_bytes())
    for i, value in enumerate(data):
        data[i] = value ^ XOR_KEY
    dst.write_bytes(data)


def pack_grd(src_dir: Path, dst_dir: Path) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(src_dir.glob("*.png")):
        shutil.copyfile(src, dst_dir / src.stem)
        count += 1
    return count


def pack_script(src_dir: Path, dst_dir: Path, code_src: Path | None) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    data_src = src_dir / "DATA.SSB"
    if data_src.exists():
        xor_file(data_src, dst_dir / "DATA.SSB")
        count += 1

    if code_src and code_src.exists():
        shutil.copyfile(code_src, dst_dir / "CODE.SSB")
        count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack SaiSys GRD and SCRIPT resources back to engine files."
    )
    parser.add_argument("--grd-resource", type=Path, default=Path("GRD_resource"))
    parser.add_argument("--script-resource", type=Path, default=Path("SCRIPT_resource"))
    parser.add_argument("--out-grd", type=Path, default=Path("GRD_packed"))
    parser.add_argument("--out-script", type=Path, default=Path("SCRIPT_packed"))
    parser.add_argument(
        "--code",
        type=Path,
        default=Path("SCRIPT") / "CODE.SSB",
        help="CODE.SSB is not transformed by the SaiSys crass plugin; copy it if present.",
    )
    args = parser.parse_args()

    if not args.grd_resource.is_dir():
        raise SystemExit(f"missing GRD resource directory: {args.grd_resource}")
    if not args.script_resource.is_dir():
        raise SystemExit(f"missing SCRIPT resource directory: {args.script_resource}")

    grd_count = pack_grd(args.grd_resource, args.out_grd)
    script_count = pack_script(args.script_resource, args.out_script, args.code)

    print(f"packed {grd_count} GRD files to {args.out_grd}")
    print(f"packed {script_count} SCRIPT files to {args.out_script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
