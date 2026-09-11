# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题三 —— 由求解结果直接生成论文表格片段。

写出 05_论文/CUMCMThesis/p3_tables.tex，由 main.tex 以 \input 引入，
使论文中的每个数字都与 result3/p3_results.json 严格同源，避免手工转录错误。

运行：python3 03_代码/p3_tables.py （需先运行 p3_microgrid.py）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_microgrid import N  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "06_支撑材料"
OUT_TEX = ROOT / "05_论文" / "CUMCMThesis" / "p3_tables.tex"
# TEX 规范第四条：正文（含摘要页）不超过 30 页，附录页数不限。故把"支撑性"
# 的两张表放进附录：预报精度表与七项校验表。它们只是论据，正文用一句话给出
# 结论并 \ref 过去即可。
#
# 注意\textbf{不能}移到附录的是什么：题目问题二、问题三都明确要求"在论文中按
# 表 1、表 2 和表 3 的格式给出表 3 中指定日期的结果"，即 tab_buy（表 1 格式）、
# tab_storage/tab_storage-dec（表 2 格式）与 tab_emg（表 3 格式）必须留在正文；
# tab_combo 是"是否需要引入其他时刻预报"这一提问的直接答案，也必须留在正文。
OUT_TEX_TAIL = ROOT / "05_论文" / "CUMCMThesis" / "p3_tables_appendix.tex"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
DISP = {"2025-03-20": "2025.3.20", "2025-06-21": "2025.6.21",
        "2025-09-23": "2025.9.23", "2025-12-21": "2025.12.21"}
BLOCK_LAB = ["0:00-4:00", "4:00-8:00", "8:00-12:00", "12:00-16:00",
             "16:00-20:00", "20:00-24:00"]

SIX = ["10:00-10:10", "12:00-12:10", "14:00-14:10",
       "16:00-16:10", "18:00-18:10", "20:00-20:10"]


def fmt(v: float, nd: int = 2) -> str:
    return f"{v:,.{nd}f}"


def texlab(s: str) -> str:
    return s.replace(":", "{:}")


def signed(pct: float) -> str:
    return f"{pct:+.2f}\\%".replace("+-", "-")


