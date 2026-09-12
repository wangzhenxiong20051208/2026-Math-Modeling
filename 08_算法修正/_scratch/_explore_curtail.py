# -*- coding: utf-8 -*-
"""试算弃电分解口径，目标：W1=1,769,824.2 / W2=693,721 / cost=466,267 / 光伏=19,068,890。"""
import pandas as pd, numpy as np
from pathlib import Path

p = Path('C:/Users/海平面之恋/Documents/GitHub/2026-Math-Modeling/06_支撑材料/p2_detail.csv')
df = pd.read_csv(p, encoding='utf-8-sig')
print('列:', list(df.columns)[:22])
print('行数', len(df), ' 日期范围', df['日期'].iloc[0], '~', df['日期'].iloc[-1])
w = df['弃电_kWh'].to_numpy(float)
pv = df['实际光伏_kWh'].to_numpy(float)
ld = df['实际负载_kWh'].to_numpy(float)
pr = df['电价_元每kWh'].to_numpy(float)
g = df['计划购电_kWh'].to_numpy(float)
print('光伏合计 %.1f kWh  (目标 19,068,890)' % pv.sum())
print('弃电合计 %.2f kWh  (目标 2,463,544.98)' % w.sum())
mask_surplus = pv > ld                       # 光伏富余
W1 = w[mask_surplus].sum(); W2 = w[~mask_surplus].sum()
print('W1(光伏富余时段) %.2f  (目标 1,769,824.2)  占比 %.4f%%' % (W1, W1 / w.sum() * 100))
print('W2(无富余时段)   %.2f  (目标 693,721)     占比 %.4f%%' % (W2, W2 / w.sum() * 100))
for nm, c in [('Σ p·w  (W2)', (pr * w * (~mask_surplus)).sum()),
              ('Σ p·g  (W2)', (pr * g * (~mask_surplus)).sum()),
              ('Σ p·(g-pv+ld)(W2)', (pr * np.clip(g, 0, None) * (~mask_surplus)).sum())]:
    print('  %-20s %.2f 元  (目标 466,267)' % (nm, c))
