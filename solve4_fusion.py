# -*- coding: utf-8 -*-
"""问题四 融合最优版（一步出 result4-2 / result4-3）
================================================================
设计思路（融合两家长处）：
  4-2：p2 框架 + P2_CUTS 八段冻结参数 + 因果电价预测
       —— p2 框架在固定电价基准上就比 p3 无调整单参数低约 19 万，
          八段参数日程应对季节性，已在问题二定稿验证。
  4-3：分时段 Qvec 风险准备 + 1 月标定 + 因果电价预测
       —— 每个 10 分钟时段用自己历史误差的 alpha 分位数 Q_t，
          比全天一个标量 Q 精细；alpha/rho 仅由 1 月预热期标定。
  电价预测：统一用 forecast_attach4（因果，hat[n] 只用 price4[:n]，
            第 0 天退回附件 1，窗口 28 天、按周指数衰减、只保留同星期）。
  三臂分解：S1 固定决策+固定结算（实跑）/ S2 固定决策+波动结算（复用 S1 物理计划）
            / S3 预测决策+波动结算（提交值）/ S3* 上帝视角（仅对照，不上报）。
合规性：
  [A1] S1 当场实跑，不硬编码；
  [A2] 计划价与结算价通过 bill_price 分离，S2 只换计价不换物理计划；
  [A3] 0:00 计划层只用电价预测（历史因果），结算才用当天实际电价；
       6/12/18 点调整时已观测前缀用实际电价、剩余时段用预测；
  [参数] 4-2 用 P2_CUTS（固定电价下滚动标定），4-3 用 1 月标定，无事后取参。
================================================================
"""
from __future__ import annotations
import sys
import importlib.util
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, r"D:\download")

# ---- 导入同学的 p4_export (2).py（提供 forecast_attach4 / run_p2_frozen / P2_CUTS / export_p42）----
_spec = importlib.util.spec_from_file_location(
    "p4v2", r"D:\download\p4_export (2).py")
p4v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p4v2)

from p3_microgrid import (  # noqa: E402
    N, TAU, E_MIN, E_MAX, E_INIT, M_ENERGY, EC, ED,
    ISSUE_H, load_all, load_predict, pv_interp_for_issue,
    solve_lp_plan, solve_lp_adjust, realtime, ROOT,
)
from p2_microgrid import REPORT_START, REPORT_END  # noqa: E402

ATT4 = ROOT / "01_题目" / "C题" / "附件" / "附件4.xlsx"
TEMPLATE_DIR = ROOT / "01_题目" / "C题" / "附件" / "附件5"
OUT_DIR = ROOT / "06_支撑材料"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_attach4() -> np.ndarray:
    df = pd.read_excel(ATT4, sheet_name=0, header=0)
    price = df.iloc[:, 1:].to_numpy(float)
    assert price.shape == (365, 144), f"附件4形状应为(365,144)，实际{price.shape}"
    return price