# ---------------------------------------------------------------- 表：预报精度
def tab_skill(res: dict) -> str:
    """表：各发布版本的净负荷预测误差，以及问题二历史外推的对照。"""
    prec = res["预报精度_净负荷MAE_kWh每日"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{各发布版本在 2025 年 2 月 1 日--12 月 31 日的净负荷预测"
        r"误差（只统计发布时刻之后的时段）}",
        r"  \label{tab:p3-skill}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrr}",
        r"    \toprule",
        r"    预报版本 & 逐时段绝对偏差之和/kWh & 全天电量偏差/kWh & "
        r"符号偏差/kWh & 相对日净负荷 \\",
        r"    \midrule",
    ]
    for hr in (0, 6, 12, 18):
        v = prec[str(hr)] if str(hr) in prec else prec[hr]
        lines.append(
            f"    {hr}{{:}}00 发布 & {fmt(v['逐时段绝对偏差之和_kWh每日'], 1)}"
            f" & {fmt(v['全天电量偏差_kWh每日'], 1)}"
            f" & {v['符号偏差_kWh每日']:+,.1f}"
            f" & {v['相对日净负荷']*100:.2f}\\% \\\\")
    h = prec["对照_历史外推"]
    lines += [
        r"    \midrule",
        f"    问题二历史外推对照 & "
        f"{fmt(h['逐时段绝对偏差之和_kWh每日'], 1)}"
        f" & {fmt(h['全天电量偏差_kWh每日'], 1)}"
        f" & {h['符号偏差_kWh每日']:+,.1f}"
        f" & {h['相对日净负荷']*100:.2f}\\% \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：“逐时段绝对偏差之和”为 $\sum_t|N_t-\widehat N_t|$，衡量十分钟"
        r"尺度的错位；“全天电量偏差”为 $|\sum_t(N_t-\widehat N_t)|$，衡量日总量"
        r"口径，二者不可混用。符号偏差为正表示净负荷被\textbf{低估}。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表 1：购电结果
def tab_buy(res: dict) -> str:
    """论文表 1：六个指定时段的初始计划、最终购电与全天费用分解。"""
    sd = res["指定日期"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{指定日期六个时段的初始计划购电量 $g^0_t$、最终生效购电量 "
        r"$x_t$、正式调整量与紧急购电量（单位：kWh）}",
        r"  \label{tab:p3-buy}",
        r"  \scriptsize",
        r"  \begin{tabular}{llrrrr}",
        r"    \toprule",
        r"    日期 & 时段 & 初始计划 $g^0_t$ & 最终生效 $x_t$ & 调整量 "
        r"& 紧急购电 $r_t$ \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        t1 = {r["时间段"]: r for r in sd[d]["table1"]}
        lines.append(
            f"    \\multirow{{6}}{{*}}{{{DISP[d]}}}"
            f" & {texlab(SIX[0])} & {fmt(t1[SIX[0]]['计划购电量_kWh'])}"
            f" & {fmt(t1[SIX[0]]['调整购电量_kWh'])}"
            f" & {fmt(t1[SIX[0]]['增量_kWh'])}"
            f" & {fmt(t1[SIX[0]]['紧急购电量_kWh'])} \\\\")
        for k in SIX[1:]:
            lines.append(
                f"     & {texlab(k)} & {fmt(t1[k]['计划购电量_kWh'])}"
                f" & {fmt(t1[k]['调整购电量_kWh'])}"
                f" & {fmt(t1[k]['增量_kWh'])}"
                f" & {fmt(t1[k]['紧急购电量_kWh'])} \\\\")
        lines.append(r"    \midrule")
    if lines[-1] == r"    \midrule":
        lines.pop()
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    续表：全天费用分解（单位：元）。计划费按 $g^0_t$ 全额收取，"
        r"调整费按 $1.5p_t(x_t-g^0_t)$ 另计，二者与紧急费之和即当日实际总费用。",
        r"  \end{minipage}",
        r"  \par\vspace{4pt}",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    日期 & 初始计划量 & 最终常规量 & 紧急购电量 & 计划费 & 调整费 "
        r"& 当日合计费用 \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        s = sd[d]
        lines.append(
            f"    {DISP[d]} & {fmt(s['初始计划量_kWh'], 1)}"
            f" & {fmt(s['最终常规量_kWh'], 1)}"
            f" & {fmt(s['紧急购电量_kWh'], 1)}"
            f" & {fmt(s['计划费_元'], 0)} & {fmt(s['调整费_元'], 0)}"
            f" & \\textbf{{{fmt(s['合计费用_元'], 0)}}} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表 2：储能
def tab_storage(res: dict) -> str:
    """论文表 2：指定日期的实际充放电量与 0:00、24:00 储电量。"""
    sd = res["指定日期"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{储能设备在指定日期的实际充放电量（按四小时汇总，"
        r"单位：kWh）}",
        r"  \label{tab:p3-storage}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    时段 & \multicolumn{2}{c}{2025.3.20} & \multicolumn{2}{c}{2025.6.21}"
        r" & \multicolumn{2}{c}{2025.9.23} \\",
        r"     & 充电 & 放电 & 充电 & 放电 & 充电 & 放电 \\",
        r"    \midrule",
    ]
    # 按位置取，不按标签字符串取：求解器把末块标为 "20:00-0:00+1"（即次日 0 点，
    # 与 24:00 是同一时刻），论文里统一显示为 "20:00-24:00"。两者语义相同，且
    # 六个四小时块一一对应，故用位置索引最稳妥。
    per = {d: list(sd[d]["table2"]) for d in SPECIAL}
    for d in SPECIAL:
        assert len(per[d]) == len(BLOCK_LAB), (d, len(per[d]))
    for i, lab in enumerate(BLOCK_LAB):
        cells = " & ".join(
            f"{fmt(per[d][i]['充电量_kWh'])} & {fmt(per[d][i]['放电量_kWh'])}"
            for d in SPECIAL[:3])
        lines.append(f"    {texlab(lab)} & {cells} \\\\")
    lines += [r"    \midrule"]
    for lab, key in [(r"$0{:}00$ 储电量", "期初储电量_kWh"),
                     (r"$24{:}00$ 储电量", "期末储电量_kWh")]:
        cells = " & ".join(
            f"\\multicolumn{{2}}{{c}}{{{fmt(sd[d][key], 1)}}}"
            for d in SPECIAL[:3])
        lines.append(f"    {lab} & {cells} \\\\")
    lines += [r"  \end{tabular}", r"\end{table}", ""]

    d = "2025-12-21"
    s = sd[d]
    lines += [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{2025 年 12 月 21 日储能设备的实际充放电量与 "
        r"$0{:}00$、$24{:}00$ 储电量}",
        r"  \label{tab:p3-storage-dec}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    时段 & 充电量/kWh & 放电量/kWh \\",
        r"    \midrule",
    ]
    for i, lab in enumerate(BLOCK_LAB):
        lines.append(f"    {texlab(lab)} & {fmt(per[d][i]['充电量_kWh'])}"
                     f" & {fmt(per[d][i]['放电量_kWh'])} \\\\")
    lines += [
        r"    \midrule",
        f"    $0{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}"
        f"{{{fmt(s['期初储电量_kWh'], 1)}}} \\\\",
        f"    $24{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}"
        f"{{{fmt(s['期末储电量_kWh'], 1)}}} \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表 3：紧急购电
def tab_emg(res: dict) -> str:
    """论文表 3：指定日期的紧急购电事件。"""
    sd = res["指定日期"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{微网在指定日期的紧急购电事件（问题三，按同日连续时段"
        r"合并）}",
        r"  \label{tab:p3-emg}",
        r"  \footnotesize",
        r"  \begin{tabular}{llrl}",
        r"    \toprule",
        r"    日期 & 紧急购电时间段 & 紧急购电量/kWh & 该日紧急费/元 \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        s = sd[d]
        evs = s["events"]
        if not evs:
            lines.append(f"    {DISP[d]} & \\multicolumn{{2}}{{c}}{{无}}"
                         f" & 0.00 \\\\")
            continue
        n = len(evs)
        lines.append(
            f"    \\multirow{{{n}}}{{*}}{{{DISP[d]}}}"
            f" & {texlab(evs[0]['区间标签'])}"
            f" & {fmt(evs[0]['购电量_kWh'])}"
            f" & \\multirow{{{n}}}{{*}}{{{fmt(s['紧急费_元'], 0)}}} \\\\")
        for e in evs[1:]:
            lines.append(f"     & {texlab(e['区间标签'])}"
                         f" & {fmt(e['购电量_kWh'])} & \\\\")
        lines.append(r"    \midrule")
    if lines[-1] == r"    \midrule":
        lines.pop()
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：紧急购电量逐十分钟按 $5p_tr_t$ 计费后再把同日连续时段合并"
        r"成事件，合并不改变费用；合并后电量与逐段之和严格相等。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表 4：组合比较
def tab_combo(res: dict) -> str:
    """表：八种预报组合的费用对照，含增量收益与对照策略。"""
    rows = res["八种组合"]
    ctrl = res["对照_沿用0点预报版本"]
    rf = res["敏感性_退款口径"]
    base = next(r for r in rows if r["组合"] == "∅")["合计费用_元"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{八种预报组合在 2025 年 2 月 1 日--12 月 31 日的实际费用"
        r"（各组合单独标定参数，评价区间、负载模型、执行规则与计费口径完全一致）}",
        r"  \label{tab:p3-combo}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    使用的预报时刻 & 初始计划费/元 & 调整费/元 & 紧急费/元 "
        r"& 合计费用/元 & 相对 $\varnothing$ & 期末储电量/kWh \\",
        r"    \midrule",
    ]
    for r in rows:
        tot = r["合计费用_元"]
        rel = "---" if r["组合"] == "∅" else signed((tot - base) / base * 100)
        name = "仅 0:00" if r["组合"] == "∅" else r["组合"]
        lines.append(
            f"    {name} & {fmt(r['计划费_元'], 0)}"
            f" & {fmt(r['调整费_元'], 0)} & {fmt(r['紧急费_元'], 0)}"
            f" & \\textbf{{{fmt(tot, 0)}}} & {rel}"
            f" & {fmt(r['期末储电量_kWh'], 1)} \\\\")
    lines += [
        r"    \midrule",
        f"    对照：重新优化但仍用 0{{:}}00 版本 & --- & --- & ---"
        f" & \\textbf{{{fmt(ctrl['合计费用_元'], 0)}}} & "
        f"{signed((ctrl['合计费用_元'] - base) / base * 100)}"
        f" & {fmt(ctrl['期末储电量_kWh'], 1)} \\\\",
        r"    \midrule",
        f"    敏感性：退款口径（$x_t$ 可双向调整） & --- & --- & ---"
        f" & \\textbf{{{fmt(rf['合计费用_元'], 0)}}} & --- & --- \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：所有方案都使用 0:00 发布的预报；组合列出的时刻是\textbf{额外}"
        r"使用的版本。费用按主计费口径计算，\"合计费用\"已经包含初始计划费，"
        r"不能与计划费、调整费再相加。期末储电量用于说明各方案的跨日状态差异，"
        r"不能只比较费用。末行为计费口径的敏感性检查：退款口径的目标函数另含"
        r"调减收益，其总额与上表的\"相对\"列不可直接比较。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 表：校验
def tab_check(res: dict) -> str:
    """表：框架 8.2 节七项强制检查的实测最坏值。"""
    v = res["校验数值口径"]
    f = res["逐日校验失败天数"]
    items = [
        ("信息可用性", None, f["信息可用性"]),
        ("时间转换", None, f["时间转换"]),
        ("计划锁定", "主口径最大下调量_kWh", f["计划锁定"]),
        ("费用核对", "调整费最大复算偏差_元", f["费用核对"]),
        ("储能与供电", "供需平衡最大残差_kWh", f["储能与供电"]),
        ("状态衔接", "状态累计最大绝对偏差_kWh", f["状态衔接"]),
        ("结果一致性", None, f["结果一致性"]),
    ]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{框架要求的七项检查在主策略全部 334 个交付日上的实测结果}",
        r"  \label{tab:p3-check}",
        r"  \footnotesize",
        r"  \begin{tabular}{llr}",
        r"    \toprule",
        r"    检查项 & 实测最坏值 & 未通过天数 \\",
        r"    \midrule",
    ]
    unit = {"主口径最大下调量_kWh": " kWh", "调整费最大复算偏差_元": " 元",
            "供需平衡最大残差_kWh": " kWh", "状态累计最大绝对偏差_kWh": " kWh"}
    for name, key, bad in items:
        if key is None:
            lines.append(f"    {name} & 结构上恒成立 & {bad} \\\\")
        else:
            lines.append(f"    {name} & ${v[key]:.2e}$"
                         f"{unit[key]} & {bad} \\\\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：另有储电量越界最大量 "
        rf"${v['储电量越界最大量_kWh']:.2e}$~kWh、充放电越限最大量 "
        rf"${v['充放电越限最大量_kWh']:.2e}$~kWh、同时充放电时段数 "
        rf"${int(v['同时充放电时段数'])}$，均并入“储能与供电”一项。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


HEADER = [
    "% 本文件由 03_代码/p3_tables.py 自动生成，请勿手工修改。",
    "% 数据源：06_支撑材料/p3_results.json",
    "",
]


def main() -> None:
    with open(SUP / "p3_results.json", encoding="utf-8") as fh:
        res = json.load(fh)
    if "--split" in sys.argv:
        # 正文留题目要求的表 1/表 2/表 3 格式结果与组合比较；
        # 只把预报精度表与七项校验表移到附录，数据一条不少。
        body = HEADER + [
            tab_buy(res),
            tab_storage(res),
            tab_emg(res),
            tab_combo(res),
        ]
        tail = HEADER + [tab_skill(res), tab_check(res)]
        OUT_TEX.write_text("\n".join(body), encoding="utf-8")
        OUT_TEX_TAIL.write_text("\n".join(tail), encoding="utf-8")
        print(f"写入 {OUT_TEX}（正文：表 1/2/3 格式结果 + 组合比较）")
        print(f"写入 {OUT_TEX_TAIL}（附录：预报精度 + 七项校验）")
        return
    parts = HEADER + [
        tab_skill(res),
        tab_buy(res),
        tab_storage(res),
        tab_emg(res),
        tab_combo(res),
        tab_check(res),
    ]
    OUT_TEX.write_text("\n".join(parts), encoding="utf-8")
    print(f"写入 {OUT_TEX}")


if __name__ == "__main__":
    main()
