# -*- coding: utf-8 -*-
r"""
问题二 日末储备惩罚 λ 的消融实验

要回答的问题
------------
1 月联合标定选中 λ=0.00 并冻结整年。但 λ=0 使 ξ 在经济上完全自由，
终端约束不再产生定价信号，日前参考轨迹 Ē 的日末值退化到下限 E_MIN
（实测 334/334 天，见 p2_lambda_diag.py）。于是执行层的储备线
R_t = E_MIN + ρ(Ē_t − E_MIN) 建立在一条没有终端价值的轨迹上。

本脚本在全年的因果回放上比较不同 λ，回答三个问题：
  Q1 λ>0 是否能把 Ē 恢复到有意义的形态？
  Q2 λ>0 的全年实际总费用是多少？（含期末库存的价值折算）
  Q3 1 月选中 λ=0 是不是"窗口内消耗库存"造成的选择偏差？

设计
----
* 所有臂都从 2025-01-01 的 E_INIT 出发、跑到 2025-12-31，同一预测器、
  同一执行规则、同一 (α, ρ)，**只动 λ**，关掉滚动标定以隔离单一变量。
* 费用口径同时报两种：
    - 原样总费用 Σ(计划费 + 紧急费)
    - 库存修正费用 = 原样总费用 + v·(E_初 − E_末)，v 为储电量单价（元/kWh）
  不修正期末库存的窗口比较，会系统性偏爱"把电池用空"的策略。

输出 06_支撑材料/p2_lambda_ablation.json。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np

from p2_microgrid import (
    E_INIT, E_MAX, E_MIN, N, N_DAY, REPORT_END, REPORT_START, JIA_MIN_SAMPLES,
    CalConfig, Forecaster, JIA_LOAD_FORECAST, JIA_PV_FORECAST, RiskParams,
    reference_price,
    Simulator, build_error_table, load_attach2, run_strategy, strategy_totals,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "06_支撑材料" / "p2_lambda_ablation.json"

# 消融网格：λ 取 0 与四个正值；Δ 的间隔要跨过一月选参里 0.3→0.5 的跳变
LAMS = (0.00, 0.20, 0.50, 0.80, 1.20)
# 固定 (α, ρ)：主策略 8 次滚动标定中出现最多的组合 + 两个对照点
AR_GRID = ((0.75, 0.9), (0.75, 0.5), (0.70, 0.9))
# 库存折价单价（元/kWh），用于把期末储电量折算成可比费用
V_GRID = (0.35, 0.50, 0.65)
EDGE_TOL = 1.0


def arm_stats(records, lo: int, hi: int, rho: float) -> dict:
    """统计单臂在 [lo, hi) 上的费用、库存与参考轨迹形态。"""
    rep = [r for r in records if lo <= r.n < hi]

    cost = sum(r.exec.cost_total for r in rep)
    cost_plan = sum(r.exec.cost_plan for r in rep)
    cost_emg = sum(r.exec.cost_emg for r in rep)

    Ebar = np.concatenate([r.Ebar for r in rep])
    Ebar_end = np.array([r.Ebar[-1] for r in rep])
    E_end_daily = np.array([r.exec.E_end for r in rep])

    # 执行层逐时段的时段初储电量与实际盈余 b_t
    starts = np.concatenate([
        np.concatenate([[r.exec.E0], r.exec.E[:-1]]) for r in rep])
    d_all = np.concatenate([r.exec.d for r in rep])
    r_all = np.concatenate([r.exec.r for r in rep])
    # b_t = 计划购电 + 实际光伏 − 实际负载，与 execute_day 内部一致
    b_all = np.concatenate([r.exec.g + r.v_act - r.l_act for r in rep])
    needs = b_all < -1e-9

    R = E_MIN + rho * (Ebar - E_MIN)
    # 口径a：站在储备线下。E_{t-1} < R_t ⟹ head=0 ⟹ d_t=0 是恒等推论，
    # 故该口径**必然**对应"未放电"，不能据此声称"因储备线而未能放电"——
    # 其中多数时段根本不需要放电。
    below = starts < R - 1e-6
    # 口径b：真的被卡住。既需要放电（b<0）又站在储备线下，缺口只能转紧急购电。
    blocked = needs & (starts <= R + 1e-6)

    return {
        "天数": len(rep),
        "出发储电量_kWh": float(rep[0].exec.E0),
        "期末储电量_kWh": float(rep[-1].exec.E_end),
        "总费用_元": cost,
        "计划购电费_元": cost_plan,
        "紧急购电费_元": cost_emg,
        "紧急购电量_kWh": float(sum(r.exec.r.sum() for r in rep)),
        "弃电量_kWh": float(sum(r.exec.w.sum() for r in rep)),
        "参考轨迹": {
            "日末均值_kWh": float(Ebar_end.mean()),
            "日末贴下限占比": float((np.abs(Ebar_end - E_MIN) <= EDGE_TOL).mean()),
            "全时段贴上限占比": float((np.abs(Ebar - E_MAX) <= EDGE_TOL).mean()),
            "全时段贴下限占比": float((np.abs(Ebar - E_MIN) <= EDGE_TOL).mean()),
            "均值_kWh": float(Ebar.mean()),
            "标准差_kWh": float(Ebar.std()),
        },
        "储备线": {
            "E_低于R_时段占比": float(below.mean()),
            "E_低于R_且未放电_时段占比": float(
                (below & (d_all <= 1e-9)).mean()),
            "需要放电_时段占比": float(needs.mean()),
            "放电被结构性拒绝_时段占比": float(blocked.mean()),
            "被拒时段紧急购电量_kWh": float(r_all[blocked].sum()),
            "被拒占全部紧急购电比例": float(
                r_all[blocked].sum() / max(1e-9, r_all.sum())),
            "日末E_均值_kWh": float(E_end_daily.mean()),
            "日末E_贴下限占比": float(
                (np.abs(E_end_daily - E_MIN) <= EDGE_TOL).mean()),
        },
    }


def breakeven_from_january_table() -> dict | None:
    """从已交付的 1 月选参表反解 λ 的盈亏平衡库存单价 v*。

    1 月选参的准则是"窗口内总费用最小"。窗口截断会把**消耗库存**的策略
    系统性地选出来：少买的电计入费用、少掉的库存不计价。把准则换成库存
    修正费用 J + v·(E_0 − E_144) 后，λ=0 与 λ>0 谁更优取决于 v。

    本函数不解方程，而是直接在所有候选点上扫描 v，找出结论翻转的临界值。
    数据源是 06_支撑材料/p2_results.json 的「1月离线选参.明细」（180 点，
    每点含 1 月总费用与 2 月 1 日储电量）。
    """
    src = ROOT / "06_支撑材料" / "p2_results.json"
    if not src.exists():
        return None
    payload = json.loads(src.read_text(encoding="utf-8"))
    detail = payload.get("1月离线选参", {}).get("明细", [])
    if not detail:
        return None

    rows = []
    for r in detail:
        m = re.match(r"α=([\d.]+), ρ=([\d.]+), λ=([\d.]+)", r["参数"])
        if m:
            rows.append({
                "α": float(m.group(1)), "ρ": float(m.group(2)),
                "λ": float(m.group(3)),
                "1月费用_元": r["1月总费用_元"],
                "期末储电量_kWh": r["2月1日储电量_kWh"],
            })
    if not rows:
        return None

    def winner(v: float) -> dict:
        return min(rows, key=lambda z: z["1月费用_元"] + v * (E_INIT - z["期末储电量_kWh"]))

    # 在 [0, 4] 上二分找"最优解的 λ 首次变为正值"的临界单价
    lo, hi = 0.0, 4.0
    if winner(hi)["λ"] == 0.0:
        return {"临界单价_元每kWh": None, "说明": "上界 4.0 元/kWh 内 λ=0 恒优"}
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if winner(mid)["λ"] == 0.0:
            lo = mid
        else:
            hi = mid
    base = winner(0.0)
    flip = winner(hi)
    return {
        "临界单价_元每kWh": hi,
        "库存计价准则": "J + v·(E_初 − E_末)，E_初 = 6000 kWh",
        "候选点数": len(rows),
        "v=0 时最优": {"α": base["α"], "ρ": base["ρ"], "λ": base["λ"],
                       "期末储电量_kWh": base["期末储电量_kWh"]},
        "临界点最优": {"α": flip["α"], "ρ": flip["ρ"], "λ": flip["λ"],
                       "期末储电量_kWh": flip["期末储电量_kWh"]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="问题二 日末储备惩罚 λ 的消融实验")
    ap.add_argument("--breakeven-only", action="store_true",
                    help="只做标定准则的库存偏差检验，跳过全年消融（秒级）")
    args = ap.parse_args()

    from p1_microgrid import load_attach1

    import p2_microgrid

    price = load_attach1()["电价"].to_numpy(float)
    p2_microgrid._PRICE_REF = price      # 供 day_summary / validate_day 复算

    if args.breakeven_only:
        payload = (json.loads(OUT.read_text(encoding="utf-8"))
                   if OUT.exists() else {"臂": []})
        be = report_breakeven(price)
        if be is not None:
            payload["盈亏平衡检验"] = be
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"\n已更新 {OUT.relative_to(ROOT)}（保留原有消融结果）")
        return

    LOAD, PV, dates = load_attach2()
    fo = Forecaster(LOAD, PV, JIA_LOAD_FORECAST, JIA_PV_FORECAST)
    eps = build_error_table(LOAD, PV, fo)
    sim = Simulator(LOAD, PV, price, dates, eps, fo)

    # 关掉滚动标定：start=N_DAY 表示整年只用传入的 warmup 参数
    cal = CalConfig(rule="greedy", start=N_DAY, min_samples=JIA_MIN_SAMPLES,
                    day0="plan")

    out: dict = {
        "口径": {
            "λ网格": list(LAMS),
            "(α,ρ)网格": [list(x) for x in AR_GRID],
            "库存折价单价_元每kWh": list(V_GRID),
            "滚动标定": "关闭（隔离 λ 单一变量）",
            "预测器": JIA_LOAD_FORECAST.label() + "；" + JIA_PV_FORECAST.label(),
            "起点": f"2025-01-01，{E_INIT:.0f} kWh",
        },
        "臂": [],
    }

    for alpha, rho in AR_GRID:
        for lam in LAMS:
            rp = RiskParams(alpha=alpha, rho=rho, lam=lam, window=28,
                            min_samples=JIA_MIN_SAMPLES)
            records, _ = run_strategy(sim, cal, warmup=rp, verbose=False)
            full = strategy_totals(records, 0, N_DAY, reference_price(price))
            rep = arm_stats(records, REPORT_START, REPORT_END, rho)
            jan = arm_stats(records, 0, REPORT_START, rho)

            # 库存修正：以报告区间起点储电量为基准，把期末库存折算成费用
            d_inv = rep["出发储电量_kWh"] - rep["期末储电量_kWh"]
            adj = {f"v={v:.2f}": rep["总费用_元"] + v * d_inv for v in V_GRID}

            out["臂"].append({
                "α": alpha, "ρ": rho, "λ": lam,
                "1月费用_元": jan["总费用_元"],
                "1月期末储电量_kWh": jan["期末储电量_kWh"],
                "全年总费用_元": full["合计购电费_元"],
                "年末储电量_kWh": full["期末储电量_kWh"],
                "报告区间": rep,
                "库存修正费用_元": adj,
            })
            rs = rep["储备线"]
            print(f"  α={alpha} ρ={rho} λ={lam:.2f}  "
                  f"报告区间 {rep['总费用_元']:>14,.2f} 元  "
                  f"期初 {rep['出发储电量_kWh']:>8,.1f} → 期末 "
                  f"{rep['期末储电量_kWh']:>8,.1f} kWh  "
                  f"Ebar日末 {rep['参考轨迹']['日末均值_kWh']:>8,.1f} "
                  f"贴上限 {rep['参考轨迹']['全时段贴上限占比'] * 100:5.1f}%  "
                  f"禁放 {rs['放电被结构性拒绝_时段占比'] * 100:5.2f}%"
                  f"（口径a {rs['E_低于R_时段占比'] * 100:5.2f}%）")

    # 标定准则的库存偏差检验：λ=0 是不是窗口截断造成的假象？
    be = report_breakeven(price)
    if be is not None:
        out["盈亏平衡检验"] = be

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写出 {OUT.relative_to(ROOT)}")


def report_breakeven(price: np.ndarray) -> dict | None:
    """跑库存偏差检验并打印结论。返回检验结果或 None（缺 1 月选参表时）。"""
    be = breakeven_from_january_table()
    if be is None:
        print("\n盈亏平衡检验：跳过（未找到 06_支撑材料/p2_results.json 的 1 月选参表）")
        return None

    v_star = be["临界单价_元每kWh"]
    # 库存在最贵时段顶替计划购电的边际价值上界：η_c·η_d·max p_t
    v_cap = 0.9 * 0.9 * float(price.max())
    print(f"\n盈亏平衡检验（库存计价准则 J + v·(E_初 - E_末)）")
    print(f"  候选点 {be['候选点数']} 个，v=0 时最优 "
          f"α={be['v=0 时最优']['α']} ρ={be['v=0 时最优']['ρ']} "
          f"λ={be['v=0 时最优']['λ']:.2f}"
          f"（期末储电 {be['v=0 时最优']['期末储电量_kWh']:,.1f} kWh）")
    if v_star is None:
        print(f"  在 v ≤ 4.0 元/kWh 内 λ=0 恒为最优")
        return be
    print(f"  临界库存单价 v* = {v_star:.3f} 元/kWh"
          f"（v 超过该值时转为 λ={be['临界点最优']['λ']:.2f}）")
    print(f"  库存边际价值上界 η_cη_d·max p = {v_cap:.3f} 元/kWh"
          f"（电价区间 [{price.min():.4f}, {price.max():.4f}]）")
    print(f"  v* / 上界 = {v_star / v_cap:.2f} —— "
          f"{'λ=0 对库存计价稳健' if v_star > v_cap else '需重新审视 λ=0'}")
    return be


if __name__ == "__main__":
    main()
