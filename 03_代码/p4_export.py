# -*- coding: utf-8 -*-
<<<<<<< Updated upstream
"""问题四：附件 4 波动电价下分别重算问题二、问题三。

不写 result3.xlsx。输出：
  06_支撑材料/result4-2.xlsx
  06_支撑材料/result4-3.xlsx
  06_支撑材料/p4_results.json
=======
"""问题四：附件4下重算问题二、三。计划价与结算价拆开。

三臂（全部本脚本当场跑出，禁止抄死数字）：
  S1  计划附件1 + 结算附件1
  S2  计划附件1 + 结算附件4（同一物理计划只换计价）
  S3  计划附件4 + 结算附件4（提交 result4-2 / result4-3）

不写 result3.xlsx。
>>>>>>> Stashed changes

复现：
  python 03_代码/p4_export.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p1_microgrid import load_attach1  # noqa: E402
from p2_microgrid import (  # noqa: E402
    E_INIT,
    N,
    N_DAY,
    REPORT_END,
    REPORT_START,
    RiskParams,
    Forecaster,
    Simulator,
    build_error_table,
    day_summary,
<<<<<<< Updated upstream
    emergency_events,
=======
>>>>>>> Stashed changes
    load_attach2,
    strategy_totals,
    validate_day,
    write_result2,
)
<<<<<<< Updated upstream
from p3_microgrid import ATT3, ROOT, TAU, load_all, price_row  # noqa: E402
=======
from p3_microgrid import ATT3, ROOT, load_all, price_row  # noqa: E402
>>>>>>> Stashed changes
from p3_backtest import run_backtest  # noqa: E402
from p3_export import (  # noqa: E402
    BEST,
    BLOCKS,
    SPEC,
    block_label,
    export_result3,
    fmt_slot,
    validate_day as validate_p3_day,
)

ATT4 = ROOT / "01_题目" / "C题" / "附件" / "附件4.xlsx"
TEMPLATE42 = ROOT / "01_题目" / "C题" / "附件" / "附件5" / "result4-2.xlsx"
TEMPLATE43 = ROOT / "01_题目" / "C题" / "附件" / "附件5" / "result4-3.xlsx"
OUT_DIR = ROOT / "06_支撑材料"
OUT_P42 = OUT_DIR / "result4-2.xlsx"
OUT_P43 = OUT_DIR / "result4-3.xlsx"
OUT_P3 = OUT_DIR / "result3.xlsx"
OUT_JSON = OUT_DIR / "p4_results.json"
FIG_DIR = ROOT / "04_图"

<<<<<<< Updated upstream
# 附件 1 固定电价下已锁定的 2–12 月总费用（元），问题四对照表左列
P2_FIXED_TOTAL = 14021565.119404145
P3_FIXED_TOTAL = 13384828.869660389

