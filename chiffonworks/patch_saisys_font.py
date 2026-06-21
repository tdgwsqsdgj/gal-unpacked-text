#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


OLD_FONT_BYTES = (
    b"\x82\x6c\x82\x72\x20\x82\x6f\x83\x53\x83\x56\x83\x62\x83\x4e",
    b"\x82\x6c\x82\x72\x20\x83\x53\x83\x56\x83\x62\x83\x4e",
)


def patch_font(exe_path: Path, font_name: str, out_path: Path | None) -> int:
    new_bytes = font_name.encode("ascii")

    data = bytearray(exe_path.read_bytes())
    total_count = 0

    for old_bytes in OLD_FONT_BYTES:
        if len(new_bytes) > len(old_bytes):
            raise SystemExit(
                f"{font_name!r} is {len(new_bytes)} bytes, too long for "
                f"{len(old_bytes)}-byte font slot"
            )

        replacement = new_bytes.ljust(len(old_bytes), b"\x00")
        count = data.count(old_bytes)
        total_count += count
        data = data.replace(old_bytes, replacement)

    if total_count == 0:
        raise SystemExit("font marker not found")

    if out_path is None:
        backup = exe_path.with_suffix(exe_path.suffix + ".bak")
        if not backup.exists():
            shutil.copyfile(exe_path, backup)
        out_path = exe_path

    out_path.write_bytes(data)
    return total_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch embedded SaiSys Delphi form font name in SAISYS.EXE."
    )
    parser.add_argument("--exe", type=Path, default=Path("SAISYS.EXE"))
    parser.add_argument(
        "--font",
        default="SimHei",
        help="ASCII font face name; must be 13 bytes or shorter, e.g. SimHei, SimSun",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write patched exe to another path; default patches SAISYS.EXE and creates SAISYS.EXE.bak",
    )
    args = parser.parse_args()

    if not args.exe.is_file():
        raise SystemExit(f"missing exe: {args.exe}")

    count = patch_font(args.exe, args.font, args.out)
    target = args.out if args.out else args.exe
    print(f"patched {count} font name occurrence(s)")
    print(f"output: {target}")
    if args.out is None:
        print(f"backup: {args.exe.with_suffix(args.exe.suffix + '.bak')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
