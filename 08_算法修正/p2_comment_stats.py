# -*- coding: utf-8 -*-
r"""
问题二：正文/注释里引用、但此前无脚本产出的统计量的**唯一溯源脚本**。

背景（同学按国奖标准的 D9 条）：论文 §6.3、§6.5 与附录用了一批数字——
日总量两族比 1.58、两族日内形状相关系数 0.888、族间逐时段相对差中位 8.9%／
最大 38.5%（slot 105 = 17:30）、族内中位 0.250%／0.254%、族内最大约 22%，
以及弃电成因分解 12.9%／71.8%（1,769,824.2）／28.2%（693,721）／成本 466,267 元
——它们此前**只以注释形式写在 p2_microgrid.py:165--174 里，没有任何脚本产出**，
属于"溯源缺口"。本脚本把它们的口径固定下来并可复现，输出到
`08_算法修正/输出/p2_comment_stats.json`。

口径（逐条固定，避免"换个算法就对不上"）：
  族划分      周一--周四 + 周日 = 族A（高）；周五、周六 = 族B（低）
  日总量比    族A 日总电量均值 / 族B 日总电量均值（全年 365 天）
  日内形状    **先把每一天各自归一化**（除以当天总电量），再按星期几求平均，
              再按族求平均。（先按星期平均再归一化会得到 8.85%/37.9%，
              与论文不符——这一点必须写清，否则复现不出来。）
  相对差      |族A形状 − 族B形状| / 族B形状（论文明确"以周五六一族为基准"）
  族内偏差    |该星期几形状 − 所属族形状| / 族形状，对 (星期几, 时段) 取中位/最大
  弃电分解    光伏富余时段 = 实际光伏 > 实际负载；W1 为其弃电量，W2 为其余；
              W2 的购电成本 = Σ p_t·w_t（被弃掉的已购电量的电费）
  光伏发电量  正式区间（2/1--12/31，334 天）Σ 实际光伏
  1月预测误差 日总量净负荷绝对误差 |Σ_t(N̂−N_t)|，负荷 win15/decay0.30、
              光伏 win5/decay0.50，仅切换 weekday_only；n=1..30 取平均

运行：python p2_comment_stats.py
"""
from __future__ import annotations
import json
import sys
import datetime as dt
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
OUT = HERE / "输出"
OUT.mkdir(parents=True, exist_ok=True)

from p2_microgrid import load_attach2, TAU, N, weekday_of    # noqa: E402

KA = [0, 1, 2, 3, 6]        # 周一--周四 + 周日
KB = [4, 5]                 # 周五、周六
REPORT_START, REPORT_END = 31, 365                                  # 2/1 -- 12/31