# 问题二滚动标定日志（仅用附件 1 费用选出，问题四沿用，不按波动电价重标定）
# (起始日下标, alpha, rho, lam)；此前沿用上一段。n<31 用默认 λ=0.60
P2_CUTS = (
    (31, 0.80, 1.0, 0.00),   # 2025-02-01
    (73, 0.80, 0.0, 0.00),   # 2025-03-15
    (115, 0.80, 0.0, 0.00),  # 2025-04-26
    (157, 0.90, 1.0, 0.00),  # 2025-06-07
    (199, 0.80, 0.0, 0.00),  # 2025-07-19
    (241, 0.70, 0.0, 0.00),  # 2025-08-30
    (283, 0.80, 0.0, 0.00),  # 2025-10-11
    (325, 0.80, 0.0, 0.00),  # 2025-11-22
=======
# 仅作回归对照，论文数字必须用当场跑出的 S1
P2_S1_REGRESSION = 14021565.119404145
P3_S1_REGRESSION = 13384828.869660389

P2_CUTS = (
    (31, 0.80, 1.0, 0.00),
    (73, 0.80, 0.0, 0.00),
    (115, 0.80, 0.0, 0.00),
    (157, 0.90, 1.0, 0.00),
    (199, 0.80, 0.0, 0.00),
    (241, 0.70, 0.0, 0.00),
    (283, 0.80, 0.0, 0.00),
    (325, 0.80, 0.0, 0.00),
>>>>>>> Stashed changes
)


def day_price(price, n: int) -> np.ndarray:
    a = np.asarray(price, dtype=float)
    if a.ndim == 2:
        return a[n].copy()
    return a.copy()


def load_attach4() -> np.ndarray:
    df = pd.read_excel(ATT4, sheet_name=0, header=0)
    price = df.iloc[:, 1:].to_numpy(float)
    if price.shape != (365, 144):
        raise ValueError(f"附件 4 形状应为 (365, 144)，实际 {price.shape}")
    if not np.isfinite(price).all():
        raise ValueError("附件 4 存在空值或非有限值")
    if (price < 0).any():
        raise ValueError("附件 4 存在负电价")
    return price


def bill_p2(price_1d, g, r) -> tuple[float, float, float]:
    p = np.asarray(price_1d, dtype=float)
    plan = float(np.sum(p * g))
    emg = float(np.sum(5.0 * p * r))
    return plan, emg, plan + emg


def bill_p3(price_1d, gP, gA, r) -> tuple[float, float, float]:
    p = np.asarray(price_1d, dtype=float)
    up = np.clip(gA - gP, 0.0, None)
    down = np.clip(gP - gA, 0.0, None)
    pa = float(np.sum(p * gP + 1.5 * p * up - 0.5 * p * down))
    emg = float(np.sum(5.0 * p * r))
    return pa, emg, pa + emg


<<<<<<< Updated upstream
=======
def rebill_p3_day(out: dict, price_1d) -> tuple[float, float, float]:
    return bill_p3(price_1d, out["gP"], out["gA"], out["r"])


def decompose(s1: float, s2: float, s3: float) -> dict[str, float]:
    return {
        "s1": float(s1),
        "s2": float(s2),
        "s3": float(s3),
        "reprice": float(s2 - s1),
        "strategy": float(s3 - s2),
        "total": float(s3 - s1),
    }


>>>>>>> Stashed changes
def p2_params_for_day(n: int) -> RiskParams:
    rp = RiskParams()
    for start, alpha, rho, lam in P2_CUTS:
        if n >= start:
            rp = RiskParams(alpha=alpha, rho=rho, lam=lam)
    return rp


def run_p2_frozen(price, LOAD, PV, dates, verbose: bool = True):
    fo = Forecaster(LOAD, PV)
    eps = build_error_table(LOAD, PV, fo)
    sim = Simulator(LOAD, PV, price, dates, eps, fo)
    records = []
    e = E_INIT
    t0 = time.time()
    for n in range(N_DAY):
        rec = sim.run_day(n, p2_params_for_day(n), e)
        records.append(rec)
        e = rec.exec.E_end
        if verbose and (n + 1) % 30 == 0:
            print(f"    p2 {dates[n]} 累计 {n + 1} 天  用时 {time.time() - t0:.1f}s",
                  flush=True)
    return records


def _p2_summaries(records):
    summaries = []
    for rec in records[REPORT_START:REPORT_END]:
        s = day_summary(rec)
        s["plan_series"] = rec.exec.g.copy()
        summaries.append(s)
    return summaries


def export_p42(records, dates) -> None:
    shutil.copyfile(TEMPLATE42, OUT_P42)
    summaries = _p2_summaries(records)
    write_result2(summaries, dates, OUT_P42)
    from openpyxl import load_workbook
    wb = load_workbook(OUT_P42)
    if "全天汇总" in wb.sheetnames:
        del wb["全天汇总"]
    wb.save(OUT_P42)


def _spec_from_p3(res, dates, price):
    date_strs = [pd.Timestamp(d).date() for d in dates]
    spec = {}
    for s in SPEC:
        dt = pd.to_datetime(s).date()
        i = date_strs.index(dt)
        o = res[i]
        p = price_row(price, i)
        want_idx = [60, 72, 84, 96, 108, 120]
        t1 = [{"slot": fmt_slot(k), "gP": float(o["gP"][k]), "gA": float(o["gA"][k])}
              for k in want_idx]
        t2 = [{"block": block_label(a, z),
               "chg": float(o["c_act"][a:z].sum()),
               "dis": float(o["d_act"][a:z].sum())}
              for a, z in BLOCKS]
        r = o["r"]
        ev, t = [], 0
        while t < N:
            if r[t] > 1e-6:
                s0 = t
                while t < N and r[t] > 1e-6:
                    t += 1
                ev.append({
                    "start": fmt_slot(s0).split("-")[0],
                    "end": fmt_slot(t - 1).split("-")[1],
                    "kwh": float(r[s0:t].sum()),
                    "cost": float(np.sum(5 * p[s0:t] * r[s0:t])),
                })
            else:
                t += 1
        spec[s] = {
            "table1": t1,
            "Gplan": float(o["gP"].sum()),
            "Gadj": float(o["gA"].sum()),
            "Gemg": float(o["r"].sum()),
            "cost_plan_adj": float(o["cost_plan_adj"]),
            "cost_emg": float(o["cost_emg"]),
            "cost_total": float(o["cost_total"]),
            "table2": t2,
            "E0": float(o["E0"]),
            "E144": float(o["E"][-1]),
            "emg_events": ev,
        }
    return spec


def _daily_from_p2(records):
    rows = []
    for rec in records[REPORT_START:REPORT_END]:
        rows.append({
            "date": rec.date,
            "cost_plan": rec.exec.cost_plan,
            "cost_emg": rec.exec.cost_emg,
            "cost_total": rec.exec.cost_total,
            "g": rec.exec.g.tolist(),
            "r": rec.exec.r.tolist(),
        })
    return rows


def _daily_from_p3(res, dates):
    rows = []
    for d in range(REPORT_START, REPORT_END):
        o = res[d]
        rows.append({
            "date": str(pd.Timestamp(dates[d]).date()),
            "cost_plan_adj": float(o["cost_plan_adj"]),
            "cost_emg": float(o["cost_emg"]),
            "cost_total": float(o["cost_total"]),
            "gP": o["gP"].tolist(),
            "gA": o["gA"].tolist(),
            "r": o["r"].tolist(),
        })
    return rows


<<<<<<< Updated upstream
def make_figures(price1, price4, dates, p2_daily, p3_daily) -> list[str]:
=======
def rebill_p2_records(records, price) -> dict:
    plan = emg = 0.0
    daily = []
    for rec in records[REPORT_START:REPORT_END]:
        p = day_price(price, rec.n)
        cp, ce, tot = bill_p2(p, rec.exec.g, rec.exec.r)
        plan += cp
        emg += ce
        daily.append({
            "date": rec.date, "cost_plan": cp, "cost_emg": ce, "cost_total": tot,
            "g": rec.exec.g.tolist(), "r": rec.exec.r.tolist(),
        })
    return {"plan": plan, "emg": emg, "total": plan + emg, "daily": daily}


def rebill_p3_res(res, dates, price) -> dict:
    pa = emg = 0.0
    daily = []
    for d in range(REPORT_START, REPORT_END):
        p = price_row(price, d)
        cpa, ce, tot = rebill_p3_day(res[d], p)
        pa += cpa
        emg += ce
        daily.append({
            "date": str(pd.Timestamp(dates[d]).date()),
            "cost_plan_adj": cpa, "cost_emg": ce, "cost_total": tot,
            "gP": res[d]["gP"].tolist(), "gA": res[d]["gA"].tolist(),
            "r": res[d]["r"].tolist(),
        })
    return {"plan_adj": pa, "emg": emg, "total": pa + emg, "daily": daily}


def make_figures(price1, price4, dates, p2_s2, p2_s3, p3_s2, p3_s3,
                 p2_dec: dict, p3_dec: dict) -> list[str]:
>>>>>>> Stashed changes
    from cumcm_plot import savefig, setup_plot
    import matplotlib.pyplot as plt
    setup_plot()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    hours = (np.arange(N) + 0.5) / 6.0

<<<<<<< Updated upstream
    # 选 2–12 月电价峰谷差最大的一天叠价格与购电
    span = price4.max(axis=1) - price4.min(axis=1)
    peak = REPORT_START + int(np.argmax(span[REPORT_START:REPORT_END]))
    date_lab = str(pd.Timestamp(dates[peak]).date()) if not isinstance(dates[peak], str) else dates[peak]
    g2 = np.array(p2_daily[peak - REPORT_START]["g"])
    g3 = np.array(p3_daily[peak - REPORT_START]["gA"])
=======
    span = price4.max(axis=1) - price4.min(axis=1)
    peak = REPORT_START + int(np.argmax(span[REPORT_START:REPORT_END]))
    date_lab = str(pd.Timestamp(dates[peak]).date()) if not isinstance(dates[peak], str) else dates[peak]
    i = peak - REPORT_START
    g2 = np.array(p2_s3[i]["g"])
    g3 = np.array(p3_s3[i]["gA"])
>>>>>>> Stashed changes

    fig, ax1 = plt.subplots(figsize=(8.2, 4.2))
    ax1.plot(hours, price1, color="#7f8c8d", lw=1.4, label="附件1 固定电价")
    ax1.plot(hours, price4[peak], color="#c0392b", lw=1.6, label="附件4 当天电价")
    ax1.set_ylabel("电价（元/kWh）")
    ax1.set_xlabel("时刻（h）")
    ax2 = ax1.twinx()
<<<<<<< Updated upstream
    ax2.plot(hours, g2, color="#2980b9", lw=1.2, alpha=0.9, label="问题二计划购电")
    ax2.plot(hours, g3, color="#27ae60", lw=1.2, alpha=0.9, label="问题三调整购电")
=======
    ax2.plot(hours, g2, color="#2980b9", lw=1.2, alpha=0.9, label="问题二 S3 计划购电")
    ax2.plot(hours, g3, color="#27ae60", lw=1.2, alpha=0.9, label="问题三 S3 调整购电")
>>>>>>> Stashed changes
    ax2.set_ylabel("购电量（kWh/10min）")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
<<<<<<< Updated upstream
    ax1.set_title(f"图P4-1 {date_lab} 固定/波动电价与购电")
    ax1.set_xlim(0, 24)
    written.append(str(savefig("p4_fig_price_buy.png")))

    c2 = np.cumsum([row["cost_total"] for row in p2_daily]) / 1e4
    c3 = np.cumsum([row["cost_total"] for row in p3_daily]) / 1e4
    x = np.arange(1, len(c2) + 1)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(x, c2, color="#2980b9", lw=1.8, label="问题二 · 附件4")
    ax.plot(x, c3, color="#27ae60", lw=1.8, label="问题三 · 附件4")
    ax.axhline(P2_FIXED_TOTAL / 1e4, color="#2980b9", ls="--", lw=1.0,
               label=f"问题二 · 附件1  {P2_FIXED_TOTAL/1e4:.2f} 万")
    ax.axhline(P3_FIXED_TOTAL / 1e4, color="#27ae60", ls="--", lw=1.0,
               label=f"问题三 · 附件1  {P3_FIXED_TOTAL/1e4:.2f} 万")
    ax.set_xlabel("2–12 月累计天数")
    ax.set_ylabel("累计购电费（万元）")
    ax.set_title("图P4-2 全年累计费用：固定电价 vs 波动电价")
    ax.legend(loc="upper left", fontsize=8)
    written.append(str(savefig("p4_fig_cumcost.png")))

    # 紧急费落在高价时段的比例（按当天电价分位）
    def emg_high_share(daily, key_r, key_cost):
        high_cost = 0.0
        tot = 0.0
        for i, row in enumerate(daily):
            d = REPORT_START + i
            p = price4[d]
            r = np.asarray(row["r"], dtype=float)
            thr = np.quantile(p, 0.8)
            slot_cost = 5.0 * p * r
            tot += float(slot_cost.sum())
            high_cost += float(slot_cost[p >= thr].sum())
        return 0.0 if tot <= 0 else high_cost / tot

    s2 = emg_high_share(p2_daily, "r", "cost_emg")
    s3 = emg_high_share(p3_daily, "r", "cost_emg")
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    bars = ax.bar(["问题二", "问题三"], [s2 * 100, s3 * 100],
                  color=["#2980b9", "#27ae60"], alpha=0.85)
    for b, v in zip(bars, [s2, s3]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8,
                f"{v*100:.1f}%", ha="center", fontsize=10)
    ax.set_ylabel("占紧急费的比例（%）")
    ax.set_title("图P4-3 紧急费落在当天最高20%电价时段的比例")
    ax.set_ylim(0, 100)
    written.append(str(savefig("p4_fig_emg_highprice.png")))
=======
    ax1.set_title(f"图P4-1 {date_lab} 电价与按附件4重做的购电计划")
    ax1.set_xlim(0, 24)
    written.append(str(savefig("p4_fig_price_buy.png")))

    x = np.arange(1, len(p2_s2) + 1)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(x, np.cumsum([r["cost_total"] for r in p2_s2]) / 1e4,
            color="#2980b9", ls="--", lw=1.5, label="问题二 S2（计划附件1，结算附件4）")
    ax.plot(x, np.cumsum([r["cost_total"] for r in p2_s3]) / 1e4,
            color="#2980b9", lw=1.8, label="问题二 S3（计划+结算均附件4）")
    ax.plot(x, np.cumsum([r["cost_total"] for r in p3_s2]) / 1e4,
            color="#27ae60", ls="--", lw=1.5, label="问题三 S2（计划附件1，结算附件4）")
    ax.plot(x, np.cumsum([r["cost_total"] for r in p3_s3]) / 1e4,
            color="#27ae60", lw=1.8, label="问题三 S3（计划+结算均附件4）")
    ax.set_xlabel("2–12 月累计天数")
    ax.set_ylabel("累计购电费（万元）")
    ax.set_title("图P4-2 同一附件4结算下：沿用旧计划 vs 按新电价重做计划")
    ax.legend(loc="upper left", fontsize=8)
    written.append(str(savefig("p4_fig_cumcost.png")))

    labs = ["问题二", "问题三"]
    reprice = [p2_dec["reprice"] / 1e4, p3_dec["reprice"] / 1e4]
    strategy = [p2_dec["strategy"] / 1e4, p3_dec["strategy"] / 1e4]
    xx = np.arange(len(labs))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(xx - 0.18, reprice, 0.36, color="#7f8c8d", label="S2−S1 计价口径（同一计划）")
    ax.bar(xx + 0.18, strategy, 0.36, color="#c0392b", label="S3−S2 策略效应（同一结算）")
    ax.axhline(0.0, color="black", lw=0.6)
    ax.set_xticks(xx)
    ax.set_xticklabels(labs)
    ax.set_ylabel("费用变化（万元）")
    ax.set_title("图P4-3 波动电价总差分解：计价 vs 策略")
    ax.legend(fontsize=8)
    written.append(str(savefig("p4_fig_decompose.png")))
>>>>>>> Stashed changes
    return written


def main(argv=None) -> None:
<<<<<<< Updated upstream
    ap = argparse.ArgumentParser(description="问题四：附件4重算问题二、三")
=======
    ap = argparse.ArgumentParser(description="问题四：S1/S2/S3 三臂对照")
>>>>>>> Stashed changes
    ap.add_argument("--skip-p2", action="store_true")
    ap.add_argument("--skip-p3", action="store_true")
    ap.add_argument("--no-xlsx", action="store_true")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p3_before = (OUT_P3.stat().st_mtime, OUT_P3.stat().st_size) if OUT_P3.exists() else None

    price1 = load_attach1()["电价"].to_numpy(float)
    price4 = load_attach4()
    print(f"附件4 电价 min={price4.min():.4f} max={price4.max():.4f} 元/kWh", flush=True)

    LOAD, PV, dates2 = load_attach2()
    payload = {
        "attach4": {"min": float(price4.min()), "max": float(price4.max())},
<<<<<<< Updated upstream
        "p2_fixed": {"total": P2_FIXED_TOTAL, "wan": P2_FIXED_TOTAL / 1e4},
        "p3_fixed": {"total": P3_FIXED_TOTAL, "wan": P3_FIXED_TOTAL / 1e4},
    }

    p2_daily = None
    if not args.skip_p2:
        print("问题二 · 冻结 α,ρ,λ 日程 · 附件4", flush=True)
        recs = run_p2_frozen(price4, LOAD, PV, dates2)
        tot = strategy_totals(recs, REPORT_START, REPORT_END)
        print(f"  Feb-Dec 计划 {tot['计划购电费_元']:.2f}  紧急 {tot['紧急购电费_元']:.2f}"
              f"  合计 {tot['合计购电费_元']:.2f}", flush=True)
        bad = 0
        for rec in recs[REPORT_START:REPORT_END]:
=======
        "arms": {
            "S1": "计划附件1 + 结算附件1（本脚本当场跑出）",
            "S2": "计划附件1 + 结算附件4（同一物理计划只换计价）",
            "S3": "计划附件4 + 结算附件4（提交 result4-2/4-3）",
        },
    }

    p2_s2_daily = p2_s3_daily = None
    p2_dec = None
    if not args.skip_p2:
        print("问题二 S1 · 冻结日程 · 计划+结算=附件1", flush=True)
        recs1 = run_p2_frozen(price1, LOAD, PV, dates2)
        t1 = strategy_totals(recs1, REPORT_START, REPORT_END)
        print(f"  S1 合计 {t1['合计购电费_元']:.2f}（回归对照 {P2_S1_REGRESSION:.2f}）", flush=True)
        print("问题二 S2 · 同一 S1 计划 · 结算=附件4", flush=True)
        s2 = rebill_p2_records(recs1, price4)
        print(f"  S2 合计 {s2['total']:.2f}  计价差 S2-S1={s2['total']-t1['合计购电费_元']:.2f}",
              flush=True)
        print("问题二 S3 · 冻结日程 · 计划+结算=附件4", flush=True)
        recs3 = run_p2_frozen(price4, LOAD, PV, dates2)
        t3 = strategy_totals(recs3, REPORT_START, REPORT_END)
        bad = 0
        for rec in recs3[REPORT_START:REPORT_END]:
