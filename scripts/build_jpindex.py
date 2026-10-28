#!/usr/bin/env python3
"""从 assets/pinyin/dict.bin 反解词条，构建简拼（声母首字母）索引 jpindex.bin。

简拼 = 每个音节只打首字母：hhh → 哈哈哈、nh → 你好。
dict.bin 里词条的拼音是无分隔拼接（西安=仙=xian），但词条同时存了汉字数，
所以可以把拼音**按汉字数切回音节**（DFS 找恰好 hanCount 个音节的切法），
取每个音节首字母得到该词的声母串，按声母串分组即索引。

只索引 2..MAX_KEY 字、词长 >=2 的词：单字走全拼，长简拼没人打。
每个声母串只留词频最高的 TOP_PER_KEY 条，防止「ssss」这种大键撑爆体积。

输出格式（小端）：
    magic       4B   "PYJ1"
    u32         声母串条数 keyCount
    u32         键区偏移（固定 12）
    u32         词条区偏移（4 字节对齐）
    键区        按声母串字典序排序的定长前缀 + 变长记录：
                u16 键长 / 键 UTF-8 / u32 词条块绝对偏移 / u16 词条数
    词条区      每键连续：词条数 × [u16 汉字数 / 汉字 UTF-16LE / f32 频率]
                键内词条按频率降序（分组时已排好）

用法：
    python tools/pinyin/build_jpindex.py app/src/main/assets/pinyin/dict.bin \
        app/src/main/assets/pinyin/jpindex.bin
"""

import struct
import sys
from pathlib import Path

MAGIC = b"PYJ1"
MIN_KEY = 2          # 最短声母串（nh → 你好）
MAX_KEY = 6          # 最长声母串（再长的纯首字母输入极少）
TOP_PER_KEY = 16     # 每个声母串最多保留的词条数
MIN_HAN = 2          # 单字不进简拼索引（打首字母出单字只会是噪声）


def load_dict(path: Path):
    """读 dict.bin（格式见 build_dict.py），返回 (音节表, [(词, 频率, 拼音)])。

    词典 89 万条，拼音串一次性全解码约占几十 MB 堆，可接受（构建期一次性）。
    """
    data = path.read_bytes()
    if data[:4] != b"PYD1":
        raise SystemExit(f"魔数不对：{data[:4]!r}")
    entry_count, syl_count, syl_off, ent_off = struct.unpack_from("<4I", data, 4)

    # 音节表：逗号分隔 UTF-8，尾部 0 填充对齐
    syl_end = ent_off
    while syl_end > syl_off and data[syl_end - 1] in (0, ord(",")):
        syl_end -= 1
    syllables = set(data[syl_off:syl_end].decode("utf-8").split(","))
    assert len(syllables) == syl_count, "音节表条数不符"
    max_syl_len = max(len(s) for s in syllables)

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
    return syllables, max_syl_len, entries


def split_into_n_syllables(pinyin: str, n: int, syllables: set, max_len: int):
    """把拼音切成恰好 n 个音节（最长优先 DFS）。切不出来返回 None。"""
    total = len(pinyin)
    # 速剪：n 个音节至少 n 字符、至多 n*max_len 字符
    if total < n or total > n * max_len:
        return None
    out = []

    def dfs(pos: int, left: int) -> bool:
        if left == 0:
            return pos == total
        remain = total - pos
        if remain < left or remain > left * max_len:
            return False
        for ln in range(min(max_len, remain - left + 1), 0, -1):
            seg = pinyin[pos: pos + ln]
            if seg in syllables:
                out.append(seg)
                if dfs(pos + ln, left - 1):
                    return True
                out.pop()
        return False

    return "".join(s[0] for s in out) if dfs(0, n) else None


def build(src: Path, dst: Path) -> None:
    syllables, max_syl_len, entries = load_dict(src)

    groups: dict[str, list] = {}
    skipped = 0
    for word, freq, pinyin in entries:
        n = len(word)
        if n < MIN_HAN or n > MAX_KEY:
            continue
        key = split_into_n_syllables(pinyin, n, syllables, max_syl_len)
        if key is None:
            skipped += 1
            continue
        groups.setdefault(key, []).append((freq, word))

    # 键内按频率降序，截 TOP_PER_KEY
    items = sorted(groups.items())
    key_records = []          # (key bytes, entry block placeholder)
    blob = bytearray()
    kept = 0
    for key, lst in items:
        lst.sort(key=lambda t: -t[0])
        lst = lst[:TOP_PER_KEY]
        kb = key.encode("ascii")
        key_records.append((kb, len(blob), len(lst)))
        for freq, word in lst:
            han = word.encode("utf-16-le")
            # 必须写 UTF-16 码元数（= 字节 / 2），不能写 len(word)：增补平面汉字是代理对，
            # len() 数的是码点、UTF-16 占 4 字节，写错会让整块后续记录全部错位
            blob += struct.pack("<H", len(han) // 2) + han + struct.pack("<f", freq)
            kept += 1

    head = 12  # magic(4) + keyCount(4) + entriesOffset(4)
    keys_size = sum(2 + len(kb) + 4 + 2 for kb, _, _ in key_records)
    entries_offset = head + keys_size
    entries_offset += (4 - entries_offset % 4) % 4

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", len(key_records))
    out += struct.pack("<I", entries_offset)
    for kb, rel_off, cnt in key_records:
        out += struct.pack("<H", len(kb)) + kb
        out += struct.pack("<I", entries_offset + rel_off)
        out += struct.pack("<H", cnt)
    out += b"\x00" * (entries_offset - len(out))
    out += blob

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))
    print(f"keys={len(key_records)} entries_kept={kept} skipped_unsplittable={skipped} "
          f"size={dst.stat().st_size / 1048576:.2f} MB -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
