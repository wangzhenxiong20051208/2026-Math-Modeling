# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题二 —— 论文插图生成
输出到 04_图/，300 dpi，供 LaTeX 直接 \includegraphics 引用。

数据来源（先运行 03_代码/p2_microgrid.py 生成）：
  06_支撑材料/p2_detail.csv       逐时段预测/计划/实际明细
  06_支撑材料/p2_daily.csv        逐日汇总
  06_支撑材料/p2_results.json     总量、指定日期表、对照策略
运行：python3 03_代码/p2_figures.py
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
from p1_microgrid import N, E_MIN, E_MAX, E_INIT, TAU  # noqa: E402

setup_plot()

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "08_算法修正" / "输出"
OUT = ROOT / "08_算法修正" / "输出" / "图"

# 统一配色
C_PRICE = "#c0392b"   # 电价 红
C_LOAD = "#2c3e50"    # 实际净负荷 深蓝
C_PRED = "#2980b9"    # 预测 蓝
C_RISK = "#e67e22"    # 风险余量/风险净负荷 橙
C_EMG = "#c0392b"     # 紧急购电 红
C_PLAN = "#2980b9"    # 计划购电 蓝
C_SOC = "#16a085"     # 实际储电量 青
C_REF = "#8e44ad"     # 参考储电量 紫

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
SPECIAL_TITLE = {"2025-03-20": "2025-03-20（春分）",
                 "2025-06-21": "2025-06-21（夏至）",
                 "2025-09-23": "2025-09-23（秋分）",
                 "2025-12-21": "2025-12-21（冬至）"}


def hours(n: int = N) -> np.ndarray:
    """区间起始时刻（小时）。"""
    return np.arange(n) * 10 / 60


def load_inputs():
    with open(SUP / "p2_results.json", encoding="utf-8") as f:
        res = json.load(f)
    det = pd.read_csv(SUP / "p2_detail.csv", encoding="utf-8-sig")
    daily = pd.read_csv(SUP / "p2_daily.csv", encoding="utf-8-sig")
    return res, det, daily


def panels():
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 4.8))
    return fig, axes.ravel()


