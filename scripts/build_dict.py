#!/usr/bin/env python3
"""把 AOSP PinyinIME 的明文词典编译成紧凑二进制 assets/pinyin/dict.bin。

源词典（Apache-2.0，来自 AOSP packages/inputmethods/PinyinIME）：
    https://android.googlesource.com/platform/packages/inputmethods/PinyinIME
    文件：app/src/main/cpp/data/rawdict_utf16_65105_freq.txt（UTF-16LE）
    格式：每行「词 频率 词长 音节1 音节2 ...」，音节以空格分隔，ü 记作 v
    例： 爸爸 9814.0643895 0 ba ba

输出格式（小端）：
    magic       4B   "PYD1"
    u32         词条数
    u32         音节数
    u32         音节表偏移（固定 20）
    u32         词条区偏移
    音节表      UTF-8，逗号分隔，按 (长度, 字典序) 排序，便于最长匹配与二分
    词条区      按拼音串字典序排序的变长记录：
                u16 拼音长度 / 拼音 UTF-8 / u16 汉字数 / 汉字 UTF-16LE / f32 频率

排序是必须的：运行时用「拼音前缀」在词条区上二分定位候选区间。

用法：
    python tools/pinyin/build_dict.py <rawdict.txt> <out dict.bin>
"""

import struct
import sys
from pathlib import Path

MAGIC = b"PYD1"


def read_raw_dict(path: Path):
    """解析明文词典，返回 [(词, 频率, 拼音串)]，拼音串是音节直接拼接（无分隔符）。"""
    entries = []
    syllables = set()
    with open(path, encoding="utf-16") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            word, freq, syls = parts[0], parts[1], parts[3:]
            if not word or not syls:
                continue
            pinyin = "".join(syls)
            syllables.update(syls)
            entries.append((word, float(freq), pinyin))
    return entries, syllables


def build(src: Path, dst: Path) -> None:
    entries, syllables = read_raw_dict(src)
    # 同一个拼音可能对应多个词（同音字/同音词），按拼音再按频率降序排，
    # 保证高频词落在区间前部，二分定位到的区间里前排就是好候选
    entries.sort(key=lambda e: (e[2], -e[1]))
    syl_sorted = sorted(syllables, key=lambda s: (len(s), s))

    head = 20  # magic(4) + entryCount(4) + sylCount(4) + sylOffset(4) + entriesOffset(4)
    syl_blob = ",".join(syl_sorted).encode("utf-8")
    # 4 字节对齐，词条区起始
    entries_offset = head + len(syl_blob)
    entries_offset += (4 - entries_offset % 4) % 4

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", len(entries))
    out += struct.pack("<I", len(syl_sorted))
    out += struct.pack("<I", head)
    out += struct.pack("<I", entries_offset)
    out += syl_blob
    out += b"\x00" * (entries_offset - len(out))
    for word, freq, pinyin in entries:
        py = pinyin.encode("utf-8")
        if len(py) > 0xFFFF:
            continue
        han = word.encode("utf-16-le")
        out += struct.pack("<H", len(py)) + py
        out += struct.pack("<H", len(han) // 2) + han
        out += struct.pack("<f", freq)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))
    print(f"entries={len(entries)} syllables={len(syl_sorted)} "
          f"size={dst.stat().st_size / 1048576:.2f} MB -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
