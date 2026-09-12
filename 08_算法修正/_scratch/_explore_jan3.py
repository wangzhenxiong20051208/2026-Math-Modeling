# -*- coding: utf-8 -*-
r"""D9 溯源：1月「净负荷日绝对误差 20173.9 → 5903.7 kWh/日」的口径搜索。

候选口径：
  metric: (a) Σ_t |N_hat − N_act|  (日总量等效绝对误差, kWh/日)
          (b) mean_t |N_hat − N_act|  (逐时段平均, kWh/(段·日))
          (c) |Σ_t (N_hat − N_act)|   (日总量偏差绝对值)
  load:   win ∈ {15,28}, decay ∈ {0.30}, weekday_only ∈ {F,T}
  pv:     win ∈ {5,7}, decay ∈ {0.50,0.30}, weekday_only ∈ {F,T}
  days:   predict n ∈ {1..30, 7..30, 0..30(需历史)}
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from p2_microgrid import load_attach2, TAU, N, weekday_of  # noqa

LOAD, PV, dates = load_attach2()


def fc(n, arr, window, decay, wk):
    idx = np.arange(max(0, n - window), n)
    if len(idx) == 0:
        return None
    w = decay ** ((n - 1 - idx) / 7.0)
    if wk:
        same = np.array([weekday_of(i) == weekday_of(n) for i in idx])
        if same.any():
            w = w * same
    w = w / w.sum()
    return (arr[idx] * w[:, None]).sum(0)


def run(metric, lw, ld, lwk, pw, pd_, pwk, days):
    es = []
    for n in days:
        lh = fc(n, LOAD, lw, ld, lwk)
        vh = fc(n, PV, pw, pd_, pwk)
        if lh is None or vh is None:
            continue
        nh = (lh - vh) * TAU
        na = (LOAD[n] - PV[n]) * TAU
        e = nh - na
        if metric == "sum":
            es.append(np.abs(e).sum())
        elif metric == "mean":
            es.append(np.abs(e).mean())
        else:
            es.append(abs(e.sum()))
    return float(np.mean(es)) if es else float("nan")


print("目标：全部历史 20173.9 ；仅同星期 5903.7")
for days_lbl, days in [("n=1..30", list(range(1, 31))), ("n=7..30", list(range(7, 31))),
                       ("n=0..30", list(range(0, 31)))]:
    for metric in ("sum", "mean", "total"):
        for lw in (15, 28):
            for pw, pd_ in ((5, 0.50), (5, 0.30), (7, 0.30), (7, 0.50)):
                a = run(metric, lw, 0.30, False, pw, pd_, False, days)
                b = run(metric, lw, 0.30, True, pw, pd_, False, days)
                flag = ""
                if abs(a - 20173.9) < 300 or abs(b - 5903.7) < 300:
                    flag = "  <<<<<<"
                print(f"{days_lbl} {metric:5s} lw{lw} pv{pw}/{pd_:.2f}   "
                      f"全部={a:11.1f}  同星期={b:11.1f}{flag}")
    print("-" * 78)
