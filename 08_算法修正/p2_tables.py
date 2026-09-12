# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题二 —— 由求解结果直接生成论文表格片段。

写出 05_论文/CUMCMThesis/p2_tables.tex，由 main.tex 以 \input 引入，
使论文中的每个数字都与 result2/p2_results.json 严格同源，避免手工转录错误。

运行：python3 03_代码/p2_tables.py （需先运行 p2_microgrid.py）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_microgrid import BLOCKS, block_label, N  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SUP = ROOT / "08_算法修正" / "输出"
OUT_TEX = ROOT / "08_算法修正" / "输出" / "论文表格" / "p2_tables.tex"
OUT_TEX_TAIL = ROOT / "08_算法修正" / "输出" / "论文表格" / "p2_tables_appendix.tex"

SPECIAL = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
DISP = {"2025-03-20": "2025.3.20", "2025-06-21": "2025.6.21",
        "2025-09-23": "2025.9.23", "2025-12-21": "2025.12.21"}

# 表 1 中六个指定时段的展示次序
SIX = ["10:00-10:10", "12:00-12:10", "14:00-14:10",
       "16:00-16:10", "18:00-18:10", "20:00-20:10"]


def fmt(v: float, nd: int = 2) -> str:
    return f"{v:,.{nd}f}"


def texlab(s: str) -> str:
    """把 '20:20-20:40' 这类时间标签转成 LaTeX 安全的写法。"""
    return s.replace(":", "{:}")


def signed(pct: float) -> str:
    """把百分比写成带显式正负号的 LaTeX 形式（负号不能与 '+' 拼成 '+-'）。"""
    return f"{pct:+.2f}\\%".replace("+-", "-")


