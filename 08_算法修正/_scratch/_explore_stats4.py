# -*- coding: utf-8 -*-
"""再扫一批口径：未归一化的水平轮廓、中位数轮廓、分母互换。"""
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
    print(f'=== {tag} ===')
    for how in ['mean', 'median']:
        agg = (lambda x: x.mean(0)) if how == 'mean' else (lambda x: np.median(x, 0))
        A = agg(L[(W <= 3) | (W == 6)]) * TAU          # 未归一化水平
        B = agg(L[(W == 4) | (W == 5)]) * TAU
        for nm, d in [('|A-B|/B', np.abs(A - B) / B), ('|A-B|/A', np.abs(A - B) / A),
                      ('|A-B|/mean', np.abs(A - B) / ((A + B) / 2))]:
            print(f'  [{how}水平] {nm:12s} 中位 {np.median(d)*100:.4f}% '
                  f'最大 {d.max()*100:.4f}% slot{d.argmax()}')
        # 族内（未归一化水平）
        for key, ks in [('A', KA), ('B', KB)]:
            Fr = agg(L[(W <= 3) | (W == 6)]) * TAU if key == 'A' else \
                 agg(L[(W == 4) | (W == 5)]) * TAU
            dev = np.concatenate([np.abs(agg(L[W == k]) * TAU - Fr) / Fr for k in ks])
            print(f'  [{how}] 族{key} 族内 中位 {np.median(dev)*100:.4f}% 最大 {dev.max()*100:.4f}%')
