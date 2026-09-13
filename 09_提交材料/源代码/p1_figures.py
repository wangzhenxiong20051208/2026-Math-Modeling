# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题一 —— 论文插图生成
输出到 04_图/，300 dpi，供 LaTeX 直接 \includegraphics 引用。
运行：python3 03_代码/p1_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cumcm_plot import savefig, setup_plot  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1_microgrid as M  # noqa: E402

setup_plot()

# 统一配色
C_PRICE = "#c0392b"   # 电价 红
C_LOAD = "#2c3e50"    # 负载 深蓝
C_PV = "#e8a33d"      # 光伏 橙
C_BUY = "#2980b9"     # 购电 蓝
C_CHG = "#27ae60"     # 充电 绿
C_DIS = "#8e44ad"     # 放电 紫
C_SOC = "#16a085"     # 储电量 青


def hours(n: int = M.N) -> np.ndarray:
    """区间起始时刻（小时）。"""
    return np.arange(n) * 10 / 60


def fig1_profiles(df) -> None:
    """图 1：单日电价、小区负载与光伏发电预测功率。"""
    t = hours()
    price = df["电价"].to_numpy(float)
    load = df["小区负载"].to_numpy(float)
    pv = df["光伏发电预测功率"].to_numpy(float)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 4.05), sharex=True,
        gridspec_kw={"height_ratios": [1, 1.35], "hspace": 0.12},
    )

    ax1.plot(t, price, color=C_PRICE, lw=1.3)
    ax1.fill_between(t, price, price.min() * 0.985, color=C_PRICE, alpha=0.12)
    ax1.set_ylabel("电价 (元/kWh)")
    ax1.set_ylim(price.min() * 0.985, price.max() * 1.02)
    # 图内不写"图 N"：LaTeX 的 \caption 才负责编号，写死在这里会与真实编号冲突
    ax1.set_title("单日电价、小区负载与光伏发电预测功率", fontsize=12)

    ax2.plot(t, load, color=C_LOAD, lw=1.6, label="小区负载")
    ax2.plot(t, pv, color=C_PV, lw=1.6, label="光伏发电预测功率")
    ax2.fill_between(t, 0, pv, color=C_PV, alpha=0.18)
    ax2.set_ylabel("功率 (kW)")
    ax2.set_xlabel("时刻 (h)")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 2))
    ax2.set_ylim(0, None)
    ax2.legend(loc="upper left", ncol=2, framealpha=0.9)

    savefig("p1_fig1_profiles.png")


def fig2_purchase(sol, df) -> None:
    """图 2：计划购电量与电价。"""
    t = hours()
    buy = sol.g * M.TAU          # 每 10 分钟购电量 kWh
    price = df["电价"].to_numpy(float)

    fig, ax = plt.subplots(figsize=(9, 3.15))
    ax.bar(t, buy, width=10 / 60 * 0.92, color=C_BUY, alpha=0.85,
           label="计划购电量 (kWh/10min)")
    ax.set_xlabel("时刻 (h)")
    ax.set_ylabel("购电量 (kWh/10min)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_ylim(0, buy.max() * 1.18)
    ax.set_title("全天计划购电量与电价", fontsize=12)

    ax2 = ax.twinx()
    ax2.plot(t, price, color=C_PRICE, lw=1.3, label="电价 (元/kWh)")
    ax2.set_ylabel("电价 (元/kWh)", color=C_PRICE)
    ax2.tick_params(axis="y", labelcolor=C_PRICE)
    ax2.grid(False)
    ax2.set_ylim(price.min() * 0.9, price.max() * 1.25)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", framealpha=0.9)

    savefig("p1_fig2_purchase.png")


def fig3_storage(sol) -> None:
    """图 3：储能充放电功率与储电量轨迹（上下双栏，避免双轴量纲混淆）。"""
    t = hours()
    chg = sol.c                     # kW
    dis = sol.d                     # kW，向下画
    E = np.concatenate([[sol.E0], sol.E])
    tE = np.concatenate([[0.0], t + 10 / 60])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 4.35), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.12},
    )

    # 上栏：充放电功率
    ax1.fill_between(t, 0, chg, step="post", color=C_CHG, alpha=0.8, label="充电功率")
    ax1.fill_between(t, 0, -dis, step="post", color=C_DIS, alpha=0.8, label="放电功率")
    ax1.axhline(0, color="k", lw=0.8)
    ax1.axhline(M.P_MAX, color=C_CHG, ls="--", lw=0.9)
    ax1.axhline(-M.P_MAX, color=C_DIS, ls="--", lw=0.9)
    ax1.set_ylabel("充/放电功率 (kW)")
    ax1.set_ylim(-M.P_MAX * 1.3, M.P_MAX * 1.3)
    ax1.legend(loc="lower right", ncol=2, framealpha=0.9)
    ax1.set_title("储能设备充放电功率与储电量", fontsize=12)
    ax1.text(0.25, M.P_MAX * 1.04, "功率上限 +5000 kW", color=C_CHG, fontsize=8.5)
    ax1.text(0.25, -M.P_MAX * 1.24, "功率下限 -5000 kW", color=C_DIS, fontsize=8.5)

    # 下栏：储电量
    ax2.plot(tE, E, color=C_SOC, lw=2.0)
    ax2.fill_between(tE, M.E_MIN, np.minimum(E, M.E_MAX), color=C_SOC, alpha=0.14)
    ax2.axhline(M.E_MAX, color=C_SOC, ls=":", lw=1.1)
    ax2.axhline(M.E_MIN, color=C_SOC, ls=":", lw=1.1)
    ax2.axhline(M.E_INIT, color="gray", ls="-.", lw=1.0)
    ax2.set_ylabel("储电量 (kWh)")
    ax2.set_xlabel("时刻 (h)")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 2))
    ax2.set_ylim(0, M.E_MAX * 1.2)
    ax2.text(0.25, M.E_MAX * 1.05, "储电量上限 10800 kWh", color=C_SOC, fontsize=8.5)
    ax2.text(0.25, M.E_MIN + 280, "储电量下限 1200 kWh", color=C_SOC, fontsize=8.5)
    ax2.text(12.3, M.E_INIT + 260, "0:00 / 24:00 储电量 6000 kWh", color="gray", fontsize=8.5)

    savefig("p1_fig3_storage.png")


