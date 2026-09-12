# -*- coding: utf-8 -*-
"""问题三：在已完成模型（p3_microgrid / p3_backtest / p3_export）之上做全套量化分析。

论文所需的每一个数字都从本脚本产生，`p3_tables.py` 与 `p3_figures.py` 只做排版，
不再自行计算。分析分五组：

  1. 主结果           全年因果回放（1 月预热、2 月 1 日--12 月 31 日评价）
  2. 预报组合消融     6:00 / 12:00 / 18:00 三个发布时刻的 2^3 = 8 种取法，
                      外加"只用 0:00 预报"的对照（共 9 条策略）
  3. 口径敏感性       计费口径（退款 / 不退款）与风险分位数口径（跨时段合并 / 逐时段）
  4. 参数敏感性       alpha、rho、lambda、W 四个参数的单变量扰动
  5. 逐日校验与精度   九项逐日一致性检查、附件 3 四个发布版本的预报精度

后两组中的"不退款口径"与"逐时段分位数"两个变体，由本脚本按最小改动从
`p3_microgrid.py` / `p3_backtest.py` 自动生成到 `03_代码/_p3_variants/`，
生成规则写在 `build_variants()` 里，改动只有一行目标函数或两处分位数语句。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
OUT = ROOT / "06_支撑材料"
OUT.mkdir(exist_ok=True)
VAR = HERE / "_p3_variants"
VAR.mkdir(exist_ok=True)

START, END = 31, 365          # 评价区间：2 月 1 日 -- 12 月 31 日（334 天）
BEST = dict(alpha=0.6, lam=1.0, rho=0.5, E_tar=6000.0, W=28)
TKS = (36, 72, 108)
ADJ_LABELS = ("6:00", "12:00", "18:00")
COMMON = slice(108, 144)      # 四个发布版本共同覆盖的时段：18:00--24:00


# ------------------------------------------------------------------ 变体生成
def build_variants() -> None:
    """把两个口径变体写成独立模块，供消融实验导入。"""
    (VAR / "__init__.py").write_text("", encoding="utf-8")
    src_m = (HERE / "p3_microgrid.py").read_text(encoding="utf-8")
    src_b = (HERE / "p3_backtest.py").read_text(encoding="utf-8")

    # 变体一：不退款口径。调减不产生贷方，于是调整 LP 的目标去掉 -0.5*p*dn。
    m_c = src_m.replace(
        "prob+=pulp.lpSum([1.5*price[i]*up[i]-0.5*price[i]*dn[i] for i in R])+lam*xi",
        "prob+=pulp.lpSum([1.5*price[i]*up[i] for i in R])+lam*xi",
    )
    assert m_c != src_m, "不退款口径的目标函数替换失败"
    (VAR / "p3_microgrid_c.py").write_text(m_c, encoding="utf-8")

    #   backtest 的其余名字（常量、预测、实时规则）在 _c 模块里是同一份拷贝，
    #   所以只要把 import 改指到 _c，它调用的 solve_lp_adjust 就自动换成不退款的那一版。
    b_c = src_b.replace(
        "from p3_microgrid import *", "from p3_microgrid_c import *"
    ).replace(
        "cost_plan_adj=float(np.sum(bill_d*gP+1.5*bill_d*up-0.5*bill_d*down))",
        "cost_plan_adj=float(np.sum(bill_d*gP+1.5*bill_d*up))",
    )
    assert "from p3_microgrid_c import *" in b_c, "不退款口径的 import 替换失败"
    assert "-0.5*bill_d*down" not in b_c, "不退款口径的结算式替换失败"
    (VAR / "p3_backtest_c.py").write_text(b_c, encoding="utf-8")

    # 变体二：逐时段分位数。把"跨全部时段合并成一个标量"换成"每段各自一个分位数"。
    old_plan = """        if len(plan_err_hist)>=7:
            pool=np.concatenate(plan_err_hist[-W:])
            Q=np.quantile(pool, alpha)
        else:
            Q=0.0
        net_risk=net_pred_kwh+Q"""
    new_plan = """        if len(plan_err_hist)>=7:
            pool=np.stack(plan_err_hist[-W:])
            Q=np.quantile(pool, alpha, axis=0)
        else:
            Q=np.zeros(N)
        net_risk=net_pred_kwh+Q"""
    old_adj = """                hist=adj_err_hists[Tk]
                if len(hist)>=7:
                    pool=np.concatenate(hist[-W:])
                    Qadj=np.quantile(pool, alpha)
                else:
                    Qadj=Q  # fallback to plan Q"""
    new_adj = """                hist=adj_err_hists[Tk]
                if len(hist)>=7:
                    pool=np.stack(hist[-W:])
                    Qadj=np.quantile(pool, alpha, axis=0)
                else:
                    Qadj=Q[Tk:]  # 样本不足时退回 0:00 版的逐时段分位数"""
    b_ps = src_b.replace(old_plan, new_plan).replace(old_adj, new_adj)
    b_ps = b_ps.replace('"Q":float(Q)}', '"Q":float(np.mean(Q))}')
    assert b_ps != src_b, "逐时段分位数变体的替换失败"
    (VAR / "p3_backtest_ps.py").write_text(b_ps, encoding="utf-8")

    # 变体模块放在 _p3_variants/ 下，要能 import 到主模块与彼此。路径插入必须
    # 落在 `from __future__` 之后，否则会破坏“future 导入须在最前”的语法要求。
    for name in ("p3_microgrid_c.py", "p3_backtest_c.py", "p3_backtest_ps.py"):
        p = VAR / name
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        at = 0
        for i, ln in enumerate(lines):
            if ln.startswith("from __future__"):
                at = i + 1
                break
            if i > 80:      # 文件头 docstring 可能很长，但不会超过 80 行
                break
        lines.insert(at,
                     "import sys as _sys\n"
                     f"_sys.path.insert(0, r'{HERE}')\n"
                     f"_sys.path.insert(0, r'{VAR}')\n")
        p.write_text("".join(lines), encoding="utf-8")


