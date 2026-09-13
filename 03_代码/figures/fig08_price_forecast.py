# -*- coding: utf-8 -*-
r"""
Fig.8  问题四：价格结构分解 P(d,t) = F_t + R(d,t)，以及"同星期加权"预测
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
附件 4 的日价格并不是一团噪声。把它按"日内形状 + 星期水平"拆开后立刻可见：
**日内形状与附件 1 逐时段均值只差 5.15e-05 元/kWh（水平相同）**，而残差几乎
全部集中在**星期维度**上——周五、周六比其余五天低 **0.1913 元/kWh**（均价的
25.0%）。因此"取最近三个同星期几加权平均"不是拍脑袋：它同时借用了附件 1 的
日内形状与该星期几的缓慢漂移偏移。

证据链（三张 panel 依次回答"形状是什么 / 偏移在哪 / 预测怎么样"）
------------------------------------------------------------------
(a) 形状 —— 附件 1 曲线 F_t 的 144 段逐时段结构：深夜低谷、傍晚尖峰，
    峰谷比 3.76；同时画出附件 4 的 365 天逐时段均值，两条曲线几乎重合。
(b) 偏移 —— 残差 R(d,t) = P − F 按星期几平均：周一至周四与周日都在
    +0.053 附近，**周五、周六却是 −0.137**；星期效应解释了残差方差的 41.7%。
(c) 预测 —— 冻结预测器 R̂ = 0.5R(d−7)+0.3R(d−14)+0.2R(d−21) 在评价区间
    （2025-02-01 至 12-31，334 天）的平均绝对误差 **0.0446 元/kWh**，只有均价
    的 5.9%；图右给出 2025-06-02 起一周的实际/预测逐时段对比。

三条可复算的读数
----------------
1. 水平一致性  max_t |mean_d P(d,t) − F_t| = **5.151e-05** 元/kWh
2. 残差正交性  corr(R, F) = **−1.48e-05**
3. 星期偏移    族A（周一~四+日）**+0.0545**，族B（周五、六）**−0.1368**，
   差 **0.1913** 元/kWh

信息边界（问题四的硬约束，图内明确标出）
------------------------------------------
预测只用 **d−7 / d−14 / d−21 的实际价格**——它们全部落在过去。当日的任何
实际价格都不进入决策；图中 (c) 的"实际"曲线仅用于事后评估，不是模型输入。

数据来源（真实，无编造）
------------------------
* 01_题目/C题/附件/附件1.xlsx —— 固定日内价格曲线 F（144 段）
* 01_题目/C题/附件/附件4.xlsx —— 全年实际电价 P（365 × 144）
* 06_支撑材料/p4_price_forecast_candidates.csv —— 各候选预测器的 MAE，
  用于核对本图复现的 0.5/0.3/0.2 取值（该表记 0.044573976837990685）。

本图只做读取、差分与加权平均（预测公式照抄论文），**不重算任何调度模型**。

排版约束
--------
全部文字为普通 Unicode，不使用 mathtext。多面板用 constrained layout 且
**不显式传 hspace**（见 Fig.6 docstring 的实测坑）；panel (c) 的日界线用
`axvline` 限定在数据带内，避免线端穿过文字被判 text-stroke。

图内不出现文字（本版新增）
--------------------------
图内只留坐标轴标签/刻度标签/panel 字母/图例；除此之外只允许数字与符号。
原先 panel (a) 写的「峰价 1.40 / 谷价 0.37 / 均价 0.77」三处汉字已删，只留
`1.40` / `0.37` / `0.77` 三个纯数值读数，各自贴住所标注的峰、谷与均值线。
三个 panel 里的结论句（星期偏移量、族 A/B 均值、方差解释比例、MAE 与信息边界
说明）与底部脚注一并移入 `CAPTION` / `NOTE`，由 figstyle 的 prose gate 拦截。
去掉上下两条文字带后画布从 132 mm 收到 116 mm。

输出
----
04_图/pdf/fig08_price_forecast.pdf
04_图/pdf/fig08_price_forecast.svg
04_图/fig08_price_forecast.png
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

ATT_DIR = S.ROOT / "01_题目" / "C题" / "附件"
SLOTS = 144
DT_H = 10.0 / 60.0              # 每段 10 min = 1/6 h（与 fig02 的 hours() 一致）
DAY0, DAY1 = 31, 365            # 评价区间：2025-02-01 起 334 天（0-based）
WEIGHTS = (0.5, 0.3, 0.2)       # 冻结权重（论文正文，选型期胜出）
LAGS = (7, 14, 21)
WEEK_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

#: panel (c) 展示窗口：2025-06-02（周一）起 7 天，含周五、周六
SHOW_START = 152                # 2025-06-02 的 0-based 日索引
SHOW_DAYS = 7

STEM = "fig08_price_forecast"

#: 正文图题（进入 LaTeX \caption{}，图内不再出现）
CAPTION = "附件 4 电价的结构分解：价格 = 附件 1 的日内形状 + 星期几的缓慢漂移"

C_FAM_A = "#A0522D"             # 族 A（周一~四+日）：残差为正（电价偏高）
C_FAM_B = "#D8B79F"             # 族 B（周五、六）：残差为负（电价偏低）


# ================================================================ 数据

def load_attach() -> tuple[np.ndarray, np.ndarray, list]:
    """读附件 1 的固定曲线 F 与附件 4 的全年实际价格 P 及日期。"""
    ws = openpyxl.load_workbook(ATT_DIR / "附件1.xlsx", data_only=True)["Sheet1"]
    F = np.array([r[1] for r in list(ws.iter_rows(values_only=True))[1:]], float)
    ws = openpyxl.load_workbook(ATT_DIR / "附件4.xlsx", data_only=True)["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))[1:]
    P = np.array([[float(x) for x in r[1:1 + SLOTS]] for r in rows], float)
    dates = [r[0] for r in rows]
    if F.shape != (SLOTS,) or P.shape != (365, SLOTS):
        raise ValueError(f"附件维度异常：F={F.shape}, P={P.shape}")
    return F, P, dates


def frozen_mae() -> float:
    """从支撑材料读回候选表里 0.5/0.3/0.2 的 MAE，用于交叉核对。"""
    with open(S.SUP_DIR / "p4_price_forecast_candidates.csv",
              encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["预测器"].strip() == "同星期加权 0.5/0.3/0.2":
                return float(row["平均绝对误差_元每kWh"])
    raise KeyError("p4_price_forecast_candidates.csv 中找不到『同星期加权 0.5/0.3/0.2』")


def predict(Rm: np.ndarray, n: int) -> np.ndarray:
    """冻结预测器：R̂(d,t) = Σ w_k · R(d−lag_k, t)。R̂ 是**逐时段**的。"""
    return sum(w * Rm[n - lag] for w, lag in zip(WEIGHTS, LAGS)) / sum(WEIGHTS)


# ================================================================ 画图

def build(F, P, dates) -> plt.Figure:
    S.apply_style()
    Rm = P - F
    wd = np.array([d.weekday() for d in dates])

    # --- panel b 的统计量（族 A/B 的均值、方差解释比例已移入图下"注"，此处不再算）---
    rbar = np.array([Rm[wd == k].mean() for k in range(7)])
    rstd = np.array([Rm[wd == k].mean(1).std(ddof=1) for k in range(7)])

    # 高度 116 mm：已去掉顶部标题带与底部注脚带（移入 caption/note），比首版矮 16 mm。
    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(116)), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.02], wspace=0.20)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, :])
    for ax in (ax_a, ax_b, ax_c):
        ax.grid(False)

    t = np.arange(SLOTS) * DT_H

    # ============================================================ (a) 日内形状
    ax_a.plot(t, F, color=S.C_PRICE, lw=1.4, drawstyle="steps-post", zorder=4,
              label="附件 1 固定曲线 F")
    ax_a.plot(t, P.mean(0), color=S.C_FORECAST, lw=1.0, ls="--", zorder=3,
              label="附件 4 逐时段均值")
    ax_a.axhline(F.mean(), color=S.C_REF, lw=0.8, ls=":", zorder=2)

    # 谷/峰窗口：用**贴底**的浅灰条带标出（仅提示，不参与数据编码）。
    # 首版铺满全高，结果任何落在 0–6 h / 18–20 h 横坐标范围内的文字（左上角图例、
    # 峰顶标注）都会被条带的竖直边缘切到，碰撞审计报 text-fill-edge；改成贴底条带
    # 后文字区（图例在顶部、峰价在峰顶）与条带完全脱开。
    ax_a.axvspan(0, 6, ymin=0.0, ymax=0.05, facecolor=S.C_BAND,
                 edgecolor="none", linewidth=0, zorder=0)
    ax_a.axvspan(18, 20, ymin=0.0, ymax=0.05, facecolor=S.C_BAND,
                 edgecolor="none", linewidth=0, zorder=0)
    imax, imin = int(np.argmax(F)), int(np.argmin(F))
    # 三个读数只留数值：原先写作「峰价 1.40 / 谷价 0.37 / 均价 0.77」，汉字已移入
    # 图下注。数值各自贴住它所标注的对象——峰/谷读数居中贴在曲线峰谷正上方，
    # 均价读数贴在点线的右端——避免出现"悬空数字"。
    # 首版峰价标在峰左侧且 ha="right"，文字右端 (x≈14.9 h) 会压到面板左上角图例的
    # 第二行（图例标签很长，横向一直伸到约 14.9 h 处）。该压叠一直存在，只是被碰撞
    # 审计的 trace 归并缺陷静默漏检（已修）；改为峰顶正上方居中后彻底脱开。
    #
    # 谷价读数不能取 F.min()×系数：谷底是个窄 V 形，紧邻的阶梯段比谷底高，
    # 按系数给的高度会被邻近阶梯穿过（实测判 text-stroke，'0.37' 被 2 条路径穿过）。
    # 改成取谷底两侧各 ±8 段（约 ±1.3 h，宽于标签自身）内的局部最高点再抬 6%。
    ax_a.annotate(f"{F[imax]:.2f}", xy=(t[imax], F[imax]),
                  xytext=(t[imax], F[imax] * 1.045),
                  fontsize=6.4, color=S.C_PRICE, fontweight="bold",
                  ha="center", va="bottom")
    w = 8
    y_valley = float(F[max(0, imin - w):imin + w + 1].max()) * 1.06
    ax_a.annotate(f"{F[imin]:.2f}", xy=(t[imin], F[imin]),
                  xytext=(t[imin], y_valley),
                  fontsize=6.4, color=S.C_PRICE, ha="center", va="bottom")
    ax_a.text(23.7, F.mean() + 0.05, f"{F.mean():.2f}", ha="right", va="bottom",
              fontsize=6.2, color=S.C_REF)

    ax_a.set_xlim(0, 24)
    ax_a.set_ylim(0, F.max() * 1.30)
    ax_a.set_xticks(range(0, 25, 6))
    ax_a.set_xlabel("当日时刻 (h)")
    ax_a.set_ylabel("电价（元/kWh）")
    # 图例贴左沿（首版锚在 0.20）：锚到 0.20 时图例右缘约到 x=14.9 h，正好与峰顶
    # 上方的「峰价」标注抢位置。贴左沿后图例只占 x≈0–10 h，峰价标注留出 30 pt 净空。
    ax_a.legend(loc="upper left", bbox_to_anchor=(0.02, 1.0), ncol=1,
                handlelength=1.6, borderaxespad=0.0)
    S.add_panel_label(ax_a, "a", x=0.0, y=1.0, dx_pt=-13, dy_pt=2.0, va="bottom")

    # ============================================================ (b) 星期残差
    xs = np.arange(7)
    cols = [C_FAM_A] * 7
    for k in (4, 5):
        cols[k] = C_FAM_B
    ax_b.bar(xs, rbar, width=0.60, color=cols, edgecolor="none", linewidth=0,
             zorder=3)
    ax_b.errorbar(xs, rbar, yerr=rstd, fmt="none", ecolor="#7A7A7A",
                  elinewidth=0.7, capsize=1.8, capthick=0.7, zorder=4)
    ax_b.axhline(0, color="#4D4D4D", lw=0.8, zorder=2)
    ax_b.set_xticks(xs)
    ax_b.set_xticklabels(WEEK_ZH, fontsize=6.8)
    ax_b.set_xlim(-0.62, 6.62)
    # 纵轴收紧到数据真实跨度（-0.197 … +0.117）：结论文字移出后不再需要顶部留白。
    ax_b.set_ylim(-0.24, 0.17)
    # 不画 0.2 刻度：它正好贴在轴上沿，会与面板字母 b 相撞
    ax_b.set_yticks([-0.2, -0.1, 0.0, 0.1])
    ax_b.set_xlabel("星期")
    ax_b.set_ylabel("残差日均值（元/kWh）", labelpad=4)

    S.add_panel_label(ax_b, "b", x=0.0, y=1.0, dx_pt=-13, dy_pt=2.0, va="bottom")

    # ============================================================ (c) 预测对比
    lo, hi = SHOW_START, SHOW_START + SHOW_DAYS
    n = hi - lo
    tt = np.arange(n * SLOTS) * DT_H                       # 0 … 168
    a_line = np.concatenate([P[d] for d in range(lo, hi)])
    h_line = np.concatenate([F + predict(Rm, d) for d in range(lo, hi)])

    ax_c.plot(tt, a_line, color=S.C_ACTUAL, lw=0.8, zorder=4,
              label="实际价格 P（仅事后评估，不作输入）")
    ax_c.plot(tt, h_line, color=S.C_RISK, lw=0.9, zorder=5,
              label="预测价格 P̂ = F + R̂")
    for k in range(1, n):
        ax_c.axvline(24 * k, color="#B4B4B4", lw=0.7, ls=":", zorder=1,
                     ymin=0.02, ymax=0.70)
    ax_c.set_xlim(0, 24 * n)
    # 顶部留白 26%：图例（2 行）占上沿约 16% 高度，峰价须落在图例下沿之下。
    # 实测留 14% 时峰价顶到图例文字，被判 text-stroke（1 条 FAIL）。
    ax_c.set_ylim(0, float(np.concatenate([a_line, h_line]).max()) * 1.26)
    ax_c.set_xticks([24 * k + 12 for k in range(n)])
    ax_c.set_xticklabels([f"{dates[lo + k]:%m-%d}\n{WEEK_ZH[(lo + k) % 7]}"
                          for k in range(n)], fontsize=6.6)
    ax_c.set_xlabel("日期（2025 年，起止 06-02 周一 至 06-08 周日）")
    ax_c.set_ylabel("电价（元/kWh）")
    ax_c.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=1,
                handlelength=1.8, borderaxespad=0.0)
    S.add_panel_label(ax_c, "c", x=0.0, y=1.0, dx_pt=-13, dy_pt=2.0, va="bottom")

    # 画布已无顶部标题带与底部注脚带，axes 吃满可用高度。
    fig.get_layout_engine().set(rect=(0.008, 0.028, 0.986, 0.930))
    return fig


def main() -> None:
    S.apply_style()
    F, P, dates = load_attach()
    Rm = P - F
    wd = np.array([d.weekday() for d in dates])
    rbar = np.array([Rm[wd == k].mean() for k in range(7)])
    fam_a, fam_b = rbar[[0, 1, 2, 3, 6]].mean(), rbar[[4, 5]].mean()

    print(f"附件1 F: n={len(F)} min={F.min():.4f} max={F.max():.4f} "
          f"mean={F.mean():.4f} 峰谷比={F.max()/F.min():.2f}")
    print(f"水平一致 max|mean_d P − F| = {np.abs(P.mean(0) - F).max():.3e}")
    print(f"残差正交 corr(R,F) = {np.corrcoef(Rm.ravel(), np.tile(F, 365))[0,1]:+.3e}")
    print("星期均值 周一→周日:", " ".join(f"{v:+.4f}" for v in rbar))
    print(f"族A +{fam_a:.4f}  族B {fam_b:.4f}  差 {fam_a - fam_b:.4f}")
    within = np.mean([Rm[wd == k].var() for k in range(7)])
    print(f"星期效应解释方差 {100 * (1 - within / Rm.var()):.1f}%")

    hat = np.array([predict(Rm, n) for n in range(DAY0, DAY1)])   # R̂ (334,144)
    mae = float(np.abs(hat - Rm[DAY0:DAY1]).mean())   # |R̂−R|，即预测价 vs 实际价
    ref = frozen_mae()
    print(f"\n冻结预测器 MAE = {mae:.15f}")
    print(f"候选表记录        = {ref:.15f}")
    ok = abs(mae - ref) < 1e-12
    print("✓ 与候选表一致" if ok else "✗ 与候选表不一致！")
    if not ok:
        raise AssertionError("复算 MAE 与 p4_price_forecast_candidates.csv 不符")

    gap = fam_a - fam_b
    within = np.mean([Rm[wd == k].var() for k in range(7)])
    expl = 100 * (1 - within / Rm.var())
    note = (
        "注：(a) x 轴下方的浅灰条带仅标出谷段（0:00–6:00）与晚高峰（18:00–20:00）"
        f"两个时间窗，不参与数据编码；两条曲线逐时段均值之差 max|·| = "
        f"{np.abs(P.mean(0) - F).max():.2e} 元/kWh，峰谷比 {F.max() / F.min():.2f}。"
        f"图中三个数值读数依次为 F 的峰价 {F.max():.2f}、谷价 {F.min():.2f} 与"
        f"日均价 {F.mean():.2f} 元/kWh（点线即日均价水平线）。"
        "(b) 残差 R = P − F 按星期几平均，误差棒为各星期几「日均残差」的 ±1σ；"
        f"族 A（周一至周四及周日）+{fam_a:.4f}、族 B（周五、周六）{fam_b:.4f} 元/kWh，"
        f"相差 {gap:.4f} 元/kWh（均价的 {100 * gap / P.mean():.1f}%），"
        f"星期效应解释残差方差的 {expl:.1f}%。"
        "(c) 预测照抄论文 R̂(d,t) = 0.5R(d−7,t) + 0.3R(d−14,t) + 0.2R(d−21,t)，"
        f"评价区间（2025-02-01 至 12-31，334 天）复算 MAE {mae:.6f} 元/kWh"
        f"（＝均价的 {100 * mae / P.mean():.1f}%），与 06_支撑材料候选表的 "
        f"{ref:.6f} 逐位一致。预测只读 d−7 / d−14 / d−21 的实际价格（全部落在过去），"
        "当日实际价格不进入决策，「实际」曲线仅用于事后评估。"
        "数据：01_题目/C题/附件 的附件 1、附件 4 与 06_支撑材料 的候选表（只读引用）。"
    )

    fig = build(F, P, dates)
    saved = S.save_figure(fig, STEM, caption=CAPTION, note=note)
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
