# -*- coding: utf-8 -*-
"""试算：不同口径下族统计是否等于论文值。"""
import sys, numpy as np, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_microgrid import load_attach2, TAU

LOAD, PV, dates = load_attach2()
dts = [dt.date.fromisoformat(str(d)[:10]) for d in dates]
wd = np.array([d.weekday() for d in dts])


def stats(lo, hi, tag):
    L, W = LOAD[lo:hi], wd[lo:hi]
    tot = L.sum(1) * TAU
    famA = (W <= 3) | (W == 6)
    famB = (W == 4) | (W == 5)
    print(f'--- {tag} 天数 {hi-lo} ---')
    print('  日总量比 %.4f' % (tot[famA].mean() / tot[famB].mean()))
    shp = {}
    for k in range(7):
        m = (W == k)
        s = L[m].mean(0) * TAU
        shp[k] = s / s.sum()
    A = np.mean([shp[k] for k in range(7) if (k <= 3 or k == 6)], axis=0)
    B = np.mean([shp[k] for k in range(7) if k in (4, 5)], axis=0)
    print('  corr %.4f' % np.corrcoef(A, B)[0, 1])
    for nm, d in [('族间', (A - B) / B), ('族间abs', np.abs((A - B) / B))]:
        print('  %s 中位 %.4f%%  最大 %.4f%%  峰slot %d'
              % (nm, np.median(np.abs(d)) * 100, np.abs(d).max() * 100, np.abs(d).argmax()))
    for nm, ks, F in [('族A', [k for k in range(7) if k <= 3 or k == 6], A),
                      ('族B', [k for k in range(7) if k in (4, 5)], B)]:
        dev = np.concatenate([np.abs(shp[k] - F) / F for k in ks])
        print('  %s 族内 中位 %.4f%%  最大 %.4f%%'
              % (nm, np.median(dev) * 100, dev.max() * 100))


stats(0, 365, '全年')
stats(31, 365, '正式区间 Feb-Dec')
stats(0, 31, '1 月')
