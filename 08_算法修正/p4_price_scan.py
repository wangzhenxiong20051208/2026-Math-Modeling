#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""附件 4 价格结构的**独立复核**——不与 p4_microgrid.py 共用任何代码。

这个脚本存在的唯一理由是"论文里的结论不能由产生它的同一段代码来自证"。
它只依赖 numpy/pandas/openpyxl，直接从 01_题目/C题/附件/ 下的原始 xlsx 读
数据，所有中间量都用与 p4_microgrid.py **不同的写法**重算一遍：

  1. 价格分解 P = F + R 的四条断言（水平相同、正交、星期结构、噪声占比）；
  2. "同星期加权 == 附件1曲线 + 同星期残差加权"这一恒等式的数值残差；
  3. 三个同星期加权方案在评价区间上的平均绝对误差，与 4 个滚动均值方案对比；
  4. 日内对数修正系数 β 在四个发布时刻上的最优值。

若两处结果不一致，以更朴素、更直接的这边为准（这边没有复用任何缓存与中间
结构）。结果写入 06_支撑材料/p4_price_scan.json 并在终端打印，便于人工核对。

用法：
    python3 03_代码/p4_price_scan.py
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------- 路径与常量
ROOT = Path(__file__).resolve().parent.parent
ATTACH1 = ROOT / "01_题目" / "C题" / "附件" / "附件1.xlsx"
ATTACH4 = ROOT / "01_题目" / "C题" / "附件" / "附件4.xlsx"
OUT = ROOT / "08_算法修正" / "输出" / "p4_price_scan.json"

N_DAY, N = 365, 144          # 365 天，每天 144 个十分钟时段
TAU = 1.0 / 6.0              # 一个时段的小时数
EVAL_LO, EVAL_HI = 31, 365   # 评价区间：2025-02-01 起共 334 天（0 基行号）
RELEASE_SLOTS = (0, 36, 72, 108)   # 0:00 / 6:00 / 12:00 / 18:00
BETA = 0.5


def load_price() -> np.ndarray:
    """读附件 4 的全年实际电价，返回 (365, 144) 的元/kWh 数组。"""
    raw = pd.read_excel(ATTACH4, header=0)
    vals = raw.iloc[:, 1:].to_numpy(dtype=float)
    assert vals.shape == (N_DAY, N), f"附件 4 形状异常 {vals.shape}"
    assert np.isfinite(vals).all(), "附件 4 存在空值或非数值"
    return vals


def load_fixed() -> np.ndarray:
    """读附件 1 的固定分时电价曲线（144 段），返回长度 144 的数组。

    附件 1 有四列（时间、电价、小区负载、光伏发电预测功率），按列名取"电价"，
    而不是按位置取最后一列——最后一列是光伏，取错会静默地算出一个假的结构。
    """
    raw = pd.read_excel(ATTACH1, header=0)
    assert "电价" in raw.columns, f"附件 1 缺少电价列：{list(raw.columns)}"
    vals = raw["电价"].to_numpy(dtype=float)
    assert vals.shape == (N,), f"附件 1 形状异常 {vals.shape}"
    return vals


def weekday_of(n: int) -> int:
    """第 n 天（0 基，2025-01-01 起）的星期几，周一 = 0。"""
    return (date(2025, 1, 1) + timedelta(days=int(n))).weekday()


