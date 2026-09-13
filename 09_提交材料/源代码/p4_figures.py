# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题四 —— 论文插图生成
输出到 04_图/，300 dpi，供 LaTeX 直接 \includegraphics 引用。

六张图对应框架第八·九节：
  图 1  附件 4 电价的结构分解 P = 附件 1 曲线 + 星期偏移
  图 2  价格预测：0:00 与 6:00 两个版本对同一天的实际电价
  图 3  三种价格信息条件下的策略费用分解与 ΔJ
  图 4  4-2 的冻结计划与 4-3 的初始/最终购电曲线
  图 5  两个分支的实际储电量与参考轨迹
  图 6  八种预报组合的费用分解
  图 7  逐日费用与累计差额

数据来源（先运行 03_代码/p4_microgrid.py 生成）：
  06_支撑材料/p4_results.json
  06_支撑材料/p4_detail_42.csv
  06_支撑材料/p4_detail_43.csv
运行：python3 03_代码/p4_figures.py
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cumcm_plot import savefig, setup_plot  # noqa: E402
from p1_microgrid import N, E_MIN, E_MAX, TAU  # noqa: E402
from p4_microgrid import (  # noqa: E402
    PriceForecaster, load_attach4, load_attach1,
    select_forecast_params, REPORT_START,
)

setup_plot()

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "06_支撑材料"
OUT = ROOT / "04_图"

C_FIXED = "#7f8c8d"
C_PRICE = "#c0392b"
C_FCOST = "#2980b9"
C_FCST6 = "#16a085"
C_ACT = "#c0392b"
C_G0 = "#2980b9"
C_X = "#c0392b"
C_EMG = "#e67e22"
C_SOC42 = "#8e44ad"
C_SOC43 = "#16a085"
C_REF = "#7f8c8d"
C_PLANFEE = "#34495e"
C_ADJFEE = "#e67e22"
C_EMGFEE = "#c0392b"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
SPECIAL_TITLE = {"2025-03-20": "2025-03-20（春分）",
                 "2025-06-21": "2025-06-21（夏至）",
                 "2025-09-23": "2025-09-23（秋分）",
                 "2025-12-21": "2025-12-21（冬至）"}
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def hours() -> np.ndarray:
    return np.arange(N) * 10 / 60


def load_inputs():
    res = json.loads((SUP / "p4_results.json").read_text(encoding="utf-8"))
    det42 = pd.read_csv(SUP / "p4_detail_42.csv", encoding="utf-8-sig")
    det43 = pd.read_csv(SUP / "p4_detail_43.csv", encoding="utf-8-sig")
    return res, det42, det43


def panels(ncol: int = 2):
    fig, axes = plt.subplots(2, ncol, figsize=(11.2, 4.8))
    return fig, np.asarray(axes).ravel()


def _day(det: pd.DataFrame, d: str) -> pd.DataFrame:
    return det[det["日期"] == d]


