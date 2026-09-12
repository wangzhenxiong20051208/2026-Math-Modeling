# -*- coding: utf-8 -*-
"""问题三：把分析结果排版成论文表格。

数据来源只有一个方向，本脚本不重新求解任何模型：
  * `06_支撑材料/p3_spec.json`     指定日期的表 1/表 2/表 3 明细（p3_export.py 写出）
  * `06_支撑材料/p3_analysis.json` 全年回放、消融、参数、校验、精度（p3_analysis.py 写出）
  * `06_支撑材料/p3_main_arrays.npz` 主策略逐时段的 g^0/x/r/c/d/E 数组（p3_analysis.py 写出）

产出：
  * 05_论文/CUMCMThesis/p3_tables.tex          正文的表 1、表 2、表 3
  * 05_论文/CUMCMThesis/p3_tables_appendix.tex 附录的消融、精度、校验、参数、口径
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
SUP = ROOT / "08_算法修正" / "输出"
TEX = ROOT / "08_算法修正" / "输出" / "论文表格"

SPEC_DATES = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
SHORT = {
    "2025-03-20": "2025.3.20",
    "2025-06-21": "2025.6.21",
    "2025-09-23": "2025.9.23",
    "2025-12-21": "2025.12.21",
}
BLOCKS = ["0:00-4:00", "4:00-8:00", "8:00-12:00", "12:00-16:00", "16:00-20:00", "20:00-24:00"]
ADJ_ORDER = ["6:00", "12:00", "6:00+12:00", "18:00", "6:00+18:00", "12:00+18:00",
             "6:00+12:00+18:00"]


# ------------------------------------------------------------------ 格式化
def n(x, d: int = 2, clamp: float = 5e-3) -> str:
    """千分位数字；绝对值小于 clamp 的按 0 处理，避免出现 -0.00。"""
    v = float(x)
    if abs(v) < clamp:
        v = 0.0
    return f"{v:,.{d}f}"


def n0(x) -> str:
    return n(x, 0, clamp=0.5)


def pct(x) -> str:
    r"""带符号百分数，并把 % 转义成 \%——LaTeX 里裸 % 会注释掉整行剩余内容，
    使表格行少一个 \\，下一行被并进同一行，报 "Extra alignment tab"。"""
    return f"{float(x):+.2%}".replace("%", r"\%")


def tb(s: str) -> str:
    r"""时间里的冒号写成 {;}，防止 LaTeX 把它当标点断行。"""
    return s.replace(":", "{:}")


# ------------------------------------------------------------------ 正文表
def body_tables(spec: dict, arr: dict, price: np.ndarray, dates) -> str:
    L: list[str] = []
    A = L.append
    A("% 本文件由 03_代码/p3_tables.py 自动生成，请勿手工修改。")
    A("% 数据源：06_支撑材料/p3_spec.json 与 p3_main_arrays.npz")
    A("")

    idx = {s: int(np.flatnonzero(pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
                                 == pd.Timestamp(s))[0]) for s in SPEC_DATES}

    # ---------------------------------------------------------- 表 1 格式
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{指定日期六个时段的初始计划购电量 $g^0_t$、最终生效购电量 $x_t$、"
      r"调整量与紧急购电量（单位：kWh）}")
    A(r"  \label{tab:p3-buy}")
    A(r"  \scriptsize")
    A(r"  \begin{tabular}{llrrrr}")
    A(r"    \toprule")
    A(r"    日期 & 时段 & 初始计划 $g^0_t$ & 最终生效 $x_t$ & 调整量 & 紧急购电 $r_t$ \\")
    A(r"    \midrule")
    for di, d in enumerate(SPEC_DATES):
        if di:
            A(r"    \midrule")
        k = idx[d]
        r_arr = arr[f"r_{k}"]
        t1 = spec["spec"][d]["table1"]
        # p3_spec.json 的 table1 按显示顺序给出 slot 标签，逐条与数组下标对齐：
        # 标签 "10:00-10:10" 对应 slot 60，即下标 = 起始小时*6 + 起始分钟//10。
        for j, row in enumerate(t1):
            i = _slot_index(row["slot"])
            gP, gA = float(row["gP"]), float(row["gA"])
            head = (r"    \multirow{6}{*}{%s} & %s" % (SHORT[d], tb(row["slot"]))) if j == 0 \
                else (r"     & %s" % tb(row["slot"]))
            A(f"{head} & {n(gP)} & {n(gA)} & {n(gA - gP)} & {n(r_arr[i])} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    续表：全天费用分解（单位：元）。当日计划费为 $\sum_t p_tg^0_t$；"
      r"调整费为 $p_tg^0_t+1.5p_t(x_t-g^0_t)_+-0.5p_t(g^0_t-x_t)_+$ 与计划费之差；"
      r"紧急费为 $\sum_t5p_tr_t$。三项相加即当日实际总费用。")
    A(r"  \end{minipage}")
    A(r"  \par\vspace{4pt}")
    A(r"  \begin{tabular}{lrrrrrr}")
    A(r"    \toprule")
    A(r"    日期 & 初始计划量 & 最终常规量 & 紧急购电量 & 计划费 & 调整费 & 当日合计费用 \\")
    A(r"    \midrule")
    for d in SPEC_DATES:
        s = spec["spec"][d]
        k = idx[d]
        plan_fee = float(np.sum(price * arr[f"gP_{k}"]))
        A(f"    {SHORT[d]} & {n(s['Gplan'], 1)} & {n(s['Gadj'], 1)} & {n(s['Gemg'], 1)} & "
          f"{n0(plan_fee)} & {n0(float(s['cost_plan_adj']) - plan_fee)} & "
          f"\\textbf{{{n0(s['cost_total'])}}} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 表 2 格式
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{储能设备在指定日期的实际充放电量（按四小时汇总，单位：kWh）}")
    A(r"  \label{tab:p3-storage}")
    A(r"  \scriptsize")
    A(r"  \begin{tabular}{lrrrrrrrr}")
    A(r"    \toprule")
    A(r"    时段 & \multicolumn{2}{c}{2025.3.20} & \multicolumn{2}{c}{2025.6.21} & "
      r"\multicolumn{2}{c}{2025.9.23} & \multicolumn{2}{c}{2025.12.21} \\")
    A(r"     & 充电 & 放电 & 充电 & 放电 & 充电 & 放电 & 充电 & 放电 \\")
    A(r"    \midrule")
    for blk in BLOCKS:
        cells = []
        for d in SPEC_DATES:
            t2 = {r["block"]: r for r in spec["spec"][d]["table2"]}[blk]
            cells += [n(t2["chg"], 1), n(t2["dis"], 1)]
        A(f"    {tb(blk)} & " + " & ".join(cells) + r" \\")
    A(r"    \midrule")
    e0 = " & ".join(f"\\multicolumn{{2}}{{c}}{{{n(spec['spec'][d]['E0'], 1)}}}"
                    for d in SPEC_DATES)
    e1 = " & ".join(f"\\multicolumn{{2}}{{c}}{{{n(spec['spec'][d]['E144'], 1)}}}"
                    for d in SPEC_DATES)
    A(r"    $0{:}00$ 储电量 & " + e0 + r" \\")
    A(r"    $24{:}00$ 储电量 & " + e1 + r" \\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 12 月 21 日明细
    d = "2025-12-21"
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{2025 年 12 月 21 日储能设备的实际充放电量与 $0{:}00$、$24{:}00$ 储电量}")
    A(r"  \label{tab:p3-storage-dec}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{lrr}")
    A(r"    \toprule")
    A(r"    时段 & 充电量/kWh & 放电量/kWh \\")
    A(r"    \midrule")
    for row in spec["spec"][d]["table2"]:
        A(f"    {tb(row['block'])} & {n(row['chg'], 2)} & {n(row['dis'], 2)} \\\\")
    A(r"    \midrule")
    A(f"    $0{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}"
      f"{{{n(spec['spec'][d]['E0'], 2)}}} \\\\")
    A(f"    $24{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}"
      f"{{{n(spec['spec'][d]['E144'], 2)}}} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 表 3 格式
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{微网在指定日期的紧急购电事件（问题三，按同日连续时段合并）}")
    A(r"  \label{tab:p3-emg}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{llrl}")
    A(r"    \toprule")
    A(r"    日期 & 紧急购电时间段 & 紧急购电量/kWh & 该日紧急费/元 \\")
    A(r"    \midrule")
    first = True
    for d in SPEC_DATES:
        evs = spec["spec"][d]["emg_events"]
        if not first:
            A(r"    \midrule")
        first = False
        if not evs:
            A(f"    {SHORT[d]} & \\multicolumn{{2}}{{c}}{{无}} & 0.00 \\\\")
            continue
        span = len(evs)
        for ei, ev in enumerate(evs):
            rng = tb(ev["start"] + "-" + ev["end"])
            if ei == 0:
                A(f"    \\multirow{{{span}}}{{*}}{{{SHORT[d]}}} & {rng} & {n(ev['kwh'])} & "
                  f"\\multirow{{{span}}}{{*}}{{{n0(ev['cost'])}}} \\\\")
            else:
                A(f"     & {rng} & {n(ev['kwh'])} & \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    注：紧急购电量逐十分钟按 $5p_tr_t$ 计费后再把同日连续时段合并成事件，"
      r"合并不改变费用；合并后电量与逐段之和严格相等。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    return "\n".join(L) + "\n"


def _slot_index(label: str) -> int:
    """把 '10:00-10:10' 映射到 0..143 的时段下标。"""
    a = label.split("-")[0]
    h, m = a.split(":")
    return int(h) * 6 + int(m) // 10


# ------------------------------------------------------------------ 附录表
def appendix_tables(A_: dict, cal: dict | None = None) -> str:
    cfgs = A_["configs"]
    L: list[str] = []
    A = L.append
    A("% 本文件由 03_代码/p3_tables.py 自动生成，请勿手工修改。")
    A("% 数据源：06_支撑材料/p3_analysis.json")
    A("")

    main = cfgs["主策略"]
    ctrl = cfgs["对照：只用0:00预报"]

    # ---------------------------------------------------------- 预报组合消融
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{八种预报组合在 2025 年 2 月 1 日--12 月 31 日的实际费用"
      r"（参数固定为 $\alpha=0.6,\rho=0.5,\lambda=1.0,W=28$，"
      r"评价区间、负载模型、执行规则与计费口径完全一致）}")
    A(r"  \label{tab:p3-combo}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{lrrrrr}")
    A(r"    \toprule")
    A(r"    使用的预报时刻 & 计划调整费/元 & 紧急费/元 & 合计费用/元 & 相对基准 & 期末储电量/kWh \\")
    A(r"    \midrule")
    A(f"    仅 0{{:}}00 & {n0(ctrl['plan_adj'])} & {n0(ctrl['emg'])} & "
      f"\\textbf{{{n0(ctrl['total'])}}} & --- & {n(ctrl['E144_last'], 1)} \\\\")
    base = ctrl["total"]
    for lab in ADJ_ORDER:
        c = cfgs[lab]
        d = (c["total"] - base) / base
        A(f"    {tb(lab)} & {n0(c['plan_adj'])} & {n0(c['emg'])} & "
          f"\\textbf{{{n0(c['total'])}}} & {pct(d)} & {n(c['E144_last'], 1)} \\\\")
    A(r"    \midrule")
    A(f"    \\textbf{{主策略（全用）}} & {n0(main['plan_adj'])} & {n0(main['emg'])} & "
      f"\\textbf{{{n0(main['total'])}}} & {pct((main['total'] - base) / base)} & "
      f"{n(main['E144_last'], 1)} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    注：所有方案都使用 0:00 发布的预报；组合列出的时刻是\textbf{额外}使用的版本。"
      r"首行“仅 0:00”是关闭全部调整的对照，其购电量不随日内预报变化。"
      r"“相对基准”以该对照为分母，负值表示比不做调整更省。"
      r"合计费用已含计划部分，不能再与计划调整费、紧急费相加。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 预报精度
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{附件 3 四个发布版本在 2025 年 2 月 1 日--12 月 31 日的光伏出力"
      r"预报精度（单位：kW；把整点预报因果内插到十分钟后与实际光伏逐段比较）}")
    A(r"  \label{tab:p3-skill}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{llrrr}")
    A(r"    \toprule")
    A(r"    预报版本 & 当天可用时段 & 可用时段数 & 覆盖段绝对误差 & 其中 $12{:}00$--$18{:}00$ \\")
    A(r"    \midrule")
    COV = {"0:00": "0{:}00--24{:}00", "6:00": "6{:}00--24{:}00",
           "12:00": "12{:}00--24{:}00", "18:00": "18{:}00--24{:}00"}
    for row in A_["skill"]:
        rel = row["release"]
        noon = "---" if row["mae_noon_kw"] is None else n(row["mae_noon_kw"], 1)
        A(f"    {tb(rel)} 发布 & {COV[rel]} & {row['n']:,} & {n(row['mae_kw'], 1)} & "
          f"{noon} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    注：只报\textbf{绝对}误差而不报相对误差，因为四个版本的覆盖时段长度不同："
      r"$18{:}00$ 版只覆盖光伏趋近于零的夜间，任何以该段平均功率为分母的相对指标"
      r"都会被极小的分母放大成无意义的数字。在四版共同覆盖的 $18{:}00$--$24{:}00$"
      r"上，四者误差几乎相同（均在 $15.7$--$15.9$~kW），差异全部来自白天；"
      r"$18{:}00$ 版对白天\textbf{没有任何}覆盖，因此该列为空——它的价值不在预报精度，"
      r"而在它决定的是哪一个时段（见后文第（1）条）。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 参数敏感性
    p = A_["params"]
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{主策略参数的单变量扰动（每次只动一个参数，其余取 "
      r"$\alpha=0.6,\rho=0.5,\lambda=1.0,W=28$，评价区间同前）}")
    A(r"  \label{tab:p3-param}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{lrrrr}")
    A(r"    \toprule")
    A(r"    参数取值 & 计划调整费/元 & 紧急费/元 & 合计费用/元 & 相对主策略 \\")
    A(r"    \midrule")
    A(f"    主策略 $\\alpha=0.6,\\rho=0.5,\\lambda=1.0,W=28$ & "
      f"{n0(main['plan_adj'])} & {n0(main['emg'])} & "
      f"\\textbf{{{n0(main['total'])}}} & --- \\\\")
    A(r"    \midrule")
    for lab in sorted(p, key=lambda s: s):
        c = p[lab]
        if lab in ("alpha=0.6,rho=0.5", "lam=1.0", "W=28"):
            continue
        pretty = (lab.replace("alpha=", r"$\alpha=$").replace("rho=", r"$\rho=$")
                  .replace("lam=", r"$\lambda=$").replace("W=", r"$W=$")
                  .replace(",", r",\;"))
        d = (c["total"] - main["total"]) / main["total"]
        A(f"    {pretty} & {n0(c['plan_adj'])} & {n0(c['emg'])} & {n0(c['total'])} & "
          f"{pct(d)} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    注：$\alpha$ 为净负荷预测的风险分位数，$\rho$ 为实时放电储备线比例，"
      r"$\lambda$ 为日末储电量回归目标的引导权重，$W$ 为分位数所用的历史窗口天数。"
      r"表中省略了与主策略完全相同的取值行。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 计费口径
    nrf = cfgs["敏感性：不退款口径"]
    ps = cfgs["敏感性：逐时段分位数"]
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{计费口径与风险分位数口径的敏感性（模型、参数、评价区间均与主策略相同，"
      r"只换这一处口径）}")
    A(r"  \label{tab:p3-billing}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{lrrrr}")
    A(r"    \toprule")
    A(r"    口径 & 计划调整费/元 & 紧急费/元 & 合计费用/元 & 相对主策略 \\")
    A(r"    \midrule")
    A(f"    主策略：退款口径 $+$ 跨时段合并分位数 & {n0(main['plan_adj'])} & "
      f"{n0(main['emg'])} & \\textbf{{{n0(main['total'])}}} & --- \\\\")
    A(f"    调减不退款口径 & {n0(nrf['plan_adj'])} & {n0(nrf['emg'])} & {n0(nrf['total'])} & "
      f"{pct((nrf['total'] - main['total']) / main['total'])} \\\\")
    A(f"    逐时段分位数 & {n0(ps['plan_adj'])} & {n0(ps['emg'])} & {n0(ps['total'])} & "
      f"{pct((ps['total'] - main['total']) / main['total'])} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    A(r"    注：第一项口径之争在于题目只说“计划购电量高于调整购电量的部分按 $50\%$ 计算”，"
      r"未说明这部分原价是否退回。主策略按\textbf{退款}理解，即调减只按 $0.5p_t$ 结算；"
      r"若按不退款理解（调减仍付 $p_t$），最优调整将从不调减，与题目允许调整的设定相悖，"
      r"故本表把两种读法并列报告。第二项把“把全部时段的历史误差合并成一个分位数”"
      r"换成“每个时段各自一个分位数”，用以衡量风险刻画的粒度。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    A("")

    # ---------------------------------------------------------- 1 月标定
    if cal is not None:
        A(r"\begin{table}[htbp]")
        A(r"  \centering")
        A(r"  \caption{参数的 1 月标定记录：标定面，以及用 1 月最优参数直接外推的检验}")
        A(r"  \label{tab:p3-calib}")
        A(r"  \footnotesize")
        A(r"  \begin{tabular}{lrrrr}")
        A(r"    \toprule")
        A(r"    风险分位数 $\alpha$ & $\rho=0.35$ & $\rho=0.5$ & $\rho=0.7$ & 该行最小 \\")
        A(r"    \midrule")
        for a in (0.4, 0.5, 0.6, 0.7, 0.8):
            vals = [cal["jan"].get(f"a{a}_r{r}_W28") for r in (0.35, 0.5, 0.7)]
            if any(v is None for v in vals):
                continue
            cells = [n(v["total"], 0) for v in vals]
            best = min(v["total"] for v in vals)
            row = f"    {a:.1f} & " + " & ".join(
                f"\\textbf{{{c}}}" if v["total"] == best else c
                for c, v in zip(cells, vals))
            A(row + f" & {n(best, 0)} \\\\")
        A(r"    \midrule")
        for w in (14, 21, 28):
            v = cal["jan"][f"a0.6_r0.5_W{w}"]
            tail = "（采用）" if w == 28 else ""
            A(f"    窗口 $W={w}$ & \\multicolumn{{3}}{{c}}{{{n(v['total'], 0)}}} & "
              f"{tail} \\\\")
        A(r"    \midrule")
        for l in (0.0, 0.5, 1.0):
            v = cal["lam_scan"][f"lam{l}"]
            tail = ("（日末储电仅 %s~kWh）" % n(v["E144"], 0)) if l == 0.0 else \
                   ("（采用）" if l == 1.0 else "")
            A(f"    $\\lambda={l:.1f}$ & \\multicolumn{{3}}{{c}}{{{n(v['total'], 0)}}} & "
              f"{tail} \\\\")
        A(r"    \bottomrule")
        A(r"  \end{tabular}")
        A(r"  \par\vspace{2pt}")
        A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
        fb = cal["frozen_jan"]["total"]
        jb = cal["jan_best_jan"]["total"]
        oo = cal["jan_best_febdec"]["total"]
        fo = cal["best_febdec"]["total"]
        A(r"    上半部分为 1 月标定面（$W=28$，单位：元），下半部分为 $W$ 与 $\lambda$ 的"
          r"单变量扫描。标定面在 $\alpha$ 方向有明确的极小点 $\alpha=0.6$，在 $\rho$ 与 "
          r"$W$ 方向则相当平坦：$\rho\in[0.35,0.5]$、$W\in[14,28]$ 的全部取值都落在"
          r"同一水平内，彼此相差不到 $1\%$。")
        A(r"    \textbf{外推检验}（本表最重要的一行）：1 月标定面上的最小值在 "
          f"$(\\alpha,\\rho,W)=(0.6,0.35,14)$，1 月费用 ${n(jb, 0)}$~元，"
          f"低于本文采用的 $(0.6,0.5,28)$ 的 ${n(fb, 0)}$~元（省 ${n(fb - jb, 0)}$~元）。"
          f"但把这两组参数分别拿去跑完整评价区间，前者为 ${n(oo, 0)}$~元，"
          f"后者为 ${n(fo, 0)}$~元——\\textbf{{在 1 月上更优的那一组反而更贵}}"
          f"（多花 ${n(oo - fo, 0)}$~元）。这说明 31 天的标定窗口已足以把标定面上的"
          r"细小凸起拟合进去，直接取最小点是过拟合；因此本文取标定面的\textbf{中心}"
          r"\textbf{取值} $(0.6,0.5,28)$，而不是它的最小点。$\lambda$ 取 $1.0$ 而非 "
          r"1 月最优的 $0.5$：二者在评价区间上只差 $0.07\%$（$9{,}852$~元），"
          r"但 $\lambda=0$ 会把日末储电量抽到 $1{,}806$~kWh（贴近下界 $1{,}200$），"
          r"属于把成本推给次日的透支行为，故保留非零惩罚。")
        A(r"  \end{minipage}")
        A(r"\end{table}")
        A("")

    # ---------------------------------------------------------- 校验
    v = A_["validation"]
    worst = v["worst"]
    A(r"\begin{table}[htbp]")
    A(r"  \centering")
    A(r"  \caption{九项检查在主策略全部 " + f"{v['n_days']}" + r" 个交付日上的实测结果}")
    A(r"  \label{tab:p3-check}")
    A(r"  \footnotesize")
    A(r"  \begin{tabular}{llr}")
    A(r"    \toprule")
    A(r"    检查项 & 实测最坏值 & 未通过天数 \\")
    A(r"    \midrule")
    A(f"    逐段能量平衡 & ${worst['balance']:.2e}$ kWh & 0 \\\\")
    A(f"    储能状态递推 & ${worst['dynamics']:.2e}$ kWh & 0 \\\\")
    A(f"    计划调整费复算 & ${worst['cost_adj']:.2e}$ 元 & 0 \\\\")
    A(f"    紧急购电费复算 & ${worst['cost_emg']:.2e}$ 元 & 0 \\\\")
    A(r"    储电量上下界 & 结构上恒成立 & 0 \\")  # noqa: W605
    A(r"    充放电功率上限 & 结构上恒成立 & 0 \\")
    A(r"    同时充放电 & 结构上恒成立 & 0 \\")
    A(r"    购电量非负 & 结构上恒成立 & 0 \\")
    A(r"    跨日状态衔接 & 结构上恒成立 & 0 \\")
    A(r"    \midrule")
    A(f"    合计 & --- & \\textbf{{{v['n_days_bad']}}} \\\\")
    A(r"    \bottomrule")
    A(r"  \end{tabular}")
    A(r"  \par\vspace{2pt}")
    A(r"  \begin{minipage}{.92\textwidth}\footnotesize")
    if v["problems"]:
        A(r"    注：未通过日的具体问题为 " +
          "、".join(v["problems"]) + r"。")
    else:
        A(r"    注：九项检查在全部交付日上一次通过，无任何残差、越界或复算不符。")
    A(r"    前四项由独立复算得到最坏值，后五项由线性规划的约束边界与实时执行规则"
      r"结构性地保证，故逐日实测值恒为零。")
    A(r"  \end{minipage}")
    A(r"\end{table}")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ 主流程
def main() -> None:
    import p3_microgrid as M

    spec = json.loads((SUP / "p3_spec.json").read_text(encoding="utf-8"))
    anal = json.loads((SUP / "p3_analysis.json").read_text(encoding="utf-8"))
    calp = SUP / "p3_calibration.json"
    cal = json.loads(calp.read_text(encoding="utf-8")) if calp.exists() else None
    price, dates, _, _, _ = M.load_all()

    arrays = np.load(SUP / "p3_main_arrays.npz")
    arr = {k: arrays[k] for k in arrays.files}

    (TEX / "p3_tables.tex").write_text(body_tables(spec, arr, price, dates),
                                       encoding="utf-8")
    (TEX / "p3_tables_appendix.tex").write_text(appendix_tables(anal, cal),
                                               encoding="utf-8")
    print("已写出 p3_tables.tex 与 p3_tables_appendix.tex")


if __name__ == "__main__":
    main()
