# -*- coding: utf-8 -*-
r"""
Fig.1  全文统一建模框架与四问递进关系
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
问题一至问题四不是四个彼此独立的模型，而是**同一个"预测—风险修正—优化—
实时执行—状态回传"闭环模型逐层叠加信息与不确定性处理能力**的结果：
P1 只有确定性单日优化；P2 补上预测、风险分位数与实时执行；P3 再补上
6/12/18 时滚动调整与交付块；P4 再补上动态电价预测与价格加权风险分位数。

证据链（每个元素回答什么）
--------------------------
上块·左栏  流程链：模型实际做什么，以及"跨日/日内"两条回传回路如何闭合
上块·右栏  归属网格：**哪一问引入了哪个环节**——"逐层扩展"的直接证据
下块       目标函数阶梯：每一问在数学上新增了什么，条带随问题序号变长

数据来源
--------
**纯概念图，不使用任何数据，不编造任何数值。**
环节归属来自论文正文与代码：
  * P1 无预测/无风险/无紧急购电：03_代码/p1_microgrid.py（附件1 直接给定电价、
    负载与光伏预测功率，求解单日 LP/MILP）
  * P2 三层滚动（预测层→计划层→执行层）：03_代码/p2_microgrid.py
  * P3 发布时刻为 6/12/18 时——**是发布时刻，不是提前小时数**，每次发布整条
    24 点曲线，仅正式提交当前 6 h 交付块，g⁰ 永久冻结：
    03_代码/p3_rolling_microgrid.py
  * P4 在既有链上**插入**电价预测与价格加权分位数，并区分决策价与结算价：
    03_代码/p4_microgrid.py

排版约束（改图前必读）
----------------------
1. 含 `$...$` 的字符串会被整串交给 mathtext 渲染，而 mathtext **不走**
   font.family 回退链，中文会静默变成 dummy symbol。故中文与数学式必须是
   **两个独立的 text 对象**，任何一行都不得混写。
2. 字距按 160 mm 物理宽度折算：1 个 x 单位 = 1.6 mm，7.5 pt 汉字宽约 2.65 mm
   ≈ 1.66 个 x 单位。排文本前先算宽度，不要靠目测。

输出
----
04_图/pdf/fig01_framework.pdf （矢量，LaTeX 引用）
04_图/fig01_framework.png     （300 dpi 预览）
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

# ================================================================ 版式常量
# 画布坐标 x ∈ [0,100] 映射到 160 mm，故 1 单位 = 1.6 mm。

X_STAGE_L, X_STAGE_R = 8.0, 44.0      # 流程框横向范围（36 单位 = 58 mm）
X_GRID0, DX_COL = 55.5, 11.2          # 归属网格首列中心与列距
X_GRID_R = X_GRID0 + 3 * DX_COL       # 末列中心

Y_HDR1, Y_HDR2 = 88.5, 85.0           # 列头两行（第三行为 Y_HDR2-2.7）
Y_ROW0, DY_ROW = 79.0, 4.0            # 首行中心与行距
Y_BLOCK2 = 35.5                       # 下块标题
Y_LAD0, DY_LAD = 26.5, 6.8            # 下块首行中心与行距

#: 画布纵向**可视**范围。内容实际落在 y ∈ [3.62, 89.44]（把每个 ax.text 的
#: window_extent 用 transData 反算得到，非目测），故上下各留约 1 个单位余量。
#: 原先沿用 0–100 会在顶部留下 17 mm 空白——那是删掉大标题后残留的版面余量。
#: 画布高度按同一比例缩小，**1 个 y 单位仍等于 1.62 mm**，因此所有文字与图元的
#: 物理尺寸完全不变，被剪掉的只有空白。
Y_VIEW_LO, Y_VIEW_HI = 2.42, 90.94
FIG_H_MM = 162.0 * (Y_VIEW_HI - Y_VIEW_LO) / 100.0

DOT_MS = 5.0
BOX_HH = 1.65                         # 流程框半高
# 框内文字与框边必须留出余量：PyMuPDF 报出的文字框含字体 ascent/descent，
# 比可见字形高，贴边会被碰撞审计判为 text-stroke。
BOX_PAD_X = 2.0                       # 框内左右留白（x 单位）

# ================================================================ 内容定义

#: 四个问题（列）：(标签, 描述第一行, 描述第二行)
PROBLEMS = [
    ("问题一", "确定性单日", "MILP"),
    ("问题二", "预测·风险·实时", "三层滚动"),
    ("问题三", "滚动调整", "多版本预报"),
    ("问题四", "动态电价预测", "两个分支"),
]

#: 流程链各环节：(名称, 归属掩码, 语义色, 右侧短语)
#: 归属掩码 [P1, P2, P3, P4]，1 = 该问具备此环节。
STAGES = [
    ("输入数据（电价 / 负载 / 光伏）", [1, 1, 1, 1], S.C_NEUTRAL, "附件1"),
    ("负荷与光伏预测", [0, 1, 1, 1], S.C_FORECAST, "历史外推"),
    ("电价预测", [0, 0, 0, 1], S.C_PRICE, "仅 P4"),
    ("预测误差与不确定性分析", [0, 1, 1, 1], S.C_FORECAST, "经验分布"),
    ("风险修正（分位数余量）", [0, 1, 1, 1], S.C_RISK, "Qα"),
    ("日前优化（冻结初始计划）", [1, 1, 1, 1], S.C_GRID, "0:00"),
    ("滚动调整", [0, 0, 1, 1], S.C_GRID, "6/12/18 时"),
    ("实时执行（观测实际值）", [0, 1, 1, 1], S.C_ACTUAL, "因果规则"),
    ("储能充放电 / 弃光", [1, 1, 1, 1], S.C_CHARGE, "储备线 R"),
    ("紧急购电", [0, 1, 1, 1], S.C_EMERGENCY, "5 倍电价"),
    ("储能状态更新", [0, 1, 1, 1], S.C_SOC, "回传次日"),
]

#: 下块目标函数阶梯：(问题标签, 累计目标式(纯 mathtext), 本问新增说明(纯中文),
#:                   条带长度(x 单位), 语义色)
#: 说明文字排在条带右端之后，故**必须短**：条带 49 + 起点 13.5 + 文字 ≈ ≤ 97 单位，
#: 12 个汉字（约 17 单位）已是上限。
LADDER = [
    ("问题一", r"$\min\ \sum_t p_t\,g_t$",
     "确定性单日调度", 16.0, S.C_GRID),
    ("问题二", r"$\min\ \sum_t p_t\,g_{n,t}+\lambda\,\xi_n$",
     "风险分位数与风险净负荷", 27.0, S.C_RISK),
    ("问题三", r"$+\ 1.5p\,u_t-0.5p\,v_t+5p\,\bar r_t$",
     "滚动调整费与紧急费", 38.0, S.C_GRID),
    ("问题四", r"$p\to\widehat p^{(\tau)},\qquad Q_{\alpha}\to Q^{P}$",
     "电价预测与价格加权分位数", 49.0, S.C_PRICE),
]


def _rounded(ax, x0, y0, x1, y1, **kw):
    """圆角矩形补丁。"""
    kw.setdefault("facecolor", "white")
    kw.setdefault("edgecolor", "#C8C8C8")
    kw.setdefault("linewidth", 0.7)
    kw.setdefault("zorder", 2)
    ax.add_patch(FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0,rounding_size=1.2", **kw))


def _arrow(ax, p0, p1, *, color="#B0B0B0", lw=0.85, style="-|>",
           zorder=1, ms=6.0, rad=0.0):
    """带箭头连线。"""
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=ms, color=color, lw=lw,
        zorder=zorder, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))


def build() -> plt.Figure:
    """绘制 Fig.1。单幅画布、无坐标轴（对齐门判定为 NOT APPLICABLE）。"""
    S.apply_style()

    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(FIG_H_MM)))
    ax = fig.add_axes((0.006, 0.006, 0.988, 0.988))
    ax.set_xlim(0, 100)
    ax.set_ylim(Y_VIEW_LO, Y_VIEW_HI)
    ax.axis("off")

    # ============================================================ 上块：标题
    # 大标题与副标题不进图：放在正文的 \caption 里（全篇插图规范）。

    # ============================================================ 上块：列头
    for j, (tag, d1, d2) in enumerate(PROBLEMS):
        xc = X_GRID0 + j * DX_COL
        ax.text(xc, Y_HDR1, tag, fontsize=S.FS_PANEL, fontweight="bold",
                color="#1A1A1A", ha="center", va="center")
        ax.text(xc, Y_HDR2, d1, fontsize=6.5, color="#5A5A5A",
                ha="center", va="center")
        ax.text(xc, Y_HDR2 - 2.7, d2, fontsize=6.2, color="#9A9A9A",
                ha="center", va="center")

    # ============================================================ 上块：流程 + 网格
    for i, (name, mask, color, note) in enumerate(STAGES):
        yc = Y_ROW0 - i * DY_ROW
        introduced = bool(mask[0])

        _rounded(ax, X_STAGE_L, yc - BOX_HH, X_STAGE_R, yc + BOX_HH,
                 edgecolor=color if introduced else "#B3AAA0",
                 linewidth=1.0 if introduced else 0.65)

        ax.text(X_STAGE_L + BOX_PAD_X, yc, name, fontsize=7.2,
                color="#1F1F1F", fontweight="bold" if introduced else "normal",
                ha="left", va="center")
        ax.text(X_STAGE_R - BOX_PAD_X, yc, note, fontsize=5.9,
                color="#909090", ha="right", va="center")

        for j, has in enumerate(mask):
            xc = X_GRID0 + j * DX_COL
            if has:
                ax.plot(xc, yc, marker="o", ms=DOT_MS, color=color,
                        markeredgecolor="white", markeredgewidth=0.55, zorder=4)
            else:
                ax.plot(xc, yc, marker="o", ms=DOT_MS * 0.78, color="none",
                        markeredgecolor="#D4D4D4", markeredgewidth=0.65, zorder=3)

        if i < len(STAGES) - 1:
            ax.plot([X_STAGE_L, X_GRID_R + DX_COL / 2 - 1.5],
                    [yc - DY_ROW / 2] * 2, color="#F0F0F0", lw=0.6, zorder=0)

    # 竖向分隔：归属网格左右边界
    y_top_edge = Y_ROW0 + BOX_HH
    y_bot_edge = Y_ROW0 - (len(STAGES) - 1) * DY_ROW - BOX_HH
    for xv in (X_GRID0 - DX_COL / 2, X_GRID_R + DX_COL / 2):
        ax.plot([xv, xv], [y_bot_edge - 0.6, y_top_edge + 0.6],
                color="#E4E4E4", lw=0.7, zorder=0)

    # ============================================================ 流程主箭头
    for i in range(len(STAGES) - 1):
        _arrow(ax, (X_STAGE_L + 5.0, Y_ROW0 - i * DY_ROW - BOX_HH),
               (X_STAGE_L + 5.0, Y_ROW0 - (i + 1) * DY_ROW + BOX_HH), ms=5.2)

    # ============================================================ 两条回路
    y_state = Y_ROW0 - 10 * DY_ROW          # 储能状态更新
    y_pred = Y_ROW0 - 1 * DY_ROW            # 负荷与光伏预测
    y_exec = Y_ROW0 - 7 * DY_ROW            # 实时执行
    y_roll = Y_ROW0 - 6 * DY_ROW            # 滚动调整
    x_loop = 3.6

    _arrow(ax, (X_STAGE_L, y_state), (x_loop, y_state), color=S.C_SOC, lw=1.0, ms=5.2)
    _arrow(ax, (x_loop, y_state), (x_loop, y_pred), color=S.C_SOC, lw=1.0,
           style="-", ms=5.2)
    _arrow(ax, (x_loop, y_pred), (X_STAGE_L, y_pred), color=S.C_SOC, lw=1.0, ms=5.2)
    ax.text(x_loop - 1.0, (y_state + y_pred) / 2, "跨日滚动", fontsize=6.2,
            color=S.C_SOC, rotation=90, ha="center", va="center",
            fontweight="bold")

    # 日内回路不另画箭头：滚动调整与实时执行是相邻行，行间距（0.7 单位 ≈ 1.1 mm）
    # 容不下任何可见回路或标签，硬画只会压住框内文字。二者的先后关系由主流程
    # 竖箭头表达，滚动的时间点在"滚动调整"框右侧以 "6/12/18 时" 直接标注。

    # ============================================================ 下块：目标阶梯
    ax.text(3.0, Y_BLOCK2 - 1.0, "目标函数逐层新增的项", fontsize=8.6,
            fontweight="bold", color="#1A1A1A", ha="left", va="center")

    for i, (tag, expr, note, bar_len, color) in enumerate(LADDER):
        yc = Y_LAD0 - i * DY_LAD

        ax.text(3.0, yc + 0.5, tag, fontsize=8.2, fontweight="bold",
                color=color, ha="left", va="center")

        # 累计目标式（mathtext 的上下标使文字框比可见字形高，须与上行留足间距）
        ax.text(13.5, yc + 1.5, expr, fontsize=7.6, color="#1F1F1F",
                ha="left", va="center")

        # 增长条带：长度体现"逐层扩展"
        x0, x1 = 13.5, 13.5 + bar_len
        ax.add_patch(FancyBboxPatch(
            (x0, yc - 2.2), bar_len, 0.8,
            boxstyle="round,pad=0,rounding_size=0.4",
            facecolor=color, edgecolor="none", alpha=0.85, zorder=3))

        # 本问新增说明（与条带同高，排在条带右端之后）
        ax.text(x1 + 1.6, yc - 1.8, "新增：" + note, fontsize=6.4,
                color=color, ha="left", va="center")

    # ============================================================ 图注
    # 圆点含义与回路说明不进图：放在正文的「注」里。

    return fig


def main() -> None:
    fig = build()
    saved = S.save_figure(fig, "fig01_framework")
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