# ------------------------------------------------------------------ 汇总
def summarize(res) -> dict:
    """把一个全年回放结果压成汇总量。"""
    N = len(res[END - 1]["gA"])
    tot = pa = em = 0.0
    gP_s = gA_s = r_s = c_s = d_s = w_s = up_s = dn_s = 0.0
    n_days_chg = 0
    n_emg_events = 0
    E_min, E_max = np.inf, -np.inf
    daily = []
    for d in range(START, END):
        o = res[d]
        up = np.clip(o["gA"] - o["gP"], 0, None)
        dn = np.clip(o["gP"] - o["gA"], 0, None)
        tot += o["cost_total"]; pa += o["cost_plan_adj"]; em += o["cost_emg"]
        gP_s += o["gP"].sum(); gA_s += o["gA"].sum(); r_s += o["r"].sum()
        c_s += o["c_act"].sum(); d_s += o["d_act"].sum(); w_s += o["w"].sum()
        up_s += up.sum(); dn_s += dn.sum()
        n_days_chg += int((np.abs(o["gA"] - o["gP"]) > 1e-6).any())
        r = o["r"]; t = 0
        while t < N:
            if r[t] > 1e-6:
                n_emg_events += 1
                while t < N and r[t] > 1e-6:
                    t += 1
            else:
                t += 1
        seq = np.concatenate([[o["E0"]], o["E"]])
        E_min = min(E_min, float(seq.min())); E_max = max(E_max, float(seq.max()))
        daily.append(dict(
            day=d, total=o["cost_total"], plan_adj=o["cost_plan_adj"], emg=o["cost_emg"],
            gP=float(o["gP"].sum()), gA=float(o["gA"].sum()), up=float(up.sum()),
            dn=float(dn.sum()), r=float(r.sum()), w=float(o["w"].sum()),
            charge=float(o["c_act"].sum()), discharge=float(o["d_act"].sum()),
            E0=float(o["E0"]), E144=float(o["E"][-1]),
            Emin=float(seq.min()), Emax=float(seq.max()),
            nsub=int((np.abs(o["gA"] - o["gP"]) > 1e-6).sum()),
        ))
    return dict(
        total=tot, plan_adj=pa, emg=em, gP=gP_s, gA=gA_s, r=r_s,
        charge=c_s, discharge=d_s, curtail=w_s, up=up_s, dn=dn_s,
        n_days_adjusted=n_days_chg, n_emg_events=n_emg_events,
        E_min=E_min, E_max=E_max,
        E0_first=float(res[START]["E0"]), E144_last=float(res[END - 1]["E"][-1]),
        daily=daily,
    )


