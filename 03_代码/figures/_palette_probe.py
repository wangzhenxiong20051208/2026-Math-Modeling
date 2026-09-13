# -*- coding: utf-8 -*-
r"""
配色候选对比图（QA / 选型工具，非交付件）
================================================================================

用户反馈：现有配色"蓝紫调太重、AI 味太浓、太浅、不够醒目"。
色感是主观的，靠文字描述定不下来，故用**真实数据**把三套候选配色渲染出来，
放在同一张图上对比，由人来挑。

三套候选的设计取向
------------------
1. **赤陶**：暖调主导，彻底去蓝紫。赭石/焦橙/墨绿/绛红，接近印刷品与地质图
   的传统配色，最不像"技术图表"。
2. **墨金**：灰阶压住画面，只留金与朱两处高饱和。接近编辑设计/版画，克制、
   沉、有分量；但颜色之间靠明度区分，注意力更集中。
3. **高对比**：直接回应"不够醒目"——提高饱和度与明度差，红绿对撞明确。
   最抓眼，但也最容易显"跳"。

三套都遵守同一条语义主线：**蓝紫被移出**；暖色承担价格与代价，
绿系承担储能动作，深墨承担"实际发生"。

运行：python 03_代码/figures/_palette_probe.py
输出：04_图/qa/_palette_probe.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

# ================================================================ 候选配色
# 每个候选按同一组语义角色给出 9 个颜色。
CANDIDATES: list[tuple[str, str, dict[str, str]]] = [
    ("候选一 · 赤陶", "暖调主导、彻底去蓝紫：赭石 / 焦橙 / 墨绿 / 绛红，接近印刷品配色",
     {
         "C_PRICE":     "#B4531F",   # 电价：焦橙
         "C_FORECAST":  "#8A7A66",   # 预测：暖灰褐
         "C_RISK":      "#E39A2A",   # 风险修正：琥珀
         "C_ACTUAL":    "#1A1A1A",   # 实际：墨黑
         "C_GRID":      "#1E5B4C",   # 计划购电：墨绿
         "C_EMERGENCY": "#C1272D",   # 紧急购电：朱红
         "C_CHARGE":    "#4A8B2C",   # 充电：草绿
         "C_DISCHARGE": "#8C3A2B",   # 放电：赭红
         "C_SOC":       "#0F5C50",   # 储电量：深松绿
     }),
    ("候选二 · 墨金", "灰阶压场、只留金朱两处高饱和：克制、有分量，靠明度分层",
     {
         "C_PRICE":     "#9A6B2F",   # 电价：暗金褐
         "C_FORECAST":  "#9B9B93",   # 预测：中灰
         "C_RISK":      "#D4A017",   # 风险修正：金
         "C_ACTUAL":    "#111111",   # 实际：纯墨
         "C_GRID":      "#3F4A3C",   # 计划购电：墨橄榄
         "C_EMERGENCY": "#B3261E",   # 紧急购电：深朱
         "C_CHARGE":    "#5C8A3C",   # 充电：橄榄绿
         "C_DISCHARGE": "#7A4A2E",   # 放电：深棕
         "C_SOC":       "#2A5A50",   # 储电量：墨松绿
     }),
    ("候选三 · 高对比", "直接回应「不够醒目」：提高饱和度与明度差，红绿对撞明确",
     {
         "C_PRICE":     "#E8590C",   # 电价：亮橙
         "C_FORECAST":  "#6C757D",   # 预测：中灰
         "C_RISK":      "#F2A516",   # 风险修正：亮金
         "C_ACTUAL":    "#0A0A0A",   # 实际：纯黑
         "C_GRID":      "#0B6E4F",   # 计划购电：翠绿
         "C_EMERGENCY": "#E03131",   # 紧急购电：亮红
         "C_CHARGE":    "#2F9E44",   # 充电：亮绿
         "C_DISCHARGE": "#B54A2E",   # 放电：赭红
         "C_SOC":       "#10785F",   # 储电量：深翠
     }),
]

#: 色板角色 → 中文标签（与 figstyle 语义表一致）
ROLES = [
    ("C_PRICE", "电价"), ("C_FORECAST", "预测"), ("C_RISK", "风险修正"),
    ("C_ACTUAL", "实际"), ("C_GRID", "计划购电"), ("C_EMERGENCY", "紧急购电"),
    ("C_CHARGE", "充电"), ("C_DISCHARGE", "放电"), ("C_SOC", "储电量"),
]

BLOCK_H = 60.0          # 每个候选块占的画布高度（y 单位）
SWATCH_H = 3.6


def mini_panels(fig, x0, y0, w, h, pal, df) -> None:
    """用真实 P1 数据画 4 个迷你面板，仅用于判断配色。"""
    t = np.arange(len(df)) * 10.0 / 60.0
    dt = 10.0 / 60.0
    price = df["电价_元每kWh"].to_numpy(float)
    buy = df["购电量_kWh"].to_numpy(float)
    chg = df["充电量_kWh"].to_numpy(float)
    dis = df["放电量_kWh"].to_numpy(float)
    soc = np.concatenate([[df["期初储电量_kWh"].to_numpy(float)[0]],
                          df["期末储电量_kWh"].to_numpy(float)])
    tS = np.concatenate([[0.0], t + dt])

    ph = h / 4.0
    specs = [
        ("电价", lambda ax: ax.step(t, price, where="post",
                                    color=pal["C_PRICE"], lw=1.3)),
        ("计划购电量", lambda ax: ax.bar(t, buy, width=dt * 0.94,
                                         color=pal["C_GRID"], lw=0, alpha=0.95)),
        ("充 / 放电量", None),
        ("储电量", lambda ax: ax.plot(tS, soc, color=pal["C_SOC"], lw=1.7)),
    ]
    for i, (name, fn) in enumerate(specs):
        ax = fig.add_axes((x0, y0 + (3 - i) * ph, w, ph * 0.86))
        ax.grid(False)
        if name == "充 / 放电量":
            ax.bar(t, chg, width=dt * 0.94, color=pal["C_CHARGE"], lw=0, alpha=0.95)
            ax.bar(t, -dis, width=dt * 0.94, color=pal["C_DISCHARGE"], lw=0,
                   alpha=0.95)
            ax.axhline(0, color="#4D4D4D", lw=0.7)
        else:
            fn(ax)
        ax.set_xlim(0, 24)
        ax.set_ylim(bottom=0) if name != "充 / 放电量" else None
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=5.4, length=1.6, pad=1.2)
        ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_ylabel(name, fontsize=5.6, labelpad=1.5)


def build(df: pd.DataFrame) -> plt.Figure:
    S.apply_style()
    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(206)))

    y = 97.0
    for title, desc, pal in CANDIDATES:
        fig.text(0.008, (y + 2.6) / 100, title, fontsize=9.0, fontweight="bold",
                 color="#1A1A1A", va="top")
        # 色卡条：一行 9 格。与下方迷你图之间留出足量空隙——
        # 角色标签若落在迷你图的纵向范围内，会直接压在电价面板上。
        sw_y = y - 2.0
        for i, (key, zh) in enumerate(ROLES):
            x = 0.008 + i * 0.1095
            fig.patches.append(Rectangle(
                (x, (sw_y) / 100 * 0.98), 0.086, SWATCH_H / 100 * 0.98,
                transform=fig.transFigure, facecolor=pal[key],
                edgecolor="none"))
            fig.text(x + 0.043, (sw_y - 4.8) / 100, zh, fontsize=5.8,
                     color="#4D4D4D", ha="center", va="top")

        mini_panels(fig, 0.105, (y - 56.0) / 100, 0.88, 0.415, pal, df)
        y -= BLOCK_H + 3.4

    return fig


def main() -> None:
    S.apply_style()
    df = pd.read_csv(S.SUP_DIR / "p1_detail.csv", encoding="utf-8-sig")
    fig = build(df)
    out = S.FIG_QA / "_palette_probe.png"
    fig.savefig(out, dpi=170, bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    plt.close(fig)
    print("已输出：", out.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
