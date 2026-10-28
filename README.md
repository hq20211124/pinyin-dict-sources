# 大胆聊 · 拼音词典源码包

本仓库用于履行 **GPL-3.0** 的分发义务，只包含「拼音词典」这一份数据的**对应源码**
（输入词库的固定版本 + 转换脚本），不包含「大胆聊」输入法应用本身的任何源码。

## 这里面是什么

`dict.bin` / `jpindex.bin` / `t9index.bin` 是「大胆聊」Android 输入法内置的三个拼音
词典资源。其中多字词条来自 **雾凇拼音（rime-ice）**，该词库以 **GPL-3.0** 发布，
我们把它重新编码成紧凑二进制后随 App 分发，因此按 GPL-3.0 第 6 条提供对应源码。

对应源码 = 下面这些**未经修改**的上游词库文件 + 我们写的**转换脚本**。
按 GPL-3.0 第 1 条，「对应源码」不需要包含能从其他部分自动重新生成的东西，
所以这里给的是可完全复现产物的最小集合。

| 部分 | 许可 | 说明 |
|---|---|---|
| `scripts/*.py` | GPL-3.0 | 本仓库作者编写的转换脚本（6 个，共约 23 KB，纯离线） |
| 雾凇拼音 `cn_dicts/{base,ext,tencent}.dict.yaml` | GPL-3.0 | 上游 `iDvel/rime-ice`，版本固定，**未修改** |
| AOSP PinyinIME `rawdict_utf16_65105_freq.txt` | Apache-2.0 | 上游 AOSP，未修改，提供单字兜底 |

`dict.bin` 的生成过程只有一件事：**把词条重新编码为二进制**（拼音串 + 汉字 + 频率），
不增删词条内容、不改注音。索引文件 `jpindex.bin`（声母简拼）与 `t9index.bin`
（九宫格数字串）都是由 `dict.bin` 二次派生的，脚本里可以看出全过程。

## 复现步骤

```bash
# 1) 按固定版本取回上游源码，并校验 SHA-256
python fetch_sources.py

# 2) 重建三个 bin，产物与原版逐字节可比对
python scripts/rebuild_all.py --source rime \
    --rime-dir sources/rime-ice/cn_dicts \
    --aosp-rawdict sources/PinyinIME/rawdict_utf16_65105_freq.txt \
    --out out
```

产物：

```
out/dict.bin      ~24 MB
out/jpindex.bin   ~11 MB
out/t9index.bin   ~23 MB
```

只想要**许可最干净**的版本（不掺 GPL 词库，只用 Apache-2.0 的 AOSP 单字词典）：

```bash
python scripts/rebuild_all.py --source aosp \
    --aosp-rawdict sources/PinyinIME/rawdict_utf16_65105_freq.txt \
    --out out_aosp
```

## 固定版本与校验和

上游文件均为**逐字节固定**，`fetch_sources.py` 会校验以下 SHA-256：

```
rime-ice  2025.04.06  cn_dicts/base.dict.yaml
  04fb54d5875b930e29ae26f03baf0b1ced097524f9801920c8a23489cb224c2e
rime-ice  2025.04.06  cn_dicts/ext.dict.yaml
  9939d89d3878dbc59c70755080438ebb071cb8c5bd048b744dfde6ed7e71f4a3
rime-ice  2025.04.06  cn_dicts/tencent.dict.yaml
  50c896b87d4db0aa091653a35fb6d75938f470c9342e3f1812fcba97cc129815
AOSP PinyinIME                     rawdict_utf16_65105_freq.txt
  408700f28a56091fa07f3b849a0f134fbfc71e6b2ae9b3f52973a5b076f599ff
```

用别的版本去跑，产出的词库和 App 里那份就不是一回事了，请按上面的版本取。

## 关于上游权利链（如实说明）

雾凇拼音本身是一份**汇编**，它自己的文件头注明了成分：华宇野风系统词库、
清华大学开源词库 THUOCL、现代汉语常用词表，以及**腾讯词向量**补充的两字词。
其中腾讯词向量（Tencent AI Lab Embedding）的使用条款限定为学术研究用途。

也就是说：这份词库的**权利链并不完全清晰**，GPL-3.0 只是雾凇拼音仓库声明的许可。
「大胆聊」只是把它原样转码使用，没有改动内容，也没有从中获利（应用免费、无广告、
不收集数据）。如果任何权利人对此有异议，请通过下面的邮箱联系，我们会立即更换词库
并发布新版本——替换只需要一条命令，见上面的 `--source aosp` 用法。

## 许可

本仓库下的脚本与本文档：**GPL-3.0**，全文见 `COPYING`。

上游词库文件按各自原许可分发：雾凇拼音为 GPL-3.0（https://github.com/iDvel/rime-ice），
AOSP PinyinIME 为 Apache-2.0（https://android.googlesource.com/platform/packages/inputmethods/PinyinIME）。

## 联系

赖红全　forwork8888@foxmail.com
