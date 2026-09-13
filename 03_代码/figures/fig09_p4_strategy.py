# -*- coding: utf-8 -*-
r"""
Fig.9  问题四：两种合同口径下的策略对照——总费用、尾部代价与节省率
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
问题四的关键不在"预测得多准"，而在**合同允许不允许滚动调整**。同样用波动
电价预测策略：不可调整合同（4-2）全年 1474.08 万元；允许**滚动调整**后
（4-3）降到 1415.33 万元，**省 58.75 万元（−3.99%）**，其中**紧急购电费
从 69.89 万元砍到 15.31 万元（−78.1%）**——代价只是 19.72 万元的调整费。
换句话说：**滚动调整用"低价的计划内改动"替换了"5 倍价的尾部抢购"。**

证据链（三块，各自承担一个不可替代的推理角色）
----------------------------------------------
(a) 构成 —— 六个策略的实际费用拆成 计划费 + 调整费 + 紧急费 三段：
    计划费两支几乎相同（约 1372–1404 万元），差异**全部**在调整费与紧急费。
(b) 放大 —— 把"增量费用"（调整费 + 紧急费）单独放大：不可调整合同 ~70–74 万元，
    可滚动的只 ~35 万元，**尾部代价减半**。
(c) 节省率 —— 本文预测策略相对"固定电价参考"省 0.14%（4-2）/ 0.26%（4-3）；
    相对"完全预知未来"的下界仍差 0.64%（4-2）/ 0.55%（4-3）。

信息边界（问题四的硬约束，图内明确标出）
------------------------------------------
三个策略的价格输入都只用**过去**：预测策略用 d−7/14/21 的实际价；"固定电价
参考"忽略波动；"已知未来"是**理论上界**，仅用于给出下界，**不是可行方案**。

数据来源（真实，无编造）
------------------------
* 06_支撑材料/p4_strategies.csv      —— 6 行（2 分支 × 3 策略）的真实求解输出
* 06_支撑材料/p4_strategy_fees.csv   —— 同一批结果的万元口径（用于交叉核对）

本图只做读取与加总，**不重算任何调度模型、不编造任何数值**。

排版约束
--------
全部文字为普通 Unicode，不使用 mathtext（含 `$...$` 的字符串会绕过 font.family
回退链，中文会变豆腐块）。所有 bar 显式 `edgecolor="none"`（只写 lw=0 仍会在
PDF 里留下贯穿整幅 panel 的描边路径，被判 text-stroke）；关掉网格。
多面板用 constrained layout 且**不显式传 hspace**（见 Fig.6 docstring 实测坑）。

图内不出现文字（本版新增）
--------------------------
图内只留坐标轴标签/刻度标签/panel 字母/图例；除此之外只允许数字与符号
（柱顶金额、`−78.1%`）。原先挂在 panel (b) 右缘的两行「紧急费 69.9 → 15.3 万元 /
−78.1%」已删——汉字移入 `NOTE`，降幅读数改挂到 4-3 组正上方（有锚点，不悬空）。
顶部标题句、panel (a) 的计划费对比结论句、底部脚注全部移入 `CAPTION` / `NOTE`，
由 figstyle 的 prose gate 拦截。去掉上下两条文字带后画布从 134 mm 收到 116 mm。

输出
----
04_图/pdf/fig09_p4_strategy.pdf
04_图/pdf/fig09_p4_strategy.svg
04_图/fig09_p4_strategy.png
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

BRANCHES = ("4-2", "4-3")
STRATS = ("波动电价预测策略", "固定电价参考策略", "未来价格已知参考")
SHORT = {
    "波动电价预测策略": "预测",
    "固定电价参考策略": "固定参考",
    "未来价格已知参考": "已知未来",
}
BRANCH_NOTE = {"4-2": "不可调整合同", "4-3": "可滚动调整合同"}
WK = 1e-4                       # 元 → 万元

STEM = "fig09_p4_strategy"

#: 正文图题（进入 LaTeX \caption{}，图内不再出现）
CAPTION = "允许滚动调整后，尾部代价（紧急购电费）减半，全年总费用因此降 3.99%"

#: 六个柱的横坐标：两个分支各留 1.6 的组间距
XPOS = np.array([0.0, 1.0, 2.0, 3.6, 4.6, 5.6])


# ================================================================ 数据

def load_strategies() -> dict[tuple[str, str], dict]:
    """读 p4_strategies.csv → {(分支, 策略): {各费用字段}}，单位统一为万元。"""
    out: dict[tuple[str, str], dict] = {}
    with open(S.SUP_DIR / "p4_strategies.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            br, st = row["分支"].strip(), row["策略"].strip()
            if br not in BRANCHES or st not in STRATS:
                continue
            out[(br, st)] = {
                "plan":  float(row["计划费_元"]) * WK,
                "adj":   float(row["调整费_元"]) * WK,
                "emg":   float(row["紧急费_元"]) * WK,
                "total": float(row["合计费用_元"]) * WK,
                "emg_kwh": float(row["紧急购电量_kWh"]),
            }
    if len(out) != 6:
        raise ValueError(f"p4_strategies.csv 期望 6 行，实得 {len(out)}")
    return out


def load_fees_crosscheck() -> dict[tuple[str, str], float]:
    """读 p4_strategy_fees.csv 的合计（万元），用于交叉核对。"""
    out: dict[tuple[str, str], float] = {}
    with open(S.SUP_DIR / "p4_strategy_fees.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[(row["分支"].strip(), row["策略"].strip())] = float(row["合计_万元"])
    return out


# ================================================================ 画图

def build(D: dict[tuple[str, str], dict]) -> plt.Figure:
    S.apply_style()

    # 高度 116 mm：已去掉顶部标题带与底部注脚带（移入 caption/note），比首版矮 18 mm。
    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(116)), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.92], wspace=0.24)
    ax_a = fig.add_subplot(gs[0, :])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[1, 1])
    for ax in (ax_a, ax_b, ax_c):
        ax.grid(False)

    keys = [(br, st) for br in BRANCHES for st in STRATS]
    plan = np.array([D[k]["plan"] for k in keys])
    adj = np.array([D[k]["adj"] for k in keys])
    emg = np.array([D[k]["emg"] for k in keys])
    tot = np.array([D[k]["total"] for k in keys])

    # ============================================================ (a) 费用构成
    bw = 0.74
    ax_a.bar(XPOS, plan, bw, color=S.C_GRID, edgecolor="none", linewidth=0,
             zorder=3, label="计划购电费")
    ax_a.bar(XPOS, adj, bw, bottom=plan, color=S.C_DISCHARGE, edgecolor="none",
             linewidth=0, zorder=3, label="调整费")
    ax_a.bar(XPOS, emg, bw, bottom=plan + adj, color=S.C_EMERGENCY,
             edgecolor="none", linewidth=0, zorder=3, label="紧急购电费")
    for x, t in zip(XPOS, tot):
        ax_a.text(x, t + 18, f"{t:,.0f}", ha="center", va="bottom", fontsize=6.3,
                  color="#1A1A1A", fontweight="bold", zorder=5)

    ax_a.set_xlim(-0.7, 6.3)
    ax_a.set_ylim(0, 1870)
    ax_a.set_xticks(XPOS)
    ax_a.set_xticklabels([f"{SHORT[st]}\n({br})" for br, st in keys], fontsize=6.6)
    ax_a.set_ylabel("全年费用（万元）")
    ax_a.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=3,
                handlelength=1.3, columnspacing=1.2, borderaxespad=0.0)

    S.add_panel_label(ax_a, "a", x=0.0, y=1.0, dx_pt=-15, dy_pt=3.5, va="bottom")

    # ============================================================ (b) 增量费用放大
    inc_adj = adj
    inc_emg = emg
    ax_b.bar(XPOS, inc_adj, bw, color=S.C_DISCHARGE, edgecolor="none",
             linewidth=0, zorder=3, label="调整费")
    ax_b.bar(XPOS, inc_emg, bw, bottom=inc_adj, color=S.C_EMERGENCY,
             edgecolor="none", linewidth=0, zorder=3, label="紧急购电费")
    for x, a_, e_ in zip(XPOS, inc_adj, inc_emg):
        ax_b.text(x, a_ + e_ + 1.2, f"{a_ + e_:.1f}", ha="center", va="bottom",
                  fontsize=6.2, color="#1A1A1A", fontweight="bold", zorder=5)

    # 组级读数只留数值。原先在面板右缘写了两行「紧急费 69.9 → 15.3 万元 / −78.1%」，
    # 汉字已移入图下注；改为把降幅挂在 4-3 组正上方——有锚点的数字标签，而不是
    # 悬在右缘、脱离数据的结论句。
    e42 = D[("4-2", "波动电价预测策略")]["emg"]
    e43 = D[("4-3", "波动电价预测策略")]["emg"]
    ax_b.text(float(XPOS[3:].mean()), 47.0, f"−{100 * (1 - e43 / e42):.1f}%",
              ha="center", va="bottom", fontsize=7.0, color=S.C_EMERGENCY,
              fontweight="bold", zorder=6)

    ax_b.set_xlim(-0.7, 6.3)
    ax_b.set_ylim(0, 86)
    ax_b.set_xticks(XPOS)
    ax_b.set_xticklabels([f"{SHORT[st][:2]}\n{br}" for br, st in keys], fontsize=6.6)
    ax_b.set_ylabel("增量费用（万元）")
    ax_b.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0), ncol=1,
                handlelength=1.3, borderaxespad=0.0)
    S.add_panel_label(ax_b, "b", x=0.0, y=1.0, dx_pt=-15, dy_pt=3.5, va="bottom")

    # ============================================================ (c) 相对降幅
    save_42 = 100 * (D[("4-2", "固定电价参考策略")]["total"]
                     - D[("4-2", "波动电价预测策略")]["total"]) / D[("4-2", "固定电价参考策略")]["total"]
    save_43 = 100 * (D[("4-3", "固定电价参考策略")]["total"]
                     - D[("4-3", "波动电价预测策略")]["total"]) / D[("4-3", "固定电价参考策略")]["total"]
    gap_42 = 100 * (D[("4-2", "波动电价预测策略")]["total"]
                    - D[("4-2", "未来价格已知参考")]["total"]) / D[("4-2", "未来价格已知参考")]["total"]
    gap_43 = 100 * (D[("4-3", "波动电价预测策略")]["total"]
                    - D[("4-3", "未来价格已知参考")]["total"]) / D[("4-3", "未来价格已知参考")]["total"]
    vals = np.array([save_42, save_43, gap_42, gap_43])
    cols = [S.C_SAVE, S.C_SAVE, S.C_RISK, S.C_RISK]
    ypos = np.array([3.0, 2.0, 1.0, 0.0])
    ax_c.barh(ypos, vals, 0.62, color=cols, edgecolor="none", linewidth=0,
              zorder=3)
    for y, v in zip(ypos, vals):
        ax_c.text(v + 0.012, y, f"{v:.2f}%", va="center", ha="left",
                  fontsize=6.3, color="#1A1A1A", fontweight="bold", zorder=5)
    ax_c.set_xlim(0, 0.86)
    ax_c.set_ylim(-0.62, 3.62)
    ax_c.set_yticks(ypos)
    ax_c.set_yticklabels(["4-2 省（vs 固定参考）", "4-3 省（vs 固定参考）",
                          "4-2 差距（vs 已知未来）", "4-3 差距（vs 已知未来）"],
                         fontsize=6.4)
    ax_c.set_xlabel("相对差额（%）")
    S.add_panel_label(ax_c, "c", x=0.0, y=1.0, dx_pt=-15, dy_pt=3.5, va="bottom")

    # 画布已无顶部标题带与底部注脚带，axes 吃满可用高度。
    fig.get_layout_engine().set(rect=(0.008, 0.026, 0.986, 0.930))
    return fig


def main() -> None:
    S.apply_style()
    D = load_strategies()
    ref = load_fees_crosscheck()

    for k, v in D.items():
        print(f"{k[0]} {k[1]:<10s} 计划 {v['plan']:9.2f}  调整 {v['adj']:7.2f}  "
              f"紧急 {v['emg']:7.2f}  合计 {v['total']:9.2f} 万元")
    bad = [k for k in D if abs(D[k]["total"] - ref[k]) > 1e-6]
    if bad:
        raise AssertionError(f"合计与 p4_strategy_fees.csv 不符：{bad}")
    print("✓ 6 行合计与 p4_strategy_fees.csv 逐一一致")

    e42, e43 = D[("4-2", "波动电价预测策略")]["emg"], D[("4-3", "波动电价预测策略")]["emg"]
    t42, t43 = D[("4-2", "波动电价预测策略")]["total"], D[("4-3", "波动电价预测策略")]["total"]
    print(f"4-2 → 4-3：总费用 {t42:.2f} → {t43:.2f} 万元（−{100*(1-t43/t42):.2f}%）；"
          f"紧急费 {e42:.2f} → {e43:.2f} 万元（−{100*(1-e43/e42):.2f}%）")

    keys = [(br, st) for br in BRANCHES for st in STRATS]
    plan = np.array([D[k]["plan"] for k in keys])
    d_plan = abs(plan[:3].mean() - plan[3:].mean())
    note = (
        "注：(a) 六个策略的实际费用拆为计划购电费（深蓝）＋调整费（紫）＋紧急购电费"
        "（红）三段，柱顶为全年合计。两支合同的计划费几乎相同（均值相差 "
        f"{d_plan:.0f} 万元），差异全部落在调整费与紧急购电费上。"
        "(b) 把增量费用（调整费＋紧急购电费）单独放大：不可调整合同约 70–74 万元，"
        "可滚动调整的只约 35 万元；同策略下 4-3 相对 4-2 的紧急购电费由 "
        f"{e42:.1f} 万元降至 {e43:.1f} 万元，降幅 −{100 * (1 - e43 / e42):.1f}%"
        "（即图中 4-3 组正上方的读数）。"
        "(c) 以「固定电价参考」为参照的节省率，与距「未来价格完全已知」理论下界的差距。"
        "4-2 为不可调整合同（提交后不得改量），4-3 为可滚动调整合同（每次只改未来 "
        "6 h）；两分支的策略定义、价格输入与风险口径完全一致。"
        f"同策略下 4-3 相对 4-2 省 {t42 - t43:.2f} 万元（−{100 * (1 - t43 / t42):.2f}%），"
        f"紧急购电费由 {e42:.2f} 万元降至 {e43:.2f} 万元（−{100 * (1 - e43 / e42):.1f}%）。"
        "「已知未来」是完全预知的理论上界，仅用于给出下界，不是可行方案；"
        "三个策略的价格输入都只用过去（预测策略用 d−7 / d−14 / d−21 的实际价）。"
        "数据：06_支撑材料/p4_strategies.csv（6 行真实求解输出，万元口径与 "
        "p4_strategy_fees.csv 逐行一致，只读引用）。"
    )

    fig = build(D)
    saved = S.save_figure(fig, STEM, caption=CAPTION, note=note)
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