>>>>>>> Stashed changes
            for msgs in validate_day(rec).values():
                if msgs:
                    bad += 1
                    break
<<<<<<< Updated upstream
        print(f"  问题二校验：{bad} 天有问题", flush=True)
        payload["p2_flex"] = {
            "plan": tot["计划购电费_元"],
            "emg": tot["紧急购电费_元"],
            "total": tot["合计购电费_元"],
            "wan": tot["合计购电费_元"] / 1e4,
            "validate_bad": bad,
        }
        p2_daily = _daily_from_p2(recs)
        if not args.no_xlsx:
            export_p42(recs, dates2)
            print("  saved", OUT_P42, flush=True)

    p3_daily = None
    if not args.skip_p3:
        print("问题三 · α=0.6 分时段 Q_t 三次调整 · 附件4", flush=True)
        _p1, dates3, load_kw, pv_kw, fc = load_all()
        assert ATT3.exists()
        res = run_backtest(price4, dates3, load_kw, pv_kw, fc,
                           day_range=range(0, 365), **BEST,
                           use_adjust=True, adjust_mask=(True, True, True))
        tot = sum(res[d]["cost_total"] for d in range(31, 365))
        pa = sum(res[d]["cost_plan_adj"] for d in range(31, 365))
        emg = sum(res[d]["cost_emg"] for d in range(31, 365))
        print(f"  Feb-Dec 合同 {pa:.2f}  紧急 {emg:.2f}  合计 {tot:.2f}", flush=True)
        bad = 0
        for d in range(31, 365):
            probs = validate_p3_day(d, price4, load_kw, pv_kw, res[d])
            if probs:
                bad += 1
                print(dates3[d].date(), probs)
        print(f"  问题三校验：334天中{bad}天有问题", flush=True)
        payload["p3_flex"] = {
            "plan_adj": pa,
            "emg": emg,
            "total": tot,
            "wan": tot / 1e4,
            "validate_bad": bad,
        }
        payload["spec"] = _spec_from_p3(res, dates3, price4)
        p3_daily = _daily_from_p3(res, dates3)
        if not args.no_xlsx:
            shutil.copyfile(TEMPLATE43, OUT_P43)
            export_result3(price4, dates3, res, out_xlsx=OUT_P43, template=TEMPLATE43)
            print("  saved", OUT_P43, flush=True)

    if "p2_flex" in payload and "p3_flex" in payload:
        payload["p3_minus_p2_flex"] = payload["p3_flex"]["total"] - payload["p2_flex"]["total"]

    if not args.no_fig and p2_daily is not None and p3_daily is not None:
        figs = make_figures(price1, price4, dates2, p2_daily, p3_daily)
        payload["figures"] = figs
        print("  figs", figs, flush=True)

    # json 不落盘逐时序列（太大）；每日费用单独写 csv
    slim = {k: v for k, v in payload.items()}
    if p2_daily is not None:
        pd.DataFrame([{k: row[k] for k in ("date", "cost_plan", "cost_emg", "cost_total")}
                      for row in p2_daily]).to_csv(OUT_DIR / "p4_p2_daily.csv",
                                                   index=False, encoding="utf-8-sig")
    if p3_daily is not None:
        pd.DataFrame([{k: row[k] for k in ("date", "cost_plan_adj", "cost_emg", "cost_total")}
                      for row in p3_daily]).to_csv(OUT_DIR / "p4_p3_daily.csv",
                                                   index=False, encoding="utf-8-sig")
    OUT_JSON.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
