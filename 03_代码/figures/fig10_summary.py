# -*- coding: utf-8 -*-
r"""
Fig.10  全文总结：四问逐层叠加——费用指数与尾部代价
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
四个问题不是各自为战，而是**同一套闭环模型逐层加能力**。把每一问的本文策略
与**该问自己的朴素基线**相比（基线 = 100%），四问的费用指数分别是
**73.1% / 93.5% / 89.6% / 99.7%**——**每一层都不亏**；而尾部代价（紧急购电费）
在 P2、P3 上分别被压到基线的 **27.9% / 11.5%**。

为什么必须"各问自比"
--------------------
P1 用附件 1 的给定曲线做单日确定性调度；P2、P3 用它做全年滚动；**P4 换用附件 4
的波动电价**。四问的费用口径与电价情景不同，**绝对值不可直接横比**。因此本图
统一用"相对该问朴素基线的百分比"，这样四层才能放在同一把尺子上。

四问的朴素基线（同一模型、少一项能力）
--------------------------------------
* P1：无储能（同样买电、同样弃光）
* P2：预测均值策略（不加分位风险余量）
* P3：只用 0:00 预报（不使用 6/12/18 的更新）
* P4：固定电价参考（忽略价格波动）

数据来源（真实，无编造）
------------------------
* 06_支撑材料/p1_results.json      —— 主模型 total_cost 与 benchmarks.无储能_购电费
* 06_支撑材料/p2_results.json      —— 对照策略：风险修正 / 预测均值
* 06_支撑材料/p3_analysis.json     —— configs：只用0:00预报 / 6:00+12:00+18:00
* 06_支撑材料/p4_strategies.csv    —— 4-3 分支的 固定电价参考 / 波动电价预测

本图只做读取与相除，**不重算任何模型、不编造任何数值**。

排版约束
--------
全部文字为普通 Unicode，不使用 mathtext；所有 bar 显式 `edgecolor="none"`；
关掉网格。两面板用 constrained layout，**不显式传 hspace**。

图内不出现文字（本版新增）
--------------------------
图内只留坐标轴标签/刻度标签/panel 字母/图例；除此之外只允许数字与符号
（费用指数、紧急费、`−72.1%`）。原先柱顶第二行「(省 26.9%)」与左下角
「基线 = 100%」两处汉字已删——前者移入 `NOTE`，后者由纵轴标签独立承担口径。
顶部标题句、panel (b) 的结论句、底部脚注全部移入 `CAPTION` / `NOTE`，
由 figstyle 的 prose gate 拦截。去掉上下两条文字带后画布从 100 mm 收到 88 mm。

输出
----
04_图/pdf/fig10_summary.pdf
04_图/pdf/fig10_summary.svg
04_图/fig10_summary.png
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

WK = 1e-4                       # 元 → 万元

STEM = "fig10_summary"

#: 正文图题（进入 LaTeX \caption{}，图内不再出现）
CAPTION = "四问逐层叠加：每一层都相对自己的朴素基线更省，尾部代价同步压缩"

#: 四问的显示名、基线名、语义色（沿用全篇色板的物理含义）
LAYERS = (
    ("P1", "单日调度", "无储能", S.C_CHARGE),
    ("P2", "风险滚动", "预测均值", S.C_RISK),
    ("P3", "多预报滚动", "只用 0:00 预报", S.C_FORECAST),
    ("P4", "波动电价", "固定电价参考", S.C_PRICE),
)


# ================================================================ 数据

def load_all() -> list[dict]:
    """读四问的 (基线费用, 本文费用, 基线紧急费, 本文紧急费)，单位元。"""
    out: list[dict] = []

    d1 = json.load(open(S.SUP_DIR / "p1_results.json", encoding="utf-8"))
    out.append({"base": float(d1["benchmarks"]["无储能_购电费"]),
                "ours": float(d1["main"]["total_cost"]),
                "base_emg": None, "ours_emg": None})

    d2 = json.load(open(S.SUP_DIR / "p2_results.json", encoding="utf-8"))["对照策略"]
    a = d2["本文风险修正策略（主模型）"]
    b = d2["预测均值策略（不加分位风险余量）"]
    out.append({"base": float(b["合计购电费_元"]), "ours": float(a["合计购电费_元"]),
                "base_emg": float(b["紧急购电费_元"]),
                "ours_emg": float(a["紧急购电费_元"])})

    d3 = json.load(open(S.SUP_DIR / "p3_analysis.json", encoding="utf-8"))["configs"]
    b3 = d3["对照：只用0:00预报"]
    a3 = d3["6:00+12:00+18:00"]
    out.append({"base": float(b3["total"]), "ours": float(a3["total"]),
                "base_emg": float(b3["emg"]), "ours_emg": float(a3["emg"])})

    d4: dict[str, dict] = {}
    with open(S.SUP_DIR / "p4_strategies.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["分支"].strip() != "4-3":
                continue
            d4[row["策略"].strip()] = {
                "total": float(row["合计费用_元"]),
                "emg": float(row["紧急费_元"]),
            }
    out.append({"base": d4["固定电价参考策略"]["total"],
                "ours": d4["波动电价预测策略"]["total"],
                "base_emg": d4["固定电价参考策略"]["emg"],
                "ours_emg": d4["波动电价预测策略"]["emg"]})
    return out


# ================================================================ 画图

def build(rows: list[dict]) -> plt.Figure:
    S.apply_style()

    # 高度 88 mm：已去掉顶部标题带与底部注脚带（移入 caption/note），比首版矮 12 mm。
    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(88)), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.10, 1.0], wspace=0.26)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    for ax in (ax_a, ax_b):
        ax.grid(False)

    idx = np.array([100.0 * r["ours"] / r["base"] for r in rows])
    xs = np.arange(4)

    # ============================================================ (a) 费用指数
    ax_a.axhline(100, color=S.C_REF, lw=0.9, ls="--", zorder=2)
    ax_a.bar(xs, idx, 0.60, edgecolor="none", linewidth=0, zorder=3,
             color=[c for _, _, _, c in LAYERS])
    for x, v in zip(xs, idx):
        # 柱顶只留指数一项。原先第二行还写了「(省 26.9%)」，汉字已移入图下注；
        # 读数行固定在 100% 基线之上，避免与基线相切。
        ax_a.text(x, 103.5, f"{v:.1f}%", ha="center", va="bottom", fontsize=6.5,
                  color=S.C_ACTUAL, fontweight="bold", zorder=5)
    # 原先在左下角写「基线 = 100%」：纵轴标签已完整表述该口径
    # （费用指数（各自朴素基线 = 100%）），图内不再重复。
    ax_a.set_xlim(-0.62, 3.62)
    ax_a.set_ylim(0, 116)
    ax_a.set_xticks(xs)
    ax_a.set_xticklabels([f"{p}\n{name}" for p, name, _, _ in LAYERS], fontsize=6.8)
    ax_a.set_ylabel("费用指数（各自朴素基线 = 100%）")
    S.add_panel_label(ax_a, "a", x=0.0, y=1.0, dx_pt=-15, dy_pt=3.5, va="bottom")

    # ============================================================ (b) 尾部代价
    # (b) 只列 P2、P3：两者同为附件 1 电价情景，紧急费口径可比
    pe = [rows[1], rows[2]]
    labels = ["P2", "P3"]
    base_e = np.array([r["base_emg"] * WK for r in pe])
    ours_e = np.array([r["ours_emg"] * WK for r in pe])
    xp = np.arange(len(pe))
    w = 0.34
    ax_b.bar(xp - w / 2 - 0.01, base_e, w, color=S.tint(S.C_NEUTRAL, 0.62), edgecolor="none",
             linewidth=0, zorder=3, label="朴素基线")
    ax_b.bar(xp + w / 2 + 0.01, ours_e, w, color=S.C_EMERGENCY, edgecolor="none",
             linewidth=0, zorder=3, label="本文做法")
    for x, b_, o_ in zip(xp, base_e, ours_e):
        ax_b.text(x - w / 2 - 0.01, b_ + 4, f"{b_:.0f}", ha="center", va="bottom",
                  fontsize=6.5, color=S.C_NEUTRAL, fontweight="bold", zorder=5)
        ax_b.text(x + w / 2 + 0.01, o_ + 4, f"{o_:.0f}", ha="center", va="bottom",
                  fontsize=6.5, color=S.C_EMERGENCY, fontweight="bold", zorder=5)
        ax_b.text(x, max(b_, o_) + 26, f"−{100 * (1 - o_ / b_):.1f}%", ha="center",
                  va="bottom", fontsize=6.8, color=S.C_EMERGENCY, fontweight="bold",
                  zorder=5)
    ax_b.set_xlim(-0.62, len(pe) - 0.38)
    ax_b.set_ylim(0, 340)
    ax_b.set_xticks(xp)
    ax_b.set_xticklabels([f"{lab}\n{LAYERS[int(lab[1]) - 1][1]}" for lab in labels],
                         fontsize=6.8)
    ax_b.set_ylabel("紧急购电费（万元）")
    ax_b.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0), ncol=1,
                handlelength=1.3, borderaxespad=0.0)
    S.add_panel_label(ax_b, "b", x=0.0, y=1.0, dx_pt=-15, dy_pt=3.5, va="bottom")

    # 画布已无顶部标题带与底部注脚带，axes 吃满可用高度。
    fig.get_layout_engine().set(rect=(0.008, 0.024, 0.986, 0.932))
    return fig


def main() -> None:
    S.apply_style()
    rows = load_all()
    names = ["P1", "P2", "P3", "P4"]
    for n, r in zip(names, rows):
        i = 100 * r["ours"] / r["base"]
        print(f"{n}: 基线 {r['base']:,.2f} → 本文 {r['ours']:,.2f} 元  "
              f"指数 {i:.2f}%")
        if r["base_emg"] is not None:
            print(f"    紧急费 {r['base_emg'] * WK:.2f} → {r['ours_emg'] * WK:.2f} 万元 "
                  f"(−{100 * (1 - r['ours_emg'] / r['base_emg']):.1f}%)")

    ok = all(r["ours"] <= r["base"] + 1e-6 for r in rows)
    print("✓ 四问本文策略均不劣于各自朴素基线" if ok else "✗ 存在反例")
    if not ok:
        raise AssertionError("存在本文策略劣于基线的问，图的口径需要复核")

    def wan(i: int) -> str:
        return f"{rows[i]['base'] * WK:,.2f} → {rows[i]['ours'] * WK:,.2f}"

    idx = [100.0 * r["ours"] / r["base"] for r in rows]
    note = (
        "注：(a) 纵轴 = 各问「本文策略 / 该问朴素基线」的费用比，虚线为基线 = 100%；"
        "柱顶读数即该指数，柱顶到 100% 的距离即相对基线的节约比例。"
        "四问的费用指数依次为 "
        + " / ".join(f"{v:.1f}%" for v in idx)
        + "，即分别省 "
        + " / ".join(f"{100 - v:.1f}%" for v in idx)
        + "。绝对费用（万元；P1 为万元/日）："
        f"P1 {wan(0)}；P2 {wan(1)}；P3 {wan(2)}；P4 {wan(3)}。"
        "基线定义：P1 无储能、P2 预测均值（不加风险余量）、P3 只用 0:00 预报、"
        "P4 固定电价参考——同一套模型、各少一项能力。"
        "四问的费用口径与电价情景不同（P1 为单日、P2 与 P3 为全年附件 1 情景、"
        "P4 换用附件 4 的波动电价），故各问自比，绝对值不可横向比较。"
        "(b) 只列可比的两问（同附件 1 情景）：紧急购电费由 P2 的 "
        f"{rows[1]['base_emg'] * WK:.2f} 与 P3 的 {rows[2]['base_emg'] * WK:.2f} 万元，"
        f"分别降至 {rows[1]['ours_emg'] * WK:.2f} 与 {rows[2]['ours_emg'] * WK:.2f} 万元"
        f"（−{100 * (1 - rows[1]['ours_emg'] / rows[1]['base_emg']):.1f}% 与 "
        f"−{100 * (1 - rows[2]['ours_emg'] / rows[2]['base_emg']):.1f}%）。"
        "数据：06_支撑材料 的 p1/p2/p3/p4 结果文件（只读引用，只做读取与相除）。"
    )

    fig = build(rows)
    saved = S.save_figure(fig, STEM, caption=CAPTION, note=note)
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
