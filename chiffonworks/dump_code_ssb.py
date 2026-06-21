#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path


PRINTABLE_ASCII = set(range(0x20, 0x7F))


def read_words(path: Path) -> list[int]:
    data = path.read_bytes()
    if len(data) % 4:
        raise ValueError(f"{path} size is not aligned to 4 bytes: {len(data)}")
    return list(struct.unpack(f"<{len(data) // 4}I", data))


def dump_words_csv(words: list[int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["word_index", "byte_offset", "u32_hex", "u32_dec", "signed_dec"])
        for index, value in enumerate(words):
            signed = value if value < 0x80000000 else value - 0x100000000
            writer.writerow([index, index * 4, f"{value:08X}", value, signed])


def dump_words_txt(words: list[int], out_path: Path, columns: int = 4) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fp:
        for base in range(0, len(words), columns):
            chunk = words[base : base + columns]
            values = " ".join(f"{value:08X}" for value in chunk)
            fp.write(f"{base * 4:08X}: {values}\n")


def extract_sjis_strings(path: Path, out_path: Path, min_chars: int = 4) -> None:
    data = path.read_bytes()
    strings: list[tuple[int, str]] = []
    start: int | None = None
    buf = bytearray()

    def flush() -> None:
        nonlocal start, buf
        if start is not None and len(buf) >= min_chars:
            try:
                text = bytes(buf).decode("cp932")
            except UnicodeDecodeError:
                text = bytes(buf).decode("cp932", errors="ignore")
            if len(text.strip()) >= min_chars:
                strings.append((start, text))
        start = None
        buf = bytearray()

    i = 0
    while i < len(data):
        b = data[i]
        if b in PRINTABLE_ASCII:
            if start is None:
                start = i
            buf.append(b)
            i += 1
            continue

        if (
            i + 1 < len(data)
            and ((0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC))
            and ((0x40 <= data[i + 1] <= 0x7E) or (0x80 <= data[i + 1] <= 0xFC))
        ):
            if start is None:
                start = i
            buf.extend(data[i : i + 2])
            i += 2
            continue

        flush()
        i += 1

    flush()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fp:
        for offset, text in strings:
            fp.write(f"0x{offset:08X}\t{text}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dump SaiSys CODE.SSB as 32-bit VM words and optionally extract DATA.SSB strings."
    )
    parser.add_argument("--code", type=Path, default=Path("SCRIPT") / "CODE.SSB")
    parser.add_argument("--data", type=Path, default=Path("SCRIPT_resource") / "DATA.SSB")
    parser.add_argument("--out", type=Path, default=Path("CODE_dump"))
    args = parser.parse_args()

    words = read_words(args.code)
    args.out.mkdir(parents=True, exist_ok=True)
    dump_words_txt(words, args.out / "CODE_words.txt")
    dump_words_csv(words, args.out / "CODE_words.csv")

    if args.data.is_file():
        extract_sjis_strings(args.data, args.out / "DATA_strings_sjis.txt")

    print(f"CODE.SSB words: {len(words)}")
    print(f"wrote {args.out / 'CODE_words.txt'}")
    print(f"wrote {args.out / 'CODE_words.csv'}")
    if args.data.is_file():
        print(f"wrote {args.out / 'DATA_strings_sjis.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
