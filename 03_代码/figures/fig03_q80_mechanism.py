# -*- coding: utf-8 -*-
r"""
Fig.3  问题二核心机制：为什么风险分位数落在 0.8
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
0.8 不是拍脑袋选的：正常购电价 p 与紧急购电价 5p 的**代价不对称**，使"多买
1 kWh"与"少买 1 kWh"的期望边际成本恰好在 F(g)=0.8 处相等：

    多买 1 kWh 的确定成本      = p
    少买 1 kWh 的期望边际成本  = 5p·P(N>g)
    令二者相等： p = 5p·Pr(N>g)  ⟹  F(g) = (5−1)/5 = 0.8 .

证据链（两 panel 共用同一横轴，同一族的经验分布驱动两张图）
----------------------------------------------------------
(a) 经验分布与 0.8 分位 —— 把"风险余量"落到具体位置：右侧 20% 即尾部风险
(b) 边际成本平衡       —— 解释"为什么恰好是这里"：两条边际成本曲线的交点

(a) 回答 where，(b) 回答 why；(b) 的横坐标就是 (a) 的横坐标。

数学忠实性（重要，勿改）
------------------------
本图**照抄论文结论**，不改写、不加强：
  * 目标函数与一阶条件取自论文 §6.4（式 eq:p2-newsvendor / eq:p2-critical）。
  * 论文明确声明该结论**只在忽略储能与跨时段耦合时严格成立**，故本文把 α 作为
    **参数搜索的起点**而非最终结论，最终由连续运行总费用标定（8 轮滚动标定落在
    α∈[0.70,0.90]，0.75 出现最多）。图内脚注原样保留这一限定，避免读者误以为
    模型就是"按 Q0.8 采购"。
  * 该分位结论**不依赖任何分布假设**（论文 §2.2 原话）。经验分布只是形状示例，
    不是推导前提——脚注同时说明这一点。

数据来源（真实，无编造）
------------------------
06_支撑材料/p2_detail.csv —— 逐时段「实际负载 − 实际光伏 − 净负荷预测」得到净负荷
预测误差 ε。**只读 CSV，不重算模型。**
模型内部是**逐时段**取 28 天窗口的 α 分位数；本图为讲解机制把全区间样本汇总成
一条经验分布，差异已在脚注写明。

排版约束
--------
**全图不使用 mathtext。** Arial 缺下标字形 ₀/₈（U+2080/2088），而含 `$...$` 的
字符串又会绕过 font.family 回退链把中文变成 dummy symbol；故一律改用普通
Unicode 字符（− ≤ · 等均已确认 Arial 与雅黑同时支持）。

输出
----
04_图/pdf/fig03_q80_mechanism.pdf
04_图/fig03_q80_mechanism.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

ALPHA = 0.80            # 论文主参数：风险分位数
PRICE_RATIO = 5.0       # 紧急购电 / 正常购电 = 5
N_BINS = 90

XY_LABEL = (0.022, 0.972)
XY_CLAIM = (0.988, 0.978)


def _claim(ax, text: str, color: str) -> None:
    ax.text(*XY_CLAIM, text, transform=ax.transAxes, ha="right", va="top",
            fontsize=6.9, color=color, fontweight="bold")


def _wrap_cjk(text: str, per_line: int) -> str:
    """按字数折行。

    中文没有空格，`textwrap` 对它无效；而 `save_figure` 用
    `bbox_inches="tight"` 导出，**一行超宽的文字会把整页横向撑开**
    （实测把 160 mm 的图撑成 337 mm）。长中文说明必须先折行再交给 fig.text。
    尽量在标点后断行，避免把「α ∈ [0.70」这类整体截断。
    """
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= per_line - 8 and ch in "；，。、）":
            lines.append(cur)
            cur = ""
        elif len(cur) >= per_line:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def load_errors() -> np.ndarray:
    """净负荷预测误差 ε =（实际负载 − 实际光伏）− 净负荷预测。"""
    df = pd.read_csv(S.SUP_DIR / "p2_detail.csv", encoding="utf-8-sig")
    need = ["实际负载_kWh", "实际光伏_kWh", "净负荷预测_kWh"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise KeyError(f"p2_detail.csv 缺少列：{missing}")
    eps = (df["实际负载_kWh"].to_numpy(float)
           - df["实际光伏_kWh"].to_numpy(float)
           - df["净负荷预测_kWh"].to_numpy(float))
    return eps[np.isfinite(eps)]


def build(eps: np.ndarray) -> plt.Figure:
    """绘制 Fig.3。两 panel 共用 ε 横轴。"""
    S.apply_style()

    q80 = float(np.quantile(eps, ALPHA))
    lo, hi = (float(np.quantile(eps, 0.001)), float(np.quantile(eps, 0.999)))
    pad = 0.10 * (hi - lo)
    x_lo, x_hi = lo - pad, hi + pad
    span = x_hi - x_lo

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(S.mm2in(160), S.mm2in(94)),
        gridspec_kw={"wspace": 0.22},
    )

    # 关网格：网格线是贯穿整幅 panel 的描边路径，会穿过几乎每一段轴内文字，
    # 碰撞审计一律判 text-stroke。本图靠参考线与色块读值，网格并非必要。
    ax_a.grid(False)
    ax_b.grid(False)

    # ================================================== (a) 经验分布 + 0.8 分位
    counts, edges = np.histogram(eps, bins=N_BINS, range=(x_lo, x_hi), density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    width = edges[1] - edges[0]
    ymax = float(counts.max())

    ax_a.bar(centers, counts, width=width, color=S.C_FORECAST, alpha=0.36,
             lw=0, zorder=2)
    tail = centers > q80
    ax_a.bar(centers[tail], counts[tail], width=width, color=S.C_EMERGENCY,
             alpha=0.62, lw=0, zorder=3)

    ax_a.axvline(0, color=S.C_ACTUAL, ls="-.", lw=1.0, zorder=4)
    ax_a.axvline(q80, color=S.C_EMERGENCY, lw=1.6, zorder=5)
    ax_a.set_xlim(x_lo, x_hi)
    ax_a.set_ylim(0, ymax * 1.34)
    ax_a.set_xlabel("净负荷预测误差 ε (kWh / 10min)")
    ax_a.set_ylabel("概率密度")
    S.add_panel_label(ax_a, "a", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")
    _claim(ax_a, "右侧 20% 即尾部风险", S.C_EMERGENCY)

    # 两条参考线的标注分列线的左右、同一高度：q80(0.55) 与 0(0.49) 在轴上很近，
    # 若都靠右会直接叠字，故一个右对齐留在 0 左侧、一个左对齐放在 q80 右侧。
    ax_a.text(-6.0, ymax * 1.12, "预测值 0", fontsize=6.8, color=S.C_ACTUAL,
              ha="right", va="bottom")
    ax_a.text(q80 + 6.0, ymax * 1.12, f"Q0.8 = {q80:.1f} kWh", fontsize=6.8,
              color=S.C_EMERGENCY, ha="left", va="bottom", fontweight="bold")
    # 尾部区域内的说明：放在色块下半部的空白处
    ax_a.text(0.5 * (q80 + x_hi), ymax * 0.34, "紧急购电区", fontsize=6.8,
              color="#8C2F3C", ha="center", va="center", fontweight="bold")

    # ================================================== (b) 边际成本平衡
    grid = np.linspace(x_lo, x_hi, 800)
    srt = np.sort(eps)
    # 经验生存函数 P(ε>g)：直接数样本，不做任何分布假设
    surv = 1.0 - np.searchsorted(srt, grid, side="right") / srt.size

    ax_b.plot(grid, PRICE_RATIO * surv, color=S.C_EMERGENCY, lw=1.8, zorder=4)
    ax_b.axhline(1.0, color=S.C_GRID, lw=1.8, zorder=3)
    # 交点竖线只画到 y=2.0：若贯穿整幅 panel，它会穿过上方的曲线标注文字
    # （碰撞审计判 text-stroke）。只连到交点即可表达"这个横坐标"。
    ax_b.plot([q80, q80], [0.0, 1.15], color=S.C_REF, ls=":", lw=1.0, zorder=2)
    ax_b.plot([q80], [1.0], marker="o", ms=6.2, color="#1A1A1A",
              markeredgecolor="white", markeredgewidth=0.8, zorder=6)

    ax_b.set_xlim(x_lo, x_hi)
    ax_b.set_ylim(0, PRICE_RATIO * 1.55)
    ax_b.set_xlabel("计划购电量 g (kWh / 10min)")
    ax_b.set_ylabel("边际成本（正常电价 p 的倍数）")
    S.add_panel_label(ax_b, "b", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")
    _claim(ax_b, "两线相交于 F(g) = 0.8", S.C_GRID)

    # 两条曲线的直接标注。降曲线标注放在曲线值域(0→5)之上的空白带；
    # 水平线标注贴在线右端上方——降曲线在该处已跌破 1，不会与文字相交。
    ax_b.text(x_lo + 0.03 * span, PRICE_RATIO * 1.38,
              "少买 1 kWh 的期望成本 = 5p · P(N > g)", fontsize=6.9,
              color=S.C_EMERGENCY, ha="left", va="center", fontweight="bold")
    ax_b.text(x_hi - 0.01 * span, 1.25,
              "多买 1 kWh 的成本 = p", fontsize=6.9,
              color=S.C_GRID, ha="right", va="bottom", fontweight="bold")

    # ================================================== 脚注（数学限定）
    note = ("注：F(g) = (5−1)/5 = 0.8 不依赖任何分布假设，(a) 的经验分布仅示范形状；该结论只在忽略储能与跨时段耦合时严格成立，"
            "故本文把 α 作为参数搜索起点（8 轮标定落在 α ∈ [0.70, 0.90]，0.75 最多），最终由连续运行总费用标定；"
            "经验分布由 334 天 × 144 时段汇总，模型内部为逐时段 28 天窗口分位数。")
    fig.text(0.006, 0.012, S.wrap_cjk(note, fontsize=6.2), fontsize=6.2, color="#7A7A7A",
             ha="left", va="bottom", linespacing=1.5)

    fig.subplots_adjust(top=0.93, bottom=0.24)
    return fig


def main() -> None:
    S.apply_style()
    eps = load_errors()
    print(f"样本数 {eps.size}，Q0.8 = {np.quantile(eps, ALPHA):.2f} kWh")
    fig = build(eps)
    saved = S.save_figure(fig, "fig03_q80_mechanism")
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
