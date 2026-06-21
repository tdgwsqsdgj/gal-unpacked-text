#!/usr/bin/env python3
import argparse
import csv
import re
import struct
from pathlib import Path


JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\u3000-\u303f\uff01-\uff60]")


def iter_c_strings(data: bytes):
    offset = 0
    for chunk in data.split(b"\x00"):
        if chunk:
            yield offset, chunk
        offset += len(chunk) + 1


def decode_cp932_strings(data: bytes, min_bytes: int):
    rows = []
    for offset, raw in iter_c_strings(data):
        if len(raw) < min_bytes:
            continue
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            continue
        text = text.rstrip("\r\n")
        if JAPANESE_RE.search(text):
            rows.append(
                {
                    "offset": offset,
                    "length": len(raw),
                    "text": text,
                }
            )
    return rows


def count_code_refs(code_path: Path, offsets: set[int]) -> dict[int, int]:
    if not code_path.is_file():
        return {}
    code = code_path.read_bytes()
    if len(code) % 4:
        return {}
    refs = {offset: 0 for offset in offsets}
    for (word,) in struct.iter_unpack("<I", code):
        if word in refs:
            refs[word] += 1
    return refs


def write_text(rows, out_path: Path, refs: dict[int, int]) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as fp:
        for index, row in enumerate(rows):
            offset = row["offset"]
            ref_count = refs.get(offset, 0)
            fp.write(f"[{index:05d}] 0x{offset:08X} len={row['length']} refs={ref_count}\n")
            fp.write(row["text"])
            fp.write("\n\n")


def write_csv(rows, out_path: Path, refs: dict[int, int]) -> None:
    with out_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["index", "offset_hex", "offset_dec", "length", "code_refs", "text"])
        for index, row in enumerate(rows):
            offset = row["offset"]
            writer.writerow(
                [
                    index,
                    f"0x{offset:08X}",
                    offset,
                    row["length"],
                    refs.get(offset, 0),
                    row["text"],
                ]
            )


def write_duplicates(rows, out_path: Path, refs: dict[int, int]) -> None:
    adjacent = []
    for left, right in zip(rows, rows[1:]):
        if left["text"] == right["text"]:
            adjacent.append((left, right))

    all_dups = {}
    for row in rows:
        all_dups.setdefault(row["text"], []).append(row)

    with out_path.open("w", encoding="utf-8", newline="\n") as fp:
        fp.write(f"adjacent_duplicate_pairs={len(adjacent)}\n\n")
        for left, right in adjacent:
            fp.write(
                f"0x{left['offset']:08X} refs={refs.get(left['offset'], 0)} -> "
                f"0x{right['offset']:08X} refs={refs.get(right['offset'], 0)} "
                f"len={left['length']}\n"
            )
            fp.write(left["text"])
            fp.write("\n\n")

        fp.write("\nrepeated_text_groups=\n\n")
        for text, group in sorted(all_dups.items(), key=lambda item: (-len(item[1]), item[1][0]["offset"])):
            if len(group) < 2:
                continue
            offsets = ", ".join(f"0x{row['offset']:08X}" for row in group[:20])
            fp.write(f"count={len(group)} offsets={offsets}\n{text}\n\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract CP932 text strings from SaiSys DATA.SSB.")
    parser.add_argument("--data", type=Path, default=Path("SCRIPT_resource") / "DATA.SSB")
    parser.add_argument("--code", type=Path, default=Path("SCRIPT") / "CODE.SSB")
    parser.add_argument("--out", type=Path, default=Path("DATA_text_dump"))
    parser.add_argument("--min-bytes", type=int, default=4)
    args = parser.parse_args()

    data = args.data.read_bytes()
    rows = decode_cp932_strings(data, args.min_bytes)
    refs = count_code_refs(args.code, {row["offset"] for row in rows})

    args.out.mkdir(parents=True, exist_ok=True)
    write_text(rows, args.out / "DATA_text.txt", refs)
    write_csv(rows, args.out / "DATA_text.csv", refs)
    write_duplicates(rows, args.out / "DATA_duplicates.txt", refs)

    print(f"extracted strings: {len(rows)}")
    print(f"wrote: {args.out / 'DATA_text.txt'}")
    print(f"wrote: {args.out / 'DATA_text.csv'}")
    print(f"wrote: {args.out / 'DATA_duplicates.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
