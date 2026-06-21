#!/usr/bin/env python3
import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR.parent / "DATA_text_dump" / "DATA_text.csv"
SSB_PATH = BASE_DIR / "DATA02.SSB"
ORIG_JSON_PATH = BASE_DIR / "extracted_text.json"
CHS_JSON_PATH = BASE_DIR / "extracted_text_chs.json"
UIF_TABLE_PATH = BASE_DIR / "hanzi2kanji_table.txt"
OUT_PATH = BASE_DIR / "DATA01.SSB"
REPORT_PATH = BASE_DIR / "DATA01_pack_report.json"


ALIGN_REPLACEMENTS = {
    "\u301c": "\uff5e",
    "\u339d": "p",
    "\u2212": "\uff0d",
    "\u2015": "\u2014",
}

PUNCT_REPLACEMENTS = {
    "\u00b7": "\u30fb",
    "\u2014": "\u30fc",
}


@dataclass
class TextRow:
    index: int
    offset: int
    length: int
    csv_text: str
    raw_text: str
    prefix: str = ""
    suffix: str = ""
    segments: list[tuple[int, int, str, int]] = field(default_factory=list)


def load_uif_table(path: Path) -> dict[str, str]:
    table = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        src, dst = line.split("\t", 1)
        table[src] = dst
    return table


def align_norm(text: str) -> str:
    text = text.strip(" \t\r\n\u3000")
    for src, dst in ALIGN_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def uif_text(text: str, table: dict[str, str]) -> str:
    text = "".join(table.get(ch, ch) for ch in text)
    for src, dst in PUNCT_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def split_affixes(raw_text: str, csv_text: str) -> tuple[str, str]:
    start = raw_text.find(csv_text)
    if start < 0:
        return "", ""
    end = start + len(csv_text)
    return raw_text[:start], raw_text[end:]


def build_norm_map(text: str) -> tuple[str, list[int]]:
    norm_chars = []
    raw_indices = []
    for i, ch in enumerate(text):
        if ch in " \t\r\n\u3000":
            continue
        mapped = ALIGN_REPLACEMENTS.get(ch, ch)
        for out_ch in mapped:
            norm_chars.append(out_ch)
            raw_indices.append(i)
    return "".join(norm_chars), raw_indices


def find_raw_span(row_text: str, target: str, search_start: int) -> tuple[int, int] | None:
    target_norm = align_norm(target).replace(" ", "").replace("\t", "")
    row_norm, raw_indices = build_norm_map(row_text[search_start:])
    pos = row_norm.find(target_norm)
    if pos < 0:
        return None
    raw_start = search_start + raw_indices[pos]
    raw_end = search_start + raw_indices[pos + len(target_norm) - 1] + 1
    return raw_start, raw_end


def load_rows(ssb: bytes) -> list[TextRow]:
    rows = []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fp:
        for item in csv.DictReader(fp):
            offset = int(item["offset_dec"])
            length = int(item["length"])
            raw = ssb[offset : offset + length].decode("cp932")
            csv_text = item["text"]
            prefix, suffix = split_affixes(raw, csv_text)
            rows.append(
                TextRow(
                    index=int(item["index"]),
                    offset=offset,
                    length=length,
                    csv_text=csv_text,
                    raw_text=raw,
                    prefix=prefix,
                    suffix=suffix,
                )
            )
    return rows


def align_replacements(rows: list[TextRow], orig: list[dict], chs: list[dict]) -> dict:
    json_index = 0
    row_index = 0
    full_matches = 0
    partial_matches = 0
    skipped_rows = 0
    unmatched_json = []

    while json_index < len(orig) and row_index < len(rows):
        original = orig[json_index].get("message", "")
        translated = chs[json_index].get("message", "")

        matched = False
        while row_index < len(rows):
            row = rows[row_index]
            if align_norm(row.csv_text) == align_norm(original):
                row.segments = [(0, len(row.csv_text), translated, json_index)]
                full_matches += 1
                matched = True
                break

            span = find_raw_span(row.csv_text, original, 0)
            if span is not None:
                row.segments.append((*span, translated, json_index))
                partial_matches += 1
                matched = True
                break

            skipped_rows += 1
            row_index += 1

        if not matched:
            unmatched_json.append(json_index)
            json_index += 1
            continue

        json_index += 1

        # Allow more extracted segments to be replaced inside the same CSV string.
        search_start = rows[row_index].segments[-1][1]
        while json_index < len(orig):
            span = find_raw_span(rows[row_index].csv_text, orig[json_index].get("message", ""), search_start)
            if span is None:
                break
            rows[row_index].segments.append((*span, chs[json_index].get("message", ""), json_index))
            partial_matches += 1
            search_start = span[1]
            json_index += 1

        row_index += 1

    if json_index < len(orig):
        unmatched_json.extend(range(json_index, len(orig)))

    return {
        "json_entries": len(orig),
        "csv_rows": len(rows),
        "full_matches": full_matches,
        "partial_matches": partial_matches,
        "matched_json_entries": full_matches + partial_matches,
        "unmatched_json_entries": len(unmatched_json),
        "unmatched_json_indices": unmatched_json[:100],
        "skipped_csv_rows_kept_original": skipped_rows + max(0, len(rows) - row_index),
    }


def apply_segments(row: TextRow, table: dict[str, str]) -> str:
    if not row.segments:
        return row.csv_text

    out = []
    cursor = 0
    for start, end, translated, _json_index in sorted(row.segments, key=lambda item: item[0]):
        if start < cursor:
            continue
        out.append(row.csv_text[cursor:start])
        out.append(uif_text(translated, table))
        cursor = end
    out.append(row.csv_text[cursor:])
    return "".join(out)


