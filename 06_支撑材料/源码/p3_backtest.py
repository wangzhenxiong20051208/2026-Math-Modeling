# -*- coding: utf-8 -*-
"""问题三回测：因果滚动、Jan调参、Feb-Dec评价、消融对比。"""
from __future__ import annotations
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from p3_microgrid import *

def run_backtest(price_in, dates, load_kw, pv_kw, fc, alpha=0.8, lam=1.0, rho=0.5, E_tar=6000.0, W=28,
                 use_adjust=True, adjust_mask=(True,True,True), day_range=None, verbose=False,
                 bill_price=None):
    n_days=load_kw.shape[0]
    if day_range is None: day_range=range(n_days)
    # histories of errors (kWh) for quantile: store per-day full vectors of (actual_net - pred_net) at plan/adj times
    # For simplicity pooled scalar quantile across all slots & recent W days (causal).
    plan_err_hist=[]  # list of arrays
    adj_err_hists={36:[],72:[],108:[]}  # per Tk
    E0=E_INIT
    # need to carry E0 across all days from Jan1 even if day_range starts later? Caller must ensure warmup.
    # Here we simulate only day_range but E0 passed in? Simplify: simulate from 0..max(day_range) always, record only day_range.
    maxd=max(day_range)
    results={}
    # storage for E0 per day
    E0_by_day={}
    E0_cur=E_INIT
    for d in range(0, maxd+1):
        E0_by_day[d]=E0_cur
        price=price_row(price_in, d)  # 支持2D波动电价：取当天144时段（计划价）
        # 结算价：默认与计划价相同；传入 bill_price 时计划/结算分离（合规：计划用预测、结算用实际）
        bill_d=price_row(bill_price, d) if bill_price is not None else price
        if d not in day_range:
            # still need to step storage? For days before range (warmup), we must simulate with same policy to get correct E0.
            # To avoid complexity, require day_range starts at 0. We'll just simulate all from 0.
            pass
        # ---- 0:00 plan prediction
        load_pred_kw=load_predict(d, load_kw, dates)
        anchor_v=0.0  # midnight PV=0
        pv_pred_kw=pv_interp_for_issue(0, anchor_v, fc[d,0,:])
        # nan beyond 24h? all 144 should be valid for 0:00 (covers full day)
        pv_pred_kw=np.where(np.isnan(pv_pred_kw), 0.0, pv_pred_kw)
        net_pred_kwh=(load_pred_kw-pv_pred_kw)*TAU
        # quantile from history
        if len(plan_err_hist)>=7:
            pool=np.concatenate(plan_err_hist[-W:])
            Q=np.quantile(pool, alpha)
        else:
            Q=0.0
        net_risk=net_pred_kwh+Q
        gP,_,_,_,Ebar_plan,_=solve_lp_plan(price, net_risk, E0_cur, E_tar, lam)
        # adjustments
        gA_final=gP.copy()
        Ebar_final=np.zeros(N); Ebar_final[:]=Ebar_plan  # provisional, will overwrite segments
        # track per-segment solutions for reserve
        seg_Ebars={}
        seg_Ebars[(0,36)]=Ebar_plan[0:36]
        if use_adjust:
            # ordered Tk
            Tks=[36,72,108]
            for si,Tk in enumerate(Tks):
                if not adjust_mask[si]: continue
                # observed prefix bias for load: mean(actual-pred) over [0,Tk)
                l_actual_pre=load_kw[d,0:Tk]; p_pred_pre=load_pred_kw[0:Tk]
                bias_kw=float((l_actual_pre-p_pred_pre).mean()) if Tk>0 else 0.0
                # load remaining pred = base + bias
                load_rem_pred=load_pred_kw.copy()
                load_rem_pred[Tk:]+=bias_kw
                # PV remaining pred from latest forecast anchored at actual at Tk
                issue_h=ISSUE_H[si+1]
                anchor_actual_kw=float(pv_kw[d,Tk-1])  # power at Tk:00 (slot ending)
                fc24=fc[d,si+1,:]
                pv_rem_kw=pv_interp_for_issue(issue_h, anchor_actual_kw, fc24)
                pv_rem_kw=np.where(np.isnan(pv_rem_kw), pv_pred_kw, pv_rem_kw)
                # for t<Tk keep old, for t>=Tk use new
                pv_pred_new=pv_pred_kw.copy(); pv_pred_new[Tk:]=pv_rem_kw[Tk:]
                load_pred_new=load_pred_kw.copy(); load_pred_new[Tk:]=load_rem_pred[Tk:]
                net_pred_new=(load_pred_new-pv_pred_new)*TAU
                # quantile for this Tk
                hist=adj_err_hists[Tk]
                if len(hist)>=7:
                    pool=np.concatenate(hist[-W:])
                    Qadj=np.quantile(pool, alpha)
                else:
                    Qadj=Q  # fallback to plan Q
                net_risk_new=net_pred_new.copy(); net_risk_new[Tk:]+= (Qadj)  # only remaining matters
                # E0 at Tk = actual storage after executing prefix with final gA so far?
                # To get E0_actual at Tk, we need to have simulated prefix actuals with committed gA.
                # Commit logic: segments before Tk already frozen. Simulate prefix [0,Tk) with current gA_final (which includes prior adjustments) + actuals to get E at Tk-1.
                # Use provisional Ebar for reserve? For prefix simulation use rho rule with Ebar_final provisional? Simpler: simulate prefix exactly as final realtime will do, using Ebar_final current (which for prefix segments is already final).
                # Do prefix simulation:
                E_tmp=E0_cur
                # need Ebar_ref for prefix: Ebar_final[0:Tk] (already committed)
                # run realtime prefix only
                # quick inline prefix sim
                E_prev=E0_cur
                for t in range(Tk):
                    b=gA_final[t]+pv_kw[d,t]*TAU-load_kw[d,t]*TAU
                    Rline=E_MIN+rho*(Ebar_final[t]-E_MIN); Rline=min(max(Rline,E_MIN),E_MAX)
                    if b>=0:
                        c_=min(b,M_ENERGY,(E_MAX-E_prev)/EC); dd_=0.0
                    else:
                        dd_=min(-b,M_ENERGY,max(0.0,ED*(E_prev-Rline))); c_=0.0
                    E_prev=E_prev+EC*c_-dd_/ED
                E_at_Tk=E_prev
                gA_new,_,_,Ebar_rem,_,_,_=solve_lp_adjust(price, net_risk_new, E_at_Tk, gP, Tk, E_tar, lam)
                # commit only until next Tk (or end)
                next_Tk=Tks[si+1] if si+1<len(Tks) else N
                gA_final[Tk:next_Tk]=gA_new[Tk:next_Tk]
                Ebar_final[Tk:next_Tk]=Ebar_rem[Tk:next_Tk]
        # ---- realtime full day with final gA (裁剪求解容差负值)
        gA_final=np.maximum(gA_final,0.0); gP=np.maximum(gP,0.0)
        load_act_kwh=load_kw[d,:]*TAU; pv_act_kwh=pv_kw[d,:]*TAU
        c_act,d_act,r_act,w_act,E_arr=realtime(gA_final, load_act_kwh, pv_act_kwh, E0_cur, Ebar_final, rho)
        # costs
        up=(gA_final-gP).clip(min=0); down=(gP-gA_final).clip(min=0)
        cost_plan_adj=float(np.sum(bill_d*gP+1.5*bill_d*up-0.5*bill_d*down))
        cost_emg=float(np.sum(5*bill_d*r_act))
        cost_total=cost_plan_adj+cost_emg
        # update error histories (causal for future): plan error = actual_net - pred_net (without Q)
        actual_net=(load_kw[d,:]-pv_kw[d,:])*TAU
        pred_net_plan=(load_pred_kw-pv_pred_kw)*TAU
        plan_err_hist.append(actual_net-pred_net_plan)
        # adj errors: for each Tk, error of that Tk's prediction vs actual for t>=Tk
        # reconstruct adj predictions used (need to store)? Simplify: error of final PV/load combo? For quantile we need distribution of (actual - pred_at_Tk).
        # Recompute adj preds as above (without Q) for each Tk to record error.
        for si,Tk in enumerate([36,72,108]):
            issue_h=ISSUE_H[si+1]
            anchor_actual_kw=float(pv_kw[d,Tk-1])
            pv_rem=pv_interp_for_issue(issue_h, anchor_actual_kw, fc[d,si+1,:])
            pv_rem=np.where(np.isnan(pv_rem), pv_pred_kw, pv_rem)
            # load with bias as used
            l_actual_pre=load_kw[d,0:Tk]; p_pred_pre=load_pred_kw[0:Tk]
            bias_kw=float((l_actual_pre-p_pred_pre).mean()) if Tk>0 else 0.0
            load_rem=load_pred_kw.copy(); load_rem[Tk:]+=bias_kw
            pv_full=pv_pred_kw.copy(); pv_full[Tk:]=pv_rem[Tk:]
            load_full=load_pred_kw.copy(); load_full[Tk:]=load_rem[Tk:]
            pred_net_adj=(load_full-pv_full)*TAU
            err_full=actual_net-pred_net_adj
            adj_err_hists[Tk].append(err_full[Tk:])  # only remaining matters
        E0_cur=E_arr[-1]
        if d in day_range:
            results[d]={"gP":gP.copy(),"gA":gA_final.copy(),"Ebar":Ebar_final.copy(),
                        "c_act":c_act,"d_act":d_act,"r":r_act,"w":w_act,"E":E_arr.copy(),
                        "E0":E0_by_day[d],"cost_plan_adj":cost_plan_adj,"cost_emg":cost_emg,"cost_total":cost_total,
                        "Q":float(Q)}
    return results

if __name__=="__main__":
    price,dates,load_kw,pv_kw,fc=__import__("p3_microgrid").load_all()
    # quick smoke: Jan first 3 days
    res=run_backtest(price,dates,load_kw,pv_kw,fc,day_range=range(0,3),verbose=True)
    for d,v in res.items():
        print(d, round(v["cost_total"],2), "emg", round(v["cost_emg"],2), "Q", round(v["Q"],2))