def family_and_shape_stats(LOAD: np.ndarray, wd: np.ndarray) -> dict:
    """族统计：日总量比、形状相关、族间/族内相对差。定义见模块 docstring。"""
    res: dict = {}
    tot = LOAD.sum(1) * TAU
    famA = np.isin(wd, KA)
    famB = np.isin(wd, KB)
    res["日总量比_族A比族B"] = float(tot[famA].mean() / tot[famB].mean())
    res["族A日总量均值_kWh"] = float(tot[famA].mean())
    res["族B日总量均值_kWh"] = float(tot[famB].mean())

    # 关键：逐日各自归一化后再按星期平均
    day_norm = LOAD / LOAD.sum(1, keepdims=True)
    shp = {k: day_norm[wd == k].mean(0) for k in range(7)}
    A = np.mean([shp[k] for k in KA], axis=0)
    B = np.mean([shp[k] for k in KB], axis=0)

    res["两族形状相关系数"] = float(np.corrcoef(A, B)[0, 1])
    rel = np.abs(A - B) / B
    res["族间相对差_中位_百分比"] = float(np.median(rel) * 100)
    res["族间相对差_最大_百分比"] = float(rel.max() * 100)
    res["族间相对差_最大所在时段"] = str(int(rel.argmax() * 10 // 60)) + ":" + \
        f"{int(rel.argmax() * 10 % 60):02d}"
    for nm, ks, F in (("族A", KA, A), ("族B", KB, B)):
        dev = np.concatenate([np.abs(shp[k] - F) / F for k in ks])
        res[f"{nm}族内相对差_中位_百分比"] = float(np.median(dev) * 100)
        res[f"{nm}族内相对差_最大_百分比"] = float(dev.max() * 100)
    return res


def curtailment_stats(detail_csv: Path) -> dict:
    """弃电成因分解。读逐时段明细（p2_detail.csv）。"""
    import pandas as pd
    df = pd.read_csv(detail_csv, encoding="utf-8-sig")
    w = df["弃电_kWh"].to_numpy(float)
    pv = df["实际光伏_kWh"].to_numpy(float)
    ld = df["实际负载_kWh"].to_numpy(float)
    pr = df["电价_元每kWh"].to_numpy(float)
    surplus = pv > ld
    W, W1 = float(w.sum()), float(w[surplus].sum())
    W2 = W - W1
    return {
        "明细文件": str(detail_csv),
        "时段数": int(len(df)),
        "光伏发电量_kWh": float(pv.sum()),
        "弃电量_kWh": W,
        "弃电占光伏_百分比": float(W / pv.sum() * 100),
        "光伏富余时段弃电量_kWh": W1,
        "光伏富余时段占比_百分比": float(W1 / W * 100),
        "无富余时段弃电量_kWh": W2,
        "无富余时段占比_百分比": float(W2 / W * 100),
        "无富余时段弃电的购电成本_元": float((pr * w * ~surplus).sum()),
    }


def january_predictor_mae(LOAD: np.ndarray, PV: np.ndarray) -> dict:
    """仅用 1 月数据判定"按星期分组预测"是否成立：净负荷日绝对误差对比。

    口径（经逐项比对固定，与 p2_microgrid.py:164 注释一致）：
      · 误差定义 = **日总量净负荷的绝对误差** |Σ_t (N̂_t − N_t)|，单位 kWh/日，
        再对 1 月（第 1--30 天，n=0 无历史故跳过）取平均；
        注意这不是逐时段绝对值之和 Σ_t|err|（那会得到 20455.4 / 8249.1），
        也不是逐时段平均——两者都对不上注释里的 20173.9 / 5903.7。
      · 超参数用模块冻结值：负荷 win=15/decay=0.30，光伏 win=5/decay=0.50。
      · 对照只切换负荷的 weekday_only：全部历史(False) → 仅同星期(True)。
    """
    def mae(weekday_only: bool) -> float:
        errs = []
        for n in range(1, 31):
            idx = np.arange(max(0, n - 15), n)
            wts = 0.30 ** ((n - 1 - idx) / 7.0)
            if weekday_only:
                same = np.array([weekday_of(i) == weekday_of(n) for i in idx])
                if same.any():
                    wts = wts * same
            wts = wts / wts.sum()
            l_hat = (LOAD[idx] * wts[:, None]).sum(0) * TAU
            pidx = np.arange(max(0, n - 5), n)
            pw = 0.50 ** ((n - 1 - pidx) / 7.0); pw = pw / pw.sum()
            v_hat = (PV[pidx] * pw[:, None]).sum(0) * TAU
            n_hat = (l_hat - v_hat).sum()                 # 日总量预测
            n_act = ((LOAD[n] - PV[n]) * TAU).sum()        # 日总量实际
            errs.append(abs(n_hat - n_act))
        return float(np.mean(errs))

    return {"仅用全部历史日_净负荷日绝对误差_kWh每日": mae(False),
            "仅同星期历史日_净负荷日绝对误差_kWh每日": mae(True)}


def main() -> None:
    LOAD, PV, dates = load_attach2()
    dts = [dt.date.fromisoformat(str(d)[:10]) for d in dates]
    wd = np.array([d.weekday() for d in dts])

    payload: dict = {"口径说明": __doc__.split("运行：")[0].strip()}
    payload.update(family_and_shape_stats(LOAD, wd))
    payload.update(january_predictor_mae(LOAD, PV))

    detail = OUT / "p2_detail.csv"
    if not detail.exists():
        alt = ROOT / "06_支撑材料" / "p2_detail.csv"
        detail = alt if alt.exists() else detail
    if detail.exists():
        payload["弃电成因分解"] = curtailment_stats(detail)
    else:
        payload["弃电成因分解"] = "缺 p2_detail.csv，先运行 p2_microgrid.py"

    (OUT / "p2_comment_stats.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 74)
    print("问题二 正文数字溯源（p2_comment_stats.py）")
    print("=" * 74)
    for k, v in payload.items():
        if isinstance(v, str):
            continue
        if isinstance(v, dict):
            print(f"\n[{k}]")
            for kk, vv in v.items():
                print(f"  {kk:34s} {vv if not isinstance(vv, float) else round(vv, 4)}")
        else:
            print(f"  {k:34s} {v if not isinstance(v, float) else round(v, 4)}")
    print(f"\n已写出 {OUT / 'p2_comment_stats.json'}")


if __name__ == "__main__":
    main()
