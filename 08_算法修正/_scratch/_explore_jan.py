# -*- coding: utf-8 -*-
"""试算 1 月净负荷日绝对误差的几种口径，目标 20173.9 -> 5903.7 kWh/日。"""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_microgrid import load_attach2, TAU

LOAD, PV, dates = load_attach2()


def daily_abs(weekday_only, win, decay, mode):
    errs = []
    for n in range(1, 31):
        if mode == 'window':
            idx = np.arange(max(0, n - win), n)
            if weekday_only:
                same = idx[(idx - n) % 7 == 0]
                if len(same):
                    idx = same
            w = decay ** ((n - 1 - idx) / 7.0); w = w / w.sum()
            l_hat = (LOAD[idx] * w[:, None]).sum(0) * TAU
        elif mode == 'prev':
            l_hat = LOAD[n - 1] * TAU
        elif mode == 'allmean':
            l_hat = LOAD[max(0, n - 7):n].mean(0) * TAU if n >= 7 else LOAD[:n].mean(0) * TAU
        elif mode == 'samewd_all':
            same = np.arange(n)[(np.arange(n) - n) % 7 == 0]
            l_hat = LOAD[same].mean(0) * TAU if len(same) else LOAD[:n].mean(0) * TAU
        n_act = (LOAD[n] - PV[n]) * TAU
        n_hat = l_hat - PV[n] * TAU            # 光伏用实际值，只看负载预测误差
        errs.append(np.abs(n_hat - n_act).sum())
    return float(np.mean(errs))


cases = [
    ('window win15 d0.30 wd=1', dict(weekday_only=True, win=15, decay=0.30, mode='window')),
    ('window win15 d0.30 wd=0', dict(weekday_only=False, win=15, decay=0.30, mode='window')),
    ('prev-day', dict(weekday_only=False, win=1, decay=1.0, mode='prev')),
    ('allmean 7', dict(weekday_only=False, win=7, decay=1.0, mode='allmean')),
    ('samewd all', dict(weekday_only=True, win=0, decay=1.0, mode='samewd_all')),
    ('window win28 d0.30 wd=1', dict(weekday_only=True, win=28, decay=0.30, mode='window')),
    ('window win28 d0.30 wd=0', dict(weekday_only=False, win=28, decay=0.30, mode='window')),
]
for nm, kw in cases:
    print('%-28s %10.1f kWh/日' % (nm, daily_abs(**kw)))
