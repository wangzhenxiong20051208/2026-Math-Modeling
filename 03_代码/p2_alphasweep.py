"""问题二 α 敏感性验证：固定 ρ=1、λ=0，让 α 在 {0.50,0.70,0.80,0.90} 上取值。

论文 6.9.6 节引用了「降低 α 可减少弃电但会抬高紧急购电，总费用在 α=0.80 附近
取到最小」的结论。该结论必须由真实跑出的数字支撑，故单列此脚本，与主求解共用
同一预测器、同一实时执行规则、同一评价区间（REPORT_START..REPORT_END），
唯一的差别就是 α 固定、不再逐窗口重标定。

输出：06_支撑材料/p2_alpha_sensitivity.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from p2_microgrid import (
    REPORT_START, REPORT_END, TAU,
    Forecaster, Simulator, RiskParams, CalConfig,
    load_attach2, build_error_table, run_strategy, strategy_totals,
)

OUT = Path(__file__).resolve().parents[1] / "06_支撑材料" / "p2_alpha_sensitivity.json"


def main() -> None:
    from p1_microgrid import load_attach1
    price = load_attach1()["电价"].to_numpy(float)

    LOAD, PV, dates = load_attach2()
    fo = Forecaster(LOAD, PV)
    eps = build_error_table(LOAD, PV, fo)
    sim = Simulator(LOAD, PV, price, dates, eps, fo)

    rows = []
    for a in (0.50, 0.70, 0.80, 0.90):
        t0 = time.time()
        rp = RiskParams(alpha=a, rho=1.0, lam=0.0)
        # 固定参数、不做滚动标定：直接把整年按同一组参数回放
        recs, _ = run_strategy(
            sim, CalConfig(rule="greedy", alphas=(a,), rhos=(1.0,), lams=(0.0,)),
            verbose=False)
        tot = strategy_totals(recs, REPORT_START, REPORT_END)
        row = {
            "alpha": a,
            "弃电量_MWh": tot["弃电量_kWh"] / 1000.0,
            "紧急购电量_MWh": tot["紧急购电量_kWh"] / 1000.0,
            "计划购电量_MWh": tot["计划购电量_kWh"] / 1000.0,
            "计划购电费_万元": tot["计划购电费_元"] / 1e4,
            "紧急购电费_万元": tot["紧急购电费_元"] / 1e4,
            "合计购电费_万元": tot["合计购电费_元"] / 1e4,
            "期末储电量_kWh": tot["期末储电量_kWh"],
        }
        rows.append(row)
        print(f"α={a:.2f}  ρ={rp.rho:.1f}  λ={rp.lam:.2f}  "
              f"弃电 {row['弃电量_MWh']:8.1f} MWh  "
              f"紧急购电 {row['紧急购电量_MWh']:7.1f} MWh  "
              f"合计 {row['合计购电费_万元']:9.2f} 万元  "
              f"({time.time() - t0:.0f}s)", flush=True)

    best = min(rows, key=lambda r: r["合计购电费_万元"])
    payload = {
        "说明": "固定 ρ=1、λ=0，仅改变 α 的全区间敏感性验证；"
                "与主策略共用预测器、执行规则与评价区间，只是不做滚动重标定。",
        "评价区间": f"{dates[REPORT_START]} 至 {dates[REPORT_END - 1]}",
        "总费用最小者": best["alpha"],
        "结果": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {OUT}")
    print(f"总费用最小的 α = {best['alpha']:.2f}（{best['合计购电费_万元']:.2f} 万元）")


if __name__ == "__main__":
    main()