# ---------------------------------------------------------------- 图 1
def fig1_structure() -> None:
    """图 1：左——一周的实际电价与附件 1 曲线；右——残差的星期均值。"""
    PRICE = load_attach4()
    FIXED = load_attach1()["电价"].to_numpy(float)
    R = PRICE - FIXED
    d0 = datetime.date(2025, 1, 1)              # 0=周一 … 6=周日
    wd = np.array([(d0 + datetime.timedelta(days=n)).weekday()
                   for n in range(PRICE.shape[0])])

    t = hours()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 3.3),
                                   gridspec_kw={"width_ratios": [2.0, 1.0]})

    n0 = 60                                     # 2025-03-02 起一周
    for k in range(7):
        n = n0 + k
        lo = wd[n] in (4, 5)
        ax1.plot(t + 24 * k, PRICE[n], color=C_PRICE if lo else C_FCOST,
                 lw=1.1, alpha=0.9 if lo else 0.55, zorder=4 if lo else 3)
    for k in range(7):
        ax1.plot(t + 24 * k, FIXED, color="k", lw=1.0, ls="--", alpha=0.75,
                 zorder=5)
    ax1.plot([], [], color=C_PRICE, lw=1.4, label="附件 4 实际电价（周五/周六）")
    ax1.plot([], [], color=C_FCOST, lw=1.4, label="附件 4 实际电价（其余曜日）")
    ax1.plot([], [], color="k", lw=1.0, ls="--", label="附件 1 固定电价曲线 $F$")
    ax1.set_xlim(0, 24 * 7)
    ax1.set_xticks(np.arange(0, 24 * 7 + 1, 24))
    ax1.set_xticklabels(["周一", "周二", "周三", "周四", "周五", "周六",
                         "周日", "次周一"], fontsize=8)
    ax1.set_xlabel("日期（2025-03-03 起一周）")
    ax1.set_ylabel("电价 / (元/kWh)")
    ax1.set_title("实际电价 = 固定曲线 + 星期偏移", fontsize=11)
    ax1.legend(fontsize=8, loc="upper left")

    means = [float(R[wd == w].mean()) for w in range(7)]
    cols = [C_PRICE if w in (4, 5) else C_FCOST for w in range(7)]
    ax2.bar(np.arange(7), means, 0.62, color=cols)
    for i, v in enumerate(means):
        ax2.annotate(f"{v:+.3f}", (i, v), ha="center",
                     va="bottom" if v > 0 else "top", fontsize=8,
                     xytext=(0, 3 if v > 0 else -3),
                     textcoords="offset points")
    ax2.axhline(0, color="k", lw=0.8)
    hi = np.mean([means[k] for k in (0, 1, 2, 3, 6)])
    lo_ = (means[4] + means[5]) / 2
    ax2.axhline(hi, color=C_FCOST, lw=1.0, ls=":")
    ax2.axhline(lo_, color=C_PRICE, lw=1.0, ls=":")
    ax2.annotate(f"差 {hi - lo_:.3f} 元/kWh", (5.5, (hi + lo_) / 2),
                 fontsize=8, ha="right", color="k",
                 bbox=dict(fc="white", ec="gray", lw=0.5, alpha=0.85))
    ax2.set_xticks(np.arange(7))
    ax2.set_xticklabels(WD, fontsize=8)
    ax2.set_ylabel("残差 $R$ 的星期均值 / (元/kWh)")
    ax2.set_title("残差的星期结构", fontsize=11)
    fig.suptitle("附件 4 实时电价并非另一条曲线，而是附件 1 曲线叠加星期偏移",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    savefig("p4_fig1_price_structure.png")


# ---------------------------------------------------------------- 图 2
def fig2_forecast() -> None:
    """图 2：两个发布版本的价格预测与当天实际电价（选四个特征日）。

    预测器参数与正式计算完全一致：只在 1 月预热期（评价区间之外）选一次、
    冻结后全程复用，见 p4_microgrid.select_forecast_params。
    """
    PRICE = load_attach4()
    pp, _ = select_forecast_params(PRICE, 1, REPORT_START)
    pf = PriceForecaster(PRICE, pp)
    idx = {str(np.datetime64("2025-01-01") + np.timedelta64(n, "D")): n
           for n in range(PRICE.shape[0])}
    t = hours()

    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        n = idx[d]
        act = PRICE[n]
        q0 = pf.forecast0(n)
        # hi 是发布序号（0/1/2/3 ↔ 0:00/6:00/12:00/18:00），不是小时数：
        # 传 6 会让 t0 = 36*6 = 216（即 15:00），由图从第 36 时段画起就自相矛盾。
        q6 = pf.forecast_at(n, 1)
        ax.plot(t, act, color=C_ACT, lw=2.0, label="实际电价", zorder=6)
        ax.plot(t, q0, color=C_FCOST, lw=1.2, ls="--", label="0:00 预测")
        ax.plot(t[36:], q6[36:], color=C_FCST6, lw=1.4, ls="-.",
                label="6:00 修正后预测")
        ax.fill_between(t[36:], q0[36:], q6[36:], where=q0[36:] > q6[36:],
                        color=C_FCST6, alpha=0.18, step="mid")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("电价 / (元/kWh)")
        ax.set_title(SPECIAL_TITLE[d], fontsize=11)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, fontsize=9, ncol=3, loc="lower center",
               bbox_to_anchor=(0.5, -0.035), frameon=False)
    fig.suptitle("价格预测与实际电价（6:00 起用当日已实现价格修正剩余时段）",
                 fontsize=12, y=1.0)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    savefig("p4_fig2_forecast.png")


