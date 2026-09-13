# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题四 —— 由求解结果直接生成论文表格片段。

写出 05_论文/CUMCMThesis/p4_tables.tex（正文用）与 p4_tables_appendix.tex
（附录用），由 main.tex 以 \input 引入，使论文中每个数字都与
result4-2/result4-3/p4_results.json 严格同源，避免手工转录错误。

正文只有 30 页额度，问题四能占的篇幅有限，因此按"哪些数字是回答题目所必需"
来分：题目明确要求两个交付文件，故两个分支的费用汇总表与策略对照表留在正文；
价格预测的选型过程、风险口径的对照、八种预报组合与校验明细属于论据，放附录；
计费口径的敏感性另写 p4_tables_refund.tex，由 main.tex 在附录单独 \input：
主口径取题面字面读法的退款（被取消部分按 50% 违约电价计），"不退款、只追加"
作为独立敏感性并列报告。

运行：python3 03_代码/p4_tables.py --split  （需先运行 p4_microgrid.py）
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "06_支撑材料"
THESIS = ROOT / "05_论文" / "CUMCMThesis"
OUT_TEX = THESIS / "p4_tables.tex"
OUT_TEX_TAIL = THESIS / "p4_tables_appendix.tex"
OUT_TEX_REFUND = THESIS / "p4_tables_refund.tex"
OUT_TEX_COMBO = THESIS / "p4_combo_detail.tex"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
DISP = {"2025-03-20": "2025.3.20", "2025-06-21": "2025.6.21",
        "2025-09-23": "2025.9.23", "2025-12-21": "2025.12.21"}


def fmt(v: float, nd: int = 2) -> str:
    return f"{v:,.{nd}f}"


def sci(v: float) -> str:
    return "0.00" if abs(v) < 1e-9 else f"{v:.2e}"


def texlab(s: str) -> str:
    return s.replace(":", "{:}")


def pct(v: float, nd: int = 1) -> str:
    """百分数。LaTeX 里 `%` 是注释符，直接写 `41.7%` 会把该行后面的
    `&` 和 `\\\\` 一起注释掉，表格随即报 "Extra alignment tab"，
    所以这里必须输出 `\\%`。"""
    return f"{v * 100:.{nd}f}\\%"


def signed(pct: float) -> str:
    return f"{pct:+.2f}\\%".replace("+-", "-")


def signed_pct(v: float, nd: int = 2) -> str:
    """带正负号的百分数（同样要转义 `%`）。"""
    return f"{v * 100:+.{nd}f}\\%".replace("+-", "-")


def has(res: dict, key: str) -> bool:
    return key in res


