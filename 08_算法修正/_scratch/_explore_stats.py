# -*- coding: utf-8 -*-
import sys, numpy as np, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_microgrid import load_attach2, TAU, N
LOAD, PV, dates = load_attach2()
dts = [dt.date.fromisoformat(str(d)[:10]) for d in dates]
wd = np.array([d.weekday() for d in dts])       # 0=Mon..6=Sun
tot = LOAD.sum(1) * TAU
famA = (wd <= 3) | (wd == 6)
famB = (wd == 4) | (wd == 5)
print('族A 日总量均值 %.1f  族B %.1f  比值 %.4f'
      % (tot[famA].mean(), tot[famB].mean(), tot[famA].mean() / tot[famB].mean()))
shp = {}
for k in range(7):
    m = (wd == k)
    s = LOAD[m].mean(0) * TAU
    shp[k] = s / s.sum()
A = np.mean([shp[k] for k in range(7) if (k <= 3 or k == 6)], axis=0)
B = np.mean([shp[k] for k in range(7) if k in (4, 5)], axis=0)
print('corr(族A,族B)=%.4f' % np.corrcoef(A, B)[0, 1])
relAB = np.abs(A - B) / B
print('族间 相对差 中位 %.4f%%  最大 %.4f%% (slot %d)'
      % (np.median(relAB) * 100, relAB.max() * 100, relAB.argmax()))
for nm, ks, F in [('族A', [k for k in range(7) if k <= 3 or k == 6], A),
                  ('族B', [k for k in range(7) if k in (4, 5)], B)]:
    dev = np.concatenate([np.abs(shp[k] - F) / F for k in ks])
    print('%s 族内 相对差 中位 %.4f%%  最大 %.4f%%'
          % (nm, np.median(dev) * 100, dev.max() * 100))
pv_kwh = PV * TAU
print('光伏 全年(365天) %.1f kWh' % pv_kwh.sum())
print('光伏 Feb1-Dec31(334天) %.1f kWh' % pv_kwh[31:365].sum())