def worker(cfg):
    """一个配置 = 一次全年回放。子进程里执行。"""
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(VAR))
    if cfg["kind"] == "norefund":
        import p3_backtest_c as B
    elif cfg["kind"] == "perslot":
        import p3_backtest_ps as B
    else:
        import p3_backtest as B
    import p3_microgrid as M

    price, dates, load_kw, pv_kw, fc = M.load_all()
    kw = dict(cfg["params"])
    if cfg["kind"] == "ctrl":
        res = B.run_backtest(price, dates, load_kw, pv_kw, fc,
                             day_range=range(0, 365), use_adjust=False, **kw)
    else:
        res = B.run_backtest(price, dates, load_kw, pv_kw, fc,
                             day_range=range(0, 365), use_adjust=True,
                             adjust_mask=cfg["mask"], **kw)
    s = summarize(res)
    if cfg.get("dump"):
        np.savez_compressed(
            OUT / "p3_main_arrays.npz",
            **{f"gP_{d}": res[d]["gP"] for d in range(START, END)},
            **{f"gA_{d}": res[d]["gA"] for d in range(START, END)},
            **{f"r_{d}": res[d]["r"] for d in range(START, END)},
            **{f"c_{d}": res[d]["c_act"] for d in range(START, END)},
            **{f"d_{d}": res[d]["d_act"] for d in range(START, END)},
            **{f"E_{d}": res[d]["E"] for d in range(START, END)},
            **{f"Ebar_{d}": res[d]["Ebar"] for d in range(START, END)},
        )
    return cfg["label"], s


def build_configs():
    cfgs = [
        dict(label="主策略", kind="main", mask=(True, True, True), params=BEST, dump=True),
        dict(label="对照：只用0:00预报", kind="ctrl", mask=None, params=BEST),
        dict(label="敏感性：不退款口径", kind="norefund", mask=(True, True, True), params=BEST),
        dict(label="敏感性：逐时段分位数", kind="perslot", mask=(True, True, True), params=BEST),
    ]
    for i in range(1, 8):
        mask = tuple(bool(i >> k & 1) for k in range(3))
        name = "+".join(ADJ_LABELS[k] for k in range(3) if mask[k])
        cfgs.append(dict(label=name, kind="combo", mask=mask, params=BEST))
    return cfgs


def param_grid():
    g = []
    for a in (0.5, 0.6, 0.7, 0.8):
        for r in (0.35, 0.5, 0.7):
            g.append(dict(label=f"alpha={a},rho={r}", kind="combo",
                          mask=(True, True, True), params=dict(BEST, alpha=a, rho=r)))
    for lam in (0.0, 0.5):
        g.append(dict(label=f"lam={lam}", kind="combo", mask=(True, True, True),
                      params=dict(BEST, lam=lam)))
    for w in (14, 21):
        g.append(dict(label=f"W={w}", kind="combo", mask=(True, True, True),
                      params=dict(BEST, W=w)))
    return g


# ------------------------------------------------------------------ 逐日校验
def validation():
    """九项逐日一致性检查（与 p3_export.py 中的校验完全同一套判据）。"""
    from p3_export import validate_day
    import p3_microgrid as M
    import p3_backtest as B
    price, dates, load_kw, pv_kw, fc = M.load_all()
    res = B.run_backtest(price, dates, load_kw, pv_kw, fc,
                         day_range=range(0, 365), use_adjust=True,
                         adjust_mask=(True, True, True), **BEST)
    n_days_bad = 0
    problems: set[str] = set()
    worst = dict(balance=0.0, dynamics=0.0, cost_adj=0.0, cost_emg=0.0)
    for d in range(START, END):
        o = res[d]
        bal = np.abs(o["gA"] + pv_kw[d, :] * M.TAU + o["d_act"] + o["r"]
                     - load_kw[d, :] * M.TAU - o["c_act"] - o["w"])
        worst["balance"] = max(worst["balance"], float(bal.max()))
        rec = [o["E0"]] + list(o["E"])
        dyn = np.abs(np.array([rec[i] + M.EC * o["c_act"][i] - o["d_act"][i] / M.ED
                               for i in range(len(o["c_act"]))]) - np.array(o["E"]))
        worst["dynamics"] = max(worst["dynamics"], float(dyn.max()))
        up = np.clip(o["gA"] - o["gP"], 0, None); down = np.clip(o["gP"] - o["gA"], 0, None)
        c1 = float((price * o["gP"] + 1.5 * price * up - 0.5 * price * down).sum())
        c2 = float((5 * price * o["r"]).sum())
        worst["cost_adj"] = max(worst["cost_adj"], abs(c1 - o["cost_plan_adj"]))
        worst["cost_emg"] = max(worst["cost_emg"], abs(c2 - o["cost_emg"]))
        probs = validate_day(d, price, load_kw, pv_kw, o)
        if probs:
            n_days_bad += 1
            problems.update(probs)
    return dict(n_days_bad=n_days_bad, problems=sorted(problems),
                n_days=END - START, worst=worst)


