#!/usr/bin/env python3
"""把 RIME 雾凇拼音的三个 yaml 词典合并成 build_dict.py 能吃的 rawdict 格式。

源词典：
  base.dict.yaml + tencent.dict.yaml + ext.dict.yaml（各 10-17MB）
  格式：词\\t拼音(空格分隔)\\t频率

输出：
  UTF-16-LE 明文，每行「词 频率 0 音节1 音节2 ...」
  喂给 tools/pinyin/build_dict.py 生成 dict.bin

用法：
  python tools/pinyin/rime_to_rawdict.py <rime_dir> <out.txt>
  python tools/pinyin/build_dict.py <out.txt> app/src/main/assets/pinyin/dict.bin
"""
import re
import sys
from pathlib import Path


def parse_rime_dict(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    # 跳过 YAML header（两个 --- 之间）
    body_start = 0
    dash_count = 0
    for i, l in enumerate(lines):
        if l.strip() == "---":
            dash_count += 1
            if dash_count == 2:
                body_start = i + 1
                break

    entries = []
    for line in lines[body_start:]:
        line = line.strip()
        if (not line or line.startswith("#") or line.startswith("...") or
                line.startswith("name:") or line.startswith("version:") or
                line.startswith("sort:")):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 3:
            continue
        word = parts[0]
        try:
            freq = float(parts[-1])
        except ValueError:
            continue
        syls = parts[1:-1]
        if not syls or not word:
            continue
        pinyin_str = " ".join(syls)
        # rawdict 格式：词 频率 0 音节1 音节2 ...
        entries.append((word, freq, pinyin_str))
    return entries


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    rime_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    files = ["base.dict.yaml", "tencent.dict.yaml", "ext.dict.yaml"]
    all_entries = []
    for f in files:
        p = rime_dir / f
        if not p.exists():
            print(f"skip {f} (not found)")
            continue
        ents = parse_rime_dict(p)
        print(f"{f}: {len(ents)} entries")
        all_entries.extend(ents)

    # 去重：同词+同拼音保留最高频率
    best = {}
    for word, freq, py in all_entries:
        key = (word, py)
        if key not in best or freq > best[key][1]:
            best[key] = freq

    print(f"Total after dedup: {len(best)}")

    lines = []
    for (word, py), freq in best.items():
        # UTF-16LE，空格分隔
        lines.append(f"{word} {freq:.6f} 0 {py}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-16")
    print(f"Wrote {out_path} ({out_path.stat().st_size / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
