#!/usr/bin/env python3
"""从 dict.bin 构建九宫格（T9）索引 t9index.bin。

九宫格按键 2..9 各对应 3–4 个字母（2=abc … 7=pqrs … 9=wxyz），用户按下的是一串数字，
输入法要把「94664486」还原成「中国」。**不能直接拿 dict.bin 二分数字串**：字母→数字是
多对一的（a/b/c 都是 2），词典按字母序排好后数字序会互相穿插（`aao`(226) < `aba`(222)），
二分不成立。所以单独建一份按**数字串字典序**排好的索引。

输出格式（小端）：
    magic       4B   "PYT1"
    u32         键数 keyCount
    u32         词条区偏移
    键区        按数字键字典序排序，定长前缀 + 变长记录：
                u16 键长 / 键 ASCII / u32 词条块绝对偏移 / u16 词条数
    词条区      每键连续：词条数 × [u16 汉字数 / 汉字 UTF-16LE / f32 频率]
                键内按频率降序（分组时已排好）

键区按数字串字典序排好，所以「以 D 开头的键」是连续区间——运行时二分定位即可
（`PinyinT9Index.prefixScan` 打 3 位以上数字时就是扫这一段，按词频取 Top-K）。

用法：
    python tools/pinyin/build_t9index.py app/src/main/assets/pinyin/dict.bin \
        app/src/main/assets/pinyin/t9index.bin
"""

import struct
import sys
from pathlib import Path

MAGIC = b"PYT1"
TOP_PER_KEY = 32     # 每个数字串最多保留的词条数（同音词一大把，只留高频的）
MAX_HAN = 6          # 超过六字的短语没人用九宫格整串打
MIN_FREQ = 0.5       # 词频地板：极生僻的条目进索引只会让扫描变慢

# a..z → 数字键（与 Kotlin 侧 T9.KEYS 必须一致）
T9_KEYS = "22233344455566677778889999"


def load_dict(path: Path):
    """读 dict.bin（格式见 build_dict.py），返回 [(词, 频率, 拼音)]。"""
    data = path.read_bytes()
    if data[:4] != b"PYD1":
        raise SystemExit(f"魔数不对：{data[:4]!r}")
    entry_count, _syl_count, _syl_off, ent_off = struct.unpack_from("<4I", data, 4)

    entries = []
    pos = ent_off
    for _ in range(entry_count):
        (py_len,) = struct.unpack_from("<H", data, pos)
        pinyin = data[pos + 2: pos + 2 + py_len].decode("ascii")
        (han_len,) = struct.unpack_from("<H", data, pos + 2 + py_len)
        han_from = pos + 4 + py_len
        word = data[han_from: han_from + han_len * 2].decode("utf-16-le")
        (freq,) = struct.unpack_from("<f", data, han_from + han_len * 2)
        entries.append((word, freq, pinyin))
        pos = han_from + han_len * 2 + 4
    return entries


def t9_digits(pinyin: str):
    """拼音字母串 → 数字串（长度不变）。出现 a-z 以外的字符返回 None。"""
    out = []
    for ch in pinyin:
        i = ord(ch) - 97
        if i < 0 or i >= 26:
            return None
        out.append(T9_KEYS[i])
    return "".join(out)


def build(src: Path, dst: Path) -> None:
    entries = load_dict(src)

    groups: dict[str, dict[str, float]] = {}
    skipped = 0
    for word, freq, pinyin in entries:
        if not word or len(word) > MAX_HAN or freq < MIN_FREQ:
            continue
        key = t9_digits(pinyin)
        if key is None:
            skipped += 1
            continue
        bucket = groups.setdefault(key, {})
        # 同一数字串下同一个词可能来自不同拼音（同音词），只留最高频那次
        if bucket.get(word, 0.0) < freq:
            bucket[word] = freq

    keys = sorted(groups.keys())
    blob = bytearray()
    records = []   # (key bytes, entry block offset, count)
    kept = 0
    for key in keys:
        items = sorted(groups[key].items(), key=lambda kv: -kv[1])[:TOP_PER_KEY]
        kb = key.encode("ascii")
        records.append((kb, len(blob), len(items)))
        for word, freq in items:
            han = word.encode("utf-16-le")
            # 必须写 UTF-16 码元数（= 字节 / 2），不能写 len(word)：增补平面汉字是代理对，
            # len() 数的是码点、UTF-16 占 4 字节，写错会让整块后续记录全部错位（freq 读出垃圾）
            blob += struct.pack("<H", len(han) // 2) + han + struct.pack("<f", freq)
            kept += 1

    head = 12  # magic(4) + keyCount(4) + entriesOffset(4)
    keys_size = sum(2 + len(kb) + 4 + 2 for kb, _, _ in records)
    entries_offset = head + keys_size
    entries_offset += (4 - entries_offset % 4) % 4

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", len(records))
    out += struct.pack("<I", entries_offset)
    for kb, rel_off, cnt in records:
        out += struct.pack("<H", len(kb)) + kb
        out += struct.pack("<I", entries_offset + rel_off)
        out += struct.pack("<H", cnt)
    out += b"\x00" * (entries_offset - len(out))
    out += blob

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))
    print(f"keys={len(records)} entries_kept={kept} skipped_non_ascii={skipped} "
          f"size={dst.stat().st_size / 1048576:.2f} MB -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
