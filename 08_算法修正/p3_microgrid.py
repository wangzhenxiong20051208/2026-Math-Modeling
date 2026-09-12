# -*- coding: utf-8 -*-
r"""
2026 CUMCM C题 问题三 —— 日前计划 + 日内滚动调整 + 实时执行

口径（与题面及附件5模板一致）：
  * 10分钟时段 i=0..143，区间 [i*10min,(i+1)*10min]，Δt=1/6h。
    附件1/2 的列标签 0:10 代表区间 0:00-0:10（右端点命名），与问题一框架一致。
  * 变量统一为电量 kWh/10min（模板单位），功率限值 M=5000*1/6=833.333 kWh。
  * 储能母线侧口径：E_t = E_{t-1}+0.9*c_t - d_t/0.9，1200<=E<=10800，E0(Jan1)=6000 跨日连续。
  * 电价 p_t 取附件1（全天相同 deterministic），问题三不用附件4。
  * 附件3预报：每天 0/6/12/18 时发布未来24个整点功率 (kW)。
    映射：预报k小时 = 发布时刻+k小时的整点功率。
    当天使用部分：0时报 1-24时；6时报 7-24时(前18个)；12时报13-24时(前12个)；18时报19-24时(前6个)。
    小时→10分钟采用因果分段线性插值（锚点为发布时刻已知实际功率），论文已验证优于阶梯保持
    （全年MAE 201 vs 362 kW）。
  * 负荷无外部预报，仅用历史实际（附件2）因果预测：同星期往期优先（周五/六低谷约3265 vs 平日5165 kW）。
  * 费用口径（论文需显式声明的唯一合理解释）：
      设 gP=计划购电，gA=最终调整后可用购电（分段提交：0-6时用计划，6-12用6时调整，12-18用12时，18-24用18时）。
      每时段总购电费（计划+调整）= p*gA + 0.5p*(gP-gA)_+  (gA<=gP, 退50%)
                                = p*gP + 1.5p*(gA-gP)_+  (gA>=gP, 追购1.5倍)
                              即 = p*gP + 1.5p*up - 0.5p*down，其中 up=(gA-gP)_+, down=(gP-gA)_+。
      若按字面“计划费+0.5p*下调+1.5p*上调”累加（p*gP+0.5p*down+1.5p*up），下调反而多付费，
      最优调整永不下调，与题设“可调整”矛盾，故该加法解读不成立，特此证伪。
      紧急购电 r 按 5p 计。总费用 = 计划调整费 + 紧急费。日末储备惩罚 lam*xi 仅用于优化引导，不计入账单。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl
import pulp

# 仓库根目录：本脚本位于 <仓库>/03_代码/ 下，取上一级即仓库根。
# 这样脚本无论放在仓库哪个位置（03_代码/ 或根目录）都能正确定位
# 01_题目 / 06_支撑材料，不再依赖硬编码的绝对路径。
ROOT = Path(__file__).resolve().parents[1]
ATT1 = ROOT/"01_题目"/"C题"/"附件"/"附件1.xlsx"
ATT2 = ROOT/"01_题目"/"C题"/"附件"/"附件2.xlsx"
ATT3 = ROOT/"01_题目"/"C题"/"附件"/"附件3.xlsx"
TEMPLATE3 = ROOT/"01_题目"/"C题"/"附件"/"附件5"/"result3.xlsx"
OUT_DIR = ROOT/"08_算法修正"/"输出"
OUT_XLSX = OUT_DIR/"result3.xlsx"
OUT_JSON = OUT_DIR/"p3_results.json"

N=144; TAU=10/60
E_MIN=1200.0; E_MAX=10800.0; E_INIT=6000.0
P_MAX=5000.0; M_ENERGY=P_MAX*TAU
EC=0.9; ED=0.9
TK=[0,36,72,108]  # 0,6,12,18时对应的起始slot
ISSUE_H=[0,6,12,18]

def load_all():
    a1=pd.read_excel(ATT1, sheet_name="Sheet1")
    price=a1.iloc[:,1].to_numpy(float)
    assert len(price)==N
    a2load=pd.read_excel(ATT2, sheet_name=0, header=0)
    a2pv=pd.read_excel(ATT2, sheet_name=1, header=0)
    dates=pd.to_datetime(a2load.iloc[:,0])
    load_kw=a2load.iloc[:,1:].to_numpy(float)
    pv_kw=a2pv.iloc[:,1:].to_numpy(float)
    assert load_kw.shape==(365,144) and pv_kw.shape==(365,144)
    import openpyxl as _oxl
    wb=_oxl.load_workbook(ATT3, read_only=True, data_only=True)
    ws=wb["Sheet1"]
    rows=list(ws.iter_rows(values_only=True))
    fc=np.zeros((365,4,24))
    for d in range(365):
        base=1+d*4
        for k in range(4):
            fc[d,k,:]=np.array([float(x) for x in rows[base+k][2:26]])
    return price, dates, load_kw, pv_kw, fc

def price_row(price, n: int) -> np.ndarray:
    """从电价数组取第n天的144时段电价：1D固定电价直接返回，2D波动电价取第n行。"""
    a = np.asarray(price, dtype=float)
    if a.ndim == 2:
        return a[n].copy()
    return a.copy()

def pv_interp_for_issue(anchor_h:int, anchor_v_kw:float, fc24:np.ndarray):
    """返回当天0-24h内144个slot的PV功率预测(kW)，因果插值。超出预报范围的返回nan。"""
    # 时间轴：anchor_h -> anchor_h+24，值：anchor_v -> fc24[0..23]
    t_nodes=np.arange(anchor_h, anchor_h+25)  # anchor, +1..+24
    # fc24[j] 对应 anchor_h+1+j
    v_nodes=np.concatenate([[anchor_v_kw], fc24])
    slot_mid=(np.arange(N)+0.5)/6.0  # 0.083..23.917
    out=np.full(N, np.nan)
    mask=(slot_mid>anchor_h)&(slot_mid<=anchor_h+24)
    out[mask]=np.interp(slot_mid[mask], t_nodes, v_nodes)
    out=np.maximum(out,0.0)
    return out

def load_predict(day_idx:int, load_kw:np.ndarray, dates) -> np.ndarray:
    """同星期优先：d-7；无则 d-1；再无则已有均值。因果。返回kW 144."""
    if day_idx-7>=0:
        return load_kw[day_idx-7,:].copy()
    if day_idx-1>=0:
        return load_kw[day_idx-1,:].copy()
    return np.full(N, load_kw[:max(1,day_idx),:].mean() if day_idx>0 else 4000.0)

def solve_lp_plan(price, net_risk_kwh, E0, E_tar=6000.0, lam=1.0):
    prob=pulp.LpProblem("plan", pulp.LpMinimize)
    g=[pulp.LpVariable(f"g{i}", lowBound=0) for i in range(N)]
    c=[pulp.LpVariable(f"c{i}", lowBound=0, upBound=M_ENERGY) for i in range(N)]
    d=[pulp.LpVariable(f"d{i}", lowBound=0, upBound=M_ENERGY) for i in range(N)]
    w=[pulp.LpVariable(f"w{i}", lowBound=0) for i in range(N)]
    E=[pulp.LpVariable(f"E{i}", lowBound=E_MIN, upBound=E_MAX) for i in range(N)]
    xi=pulp.LpVariable("xi", lowBound=0)
    prob+=pulp.lpSum([price[i]*g[i] for i in range(N)])+lam*xi
    for i in range(N):
        prob+=g[i]+d[i]==net_risk_kwh[i]+c[i]+w[i]
    for i in range(N):
        prev=E0 if i==0 else E[i-1]
        prob+=E[i]==prev+EC*c[i]-d[i]/ED
    prob+=xi>=E_tar-E[N-1]
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[prob.status]=="Optimal", prob.status
    gv=np.array([v.value() for v in g]); cv=np.array([v.value() for v in c])
    dv=np.array([v.value() for v in d]); wv=np.array([v.value() for v in w])
    Ev=np.array([v.value() for v in E])
    return gv,cv,dv,wv,Ev,float(pulp.value(prob.objective))

def solve_lp_adjust(price, net_risk_kwh, E0, gP, idx_from, E_tar=6000.0, lam=1.0):
    R=list(range(idx_from,N))
    m=len(R)
    prob=pulp.LpProblem("adj", pulp.LpMinimize)
    gA={i:pulp.LpVariable(f"gA{i}", lowBound=0) for i in R}
    up={i:pulp.LpVariable(f"up{i}", lowBound=0) for i in R}
    dn={i:pulp.LpVariable(f"dn{i}", lowBound=0) for i in R}
    c={i:pulp.LpVariable(f"c{i}", lowBound=0, upBound=M_ENERGY) for i in R}
    d={i:pulp.LpVariable(f"d{i}", lowBound=0, upBound=M_ENERGY) for i in R}
    w={i:pulp.LpVariable(f"w{i}", lowBound=0) for i in R}
    E={i:pulp.LpVariable(f"E{i}", lowBound=E_MIN, upBound=E_MAX) for i in R}
    xi=pulp.LpVariable("xi", lowBound=0)
    prob+=pulp.lpSum([1.5*price[i]*up[i]-0.5*price[i]*dn[i] for i in R])+lam*xi
    for i in R:
        prob+=gA[i]==gP[i]+up[i]-dn[i]
        prob+=dn[i]<=gP[i]+1e-9
        prob+=gA[i]+d[i]==net_risk_kwh[i]+c[i]+w[i]
    for k,i in enumerate(R):
        prev=E0 if k==0 else E[R[k-1]]
        prob+=E[i]==prev+EC*c[i]-d[i]/ED
    prob+=xi>=E_tar-E[R[-1]]
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    assert pulp.LpStatus[prob.status]=="Optimal", prob.status
    gA_full=gP.copy(); c_full=np.zeros(N); d_full=np.zeros(N); E_full=np.zeros(N)
    for i in R:
        gA_full[i]=gA[i].value(); c_full[i]=c[i].value(); d_full[i]=d[i].value(); E_full[i]=E[i].value()
    up_arr=np.array([up[i].value() for i in R]); dn_arr=np.array([dn[i].value() for i in R])
    return gA_full,c_full,d_full,E_full,up_arr,dn_arr,float(pulp.value(prob.objective))

def realtime(gA_kwh, load_kwh_actual, pv_kwh_actual, E0, Ebar_ref, rho=0.5):
    E_prev=E0; c_act=np.zeros(N); d_act=np.zeros(N); r_act=np.zeros(N); w_act=np.zeros(N); E_arr=np.zeros(N)
    for t in range(N):
        b=gA_kwh[t]+pv_kwh_actual[t]-load_kwh_actual[t]
        Rline=E_MIN+rho*(Ebar_ref[t]-E_MIN)
        Rline=min(max(Rline,E_MIN),E_MAX)
        if b>=0:
            c_act[t]=min(b, M_ENERGY, (E_MAX-E_prev)/EC if EC>0 else M_ENERGY)
            c_act[t]=max(c_act[t],0); d_act[t]=0.0
        else:
            need=-b
            maxd=max(0.0, ED*(E_prev-Rline))
            d_act[t]=min(need, M_ENERGY, maxd); c_act[t]=0.0
        r_act[t]=max(0.0, -b-d_act[t])
        w_act[t]=max(0.0, b-c_act[t])
        E_new=E_prev+EC*c_act[t]-d_act[t]/ED
        E_new=min(max(E_new,E_MIN-1e-6),E_MAX+1e-6)
        E_arr[t]=E_new; E_prev=E_new
    return c_act,d_act,r_act,w_act,E_arr

if __name__=="__main__":
    price,dates,load_kw,pv_kw,fc=load_all()
    print("loaded",price.shape,load_kw.shape,fc.shape)