# ------------------------------------------------------------------ 预报精度
def forecast_skill():
    """附件 3 四个发布版本的光伏预报精度。

    只报"绝对误差（kW）"而不报相对误差：各版本的覆盖时段长度不同，18:00 版只覆盖
    18:00--24:00 这一段光伏趋零的夜间，任何以"该时段平均功率"为分母的相对指标都会
    被极小的分母放大成无意义的数字。因此改为并列三个绝对口径：

      mae_kw       该版本自己覆盖到的全部时段
      mae_noon_kw  12:00--18:00（白天最后一段，光伏最强、方案差异最大）
      mae_eve_kw   18:00--24:00（四版共同覆盖的时段，唯一可横向比较的窗口）
    """
    import p3_microgrid as M
    price, dates, load_kw, pv_kw, fc = M.load_all()
    NOON = slice(72, 108)
    rows = []
    for k, h in enumerate([0, 6, 12, 18]):
        err_all, err_noon, err_eve = [], [], []
        for d in range(START, END):
            anchor = 0.0 if h == 0 else float(pv_kw[d, int(h * 6) - 1])
            f = M.pv_interp_for_issue(h, anchor, fc[d, k, :])
            m = ~np.isnan(f)
            act = pv_kw[d, :]
            err_all.append(np.abs(f[m] - act[m]))
            for sl, buf in ((NOON, err_noon), (COMMON, err_eve)):
                mm = np.zeros_like(m)
                mm[sl] = m[sl]
                if mm.any():
                    buf.append(np.abs(f[mm] - act[mm]))
        rows.append(dict(
            release=f"{h}:00",
            n=int(np.concatenate(err_all).size),
            mae_kw=float(np.concatenate(err_all).mean()),
            mae_noon_kw=float(np.concatenate(err_noon).mean()) if err_noon else None,
            mae_eve_kw=float(np.concatenate(err_eve).mean()),
        ))
    pd.DataFrame(rows).to_csv(OUT / "p3_forecast_skill.csv", index=False)
    return rows


# ------------------------------------------------------------------ 主流程
def main():
    from multiprocessing import Pool

    build_variants()
    with Pool(5) as pool:
        out = pool.map(worker, build_configs())
    main_res = dict(out)
    for k, v in main_res.items():
        print(f"{k:>22s}  total={v['total']:,.2f}  "
              f"计划调整={v['plan_adj']:,.2f}  紧急={v['emg']:,.2f}")

    with Pool(5) as pool:
        gout = pool.map(worker, param_grid())

    d = pd.DataFrame(main_res["主策略"]["daily"])
    d.to_csv(OUT / "p3_main_daily.csv", index=False)

    payload = dict(
        configs={k: {kk: vv for kk, vv in v.items() if kk != "daily"}
                 for k, v in main_res.items()},
        daily=main_res["主策略"]["daily"],
        params={k: {kk: vv for kk, vv in v.items() if kk != "daily"}
                for k, v in dict(gout).items()},
        skill=forecast_skill(),
        validation=validation(),
        best=BEST,
        start=START, end=END,
    )
    json.dump(payload, open(OUT / "p3_analysis.json", "w"),
              ensure_ascii=False, indent=1)
    print("已写出 06_支撑材料/p3_analysis.json")


if __name__ == "__main__":
    main()
