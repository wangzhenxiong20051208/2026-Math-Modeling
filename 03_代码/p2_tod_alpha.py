# -*- coding: utf-8 -*-
"""问题二灵敏度：分时 α（非正式交付）。

与主程序 p2_microgrid.py 共用预测器和执行规则，只把当天单一 α
改成按电价在 0.70–0.90 之间线性插值。不覆盖 result2.xlsx。

用法（在仓库根目录）：
    python3 03_代码/p2_tod_alpha.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import p2_microgrid as p2
from p1_microgrid import N, TAU, E_INIT, load_attach1

OUT = ROOT / "06_支撑材料" / "p2_tod_alpha.json"

SCHEDULE = [
    (31, p2.RiskParams(alpha=0.80, rho=1.0, lam=0.00)),
    (73, p2.RiskParams(alpha=0.80, rho=0.0, lam=0.00)),
    (115, p2.RiskParams(alpha=0.80, rho=0.0, lam=0.00)),
    (157, p2.RiskParams(alpha=0.90, rho=1.0, lam=0.00)),
    (199, p2.RiskParams(alpha=0.80, rho=0.0, lam=0.00)),
    (241, p2.RiskParams(alpha=0.70, rho=0.0, lam=0.00)),
    (283, p2.RiskParams(alpha=0.80, rho=0.0, lam=0.00)),
    (325, p2.RiskParams(alpha=0.80, rho=0.0, lam=0.00)),
]


def params_on(n: int) -> p2.RiskParams:
    cur = p2.RiskParams(alpha=0.80, rho=1.0, lam=0.00)
    for k, rp in SCHEDULE:
        if n >= k:
            cur = rp
    return cur


def alpha_by_price(price: np.ndarray, lo=0.70, hi=0.90) -> np.ndarray:
    pmin, pmax = float(price.min()), float(price.max())
    x = (price - pmin) / max(pmax - pmin, 1e-9)
    return lo + (hi - lo) * x


def margin_alpha_vec(eps, n, alpha_t, window=28, min_samples=10):
    q = np.zeros(N)
    if n == 0:
        return q
    hist = eps[max(0, n - window):n]
    hist = hist[~np.isnan(hist).all(axis=1)]
    k = hist.shape[0]
    if k < 3:
        return q
    if k < min_samples:
        pooled = np.empty((k, N))
        for t in range(N):
            a, b = max(0, t - 2), min(N, t + 3)
            pooled[:, t] = hist[:, a:b].mean(axis=1)
        src = pooled
    else:
        src = hist
    for t in range(N):
        q[t] = float(np.quantile(src[:, t], float(alpha_t[t])))
    return q


def replay(sim, tod: bool):
    recs = []
    e = E_INIT
    a_t = alpha_by_price(sim.price)
    for n in range(p2.N_DAY):
        rp = params_on(n)
        if n == 0 or not tod:
            rec = sim.run_day(n, rp, e)
        else:
            l_act = sim.LOAD[n] * TAU
            v_act = sim.PV[n] * TAU
            l_hat, v_hat, n_hat = sim.fo.energy(n)
            q = margin_alpha_vec(sim.eps, n, a_t)
            n_risk = n_hat + q
            plan = p2.solve_dayahead(n_risk, e, sim.price, rp)
            ex = p2.execute_day(plan.g, plan.Ebar, l_act, v_act, e, sim.price, rp)
            rec = p2.DayRecord(
                n=n, date=sim.dates[n], l_hat=l_hat, v_hat=v_hat, n_hat=n_hat,
                margin=q, n_risk=n_risk, l_act=l_act, v_act=v_act, exec=ex,
                Ebar=plan.Ebar, params=rp, rule="greedy",
            )
        recs.append(rec)
        e = rec.exec.E_end
    return p2.strategy_totals(recs, p2.REPORT_START, p2.REPORT_END)


def main() -> None:
    price = load_attach1()["电价"].to_numpy(float)
    p2._PRICE_REF = price
    LOAD, PV, dates = p2.load_attach2()
    fo = p2.Forecaster(LOAD, PV)
    eps = p2.build_error_table(LOAD, PV, fo)
    sim = p2.Simulator(LOAD, PV, price, dates, eps, fo)

    base = replay(sim, tod=False)
    tod = replay(sim, tod=True)
    delta = base["合计购电费_元"] - tod["合计购电费_元"]
    payload = {
        "说明": "分时α对照。非正式交付。",
        "评价区间": ["2025-02-01", "2025-12-31"],
        "冻住日程的原文回放": base,
        "分时α_0.70_0.90": tod,
        "相对冻住原文减少_元": delta,
        "相对冻住原文降幅": delta / base["合计购电费_元"],
        "主模型正式结果": {
            "合计购电费_元": 14021565.12,
            "紧急购电费_元": 662827.17,
            "期末储电量_kWh": 1687.84,
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("原文回放  ", f"{base['合计购电费_元']:,.2f}")
    print("分时α     ", f"{tod['合计购电费_元']:,.2f}")
    print(f"少 {delta:,.2f} 元（{delta / base['合计购电费_元'] * 100:.2f}%）")
    print("已写出", OUT)


if __name__ == "__main__":
    main()
