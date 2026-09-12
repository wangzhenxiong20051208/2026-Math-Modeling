# -*- coding: utf-8 -*-
"""扫描族统计的各种口径定义，找出与论文数字完全一致的那种。

论文目标值（main.tex:802-805 与 p2_microgrid.py 注释）：
  日总量比值 1.58 | 相关系数 0.888
  族间 中位 8.9%、最大 38.5%（slot 105 = 17:30）
  族A 族内 中位 0.250%、最大 22% | 族B 族内 中位 0.254%
"""
import sys, numpy as np, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p2_microgrid import load_attach2, TAU

LOAD, PV, dates = load_attach2()
dts = [dt.date.fromisoformat(str(d)[:10]) for d in dates]
wd = np.array([d.weekday() for d in dts])
KA = [k for k in range(7) if k <= 3 or k == 6]
KB = [k for k in (4, 5)]

win = [('全年', 0, 365), ('正式', 31, 365)]
for tag, lo, hi in win:
    L, W = LOAD[lo:hi], wd[lo:hi]
    raw = {k: L[W == k].mean(0) * TAU for k in range(7)}          # 逐星期平均(kWh/段)
    tot = {k: raw[k].sum() for k in range(7)}
    nor = {k: raw[k] / tot[k] for k in range(7)}                  # 各自归一化
    A_n = np.mean([nor[k] for k in KA], axis=0)
    B_n = np.mean([nor[k] for k in KB], axis=0)
    A_r = raw[KA[0]].copy()
    A_r = np.mean([raw[k] for k in KA], axis=0)
    A_r = A_r / A_r.sum()
    B_r = np.mean([raw[k] for k in KB], axis=0)
    B_r = B_r / B_r.sum()
    print(f'=== {tag} ===')
    for nmA, A in [('mean-of-norm', A_n), ('norm-of-mean', A_r)]:
        for nmB, B in [('mean-of-norm', B_n), ('norm-of-mean', B_r)]:
            d = np.abs(A - B) / B
            print(f'  族间[{nmA}|{nmB}] 中位 {np.median(d)*100:.4f}% 最大 {d.max()*100:.4f}% slot{d.argmax()}')
    # 族内
    for nmf, F_dic in [('mean-of-norm', None), ('norm-of-mean', None)]:
        pass
    for nmf in ['mean-of-norm', 'norm-of-mean']:
        for key, ks in [('A', KA), ('B', KB)]:
            if nmf == 'mean-of-norm':
                F = np.mean([nor[k] for k in ks], axis=0)
                dev = np.concatenate([np.abs(nor[k] - F) / F for k in ks])
            else:
                Fr = np.mean([raw[k] for k in ks], axis=0)
                Fr = Fr / Fr.sum()
                dev = np.concatenate([np.abs(raw[k] / raw[k].sum() - Fr) / Fr for k in ks])
            print(f'  族{key} 族内[{nmf}] 中位 {np.median(dev)*100:.4f}% 最大 {dev.max()*100:.4f}%')
    # 族内：用原始均值轮廓相除（不归一化）
    for key, ks in [('A', KA), ('B', KB)]:
        Fr = np.mean([raw[k] for k in ks], axis=0)
        dev = np.concatenate([np.abs(raw[k] - Fr) / Fr for k in ks])
        print(f'  族{key} 族内[raw/raw] 中位 {np.median(dev)*100:.4f}% 最大 {dev.max()*100:.4f}%')
