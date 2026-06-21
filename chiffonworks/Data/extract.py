#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, io, json, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CG_CODES = [
    "お風呂　　１", "お風呂　　２",
    "寝室　　　１", "寝室　　　２", "寝室　　　３", "寝室　　　４",
    "居間　　　１", "居間　　　２",
    "プール", "横溝先生", "旅館トイレ",
    "旅館　　　１", "旅館　　　２",
    "倉庫", "ゆか", "住宅街",
    "車内　　　１", "車内　　　２",
    "路地裏", "天狗", "教会",
]

def extract_text_from_ssb(filename):
    with open(filename, 'rb') as f:
        data = f.read()

    results = []
    current_speaker = None
    pos = 0

    student_speaker_aliases = {
        "Ａ": "女学生Ａ",
        "A": "女学生Ａ",
        "Ｂ": "女学生Ｂ",
        "B": "女学生Ｂ",
        "Ｃ": "女学生Ｃ",
        "C": "女学生Ｃ",
    }

    def normalize_speaker(name, name_pos):
        # vgak### is the voice tag used by the girl-student lines.
        prev = data[max(0, name_pos - 16):name_pos].split(b"\x00")[-2:]
        if name in student_speaker_aliases and any(part.startswith(b"vgak") for part in prev):
            return student_speaker_aliases[name]
        return name

    # 名字正则：名字 + 0D00 [0000] 8175（对话opcode）
    name_re = re.compile(
        rb'((?:[\x81-\x9F\xE0-\xEF][\x40-\x7E\x80-\xFC]|[\xA1-\xDF]|[A-Za-z0-9])+)'
        rb'\x0D\x00(?:\x00\x00)?\x81\x75'
    )

    while pos < len(data):
        # 检查名字opcode + 0D00 0000 8175
        m = name_re.match(data, pos)
        if m:
            name_bytes = m.group(1)
            try:
                current_speaker = normalize_speaker(
                    name_bytes.decode('shift_jis'),
                    m.start()
                )
            except:
                pos += 1
                continue
            # 跳过名字 + 0D00 或 0D00 0000，停在 8175 位置
            pos = m.end() - 2
            continue

        # 8175（对话 「）
        if data[pos:pos+2] == b'\x81\x75':
            end_8176 = data.find(b'\x81\x76', pos + 2)
            end_00 = data.find(b'\x00', pos + 2)
            if end_8176 != -1 and (end_00 == -1 or end_8176 < end_00):
                text = data[pos:end_8176+2].decode('shift_jis', errors='ignore')
                if text.strip() and text.strip() not in CG_CODES:
                    entry = {"message": text.strip()}
                    if current_speaker:
                        entry["name"] = current_speaker
                    results.append(entry)
                pos = end_8176 + 2
                while pos < len(data) and data[pos] == 0x00:
                    pos += 1
                continue
            elif end_00 != -1:
                text = data[pos:end_00].decode('shift_jis', errors='ignore')
                if text.strip() and text.strip() not in CG_CODES:
                    entry = {"message": text.strip()}
                    if current_speaker:
                        entry["name"] = current_speaker
                    results.append(entry)
                pos = end_00 + 1
                continue

        # 8140（旁白）
        if data[pos:pos+2] == b'\x81\x40':
            text_end = data.find(b'\x00', pos + 2)
            if text_end != -1:
                text = data[pos+2:text_end].decode('shift_jis', errors='ignore')
                if text.strip() and text.strip() not in CG_CODES and len(text.strip()) > 10:
                    results.append({"message": text.strip()})
                pos = text_end + 1
                continue

        pos += 1

    return results


def main():
    results = extract_text_from_ssb("DATA.SSB")

    with open("extracted_text.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"提取完成！共 {len(results)} 条")

    name_counts = {}
    for item in results:
        name = item.get("name", "旁白")
        name_counts[name] = name_counts.get(name, 0) + 1

    print("\n各名字出现次数：")
    for name, count in sorted(name_counts.items(), key=lambda x: -x[1]):
        print(f"  {name}: {count} 条")


if __name__ == "__main__":
    main()
