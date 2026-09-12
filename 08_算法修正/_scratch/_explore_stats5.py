# -*- coding: utf-8 -*-
"""变体：先把「每一天」各自归一化，再按星期求平均。"""
import sys, numpy as np, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_microgrid import load_attach2, TAU

LOAD, PV, dates = load_attach2()
dts = [dt.date.fromisoformat(str(d)[:10]) for d in dates]
wd = np.array([d.weekday() for d in dts])
KA = [k for k in range(7) if k <= 3 or k == 6]
KB = [k for k in (4, 5)]

for tag, lo, hi in [('全年', 0, 365), ('正式', 31, 365)]:
    L, W = LOAD[lo:hi], wd[lo:hi]
    day_norm = L / L.sum(1, keepdims=True)              # 每天各自归一化
    shp = {k: day_norm[W == k].mean(0) for k in range(7)}
    A = np.mean([shp[k] for k in KA], axis=0)
    B = np.mean([shp[k] for k in KB], axis=0)
    d = np.abs(A - B) / B
    print(f'=== {tag} 逐日归一化 ===')
    print('  corr %.4f' % np.corrcoef(A, B)[0, 1])
    print('  族间 中位 %.4f%%  最大 %.4f%% slot%d' % (np.median(d) * 100, d.max() * 100, d.argmax()))
    for key, ks, F in [('A', KA, A), ('B', KB, B)]:
        dev = np.concatenate([np.abs(shp[k] - F) / F for k in ks])
        print('  族%s 族内 中位 %.4f%%  最大 %.4f%%' % (key, np.median(dev) * 100, dev.max() * 100))
    tot = L.sum(1) * TAU
    print('  日总量比 %.4f' % (tot[(W <= 3) | (W == 6)].mean() / tot[(W == 4) | (W == 5)].mean()))