# ============================================================
# 4-3 分时段 Qvec 回测（接受预计算的计划电价矩阵 / 结算电价矩阵）
# ============================================================
def run_backtest_qvec(price_plan, price_settle, dates, load_kw, pv_kw, fc,
                       alpha=0.6, lam=1.0, rho=0.5, E_tar=6000.0, W=28,
                       use_adjust=True, day_range=None):
    """
    price_plan   : (365,144) 每天的计划电价（0:00 与调整层用）
    price_settle : (365,144) 每天的结算电价
    风险准备：分时段 Qvec（每个 10 分钟时段独立的历史误差 alpha 分位）。
    """
    n_days = load_kw.shape[0]
    if day_range is None:
        day_range = range(n_days)
    maxd = max(day_range)

    plan_err_hist = []
    adj_err_hists = {36: [], 72: [], 108: []}
    E0_cur = E_INIT
    results = {}
    E0_by_day = {}

    for d in range(0, maxd + 1):
        E0_by_day[d] = E0_cur
        price_plan_d = price_plan[d]

        # ---- 0:00 日前计划 ----
        load_pred_kw = load_predict(d, load_kw, dates)
        pv_pred_kw = pv_interp_for_issue(0, 0.0, fc[d, 0, :])
        pv_pred_kw = np.where(np.isnan(pv_pred_kw), 0.0, pv_pred_kw)
        net_pred_kwh = (load_pred_kw - pv_pred_kw) * TAU

        if len(plan_err_hist) >= 7:
            Qvec = np.quantile(np.vstack(plan_err_hist[-W:]), alpha, axis=0)
        else:
            Qvec = np.zeros(N)
        net_risk = net_pred_kwh + Qvec

        gP, _, _, _, Ebar_plan, _ = solve_lp_plan(
            price_plan_d, net_risk, E0_cur, E_tar, lam)

        # ---- 日内调整（6/12/18 点）----
        gA_final = gP.copy()
        Ebar_final = Ebar_plan.copy()
        if use_adjust:
            Tks = [36, 72, 108]
            for si, Tk in enumerate(Tks):
                # 调整电价：计划电价的前缀 [0,Tk) 替换为当天已观测实际电价
                price_adj_d = price_plan_d.copy()
                price_adj_d[:Tk] = price_settle[d, :Tk]

                l_actual_pre = load_kw[d, 0:Tk]
                p_pred_pre = load_pred_kw[0:Tk]
                bias_kw = float((l_actual_pre - p_pred_pre).mean()) if Tk > 0 else 0.0
                load_rem_pred = load_pred_kw.copy()
                load_rem_pred[Tk:] += bias_kw

                issue_h = ISSUE_H[si + 1]
                anchor_actual_kw = float(pv_kw[d, Tk - 1])
                pv_rem_kw = pv_interp_for_issue(issue_h, anchor_actual_kw, fc[d, si + 1, :])
                pv_rem_kw = np.where(np.isnan(pv_rem_kw), pv_pred_kw, pv_rem_kw)
                pv_pred_new = pv_pred_kw.copy()
                pv_pred_new[Tk:] = pv_rem_kw[Tk:]
                load_pred_new = load_pred_kw.copy()
                load_pred_new[Tk:] = load_rem_pred[Tk:]
                net_pred_new = (load_pred_new - pv_pred_new) * TAU

                hist = adj_err_hists[Tk]
                if len(hist) >= 7:
                    Qadj_vec = np.quantile(np.vstack(hist[-W:]), alpha, axis=0)
                else:
                    Qadj_vec = Qvec[Tk:]
                net_risk_new = net_pred_new.copy()
                net_risk_new[Tk:] += Qadj_vec

                # 前缀模拟求 E_at_Tk
                E_prev = E0_cur
                for t in range(Tk):
                    b = gA_final[t] + pv_kw[d, t] * TAU - load_kw[d, t] * TAU
                    Rline = E_MIN + rho * (Ebar_final[t] - E_MIN)
                    Rline = min(max(Rline, E_MIN), E_MAX)
                    if b >= 0:
                        c_ = min(b, M_ENERGY, (E_MAX - E_prev) / EC)
                        dd_ = 0.0
                    else:
                        dd_ = min(-b, M_ENERGY, max(0.0, ED * (E_prev - Rline)))
                        c_ = 0.0
                    E_prev = E_prev + EC * c_ - dd_ / ED
                E_at_Tk = E_prev

                gA_new, _, _, Ebar_rem, _, _, _ = solve_lp_adjust(
                    price_adj_d, net_risk_new, E_at_Tk, gP, Tk, E_tar, lam)
                next_Tk = Tks[si + 1] if si + 1 < len(Tks) else N
                gA_final[Tk:next_Tk] = gA_new[Tk:next_Tk]
                Ebar_final[Tk:next_Tk] = Ebar_rem[Tk:next_Tk]

        # ---- 实时执行（当天实际负载 / 光伏）----
        gA_final = np.maximum(gA_final, 0.0)
        gP = np.maximum(gP, 0.0)
        load_act_kwh = load_kw[d, :] * TAU
        pv_act_kwh = pv_kw[d, :] * TAU
        c_act, d_act, r_act, w_act, E_arr = realtime(
            gA_final, load_act_kwh, pv_act_kwh, E0_cur, Ebar_final, rho)

        # ---- 结算（当天实际电价 / 固定电价）----
        price_settle_d = price_settle[d]
        up = (gA_final - gP).clip(min=0)
        down = (gP - gA_final).clip(min=0)
        cost_plan_adj = float(np.sum(
            price_settle_d * gP + 1.5 * price_settle_d * up - 0.5 * price_settle_d * down))
        cost_emg = float(np.sum(5.0 * price_settle_d * r_act))

        # ---- 更新误差历史（因果，供未来天使用）----
        actual_net = (load_kw[d, :] - pv_kw[d, :]) * TAU
        pred_net_plan = (load_pred_kw - pv_pred_kw) * TAU
        plan_err_hist.append(actual_net - pred_net_plan)
        for si, Tk in enumerate([36, 72, 108]):
            issue_h = ISSUE_H[si + 1]
            anchor_actual_kw = float(pv_kw[d, Tk - 1])
            pv_rem = pv_interp_for_issue(issue_h, anchor_actual_kw, fc[d, si + 1, :])
            pv_rem = np.where(np.isnan(pv_rem), pv_pred_kw, pv_rem)
            l_actual_pre = load_kw[d, 0:Tk]
            p_pred_pre = load_pred_kw[0:Tk]
            bias_kw = float((l_actual_pre - p_pred_pre).mean()) if Tk > 0 else 0.0
            load_rem = load_pred_kw.copy()
            load_rem[Tk:] += bias_kw
            pv_full = pv_pred_kw.copy()
            pv_full[Tk:] = pv_rem[Tk:]
            load_full = load_pred_kw.copy()
            load_full[Tk:] = load_rem[Tk:]
            pred_net_adj = (load_full - pv_full) * TAU
            adj_err_hists[Tk].append((actual_net - pred_net_adj)[Tk:])

        E0_cur = E_arr[-1]
        if d in day_range:
            results[d] = {
                "gP": gP.copy(), "gA": gA_final.copy(),
                "c_act": c_act, "d_act": d_act, "r": r_act, "w": w_act,
                "E": E_arr.copy(), "E0": E0_by_day[d],
                "cost_plan_adj": cost_plan_adj, "cost_emg": cost_emg,
                "cost_total": cost_plan_adj + cost_emg,
            }
    return results


