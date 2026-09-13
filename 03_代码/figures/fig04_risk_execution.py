# -*- coding: utf-8 -*-
r"""
Fig.4  问题二：超出风险净负荷 ≠ 一定发生紧急购电
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
"实际净负荷超过风险修正净负荷"只是发生紧急购电的**必要条件、不是充分条件**。
真正的触发机制是「实际超出风险余量的部分」与「储能剩余可放能力」**两者之差**：
只要储能还有余量，超出部分就被吸收；只有储能被放到储备线、再无电可放时，
超出才转化为 5 倍电价的紧急购电支出。

证据链（2×2：行是两天，列是两个量；同列两 panel 直接可比）
--------------------------------------------------------
(a) 冬至 12-21 净负荷 —— 18 个时段超出风险净负荷，最大超出 84.4 kWh
(b) 冬至 12-21 储电量 —— 储能全程未触底（最低 1401 kWh）→ **紧急购电 = 0**
(c) 秋分 09-23 净负荷 —— 71 个时段超出，最大超出 133.7 kWh
(d) 秋分 09-23 储电量 —— 储能被放到 1200 kWh 下界 → **19 个时段紧急购电**

(a)(b) 与 (c)(d) 两组对照说明：两天的"超出"都存在，(b) 无损而 (d) 触底，
唯一的差别是储能余量。这正是论文附录"紧急购电的触发机制"一节的数据。

为什么选这两天而不是论文同时提到的春分 03-20
--------------------------------------------
论文附录把 03-20 与 12-21 并列称"储能全部吸收、零紧急购电"，但逐时段核对
03-20 实际有 1 个时段、14.6 kWh 的紧急购电（相对当日 45 655 kWh 计划量约
0.03%，量级可忽略，但严格讲不是零）。为让对照完全干净、可被逐项复核，本图
改用**数据上确为零**的 12-21。03-20 的结论（50 个时段超出、最大 79.9 kWh）
与本图结论一致，未受影响。

数据来源（真实，无编造）
------------------------
06_支撑材料/p2_detail.csv —— 逐时段 实际负载/实际光伏/风险净负荷/参考储电量/
实际储电量/紧急购电量。**只读 CSV，不重算模型。**
储备线 R = 1200 + ρ(Ē − 1200)，ρ 由 p2_daily.csv 标定参数列读出。

输出
----
04_图/pdf/fig04_risk_execution.pdf
04_图/fig04_risk_execution.png
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

E_MIN, E_MAX = 1200.0, 10800.0

#: 两天：数据上"超出但零紧急购电" 与 "超出且触底紧急购电" 的干净对照
DAY_ABSORB = "2025-12-21"     # 冬至
DAY_EMERG = "2025-09-23"      # 秋分

BAND_EXCEED = "#F7E3E1"       # 超出风险净负荷的时段底纹
XY_LABEL = (0.020, 0.968)
XY_CLAIM = (0.985, 0.968)


def read_rho() -> float:
    """从 p2_daily.csv 的标定参数列读出 ρ；读不到则退回 0.9。"""
    try:
        d = pd.read_csv(S.SUP_DIR / "p2_daily.csv", encoding="utf-8-sig")
        m = re.search(r"ρ=([0-9.]+)", str(d["params"].iloc[0]))
        if m:
            return float(m.group(1))
    except (KeyError, FileNotFoundError, IndexError):
        pass
    return 0.9


def _claim(ax, text: str, color: str) -> None:
    ax.text(*XY_CLAIM, text, transform=ax.transAxes, ha="right", va="top",
            fontsize=6.6, color=color, fontweight="bold")


def hours(n: int) -> np.ndarray:
    return np.arange(n) * 10.0 / 60.0


def build(det: pd.DataFrame, rho: float) -> plt.Figure:
    S.apply_style()

    # 用 constrained layout：由 matplotlib 自己为旋转的 y 轴标签、刻度与 x 轴标签
    # 预留空间。手工 subplots_adjust 时 wspace 留不够，右列的 y 轴标签会压到左列
    # 的绘图区上（碰撞审计报 text-stroke）。
    fig, axes = plt.subplots(
        2, 2, figsize=(S.mm2in(160), S.mm2in(134)), sharex=True,
        layout="constrained",
        gridspec_kw={"hspace": 0.10, "wspace": 0.13},
    )
    (ax_na, ax_sa), (ax_ne, ax_se) = axes
    for ax in axes.ravel():
        ax.grid(False)

    stats = {}
    for day, ax_n, ax_s, tag in (
        (DAY_ABSORB, ax_na, ax_sa, "absorb"),
        (DAY_EMERG, ax_ne, ax_se, "emerg"),
    ):
        g = det[det["日期"] == day]
        if g.empty:
            raise ValueError(f"p2_detail.csv 中没有 {day} 的数据")
        t = hours(len(g))
        dt = 10.0 / 60.0
        N = (g["实际负载_kWh"] - g["实际光伏_kWh"]).to_numpy(float)
        Nr = g["风险净负荷_kWh"].to_numpy(float)
        emg = g["紧急购电_kWh"].to_numpy(float)
        Ebar = g["参考储电量_kWh"].to_numpy(float)
        E = np.concatenate([[g["期初储电量_kWh"].iloc[0]],
                            g["期末储电量_kWh"].to_numpy(float)])
        tE = np.concatenate([[0.0], t + dt])
        reserve = E_MIN + rho * (Ebar - E_MIN)
        exceed = N - Nr

        stats[tag] = dict(n_ex=int((exceed > 1e-9).sum()),
                          max_ex=float(exceed.max()),
                          n_emg=int((emg > 1e-6).sum()),
                          emg_kwh=float(emg.sum()),
                          soc_min=float(E.min()))

        # ---------------- 净负荷 panel ----------------
        band = exceed > 1e-9
        for a, b in _runs(band):
            ax_n.axvspan(t[a], t[b - 1] + dt, facecolor=BAND_EXCEED,
                         edgecolor="none", linewidth=0, zorder=0)
        ax_n.plot(t, Nr, color=S.C_RISK, lw=1.4, zorder=4)
        ax_n.plot(t, N, color=S.C_ACTUAL, lw=1.4, zorder=5)
        # 纵轴必须容纳**负**净负荷：秋分正午光伏超过负载，净负荷最低到 −479 kWh。
        # 早期版本写死 set_ylim(0, ...)，把这 26 个时段整段裁掉，曲线在图上凭空
        # 断成两截——属于把真实数据画丢，必须避免。
        lo_n = min(0.0, float(N.min()), float(Nr.min()))
        hi_n = max(float(N.max()), float(Nr.max()))
        pad_n = 0.10 * (hi_n - lo_n)
        ax_n.set_ylim(lo_n - pad_n, hi_n + pad_n * 1.2)
        ax_n.axhline(0.0, color="#9A9A9A", lw=0.7, zorder=1)
        ax_n.set_ylabel("净负荷 (kWh/10min)")
        ax_n.set_xlim(0, 24)
        ax_n.set_xticks(range(0, 25, 4))
        S.add_panel_label(ax_n, "a" if tag == "absorb" else "c",
                          x=XY_LABEL[0], y=XY_LABEL[1], dx_pt=0, dy_pt=0,
                          va="top")

        # 紧急购电时段：在净负荷 panel 上用红色竖线标出
        if stats[tag]["n_emg"]:
            for a, _ in _runs(emg > 1e-6):
                ax_n.axvline(t[a], ymin=0.14, ymax=0.86, color=S.C_EMERGENCY,
                             lw=1.0, ls="-", alpha=0.85, zorder=3)

        # ---------------- 储电量 panel ----------------
        for a, b in _runs(band):
            ax_s.axvspan(t[a], t[b - 1] + dt, facecolor=BAND_EXCEED,
                         edgecolor="none", linewidth=0, zorder=0)
        ax_s.plot(t, reserve, color=S.C_REF, lw=1.1, ls="--", zorder=3)
        ax_s.plot(tE, E, color=S.C_SOC, lw=1.8, zorder=5)
        ax_s.fill_between(tE, E_MIN, E, color=S.C_SOC, alpha=0.11, lw=0,
                          edgecolor="none", zorder=2)
        ax_s.axhline(E_MIN, color=S.C_REF, ls=":", lw=1.0, zorder=3)
        ax_s.set_ylim(0, E_MAX * 1.18)
        ax_s.set_xlim(0, 24)
        ax_s.set_xticks(range(0, 25, 4))
        ax_s.set_ylabel("储电量 (kWh)")
        S.add_panel_label(ax_s, "b" if tag == "absorb" else "d",
                          x=XY_LABEL[0], y=XY_LABEL[1], dx_pt=0, dy_pt=0,
                          va="top")

        if stats[tag]["n_emg"]:
            for a, b in _runs(emg > 1e-6):
                ax_s.axvspan(t[a], t[b - 1] + dt, facecolor=S.C_EMERGENCY,
                             alpha=0.20, edgecolor="none", linewidth=0, zorder=1)

    # ---------------------------------------------------------- 结论标注
    st_a, st_e = stats["absorb"], stats["emerg"]

    _claim(ax_na, f"冬至 12-21：{st_a['n_ex']} 个时段超出", S.C_ACTUAL)
    _claim(ax_sa, f"储能未触底 → 紧急购电 = 0", S.C_SOC)
    _claim(ax_ne, f"秋分 09-23：{st_e['n_ex']} 个时段超出", S.C_ACTUAL)
    _claim(ax_se, f"储能触底 → {st_e['n_emg']} 个时段紧急购电", S.C_EMERGENCY)

    # 日期与日期对照写在 panel 结论里，**不另设行标题**：行间那点空隙被上下两行
    # 绘图区占满，任何夹在中间的整行文字都会被曲线穿过（早期版本即为此）。
    # 底纹含义放进脚注，避免在绘图区底部再压一行字（底部正是曲线回落的区间）。

    # 四个 panel 共用同一条时间轴，逐幅挂 x 轴标签既冗余、又会被刻度笔画穿过；
    # 改为在绘图区下方挂**一个**共享标签，位置显式给定，不参与 axes 布局。
    fig.text(0.5, 0.090, "时刻 (h)", ha="center", va="center",
             fontsize=S.FS_LABEL, color="#272727")

    note = ("注：两天都出现了「实际 > 风险净负荷」，差别只在储能余量——真正的触发机制是"
            "「超出风险余量的部分」与「储能剩余可放能力」之差。浅红底纹 = 实际净负荷 > 风险净负荷；"
            f"红色带 = 紧急购电时段。储备线 R = 1200 + ρ(Ē − 1200)，ρ = {rho:.1f} 读自标定结果。")
    fig.text(0.006, 0.006, S.wrap_cjk(note, fontsize=6.2), fontsize=6.2, color="#7A7A7A",
             ha="left", va="bottom", linespacing=1.5)

    # rect = (left, bottom, width, height)，四者之和不得超过 1（早期写成
    # height=0.985 而 bottom=0.105，顶端越界，对齐门直接报 ERROR 并阻断导出）。
    fig.get_layout_engine().set(rect=(0.008, 0.160, 0.984, 0.828))
    return fig


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """布尔掩码 → 连续 True 的 [起, 止) 区间。"""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


def _wrap(text: str, per_line: int) -> str:
    """中文折行。一行超宽会把 bbox_inches='tight' 的整页撑开，必须先折行。"""
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= per_line - 8 and ch in "；，。、）":
            lines.append(cur)
            cur = ""
        elif len(cur) >= per_line:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def main() -> None:
    S.apply_style()
    det = pd.read_csv(S.SUP_DIR / "p2_detail.csv", encoding="utf-8-sig")
    rho = read_rho()
    print(f"ρ = {rho}")
    fig = build(det, rho)
    saved = S.save_figure(fig, "fig04_risk_execution")
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
