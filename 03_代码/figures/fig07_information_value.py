# -*- coding: utf-8 -*-
r"""
Fig.7  问题三：信息集合格——预测信息的价值是"边际"的，不是"谁更准"
================================================================================

核心结论（这张图要证明的一句话）
--------------------------------
滚动决策里可用的预报更新时刻有 6:00 / 12:00 / 18:00 三个，它们能组合出
8 个**信息集** S ⊆ {6,12,18}。滚动购电费用 J(S) 随 S 变大而单调下降。真正
有意义的量不是"哪个预报最准"，而是**在已有信息集下新增某条预报，费用降了
多少**：

    Δ(S → S∪{k}) = J(S∪{k}) − J(S)     （负值 = 省钱）

本图把 8 个信息集画成 **Boolean 格（Hasse 图）**，**每条覆盖边标出该项边际
价值**；右 panel 给出常用的总量口径 ΔJ(S) = J(∅) − J(S)。

证据链（两张 panel 各承担一个读数）
------------------------------------
(a) 格 —— 4 层：∅ → 单元素 → 双元素 → 全信息。12 条覆盖边各自标出边际价值。
(b) 总价值 —— 8 个信息集相对 ∅ 的累计节约 ΔJ(S)。它把"格"压成一维排序，
    给出"信息越多越省"的单调证据，以及全信息的价值上界。

两条可复算的读数（本图即为此二数而作）
--------------------------------------
1. **总信息价值** J(∅) − J({6,12,18}) = **1,559,182.68 元** = 155.9 万元。
2. **边际价值随"已掌握的信息"而衰减**：18:00 预报加进空集省 117.8 万元；
   若已掌握 {6,12}，再加它只省 46.2 万元。同一条预报，价值取决于上下文。

数据来源（真实，无编造）
------------------------
06_支撑材料/p3_analysis.json → "configs" 的 8 个条目，均为
03_代码/p3_microgrid.py + p3_backtest.py 在同一预测器、同一滚动规则下的
**真实滚动回放结果**（评价区间 2025-02-01 至 2025-12-31，334 天）。
本图只做读取与相减，**不重算任何模型**。

已知口径提醒
------------
"∅" 一栏在 json 中的键名是 ``对照：只用0:00预报``——它并非"没有任何预报"，
而是**只有 0:00 那一次全 24 点预报**（即首轮计划的净负荷预报），作为信息基线。
本图全部边际量都是相对该基线的差分。

排版约束（三次实测踩坑，勿再犯）
--------------------------------
1. 全部文字为普通 Unicode（∅、⊆、∪ 等），不使用 mathtext（含 `$...$` 的字符串
   会绕过 font.family 回退链，中文变豆腐块）。
2. **边线必须在节点框边界处截断**。若按节点**中心**连线，线端会落在节点文字
   的包围盒里，碰撞审计按几何判 `text-stroke`（节点框虽以更高 zorder 盖住了线，
   审计仍看得见线）。这里用矩形边界求交把两端各截去一段。
3. **边标签必须避让**。第一版一律放在边的中点，而 {6}→{6,18} 与 {12}→{6,12}
   的中点**完全重合**（{12}→{12,18} 与 {18}→{6,18} 亦然），标签互相压住、
   又被节点框压住，审计报 19 处 FAIL。现改为 `_place_labels()`：以节点框为
   障碍、按候选 (沿线位置 t, 法向侧, 偏移量) 贪心搜索最大净空位。
4. **比例尺要实测**，不能猜。点→数据单位的换算 `ppu` 由 `fig.canvas.draw()`
   之后的真实 axes 位置反算，否则标签框估歪、避让失效。

图内不出现文字（本版新增）
---------------------------
图内只留坐标轴标签/刻度标签/panel 字母/图例；除此之外只允许数字与符号
（节点费用、边上的 ΔJ、`0`、`117.8`）。格图左沿原先竖排的四行层级名
（空信息 / 单条预报 / 两条预报 / 三条全用）、`0（基线）` 与 `单条最好 117.8`
里的汉字全部移入 `NOTE`，由 figstyle 的 prose gate 拦截。腾出的左侧留白同时
把 XLO 从 -1.36 收到 -0.88，格体放大约 10%。

输出
----
04_图/pdf/fig07_information_value.pdf
04_图/pdf/fig07_information_value.svg
04_图/fig07_information_value.png
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figstyle as S  # noqa: E402

WAN = 1e4          # 元 → 万元

STEM = "fig07_information_value"

#: 正文图题（进入 LaTeX \caption{}，图内不再出现）
CAPTION = "预测信息的价值取决于已掌握的信息：边际价值递减，但始终为正"

#: json 中 8 个信息集的键名（"" = ∅）
KEY = {
    "": "对照：只用0:00预报",
    "6": "6:00",
    "12": "12:00",
    "18": "18:00",
    "6+12": "6:00+12:00",
    "6+18": "6:00+18:00",
    "12+18": "12:00+18:00",
    "6+12+18": "6:00+12:00+18:00",
}

#: 显示名（集合记号）
LBL = {"": "∅", "6": "{6}", "12": "{12}", "18": "{18}",
       "6+12": "{6,12}", "6+18": "{6,18}", "12+18": "{12,18}",
       "6+12+18": "{6,12,18}"}

RANK = {"": 0, "6": 1, "12": 1, "18": 1,
        "6+12": 2, "6+18": 2, "12+18": 2, "6+12+18": 3}

#: 层间距 1.3（不是 1.0）。层间距若等于 1.0，节点框（半高 0.26）之外只剩
#: 0.48 单位给边标签，而标签本身高 0.27 —— 6 个标签挤在同一个窄带里必然重叠
#: （第二版实测：4 个标签被压成 2 个重合框）。1.3 把可用带高提到 0.78。
RANK_Y = {0: 0.0, 1: 1.3, 2: 2.6, 3: 3.9}

#: 信息集 → 屏幕纵坐标（由层号查层高）
Y_OF = {k: RANK_Y[v] for k, v in RANK.items()}

#: Hasse 布局（经 36 种层内排序穷举，此序直线交叉数 = 2，为最小）
X_OF = {"": 1.20, "6": 0.00, "12": 1.20, "18": 2.40,
        "6+12": 0.00, "6+18": 1.20, "12+18": 2.40, "6+12+18": 1.20}

RANK_NAME = {0: "空信息", 1: "单条预报", 2: "两条预报", 3: "三条全用"}

# 数据范围只包住格本身：首版上下各挂了半行说明文字，故 YLO/YHI 留了 0.88/4.76。
# 说明文字已移入 caption/注，这里收紧到 ±0.45，格体在画布上的占比提高约三成。
# 左右同步收紧：XLO 原为 -1.36，其中约 0.5 个单位是留给格图左沿那四行层级名
# （空信息 / 单条预报 / …）的；名称移入注后把余量还给格体（ppux 提高约 10%）。
# 余量不能压到零——边标签按垂直方向外推最多 0.54 + 自身半宽约 0.23 个单位，
# 故左侧仍需 ≈0.8 个单位、右侧 ≈0.5 个单位的净空。
XLO, XHI = -0.88, 3.14
YLO, YHI = -0.45, 4.36

#: 节点配色：蓝的深浅 = 信息量（与 figstyle"蓝色家族 = 先验信息"一致）
#: 节点/柱配色：**同一色相（S.C_GRID，墨绿 = 日前计划/先验信息）由浅到深 = 信息量多少**。
#: 空信息集（rank 0）刻意**不入绿色家族**，改用中性暖灰的浅色档 —— 它不是"信息较少"，
#: 而是"没有信息"，用灰与用绿是两个不同的断言。三元组含义：(填色, 描边, 字色)。
#: 旧版这里是一条蓝色渐深阶（#E6EFF9 → #0F4D92），随主调改暖后全部重派生。
NODE_STYLE = {
    0: (S.tint(S.C_REF, 0.88), S.tint(S.C_REF, 0.40), S.C_ACTUAL),
    1: (S.tint(S.C_GRID, 0.74), S.tint(S.C_GRID, 0.34), S.C_ACTUAL),
    2: (S.tint(S.C_GRID, 0.44), S.tint(S.C_GRID, 0.12), S.C_ACTUAL),
    3: (S.C_GRID, S.C_GRID, "#FFFFFF"),
}
BAR_COLOR = {0: S.tint(S.C_REF, 0.82), 1: S.tint(S.C_GRID, 0.64),
             2: S.tint(S.C_GRID, 0.34), 3: S.C_GRID}
C_EDGE = S.tint(S.C_NEUTRAL, 0.45)
C_MARGIN = S.C_SAVE       # 边际价值（全部为节约方向）

FS_NODE = 6.3             # 节点两行字号
FS_EDGE = 6.1             # 边标签字号
PAD_BOX = 2.2             # 节点框内边距（pt，对应 boxstyle pad≈0.35×字号）
#: 边标签白底框内边距（pt，**每边**）。注意 `bbox=dict(pad=X)` 的 X 是「点」而
#: 不是字号倍数（实测：pad=0.51 每边只撑开 0.5 pt）。而 PDF 文本抽取用字体
#: ascent/descent 量出的行高比 matplotlib 的紧致框高约 2.1 pt，因此每边必须
#: ≥ 2.4 pt —— 首版沿用 pad=0.33（=0.33 pt）时 12 条边标签全部被判
#: text-fill-edge（文字戳出自己的白底框）。
PAD_LAB = 2.6
LINESP = 1.45             # 节点两行行距倍数


# ================================================================ 数据

def load_J() -> tuple[dict[str, float], dict[str, float]]:
    """读取 8 个信息集的全年合计购电费与紧急购电费（元）。"""
    path = S.SUP_DIR / "p3_analysis.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))["configs"]
    missing = [v for v in KEY.values() if v not in cfg]
    if missing:
        raise KeyError(f"p3_analysis.json 的 configs 缺少：{missing}")
    return ({k: float(cfg[v]["total"]) for k, v in KEY.items()},
            {k: float(cfg[v]["emg"]) for k, v in KEY.items()})


def covers(a: str, b: str) -> bool:
    """a ⊂ b 且 |b| = |a| + 1（Hasse 图的覆盖关系）。"""
    sa = set(a.split("+")) - {""}
    sb = set(b.split("+")) - {""}
    return len(sb) == len(sa) + 1 and sa <= sb


def check_monotone(J: dict[str, float]) -> None:
    """断言：加入信息永远不会变贵。若不成立说明数据或口径有问题。"""
    bad = [(a, b) for a in KEY for b in KEY if covers(a, b) and J[b] > J[a] + 1e-6]
    if bad:
        raise AssertionError(f"信息集费用非单调下降：{bad} —— 请核对 p3_analysis.json")


# ================================================================ 几何助手

def _em_width(text: str) -> float:
    """一行文字的相对宽度（em）。ASCII 记 0.58 em，CJK/全角记 1.0 em。"""
    return sum(1.0 if ord(c) > 0x2000 else 0.58 for c in text)


def _rect(cx: float, cy: float, w: float, h: float):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _gap(a, b) -> float:
    """两个轴对齐矩形之间的净空（负值 = 重叠深度）。"""
    dx = max(a[0] - b[2], b[0] - a[2])
    dy = max(a[1] - b[3], b[1] - a[3])
    if dx >= 0 and dy >= 0:
        return math.hypot(dx, dy)
    return max(dx, dy)


def _node_rect(k: str, J: dict[str, float], ppux: float, ppuy: float):
    """节点框（含内边距）的轴对齐包围盒，单位 = 面板 a 数据坐标。

    宽用 ppux、高用 ppuy —— 面板 a 的 x/y 刻度比例并不相等（横轴 4.40 单位配
    约 70 mm，纵轴 4.81 单位配约 55 mm），只用一个 ppu 会低估框高约 30%，
    边标签就会压到节点框上（实测 12 条 text-fill-edge 告警）。
    """
    w_pt = max(_em_width(LBL[k]), _em_width(f"{J[k] / WAN:,.1f}")) * FS_NODE
    w_pt += 2 * PAD_BOX
    h_pt = 2 * FS_NODE * LINESP + 2 * PAD_BOX
    return _rect(X_OF[k], Y_OF[k], w_pt / ppux, h_pt / ppuy)


def _trim(p, q, hp, hq):
    """把线段 p→q 的两端各截到所在矩形边界上（矩形以点为中心）。"""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L

    def step(hw, hh):
        sx = hw / abs(ux) if abs(ux) > 1e-9 else math.inf
        sy = hh / abs(uy) if abs(uy) > 1e-9 else math.inf
        return min(sx, sy) + 0.012          # 再多留一点缝

    sp, sq = step(*hp), step(*hq)
    a = (p[0] + ux * sp, p[1] + uy * sp)
    b = (q[0] - ux * sq, q[1] - uy * sq)
    return a, b


def _place_labels(ax, items, obstacles, ppux: float, ppuy: float) -> None:
    """为每条边找一个不与节点框/已放置标签相撞的位置（贪心 + 白底框兜底）。"""
    placed: list[tuple[float, float, float, float]] = []
    order = sorted(items, key=lambda it: -math.hypot(it[1][0] - it[0][0],
                                                     it[1][1] - it[0][1]))
    for p, q, text in order:
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        if ny < 0:
            nx, ny = -nx, -ny
        w = (_em_width(text) * FS_EDGE + 2 * PAD_LAB) / ppux
        h = (FS_EDGE * 1.25 + 2 * PAD_LAB) / ppuy
        best, best_score = (0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1])), -1e9
        for t in (0.28, 0.34, 0.40, 0.46, 0.52, 0.58, 0.64, 0.70):
            for side in (1.0, -1.0):
                for off in (0.22, 0.30, 0.38, 0.46, 0.54):
                    cx = p[0] + t * dx + side * nx * off
                    cy = p[1] + t * dy + side * ny * off
                    r = _rect(cx, cy, w, h)
                    score = min((_gap(r, o) for o in obstacles + placed),
                                default=9.9)
                    if score > best_score:
                        best, best_score = (cx, cy), score
        cx, cy = best
        # pad 单位为「点/每边」（不是字号倍数），与上面的 PAD_LAB 几何模型一致。
        ax.text(cx, cy, text, ha="center", va="center", fontsize=FS_EDGE,
                color=C_MARGIN, fontweight="bold", zorder=6,
                bbox=dict(facecolor="white", edgecolor="none", pad=PAD_LAB))
        placed.append(_rect(cx, cy, w, h))


# ================================================================ 画图

def build(J: dict[str, float], emg: dict[str, float]) -> plt.Figure:
    S.apply_style()

    fig = plt.figure(figsize=(S.mm2in(160), S.mm2in(84)), layout="constrained")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.00, 1.06], wspace=0.14)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_a.grid(False)
    ax_b.grid(False)

    J0 = J[""]                     # ∅ 的成本：所有"节约 ΔJ"的参照

    # ============================================================ (a) Boolean 格
    ax_a.set_xlim(XLO, XHI)
    ax_a.set_ylim(YLO, YHI)
    ax_a.axis("off")

    fig.canvas.draw()                       # 先把 constrained layout 定下来
    ax_pos = ax_a.get_position()            # axes 分数 box
    fw_in, fh_in = fig.get_size_inches()
    ppux = ax_pos.width * fw_in * 72 / (XHI - XLO)     # 点 / x 单位
    ppuy = ax_pos.height * fh_in * 72 / (YHI - YLO)    # 点 / y 单位（≠ ppux！）
    node_rect = {k: _node_rect(k, J, ppux, ppuy) for k in KEY}
    half = {k: ((node_rect[k][2] - node_rect[k][0]) / 2,
                (node_rect[k][3] - node_rect[k][1]) / 2) for k in KEY}

    items = []
    for a in KEY:
        for b in KEY:
            if not covers(a, b):
                continue
            p0, q0 = (X_OF[a], Y_OF[a]), (X_OF[b], Y_OF[b])
            p, q = _trim(p0, q0, half[a], half[b])      # 两端截到节点框边界
            ax_a.plot([p[0], q[0]], [p[1], q[1]], color=C_EDGE, lw=1.0,
                      solid_capstyle="round", zorder=1)
            items.append((p, q, f"{(J[b] - J[a]) / WAN:+.1f}"))
    _place_labels(ax_a, items, list(node_rect.values()), ppux, ppuy)

    for k in KEY:
        face, edge, txt = NODE_STYLE[RANK[k]]
        ax_a.text(X_OF[k], Y_OF[k], f"{LBL[k]}\n{J[k] / WAN:,.1f}",
                  ha="center", va="center", fontsize=FS_NODE, color=txt,
                  fontweight="bold", linespacing=LINESP, zorder=7,
                  bbox=dict(boxstyle="round,pad=0.35", facecolor=face,
                            edgecolor=edge, linewidth=0.9))

    # 四层的名称（空信息 / 单条预报 / 两条预报 / 三条全用）原先竖排在格图左沿，
    # 已按"图内不出现文字"移入图下注；信息量由节点配色由浅到深承担。
    S.add_panel_label(ax_a, "a", x=0.0, y=1.0, dx_pt=-12, dy_pt=1.0, va="bottom")

    # ============================================================ (b) 总价值排序
    order = sorted(KEY, key=lambda k: J0 - J[k])       # 升序：∅ … 全信息
    ys = list(range(len(order)))
    vals = [(J0 - J[k]) / WAN for k in order]
    vmax = max(vals)

    ax_b.barh(ys, vals, height=0.58,
              color=[BAR_COLOR[RANK[k]] for k in order],
              edgecolor="none", linewidth=0, zorder=3)
    ax_b.set_yticks(ys)
    ax_b.set_yticklabels([LBL[k] for k in order], fontsize=7.0)
    ax_b.set_ylim(-0.72, len(order) - 0.06)
    ax_b.set_xlim(0, vmax * 1.22)
    ax_b.set_xlabel("相对 ∅ 的全年节约 ΔJ = J(∅) − J(S)（万元）")

    # 数值写在柱内右端：柱外会与参考线抢位置（第一版 109.7 被参考线穿过）
    for y, k, v in zip(ys, order, vals):
        if v < 1e-9:
            ax_b.text(0.0, y - 0.44, "0", va="center", ha="left",
                      fontsize=6.0, color=S.C_NEUTRAL)   # ∅ 行＝基线，读数为 0
        else:
            ax_b.text(v - vmax * 0.015, y, f"{v:,.1f}", va="center",
                      ha="right", fontsize=6.3,
                      color="#FFFFFF" if RANK[k] == 3 else S.C_ACTUAL,
                      fontweight="bold", zorder=5)

    # "最好单条"参考线：说明多条信息 > 任何单条。数值放在顶部行间空白处——
    # 放到底部会被 x 轴脊线穿过（第一版实测 text-stroke）。原先写作
    # 「单条最好 117.8」，汉字已移入图下注，图内只留数值。
    best_single = max(J0 - J[k] for k in ("6", "12", "18")) / WAN
    ax_b.axvline(best_single, color=S.C_RISK, lw=0.9, ls="--", zorder=2)
    ax_b.text(best_single - vmax * 0.012, len(order) - 0.36,
              f"{best_single:,.1f}", ha="right", va="center",
              fontsize=6.0, color=S.C_RISK)

    S.add_panel_label(ax_b, "b", x=0.0, y=1.0, dx_pt=-12, dy_pt=1.0, va="bottom")

    # 画布已无顶部标题带与底部注脚带，axes 吃满可用高度。
    fig.get_layout_engine().set(rect=(0.008, 0.024, 0.986, 0.936))
    return fig


def main() -> None:
    S.apply_style()
    J, emg = load_J()
    check_monotone(J)
    print("8 个信息集全年合计购电费（元）:")
    for k in KEY:
        print(f"  {LBL[k]:10s} {J[k]:16,.2f}   emg={emg[k]:14,.2f}")
    J0, Jfull = J[""], J["6+12+18"]
    total_value = J0 - Jfull
    best_single = max(J0 - J[k] for k in ("6", "12", "18"))
    n_edge = 12
    note = (
        "注：信息集 S ⊆ {6,12,18} 表示滚动决策中可用的预报更新时刻，∅ 为只用 0:00 "
        "那条 24 点预报的基线。(a) 节点框内第二行为该信息集的全年合计购电费（万元），"
        "边上数字为新增该条预报后的费用变化（万元，负号 = 省钱）。(b) 横轴为相对 ∅ 的"
        f"全年节约 ΔJ。{n_edge} 条覆盖边的边际量全部为负（加信息永不更贵），"
        f"合计恰为 −{total_value / WAN:,.1f} 万元，即总信息价值 "
        f"J(∅) − J(全) = {total_value:,.2f} 元；任何单条预报最多省 "
        f"{best_single / WAN:,.1f} 万元，故多条信息优于任何一条（图中虚线即该水平，"
        "虚线上方的读数就是该数值）。格图自上而下四层依次为「"
        + " / ".join(RANK_NAME[r] for r in range(4))
        + "」，节点颜色由浅到深对应该层级。"
        "数据：06_支撑材料/p3_analysis.json 的 configs"
        "（334 天滚动回放，只读引用，未重算模型）。"
    )

    print(f"总信息价值 J(∅) − J(全) = {total_value:,.2f} 元 = {total_value / WAN:,.1f} 万元")

    fig = build(J, emg)
    saved = S.save_figure(fig, STEM, caption=CAPTION, note=note)
    for p in saved:
        print("已输出：", p.relative_to(S.ROOT))


if __name__ == "__main__":
    main()