# ============================================================
# 1 月标定（只用 1 月预热期，合规）
# ============================================================
ALPHAS = [0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80]
RHOS = [0.30, 0.40, 0.50, 0.60, 0.70]


def calibrate_jan(price_plan, price_settle, dates, load_kw, pv_kw, fc, use_adjust):
    best_cost, best, grid = float("inf"), None, []
    for alpha in ALPHAS:
        for rho in RHOS:
            res = run_backtest_qvec(
                price_plan, price_settle, dates, load_kw, pv_kw, fc,
                alpha=alpha, lam=1.0, rho=rho, E_tar=6000.0, W=28,
                use_adjust=use_adjust, day_range=range(0, 31))
            cost = sum(res[d]["cost_total"] for d in range(0, 31))
            grid.append((alpha, rho, cost))
            if cost < best_cost:
                best_cost, best = cost, (alpha, rho)
    return best, best_cost, grid


# ============================================================
# S2：复用 S1 物理计划，用波动电价重新结算
# ============================================================
def resettle(results_s1, price_settle):
    res2 = {}
    for d, r in results_s1.items():
        gP, gA, r_act = r["gP"], r["gA"], r["r"]
        p = price_settle[d]
        up = (gA - gP).clip(min=0)
        down = (gP - gA).clip(min=0)
        cpa = float(np.sum(p * gP + 1.5 * p * up - 0.5 * p * down))
        cemg = float(np.sum(5.0 * p * r_act))
        nr = dict(r)
        nr["cost_plan_adj"] = cpa
        nr["cost_emg"] = cemg
        nr["cost_total"] = cpa + cemg
        res2[d] = nr
    return res2


