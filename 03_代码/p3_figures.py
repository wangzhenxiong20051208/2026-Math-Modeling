# -*- coding: utf-8 -*-
"""问题三论文图：预报精度、费用对比、指定日期策略轨迹。"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_microgrid import load_all, TAU, N
from cumcm_plot import savefig, setup_plot
import matplotlib.pyplot as plt
setup_plot()
ROOT=Path(__file__).resolve().parents[1]

def fig_forecast():
    price,dates,load_kw,pv_kw,fc=load_all()
    # MAE per issue for same-day hours
    actual_hp=np.array([[pv_kw[d,h*6-1] for h in range(1,25)] for d in range(365)])
    labels=["0时报\n(1-24时)","6时报\n(7-24时)","12时报\n(13-24时)"]
    maes=[]
    maes.append(np.abs(fc[:,0,:]-actual_hp).mean())
    maes.append(np.abs(fc[:,1,0:18]-actual_hp[:,6:24]).mean())
    maes.append(np.abs(fc[:,2,0:12]-actual_hp[:,12:24]).mean())
    fig,ax=plt.subplots(figsize=(7,4))
    ax.bar(labels,maes,color=["#2980b9","#27ae60","#8e44ad"],alpha=0.85)
    for i,v in enumerate(maes): ax.text(i,v*1.03,f"{v:.1f} kW",ha="center",fontsize=10)
    ax.set_ylabel("MAE (kW)")
    ax.set_title("图P3-1 各发布时刻对当天剩余时段的预报MAE")
    savefig("p3_fig_forecast_mae.png")

def fig_monthly():
    # from p3_spec totals? Use result3 vs no-adj totals approximated monthly by re-reading detail? Simplify: monthly emergency share from spec? Instead plot Jan calibration curve (already computed numbers).
    alphas=[0.5,0.6,0.7,0.8,0.9]; totals=[1233405,1227395,1245151,1293556,1469995]
    fig,ax=plt.subplots(figsize=(7,4))
    ax.plot(alphas,totals,"o-",color="#c0392b",lw=2)
    ax.axvline(0.6,color="gray",ls="--")
    ax.set_xlabel("风险分位数 α"); ax.set_ylabel("1月7-30日总费用 (元)")
    ax.set_title("图P3-2 风险分位数校准（1月因果调参，α=0.6最优）")
    savefig("p3_fig_alpha.png")
    # ablation bars
    names=["无调整","仅6时","仅12时","仅18时","12+18","全调整"]; vals=[1313130,1297021,1237785,1240311,None,1227395]
    # use Jan7-30 numbers: no-adj1313130 all1227395 only6 1297021 only12 1237785 only18 1240311; 12+18 approx? use full-year ratio? skip, plot available
    fig,ax=plt.subplots(figsize=(8,4))
    v2=[1313130,1297021,1237785,1240311,1227395]; n2=["无调整","仅6时","仅12时","仅18时","全调整"]
    ax.bar(n2,v2,color="#2980b9",alpha=0.85)
    ax.set_ylabel("1月7-30日总费用 (元)"); ax.set_title("图P3-3 消融：各调整时刻的费用贡献（1月）")
    plt.xticks(rotation=0)
    savefig("p3_fig_ablation.png")

if __name__=="__main__":
    fig_forecast(); fig_monthly(); print("figs done")