# ------------------------------------------------- 1. 分解与四条断言
def check_decomposition(P: np.ndarray, F: np.ndarray) -> dict:
    R = P - F

    # 断言 1：逐时段 365 天均值是否就等于附件 1 的曲线
    dev_slot = float(np.abs(P.mean(axis=0) - F).max())
    # 断言 2：残差与骨架正交（整体相关）
    rho = float(np.corrcoef(R.ravel(), np.tile(F, N_DAY))[0, 1])

    # 断言 3：残差按星期几分组后的两个水平。两个口径都报：
    #   (a) 两个**水平均值**之差——预测器实际利用的正是这个量；
    #   (b) 逐星期均值的 max−min——不受分组方式影响的原始极差。
    # 两者相差不到 2%，但 (a) 才是预测式里出现的东西，正文引用的是 (a)。
    wd = np.array([weekday_of(n) for n in range(N_DAY)])
    grp = {int(w): float(R[wd == w].mean()) for w in range(7)}
    five = float(np.mean([grp[k] for k in (0, 1, 2, 3, 6)]))   # 周一~周四、周日
    fri_sat = float((grp[4] + grp[5]) / 2)                      # 周五、周六
    gap = five - fri_sat
    raw_gap = float(max(grp.values()) - min(grp.values()))

    # 断言 4：星期效应能解释多少残差方差
    within = float(np.mean([R[wd == w].var() for w in range(7)]))
    share = 1.0 - within / float(R.var())

    # 附加：两个"波动有多大"的刻画，正文引用它们说明价格可预测性的上限。
    #   (A) 单一固定日内形状解释的方差比例——形状取 365 天的**分段均值**，
    #       看残差方差下降多少。它含未来信息，是事后口径，只能当下界用。
    #   (B) 日间水平离散度——逐日均值的标准差**除以均价**，是无量纲的
    #       变异系数，不是"多少元/kWh"。正文引用时必须写对单位。
    prof = P.mean(axis=0)
    shape_share = 1.0 - float((P - prof).var() / P.var())
    day_mean = P.mean(axis=1)
    day_cv = float(day_mean.std() / P.mean())

    return {
        "断言1_逐时段均值与附件1最大偏差": dev_slot,
        "断言1_年平均值_附件4": float(P.mean()),
        "断言1_年平均值_附件1": float(F.mean()),
        "断言2_残差与骨架相关系数": rho,
        "断言3_星期均值": {str(k): v for k, v in grp.items()},
        "断言3_周五六均值": fri_sat,
        "断言3_其余五天均值": five,
        "断言3_两水平差_元每kWh": gap,
        "断言3_两水平差占均价": float(gap / P.mean()),
        "断言3_星期均值极差_元每kWh": raw_gap,
        "断言4_星期效应解释的方差比例": share,
        "附加_固定日内形状解释方差比": shape_share,
        "附加_日间水平离散度": day_cv,
        "附加_逐日均价标准差_元每kWh": float(day_mean.std()),
        "价格_最小值": float(P.min()),
        "价格_最大值": float(P.max()),
        "价格_均值": float(P.mean()),
        "价格_标准差": float(P.std()),
        "价格_日中位峰谷比": float(np.median(
            P.max(axis=1) / np.maximum(P.min(axis=1), 1e-12))),
    }


# ------------------------------------------------- 2. 恒等式残差
def check_identity(P: np.ndarray, F: np.ndarray) -> dict:
    """同星期加权 是否等于 附件1曲线 + 同星期残差的加权。

    左边按 P 直接加权，右边按 F 加权再加 R 的加权——若两式恒等，则
    "用同星期加权预测"等价于"用附件1曲线做骨架、只预测那个星期偏移"。
    """
    R = P - F
    w = (0.6, 0.3, 0.1)
    lags = (7, 14, 21)
    errs = []
    for n in range(EVAL_LO, EVAL_HI):
        if n - max(lags) < 0:
            continue
        num_p = sum(wi * P[n - i] for wi, i in zip(w, lags)) / sum(w)
        num_r = sum(wi * R[n - i] for wi, i in zip(w, lags)) / sum(w)
        errs.append(float(np.abs(num_p - (F + num_r)).max()))
    return {"恒等式最大残差_元每kWh": float(max(errs)),
            "恒等式核对天数": len(errs)}


# ------------------------------------------------- 3. 候选预测方案对照
def _same_weekday(P: np.ndarray, n: int, lags, w) -> np.ndarray:
    num = np.zeros(N)
    tot = float(sum(w))
    for wi, i in zip(w, lags):
        if n - i >= 0:
            num += wi * P[n - i]
    return num / tot


def _rolling_mean(P: np.ndarray, n: int, k: int) -> np.ndarray:
    lo = max(0, n - k)
    if lo == n:
        return P[n].copy()
    return P[lo:n].mean(axis=0)


def candidate_table(P: np.ndarray) -> list[dict]:
    """与 p4_microgrid.py 的候选表同口径，但用独立的实现重算。"""
    cands = [
        ("同星期加权 0.6/0.3/0.1", lambda n: _same_weekday(P, n, (7, 14, 21),
                                                           (0.6, 0.3, 0.1))),
        ("同星期加权 0.5/0.3/0.2", lambda n: _same_weekday(P, n, (7, 14, 21),
                                                           (0.5, 0.3, 0.2))),
        ("同星期等权 1/3", lambda n: _same_weekday(P, n, (7, 14, 21),
                                                   (1 / 3, 1 / 3, 1 / 3))),
        ("同星期(上周同一天)", lambda n: _same_weekday(P, n, (7,), (1.0,))),
        ("近 7 天滚动均值", lambda n: _rolling_mean(P, n, 7)),
        ("近 14 天滚动均值", lambda n: _rolling_mean(P, n, 14)),
        ("近 28 天滚动均值", lambda n: _rolling_mean(P, n, 28)),
        ("昨天同时段", lambda n: P[n - 1].copy()),
    ]
    rows = []
    for name, fn in cands:
        e = [float(np.abs(P[n] - fn(n)).mean()) for n in range(EVAL_LO,
                                                               EVAL_HI)]
        rows.append({"预测器": name,
                     "平均绝对误差_元每kWh": float(np.mean(e)),
                     "相对均价": float(np.mean(e) / P.mean())})
    rows.sort(key=lambda r: r["平均绝对误差_元每kWh"])
    return rows