def total_cost(results, lo=31, hi=365):
    return sum(results[d]["cost_total"] for d in range(lo, hi))


# ============================================================
# Excel 输出
# ============================================================
def fmt_slot(i):
    a, b = i * 10, (i + 1) * 10
    def f(m):
        return "0:00+1" if m == 1440 else f"{m//60}:{m%60:02d}"
    return f"{f(a)}-{f(b)}"


BLOCKS = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]


def block_label(a, z):
    sh = a * 10 // 60
    eh = 24 if z * 10 == 1440 else z * 10 // 60
    return f"{sh}:00-{eh}:00"


def _write_charge_emergency(wb, results, dates):
    ws = wb["充放电量"]
    ws.delete_rows(2, ws.max_row)
    row = 2
    for d in range(31, 365):
        o = results[d]
        for bi, (a, z) in enumerate(BLOCKS):
            ws.cell(row=row, column=1,
                    value=dates[d].to_pydatetime().replace(tzinfo=None) if bi == 0 else None)
            ws.cell(row=row, column=2, value=block_label(a, z))
            ws.cell(row=row, column=3, value=round(float(o["c_act"][a:z].sum()), 6))
            ws.cell(row=row, column=4, value=round(float(o["d_act"][a:z].sum()), 6))
            if bi == 0:
                ws.cell(row=row, column=5, value="0:00")
                ws.cell(row=row, column=6, value=round(float(o["E0"]), 6))
            elif bi == 1:
                ws.cell(row=row, column=5, value="24:00")
                ws.cell(row=row, column=6, value=round(float(o["E"][-1]), 6))
            row += 1
    ws = wb["紧急购电量"]
    ws.delete_rows(2, ws.max_row)
    row = 2
    for d in range(31, 365):
        r = results[d]["r"]
        ev, t = [], 0
        while t < N:
            if r[t] > 1e-6:
                s0 = t
                while t < N and r[t] > 1e-6:
                    t += 1
                ev.append((s0, t, float(r[s0:t].sum())))
            else:
                t += 1
        for ei, (s0, s1, kwh) in enumerate(ev):
            ws.cell(row=row, column=1,
                    value=dates[d].to_pydatetime().replace(tzinfo=None) if ei == 0 else None)
            ws.cell(row=row, column=2,
                    value=f"{fmt_slot(s0).split('-')[0]}-{fmt_slot(s1-1).split('-')[1]}")
            ws.cell(row=row, column=3, value=round(kwh, 6))
            row += 1


def write_q3(results, dates, out_path):
    import openpyxl
    shutil.copyfile(TEMPLATE_DIR / "result3.xlsx", out_path)
    wb = openpyxl.load_workbook(out_path)
    correct = [fmt_slot(i) for i in range(N)]
    for sheet in ["计划购电量", "调整购电量"]:
        ws = wb[sheet]
        for j, lab in enumerate(correct, start=2):
            ws.cell(row=1, column=j, value=lab)
        for r, d in enumerate(range(31, 365), start=2):
            ws.cell(row=r, column=1, value=dates[d].to_pydatetime().replace(tzinfo=None))
            arr = results[d]["gP"] if sheet == "计划购电量" else results[d]["gA"]
            for j, v in enumerate(arr, start=2):
                ws.cell(row=r, column=j, value=round(float(v), 6))
            ws.cell(row=r, column=146, value=round(float(arr.sum()), 6))
    _write_charge_emergency(wb, results, dates)
    wb.save(out_path)
    print(f"  saved {out_path}")