def tab_result1(res: dict, det: pd.DataFrame) -> str:
    """表：四个指定日期的计划购电量、全天电量与费用。"""
    sd = res["special_dates"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{微网在指定日期的计划购电量、全天购电量与购电费（问题二）}",
        r"  \label{tab:p2-buy}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    日期 & 10:00 & 12:00 & 14:00 & 16:00 & 18:00 & 20:00 \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        s = sd[d]
        t1 = {r["时间段"]: r["计划购电量_kWh"] for r in s["table1"]}
        cells = " & ".join(fmt(t1[k]) for k in SIX)
        lines.append(f"    {DISP[d]} & {cells} \\\\")
    lines += [
        r"    \midrule",
        r"    \multicolumn{7}{l}{\textit{全天汇总（单位：kWh，费用单位：元）}} \\",
        r"    \midrule",
        r"    日期 & \multicolumn{2}{c}{计划购电量} & \multicolumn{2}{c}{紧急购电量}"
        r" & \multicolumn{2}{c}{合计购电费} \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        s = sd[d]
        lines.append(
            f"    {DISP[d]} & \\multicolumn{{2}}{{c}}{{{fmt(s['plan_kwh'])}}}"
            f" & \\multicolumn{{2}}{{c}}{{{fmt(s['emg_kwh'])}}}"
            f" & \\multicolumn{{2}}{{c}}{{{fmt(s['cost_total'])}}} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tab_result2(res: dict, det: pd.DataFrame) -> str:
    """表：四个指定日期的储能充放电量与 0:00/24:00 储电量。"""
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{储能设备在指定日期的充放电量及 $0{:}00$ 和 "
        r"$24{:}00$ 的储电量（问题二）}",
        r"  \label{tab:p2-storage}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrrr}",
        r"    \toprule",
        r"    时段 & \multicolumn{2}{c}{2025.3.20} & "
        r"\multicolumn{2}{c}{2025.6.21} & \multicolumn{2}{c}{2025.9.23} \\",
        r"     & 充电 & 放电 & 充电 & 放电 & 充电 & 放电 \\",
        r"    \midrule",
    ]
    blocks = [block_label(a, b) for a, b in BLOCKS]
    per: dict[str, dict[str, tuple[float, float]]] = {}
    for d in SPECIAL:
        g = det[det["日期"] == d]
        c = g["实际充电_kWh"].to_numpy()
        dd = g["实际放电_kWh"].to_numpy()
        per[d] = {lab: (float(c[a:b].sum()), float(dd[a:b].sum()))
                  for lab, (a, b) in zip(blocks, BLOCKS)}
    for lab in blocks:
        cells = " & ".join(
            f"{fmt(per[d][lab][0])} & {fmt(per[d][lab][1])}"
            for d in ["2025-03-20", "2025-06-21", "2025-09-23"])
        lines.append(f"    {texlab(lab)} & {cells} \\\\")
    lines += [r"    \midrule"]
    for lab, key in [("$0{:}00$ 储电量", "E0"), ("$24{:}00$ 储电量", "E144")]:
        cells = " & ".join(
            f"\\multicolumn{{2}}{{c}}{{{fmt(res['special_dates'][d][key])}}}"
            for d in ["2025-03-20", "2025-06-21", "2025-09-23"])
        lines.append(f"    {lab} & {cells} \\\\")
    lines += [r"  \end{tabular}", r"\end{table}", ""]

    # 12 月 21 日单独一表，保持列宽可读
    d = "2025-12-21"
    s = res["special_dates"][d]
    lines += [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{2025 年 12 月 21 日储能设备的充放电量及 "
        r"$0{:}00$ 和 $24{:}00$ 的储电量}",
        r"  \label{tab:p2-storage-dec}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrr}",
        r"    \toprule",
        r"    时段 & 充电量/kWh & 放电量/kWh \\",
        r"    \midrule",
    ]
    for lab in blocks:
        c, dd = per[d][lab]
        lines.append(f"    {texlab(lab)} & {fmt(c)} & {fmt(dd)} \\\\")
    lines += [
        r"    \midrule",
        f"    $0{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}{{{fmt(s['E0'])}}} \\\\",
        f"    $24{{:}}00$ 储电量/kWh & \\multicolumn{{2}}{{c}}{{{fmt(s['E144'])}}} \\\\",
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def tab_result3(res: dict) -> str:
    """表：四个指定日期的紧急购电事件（合并后）。"""
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{微网在指定日期的紧急购电量（问题二，按连续时段"
        r"合并）}",
        r"  \label{tab:p2-emg}",
        r"  \footnotesize",
        r"  \begin{tabular}{llrl}",
        r"    \toprule",
        r"    日期 & 紧急购电时间段 & 紧急购电量/kWh & 该日紧急费/元 \\",
        r"    \midrule",
    ]
    for d in SPECIAL:
        s = res["special_dates"][d]
        evs = s["events"]
        if not evs:
            lines.append(
                f"    {DISP[d]} & \\multicolumn{{2}}{{c}}{{无}}"
                f" & 0.00 \\\\")
            continue
        n = len(evs)
        lines.append(
            f"    \\multirow{{{n}}}{{*}}{{{DISP[d]}}}"
            f" & {texlab(evs[0]['区间标签'])}"
            f" & {fmt(evs[0]['购电量_kWh'])}"
            f" & \\multirow{{{n}}}{{*}}{{{fmt(s['cost_emg'])}}} \\\\")
        for e in evs[1:]:
            lines.append(
                f"     & {texlab(e['区间标签'])}"
                f" & {fmt(e['购电量_kWh'])} & \\\\")
        lines.append(r"    \midrule")
    if lines[-1] == r"    \midrule":
        lines.pop()
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        r"    注：紧急购电量按框架要求逐段计算后，将同日连续发生紧急购电的时段"
        r"合并为一个事件；合并后电量与逐段之和严格相等。",
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def tab_strategy(res: dict) -> str:
    """表：各对照策略的费用与电量对比。"""
    st = res["对照策略"]
    keys = ["本文风险修正策略（主模型）",
            "预测均值策略（不加分位风险余量）",
            "无储能（同样提前计划并五倍补缺）",
            "事后理想（完全预知当天净负荷）"]
    short = {"本文风险修正策略（主模型）": "本文风险修正策略（主模型）",
             "预测均值策略（不加分位风险余量）": "预测均值策略（不加风险余量）",
             "无储能（同样提前计划并五倍补缺）": "无储能（仍提前计划、五倍补缺）",
             "事后理想（完全预知当天净负荷）": "事后理想（完全预知当天净负荷）"}
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{各策略在 2025 年 2 月 1 日--12 月 31 日的"
        r"费用对照（同一预测器、同一实时执行规则、各自单独标定）}",
        r"  \label{tab:p2-strategy}",
        r"  \footnotesize",
        r"  \begin{tabular}{lrrrrr}",
        r"    \toprule",
        r"    策略 & 计划购电费/元 & 紧急购电费/元 & 合计费用/元 & 期末储电量/kWh"
        r" & 相对本模型费用 \\",
        r"    \midrule",
    ]
    base = st[keys[0]]["合计购电费_元"]
    for k in keys:
        v = st[k]
        tot = v["合计购电费_元"]
        rel = "---" if k == keys[0] else signed((tot - base) / base * 100)
        e = v["期末储电量_kWh"]
        es = "---" if not np.isfinite(e) else fmt(e, 1)
        lines.append(
            f"    {short[k]} & {fmt(v['计划购电费_元'], 0)}"
            f" & {fmt(v['紧急购电费_元'], 0)} & \\textbf{{{fmt(tot, 0)}}}"
            f" & {es} & {rel} \\\\")
    # 事后理想的期末储电量并非「随日期变动而无单一数值」，而是被放到下限附近；
    # 用实测值如实说明，避免读者把它误当成可执行方案。
    idl = st[keys[3]]
    ebar = idl.get("日末日均储电量_kWh")
    if ebar is not None and np.isfinite(ebar):
        note = (r"    注：“事后理想”用当天实际净负荷替换预测值求解同一日前 MILP。"
                r"它每天仍从主策略的实际日初储电量出发、且不要求日末保留电量，"
                rf"故日末储电量被放到下限附近（日均 ${fmt(ebar, 1)}$~kWh），"
                r"属于\textbf{不可执行的乐观下界}，仅作参照。")
    else:
        note = (r"    注：“事后理想”用当天实际净负荷替换预测值求解同一日前 MILP，"
                r"其费用不构成可执行方案，仅作乐观下界参考。")
    # 末列以本模型费用为分母。另报以各基准费用为分母的常规节约率，两者分母不同，
    # 在表注里写明，避免读者把「相对本模型费用」误读成「较该策略的节约率」。
    save_avg = abs((st[keys[1]]["合计购电费_元"] - base)
                   / st[keys[1]]["合计购电费_元"] * 100)
    save_nos = abs((st[keys[2]]["合计购电费_元"] - base)
                   / st[keys[2]]["合计购电费_元"] * 100)
    note += (r" 末列以\textbf{本模型费用}为分母；若改以\textbf{各基准费用}为分母，"
             rf"节约率为 ${save_avg:.2f}\%$（较预测均值策略）与 "
             rf"${save_nos:.2f}\%$（较无储能策略）。两种分母口径不同，勿混用。")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"  \par\vspace{2pt}",
        r"  \begin{minipage}{.92\textwidth}\footnotesize",
        note,
        r"  \end{minipage}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


def tab_totals(res: dict) -> str:
    """表：正式区间全年汇总。"""
    t = res["totals"]
    acc = res["预测精度"]
    err = res.get("预测误差结构", {})
    rows = [
        ("正式区间", f"{res['reported_range'][0]} 至 {res['reported_range'][1]}"
                     f"（{res['n_days']} 天）"),
        ("计划购电量", f"{fmt(t['计划购电量_kWh'])} kWh"),
        ("计划购电费", f"{fmt(t['计划购电费_元'])} 元"),
        ("紧急购电量", f"{fmt(t['紧急购电量_kWh'])} kWh"),
        ("紧急购电费", f"{fmt(t['紧急购电费_元'])} 元"),
        ("合计购电量", f"{fmt(t['合计购电量_kWh'])} kWh"),
        ("合计购电费", f"\\textbf{{{fmt(t['合计购电费_元'])} 元}}"),
        ("紧急费占比", f"{t['紧急费占比'] * 100:.2f}\\%"),
        ("弃用电量", f"{fmt(t['弃电量_kWh'])} kWh"),
        ("期末储电量", f"{fmt(t['期末储电量_kWh'])} kWh"),
        ("负载预测 MAE", f"{fmt(acc['负载MAE_kWh每日'], 1)} kWh/日"
                        f"（{acc['负载相对误差'] * 100:.2f}\\%）"),
        ("光伏预测 MAE", f"{fmt(acc['光伏MAE_kWh每日'], 1)} kWh/日"
                        f"（{acc['光伏相对误差'] * 100:.2f}\\%）"),
        ("净负荷预测 MAE", f"{fmt(acc['净负荷MAE_kWh每日'], 1)} kWh/日"),
    ]
    if err:
        # 框架文档 7.1 节要求检查「净负荷被低估的情况」：逐时段口径，分方向统计
        rows += [
            ("净负荷被低估（逐时段）",
             f"{err['低估时段占比'] * 100:.1f}\\% 的时段，"
             f"{fmt(err['低估电量_kWh每日'], 1)} kWh/日"),
            ("净负荷被高估（逐时段）",
             f"{err['高估时段占比'] * 100:.1f}\\% 的时段，"
             f"{fmt(err['高估电量_kWh每日'], 1)} kWh/日"),
            ("风险余量为负的时段",
             f"{err['风险余量负值时段占比'] * 100:.1f}\\%"
             f"（最小 {fmt(err['风险余量最小值_kWh'], 1)}、"
             f"最大 {fmt(err['风险余量最大值_kWh'], 1)} kWh）"),
        ]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{问题二正式区间（2025 年 2 月 1 日--12 月 31 日）"
        r"的总体结果与预测精度}",
        r"  \label{tab:p2-totals}",
        r"  \footnotesize",
        r"  \begin{tabular}{ll}",
        r"    \toprule",
        r"    项目 & 数值 \\",
        r"    \midrule",
    ]
    for k, v in rows:
        lines.append(f"    {k} & {v} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tab_checks(res: dict) -> str:
    """表：框架文档 7.2 节六项强制检查的执行结果。"""
    names = {
        "1_信息时点": ("信息时点", "预测、误差分位数与参数仅用当天之前的数据；"
                                 "计划购电量在 $0{:}00$ 后冻结"),
        "2_物理可行性": ("物理可行性", "逐段供需平衡；储电量在 $[1200,10800]$~kWh；"
                                     "充放电量 $\\le M$ 且同段互斥"),
        "3_跨日连续性": ("跨日连续性", "次日 $0{:}00$ 储电量严格等于前日 $24{:}00$ "
                                     "实际末值"),
        "4_状态累计": ("状态累计", "$E_{n,144}-E_{n,0}=\\eta_c\\sum_t c_{n,t}"
                                 "-\\frac{1}{\\eta_d}\\sum_t d_{n,t}$ 逐日成立"),
        "5_费用一致性": ("费用一致性", "用未舍入数据复算计划费与紧急费；"
                                     "弃电不退款；储备罚不计入账单"),
        "6_汇总一致性": ("汇总一致性", "日期完整无错位；紧急事件合并前后电量一致"),
    }
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{问题二六项强制检查的执行结果}",
        r"  \label{tab:p2-checks}",
        r"  \footnotesize",
        r"  \begin{tabular}{llc}",
        r"    \toprule",
        r"    检查项 & 内容 & 结果 \\",
        r"    \midrule",
    ]
    for k, ok in res["检查"].items():
        nm, desc = names[k]
        lines.append(f"    {nm} & {desc} & {'通过' if ok else '\\textbf{{未通过}}'} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def tab_calib(res: dict) -> str:
    """表：滚动参数标定的选中结果。"""
    cal = res["参数标定"]
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{滚动参数标定的选中结果"
        r"（窗口 35 天，每 42 天重标定一次）}",
        r"  \label{tab:p2-calib}",
        r"  \begin{tabular}{lcccc}",
        r"    \toprule",
        r"    标定日 & $\alpha$ & $\rho$ & $\lambda$ & 窗口内选中策略 \\",
        r"    \midrule",
    ]
    cnt: dict[str, int] = {}
    for row in cal:
        p = row["选中参数"]
        parts = dict(kv.strip().split("=") for kv in p.split(","))
        a = parts["α"].strip()
        cnt[a] = cnt.get(a, 0) + 1
        lines.append(f"    {row['标定日']} & {a} & {parts['ρ']}"
                     f" & {parts['λ']} & {p} \\\\")
    lines += [r"    \midrule"]
    tot = sum(cnt.values())
    dist = "、".join(f"$\\alpha={a}$ {n} 次" for a, n in sorted(cnt.items()))
    lines.append(
        f"    \\multicolumn{{5}}{{l}}{{\\footnotesize 全年共标定 {tot} 次：{dist}"
        f"；$\\lambda$ 在所有标定中均取 $0.00$}} \\\\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def main() -> None:
    with open(SUP / "p2_results.json", encoding="utf-8") as f:
        res = json.load(f)
    det = pd.read_csv(SUP / "p2_detail.csv", encoding="utf-8-sig")

    header = [
        "% 本文件由 03_代码/p2_tables.py 自动生成，请勿手工编辑。",
        "% 数据来源：06_支撑材料/result2.xlsx, p2_results.json, p2_detail.csv",
        "",
    ]
    # 正文（规范第四条：正文不超过 30 页）只保留题目要求的表 1/表 2/表 3
    # 格式结果与直接支撑结论的对照表；总体结果表、标定表与校验表属于过程记录，
    # 结论均已在正文给出，故移到附录，数据一条不少。
    # --split 打开该模式，默认仍全部写正文。
    if "--split" in sys.argv:
        body = header + [
            tab_result1(res, det),
            tab_result2(res, det),
            tab_result3(res),
        ]
        tail = header + [tab_strategy(res), tab_totals(res),
                         tab_checks(res), tab_calib(res)]
        OUT_TEX.write_text("\n".join(body), encoding="utf-8")
        OUT_TEX_TAIL.write_text("\n".join(tail), encoding="utf-8")
        print(f"已写出 {OUT_TEX.relative_to(ROOT)}（正文 3 张表）")
        print(f"已写出 {OUT_TEX_TAIL.relative_to(ROOT)}（附录 4 张表）")
    else:
        parts = header + [
            tab_totals(res),
            tab_result1(res, det),
            tab_result2(res, det),
            tab_result3(res),
            tab_strategy(res),
            tab_checks(res),
            tab_calib(res),
        ]
        OUT_TEX.write_text("\n".join(parts), encoding="utf-8")
        print(f"已写出 {OUT_TEX.relative_to(ROOT)}")
    print(f"  合计购电费 {res['totals']['合计购电费_元']:,.2f} 元")
    for k, ok in res["检查"].items():
        print(f"  {k}: {'通过' if ok else '未通过'}")


if __name__ == "__main__":
    main()
