# -*- coding: utf-8 -*-
r"""问题三：参数的滚动标定记录。

题目要求"每天 0:00 制定当天计划购电策略"，因此任何参数都只能由\textbf{已经过去}
的数据决定。本文的做法是：把 2025 年 1 月当作预热月，在 1 月上做一次联合标定，
把选出的 $(\alpha,\rho,\lambda,W)$ 冻结，此后 2 月 1 日--12 月 31 日的评价区间内
\textbf{不再回头修改}。本脚本把这个标定过程完整跑一遍并留档，回答三个问题：

  1. 1 月最优的参数是哪一组？与最终采用的 $(\alpha,\rho,\lambda,W)=(0.6,0.5,1.0,28)$
     差多少？
  2. 如果直接把 1 月最优参数拿去跑 2 月--12 月，会比现在更好还是更差？
  3. 每个参数单独看，1 月的费用曲线是不是"平底"——即结论对参数是否敏感？

结果写入 `06_支撑材料/p3_calibration.json`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE.parent / "06_支撑材料"

JAN = range(0, 31)              # 预热月：1 月 1 日--1 月 31 日
BEST = dict(alpha=0.6, lam=1.0, rho=0.5, E_tar=6000.0, W=28)
ALPHAS = (0.4, 0.5, 0.6, 0.7, 0.8)
RHOS = (0.35, 0.5, 0.7)
WS = (14, 21, 28)
LAMS = (0.0, 0.5, 1.0)


def jan_cost(cfg):
    """在 1 月数据上进行时序仿真，返回该月实际总费用（计划调整费与紧急费之和）。"""
    import p3_backtest as B
    import p3_microgrid as M
    price, dates, load_kw, pv_kw, fc = M.load_all()
    res = B.run_backtest(price, dates, load_kw, pv_kw, fc,
                         day_range=JAN, use_adjust=True,
                         adjust_mask=(True, True, True), **cfg)
    days = sorted(res)
    total = sum(res[d]["cost_total"] for d in days)
    return dict(
        total=total,
        plan_adj=sum(res[d]["cost_plan_adj"] for d in days),
        emg=sum(res[d]["cost_emg"] for d in days),
        E144=float(res[days[-1]]["E"][-1]),
    )


def worker(cfg):
    return cfg["label"], jan_cost(cfg["params"])


def grid():
    g = []
    for a in ALPHAS:
        for r in RHOS:
            for w in WS:
                g.append(dict(label=f"a{a}_r{r}_W{w}",
                              params=dict(BEST, alpha=a, rho=r, W=w)))
    return g


def lam_scan():
    return [dict(label=f"lam{l}", params=dict(BEST, lam=l)) for l in LAMS]


def main() -> None:
    from multiprocessing import Pool

    with Pool(5) as pool:
        out = dict(pool.map(worker, grid()))
    with Pool(5) as pool:
        lam = dict(pool.map(worker, lam_scan()))

    best_key = min(out, key=lambda k: out[k]["total"])
    best_cfg = dict(zip(("alpha", "rho", "W"),
                        (float(best_key.split("_")[0][1:]),
                         float(best_key.split("_")[1][1:]),
                         int(best_key.split("_")[2][1:]))))
    jan_best = dict(BEST, **best_cfg)
    jan_best_lam = min(lam, key=lambda k: lam[k]["total"])

    # 问题 2：把 1 月最优参数拿去跑评价区间，看是否会更好
    from p3_analysis import summarize, BEST as _B, START, END
    import p3_backtest as B
    import p3_microgrid as M
    price, dates, load_kw, pv_kw, fc = M.load_all()

    def full(cfg):
        res = B.run_backtest(price, dates, load_kw, pv_kw, fc, day_range=range(0, 365),
                             use_adjust=True, adjust_mask=(True, True, True), **cfg)
        s = summarize(res)
        return {k: v for k, v in s.items() if k != "daily"}

    payload = dict(
        jan=out, lam_scan=lam,
        jan_best_key=best_key, jan_best_jan=out[best_key],
        jan_best_cfg=jan_best,
        jan_best_lam=jan_best_lam, jan_best_lam_jan=lam[jan_best_lam],
        frozen=BEST, frozen_jan=out.get(
            f"a{BEST['alpha']}_r{BEST['rho']}_W{BEST['W']}"),
        best_febdec=full(BEST),
        jan_best_febdec=full(jan_best),
        jan_best_lam_febdec=full(dict(BEST, lam=float(jan_best_lam[3:]))),
    )
    (OUT / "p3_calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"1 月最优：{best_key}  费用={out[best_key]['total']:,.2f}")
    print(f"采用值  ：a0.6_r0.5_W28  费用={payload['frozen_jan']['total']:,.2f}")
    print(f"1 月最优 lambda：{jan_best_lam}  费用={lam[jan_best_lam]['total']:,.2f}")
    print(f"评价区间（冻结 BEST）    ：{payload['best_febdec']['total']:,.2f}")
    print(f"评价区间（1 月最优参数）：{payload['jan_best_febdec']['total']:,.2f}")
    print(f"评价区间（1 月最优 λ）  ：{payload['jan_best_lam_febdec']['total']:,.2f}")
    print("已写出 06_支撑材料/p3_calibration.json")


if __name__ == "__main__":
    main()