# ============================================================
# main
# ============================================================
def main():
    t0 = time.time()
    print("=" * 72)
    print("问题四 融合最优版（一步出 result4-2 / result4-3）")
    print("  4-2: p2 框架 + P2_CUTS 八段参数 + 因果电价预测（无日内调整）")
    print("  4-3: 分时段 Qvec + 1 月标定 + 因果电价预测（有日内调整）")
    print("  统一电价预测: forecast_attach4（hat[n] 只用 price4[:n]，因果）")
    print("  三臂: S1 固定实跑 / S2 换计价 / S3 预测+实际结算 / S3* oracle(不上报)")
    print("=" * 72)

    price_fixed, dates, load_kw, pv_kw, fc = load_all()
    price4 = load_attach4()
    print(f"\n附件1固定电价均值={price_fixed.mean():.4f}  "
          f"附件4范围=[{price4.min():.4f},{price4.max():.4f}]")

    # ---- 统一因果电价预测 ----
    hat = p4v2.forecast_attach4(price4, price_fixed, dates)
    mae = float(np.abs(hat[31:365] - price4[31:365]).mean())
    print(f"因果电价预测 2-12月 MAE={mae:.4f} 元/kWh")

    price_fixed_mat = np.tile(price_fixed, (365, 1))

    # ================================================================
    # 4-2（p2 框架 + P2_CUTS）
    # ================================================================
    print("\n" + "=" * 72)
    print("【问题4-2】p2 框架 + P2_CUTS + 因果电价预测")
    print("=" * 72)

    print("\n[S1 固定计划+固定结算] 实跑...", flush=True)
    recs_s1 = p4v2.run_p2_frozen(
        price_fixed, load_kw, pv_kw, dates, bill_price=price_fixed, verbose=True)
    s1_2 = sum(rec.exec.cost_total for rec in recs_s1[31:365])
    print(f"  S1 = {s1_2:.2f} 元 = {s1_2/1e4:.2f} 万")

    print("[S2 固定计划+波动结算] 复用 S1 物理计划换计价...", flush=True)
    s2_2 = 0.0
    for d in range(31, 365):
        _, _, tot = p4v2.bill_p2(price4[d], recs_s1[d].exec.g, recs_s1[d].exec.r)
        s2_2 += tot
    print(f"  S2 = {s2_2:.2f} 元 = {s2_2/1e4:.2f} 万  "
          f"重新定价效应 = {s2_2-s1_2:.2f} ({(s2_2-s1_2)/1e4:.2f}万)")

    print("[S3 预测计划+波动结算] 全年...", flush=True)
    recs_s3_2 = p4v2.run_p2_frozen(
        hat, load_kw, pv_kw, dates, bill_price=price4, verbose=True)
    s3_2 = sum(rec.exec.cost_total for rec in recs_s3_2[31:365])
    print(f"  S3 = {s3_2:.2f} 元 = {s3_2/1e4:.2f} 万  ← 提交值")
    print(f"  决策质量效应 S3-S2 = {s3_2-s2_2:.2f} ({(s3_2-s2_2)/1e4:.2f}万)")

    print("[S3* 上帝视角（仅对照，不上报）]...", flush=True)
    recs_or_2 = p4v2.run_p2_frozen(
        price4, load_kw, pv_kw, dates, bill_price=price4, verbose=False)
    sor_2 = sum(rec.exec.cost_total for rec in recs_or_2[31:365])
    print(f"  S3* = {sor_2:.2f} 元 = {sor_2/1e4:.2f} 万  "
          f"预测代价 S3-S3* = {s3_2-sor_2:.2f} ({(s3_2-sor_2)/1e4:.2f}万)")

    # 导出 4-2 excel（用同学的 export_p42，内部写 p4v2.OUT_P42）
    p4v2.export_p42(recs_s3_2, dates)

    # ================================================================
    # 4-3（分时段 Qvec + 1 月标定）
    # ================================================================
    print("\n" + "=" * 72)
    print("【问题4-3】分时段 Qvec + 1 月标定 + 因果电价预测")
    print("=" * 72)

    print("\n[1月标定 alpha/rho]（35 组网格，只用 1 月）...", flush=True)
    (aa, rr), jan_cost, grid = calibrate_jan(
        hat, price4, dates, load_kw, pv_kw, fc, use_adjust=True)
    print(f"  1月最优: alpha={aa}, rho={rr}, 1月费={jan_cost:.2f}")
    for a, r, c in sorted(grid, key=lambda x: x[2])[:5]:
        print(f"    a={a:.2f} r={r:.2f}: {c:.2f}")

    print("\n[S3 预测计划+波动结算] 全年...", flush=True)
    res_s3_3 = run_backtest_qvec(
        hat, price4, dates, load_kw, pv_kw, fc,
        alpha=aa, lam=1.0, rho=rr, E_tar=6000.0, W=28,
        use_adjust=True, day_range=range(0, 365))
    s3_3 = total_cost(res_s3_3)
    print(f"  S3 = {s3_3:.2f} 元 = {s3_3/1e4:.2f} 万  ← 提交值")

    print("[S1 固定计划+固定结算] 实跑对照臂...", flush=True)
    res_s1_3 = run_backtest_qvec(
        price_fixed_mat, price_fixed_mat, dates, load_kw, pv_kw, fc,
        alpha=aa, lam=1.0, rho=rr, E_tar=6000.0, W=28,
        use_adjust=True, day_range=range(0, 365))
    s1_3 = total_cost(res_s1_3)
    print(f"  S1 = {s1_3:.2f} 元 = {s1_3/1e4:.2f} 万")

    print("[S2 固定计划+波动结算] 复用 S1 物理计划换计价...", flush=True)
    res_s2_3 = resettle(res_s1_3, price4)
    s2_3 = total_cost(res_s2_3)
    print(f"  S2 = {s2_3:.2f} 元 = {s2_3/1e4:.2f} 万")

    print(f"\n  ── 4-3 三臂分解（2-12月）──")
    print(f"    S1 固定决策+固定结算: {s1_3:.2f} ({s1_3/1e4:.2f}万)")
    print(f"    S2 固定决策+波动结算: {s2_3:.2f} ({s2_3/1e4:.2f}万)")
    print(f"    S3 波动决策+波动结算: {s3_3:.2f} ({s3_3/1e4:.2f}万)  ← 提交值")
    print(f"    S2-S1 重新定价效应:  {s2_3-s1_3:.2f} ({(s2_3-s1_3)/1e4:.2f}万)")
    print(f"    S3-S2 决策质量效应:  {s3_3-s2_3:.2f} ({(s3_3-s2_3)/1e4:.2f}万)")

    # 导出 4-3 excel
    out43 = OUT_DIR / "result4-3.xlsx"
    write_q3(res_s3_3, dates, out43)

    # ================================================================
    # 最终汇总
    # ================================================================
    print("\n" + "=" * 72)
    print("最终结果（2-12月，融合最优版）")
    print("=" * 72)
    print(f"  问题4-2 (p2框架, P2_CUTS):       {s3_2:>14.2f} 元 = {s3_2/1e4:.2f} 万")
    print(f"  问题4-3 (分时段Qvec, a={aa}, r={rr}): {s3_3:>14.2f} 元 = {s3_3/1e4:.2f} 万")
    print(f"  日内调整收益 (4-2 − 4-3):         {(s3_2-s3_3):>14.2f} 元 = {(s3_2-s3_3)/1e4:.2f} 万")
    print(f"\n  三臂对比:")
    print(f"    4-2: S1={s1_2/1e4:.2f}万  S2={s2_2/1e4:.2f}万  S3={s3_2/1e4:.2f}万  S3*={sor_2/1e4:.2f}万")
    print(f"    4-3: S1={s1_3/1e4:.2f}万  S2={s2_3/1e4:.2f}万  S3={s3_3/1e4:.2f}万")
    print(f"\n合规性声明:")
    print(f"  [A3] 电价预测 hat[n] 只用 price4[:n]，0:00 看不见当天实际电价")
    print(f"  [A2] 计划价与结算价分离（bill_price），S2 只换计价不换物理计划")
    print(f"  [A1] S1 固定电价对照臂当场实跑，不硬编码")
    print(f"  [参数] 4-2 用 P2_CUTS（固定电价下滚动标定），4-3 用 1 月标定，无事后取参")
    print(f"  [Qvec] 4-3 风险准备为分时段 Qvec（每时段独立 alpha 分位）")
    print(f"\n总用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