=======
        print(f"  S3 合计 {t3['合计购电费_元']:.2f}  校验问题天数 {bad}", flush=True)
        p2_dec = decompose(t1["合计购电费_元"], s2["total"], t3["合计购电费_元"])
        print(f"  分解 计价 {p2_dec['reprice']:.2f}  策略 {p2_dec['strategy']:.2f}  "
              f"合计 {p2_dec['total']:.2f}", flush=True)
        payload["p2"] = {
            "S1": {"plan": t1["计划购电费_元"], "emg": t1["紧急购电费_元"],
                   "total": t1["合计购电费_元"]},
            "S2": {"plan": s2["plan"], "emg": s2["emg"], "total": s2["total"]},
            "S3": {"plan": t3["计划购电费_元"], "emg": t3["紧急购电费_元"],
                   "total": t3["合计购电费_元"], "validate_bad": bad},
            "decompose": p2_dec,
        }
        p2_s2_daily = s2["daily"]
        p2_s3_daily = _daily_from_p2(recs3)
        if not args.no_xlsx:
            export_p42(recs3, dates2)
            print("  saved", OUT_P42, flush=True)

    p3_s2_daily = p3_s3_daily = None
    p3_dec = None
    if not args.skip_p3:
        _p1, dates3, load_kw, pv_kw, fc = load_all()
        assert ATT3.exists()
        print("问题三 S1 · α=0.6 分时段Q · 计划+结算=附件1", flush=True)
        res1 = run_backtest(price1, dates3, load_kw, pv_kw, fc,
                            day_range=range(0, 365), **BEST,
                            use_adjust=True, adjust_mask=(True, True, True))
        s1_pa = sum(res1[d]["cost_plan_adj"] for d in range(31, 365))
        s1_emg = sum(res1[d]["cost_emg"] for d in range(31, 365))
        s1_tot = s1_pa + s1_emg
        print(f"  S1 合计 {s1_tot:.2f}（回归对照 {P3_S1_REGRESSION:.2f}）", flush=True)
        print("问题三 S2 · 同一 S1 计划 · 结算=附件4", flush=True)
        s2 = rebill_p3_res(res1, dates3, price4)
        print(f"  S2 合计 {s2['total']:.2f}  计价差 S2-S1={s2['total']-s1_tot:.2f}",
              flush=True)
        print("问题三 S3 · α=0.6 分时段Q · 计划+结算=附件4", flush=True)
        res3 = run_backtest(price4, dates3, load_kw, pv_kw, fc,
                            day_range=range(0, 365), **BEST,
                            use_adjust=True, adjust_mask=(True, True, True))
        s3_pa = sum(res3[d]["cost_plan_adj"] for d in range(31, 365))
        s3_emg = sum(res3[d]["cost_emg"] for d in range(31, 365))
        s3_tot = s3_pa + s3_emg
        bad = 0
        for d in range(31, 365):
            probs = validate_p3_day(d, price4, load_kw, pv_kw, res3[d])
            if probs:
                bad += 1
                print(dates3[d].date(), probs)
        print(f"  S3 合计 {s3_tot:.2f}  校验 {bad} 天有问题", flush=True)
        p3_dec = decompose(s1_tot, s2["total"], s3_tot)
        print(f"  分解 计价 {p3_dec['reprice']:.2f}  策略 {p3_dec['strategy']:.2f}  "
              f"合计 {p3_dec['total']:.2f}", flush=True)
        payload["p3"] = {
            "S1": {"plan_adj": s1_pa, "emg": s1_emg, "total": s1_tot},
            "S2": {"plan_adj": s2["plan_adj"], "emg": s2["emg"], "total": s2["total"]},
            "S3": {"plan_adj": s3_pa, "emg": s3_emg, "total": s3_tot, "validate_bad": bad},
            "decompose": p3_dec,
        }
        payload["spec"] = _spec_from_p3(res3, dates3, price4)
        p3_s2_daily = s2["daily"]
        p3_s3_daily = _daily_from_p3(res3, dates3)
        if not args.no_xlsx:
            shutil.copyfile(TEMPLATE43, OUT_P43)
            export_result3(price4, dates3, res3, out_xlsx=OUT_P43, template=TEMPLATE43)
            print("  saved", OUT_P43, flush=True)

    if not args.no_fig and p2_s2_daily and p3_s2_daily and p2_dec and p3_dec:
        figs = make_figures(price1, price4, dates2,
                            p2_s2_daily, p2_s3_daily, p3_s2_daily, p3_s3_daily,
                            p2_dec, p3_dec)
        payload["figures"] = figs
        print("  figs", figs, flush=True)

    def _cost_only(rows, keys):
        return [{k: row[k] for k in keys} for row in rows]

    if p2_s2_daily is not None:
        pd.DataFrame(_cost_only(p2_s2_daily, ("date", "cost_plan", "cost_emg", "cost_total"))
                     ).to_csv(OUT_DIR / "p4_p2_s2_daily.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(_cost_only(p2_s3_daily, ("date", "cost_plan", "cost_emg", "cost_total"))
                     ).to_csv(OUT_DIR / "p4_p2_daily.csv", index=False, encoding="utf-8-sig")
    if p3_s2_daily is not None:
        pd.DataFrame(_cost_only(p3_s2_daily, ("date", "cost_plan_adj", "cost_emg", "cost_total"))
                     ).to_csv(OUT_DIR / "p4_p3_s2_daily.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(_cost_only(p3_s3_daily, ("date", "cost_plan_adj", "cost_emg", "cost_total"))
                     ).to_csv(OUT_DIR / "p4_p3_daily.csv", index=False, encoding="utf-8-sig")
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
>>>>>>> Stashed changes
    print("saved", OUT_JSON, flush=True)

    p3_after = (OUT_P3.stat().st_mtime, OUT_P3.stat().st_size) if OUT_P3.exists() else None
    if p3_before != p3_after:
        raise RuntimeError("result3.xlsx 被改写了，停止")
    print("result3.xlsx 未改写", flush=True)


if __name__ == "__main__":
    main()
