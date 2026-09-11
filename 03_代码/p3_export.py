# -*- coding: utf-8 -*-
"""问题三最终求解：全量回测 + 九项校验 + result3.xlsx导出 + 指定日期汇总。"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np, pandas as pd, openpyxl
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_microgrid import *
from p3_backtest import run_backtest

BEST=dict(alpha=0.6, lam=1.0, rho=0.5, E_tar=6000.0, W=28)
SPEC=["2025-03-20","2025-06-21","2025-09-23","2025-12-21"]

def fmt_slot(i):
    a=i*10; b=(i+1)*10
    def f(m):
        if m==1440: return "0:00+1"
        return f"{m//60}:{m%60:02d}"
    return f"{f(a)}-{f(b)}"

BLOCKS=[(0,24),(24,48),(48,72),(72,96),(96,120),(120,144)]
def block_label(a,z):
    sh=a*10//60; eh=24 if z*10==1440 else z*10//60
    return f"{sh}:00-{eh}:00"

def validate_day(d, price, load_kw, pv_kw, out):
    probs=[]
    gP=out["gP"]; gA=out["gA"]; c=out["c_act"]; dd=out["d_act"]; r=out["r"]; w=out["w"]; E=out["E"]; E0=out["E0"]
    p=price_row(price, d)
    # 1 balance actual
    resid=gA+pv_kw[d,:]*TAU+dd-load_kw[d,:]*TAU-c-w+r*0  # r already in balance? actual balance: gA+v+d+r = l+c+w
    # realtime guarantees gA+v+d+r-l-c-w=0 by construction (r=(-b-d)+, w=(b-c)+)
    bal=gA+pv_kw[d,:]*TAU+dd+r-load_kw[d,:]*TAU-c-w
    if np.abs(bal).max()>1e-6: probs.append(f"实际平衡残差{np.abs(bal).max():.2e}")
    # 2 storage bounds
    Eseq=np.concatenate([[E0],E])
    if Eseq.min()<E_MIN-1e-3: probs.append(f"E越下界{Eseq.min():.2f}")
    if Eseq.max()>E_MAX+1e-3: probs.append(f"E越上界{Eseq.max():.2f}")
    # 3 power
    if c.max()>M_ENERGY+1e-6: probs.append("充电越限")
    if dd.max()>M_ENERGY+1e-6: probs.append("放电越限")
    # 4 simultaneous
    if ((c>1e-6)&(dd>1e-6)).any(): probs.append("同时充放电")
    # 5 dynamics
    Erec=[E0]
    for i in range(N): Erec.append(Erec[-1]+EC*c[i]-dd[i]/ED)
    if np.abs(np.array(Erec[1:])-E).max()>1e-4: probs.append("递推不一致")
    # 6 down<=gP
    if ((gP-gA)<-1e-6).any(): pass
    if (gA<-1e-6).any(): probs.append("gA负")
    # 7 cost recompute
    up=(gA-gP).clip(min=0); down=(gP-gA).clip(min=0)
    c1=float(np.sum(p*gP+1.5*p*up-0.5*p*down))
    if abs(c1-out["cost_plan_adj"])>1e-3: probs.append("计划调整费复算不符")
    c2=float(np.sum(5*p*r))
    if abs(c2-out["cost_emg"])>1e-3: probs.append("紧急费复算不符")
    return probs

def main():
    price,dates,load_kw,pv_kw,fc=load_all()
    print("backtest full year with BEST",BEST,flush=True)
    res=run_backtest(price,dates,load_kw,pv_kw,fc,day_range=range(0,365),**BEST,use_adjust=True,adjust_mask=(True,True,True))
    # validate Feb-Dec
    bad=0
    for d in range(31,365):
        p=validate_day(d,price,load_kw,pv_kw,res[d])
        if p: bad+=1; print(dates[d].date(),p)
    print(f"校验：334天中{bad}天有问题",flush=True)
    # totals
    tot=sum(res[d]["cost_total"] for d in range(31,365))
    pa=sum(res[d]["cost_plan_adj"] for d in range(31,365))
    emg=sum(res[d]["cost_emg"] for d in range(31,365))
    print(f"Feb-Dec Total={tot:.2f} plan_adj={pa:.2f} emg={emg:.2f}",flush=True)
    # specified dates
    date_strs=[str(d.date()) for d in dates]
    # dates are Timestamps 2025-01-01 etc. map spec
    import datetime
    spec_idx={}
    for s in SPEC:
        dt=pd.to_datetime(s).date()
        for i,dd in enumerate(dates):
            if dd.date()==dt: spec_idx[s]=i; break
    print(spec_idx)
    payload={"BEST":BEST,"Feb-Dec":{"total":tot,"plan_adj":pa,"emg":emg},"spec":{}}
    for s,i in spec_idx.items():
        o=res[i]
        want_idx=[60,72,84,96,108,120]  # 10:00-10:10 is slot60? slot0=0:00-0:10, slot60=10:00-10:10 yes
        t1=[{"slot":fmt_slot(k),"gP":float(o["gP"][k]),"gA":float(o["gA"][k])} for k in want_idx]
        t2=[]
        for a,z in BLOCKS:
            t2.append({"block":block_label(a,z),"chg":float(o["c_act"][a:z].sum()),"dis":float(o["d_act"][a:z].sum())})
        # emergency events merged
        r=o["r"]; ev=[]; t=0
        while t<N:
            if r[t]>1e-6:
                s0=t
                while t<N and r[t]>1e-6: t+=1
                s1=t
                p=price_row(price,i)
                ev.append({"start":fmt_slot(s0).split("-")[0],"end":fmt_slot(s1-1).split("-")[1],"kwh":float(r[s0:s1].sum()),"cost":float(np.sum(5*p[s0:s1]*r[s0:s1]))})
            else: t+=1
        payload["spec"][s]={"table1":t1,"Gplan":float(o["gP"].sum()),"Gadj":float(o["gA"].sum()),
          "Gemg":float(o["r"].sum()),"cost_plan_adj":float(o["cost_plan_adj"]),"cost_emg":float(o["cost_emg"]),
          "cost_total":float(o["cost_total"]),"table2":t2,"E0":float(o["E0"]),"E144":float(o["E"][-1]),"emg_events":ev}
        print(s, payload["spec"][s])
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    (OUT_DIR/"p3_spec.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    # export result3.xlsx
    export_result3(price,dates,res)
    print("done",flush=True)

def export_result3(price,dates,res, out_xlsx=None, template=None):
    # copy template if output not exists else overwrite values preserving styles? Simplify: load template, overwrite.
    import shutil
    out_xlsx = Path(out_xlsx) if out_xlsx is not None else OUT_XLSX
    template = Path(template) if template is not None else TEMPLATE3
    if not out_xlsx.exists():
        shutil.copyfile(template, out_xlsx)
    wb=openpyxl.load_workbook(out_xlsx)
    # correct slot labels
    correct=[fmt_slot(i) for i in range(N)]
    for sheet in ["计划购电量","调整购电量"]:
        ws=wb[sheet]
        # header row1: keep first cell, overwrite slot labels, keep last two
        for j,lab in enumerate(correct, start=2):
            ws.cell(row=1,column=j,value=lab)
        # rows 2..335 correspond to Feb1..Dec31 (indices31..364)
        for r,d in enumerate(range(31,365), start=2):
            ws.cell(row=r,column=1,value=dates[d].to_pydatetime().replace(tzinfo=None))
            arr=res[d]["gP"] if sheet=="计划购电量" else res[d]["gA"]
            p=price_row(price, d)
            for j,v in enumerate(arr, start=2):
                ws.cell(row=r,column=j,value=round(float(v),6))
            ws.cell(row=r,column=146,value=round(float(arr.sum()),6))
            if sheet=="计划购电量":
                cost_pa=float(np.sum(p*res[d]["gP"]))
                ws.cell(row=r,column=147,value=round(cost_pa,6))
            else:
                up=(res[d]["gA"]-res[d]["gP"]).clip(min=0); down=(res[d]["gP"]-res[d]["gA"]).clip(min=0)
                cost_pa=float(np.sum(p*res[d]["gP"]+1.5*p*up-0.5*p*down))
                ws.cell(row=r,column=147,value=round(cost_pa,6))
    # 充放电量：展开全部334天
    ws=wb["充放电量"]
    # clear existing rows beyond header
    ws.delete_rows(2, ws.max_row)
    row=2
    for d in range(31,365):
        o=res[d]
        for bi,(a,z) in enumerate(BLOCKS):
            ws.cell(row=row,column=1,value=dates[d].to_pydatetime().replace(tzinfo=None) if bi==0 else None)
            ws.cell(row=row,column=2,value=block_label(a,z))
            ws.cell(row=row,column=3,value=round(float(o["c_act"][a:z].sum()),6))
            ws.cell(row=row,column=4,value=round(float(o["d_act"][a:z].sum()),6))
            if bi==0:
                ws.cell(row=row,column=5,value="0:00"); ws.cell(row=row,column=6,value=round(float(o["E0"]),6))
            elif bi==1:
                ws.cell(row=row,column=5,value="24:00"); ws.cell(row=row,column=6,value=round(float(o["E"][-1]),6))
            row+=1
    # 紧急购电量：合并连续事件
    ws=wb["紧急购电量"]
    ws.delete_rows(2, ws.max_row)
    row=2
    for d in range(31,365):
        r=res[d]["r"]; ev=[]; t=0
        while t<N:
            if r[t]>1e-6:
                s0=t
                while t<N and r[t]>1e-6: t+=1
                ev.append((s0,t,float(r[s0:t].sum())))
            else: t+=1
        if not ev: continue
        for ei,(s0,s1,kwh) in enumerate(ev):
            ws.cell(row=row,column=1,value=dates[d].to_pydatetime().replace(tzinfo=None) if ei==0 else None)
            ws.cell(row=row,column=2,value=f"{fmt_slot(s0).split('-')[0]}-{fmt_slot(s1-1).split('-')[1]}")
            ws.cell(row=row,column=3,value=round(kwh,6))
            row+=1
    wb.save(out_xlsx)
    print("saved",out_xlsx,flush=True)

if __name__=="__main__":
    main()
