# -*- coding: utf-8 -*-
r"""D5 原型：验证「同日同(α,λ,e0)、不同价格模式 → 计划不同」是否存在可观测差异。"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from p2_microgrid import RiskParams, solve_dayahead, LAMBDA_DEFAULT, TAU, N  # noqa
from p4_microgrid import load_attach2, load_attach4, REPORT_START            # noqa

LOAD, PV, dates = load_attach2()
PRICE = load_attach4()
print("PRICE shape", PRICE.shape)
n = REPORT_START
e0 = 5000.0
ld = LOAD[n] * TAU
pv = PV[n] * TAU
nt = (ld - pv) * TAU * 0 + (ld - pv)   # 净负荷 kWh/段
rp = RiskParams(alpha=0.80, rho=1.0, lam=LAMBDA_DEFAULT, window=28, min_samples=10)

cases = {
    "零点价": np.zeros(N),
    "平价1.0": np.full(N, 1.0),
    "固定分时": np.array([0.4] * N),
    "实际价": PRICE[n],
    "峰谷形状": np.where((np.arange(N) >= 60) & (np.arange(N) < 108), 1.2, 0.2),
}
plans = {}
for k, p in cases.items():
    pl = solve_dayahead(nt, e0, p, rp)
    plans[k] = pl.g
    print(f"{k:8s} g.sum={pl.g.sum():12.3f}  Ebar[-1]={pl.Ebar[-1]:10.3f}  g.max={pl.g.max():8.3f}")

print("\n差异矩阵 (max|Δg|):")
ks = list(cases)
for i in range(len(ks)):
    row = []
    for j in range(len(ks)):
        row.append(np.abs(plans[ks[i]] - plans[ks[j]]).max())
    print(f"{ks[i]:8s} " + " ".join(f"{v:9.2f}" for v in row))