def validate_cp932(rows: list[TextRow], table: dict[str, str]) -> list[dict]:
    failures = []
    for row in rows:
        text = row.prefix + apply_segments(row, table) + row.suffix
        try:
            text.encode("cp932")
        except UnicodeEncodeError as exc:
            failures.append(
                {
                    "row_index": row.index,
                    "offset": row.offset,
                    "text": text,
                    "error": str(exc),
                }
            )
    return failures


def rebuild_ssb(ssb: bytes, rows: list[TextRow], table: dict[str, str]) -> bytes:
    out = bytearray()
    cursor = 0
    for row in rows:
        out.extend(ssb[cursor : row.offset])
        new_text = row.prefix + apply_segments(row, table) + row.suffix
        out.extend(new_text.encode("cp932"))
        cursor = row.offset + row.length
    out.extend(ssb[cursor:])
    return bytes(out)


def truncate_cp932(text: str, byte_limit: int) -> bytes:
    out = bytearray()
    for ch in text:
        encoded = ch.encode("cp932")
        if len(out) + len(encoded) > byte_limit:
            break
        out.extend(encoded)
    return bytes(out)


TAIL_CLOSERS = "」』）】》〉〕］｝)]"
TAIL_PUNCT = "。？！!?…ー～"


def protected_tail(text: str) -> str:
    if not text or text[-1] not in TAIL_CLOSERS:
        return ""

    start = len(text) - 1
    while start > 0 and text[start - 1] in TAIL_PUNCT:
        start -= 1
    return text[start:]


def truncate_cp932_keep_tail(text: str, byte_limit: int) -> bytes:
    encoded = text.encode("cp932")
    if len(encoded) <= byte_limit:
        return encoded

    tail = protected_tail(text)
    if not tail:
        return truncate_cp932(text, byte_limit)

    tail_bytes = tail.encode("cp932")
    if len(tail_bytes) >= byte_limit:
        closer = text[-1].encode("cp932")
        if len(closer) > byte_limit:
            return truncate_cp932(text, byte_limit)
        return truncate_cp932(text[: -1], byte_limit - len(closer)) + closer

    head = truncate_cp932(text[: -len(tail)], byte_limit - len(tail_bytes))
    if tail[0] in TAIL_PUNCT:
        head_text = head.decode("cp932", errors="ignore")
        if head_text and head_text[-1] in TAIL_PUNCT:
            head = head_text[:-1].encode("cp932")
    return head + tail_bytes


def encode_fixed_length(row: TextRow, table: dict[str, str]) -> tuple[bytes, bool]:
    text_body = apply_segments(row, table)
    prefix = row.prefix.encode("cp932")
    suffix = row.suffix.encode("cp932")
    if len(prefix) + len(suffix) > row.length:
        return b"\x00" * row.length, True

    body_limit = row.length - len(prefix) - len(suffix)
    body = truncate_cp932_keep_tail(text_body, body_limit)
    raw = prefix + body + suffix
    truncated = len((row.prefix + text_body + row.suffix).encode("cp932")) > row.length
    return raw.ljust(row.length, b"\x00"), truncated


def rebuild_ssb_fixed(ssb: bytes, rows: list[TextRow], table: dict[str, str]) -> tuple[bytes, int]:
    out = bytearray(ssb)
    truncated_rows = 0
    for row in rows:
        if not row.segments:
            continue
        encoded, truncated = encode_fixed_length(row, table)
        out[row.offset : row.offset + row.length] = encoded
        if truncated:
            truncated_rows += 1
    return bytes(out), truncated_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack translated DATA.SSB text using CSV offsets.")
    parser.add_argument(
        "--mode",
        choices=("truncate", "rebuild"),
        default="truncate",
        help="truncate keeps original offsets/file size; rebuild allows strings to change size",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_PATH,
        help="output SSB path",
    )
    parser.add_argument(
        "--ssb",
        type=Path,
        default=SSB_PATH,
        help="source SSB path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORT_PATH,
        help="output JSON report path",
    )
    args = parser.parse_args()

    ssb = args.ssb.read_bytes()
    rows = load_rows(ssb)
    orig = json.loads(ORIG_JSON_PATH.read_text(encoding="utf-8"))
    chs = json.loads(CHS_JSON_PATH.read_text(encoding="utf-8"))
    if len(orig) != len(chs):
        raise SystemExit(f"JSON entry count mismatch: {len(orig)} != {len(chs)}")

    table = load_uif_table(UIF_TABLE_PATH)
    report = align_replacements(rows, orig, chs)

    failures = validate_cp932(rows, table)
    report["cp932_failures"] = failures[:50]
    report["cp932_failure_count"] = len(failures)
    if failures:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(f"cp932 validation failed: {len(failures)} rows; see {args.report}")

    if args.mode == "truncate":
        packed, truncated_rows = rebuild_ssb_fixed(ssb, rows, table)
        report["mode"] = "truncate"
        report["truncated_rows"] = truncated_rows
    else:
        packed = rebuild_ssb(ssb, rows, table)
        report["mode"] = "rebuild"
        report["truncated_rows"] = 0

    args.out.write_bytes(packed)
    report["input_size"] = len(ssb)
    report["output_size"] = len(packed)
    report["changed_rows"] = sum(1 for row in rows if row.segments)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {args.out}")
    print(f"wrote {args.report}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
