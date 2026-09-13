# -*- coding: utf-8 -*-
r"""
Fig.6  问题三：0/6/12/18 时滚动决策时间轴——只重优化未来，绝不偷看未来
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
问题三的滚动机制不是"把四条预测曲线画在一起"，而是一条**信息随时间推进**的
决策时间轴：每天 0/6/12/18 时各发布一次整条 24 点曲线，但每次**只正式提交
当前 6 h 交付块**；该块一经提交即**永久冻结、不得回改**。因此"已执行区间"
与"未来区间"的地位完全不同——只有后者能被重新优化。

证据链（三块，各自承担一个不可替代的推理角色）
----------------------------------------------
(a) 机制 —— 时间轴甘特：每个发布时刻，哪些时段已冻结、哪些本轮提交、哪些
    只是暂定方案。四行的左侧标签给出该次发布的净负荷预报 MAE（越晚发布越准，
    因为看到的本日已实现段更多）。
(b) 个例 —— 2025-12-21 的真实调整量 Δ = g − g⁰ 逐段曲线：**第一交付块
    （0:00--6:00）的 Δ 恒为 0**，调整只出现在后三个交付块。
(c) 全体 —— 把 (b) 推广到全部 334 天：逐交付块的 |Δ| 合计。第一块**恰好**
    是 0.000 MWh，且全年 334 天中 0 天有调整。

为什么 (c) 是最强的一块
-----------------------
"不能偷看未来"在代码里只是一条约束，肉眼看不见。但把 334 天逐日的 g − g⁰
按交付块切开，第一块（0:00 发布时尚未开始、6:00 发布时已过去的那一块）的
最大调整量是 **0.000000 kWh**。已执行的时间不可能再被优化——这不是声明，
是可复算的。

数据来源（真实，无编造）
------------------------
* 06_支撑材料/p3_main_arrays.npz   —— 逐日 gP_d / gA_d（各 144 段）。d 为
  0-based 日索引；本图已核验映射：gP_354.sum() = 96566.342295，与
  p3_spec.json 中 2025-12-21 的 Gplan 完全一致。
* 06_支撑材料/p3_forecast_skill.csv —— 四个发布时刻的净负荷预报 MAE。
* 06_支撑材料/p3_calibration.json   —— best_febdec 的全年调整量汇总
  （上调 656,263.05 / 下调 775,660.56 kWh），用于交叉核对本图分块合计
  （519.9 + 669.4 + 242.6 = 1,431.9 MWh，与 1,431,923.6 kWh 一致）。

以上均为只读引用，**不重算任何模型**。

排版约束
--------
三个 panel 用 2 行网格（上行跨两列）。全部文字为普通 Unicode，不使用 mathtext
（含 `$...$` 的字符串会绕过 font.family 回退链，中文会变豆腐块）。
所有 bar / axvspan 显式 `edgecolor="none"`；交付块边界线用 `vlines` **限定在
数据带内**——若画成贯穿整个面板的 `axvline`，它会穿过图例与标注文字，被碰撞
审计判为 `text-stroke`（本图第一版实测踩到的坑）。

第二个实测坑：`add_gridspec(..., hspace=0.40)` 与 constrained layout 叠加会把
行间距放大到画布高度的 **30%**（实测 0.274），上下两行被挤成窄条、x 轴刻度
互相重叠，并触发 "axes sizes collapsed to zero" 警告。**行间距交给 constrained
layout 自己算**（不传 hspace），实测行间隙回落到 0.08，两行各得约 1/3 画布高。

图内不出现文字（本版新增）
--------------------------
按全篇规范，图内**只保留**坐标轴标签/刻度标签/panel 字母/图例；除此之外只允许
数字与符号。顶部标题句、区域名、图内结论句、底部脚注一律移入 `CAPTION` 与图下
`NOTE`，由 figstyle 的 prose gate 强制拦截（`ProseInFigureError`）。因此本版：
* 顶部大标题 → `CAPTION`
* 三个 panel 里的结论句（块1 调整量、当日上下调、334 天中 0 天有调整…）→ `NOTE`
* panel (b) 灰带里的两行「已执行 / 冻结」→ `NOTE`；灰带改染 `C_FROZEN`，
  与 panel (a) 图例「已执行并冻结」同色，靠颜色映射而非文字表意
* 图下"注" → `NOTE`
去掉上下两条文字带后画布从 132 mm 收到 114 mm，panel 反而更大了。

输出
----
04_图/pdf/fig06_rolling_timeline.pdf
04_图/pdf/fig06_rolling_timeline.svg
04_图/fig06_rolling_timeline.png
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

#: 每日 144 段 → 6 h 交付块 = 36 段；四个发布时刻
SLOTS_PER_BLOCK = 36
RELEASES = (0, 6, 12, 18)
BLOCK_NAMES = ("0:00–6:00", "6:00–12:00", "12:00–18:00", "18:00–24:00")
BLOCK_TICKS = ("块1\n0–6 h", "块2\n6–12 h", "块3\n12–18 h", "块4\n18–24 h")

#: 代表日：2025-12-21（冬至，论文特日之一，可与 p3_spec.json 交叉核对）
DAY_SHOWN = "2025-12-21"

STEM = "fig06_rolling_timeline"

#: 正文图题（进入 LaTeX \caption{}，图内不再出现）
CAPTION = "问题三的滚动决策时间轴：新预报只改变未来，已提交的 6 h 交付块永久冻结"

# 与 S.C_REF（暖灰 = 参考/边界）、S.C_GRID（墨绿 = 日前计划）**同族派生**，只改明度：
# 冻结块是"已经定下来、不可回改"的旧信息，暂定块是同一条计划曲线的浅色档。这样
# 换主调时深浅两档跟着 token 走 —— 旧版写死 "#D6D6D6" / "#BFD4EA"（浅蓝），
# 主调换暖色后这两档就成了全文唯一的蓝紫残留。
C_FROZEN = S.tint(S.C_REF, 0.62)          # 已执行并冻结（暖灰浅色）
C_PROVISIONAL = S.tint(S.C_GRID, 0.45)    # 本轮优化出的暂定方案（浅绿），待下次覆盖


def load_skill() -> dict[str, float]:
    """四个发布时刻的净负荷预报 MAE（kW）。"""
    out: dict[str, float] = {}
    with open(S.SUP_DIR / "p3_forecast_skill.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[row["release"]] = float(row["mae_kw"])
    missing = [f"{h}:00" for h in RELEASES if f"{h}:00" not in out]
    if missing:
        raise KeyError(f"p3_forecast_skill.csv 缺少发布时刻：{missing}")
    return out


def day_index(iso: str) -> int:
    """ISO 日期 → npz 的 0-based 日索引（2025-01-01 为 0）。"""
    y, m, d = (int(x) for x in iso.split("-"))
    return (date(y, m, d) - date(2025, 1, 1)).days


def block_totals(z) -> tuple[np.ndarray, np.ndarray]:
    """逐交付块的 |Δ| 合计，与"有调整的天数"。"""
    tot = np.zeros(4)
    nz = np.zeros(4, dtype=int)
    for i in range(31, 365):                    # 评价区间 2025-02-01 起 334 天
        d = np.abs(z[f"gA_{i}"] - z[f"gP_{i}"])
        for k in range(4):
            v = float(d[k * SLOTS_PER_BLOCK:(k + 1) * SLOTS_PER_BLOCK].sum())
            tot[k] += v
            nz[k] += int(v > 1e-9)
    return tot, nz


def day_stats(z, i: int) -> dict[str, float]:
    """代表日 2025-12-21 的调整量统计——供图下"注"使用（不再画进图里）。"""
    delta = z[f"gA_{i}"] - z[f"gP_{i}"]
    return {
        "block1": float(np.abs(delta[:SLOTS_PER_BLOCK]).sum()),
        "up": float(delta[delta > 0].sum()),
        "dn": float(delta[delta < 0].sum()),
        "n_seg": int((np.abs(delta) > 0.5).sum()),
    }


def build(skill: dict[str, float], z, blocks: np.ndarray) -> plt.Figure:
    S.apply_style()

    # 行间距**不显式指定** hspace：交给 constrained layout。实测传 hspace=0.40 时
    # 行间隙被放大到画布高的 30%，两行塌成窄条（见模块 docstring 的第二个坑）。
    # 高度 114 mm：已去掉顶部标题带与底部注脚带（移入 caption/note），比首版矮 18 mm。
    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(114)), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.94], wspace=0.30)
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])
    for ax in (ax_a, ax_b, ax_c):
        ax.grid(False)

    # ================================================================ (a) 时间轴
    n_rows = len(RELEASES)
    y_of = {h: n_rows - 1 - i for i, h in enumerate(RELEASES)}   # 0:00 在最上
    H = 0.52
    Y_LO, Y_HI = -0.62, 4.30          # 顶部留出图例带

    # 交付块边界：只画在数据带内（贯穿整幅会穿过图例文字 → text-stroke）
    ax_a.vlines([6, 12, 18], Y_LO + 0.10, n_rows - 1 + H / 2 + 0.05,
                color=S.C_NEUTRAL, lw=0.8, ls=":", zorder=1)

    for h in RELEASES:
        y = y_of[h]
        if h > 0:                                     # 已执行并冻结：[0, h)
            ax_a.barh(y, h, left=0, height=H, color=C_FROZEN,
                      edgecolor="none", linewidth=0, zorder=2)
        ax_a.barh(y, 6, left=h, height=H, color=S.C_GRID,   # 本轮提交的交付块
                  edgecolor="none", linewidth=0, zorder=3)
        if h + 6 < 24:                                # 暂定方案
            ax_a.barh(y, 24 - h - 6, left=h + 6, height=H, color=C_PROVISIONAL,
                      edgecolor="none", linewidth=0, zorder=2)

    ax_a.set_yticks([y_of[h] for h in RELEASES])
    # 刻度标签只放发布时刻；MAE 作为直接标注挂在每行右端（figstyle 原则 4：
    # 少用图例、优先直接标注）。若把 MAE 塞进两行刻度标签，左侧留白会从 13%
    # 涨到 21%，右列两个 panel 的可用宽度被压掉 1/4。
    ax_a.set_yticklabels([f"{h}:00 发布" for h in RELEASES], fontsize=7.5)
    ax_a.set_ylim(Y_LO, Y_HI)
    ax_a.set_xlim(0, 24)
    ax_a.set_xticks(list(range(0, 25, 6)))
    ax_a.set_xlabel("当日时刻 (h)")

    for h in RELEASES:
        ax_a.text(24.25, y_of[h], f"MAE {skill[f'{h}:00']:.0f} kW",
                  ha="left", va="center", fontsize=6.6, color=S.C_NEUTRAL)
    ax_a.set_xlim(0, 28.6)          # 右侧留出 MAE 标注带

    ax_a.legend(handles=[
        Patch(facecolor=C_FROZEN, edgecolor="none", label="已执行并冻结（不可回改）"),
        Patch(facecolor=S.C_GRID, edgecolor="none", label="本轮正式提交的交付块"),
        Patch(facecolor=C_PROVISIONAL, edgecolor="none", label="暂定方案（待下次覆盖）"),
    ], loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=3,
        handlelength=1.3, columnspacing=1.3, borderaxespad=0.0,
        labelcolor=S.C_ACTUAL)

    S.add_panel_label(ax_a, "a", x=0.0, y=1.0, dx_pt=-14, dy_pt=3.5, va="bottom")

    # ================================================================ (b) 代表日 Δ
    i = day_index(DAY_SHOWN)
    gP, gA = z[f"gP_{i}"], z[f"gA_{i}"]
    delta = gA - gP
    t = np.arange(len(delta)) * 10.0 / 60.0
    dt = 10.0 / 60.0

    band = float(np.abs(delta).max())
    ax_b.set_ylim(-band * 1.32, band * 1.32)     # 上下留白对称（结论文字已移出图外）
    ax_b.set_xlim(0, 24)
    ax_b.set_xticks(list(range(0, 25, 6)))
    ax_b.set_ylabel("调整量 Δ = g − g⁰ (kWh/10min)")
    ax_b.set_xlabel("当日时刻 (h)")

    # 冻结带铺满整个交付块：色值改用与面板 (a) 图例「已执行并冻结」同一支灰
    # （C_FROZEN + alpha 压淡），让"灰 = 已冻结"这条颜色映射跨面板成立。
    # 首版在带内写了两行「已执行 / 冻结」，已按"图内不出现文字"移入图下注。
    # 交付块分界线用 axvline 的 ymin/ymax（axes 分数）**限定在数据带内**——若贯穿
    # 全高，线头会戳进相邻文字，审计判 text-stroke（本图首版最贵的一次返工）。
    ax_b.axvspan(0, 6, ymin=0.02, ymax=0.98, facecolor=C_FROZEN, alpha=0.55,
                 edgecolor="none", linewidth=0, zorder=0)
    ax_b.bar(t, delta, width=dt * 0.92, color=S.C_RISK, edgecolor="none",
             linewidth=0, zorder=3)
    S.zero_line(ax_b, zorder=4)
    for xb in (6, 12, 18):
        ax_b.axvline(xb, ymin=0.02, ymax=0.98, color=S.C_NEUTRAL, lw=0.8,
                     ls=":", zorder=1)
    S.add_panel_label(ax_b, "b", x=0.0, y=1.0, dx_pt=-14, dy_pt=3.5, va="bottom")

    # ================================================================ (c) 分块举证
    xs = np.arange(4)
    vmax = float(blocks.max()) / 1e3
    ax_c.bar(xs, blocks / 1e3, width=0.52,
             color=[C_FROZEN] + [S.C_GRID] * 3, edgecolor="none", linewidth=0,
             zorder=3)
    ax_c.set_xticks(xs)
    ax_c.set_xticklabels(BLOCK_TICKS, fontsize=6.8)
    ax_c.set_ylabel("全年 |Δ| 合计 (MWh)")
    ax_c.set_xlabel("6 h 交付块")
    ax_c.set_ylim(0, vmax * 1.18)
    ax_c.set_xlim(-0.60, 3.60)

    for k in range(4):
        v = blocks[k] / 1e3
        if v < 1e-9:
            ax_c.text(k, vmax * 0.018, "0.000", ha="center", va="bottom",
                      fontsize=7.0, color=S.C_LOSS, fontweight="bold")
        else:
            ax_c.text(k, v + vmax * 0.02, f"{v:,.0f}", ha="center", va="bottom",
                      fontsize=6.8, color=S.C_ACTUAL, fontweight="bold")

    S.add_panel_label(ax_c, "c", x=0.0, y=1.0, dx_pt=-14, dy_pt=3.5, va="bottom")

    # 画布已无顶部标题带与底部注脚带，axes 可以吃满可用高度。
    fig.get_layout_engine().set(rect=(0.008, 0.026, 0.986, 0.930))
    return fig


def main() -> None:
    S.apply_style()
    skill = load_skill()
    z = np.load(S.SUP_DIR / "p3_main_arrays.npz")
    blocks, nz = block_totals(z)

    print("分块 |Δ| 合计 (MWh):", np.round(blocks / 1e3, 1))
    print("有调整天数 ( /334 ):", nz)
    if blocks[0] > 1e-9:
        raise AssertionError(
            f"第一交付块调整量应为 0，实际 {blocks[0]:.6f} kWh —— 冻结约束被破坏！")
    print("✓ 第一交付块调整量恒为 0（已执行即冻结）")

    i = day_index(DAY_SHOWN)
    st = day_stats(z, i)
    b1, b2, b3, b4 = (blocks[k] / 1e3 for k in range(4))
    note = (
        "注：(a) 每天 0/6/12/18 时各发布一条 24 点预报曲线，每次只正式提交当前 "
        "6 h 交付块，块一经提交即冻结；行右 MAE 为净负荷预报误差，各发布时刻覆盖"
        "时段不同，仅作趋势说明。"
        f"(b) 代表日 {DAY_SHOWN} 的调整量 Δ = g − g⁰：灰色区间为已执行并冻结的"
        f"首个交付块（0:00–6:00），其全天 |Δ| 合计为 {st['block1']:.2f} kWh；"
        f"当日上调 {st['up']:,.0f}、下调 {abs(st['dn']):,.0f} kWh，"
        f"全天 {st['n_seg']}/144 段发生变动。"
        f"(c) 四个交付块的全年 |Δ| 合计依次为 {b1:.1f} / {b2:.1f} / {b3:.1f} / "
        f"{b4:.1f} MWh，其中第一块 {nz[0]}/334 天有调整，其余三块分别为 "
        f"{nz[1]} / {nz[2]} / {nz[3]} 天。"
        "数据：06_支撑材料/p3_main_arrays.npz 的 gP_d（初始计划）与 gA_d（最终执行）；"
        f"分块合计 {b2:.1f} + {b3:.1f} + {b4:.1f} MWh 与 p3_calibration.json 的"
        "上调 656,263.05 / 下调 775,660.56 kWh 之和一致（只读引用，未重算模型）。"
    )

    fig = build(skill, z, blocks)
    saved = S.save_figure(fig, STEM, caption=CAPTION, note=note)
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
