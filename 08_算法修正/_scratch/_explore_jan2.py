# -*- coding: utf-8 -*-
"""用模块自身的 Forecaster 算 1 月净负荷日绝对误差（目标 20173.9 -> 5903.7）。"""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_microgrid as M

LOAD, PV, dates = M.load_attach2()

variants = {
    'A wd0(全部历史)15/0.30': (M.ForecastParams(window=15, decay=0.30, weekday_only=False, name='负荷'),
                              M.ForecastParams(window=5, decay=0.50, weekday_only=False, name='光伏')),
    'B wd1(仅同星期)15/0.30': (M.ForecastParams(window=15, decay=0.30, weekday_only=True, name='负荷'),
                              M.ForecastParams(window=5, decay=0.50, weekday_only=False, name='光伏')),
    'C wd1 28/0.30': (M.ForecastParams(window=28, decay=0.30, weekday_only=True, name='负荷'),
                      M.ForecastParams(window=7, decay=0.30, weekday_only=False, name='光伏')),
    'D wd0 28/0.30': (M.ForecastParams(window=28, decay=0.30, weekday_only=False, name='负荷'),
                      M.ForecastParams(window=7, decay=0.30, weekday_only=False, name='光伏')),
}
for nm, (fpl, fpv) in variants.items():
    fo = M.Forecaster(LOAD, PV, fpl, fpv)
    errs_n, errs_l = [], []
    for n in range(1, 31):
        lh, vh, nh = fo.energy(n)
        l_act, v_act = LOAD[n] * M.TAU, PV[n] * M.TAU
        errs_n.append(np.abs(nh - (l_act - v_act)).sum())
        errs_l.append(np.abs(lh - l_act).sum())
    print('%-24s 净负荷 %9.1f kWh/日   负载 %9.1f' % (nm, np.mean(errs_n), np.mean(errs_l)))
