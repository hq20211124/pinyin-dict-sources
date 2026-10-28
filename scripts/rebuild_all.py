#!/usr/bin/env python3
"""一条命令重建三份拼音词典资源（dict.bin / jpindex.bin / t9index.bin）。

存在的意义：词库许可随时可能要换（雾凇拼音是 GPL-3.0，见
docs/app-store-publishing.md §13）。真要换的时候**不要手动跑三步**——
换漏一步就会出现 dict.bin 和 jpindex.bin 版本不一致，候选行为诡异。

用法（PowerShell）：

    # 许可干净的版本：只用 AOSP PinyinIME 词库（Apache-2.0，6.5 万条）
    python tools/pinyin/rebuild_all.py --source aosp `
        --aosp-rawdict downloads/PinyinIME/app/src/main/cpp/data/rawdict_utf16_65105_freq.txt

    # 当前发货的版本：雾凇拼音多字词条 + AOSP 单字（89 万条）
    python tools/pinyin/rebuild_all.py --source rime `
        --rime-dir downloads/rime-ice/rime-ice-2025.04.06/cn_dicts `
        --aosp-rawdict downloads/PinyinIME/app/src/main/cpp/data/rawdict_utf16_65105_freq.txt

默认写进 app/src/main/assets/pinyin/；加 --out <dir> 先产出到别处对比。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# 同一份脚本有两种布局：App 仓库里是 tools/pinyin/，公开源码包里是 scripts/（见
# pinyin-dict-sources/）。判据是目录名，不要写死层数。
REPO = HERE.parent.parent if HERE.name == "pinyin" else HERE.parent
APP_ASSETS = REPO / "app" / "src" / "main" / "assets" / "pinyin"


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(HERE / script), *[str(a) for a in args]]
    print(f"\n$ {' '.join(Path(c).name if i == 0 else c for i, c in enumerate(cmd[1:]))}")
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["aosp", "rime"], required=True)
    ap.add_argument("--aosp-rawdict", required=True, help="AOSP 的 rawdict_utf16_65105_freq.txt")
    ap.add_argument("--rime-dir", default=None, help="rime-ice 的 cn_dicts 目录（--source rime 必填）")
    ap.add_argument("--out", default=str(APP_ASSETS if APP_ASSETS.parent.exists() else REPO / "out"))
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dict_bin = out / "dict.bin"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if a.source == "aosp":
            rawdict = Path(a.aosp_rawdict)
        else:
            if not a.rime_dir:
                print("--source rime 需要 --rime-dir", file=sys.stderr)
                return 2
            rime_raw = tmp_path / "rime_rawdict.txt"
            merged = tmp_path / "merged_rawdict.txt"
            run("rime_to_rawdict.py", a.rime_dir, rime_raw)
            run("merge_dicts.py", rime_raw, a.aosp_rawdict, merged)
            rawdict = merged

        run("build_dict.py", rawdict, dict_bin)

    run("build_jpindex.py", dict_bin, out / "jpindex.bin")
    run("build_t9index.py", dict_bin, out / "t9index.bin")

    print("\n=== 产物 ===")
    for name in ("dict.bin", "jpindex.bin", "t9index.bin"):
        p = out / name
        print(f"  {name:14s} {p.stat().st_size / 1024 / 1024:6.2f} MB   {p}")
    print("\n下一步：跑 `gradlew :app:testDebugUnitTest`（PinyinDictTest 等直接读 dict.bin），")
    print("再 assembleRelease 出包。三份文件必须同源，别只换一份。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
