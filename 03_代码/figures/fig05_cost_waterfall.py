# -*- coding: utf-8 -*-
r"""
Fig.5  问题二：风险修正策略的费用瀑布——不是买得更少，而是换一种买法
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
风险修正策略把计划购电费**抬高**了 98.9 万元，却把紧急购电费**压低**了 195.3 万元，
净省 96.4 万元。要点不是"买得更少"——它其实买得**更多**（计划购电量 +6.7%）——
而是**用低价的确定性支出，替代了 5 倍价的尾部风险支出**（紧急购电量 −74.3%）。

证据链（瀑布把两个策略的差额拆成两项，各自对应一个物理动作）
------------------------------------------------------------
起点  预测均值策略全年合计费用
+项   计划购电费增加 —— 因为按 0.8 分位数采购，提前多买
−项   紧急购电费减少 —— 因为尾部缺口被提前堵住，5 倍价支出大幅下降
终点  本文风险修正策略全年合计费用（低于起点）

四个柱子的高度关系本身就是结论：一个不大的 + 项，扳倒了一个很大的 − 项。

数据来源（真实，无编造）
------------------------
06_支撑材料/p2_results.json → "对照策略" 两个条目，均由 03_代码/p2_microgrid.py
在同一预测器、同一实时执行规则下**各自单独标定**跑出。
本图只做减法，不重算模型。

排版约束
--------
单幅 panel（对齐门判定为 NOT APPLICABLE）。全部文字为普通 Unicode，不使用
mathtext（含 `$...$` 的字符串会绕过 font.family 回退链，中文变豆腐块）。

输出
----
04_图/pdf/fig05_cost_waterfall.pdf
04_图/fig05_cost_waterfall.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

KEY_RISK = "本文风险修正策略（主模型）"
KEY_MEAN = "预测均值策略（不加分位风险余量）"

WAN = 1e4          # 元 → 万元


def load_pairs() -> dict:
    """读取两条对照策略的费用与电量。"""
    with open(S.SUP_DIR / "p2_results.json", encoding="utf-8") as f:
        res = json.load(f)
    comp = res["对照策略"]
    missing = [k for k in (KEY_RISK, KEY_MEAN) if k not in comp]
    if missing:
        raise KeyError(f"p2_results.json 的『对照策略』缺少：{missing}")
    return {k: comp[k] for k in (KEY_RISK, KEY_MEAN)}


def build(data: dict) -> plt.Figure:
    S.apply_style()

    risk, mean = data[KEY_RISK], data[KEY_MEAN]
    plan_mean, plan_risk = mean["计划购电费_元"], risk["计划购电费_元"]
    emg_mean, emg_risk = mean["紧急购电费_元"], risk["紧急购电费_元"]
    tot_mean, tot_risk = mean["合计购电费_元"], risk["合计购电费_元"]

    d_plan = plan_risk - plan_mean          # 计划费变化（正 = 增加）
    d_emg = emg_risk - emg_mean             # 紧急费变化（负 = 减少）
    net = d_plan + d_emg                    # 合计变化（负 = 省）

    kwh_plan_mean = mean["计划购电量_kWh"]
    kwh_plan_risk = risk["计划购电量_kWh"]
    kwh_emg_mean = mean["紧急购电量_kWh"]
    kwh_emg_risk = risk["紧急购电量_kWh"]
    r_plan = 100 * (kwh_plan_risk / kwh_plan_mean - 1)
    r_emg = 100 * (kwh_emg_risk / kwh_emg_mean - 1)

    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(96)))
    ax = fig.add_axes((0.085, 0.19, 0.90, 0.70))
    ax.grid(False)

    labels = ["预测均值策略\n（不加风险余量）", "+ 计划购电费\n（提前多买）",
              "− 紧急购电费\n（尾部缺口被堵住）", "本文风险修正策略\n（主模型）"]
    xs = [0, 1, 2, 3]

    # ---------------- 柱子：两端为总量柱，中间为浮动差额柱 ----------------
    ax.bar(0, tot_mean / WAN, width=0.56, color=S.C_NEUTRAL, alpha=0.85, lw=0)

    lo1, hi1 = tot_mean / WAN, (tot_mean + d_plan) / WAN
    ax.bar(1, hi1 - lo1, bottom=lo1, width=0.56, color=S.C_GRID, alpha=0.92, lw=0)

    lo2, hi2 = (tot_mean + d_plan) / WAN, tot_risk / WAN
    ax.bar(2, lo2 - hi2, bottom=hi2, width=0.56, color=S.C_EMERGENCY,
           alpha=0.92, lw=0)

    ax.bar(3, tot_risk / WAN, width=0.56, color=S.C_NEUTRAL, alpha=0.85, lw=0)

    # 连接线：让读者顺着看差额如何累加
    for x0, x1, y in ((0, 1, tot_mean / WAN), (1, 2, hi1), (2, 3, tot_risk / WAN)):
        ax.plot([x0 + 0.28, x1 - 0.28], [y, y], color="#9A9A9A", ls=":",
                lw=0.9, zorder=1)

    # ---------------- 数值标注 ----------------
    ax.text(0, tot_mean / WAN + 22, f"{tot_mean / WAN:,.0f}", ha="center",
            va="bottom", fontsize=7.6, color="#1F1F1F", fontweight="bold")
    ax.text(3, tot_risk / WAN + 22, f"{tot_risk / WAN:,.0f}", ha="center",
            va="bottom", fontsize=7.6, color="#1F1F1F", fontweight="bold")
    ax.text(1, hi1 + 22, f"+{d_plan / WAN:,.0f}", ha="center", va="bottom",
            fontsize=7.6, color=S.C_GRID, fontweight="bold")
    ax.text(2, hi2 - 24, f"{d_emg / WAN:,.0f}", ha="center", va="top",
            fontsize=7.6, color=S.C_EMERGENCY, fontweight="bold")

    # 电量口径直接挂在差额柱上：证明"买得更多、却更便宜"
    ax.text(1, lo1 - 40, f"计划购电量 {r_plan:+.1f}%", ha="center", va="top",
            fontsize=6.5, color=S.C_GRID)
    ax.text(2, lo2 + 34, f"紧急购电量 {r_emg:+.1f}%", ha="center", va="bottom",
            fontsize=6.5, color=S.C_EMERGENCY)
    ax.text(2, hi2 - 92, "5 倍电价", ha="center", va="top", fontsize=6.5,
            color=S.C_EMERGENCY)

    # 净节约：用一条带箭头的注释指出两端高度差
    ax.annotate(
        "", xy=(3.42, tot_risk / WAN), xytext=(3.42, tot_mean / WAN),
        arrowprops=dict(arrowstyle="<->", color=S.C_SAVE, lw=1.2,
                        shrinkA=0, shrinkB=0),
    )
    ax.text(3.56, (tot_mean + tot_risk) / 2 / WAN,
            f"净节约\n{-net / WAN:,.0f} 万元",
            ha="left", va="center", fontsize=7.4, color=S.C_SAVE,
            fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=7.0)
    ax.set_ylabel("全年购电费（万元）")
    ax.set_xlim(-0.6, 4.5)
    ax.set_ylim(0, tot_mean / WAN * 1.24)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)

    S.add_panel_label(ax, "a", x=0.015, y=0.975, dx_pt=0, dy_pt=0, va="top")

    fig.text(0.006, 0.945,
             "低价确定性支出替代高价尾部风险支出", fontsize=9.6,
             fontweight="bold", color="#1A1A1A", ha="left", va="center")

    note = ("注：两策略使用同一预测器、同一实时执行规则，各自单独标定；区间为 2025-02-01 至 2025-12-31（334 天）。"
            "起点柱与终点柱为各自全年合计费用，中间两根为两者之差。数据：06_支撑材料/p2_results.json。")
    fig.text(0.006, 0.028, S.wrap_cjk(note, fontsize=6.2), fontsize=6.2,
             color="#7A7A7A", ha="left", va="bottom", linespacing=1.5)

    return fig


def main() -> None:
    S.apply_style()
    data = load_pairs()
    fig = build(data)
    saved = S.save_figure(fig, "fig05_cost_waterfall")
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
