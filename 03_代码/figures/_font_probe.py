# -*- coding: utf-8 -*-
r"""
字体回退像素级校验（QA 工具，不产出交付图）。

为什么需要它：matplotlib 的中文回退失效时**不会报错**，只是把汉字画成空白或
豆腐块，仅在 savefig 时给一条容易淹没在日志里的 UserWarning。肉眼看一次
缩略图也可能被骗过去。本脚本直接数墨迹像素，用一个已知缺中文的字体做基线，
确定性地回答"中文到底画出来了没有"。

运行：python 03_代码/figures/_font_probe.py
退出码 0 = 中文渲染正常；1 = 回退失效。
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl                          # noqa: E402
import matplotlib.pyplot as plt                   # noqa: E402

import figstyle as S                              # noqa: E402

#: 参考基线：Arial 不含汉字，用它渲染同一串汉字即为"豆腐块"墨量下限。
_REFERENCE_LACKING_CJK = "Arial"

#: 实测墨迹占比高于该值即认定汉字真实绘出（豆腐块墨量约为其 1/6）。
_INK_THRESHOLD = 0.015

_PROBE_TEXT = "中文测试电价储能"


def _ink_fraction(families, text: str) -> float:
    """以给定字体族列表渲染一行文本，返回暗像素占比。

    只临时改动 font.family 并在结束后还原，避免污染调用方的 rcParams
    （早期版本用 rcParamsDefault 整体重置，会把待测配置一起清掉）。
    """
    saved = mpl.rcParams["font.family"]
    mpl.rcParams["font.family"] = families
    try:
        fig = plt.figure(figsize=(4.0, 1.0))
        fig.patch.set_facecolor("white")
        fig.text(0.02, 0.2, text, fontsize=20)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # 缺字警告不影响判定，由墨量判定
            fig.savefig("_font_probe.png", dpi=150, facecolor="white")
        arr = np.asarray(Image.open("_font_probe.png").convert("L"))
        plt.close(fig)
        return float((arr < 128).mean())
    finally:
        mpl.rcParams["font.family"] = saved


def main() -> int:
    S.apply_style()
    configured_families = list(mpl.rcParams["font.family"])   # 先固定待测配置

    baseline = _ink_fraction([_REFERENCE_LACKING_CJK], _PROBE_TEXT)
    configured = _ink_fraction(configured_families, _PROBE_TEXT)
    latin = _ink_fraction(configured_families, "Hamburgefonstiv 0123")
    latin_ref = _ink_fraction([_REFERENCE_LACKING_CJK], "Hamburgefonstiv 0123")

    print(f"字体族列表        : {configured_families}")
    print(f"豆腐块基线墨量    : {baseline:.5f}   ({_REFERENCE_LACKING_CJK}，已知无汉字)")
    print(f"当前配置汉字墨量  : {configured:.5f}")
    print(f"拉丁字形一致性    : 当前 {latin:.5f} vs Arial {latin_ref:.5f} "
          f"({'一致，确认拉丁走 Arial' if abs(latin - latin_ref) < 1e-4 else '不一致'})")

    ok = configured > _INK_THRESHOLD and configured > baseline * 3
    print(f"判定              : {'中文回退正常' if ok else '中文回退失效（汉字为豆腐块）'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