# ---------------------------------------------------------------- 图 1
def fig1_forecast(det: pd.DataFrame) -> None:
    """图 1：指定日期的净负荷预测、风险余量与实际净负荷。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        g = det[det["日期"] == d]
        x = t[:len(g)]
        pred = g["净负荷预测_kWh"].to_numpy()
        risk = g["风险净负荷_kWh"].to_numpy()
        act = (g["实际负载_kWh"] - g["实际光伏_kWh"]).to_numpy()

        ax.fill_between(x, pred, risk, color=C_RISK, alpha=0.30,
                        label="风险余量 $Q_{\\alpha}$")
        ax.axhline(0, color="k", lw=0.7, alpha=0.5)
        ax.plot(x, pred, color=C_PRED, lw=1.2, ls="--", label="净负荷预测 $\\hat N$")
        ax.plot(x, risk, color=C_RISK, lw=1.3, label="风险净负荷 $\\tilde N$")
        ax.plot(x, act, color=C_LOAD, lw=1.5, label="实际净负荷 $N$")

        emg = g["紧急购电_kWh"].to_numpy() > 1e-6
        if emg.any():
            ax.plot(x[emg], act[emg], ls="none", marker="v", ms=4.0,
                    color=C_EMG, zorder=5, label="发生紧急购电")

        ax.set_title(SPECIAL_TITLE[d], fontsize=10.5)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_ylabel("电量 / 10min (kWh)")
    for ax in axes[2:]:
        ax.set_xlabel("时刻 (h)")
    axes[0].legend(loc="upper left", fontsize=7.6, framealpha=0.92, ncol=2)
    fig.suptitle("图 1  指定日期的净负荷预测、风险余量与实际净负荷", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    savefig("p2_fig1_forecast.png")


# ---------------------------------------------------------------- 图 2
def fig2_purchase(det: pd.DataFrame) -> None:
    """图 2：指定日期的计划购电、紧急购电与电价。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        g = det[det["日期"] == d]
        x = t[:len(g)]
        plan = g["计划购电_kWh"].to_numpy()
        emg = g["紧急购电_kWh"].to_numpy()
        price = g["电价_元每kWh"].to_numpy()

        ax.bar(x, plan, width=10 / 60 * 0.92, color=C_PLAN, alpha=0.88,
               label="计划购电量")
        ax.bar(x, emg, width=10 / 60 * 0.92, bottom=plan, color=C_EMG,
               alpha=0.95, hatch="///", edgecolor="white", lw=0.3,
               label="紧急购电量")
        ax.set_title(SPECIAL_TITLE[d], fontsize=10.5)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_ylabel("电量 / 10min (kWh)")
        ax.set_ylim(0, max((plan + emg).max() * 1.30, 1.0))

        ax2 = ax.twinx()
        ax2.step(x, price, where="post", color=C_PRICE, lw=1.1)
        ax2.set_ylabel("电价 (元/kWh)", color=C_PRICE, fontsize=9)
        ax2.tick_params(axis="y", labelcolor=C_PRICE, labelsize=8)
        ax2.grid(False)
        ax2.set_ylim(price.min() * 0.75, price.max() * 1.45)

    for ax in axes[2:]:
        ax.set_xlabel("时刻 (h)")
    h1, l1 = axes[0].get_legend_handles_labels()
    axes[0].legend(h1, l1, loc="upper left", fontsize=7.8, framealpha=0.92)
    axes[0].text(0.985, 0.94, "", transform=axes[0].transAxes)
    fig.suptitle("图 2  指定日期的计划购电量、紧急购电量与电价", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    savefig("p2_fig2_purchase.png")


# ---------------------------------------------------------------- 图 3
def fig3_storage(det: pd.DataFrame) -> None:
    """图 3：指定日期的参考储电量与实际储电量轨迹。"""
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        g = det[det["日期"] == d]
        x = hours(len(g))
        Eref = np.concatenate([[g["期初储电量_kWh"].iloc[0]],
                               g["参考储电量_kWh"].to_numpy()])
        Eact = np.concatenate([[g["期初储电量_kWh"].iloc[0]],
                               g["期末储电量_kWh"].to_numpy()])
        tE = np.concatenate([[0.0], x + 10 / 60])

        ax.axhspan(E_MIN, E_MAX, color="#95a5a6", alpha=0.07)
        ax.plot(tE, Eref, color=C_REF, lw=1.4, ls="--", label="日前参考储电量 $\\bar E$")
        ax.plot(tE, Eact, color=C_SOC, lw=1.9, label="实际储电量 $E$")
        ax.fill_between(tE, E_MIN, Eact, color=C_SOC, alpha=0.13)
        ax.axhline(E_MAX, color="#7f8c8d", ls=":", lw=1.0)
        ax.axhline(E_MIN, color="#7f8c8d", ls=":", lw=1.0)
        ax.axhline(E_INIT, color="gray", ls="-.", lw=0.9)

        ax.set_title(SPECIAL_TITLE[d], fontsize=10.5)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_ylabel("储电量 (kWh)")
        ax.set_ylim(0, E_MAX * 1.16)
        ax.text(0.2, E_MAX * 1.06, "上限 10800", color="#7f8c8d", fontsize=8)
        ax.text(0.2, E_MIN + 260, "下限 1200", color="#7f8c8d", fontsize=8)
        ax.text(12.4, E_INIT + 240, "$E^{\\mathrm{tar}}$ = 6000", color="gray",
                fontsize=8)
    for ax in axes[2:]:
        ax.set_xlabel("时刻 (h)")
    axes[0].legend(loc="upper left", fontsize=7.8, framealpha=0.92, ncol=2)
    fig.suptitle("图 3  指定日期的日前参考储电量与实际储电量", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    savefig("p2_fig3_storage.png")


# ---------------------------------------------------------------- 图 4
def _monthly(series: dict) -> tuple[list[str], np.ndarray, np.ndarray]:
    """把逐日序列按月份汇总（计划费、紧急费）。"""
    dt = pd.to_datetime(pd.Series(series["dates"]))
    df = pd.DataFrame({
        "ym": dt.dt.strftime("%Y-%m"),
        "plan": np.asarray(series["cost_plan"], float),
        "emg": np.asarray(series["cost_emg"], float),
    })
    g = df.groupby("ym", as_index=False)[["plan", "emg"]].sum()
    return g["ym"].tolist(), g["plan"].to_numpy(), g["emg"].to_numpy()


def fig4_monthly(res: dict) -> None:
    """图 4：逐月费用分解与各策略全年费用对比。"""
    ss = res["对照策略逐日"]
    k_main = "本文风险修正策略（主模型）"
    mos, plan, emg = _monthly(ss[k_main])

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.6, 3.38), gridspec_kw={"width_ratios": [1.55, 1]})

    x = np.arange(len(mos))
    ax1.bar(x, plan, width=0.66, color=C_PLAN, alpha=0.9, label="计划购电费")
    ax1.bar(x, emg, width=0.66, bottom=plan, color=C_EMG, alpha=0.95,
            hatch="///", edgecolor="white", lw=0.3, label="紧急购电费")
    for xi, (p, e) in enumerate(zip(plan, emg)):
        ax1.text(xi, p + e, f"{(p + e) / 1e4:.1f}", ha="center", va="bottom",
                 fontsize=7.4)
    ax1.set_xticks(x)
    ax1.set_xticklabels([m[-2:] + "月" for m in mos], fontsize=8.5)
    ax1.set_xlabel("月份（2025 年）")
    ax1.set_ylabel("购电费 (元)")
    ax1.set_ylim(0, (plan + emg).max() * 1.20)
    ax1.legend(loc="upper left", fontsize=8.6, framealpha=0.92)
    ax1.set_title("(a) 本文策略逐月费用分解（柱顶数字为万元）", fontsize=10.5)

    # (b) 各策略全区间费用对比
    names, tp, te = [], [], []
    for k, v in res["对照策略"].items():
        names.append(k)
        tp.append(v["计划购电费_元"])
        te.append(v["紧急购电费_元"])
    tp, te = np.array(tp), np.array(te)
    y = np.arange(len(names))[::-1]
    ax2.barh(y, tp, height=0.6, color=C_PLAN, alpha=0.9, label="计划购电费")
    ax2.barh(y, te, height=0.6, left=tp, color=C_EMG, alpha=0.95,
             hatch="///", edgecolor="white", lw=0.3, label="紧急购电费")
    for yi, (p, e) in zip(y, zip(tp, te)):
        ax2.text(p + e, yi, f"  {(p + e) / 1e4:.1f} 万", va="center",
                 fontsize=8.2)
    short = ["本文风险修正", "预测均值", "无储能", "事后理想"]
    ax2.set_yticks(y)
    ax2.set_yticklabels(short[:len(names)], fontsize=9)
    ax2.set_xlabel("购电费 (元)")
    ax2.set_xlim(0, (tp + te).max() * 1.30)
    ax2.legend(loc="lower right", fontsize=8.4, framealpha=0.92)
    ax2.set_title("(b) 各策略 2—12 月总费用对比", fontsize=10.5)

    fig.suptitle("图 4  逐月费用分解与策略费用对比", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    savefig("p2_fig4_monthly.png")


# ---------------------------------------------------------------- 图 5
def fig5_cumulative(res: dict) -> None:
    """图 5：各策略累计费用曲线与全年储电量轨迹。"""
    ss = res["对照策略逐日"]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.4, 3.15), gridspec_kw={"width_ratios": [1.35, 1]})

    styles = {
        "本文风险修正策略（主模型）": (C_SOC, "-", 1.9),
        "预测均值策略（不加分位风险余量）": (C_PRED, "--", 1.4),
        "无储能（同样提前计划并五倍补缺）": (C_EMG, "-.", 1.4),
        "事后理想（完全预知当天净负荷）": ("#7f8c8d", ":", 1.5),
    }
    labels = {"本文风险修正策略（主模型）": "本文风险修正策略",
              "预测均值策略（不加分位风险余量）": "预测均值策略",
              "无储能（同样提前计划并五倍补缺）": "无储能",
              "事后理想（完全预知当天净负荷）": "事后理想（下界参考）"}
    k_main = "本文风险修正策略（主模型）"
    dates = ss[k_main]["dates"]
    xt = np.arange(len(dates))
    ticks = [i for i, d in enumerate(dates) if d[8:] == "01"]
    ticklab = [dates[i][:7] for i in ticks]

    for k, (col, ls, lw) in styles.items():
        if k not in ss:
            continue
        v = np.asarray(ss[k]["cost_total"], float)
        if np.all(np.isnan(v)):
            continue
        ax1.plot(xt, np.cumsum(v) / 1e4, color=col, ls=ls, lw=lw, label=labels[k])
    ax1.set_xticks(ticks)
    ax1.set_xticklabels(ticklab, fontsize=8.5, rotation=45, ha="right")
    ax1.set_xlim(0, len(dates) - 1)
    ax1.set_xlabel("日期（2025 年）")
    ax1.set_ylabel("累计购电费 (万元)")
    ax1.legend(loc="upper left", fontsize=8.6, framealpha=0.92)
    ax1.set_title("(a) 累计购电费曲线", fontsize=10.5)

    E = np.asarray(ss[k_main]["E_end"], float)
    ax2.axhspan(E_MIN, E_MAX, color="#95a5a6", alpha=0.07)
    ax2.plot(xt, E, color=C_SOC, lw=1.5)
    ax2.fill_between(xt, E_MIN, E, color=C_SOC, alpha=0.14)
    ax2.axhline(E_MAX, color="#7f8c8d", ls=":", lw=1.0)
    ax2.axhline(E_MIN, color="#7f8c8d", ls=":", lw=1.0)
    ax2.axhline(E_INIT, color="gray", ls="-.", lw=0.9)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(ticklab, fontsize=8.5, rotation=45, ha="right")
    ax2.set_xlim(0, len(dates) - 1)
    ax2.set_ylim(0, E_MAX * 1.14)
    ax2.set_xlabel("日期（2025 年）")
    ax2.set_ylabel("日末实际储电量 (kWh)")
    ax2.text(2, E_MAX * 1.03, "上限 10800", color="#7f8c8d", fontsize=8)
    ax2.text(2, E_MIN + 250, "下限 1200", color="#7f8c8d", fontsize=8)
    ax2.set_title("(b) 本文策略的跨日储电量轨迹", fontsize=10.5)

    fig.suptitle("图 5  各策略累计费用与跨日储电量", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    savefig("p2_fig5_cumulative.png")


# ---------------------------------------------------------------- 图 6
def fig6_calibration(daily: pd.DataFrame) -> None:
    """图 6：紧急购电的季节分布与逐日费用构成。"""
    dt = pd.to_datetime(daily["date"])
    doy = dt.dt.dayofyear.to_numpy()
    emg = daily["emg_kwh"].to_numpy(float)
    cm = daily["cost_total"].to_numpy(float)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11.0, 4.05), sharex=True,
        gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.14})

    ax1.bar(doy, emg, width=1.0, color=C_EMG, alpha=0.85)
    ax1.set_ylabel("紧急购电量 (kWh/日)")
    ax1.set_title("图 6  紧急购电量的季节分布与逐日费用构成", fontsize=12)
    ax1.set_xlim(doy.min() - 1, doy.max() + 1)

    ax2.bar(doy, daily["cost_plan"].to_numpy(float), width=1.0,
            color=C_PLAN, alpha=0.85, label="计划购电费")
    ax2.bar(doy, daily["cost_emg"].to_numpy(float), width=1.0,
            bottom=daily["cost_plan"].to_numpy(float), color=C_EMG, alpha=0.9,
            label="紧急购电费")
    ax2.set_ylabel("购电费 (元/日)")
    ax2.set_xlabel("日期（2025 年，序日）")
    ax2.legend(loc="upper left", fontsize=8.6, framealpha=0.92)
    ticks = []
    labels = []
    for m in range(2, 13):
        d0 = pd.Timestamp(2025, m, 1).dayofyear
        ticks.append(d0)
        labels.append(f"{m}月")
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(labels, fontsize=8.5)

    n_emg = int((emg > 1e-6).sum())
    ax1.text(0.995, 0.93, f"发生紧急购电 {n_emg}/{len(daily)} 天",
             transform=ax1.transAxes, ha="right", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    savefig("p2_fig6_daily.png")


def main() -> None:
    res, det, daily = load_inputs()
    print("主策略合计购电费：",
          f"{res['totals']['合计购电费_元']:,.2f} 元")
    fig1_forecast(det)
    fig2_purchase(det)
    fig3_storage(det)
    fig4_monthly(res)
    fig5_cumulative(res)
    fig6_calibration(daily)
    print("已输出到 04_图/：p2_fig1_forecast.png, p2_fig2_purchase.png, "
          "p2_fig3_storage.png, p2_fig4_monthly.png, p2_fig5_cumulative.png, "
          "p2_fig6_daily.png")


if __name__ == "__main__":
    main()