# ---------------------------------------------------------------- 表：价格结构
def tab_price_struct(res: dict) -> str:
    """表：附件 4 的价格分解 P = 附件 1 曲线 + 星期偏移，及预测器选型。"""
    ps = res["价格结构"]
    wd = ps["断言3_残差星期均值_元每kWh"]
    order = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{附件 4 实时电价的结构分解（$P=F+R$，$F$ 为附件 1 的固定"
        r"曲线，$R$ 为残差）}",
        r"  \label{tab:p4-struct}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    项目 & 数值 & 说明 \\",
        r"    \midrule",
        f"    逐年逐段均值 $\\overline{{P}}$ 与 $F$ 的最大偏差"
        f" & ${sci(ps['断言1_附件4逐段均值与附件1最大偏差'])}$"
        r" & 两者\textbf{骨架与水平相同} \\",
        f"    $F$ 的年平均 & {fmt(ps['断言1_年平均值_附件1'], 4)}"
        r" & 元/kWh \\",
        f"    $\\overline{{P}}$ 的年平均 & {fmt(ps['断言1_年平均值_附件4'], 4)}"
        # 年均值之差只有 ~4e-7；$10^{-5}$ 是逐段均值最大偏差的量级，两者不是
        # 同一个量，写混会与正文"相差不足 $10^{-6}$"自相矛盾。
        r" & 元/kWh，与 $F$ 相差不足 $10^{-6}$ \\",
        f"    $R$ 与 $F$ 的相关系数 & ${ps['断言2_残差与固定曲线相关']:+.4f}$"
        r" & 正交，故 $R$ 就是``波动''本身 \\",
        r"    \midrule",
    ]
    for w in order:
        lines.append(f"    $R$ 的{w}均值 & {wd[w]:+.4f} & 元/kWh \\\\")
    lines += [
        r"    \midrule",
        f"    周五、周六平均 & {ps['断言3_周五六均值']:+.4f}"
        r" & 元/kWh，\textbf{偏低} \\",
        f"    其余五天平均 & {ps['断言3_其余五天均值']:+.4f}"
        r" & 元/kWh \\",
        f"    两者之差 & {ps['断言3_两水平差_元每kWh']:+.4f}"
        f" & 元/kWh，相当于均价的 {pct(ps['断言3_相对均价'], 1)} \\\\",
        f"    星期结构解释的 $R$ 方差 & {pct(ps['断言4_星期效应解释比例'], 1)}"
        r" & 其余为无规律的日内噪声 \\",
        f"    ``同星期加权''恒等式最大残差"
        f" & ${sci(ps['断言2_同星期加权恒等式最大残差'])}$"
        r" & 见式~\eqref{eq:p4-price} \\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：附件 4 的电价并非与附件 1 无关的另一条曲线，而是\textbf{在附件 1"
        r"的 144 段骨架上叠加了一个以星期为周期、均值为零的偏移}。这一条决定了"
        r"后文对照实验的读法：两者年平均值相同，因此任何费用差异都来自\textbf{波动"
        r"本身}，不掺杂价格水平的变化。周五、周六电价系统性偏低，是残差里唯一"
        r"可利用的规律，也正是同星期加权预测器的依据。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：预测器选型
def tab_select(res: dict) -> str:
    """表：预测器超参数在 1 月预热期上的选型，及子窗口稳健性复核。

    这张表存在的唯一理由是回应"参数是不是在评价区间上挑的"：它把选型窗口、
    候选对照与子窗口复核一并摊开，读者可以自行判断选型是否可复现。
    """
    sel = res.get("预测器选型")
    if not sel or "候选" not in sel:
        return ("% 选型表需要预热期选型的结果文件，"
                "请先运行：python3 03_代码/p4_microgrid.py --report-only\n")
    cand = sel["候选"]
    robust = sel.get("稳健性", [])
    # 稳健性条目里既有三个候选子窗口、也有一条 β 重扫。候选子窗口的第一条就是
    # 全窗口本身，与第一列重复，故丢掉；β 重扫的结果在 tab_beta 里另有表，
    # 这里也不列。
    cols = [r for r in robust
            if r["最优预测器"] != "（β 逐时刻）"
            and not r["子窗口"].startswith("全窗口")]
    names = [r["预测器"] for r in cand]
    lookup = [{c["预测器"]: c["平均绝对误差_元每kWh"] for c in r["前三"]}
              for r in cols]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{预测器选型：在 2025 年 1 月预热期（评价区间之外）比较候选，"
        r"并在子窗口上复核}",
        r"  \label{tab:p4-select}",
        r"  \footnotesize",
        r"  \begin{tabular}{l" + "r" * (1 + len(cols)) + r"}",
        r"    \toprule",
        r"    候选预测器 & 全窗口（30 天）"
        + "".join(f" & {r['子窗口'].split('（')[0]}（{r['天数']} 天）"
                  for r in cols) + r" \\",
        r"    \midrule",
    ]
    for i, nm in enumerate(names):
        cell = [f"{cand[i]['平均绝对误差_元每kWh']:.4f}"]
        for lk in lookup:
            v = lk.get(nm)
            cell.append("---" if v is None else f"{v:.4f}")
        # 加粗只标全窗口第一名，避免给读者"选型用了多个窗口"的错觉。
        if i == 0:
            cell[0] = rf"\textbf{{{cell[0]}}}"
            nm = rf"\textbf{{{nm}}}"
        lines.append(f"    {nm} & " + " & ".join(cell) + r" \\")
    betas = sel.get("β最优", {})
    lines += [
        r"    \midrule",
        r"    \multicolumn{" + str(2 + len(cols))
        + r"}{l}{\textit{选中的一组：权重 "
        + "/".join(f"{w:g}" for w in sel["选中权重"])
        + r"，}\ $\beta=(" + r",\,".join(
            f"{betas.get(h, '---'):g}" if isinstance(betas.get(h), (int, float))
            else "---" for h in ("6", "12", "18")) + r")$} \\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.95\textwidth}\footnotesize",
        r"    注：单位为元/kWh，为各候选对全天 $144$ 段的平均绝对误差。``全窗口''"
        r"即第 $1$--$30$ 天；``后段''只含滞后 $7/14/21$ 天样本齐备的日子（第 "
        r"$22$--$30$ 天），用于排除早期滞后退化对排序的影响；``后半''为第 "
        r"$15$--$30$ 天。三个窗口的第一名一致，故选型结果冻结后不再改动。"
        r"$\beta$ 逐发布时刻单独选，取值见上表最后一行。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：候选复核
def tab_forecast(res: dict) -> str:
    """表：评价区间上的候选复核（样本外，不参与选型）。"""
    cand = res["价格预测候选"]
    frozen_w = res.get("预测器选型", {}).get("选中权重")
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{价格预测候选方案在 2025 年 2 月 1 日--12 月 31 日的平均"
        r"绝对误差（\textbf{样本外复核}，不用于选型）}",
        r"  \label{tab:p4-forecast}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    预测方案 & 平均绝对误差/(元/kWh) & 相对均价 \\",
        r"    \midrule",
    ]
    for r in cand:
        name = r["预测器"]
        # 加粗的是"本文冻结使用的那一个"，不是"本区间上最好的那一个"。
        # 两者不同正是这张表想说明的事：按评价区间挑会挑到 0.6/0.3/0.1。
        frozen = bool(frozen_w) and name.split("(")[0].strip().endswith(
            "/".join(f"{w:g}" for w in frozen_w))
        nm = rf"\textbf{{{name}（本文冻结使用）}}" if frozen else name
        lines.append(f"    {nm} & {r['平均绝对误差_元每kWh']:.4f}"
                     f" & {pct(r['相对均价'], 2)} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：``相对均价''以\textbf{评价区间（334 天）的均价} $0.7575$~元/kWh"
        r"为基准，而非全年均价 $0.7662$~元/kWh。``全样本固定日内形状''使用了评价"
        r"区间本身的均值，含未来信息，只是作为误差下界列出，不是可用策略。``近 "
        r"$N$ 天滚动均值''系列表现不佳，原因见正文：把不同星期几混在一起平均，"
        r"恰好抹掉了电价里唯一可利用的星期偏移。\textbf{本表若作选型依据，第一名"
        r"会是 $0.6/0.3/0.1$（$0.0441$）；本文冻结使用的 $0.5/0.3/0.2$ 是 "
        r"$0.0446$，差 $0.0005$ 元/kWh——这点差异就是``在评价区间上选参''能换来的"
        r"虚高精度，本文刻意不取。}",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：β 扫描
def tab_beta(res: dict) -> str:
    """表：日内修正系数 β 在评价区间上的扫描（样本外，不参与选型）。"""
    beta = res["β扫描"]
    sel = res.get("预测器选型", {})
    frozen = sel.get("β最优", {})
    keys = ["6点版本_元每kWh", "12点版本_元每kWh", "18点版本_元每kWh"]
    heads = ["6:00 版", "12:00 版", "18:00 版"]
    fz = [frozen.get("6"), frozen.get("12"), frozen.get("18")]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{日内对数偏差修正系数 $\beta$ 的扫描（对剩余时段的平均绝对"
        r"误差，评价区间）}",
        r"  \label{tab:p4-beta}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrr}",
        r"    \toprule",
        r"    $\beta$ & " + " & ".join(heads) + r" \\",
        r"    \midrule",
    ]
    for r in beta:
        b = r["β"]
        cells = []
        for k, f in zip(keys, fz):
            v = r[k]
            # 加粗"本文冻结使用的 β"那一行，而不是"本区间最优"那一行。
            cells.append(rf"\textbf{{{v:.4f}}}" if f is not None
                         and abs(b - f) < 1e-9 else f"{v:.4f}")
        lines.append(f"    {b:g} & " + " & ".join(cells) + r" \\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：$\beta=0$ 即不做日内修正。本表是\textbf{样本外复核}：加粗行是"
        r"在 $1$ 月预热期上选出的冻结值 $\beta=(" + r",\,".join(
            f"{v:g}" if isinstance(v, (int, float)) else "---" for v in fz)
        + r")$，\textbf{不是}本区间的最优行——按本区间挑会指向 $\beta=0.5$。"
        r"$\beta$ 在评价区间上更``好看''只是区间自身的偏好，本文不据此改动参数。"
        r"$\beta\ge1.25$ 时把已实现的偏差过度外推，误差反而回升。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：预测精度
def tab_skill4(res: dict) -> str:
    """表：四个发布版本的预测精度（含共同时段可比口径）。"""
    sk = res["价格预测精度"]
    keys = ["0点版本", "6点版本", "12点版本", "18点版本"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{价格预测的四个发布版本在各自动态时刻更新后的精度}"
        r"（框架 6.3 节）",
        r"  \label{tab:p4-skill}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrr}",
        r"    \toprule",
        r"    发布版本 & 覆盖时段 & 平均绝对误差 & 相对均价 & 共同时段误差 \\",
        r"    \midrule",
    ]
    spans = {"0点版本": "0--144", "6点版本": "36--144",
             "12点版本": "72--144", "18点版本": "108--144"}
    best = min(keys, key=lambda k: sk[k]["共同时段平均绝对误差_元每kWh"])
    for k in keys:
        v = sk[k]
        s = f"{v['共同时段平均绝对误差_元每kWh']:.4f}"
        if k == best:
            s = rf"\textbf{{{s}}}"
        lines.append(f"    {k} & {spans[k]} & {v['平均绝对误差_元每kWh']:.4f}"
                     f" & {pct(v['相对均价'], 2)} & {s} \\\\")
    flat = sk["对照_全天均价"]
    lines += [
        r"    \midrule",
        f"    对照：全天用同一个均价 & 全天 & {flat['平均绝对误差_元每kWh']:.4f}"
        f" & {pct(flat['相对均价'], 2)} & --- \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：``覆盖时段''是时段索引范围，第 $h$ 个版本只能修正它发布之后的"
        r"时段，因此四个版本的``平均绝对误差''覆盖的时段\textbf{互不相同}"
        r"（$0{:}00$ 版覆盖全天 $144$ 段，$18{:}00$ 版只覆盖最后 $36$ 段），"
        r"\textbf{直接比大小是错的}。最后一列把四个版本都限制在 $18{:}00$--$24{:}00$"
        r"（四个版本都覆盖该段）上求平均绝对误差，才是可比的版本间排序；加粗者为"
        r"其中的最优。最后一行的``全天用同一个均价''是没有任何日内形状信息的"
        r"预测，它的误差远大于四个版本，说明形状信息确有价值。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：风险口径
def tab_risk(res: dict) -> str:
    """表：价格加权分位数与普通分位数的对照，以及残差—价格的协方差检查。"""
    rw = res["风险_加权对照"]
    c = res["风险_价格协方差"]
    # 「等权·下确界」与「纯加权相对抬升」是分位数定义修正后新增的两列。旧的结果
    # 文件里没有，硬取会 KeyError；这里给出可执行的提示而不是让生成器崩掉。
    if rw and "等权下确界均值_kWh" not in rw[0]:
        return ("% 风险余量对照表需要分位数定义修正后的结果文件，"
                "请先运行：python3 03_代码/p4_microgrid.py --report-only\n")
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{风险余量口径对照：以实际电价为权重的分位数 vs 等权分位数"
        r"（正式区间按每 7 天抽样求均值）}",
        r"  \label{tab:p4-risk}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrr}",
        r"    \toprule",
        r"    $\alpha$ & 价格加权/(kWh) & 等权·线性/(kWh) & 等权·下确界/(kWh)"
        r" & 比线性插值 & 比下确界 \\",
        r"    \midrule",
    ]
    for r in rw:
        # JSON 里 α=0.50 的相对抬升是 NaN（分母为负，比值无意义）。读到 NaN 时
        # 必须写成 ``---''——直接格式化会印出 ``+nan\%''，那不是"无意义"的写法，
        # 而像是一个算错的数。
        v = r["相对抬升"]
        rel = "---" if v is None or not math.isfinite(v) else signed_pct(v)
        q = r.get("纯加权相对抬升")
        relq = "---" if q is None or not math.isfinite(q) else signed_pct(q)
        lines.append(f"    {r['α']:.2f} & {r['价格加权均值_kWh']:.3f}"
                     f" & {r['普通分位数均值_kWh']:.3f}"
                     f" & {r['等权下确界均值_kWh']:.3f}"
                     f" & {rel} & {relq} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：``等权·线性''沿用问题二的做法，取 \texttt{numpy} 默认的线性插值"
        r"分位数；``等权·下确界''与``价格加权''同取下确界定义，故末列是"
        r"\textbf{纯粹的加权效应}，而倒数第二列还混入了取值约定之差。"
        r"$\alpha=0.50$ 处的余量为负，因为净负荷预测误差的中位数本身略小于零"
        r"（日间预测略偏高），此时``相对抬升''无意义，故以 ``---'' 表示。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{净负荷预测误差 $\varepsilon$ 与实际电价的协方差检查"
        r"（框架 3.2 节）}",
        r"  \label{tab:p4-cov}",
        r"  \footnotesize",
        r"  \begin{tabular}{lr}",
        r"    \toprule",
        r"    项目 & 数值 \\",
        r"    \midrule",
        f"    样本数 & {int(c['样本数']):,} \\\\".replace(",", r"\,"),
        f"    合并口径相关系数 & ${c['合并相关系数']:+.4f}$ \\\\",
        f"    逐时段相关系数均值 & ${c['逐时段相关系数均值']:+.3f}$ \\\\",
        f"    逐时段相关系数范围 & "
        f"${c['逐时段相关系数最小']:+.3f}$~${c['逐时段相关系数最大']:+.3f}$ \\\\",
        f"    逐时段相关为正的比例 & {pct(c['逐时段相关为正的比例'], 1)} \\\\",
        r"    \midrule",
        f"    电价最高 20\\% 时段的 $\\varepsilon$ 均值"
        f" & ${c['高价20%_误差均值_kW']:+.1f}$~kW \\\\",
        f"    电价最低 20\\% 时段的 $\\varepsilon$ 均值"
        f" & ${c['低价20%_误差均值_kW']:+.1f}$~kW \\\\",
        f"    两者之差 & ${c['两端误差均值差_kW']:+.1f}$~kW \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：合并口径把全部 (日期, 时段) 样本混在一起，被``时段之间''的电价"
        r"差异（傍晚贵、凌晨便宜）主导；把时段固定住再看，相关系数由 "
        f"${c['合并相关系数']:+.3f}$ 升到 ${c['逐时段相关系数均值']:+.3f}$，"
        rf"且 {pct(c['逐时段相关为正的比例'], 0)} 的时段为正。这说明"
        r"$\mathrm{Cov}(P,R)>0$ 是\textbf{同一时段内}的性质，"
        r"故风险余量必须逐时段计算，不能对全年做一次汇总——这正是框架 3.4 节"
        r"按 $t$ 单独求分位数的理由。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：两分支汇总
def tab_branches(res: dict) -> str:
    """表：result4-2 与 result4-3 的费用汇总与相互比较。"""
    a, b = res["4-2 主策略"], res["4-3 主策略"]
    # (行名, 4-2 的键, 4-3 的键, 小数位)：两个分支的键不一定同名
    rows = [
        ("计划量（$0{:}00$ 定下的量）/kWh", "计划量_kWh", "初始计划量_kWh", 0),
        ("最终生效常规量/kWh", "计划量_kWh", "最终常规量_kWh", 0),
        ("上调量/kWh", None, "上调量_kWh", 0),
        ("下调量/kWh", None, "下调量_kWh", 0),
        ("紧急购电量/kWh", "紧急购电量_kWh", "紧急购电量_kWh", 0),
        ("弃电量/kWh", "弃电量_kWh", "弃电量_kWh", 0),
        ("计划费/元", "计划费_元", "计划费_元", 0),
        ("调整费/元", None, "调整费_元", 0),
        ("紧急费/元", "紧急费_元", "紧急费_元", 0),
        ("合计费用/元", "合计费用_元", "合计费用_元", 0),
        ("期初储电量/kWh", "期初储电量_kWh", "期初储电量_kWh", 0),
        ("期末储电量/kWh", "期末储电量_kWh", "期末储电量_kWh", 0),
    ]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{两个交付文件在 2025 年 2 月 1 日--12 月 31 日（334 天）的"
        r"实际运行结果}",
        r"  \label{tab:p4-branch}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    指标 & result4-2（计划不得修改） & result4-3（6/12/18 可调整） \\",
        r"    \midrule",
    ]
    for name, k42, k43, nd in rows:
        va = None if k42 is None else a.get(k42)
        vb = None if k43 is None else b.get(k43)
        sa = "---" if va is None else fmt(va, nd)
        sb = "---" if vb is None else fmt(vb, nd)
        if k42 == "合计费用_元":
            sa, sb = rf"\textbf{{{sa}}}", rf"\textbf{{{sb}}}"
        lines.append(f"    {name} & {sa} & {sb} \\\\")
        if k43 == "紧急购电量_kWh":
            lines.append(r"    \midrule")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：两个分支都在\textbf{同一条附件 4 实际价格路径}上独立回放并独立"
        r"标定，费用一栏不可相加。两者均按\textbf{对应交付时段的实际电价}结算"
        r"（含初始计划费）。主计费口径取退款：被取消的部分按 $50\%$ 的违约电价"
        r"计，故 result4-3 全年实际发生下调；result4-2 全天冻结，无任何调整量。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：策略对照
def tab_strategies(res: dict) -> str:
    """表：三种价格信息条件下的策略对照（框架 6.1 节）。"""
    rows = res.get("策略对照")
    if not rows:
        return "% 策略对照尚未计算（需以 --strategies 运行 p4_microgrid.py）\n"
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{三种价格信息条件下的策略在同一实际价格路径上的独立回放"
        r"（框架 6.1 节）}",
        r"  \label{tab:p4-strategy}",
        r"  \footnotesize",
        r"  \begin{tabular}{llrrrr}",
        r"    \toprule",
        r"    分支 & 策略 & 计划费/元 & 调整费/元 & 紧急费/元 & 合计费用/元 \\",
        r"    \midrule",
    ]
    for r in rows:
        if r.get("模式") == "":
            # ΔJ 行
            lines.append(f"    \\midrule\n    {r['分支']} & \\textit{{{r['策略']}}}"
                         f" & --- & --- & ---"
                         f" & \\textbf{{{fmt(r['合计费用_元'], 0)}}}"
                         f"（{signed(float(r['相对降幅']) * 100)}） \\\\")
            continue
        lines.append(
            f"    {r['分支']} & {r['策略']} & {fmt(r.get('计划费_元', 0), 0)}"
            f" & {fmt(r.get('调整费_元', 0), 0)}"
            f" & {fmt(r.get('紧急费_元', 0), 0)}"
            f" & \\textbf{{{fmt(r['合计费用_元'], 0)}}} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：三种策略看到的价格信息不同，但\textbf{都在同一条实际价格路径上"
        r"结算}，故费用可直接相减。$\Delta J$ 取``固定电价参考''减``波动电价预测''，"
        r"即适应波动电价值多少钱。``未来价格已知参考''假设当天价格在 0:00 已全部"
        r"公布，作为\textbf{信息增强上界}单独报告（题目未提供该信息条件，故不作"
        r"主策略、不计入 $\Delta J$）。三者各自独立标定，用各自信息集下的历史。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：组合比较
def tab_combos(res: dict) -> str:
    """表：波动电价下 4-3 的八种预报组合（框架 6.2 节）。"""
    rows = res.get("预报组合")
    if not rows:
        return "% 预报组合尚未计算（需以 --sweep 运行 p4_microgrid.py）\n"
    base = next((r["合计费用_元"] for r in rows if r["使用预报"] == "∅"), None)
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{波动电价下 4-3 的八种预报使用组合（各组合单独标定参数，"
        r"评价区间与计费口径完全一致）}",
        r"  \label{tab:p4-combo}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    使用的预报时刻 & 初始计划费/元 & 调整费/元 & 紧急费/元 "
        r"& 合计费用/元 & 相对 $\varnothing$ & 期末储电量/kWh \\",
        r"    \midrule",
    ]
    for r in sorted(rows, key=lambda x: x["合计费用_元"]):
        tot = r["合计费用_元"]
        rel = "---" if base is None or r["使用预报"] == "∅" else \
            signed((tot - base) / base * 100)
        name = "仅 0:00" if r["使用预报"] == "∅" else r["使用预报"]
        lines.append(
            f"    {name} & {fmt(r['计划费_元'], 0)}"
            f" & {fmt(r['调整费_元'], 0)} & {fmt(r['紧急费_元'], 0)}"
            f" & \\textbf{{{fmt(tot, 0)}}} & {rel}"
            f" & {fmt(r['期末储电量_kWh'], 1)} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：与问题三的同一张表对照可以看出价格波动改变了什么——在固定电价下"
        r"``用不用新预报''主要体现在调整费与紧急费的此消彼长；在波动电价下，"
        r"更新预报同时改善了\textbf{电量}与\textbf{价格}两项判断（6:00 起既能看到"
        r"当天更准的负载与光伏，也能用当天已实现的价格修正剩余时段的电价预测），"
        r"因此增量收益的来源更宽。所有方案都使用 0:00 发布的预报，组合列出的时刻"
        r"是额外使用的版本。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def tab_combo_detail(res: dict) -> str:
    """表：4-3 八种预报组合在 12 条覆盖边上的边际价值。

    原先这张表是手抄进 moved_body.tex 的，重算后数字对不上（正是它导致了
    PDF 里的一批过时数字），故改为与其余各表同源生成。
    """
    rows = res.get("预报组合")
    if not rows:
        return "% 预报组合尚未计算（需以 --sweep 运行 p4_microgrid.py）\n"
    cost = {}
    for r in rows:
        key = frozenset() if r["使用预报"] == "∅" else \
            frozenset(int(t) for t in
                      r["使用预报"].strip("{}").split(",") if t.strip())
        cost[key] = r["合计费用_元"]
    # 12 条覆盖边：从 ∅ 逐层向上，每个集合再补一个尚未加入的时刻。
    edges = []
    for s in sorted(cost, key=lambda k: (len(k), sorted(k))):
        for h in (6, 12, 18):
            if h in s or (s | {h}) not in cost:
                continue
            edges.append((s, h, cost[s] - cost[s | {h}]))
    # 按起点集合分组（同一起点的几条边相邻），与原表的阅读顺序一致。
    edges.sort(key=lambda e: (len(e[0]), sorted(e[0]), e[1]))
    lo = min(range(len(edges)), key=lambda i: edges[i][2])

    def name(s) -> str:
        r"""集合列。空集用 \varnothing，其余写成 $\{6,18\}$ 的紧凑形式：
        CJK 标点进数学模式在 xelatex 下会排版异常，故用半角逗号。"""
        return r"$\varnothing$" if not s else \
            r"$\{" + ",".join(str(h) for h in sorted(s)) + r"\}$"

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{4-3 八种预报组合的边际价值（波动电价，各组合独立标定；"
        r"单位：元）}",
        r"  \label{tab:p4-combo-detail}",
        r"  \footnotesize",
        r"  \begin{tabular}{llrr}",
        r"    \toprule",
        r"    已有预报 $S$ & 再加一版 $h$ & 增量 $\Delta_h(S)$ & 折合 \\",
        r"    \midrule",
    ]
    prev = None
    for i, (s, h, d) in enumerate(edges):
        if prev is not None and len(s) != len(prev):
            lines.append(r"    \midrule")
        prev = s
        if i == lo:
            tail_cells = (r"\textbf{%s} & \textbf{%s 万元}"
                          % (fmt(d, 0), fmt(d / 1e4, 2)))
        else:
            tail_cells = f"{fmt(d, 0)} & {fmt(d / 1e4, 2)} 万元"
        lines.append(f"    {name(s)} & ${h}{{:}}00$ & {tail_cells} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：$\Delta_h(S)=J(S)-J(S\cup\{h\})$ 为在已有集合 $S$ 之上再订一版"
        r" $h$ 所省下的费用。所有组合都在同一条附件 4 实际价格路径上结算，且各自"
        r"重新标定 $\alpha,\rho,\lambda$，因此增量可以横向比较。加粗行是"
        r"\textbf{边际价值最低}的一条（已有 $\{6{:}00,18{:}00\}$ 时再加"
        r" $12{:}00$）；主计费口径下全部 $12$ 条边的增量\textbf{均为正}，"
        r"不存在\textbf{多一版预报反而有害}的情形——该辨析及逐边的费用构成"
        r"规律见附录该节说明。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：校验
def tab_check(res: dict) -> str:
    """表：问题四各项强制检查的实测最坏值与未通过天数。"""
    keys42 = ["信息边界", "计划冻结", "物理可行性", "状态累计", "费用一致性"]
    keys43 = ["信息边界", "调整权限", "物理可行性", "状态累计", "费用一致性"]
    f42, f43 = res["4-2 校验失败天数"], res["4-3 校验失败天数"]
    v42, v43 = res["4-2 校验数值口径"], res["4-3 校验数值口径"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{两个分支在 334 个交付日上的检查结果（未通过天数均为零）}",
        r"  \label{tab:p4-check}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    检查项 & result4-2 未通过天数 & result4-3 未通过天数 \\",
        r"    \midrule",
    ]
    for k in keys42:
        lines.append(f"    {k} & {f42[k]} & {f43.get(k, 0)} \\\\")
    for k in keys43:
        if k not in keys42:
            lines.append(f"    {k} & {f42.get(k, 0)} & {f43[k]} \\\\")
    lines += [
        r"    \midrule",
        r"    \multicolumn{3}{l}{\textit{数值口径的最坏值}} \\",
        r"    \midrule",
        f"    逐段电量平衡最大残差/kWh & ${sci(v42['逐段平衡最大残差_kWh'])}$"
        f" & ${sci(v43['逐段平衡最大残差_kWh'])}$ \\\\",
        f"    计划费重算最大偏差/元 & ${sci(v42['计划费重算最大偏差_元'])}$"
        f" & ${sci(v43['计划费重算最大偏差_元'])}$ \\\\",
        f"    调整费重算最大偏差/元 & --- "
        f"& ${sci(v43['调整费重算最大偏差_元'])}$ \\\\",
        f"    紧急费重算最大偏差/元 & ${sci(v42['紧急费重算最大偏差_元'])}$"
        f" & ${sci(v43['紧急费重算最大偏差_元'])}$ \\\\",
        f"    跨日衔接最大偏差/kWh & ${sci(v42['跨日衔接最大偏差_kWh'])}$"
        f" & ${sci(v43['跨日衔接最大偏差_kWh'])}$ \\\\",
        f"    全局储电量范围/kWh & "
        f"{fmt(v42['全局最小储电量_kWh'], 1)}~{fmt(v42['全局最大储电量_kWh'], 1)}"
        f" & {fmt(v43['全局最小储电量_kWh'], 1)}~"
        f"{fmt(v43['全局最大储电量_kWh'], 1)} \\\\",
        r"    \midrule",
        f"    储电下界余量/kWh & {fmt(v42['储电下界余量_kWh'], 3)}"
        f" & {fmt(v43['储电下界余量_kWh'], 3)} \\\\",
        f"    储电上界余量/kWh & {fmt(v42['储电上界余量_kWh'], 3)}"
        f" & {fmt(v43['储电上界余量_kWh'], 3)} \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：残差均为浮点误差量级（$<10^{-12}$~kWh），说明约束是被精确满足"
        r"而非近似满足。储电量上下界余量恰为零，说明日末储备与容量约束在个别"
        r"日期是\textbf{紧的}——这正是风险余量与储备线起作用的地方，不是缺陷。"
        r"``计划冻结''在 result4-2 下的可核验内容是逐段电量平衡：执行层唯一的外部"
        r"常规购电来源是 0:00 定下的计划量，日内不存在第二次常规购电。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ------------------------------------------- 表：不退款口径敏感性（4-3，附录）
def tab_refund(res: dict) -> str:
    """表：4-3 在主计费口径（退款）与不退款口径下的对照。

    主口径取题面的字面读法（被取消部分按 50% 违约电价计，调减每度 0.5p）；
    "不退款、只追加"是另一种更保守的读法，作为独立敏感性报告。两种口径下模型
    与执行规则完全相同，只有费用函数不同，因此这张表回答的是"主结论对这条题面
    歧义有多敏感"，而不是给出第二个答案。
    """
    main, no_ref = res.get("4-3 主策略"), res.get("4-3 不退款口径")
    if not main or not no_ref:
        return ("% 不退款口径未计算（需先由 --refund-main 换口径）\n")
    rows = [
        ("合计费用", "合计费用_元", 2),
        ("其中 计划费", "计划费_元", 2),
        ("其中 调整费", "调整费_元", 2),
        ("其中 紧急费", "紧急费_元", 2),
        ("计划量（初始）", "初始计划量_kWh", 2),
        ("最终常规量", "最终常规量_kWh", 2),
        ("上调量", "上调量_kWh", 2),
        ("下调量", "下调量_kWh", 2),
        ("紧急购电量", "紧急购电量_kWh", 2),
        ("弃电量", "弃电量_kWh", 2),
        ("期末储电量", "期末储电量_kWh", 2),
        ("调整提交次数", "调整提交次数", 0),
    ]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{4-3 在主计费口径（退款）与不退款口径下的对照（两口径各自独立"
        r"标定并回放，模型与执行规则完全相同，只换费用函数与可行域）}",
        r"  \label{tab:p4-refund}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrr}",
        r"    \toprule",
        r"    指标 & 主口径（退款） & 不退款口径 & 差异（不退款 $-$ 主口径） \\",
        r"    \midrule",
    ]
    for name, key, nd in rows:
        a, b = main.get(key), no_ref.get(key)
        if a is None or b is None:
            continue
        d = b - a
        dstr = "---" if abs(d) < 5e-7 * max(1.0, abs(a)) else \
            f"{d:+,.{nd}f}"
        lines.append(f"    {name} & {fmt(a, nd)} & {fmt(b, nd)} & {dstr} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：两种口径的差别不只是一个系数。主口径下调减每度只花 $0.5p$，",
        r"    是一条真实可用的通道，全年下调量非零；不退款口径把计划费理解为",
        r"    无条件全额、$50\%$ 只作\textbf{额外}违约费，此时调减每度净付",
        r"    $1.5p$、最优解不会真正调减，$x_t\ge g_t^0$ 成为可以外加的简化约束，",
        r"    \textbf{可行域本身变窄}。因此两条臂的\textbf{标定结果与最终计划都",
        r"    不同}，表中的差异同时包含参数差异与规则差异，不能读作同一个解的两种",
        r"    计价。这里关心的是\textbf{$4$-$3$ 相对 $4$-$2$ 的方向是否依然成立}：",
        r"    两种口径下 $4$-$3$ 都低于 $4$-$2$，主结论不依赖这条题面歧义。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


HEADER = [
    "% 本文件由 03_代码/p4_tables.py 自动生成，请勿手工修改。",
    "% 数据源：06_支撑材料/p4_results.json",
    "",
]


def main() -> None:
    with open(SUP / "p4_results.json", encoding="utf-8") as fh:
        res = json.load(fh)
    # 正文只留两张最必需的交付表：
    #   tab_branches  两个交付文件的全年结果——题目明确要求的两份文件，必须在正文；
    #   tab_strategy  三种价格信息条件的策略对照——ΔJ 的全部数字，正文逐条讨论。
    # 其余全部入附录。正文只有 30 页额度，把策略对照表放附录也有内容上的理由：
    # 它与同名的费用分解图（附录图）成对阅读更自然，正文该处已给出全部关键数字。
    body = HEADER + [
        tab_branches(res),
    ]
    tail = HEADER + [
        tab_price_struct(res),
        tab_strategies(res),
        # 选型表紧挨候选复核表：前者回答"参数怎么定的"，后者回答"定下来之后
        # 在评价区间上表现如何"，两张表连读才看得出选型与评价已经分开。
        tab_select(res),
        tab_forecast(res),
        tab_beta(res),
        tab_skill4(res),
        tab_risk(res),
        tab_combos(res),
        tab_check(res),
    ]
    if "--split" in sys.argv:
        OUT_TEX.write_text("\n".join(body), encoding="utf-8")
        OUT_TEX_TAIL.write_text("\n".join(tail), encoding="utf-8")
        OUT_TEX_REFUND.write_text(
            HEADER[0] + "\n" + HEADER[1] + "\n\n" + tab_refund(res),
            encoding="utf-8")
        OUT_TEX_COMBO.write_text(
            HEADER[0] + "\n" + HEADER[1] + "\n\n" + tab_combo_detail(res),
            encoding="utf-8")
        print(f"写入 {OUT_TEX}（正文：两分支汇总 + 策略对照）")
        print(f"写入 {OUT_TEX_TAIL}（附录：价格结构 + 预测选型 + 风险口径"
              f" + 组合比较 + 校验）")
        print(f"写入 {OUT_TEX_REFUND}（附录：不退款口径敏感性）")
        print(f"写入 {OUT_TEX_COMBO}（附录：八种组合的边际价值明细表）")
        return
    OUT_TEX.write_text("\n".join(body + tail), encoding="utf-8")
    print(f"写入 {OUT_TEX}")


if __name__ == "__main__":
    main()
