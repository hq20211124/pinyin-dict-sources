#!/usr/bin/env python3
"""按固定版本取回生成拼音词典所需的上游源码，并校验 SHA-256。

对应源码有两部分：
  * 雾凇拼音（iDvel/rime-ice）固定版本的 cn_dicts/*.dict.yaml —— GPL-3.0
  * AOSP PinyinIME 的 rawdict_utf16_65105_freq.txt —— Apache-2.0

用法：
    python fetch_sources.py                # 下载到 ./sources
    python fetch_sources.py --dir mydir    # 换目录

国内直连 GitHub 容易断，可先设代理：
    PowerShell: $env:HTTPS_PROXY='http://127.0.0.1:7897'
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

RIME_TAG = "2025.04.06"
RIME_TARBALL = (
    f"https://github.com/iDvel/rime-ice/archive/refs/tags/{RIME_TAG}.tar.gz"
)

# 只取这三个，其余文件本包用不到
RIME_FILES = {
    "cn_dicts/base.dict.yaml": "04fb54d5875b930e29ae26f03baf0b1ced097524f9801920c8a23489cb224c2e",
    "cn_dicts/ext.dict.yaml": "9939d89d3878dbc59c70755080438ebb071cb8c5bd048b744dfde6ed7e71f4a3",
    "cn_dicts/tencent.dict.yaml": "50c896b87d4db0aa091653a35fb6d75938f470c9342e3f1812fcba97cc129815",
}

AOSP_RAWDICT_URL = (
    "https://raw.githubusercontent.com/foow/PinyinIME/master/"
    "app/src/main/cpp/data/rawdict_utf16_65105_freq.txt"
)
AOSP_RAWDICT_SHA = "408700f28a56091fa07f3b849a0f134fbfc71e6b2ae9b3f52973a5b076f599ff"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  下载 {url}")
    with urllib.request.urlopen(url) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="sources")
    a = ap.parse_args()
    root = Path(a.dir)
    root.mkdir(parents=True, exist_ok=True)

    failed = False

    print(f"[1/2] 雾凇拼音 rime-ice {RIME_TAG}")
    for rel, want in RIME_FILES.items():
        dest = root / "rime-ice" / rel
        if dest.exists() and sha256(dest) == want:
            print(f"  已有且校验通过 {rel}")
            continue
        # 上游仓库整个打包下载（单文件没有稳定的 raw 地址，tag 归档最可靠）
        tar = root / f"rime-ice-{RIME_TAG}.tar.gz"
        if not tar.exists():
            download(RIME_TARBALL, tar)
        import tarfile

        with tarfile.open(tar) as tf:
            member = next(
                (m for m in tf.getmembers() if m.name.endswith("/" + rel)), None
            )
            if member is None:
                print(f"  ✗ 归档里没有 {rel}", file=sys.stderr)
                failed = True
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src, dest.open("wb") as out:
                out.write(src.read())
        got = sha256(dest)
        ok = got == want
        print(f"  {'✓' if ok else '✗'} {rel}  sha256={got[:16]}…")
        failed |= not ok

    print("[2/2] AOSP PinyinIME rawdict")
    dest = root / "PinyinIME" / "rawdict_utf16_65105_freq.txt"
    if dest.exists() and sha256(dest) == AOSP_RAWDICT_SHA:
        print("  已有且校验通过")
    else:
        download(AOSP_RAWDICT_URL, dest)
        got = sha256(dest)
        ok = got == AOSP_RAWDICT_SHA
        print(f"  {'✓' if ok else '✗'} rawdict_utf16_65105_freq.txt  sha256={got[:16]}…")
        failed |= not ok

    if failed:
        print("\n有文件校验失败：可能是代理/镜像给了别的内容，或上游改了历史版本。", file=sys.stderr)
        print("请对照 README 里的 SHA-256 手工核对。", file=sys.stderr)
        return 1
    print("\n完成。下一步：python scripts/rebuild_all.py --source rime "
          f"--rime-dir {root / 'rime-ice' / 'cn_dicts'} "
          f"--aosp-rawdict {dest} --out out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
