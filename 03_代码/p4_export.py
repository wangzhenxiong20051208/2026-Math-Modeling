# -*- coding: utf-8 -*-
"""问题四：附件 4 波动电价下分别重算问题二、问题三。

不写 result3.xlsx。输出：
  06_支撑材料/result4-2.xlsx
  06_支撑材料/result4-3.xlsx
  06_支撑材料/p4_results.json

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
    emergency_events,
    load_attach2,
    strategy_totals,
    validate_day,
    write_result2,
)
from p3_microgrid import ATT3, ROOT, TAU, load_all, price_row  # noqa: E402
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


def make_figures(price1, price4, dates, p2_daily, p3_daily) -> list[str]:
    from cumcm_plot import savefig, setup_plot
    import matplotlib.pyplot as plt
    setup_plot()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    hours = (np.arange(N) + 0.5) / 6.0

    # 选 2–12 月电价峰谷差最大的一天叠价格与购电
    span = price4.max(axis=1) - price4.min(axis=1)
    peak = REPORT_START + int(np.argmax(span[REPORT_START:REPORT_END]))
    date_lab = str(pd.Timestamp(dates[peak]).date()) if not isinstance(dates[peak], str) else dates[peak]
    g2 = np.array(p2_daily[peak - REPORT_START]["g"])
    g3 = np.array(p3_daily[peak - REPORT_START]["gA"])

    fig, ax1 = plt.subplots(figsize=(8.2, 4.2))
    ax1.plot(hours, price1, color="#7f8c8d", lw=1.4, label="附件1 固定电价")
    ax1.plot(hours, price4[peak], color="#c0392b", lw=1.6, label="附件4 当天电价")
    ax1.set_ylabel("电价（元/kWh）")
    ax1.set_xlabel("时刻（h）")
    ax2 = ax1.twinx()
    ax2.plot(hours, g2, color="#2980b9", lw=1.2, alpha=0.9, label="问题二计划购电")
    ax2.plot(hours, g3, color="#27ae60", lw=1.2, alpha=0.9, label="问题三调整购电")
    ax2.set_ylabel("购电量（kWh/10min）")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=8)
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
    return written


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="问题四：附件4重算问题二、三")
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
            for msgs in validate_day(rec).values():
                if msgs:
                    bad += 1
                    break
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
    print("saved", OUT_JSON, flush=True)

    p3_after = (OUT_P3.stat().st_mtime, OUT_P3.stat().st_size) if OUT_P3.exists() else None
    if p3_before != p3_after:
        raise RuntimeError("result3.xlsx 被改写了，停止")
    print("result3.xlsx 未改写", flush=True)


if __name__ == "__main__":
    main()
