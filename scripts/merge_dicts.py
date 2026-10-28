#!/usr/bin/env python3
"""合并 RIME 雾凇词典（多字词条）与 AOSP PinyinIME 词典（单字兜底）。

RIME 词条质量好（87万条，频率不放大，有大量新词），但不含单字。
Google PinyinIME 词典单字频率被严重放大但覆盖全，作为 fallback 保留。

合并策略：
  - 同 word+pinyin 去重时保留 RIME 的（频率更准确）
  - 仅 Google 里有的条目，保留其单字（作为兜底）
  - 仅 RIME 里有的，全部保留

用法：
  python tools/pinyin/merge_dicts.py <rime_rawdict> <google_rawdict> <out_rawdict>
"""
import sys
from pathlib import Path


def load_rawdict(path):
    entries = []
    encoding = "utf-16"
    # RIME 转的是 utf-16，Google 原文件也是 utf-16
    with open(path, encoding=encoding) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            word = parts[0]
            try:
                freq = float(parts[1])
            except ValueError:
                continue
            syls = parts[3:]
            pinyin = " ".join(syls)
            entries.append((word, freq, pinyin))
    return entries


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    rime_path = Path(sys.argv[1])
    google_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    print("Loading RIME dict...")
    rime = load_rawdict(rime_path)
    print(f"  RIME: {len(rime)} entries")

    print("Loading Google dict...")
    google = load_rawdict(google_path)
    print(f"  Google: {len(google)} entries")

    # 建立 key -> freq 映射
    # key = (word, pinyin)
    merged = {}
    for word, freq, py in rime:
        merged[(word, py)] = freq

    for word, freq, py in google:
        key = (word, py)
        if key not in merged:
            merged[key] = freq  # Google 独有的，保留（主要是单字 fallback）

    print(f"After merge (dedup by word+pinyin): {len(merged)} entries")

    # 按 (pinyin, -freq) 排序（跟 build_dict.py 的期望一致）
    sorted_entries = sorted(merged.items(), key=lambda kv: (kv[0][1], -kv[1]))

    lines = []
    for (word, py), freq in sorted_entries:
        lines.append(f"{word} {freq:.6f} 0 {py}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-16")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
