# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题三 —— 论文插图生成
输出到 04_图/，300 dpi，供 LaTeX 直接 \includegraphics 引用。

四张图对应框架 8.3 节：
  图 1  同一目标时段的多版本光伏预报（叠加事后实际值）
  图 2  初始计划与最终购电曲线（标出正式调整与紧急补购）
  图 3  参考与实际储电量曲线（标出 0:00/6:00/12:00/18:00 更新点）
  图 4  八种预报组合的费用分解

数据来源（先运行 03_代码/p3_microgrid.py 生成）：
  06_支撑材料/p3_detail.csv
  06_支撑材料/p3_daily.csv
  06_支撑材料/p3_results.json
运行：python3 03_代码/p3_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cumcm_plot import savefig, setup_plot  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_microgrid import N, E_MIN, E_MAX, TAU, fmt_time  # noqa: E402
from p2_microgrid import load_attach2, Forecaster  # noqa: E402

setup_plot()

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "08_算法修正" / "输出"
OUT = ROOT / "08_算法修正" / "输出" / "图"

C_VER = {0: "#7f8c8d", 6: "#2980b9", 12: "#e67e22", 18: "#16a085"}
C_ACT = "#c0392b"
C_G0 = "#2980b9"
C_X = "#c0392b"
C_EMG = "#e67e22"
C_SOC = "#16a085"
C_REF = "#8e44ad"
C_PLANFEE = "#34495e"
C_ADJFEE = "#e67e22"
C_EMGFEE = "#c0392b"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
SPECIAL_TITLE = {"2025-03-20": "2025-03-20（春分）",
                 "2025-06-21": "2025-06-21（夏至）",
                 "2025-09-23": "2025-09-23（秋分）",
                 "2025-12-21": "2025-12-21（冬至）"}


def hours() -> np.ndarray:
    return np.arange(N) * 10 / 60


def load_inputs():
    with open(SUP / "p3_results.json", encoding="utf-8") as f:
        res = json.load(f)
    det = pd.read_csv(SUP / "p3_detail.csv", encoding="utf-8-sig")
    daily = pd.read_csv(SUP / "p3_daily.csv", encoding="utf-8-sig")
    return res, det, daily


def panels():
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 4.8))
    return fig, axes.ravel()


# ---------------------------------------------------------------- 图 1
def fig1_versions() -> None:
    """图 1：四个发布版本对同一天的光伏预报，叠加该日实际光伏。"""
    from p3_microgrid import load_attach3, forecast_energy_slots
    from p2_microgrid import load_attach2 as _l2

    fp = load_attach3()
    LOAD, PV, dates = _l2()
    idx = {d: i for i, d in enumerate(dates)}
    t = hours()

    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        n = idx[d]
        act = PV[n] * TAU * 6.0            # 10 分钟电量 -> 等效平均功率 kW
        ax.plot(t, act, color=C_ACT, lw=2.0, label="实际光伏", zorder=5)
        for hi, hr in enumerate((0, 6, 12, 18)):
            v = forecast_energy_slots(fp, hi, n) * 6.0
            m = ~np.isnan(v)
            ax.plot(t[m], v[m], color=C_VER[hr], lw=1.3, ls="--",
                    label=f"{hr}:00 预报")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("光伏功率 / kW")
        ax.set_title(SPECIAL_TITLE[d], fontsize=11)
    axes[0].legend(fontsize=8, ncol=2, loc="upper left")
    fig.suptitle("四个发布版本对同一日的光伏预报与实际值", fontsize=12, y=1.0)
    savefig("p3_fig1_versions.png")


# ---------------------------------------------------------------- 图 2
def fig2_purchase(det: pd.DataFrame) -> None:
    """图 2：初始计划 g⁰ 与最终生效 x，标出正式调整区间和紧急补购。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        g = det[det["日期"] == d]
        g0 = g["初始计划购电_kWh"].to_numpy()
        x = g["最终购电_kWh"].to_numpy()
        emg = g["紧急购电_kWh"].to_numpy()
        ax.plot(t, g0, color=C_G0, lw=1.4, ls="--", label="初始计划 $g^0_t$")
        ax.plot(t, x, color=C_X, lw=1.5, label="最终生效 $x_t$")
        up = x > g0 + 1e-9
        if up.any():
            ax.fill_between(t, g0, x, where=up, color=C_X, alpha=0.28,
                            step="mid", label="正式调整（上调）")
            for h in (6, 12, 18):
                if up[h * 6: h * 6 + 36].any():
                    ax.axvline(h, color=C_X, lw=0.7, ls=":", alpha=0.6)
        if (emg > 1e-6).any():
            ax.fill_between(t, 0, emg, where=emg > 1e-6, color=C_EMG,
                            alpha=0.85, step="mid", label="紧急购电 $r_t$")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("十分钟电量 / kWh")
        ax.set_title(SPECIAL_TITLE[d], fontsize=11)
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("初始计划购电与最终生效购电（虚线为各发布时刻）", fontsize=12,
                 y=1.0)
    savefig("p3_fig2_purchase.png")


# ---------------------------------------------------------------- 图 3
def fig3_storage(det: pd.DataFrame) -> None:
    """图 3：实际储电量与最新参考轨迹，标出四次更新时刻。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        g = det[det["日期"] == d]
        E0 = float(g["期初储电量_kWh"].iloc[0])
        E = g["期末储电量_kWh"].to_numpy()
        ref = g["参考储电量_kWh"].to_numpy()
        ax.plot(t, ref, color=C_REF, lw=1.2, ls="--", label="参考轨迹 $\\bar E_t$")
        ax.plot(t, E, color=C_SOC, lw=1.6, label="实际储电量 $E_t$")
        ax.axhline(E_MIN, color="gray", lw=0.8, ls=":")
        ax.axhline(E_MAX, color="gray", lw=0.8, ls=":")
        for h in (0, 6, 12, 18):
            ax.axvline(h, color="k", lw=0.7, ls=":", alpha=0.5)
        ax.set_xlim(0, 24)
        ax.set_ylim(E_MIN - 250, E_MAX + 250)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("储电量 / kWh")
        ax.set_title(f"{SPECIAL_TITLE[d]}（0:00 储电 {E0:,.0f} kWh）", fontsize=10)
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("实际储电量与滚动参考轨迹（竖虚线为 0/6/12/18 时更新点）",
                 fontsize=12, y=1.0)
    savefig("p3_fig3_storage.png")