# ---------------------------------------------------------------- 图 3
def fig3_strategy(res: dict) -> None:
    """图 3：三种价格信息条件下的策略费用分解（两分支并列）与 ΔJ。"""
    # 用 .get：只跑了 --report-only 或没跑 --strategies 时这个键不存在，
    # 此时应当安静跳过，而不是让整张图的生成中断
    rows = [r for r in res.get("策略对照", []) if r.get("模式")]
    if not rows:
        print("  跳过图 3：策略对照尚未计算")
        return
    order = ["forecast", "fixed", "oracle"]
    label = {r["模式"]: r["策略"] for r in rows}

    fig, ax = plt.subplots(figsize=(9.6, 3.35))
    xs, plan, adj, emg, names = [], [], [], [], []
    pos = 0.0
    for br in ("4-2", "4-3"):
        for m in order:
            r = next((q for q in rows if q["分支"] == br and q["模式"] == m), None)
            if r is None:
                continue
            xs.append(pos)
            plan.append(r["计划费_元"] / 1e4)
            adj.append(r["调整费_元"] / 1e4)
            emg.append(r["紧急费_元"] / 1e4)
            names.append(f"{br}\n{label[m]}")
            pos += 1
        pos += 0.6
    plan, adj, emg = np.array(plan), np.array(adj), np.array(emg)
    tot = plan + adj + emg
    ax.bar(xs, plan, 0.6, color=C_PLANFEE, label="计划购电费")
    ax.bar(xs, adj, 0.6, bottom=plan, color=C_ADJFEE, label="调整费")
    ax.bar(xs, emg, 0.6, bottom=plan + adj, color=C_EMGFEE, label="紧急购电费")
    for x, v in zip(xs, tot):
        ax.annotate(f"{v:,.1f}", (x, v), ha="center", va="bottom", fontsize=8,
                    xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(xs)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("费用 / 万元")
    ax.axvline(2.8, color="gray", lw=0.8, ls="--")
    ax.set_title("三种价格信息条件下的策略：同一实际价格路径，各自独立回放",
                 fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    savefig("p4_fig3_strategy.png")

    out = pd.DataFrame({
        "分支": [b for b in ("4-2", "4-3") for _ in order],
        "策略": [label[m] for _ in ("4-2", "4-3") for m in order],
        "计划费_万元": plan, "调整费_万元": adj, "紧急费_万元": emg,
        "合计_万元": tot,
    })
    out.to_csv(SUP / "p4_strategy_fees.csv", index=False, encoding="utf-8-sig")
    print(f"  另存 {SUP / 'p4_strategy_fees.csv'}")


# ---------------------------------------------------------------- 图 4
def fig4_purchase(det42: pd.DataFrame, det43: pd.DataFrame) -> None:
    """图 4：4-2 的冻结计划与 4-3 的初始/最终购电，叠加紧急补购。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        a = _day(det42, d)
        b = _day(det43, d)
        g42 = a["计划购电_kWh"].to_numpy()
        e42 = a["紧急购电_kWh"].to_numpy()
        g0 = b["初始计划购电_kWh"].to_numpy()
        x = b["最终购电_kWh"].to_numpy()
        e43 = b["紧急购电_kWh"].to_numpy()
        ax.plot(t, g42, color=C_FIXED, lw=1.5, ls=":", label="4-2 计划 $g_t$")
        ax.plot(t, g0, color=C_G0, lw=1.3, ls="--", label="4-3 初始 $g^0_t$")
        ax.plot(t, x, color=C_X, lw=1.5, label="4-3 最终 $x_t$")
        up = x > g0 + 1e-9
        if up.any():
            ax.fill_between(t, g0, x, where=up, color=C_X, alpha=0.22,
                            step="mid")
        if (e43 > 1e-6).any():
            ax.fill_between(t, 0, e43, where=e43 > 1e-6, color=C_EMG,
                            alpha=0.5, step="mid", label="4-3 紧急购电 $r_t$")
        if (e42 > 1e-6).any():
            ax.fill_between(t, 0, -e42, where=e42 > 1e-6, color=C_FIXED,
                            alpha=0.5, step="mid", label="4-2 紧急购电 $r_t$")
        ax.axhline(0, color="k", lw=0.7)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("十分钟电量 / kWh")
        ax.set_title(SPECIAL_TITLE[d], fontsize=11)
    axes[0].legend(fontsize=7.5, loc="upper right", ncol=1)
    fig.suptitle("4-2 的冻结计划与 4-3 的初始/最终购电（6/12/18 时允许调整）",
                 fontsize=12, y=1.0)
    fig.tight_layout()
    savefig("p4_fig4_purchase.png")


# ---------------------------------------------------------------- 图 5
def fig5_storage(det42: pd.DataFrame, det43: pd.DataFrame) -> None:
    """图 5：两个分支的实际储电量与各自的参考轨迹。"""
    t = hours()
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        a = _day(det42, d)
        b = _day(det43, d)
        E42 = a["储电量_kWh"].to_numpy()
        E43 = b["储电量_kWh"].to_numpy()
        ref = b["参考储电量_kWh"].to_numpy()
        ax.plot(t, ref, color=C_REF, lw=1.0, ls="--", label="参考轨迹 $\\bar E_t$")
        ax.plot(t, E42, color=C_SOC42, lw=1.5, label="4-2 储电量 $E_t$")
        ax.plot(t, E43, color=C_SOC43, lw=1.5, label="4-3 储电量 $E_t$")
        ax.axhline(E_MIN, color="gray", lw=0.8, ls=":")
        ax.axhline(E_MAX, color="gray", lw=0.8, ls=":")
        for h in (0, 6, 12, 18):
            ax.axvline(h, color="k", lw=0.6, ls=":", alpha=0.45)
        ax.set_xlim(0, 24)
        ax.set_ylim(E_MIN - 250, E_MAX + 250)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("储电量 / kWh")
        ax.set_title(SPECIAL_TITLE[d], fontsize=11)
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("两个分支的实际储电量（竖虚线为 0/6/12/18 时决策点）",
                 fontsize=12, y=1.0)
    fig.tight_layout()
    savefig("p4_fig5_storage.png")


# ---------------------------------------------------------------- 图 6
def fig6_combos(res: dict) -> None:
    """图 6：八种预报组合的费用分解与总额。"""
    rows = res.get("预报组合")
    if not rows:
        print("  跳过图 6：预报组合尚未计算")
        return
    rows = sorted(rows, key=lambda r: r["合计费用_元"])
    labels = ["仅 0:00" if r["使用预报"] == "∅" else r["使用预报"] for r in rows]
    plan = np.array([r["计划费_元"] for r in rows]) / 1e4
    adj = np.array([r["调整费_元"] for r in rows]) / 1e4
    emg = np.array([r["紧急费_元"] for r in rows]) / 1e4
    tot = plan + adj + emg

    fig, ax = plt.subplots(figsize=(10.0, 3.4))
    xp = np.arange(len(labels))
    ax.bar(xp, plan, 0.62, color=C_PLANFEE, label="计划购电费")
    ax.bar(xp, adj, 0.62, bottom=plan, color=C_ADJFEE, label="调整费")
    ax.bar(xp, emg, 0.62, bottom=plan + adj, color=C_EMGFEE, label="紧急购电费")
    for i, v in enumerate(tot):
        ax.annotate(f"{v:,.1f}", (i, v), ha="center", va="bottom", fontsize=8,
                    xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(xp)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("费用 / 万元")
    ax.set_title("波动电价下 4-3 的八种预报组合（各组合单独标定）", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    savefig("p4_fig6_combos.png")


# ---------------------------------------------------------------- 图 7
def fig7_daily(d42: pd.DataFrame, d43: pd.DataFrame) -> None:
    """图 7：逐日费用与累计差额，看收益的月份分布。"""
    x = pd.to_datetime(d42["日期"])
    c42 = d42["合计费用_元"].to_numpy(float)
    c43 = d43["合计费用_元"].to_numpy(float)
    cum = np.cumsum(c42 - c43)

    fig, axes = plt.subplots(3, 1, figsize=(11.0, 5.4), sharex=True)
    axes[0].plot(x, c42 / 1e4, color=C_SOC42, lw=0.9, label="4-2 冻结计划")
    axes[0].plot(x, c43 / 1e4, color=C_SOC43, lw=0.9, label="4-3 可调整")
    axes[0].set_ylabel("日费用 / 万元")
    axes[0].legend(fontsize=8, ncol=2)
    axes[1].bar(x, (c42 - c43) / 1e4, color=C_FCOST, width=1.0)
    axes[1].axhline(0, color="k", lw=0.8)
    axes[1].set_ylabel("日差额 / 万元")
    axes[2].plot(x, cum / 1e4, color=C_PRICE, lw=1.1)
    axes[2].axhline(0, color="k", lw=0.8)
    axes[2].set_ylabel("累计差额 / 万元")
    axes[2].set_xlabel("日期")
    fig.suptitle("4-3 相对 4-2（冻结计划）省下的费用及其累计（正数表示 4-3 更省）",
                 fontsize=12, y=0.995)
    fig.tight_layout()
    savefig("p4_fig7_daily.png")


def main() -> None:
    res, det42, det43 = load_inputs()
    fig1_structure()
    print("  图 1 价格结构分解")
    fig2_forecast()
    print("  图 2 价格预测与实际")
    fig3_strategy(res)
    print("  图 3 三策略费用分解")
    fig4_purchase(det42, det43)
    print("  图 4 冻结计划与初始/最终购电")
    fig5_storage(det42, det43)
    print("  图 5 实际储电量")
    fig6_combos(res)
    print("  图 6 八种预报组合")
    d42 = pd.read_csv(SUP / "p4_daily_42.csv", encoding="utf-8-sig")
    d43 = pd.read_csv(SUP / "p4_daily_43.csv", encoding="utf-8-sig")
    fig7_daily(d42, d43)
    print("  图 7 逐日费用与累计差额")
    print(f"输出目录：{OUT}")


if __name__ == "__main__":
    main()