# ------------------------------------------------- 4. β 扫描
BETAS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25)


def beta_scan(P: np.ndarray) -> list[dict]:
    """β 在四个发布时刻上各自的 MAE；β=0 即不做日内修正。

    只评价发布时刻"之后"的时段（t0 起点之后），发布前已经过去的时段不参与——
    否则 18:00 版本的误差里会混进整天，四个版本又不可比了。
    """
    out = []
    for beta in BETAS:
        perl = []
        for t0 in RELEASE_SLOTS:
            errs = []
            for n in range(EVAL_LO, EVAL_HI):
                base = _same_weekday(P, n, (7, 14, 21), (0.6, 0.3, 0.1))
                if t0 == 0:
                    errs.append(float(np.abs(P[n] - base).mean()))
                    continue
                dev = float(np.log(np.maximum(P[n, :t0], 1e-9)
                                   / np.maximum(base[:t0], 1e-9)).mean())
                adj = base.copy()
                adj[t0:] *= float(np.exp(beta * dev))
                errs.append(float(np.abs(P[n, t0:] - adj[t0:]).mean()))
            perl.append(float(np.mean(errs)))
        out.append({"β": beta, "各发布时刻_元每kWh": perl})

    # 每个发布时刻（6/12/18 点）各自的最优 β，便于与主流程的选择对照
    best = {int(RELEASE_SLOTS[h] // 36): min(
        out, key=lambda r: r["各发布时刻_元每kWh"][h])["β"] for h in (1, 2, 3)}
    return out, best


def main() -> None:
    print("=" * 78)
    print("附件 4 价格结构独立复核（不引用 p4_microgrid.py 的任何代码）")
    print("=" * 78)

    P, F = load_price(), load_fixed()
    print(f"附件 4：{P.shape[0]} 天 × {P.shape[1]} 时段，"
          f"{P.min():.4f}--{P.max():.4f} 元/kWh，均值 {P.mean():.4f}")

    dec = check_decomposition(P, F)
    print("\n【分解 P = F + R 的四条断言】")
    print(f"  断言 1  逐时段 365 天均值与附件 1 最大偏差 "
          f"{dec['断言1_逐时段均值与附件1最大偏差']:.3e} 元/kWh")
    print(f"  断言 2  残差与骨架相关系数 "
          f"{dec['断言2_残差与骨架相关系数']:+.3e}")
    g = dec["断言3_星期均值"]
    print("  断言 3  星期均值（周一→周日）："
          + " ".join(f"{float(v):+.4f}" for v in g.values()))
    print(f"          其余五天 {dec['断言3_其余五天均值']:+.4f} vs 周五六 "
          f"{dec['断言3_周五六均值']:+.4f}，两水平差 "
          f"{dec['断言3_两水平差_元每kWh']:.4f} 元/kWh"
          f"（占均价 {dec['断言3_两水平差占均价']:.1%}）；"
          f"原始极差 {dec['断言3_星期均值极差_元每kWh']:.4f}")
    print(f"  断言 4  星期效应解释残差方差的 "
          f"{dec['断言4_星期效应解释的方差比例']:.1%}")
    print(f"  附加    固定日内形状（365 天分段均值，事后口径）解释方差 "
          f"{dec['附加_固定日内形状解释方差比']:.1%}；"
          f"日间水平离散度 {dec['附加_日间水平离散度']:.4f}"
          f"（变异系数，无量纲；对应标准差 "
          f"{dec['附加_逐日均价标准差_元每kWh']:.4f} 元/kWh）")

    idt = check_identity(P, F)
    print(f"\n【恒等式】同星期加权 == 附件1曲线 + 同星期残差加权："
          f"最大残差 {idt['恒等式最大残差_元每kWh']:.3e} 元/kWh"
          f"（{idt['恒等式核对天数']} 天）")

    print("\n【候选预测方案（评价区间 MAE）】")
    rows = candidate_table(P)
    for r in rows:
        print(f"  {r['预测器']:<24s} {r['平均绝对误差_元每kWh']:.4f} 元/kWh"
              f"  ({r['相对均价']:.2%})")

    print("\n【日内对数修正 β 扫描（各发布时刻 MAE）】")
    bs, best = beta_scan(P)
    print("     β     0:00      6:00     12:00     18:00")
    for r in bs:
        print(f"  {r['β']:.2f}  " + "  ".join(
            f"{v:.4f}" for v in r["各发布时刻_元每kWh"]))
    print(f"  各发布时刻最优 β：{best}")

    OUT.write_text(json.dumps(
        {"分解与断言": dec, "恒等式": idt, "候选预测方案": rows,
         "β扫描": bs, "各发布时刻最优β": {str(k): v for k, v in best.items()},
         "口径": "独立脚本，直接读附件 xlsx，不复用 p4_microgrid.py"},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写出 {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