# ---------------------------------------------------------------- 图 4
def fig4_combos(res: dict) -> None:
    """图 4：八种预报组合的费用分解与总额。"""
    rows = res["八种组合"]
    ctrl = res["对照_沿用0点预报版本"]
    labels = [r["组合"] for r in rows] + ["对照"]
    plan = np.array([r["计划费_元"] for r in rows] + [ctrl["计划费_元"]]) / 1e4
    adj = np.array([r["调整费_元"] for r in rows] + [ctrl["调整费_元"]]) / 1e4
    emg = np.array([r["紧急费_元"] for r in rows] + [ctrl["紧急费_元"]]) / 1e4
    tot = plan + adj + emg

    fig, ax = plt.subplots(figsize=(10.4, 3.45))
    xp = np.arange(len(labels))
    ax.bar(xp, plan, 0.62, color=C_PLANFEE, label="计划购电费（含调整）")
    ax.bar(xp, adj, 0.62, bottom=plan, color=C_ADJFEE, label="调整（违约/追加）费")
    ax.bar(xp, emg, 0.62, bottom=plan + adj, color=C_EMGFEE, label="紧急购电费")
    for i, v in enumerate(tot):
        ax.annotate(f"{v:,.1f}", (i, v), ha="center", va="bottom", fontsize=8,
                    xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(xp)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("费用 / 万元")
    ax.set_title("八种预报组合的实际总费用分解（对照＝重新优化但仍用 0:00 预报版本）",
                 fontsize=11)
    ax.legend(fontsize=9)
    ax.axvline(7.5, color="gray", lw=0.8, ls="--")
    savefig("p3_fig4_combos.png")

    # 省下的费用不靠图读，同时落一份数值表供正文引用
    out = pd.DataFrame({
        "组合": labels, "计划费_万元": plan, "调整费_万元": adj,
        "紧急费_万元": emg, "合计_万元": tot,
    })
    out.to_csv(SUP / "p3_combo_fees.csv", index=False, encoding="utf-8-sig")
    print(f"  另存 {SUP / 'p3_combo_fees.csv'}")


# ---------------------------------------------------------------- 附加图
def fig5_daily(daily: pd.DataFrame) -> None:
    """图 5：逐日的调整费、紧急费与储电量，刻画收益的月份分布。"""
    d = pd.to_datetime(daily["date"])
    fig, axes = plt.subplots(3, 1, figsize=(11.0, 5.4), sharex=True)
    axes[0].plot(d, daily["cost_adj"], color=C_ADJFEE, lw=0.9)
    axes[0].set_ylabel("调整费 / 元")
    axes[1].plot(d, daily["cost_emg"], color=C_EMGFEE, lw=0.9)
    axes[1].set_ylabel("紧急费 / 元")
    axes[2].plot(d, daily["E144"], color=C_SOC, lw=1.0)
    axes[2].axhline(E_MIN, color="gray", lw=0.8, ls=":")
    axes[2].axhline(E_MAX, color="gray", lw=0.8, ls=":")
    axes[2].set_ylabel("24:00 储电量 / kWh")
    axes[2].set_xlabel("日期")
    fig.suptitle("主策略逐日的调整费、紧急费与日末储电量", fontsize=12, y=0.995)
    fig.tight_layout()
    savefig("p3_fig5_daily.png")


def main() -> None:
    res, det, daily = load_inputs()
    fig1_versions()
    print("  图 1 多版本光伏预报")
    fig2_purchase(det)
    print("  图 2 初始/最终购电曲线")
    fig3_storage(det)
    print("  图 3 参考/实际储电量")
    fig4_combos(res)
    print("  图 4 八种组合费用分解")
    fig5_daily(daily)
    print("  图 5 逐日费用与储电量")
    print(f"输出目录：{OUT}")


if __name__ == "__main__":
    main()
