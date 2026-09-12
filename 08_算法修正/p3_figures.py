# -*- coding: utf-8 -*-
"""问题三：论文插图生成（基于贾的 p3 final 模型）。

数据源与 p3_tables.py 完全一致——只读结果文件，不重新求解：
  * 06_支撑材料/p3_spec.json        指定日期明细（p3_export.py 写出）
  * 06_支撑材料/p3_analysis.json    全量回放、消融、精度（p3_analysis.py 写出）
  * 06_支撑材料/p3_main_arrays.npz  主策略逐时段数组（p3_analysis.py 写出）
  * 附件 1/2/3                     经 p3_microgrid.load_all() 读取

五张图：
  图 1  同一目标时段的多版本光伏预报（叠加事后实际值）
  图 2  初始计划 g^0 与最终生效 x 曲线（标出紧急补购）
  图 3  实际储电量与实时储备线
  图 4  九种预报使用的费用分解（八种组合 + 只用 0:00 预报的对照）
  图 5  主策略逐日的调整费、紧急费与日末储电量

输出到 04_图/，300 dpi。运行：python3 03_代码/p3_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cumcm_plot import savefig, setup_plot  # noqa: E402

setup_plot()

ROOT = HERE.parent
SUP = ROOT / "08_算法修正" / "输出"

C_VER = {0: "#7f8c8d", 6: "#2980b9", 12: "#e67e22", 18: "#16a085"}
C_ACT = "#c0392b"
C_G0 = "#2980b9"
C_X = "#c0392b"
C_EMG = "#e67e22"
C_SOC = "#16a085"
C_R = "#8e44ad"
C_PLAN = "#34495e"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
TITLE = {"2025-03-20": "2025-03-20（春分）",
         "2025-06-21": "2025-06-21（夏至）",
         "2025-09-23": "2025-09-23（秋分）",
         "2025-12-21": "2025-12-21（冬至）"}
ADJ_ORDER = ["6:00", "12:00", "6:00+12:00", "18:00", "6:00+18:00", "12:00+18:00",
             "6:00+12:00+18:00"]


def hours(N: int) -> np.ndarray:
    return np.arange(N) * 10 / 60.0


def panels():
    fig, axes = plt.subplots(2, 2, figsize=(11.2, 5.4), layout="constrained")
    return fig, axes.ravel()


def hourly(v: np.ndarray) -> np.ndarray:
    """把 144 个十分钟量汇总成 24 个整点量。

    逐十分钟的计划购电量在电价分段恒定的时段内是退化的：把同样多的电挪到哪一段
    都等价，LP 落在哪个顶点取决于求解器，于是相邻十分钟会在 0 与上限之间来回跳。
    按小时汇总后这一层自由度被消掉，剩下的才是"每小时买多少"这个有意义的量。
    """
    return np.asarray(v, dtype=float).reshape(24, 6).sum(axis=1)


# ---------------------------------------------------------------- 图 1
def fig1_versions(M, price, dates, load_kw, pv_kw, fc) -> None:
    N = pv_kw.shape[1]
    t = hours(N)
    idx = {d: i for i, d in enumerate(pd.DatetimeIndex(pd.to_datetime(dates)).strftime("%Y-%m-%d"))}
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        n = idx[d]
        ax.plot(t, pv_kw[n, :], color=C_ACT, lw=2.0, label="实际光伏", zorder=5)
        for k, h in enumerate((0, 6, 12, 18)):
            anchor = 0.0 if h == 0 else float(pv_kw[n, int(h * 6) - 1])
            v = M.pv_interp_for_issue(h, anchor, fc[n, k, :])
            m = ~np.isnan(v)
            ax.plot(t[m], v[m], color=C_VER[h], lw=1.3, ls="--", label=f"{h}:00 预报")
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("光伏功率 / kW")
        ax.set_title(TITLE[d], fontsize=11)
    axes[0].legend(fontsize=8, ncol=2, loc="upper left")
    fig.suptitle("四个发布版本对同一日的光伏预报与实际值", fontsize=12)
    savefig("p3_fig1_versions.png")


# ---------------------------------------------------------------- 图 2
def fig2_purchase(arr, nday: dict) -> None:
    t = np.arange(24)
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        k = nday[d]
        g0 = hourly(arr[f"gP_{k}"])
        x = hourly(arr[f"gA_{k}"])
        r = hourly(arr[f"r_{k}"])
        up = np.clip(x - g0, 0, None)
        dn = np.clip(g0 - x, 0, None)
        ax.plot(t, g0, color=C_G0, lw=1.4, ls="--", label="初始计划 $g^0_t$")
        ax.plot(t, x, color=C_X, lw=1.5, label="最终生效 $x_t$")
        if up.max() > 1e-6:
            ax.fill_between(t, g0, g0 + up, where=up > 1e-6, color=C_X, alpha=0.28,
                            step="mid", label="上调（$1.5p_t$）")
        if dn.max() > 1e-6:
            ax.fill_between(t, x, x + dn, where=dn > 1e-6, color=C_G0, alpha=0.25,
                            step="mid", label="下调（退 $0.5p_t$）")
        if r.max() > 1e-6:
            ax.fill_between(t, 0, r, where=r > 1e-6, color=C_EMG, alpha=0.9,
                            step="mid", label="紧急购电 $r_t$")
        ax.set_xlim(0, 23)
        ax.set_xticks(range(0, 24, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("小时购电量 / kWh")
        ax.set_title(TITLE[d], fontsize=11)
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("逐小时汇总的初始计划购电与最终生效购电（6/12/18 时提交调整）",
                 fontsize=12)
    savefig("p3_fig2_purchase.png")


# ---------------------------------------------------------------- 图 3
def fig3_storage(arr, nday: dict, spec: dict) -> None:
    import p3_microgrid as M
    N = 144
    t = hours(N)
    fig, axes = panels()
    for ax, d in zip(axes, SPECIAL):
        k = nday[d]
        E0 = float(spec["spec"][d]["E0"])
        E = np.concatenate([[E0], arr[f"E_{k}"]])
        Eb = np.concatenate([[E0], arr[f"Ebar_{k}"]])
        tt = np.concatenate([[0.0], t + 10 / 60])
        ax.axhline(M.E_MIN, color="gray", lw=0.8, ls=":")
        ax.axhline(M.E_MAX, color="gray", lw=0.8, ls=":")
        ax.plot(tt, Eb, color=C_R, lw=1.2, ls="--", label="参考轨迹 $\\bar E_t$")
        ax.plot(tt, E, color=C_SOC, lw=1.6, label="实际储电量 $E_t$")
        ax.fill_between(tt, M.E_MIN, E, color=C_SOC, alpha=0.10)
        for h in (6, 12, 18):
            ax.axvline(h, color="k", lw=0.7, ls=":", alpha=0.5)
        ax.set_xlim(0, 24)
        ax.set_ylim(M.E_MIN - 400, M.E_MAX + 400)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("时刻 / h")
        ax.set_ylabel("储电量 / kWh")
        ax.set_title(f"{TITLE[d]}（0:00 储电 {E0:,.0f} kWh）", fontsize=10)
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("实际储电量轨迹（竖虚线为 6/12/18 时调整提交点）", fontsize=12)
    savefig("p3_fig3_storage.png")


# ---------------------------------------------------------------- 图 4
def fig4_combos(anal: dict) -> None:
    cfgs = anal["configs"]
    labels = ["仅 0:00"] + ADJ_ORDER
    rows = [cfgs["对照：只用0:00预报"]] + [cfgs[lab] for lab in ADJ_ORDER]
    pa = np.array([r["plan_adj"] for r in rows]) / 1e4
    em = np.array([r["emg"] for r in rows]) / 1e4
    tot = pa + em

    fig, ax = plt.subplots(figsize=(10.4, 3.5))
    xp = np.arange(len(labels))
    ax.bar(xp, pa, 0.62, color=C_PLAN, label="计划与调整费")
    ax.bar(xp, em, 0.62, bottom=pa, color=C_EMG, label="紧急购电费")
    for i, v in enumerate(tot):
        ax.annotate(f"{v:,.1f}", (i, v), ha="center", va="bottom", fontsize=8,
                    xytext=(0, 3), textcoords="offset points")
    ax.set_xticks(xp)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("费用 / 万元")
    # 给柱顶标注与图例各留出净空：bar 数值在 1.3e3 量级，图例贴在 0.8--1.0 高度带，
    # 若上限只放 13% 富余，最右一根的标注会被图例压住。
    ax.set_ylim(0, tot.max() * 1.35)
    ax.set_title("八种预报使用方式的实际总费用分解（参数固定，最左一项为只需 0:00 时的对照）",
                 fontsize=11)
    ax.legend(fontsize=9)
    ax.axvline(0.5, color="gray", lw=0.8, ls="--")
    savefig("p3_fig4_combos.png")


# ---------------------------------------------------------------- 图 5
def fig5_daily(anal: dict) -> None:
    import p3_microgrid as M
    d = pd.DataFrame(anal["daily"])
    dt = pd.to_datetime("2025-01-01") + pd.to_timedelta(d["day"], unit="D")
    fig, axes = plt.subplots(3, 1, figsize=(11.0, 5.6), sharex=True)
    axes[0].plot(dt, d["plan_adj"], color=C_X, lw=0.9)
    axes[0].set_ylabel("计划调整费 / 元")
    axes[1].plot(dt, d["emg"], color=C_EMG, lw=0.9)
    axes[1].set_ylabel("紧急费 / 元")
    axes[2].plot(dt, d["E144"], color=C_SOC, lw=1.0)
    axes[2].axhline(M.E_MIN, color="gray", lw=0.8, ls=":")
    axes[2].axhline(M.E_MAX, color="gray", lw=0.8, ls=":")
    axes[2].set_ylabel("24:00 储电量 / kWh")
    axes[2].set_xlabel("日期")
    fig.suptitle("主策略逐日的计划调整费、紧急费与日末储电量", fontsize=12, y=0.995)
    fig.tight_layout()
    savefig("p3_fig5_daily.png")


def main() -> None:
    import p3_microgrid as M
    price, dates, load_kw, pv_kw, fc = M.load_all()
    spec = json.loads((SUP / "p3_spec.json").read_text(encoding="utf-8"))
    anal = json.loads((SUP / "p3_analysis.json").read_text(encoding="utf-8"))
    z = np.load(SUP / "p3_main_arrays.npz")
    arr = {k: z[k] for k in z.files}
    ds = pd.DatetimeIndex(pd.to_datetime(dates)).strftime("%Y-%m-%d")
    nday = {d: int(np.flatnonzero(ds == d)[0]) for d in SPECIAL}

    fig1_versions(M, price, dates, load_kw, pv_kw, fc)
    print("  图 1 多版本光伏预报")
    fig2_purchase(arr, nday)
    print("  图 2 初始/最终购电曲线")
    fig3_storage(arr, nday, spec)
    print("  图 3 实际储电量轨迹")
    fig4_combos(anal)
    print("  图 4 预报组合费用分解")
    fig5_daily(anal)
    print("  图 5 逐日费用与储电量")
    print(f"输出目录：{ROOT / '04_图'}")


if __name__ == "__main__":
    main()
