# -*- coding: utf-8 -*-
r"""
Fig.2  问题一：低价购电 → 储能充电 → 高价放电的确定性调度机制
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
问题一的确定性 MILP 不是"给出一条购电曲线"，而是**用储能把高价时段的刚性
购电需求搬运到低价时段**：电价低谷买电并充电、电价高峰放电顶负荷，全天
购电费因此低于任一"不调度储能"的可行方案。

证据链（四个 panel 是同一条因果链的四个环节，故共享横轴并纵向对齐）
------------------------------------------------------------------
(a) 电价       —— 外生价格信号，标出低谷/高峰两个窗口
(b) 计划购电量 —— 决策本身：购电是否真的被压到低谷窗口
(c) 充放电量   —— 搬运机制：低谷充电、高峰放电
(d) 储电量     —— 搬运的后果：SOC 低谷抬升、高峰回落，且两端触限

数据来源（全部为真实模型输出，无任何编造）
------------------------------------------
06_支撑材料/p1_detail.csv —— 由 03_代码/p1_microgrid.py 求解附件1 得到的
144 个 10 分钟时段明细。本图**只读 CSV、不重算模型**，保证与论文数值一致。

旧图处理
--------
取代 p1_fig1_profiles / p1_fig2_purchase / p1_fig3_storage 三张分散单点图。
原图保留不删，以免破坏 LaTeX 现有引用；论文改写时再决定是否移除。

排版约束
--------
panel 字母放在轴内左上角，**不放轴外左侧**——轴外左侧正是 y 刻度数字的位置，
早期版本因此被判 text-text 重叠。每幅 panel 的结论写在轴内右上角，与左侧
字母分处两端，互不相犯；不再使用 set_title / legend，避免顶部三条文本打架。

输出
----
04_图/pdf/fig02_p1_dispatch.pdf
04_图/fig02_p1_dispatch.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

#: 物理常量（仅用于画参考线，不参与计算；与 p1_microgrid.py 一致）
E_MIN, E_MAX, E_INIT = 1200.0, 10800.0, 6000.0

#: 低谷/高峰窗口的分位阈值：由当日电价自身决定，不引入外部假设
P_LOW, P_HIGH = 25, 75

#: 窗口底纹分别呼应"充电(绿)"与"放电(紫)"，颜色本身即语义
BAND_LOW = "#ECF3E3"
BAND_HIGH = "#F5E7E0"

#: 轴内文本位置（axes fraction）
XY_LABEL = (0.012, 0.985)     # panel 字母（轴内左上）


def hours(n: int) -> np.ndarray:
    """各时段起始时刻（小时）。"""
    return np.arange(n) * 10.0 / 60.0


def contiguous_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """把布尔掩码切成若干段连续 True 的 [起, 止) 下标区间。"""
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def build(df: pd.DataFrame) -> plt.Figure:
    """绘制 Fig.2。四 panel 共享横轴。"""
    S.apply_style()

    n = len(df)
    t = hours(n)
    dt = 10.0 / 60.0
    price = df["电价_元每kWh"].to_numpy(float)
    buy = df["购电量_kWh"].to_numpy(float)
    chg = df["充电量_kWh"].to_numpy(float)
    dis = df["放电量_kWh"].to_numpy(float)
    soc = np.concatenate([[df["期初储电量_kWh"].to_numpy(float)[0]],
                          df["期末储电量_kWh"].to_numpy(float)])
    t_soc = np.concatenate([[0.0], t + dt])

    lo_thr = float(np.percentile(price, P_LOW))
    hi_thr = float(np.percentile(price, P_HIGH))
    low_runs = contiguous_runs(price <= lo_thr)
    high_runs = contiguous_runs(price >= hi_thr)

    fig, axes = plt.subplots(
        4, 1, figsize=(S.mm2in(160), S.mm2in(126)), sharex=True,
        gridspec_kw={"height_ratios": [1.0, 1.0, 1.0, 1.05], "hspace": 0.20},
    )
    ax_p, ax_b, ax_c, ax_s = axes

    # 关掉网格：matplotlib 的网格线是贯穿整幅 panel 的描边路径，任何 panel 内
    # 文字都会被最近的网格线穿过，碰撞审计一律判 text-stroke。这组图靠填充色与
    # 直接标注读值，网格并非必要。
    for ax in axes:
        ax.grid(False)

    # ---------------------------------------------------------- 窗口底纹
    for ax in axes:
        for a, b in low_runs:
            ax.axvspan(t[a], t[b - 1] + dt, facecolor=BAND_LOW,
                       edgecolor="none", linewidth=0, zorder=0)
        for a, b in high_runs:
            ax.axvspan(t[a], t[b - 1] + dt, facecolor=BAND_HIGH,
                       edgecolor="none", linewidth=0, zorder=0)

    # ---------------------------------------------------------- (a) 电价
    ax_p.step(t, price, where="post", color=S.C_PRICE, lw=1.5)
    ax_p.set_ylabel("电价\n(元/kWh)")
    ax_p.set_ylim(price.min() * 0.84, price.max() * 1.22)
    S.add_panel_label(ax_p, "a", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")
    # 低谷/高峰窗口不在轴内写字：电价折线恰好穿过窗口所在的 y 区间，
    # 任何贴线标注都会被折线穿过（碰撞审计判 text-stroke）。改由整图图例说明。

    # ---------------------------------------------------------- (b) 计划购电量
    ax_b.bar(t, buy, width=dt * 0.94, color=S.C_GRID, alpha=0.92, lw=0)
    ax_b.set_ylabel("计划购电量\n(kWh/10min)")
    ax_b.set_ylim(0, buy.max() * 1.32)
    S.add_panel_label(ax_b, "b", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")

    # ---------------------------------------------------------- (c) 充放电量
    ax_c.bar(t, chg, width=dt * 0.94, color=S.C_CHARGE, alpha=0.92, lw=0)
    ax_c.bar(t, -dis, width=dt * 0.94, color=S.C_DISCHARGE, alpha=0.92, lw=0)
    S.zero_line(ax_c)
    m = max(chg.max(), dis.max())
    ax_c.set_ylim(-m * 1.45, m * 1.45)
    ax_c.set_ylabel("充 / 放电量\n(kWh/10min)")
    S.add_panel_label(ax_c, "c", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")
    # 制度说明写在轴内右上角：充电集中在日出前，若把标签放在低谷窗口中心会正好
    # 撞上轴内左上角的 panel 字母。绿/紫两色本身已把充电与放电分开。

    # ---------------------------------------------------------- (d) 储电量
    ax_s.plot(t_soc, soc, color=S.C_SOC, lw=1.9, zorder=4)
    ax_s.fill_between(t_soc, E_MIN, soc, color=S.C_SOC, alpha=0.11, lw=0,
                      edgecolor="none", zorder=2)
    for yv in (E_MAX, E_MIN):
        ax_s.axhline(yv, color=S.C_REF, ls=":", lw=1.0, zorder=3)
    ax_s.axhline(E_INIT, color=S.C_REF, ls="-.", lw=0.9, zorder=3)
    ax_s.set_ylim(0, E_MAX * 1.30)
    ax_s.set_xlim(0, 24)
    ax_s.set_xticks(range(0, 25, 2))
    ax_s.set_xlabel("时刻 (h)")
    ax_s.set_ylabel("储电量 (kWh)\n运行区间 1200–10800")
    S.add_panel_label(ax_s, "d", x=XY_LABEL[0], y=XY_LABEL[1],
                      dx_pt=0, dy_pt=0, va="top")

    from matplotlib.patches import Patch
    handles = [Patch(facecolor=BAND_LOW, edgecolor="none",
                     label=f"低谷窗口（电价 ≤{lo_thr:.3f} 元/kWh）"),
               Patch(facecolor=BAND_HIGH, edgecolor="none",
                     label=f"高峰窗口（电价 ≥{hi_thr:.3f} 元/kWh）")]
    # 图例另起一行排在标题下方：标题很长，与图例同处一行会直接压字。
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.995, 0.995),
               ncol=2, fontsize=6.8, frameon=False, handlelength=1.2,
               columnspacing=1.4)

    # 图内不放标题与结论句：一律移到正文的 \caption 与「注」。
    # 图内只保留坐标轴、刻度数字、panel 字母与图例（全篇插图规范）。
    fig.subplots_adjust(top=0.945)
    return fig


def main() -> None:
    S.apply_style()
    df = pd.read_csv(S.SUP_DIR / "p1_detail.csv", encoding="utf-8-sig")
    if len(df) != 144:
        raise ValueError(f"p1_detail.csv 应有 144 行，实际 {len(df)} 行")

    fig = build(df)
    saved = S.save_figure(fig, "fig02_p1_dispatch")
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
