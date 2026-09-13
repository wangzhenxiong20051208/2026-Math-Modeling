# -*- coding: utf-8 -*-
r"""
字形覆盖探测（QA / 选型工具，非交付件）
================================================================================

要解决的问题
------------
matplotlib 的逐字形字体回退**缺字时不报错**，直接画成空白或 dummy symbol。
`audit_pdf_text.py` 查的是"字号是否过小"，`audit_figure_collisions.py` 查的是
"文字框是否互相压住"——**两者都查不出缺字**。缺字只能靠人眼在图上看出来，
而人眼在 6 pt 的中文里看不出来。

故本脚本在**导出之前**做静态校验：
  1. 逐个跑绘图脚本，截获其 figure（把 save_figure 换成不落盘的桩）；
  2. 遍历 figure 上所有 Text 对象，取出真实字符串；
  3. 对每个字符，沿 font.family 回退链**逐字体**查 cmap，判定是否可渲染；
  4. 报告每个字符最终由哪个字体承接——用于确认"拉丁走 Times、
     中文走宋体"这条分工真的生效，而不是整串落到回退字体上。

判定口径与 matplotlib 一致：`FT2Font.get_char_index(cp) != 0` 即该字体含此字形。

运行：python 03_代码/figures/_font_coverage.py
退出码：0 = 全部字符可渲染；1 = 存在缺字（会被静默画成空白）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ft2font  # noqa: E402
from matplotlib.font_manager import FontProperties, findfont  # noqa: E402

# Windows 控制台默认 GBK，打印 − ≤ α 这类字符会直接抛 UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
del _s

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import figstyle as S  # noqa: E402

FIGURES = [
    "fig01_framework",
    "fig02_p1_dispatch",
    "fig03_q80_mechanism",
    "fig04_risk_execution",
    "fig05_cost_waterfall",
]

SKIP = {"\n", "\r", "\t", " "}

_font_cache: dict[str, ft2font.FT2Font | None] = {}


def _font_for(family: str, weight: int, style: str) -> ft2font.FT2Font | None:
    """解析某个 family 在指定字重下的字体文件并加载 cmap；不可用返回 None。"""
    key = f"{family}|{weight}|{style}"
    if key in _font_cache:
        return _font_cache[key]

    font: ft2font.FT2Font | None = None
    try:
        path = findfont(FontProperties(family=family, weight=weight, style=style),
                        fallback_to_default=False)
        font = ft2font.FT2Font(str(path))
    except Exception:  # noqa: BLE001 - 解析失败即视为该字重不可用
        font = None
    _font_cache[key] = font
    return font


def families() -> list[str]:
    fam = matplotlib.rcParams["font.family"]
    return [fam] if isinstance(fam, str) else list(fam)


def resolve(char: str, weight: int, style: str = "normal") -> tuple[str, str] | None:
    """沿 font.family 回退链找第一个含该字形的字体。

    返回 (family, 字体文件名)；全部落空返回 None。
    文件名必须一并返回——"宋体没有粗体"这个问题正是靠 `fontweight="bold"` 的中文
    实际落到 simhei.ttf 而不是 simsun.ttc 来验证的，只看 family 名看不出来。
    """
    for fam in families():
        f = _font_for(fam, weight, style)
        if f is not None and f.get_char_index(ord(char)) != 0:
            return fam, Path(f.fname).name
    return None


def harvest(fig) -> dict[str, list[tuple[int, str]]]:
    """figure 上所有 Text → {字符: [(字重, 该文本的截断)]}。"""
    chars: dict[str, list[tuple[int, str]]] = {}
    for t in fig.findobj(matplotlib.text.Text):
        s = t.get_text()
        if not s or not s.strip():
            continue
        fw = t.get_fontweight()
        weight = int(fw) if str(fw).isdigit() else (
            700 if str(fw).lower() == "bold" else 400)
        for ch in s:
            if ch in SKIP:
                continue
            chars.setdefault(ch, []).append((weight, s[:26]))
    return chars


def grab_figure(stem: str):
    """跑脚本的 main()，但把 save_figure 换成不落盘的桩，截获 figure。"""
    captured: list = []
    original = S.save_figure

    def _stub(fig, stem_, **kw):  # noqa: ANN001, ANN003
        captured.append(fig)
        return []

    path = HERE / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(f"__probe_{stem}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    mod.S.save_figure = _stub          # 该模块内的 figstyle 是同一对象
    try:
        mod.main()
    finally:
        S.save_figure = original

    return captured[0] if captured else None


def main() -> int:
    S.apply_style()
    print("font.family =", families())
    print()

    missing: dict[str, set[str]] = {}
    routing: dict[str, set[str]] = {}
    bold_cjk: dict[tuple[str, str], set[str]] = {}

    for stem in FIGURES:
        fig = grab_figure(stem)
        if fig is None:
            print(f"  {stem}: 未能截获 figure，跳过")
            continue

        chars = harvest(fig)
        for ch, uses in chars.items():
            weight, where = uses[0]
            hit = resolve(ch, weight)
            if hit is None:
                missing.setdefault(stem, set()).add(
                    f"U+{ord(ch):04X} {ch!r}  出现在 {where!r}")
                continue
            fam, fname = hit
            routing.setdefault(fam, set()).add(ch)
            if weight >= 700 and ord(ch) > 0x2E7F:
                bold_cjk.setdefault((fam, fname), set()).add(ch)
        plt.close(fig)

    print("=== 字体承接范围 ===")
    for fam, chs in sorted(routing.items()):
        non_ascii = "".join(sorted(c for c in chs if ord(c) > 0x7E))
        ascii_ = "".join(sorted(c for c in chs if ord(c) <= 0x7E))
        print(f"  {fam}")
        print(f"      非 ASCII ({len(non_ascii):3d}): {non_ascii[:70]}")
        print(f"      ASCII   ({len(ascii_):3d}): {ascii_[:70]!r}")

    print()
    print("=== 粗体中文落到哪个字体文件（宋体无粗体，应落到黑体） ===")
    if not bold_cjk:
        print("  （图中没有粗体非 ASCII 字符）")
    for (fam, fname), chs in sorted(bold_cjk.items()):
        mark = "黑体（正确）" if "hei" in fname.lower() else "⚠ 宋体常规体（粗体失效）"
        print(f"  family={fam}  文件={fname}  {len(chs)} 个字形  → {mark}")
        print(f"      {''.join(sorted(chs))[:60]}")

    print()
    if missing:
        print("=== 缺字（会被静默画成空白） ===")
        for stem, items in sorted(missing.items()):
            print(f"  {stem}:")
            for it in sorted(items):
                print(f"      {it}")
        print("\n结论：FAIL —— 必须换字体或改字符。")
        return 1

    print("结论：PASS —— 所有字符都能沿 font.family 回退链找到字形。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
