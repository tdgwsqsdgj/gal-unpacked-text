#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
import json

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def pack_text_to_ssb(ssb_file, json_file, output_file):
    """将文本打包回 SSB 文件"""
    # 读取原始 SSB 文件
    with open(ssb_file, 'rb') as f:
        data = bytearray(f.read())

    # 读取修改后的文本
    with open(json_file, 'r', encoding='utf-8') as f:
        texts = json.load(f)

    # 定义名字的字节模式
    name_patterns = {
        '美雨': b'\x94\xfc\x89\x4a',
        '主人公': b'\x8e\xe5\x90\x6c\x8c\xf6',
        '志摩子': b'\x8e\x75\x96\x80\x8e\x71',
        '謎の男': b'\x93\xe4\x82\xcc\x92\x6a',
        '天狗': b'\x93\x56\x8a\xb0',
        '男Ｂ': b'\x92\x6a\x82\x61',
    }

    # 找到所有文本的位置
    text_positions = []
    for name, pattern_bytes in name_patterns.items():
        pos = 0
        while pos < len(data):
            idx = data.find(pattern_bytes, pos)
            if idx == -1:
                break

            pattern_len = len(pattern_bytes)

            # 格式1: 模式 + 8140 + 文本 + 0000
            if idx + pattern_len + 2 <= len(data):
                if data[idx + pattern_len:idx + pattern_len + 2] == b'\x81\x40':
                    text_start = idx + pattern_len + 2
                    text_end = data.find(b'\x00', text_start)
                    if text_end != -1:
                        text_positions.append({
                            'name': name,
                            'start': text_start,
                            'end': text_end,
                            'format': '8140'
                        })
                        pos = text_end + 1
                        continue

            # 格式2: 模式 + 0d00 + 0000 + 8175 + 文本 + 0000
            if idx + pattern_len + 6 <= len(data):
                if data[idx + pattern_len:idx + pattern_len + 2] == b'\x0d\x00':
                    if data[idx + pattern_len + 2:idx + pattern_len + 4] == b'\x00\x00':
                        if data[idx + pattern_len + 4:idx + pattern_len + 6] == b'\x81\x75':
                            text_start = idx + pattern_len + 6
                            text_end = data.find(b'\x00', text_start)
                            if text_end != -1:
                                text_positions.append({
                                    'name': name,
                                    'start': text_start,
                                    'end': text_end,
                                    'format': '0d00_0000_8175'
                                })
                                pos = text_end + 1
                                continue

            # 格式3: 模式 + 0d00 + 8175 + 文本 + 0000
            if idx + pattern_len + 4 <= len(data):
                if data[idx + pattern_len:idx + pattern_len + 2] == b'\x0d\x00':
                    if data[idx + pattern_len + 2:idx + pattern_len + 4] == b'\x81\x75':
                        text_start = idx + pattern_len + 4
                        text_end = data.find(b'\x00', text_start)
                        if text_end != -1:
                            text_positions.append({
                                'name': name,
                                'start': text_start,
                                'end': text_end,
                                'format': '0d00_8175'
                            })
                            pos = text_end + 1
                            continue

            # 格式4: 模式 + 0d00 + 其他内容
            if idx + pattern_len + 2 <= len(data):
                if data[idx + pattern_len:idx + pattern_len + 2] == b'\x0d\x00':
                    text_start = idx + pattern_len + 2
                    text_end = data.find(b'\x00', text_start)
                    if text_end != -1:
                        text_positions.append({
                            'name': name,
                            'start': text_start,
                            'end': text_end,
                            'format': '0d00'
                        })
                        pos = text_end + 1
                        continue

            pos = idx + pattern_len

    # 创建文本索引
    text_index = 0
    replaced_count = 0
    for pos_info in text_positions:
        if text_index >= len(texts):
            break

        # 检查名字是否匹配
        if pos_info['name'] != texts[text_index]['name']:
            continue

        # 获取原始文本和新文本
        original_text = data[pos_info['start']:pos_info['end']].decode('shift_jis', errors='ignore')
        new_text = texts[text_index]['message']

        # 如果文本相同，跳过
        if original_text == new_text:
            text_index += 1
            continue

        # 编码新文本
        new_text_bytes = new_text.encode('shift_jis', errors='ignore')

        # 替换文本
        # 注意：如果新文本比原始文本长，需要扩展文件
        # 如果新文本比原始文本短，需要填充 0x00
        if len(new_text_bytes) <= (pos_info['end'] - pos_info['start']):
            # 新文本较短，填充 0x00
            data[pos_info['start']:pos_info['start'] + len(new_text_bytes)] = new_text_bytes
            data[pos_info['start'] + len(new_text_bytes):pos_info['end']] = b'\x00' * (pos_info['end'] - pos_info['start'] - len(new_text_bytes))
        else:
            # 新文本较长，需要扩展
            # 这种情况下，我们需要重新构建文件
            # 为了简化，我们截断新文本
            new_text_bytes = new_text_bytes[:pos_info['end'] - pos_info['start']]
            data[pos_info['start']:pos_info['end']] = new_text_bytes

        replaced_count += 1
        text_index += 1

    # 保存为新文件
    with open(output_file, 'wb') as f:
        f.write(data)

    print(f"打包完成！共替换 {replaced_count} 条文本")
    print(f"结果已保存到 {output_file}")

def main():
    ssb_file = "DATA.SSB"
    json_file = "extracted_text.json"
    output_file = "DATA1.SSB"

    pack_text_to_ssb(ssb_file, json_file, output_file)

if __name__ == "__main__":
    main()