def fig4_balance(sol, df) -> None:
    """图 4：全天能量平衡（供给侧构成 vs 需求侧构成）。"""
    tau = M.TAU
    pv_kwh = float((df["光伏发电预测功率"].to_numpy(float) * tau).sum())
    load_kwh = float((df["小区负载"].to_numpy(float) * tau).sum())
    buy_kwh = float((sol.g * tau).sum())
    dis_kwh = float((sol.d * tau).sum())
    chg_kwh = float((sol.c * tau).sum())

    supply = [("光伏发电", pv_kwh, C_PV), ("电网购电", buy_kwh, C_BUY),
              ("储能放电", dis_kwh, C_DIS)]
    demand = [("小区负载", load_kwh, C_LOAD), ("储能充电", chg_kwh, C_CHG)]

    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    top = 0.0
    for name, val, col in supply:
        ax.bar(0, val, bottom=top, width=0.52, color=col, alpha=0.88,
               edgecolor="white", lw=0.8)
        ax.text(0, top + val / 2, f"{name}\n{val:,.0f} kWh", ha="center",
                va="center", fontsize=9, color="white", fontweight="bold")
        top += val
    total = top
    top = 0.0
    for name, val, col in demand:
        ax.bar(1, val, bottom=top, width=0.52, color=col, alpha=0.88,
               edgecolor="white", lw=0.8)
        ax.text(1, top + val / 2, f"{name}\n{val:,.0f} kWh", ha="center",
                va="center", fontsize=9, color="white", fontweight="bold")
        top += val
    ax.text(0, total * 1.02, f"合计 {total:,.0f} kWh", ha="center", fontsize=9)
    ax.text(1, total * 1.02, f"合计 {top:,.0f} kWh", ha="center", fontsize=9)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["供给侧", "需求侧"])
    ax.set_ylabel("电量 (kWh)")
    ax.set_ylim(0, total * 1.12)
    ax.set_title("全天电量平衡", fontsize=12)
    ax.margins(x=0.35)

    savefig("p1_fig4_balance.png")


def main() -> None:
    df = M.load_attach1()
    sol = M.solve(df, M.Variant(name="main"))
    print("图形所用主模型目标值：", round(sol.obj, 4), "元")

    fig1_profiles(df)
    fig2_purchase(sol, df)
    fig3_storage(sol)
    fig4_balance(sol, df)
    print("已输出到 04_图/：p1_fig1_profiles.png, p1_fig2_purchase.png, "
          "p1_fig3_storage.png, p1_fig4_balance.png")


if __name__ == "__main__":
    main()
