# -*- coding: utf-8 -*-
r"""
2026 年高教社杯全国大学生数学建模竞赛  C 题
微网与外部电网电力调控策略 —— 问题三

多次预报驱动的滚动购电与储能调度模型
--------------------------------------------------------------------------
【D2 口径警示 · 必读】本模块是问题三的**早期版本建模库**，`p3_rolling_figures.py`
/`p3_rolling_tables.py` 读取的旧结果文件已随旧版删除，本模块**不再产生论文中
问题三的任何数字**。论文问题三的全部数字出自另一套实现链：

    p3_microgrid.py  →  p3_backtest.py  →  p3_export.py（写出 result3.xlsx）

本模块之所以仍须提交，仅因问题四 `p4_microgrid.py` 直接 import 了它的
ForecastPanel / build_eps3 / solve_adjust / DayRunner 等构件。

**计费口径命名冲突（务必分清）**：本模块的 `convention="main"` 指的是
**不退款口径**（下调记 0、不允许调减），`convention="refund"` 才是退款口径。
而论文正文 `main.tex:69` 声明**问题三的主口径是退款口径**。也就是说，代码里的
字符串 `"main"` 与论文里的"主口径"**指的不是同一件事**——代码的 `"main"` 是
"问题四不退款口径"沿用的历史命名。为避免读代码的人按字面理解成"论文主口径"，
本模块在其 docstring 与常量处一律显式标注"不退款"，并用
`CONV_NO_REFUND` / `CONV_REFUND` 两个自明别名对外暴露；`"main"` 仅作兼容别名保留。
--------------------------------------------------------------------------
实现依据：《问题三_解题思路与实现框架》
  01_题目/C题/问题三_解题思路与实现框架.md

与问题二的差别只在**信息来源**与**计费口径**两处，物理模型完全一致：

  * 信息来源：光伏不再由历史外推预测，而是直接使用附件 3 中当日已发布的
    预报版本；每天 0:00／6:00／12:00／18:00 各有一个版本，每个版本覆盖发布
    时刻之后的 24 个整点。负载仍在历史外推的基础上叠加"当日已观测时段"的
    日内比例修正。
  * 计费口径（框架 3.2 节口径，即本文代码所称的**不退款**口径，token="main"；
    **注意它不等于论文问题三的主口径**——论文问题三主口径是退款口径）：
    计划费 Σp g⁰ 全额照付，调整费另计
    A_t = 1.5p(x_t-g⁰_t)_+ + 0.5p(g⁰_t-x_t)_+，紧急费 Σ5p r。允许无偿弃电时
    调减没有费用优势，因此该口径直接令 x_t ≥ g⁰_t，A_t 退化为 1.5p(x_t-g⁰_t)。
    框架 3.3 节的"退款口径" J^refund（token="refund"）作为独立敏感性检查，
    由 solve_adjust / run_day3 / replay3 的 convention 参数切换；主流程
    以 REFUND_TAG 追加一个 convention="refund" 的策略并行回放。

三个量必须分清（框架 3.1 节）：
  g⁰_t  0:00 冻结的初始计划购电量，永久保存，不被后续调整覆盖；
  x_t   该时段**最终生效的完整购电量**（不是增量、不是多次版本之和）；
  r_t   实际发生的紧急购电量。
最终收到的常规电量与紧急电量之和为 G^received = G^effective + G^emg。

交付块策略（框架 3.4 节）：每个六小时交付块只在块首正式调整一次，
0:00 提交全天 144 段，6:00 提交 6:00—12:00，12:00 提交 12:00—18:00，
18:00 提交 18:00—24:00。更远时段在优化里作为**展望值**参与，但不提交、
不收费、不写入最终调整结果。

时间纪律（框架 8.2 节第 1 项）：任何求解只使用"发布时刻不晚于决策时刻"的
预报版本，以及"目标时段已经过去"的实际观测；误差样本同样满足该条件。
--------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_microgrid import (  # noqa: E402
    N, TAU, E_MIN, E_MAX, E_INIT, M_ENERGY, ETA,
    interval_label, fmt_time, block_label,
)
from p2_microgrid import (  # noqa: E402
    ROOT, N_DAY, REPORT_START, REPORT_END, SPECIAL_DATES, WANT_LABELS,
    EMG_EPS, E_TAR, Forecaster, RiskParams, load_attach2, solve_dayahead,
    forecast_weights,
)

# ---------------------------------------------------------------- 路径
ATTACH3 = ROOT / "01_题目" / "C题" / "附件" / "附件3.xlsx"
TEMPLATE3 = ROOT / "01_题目" / "C题" / "附件" / "附件5" / "result3.xlsx"
OUT_DIR = ROOT / "08_算法修正" / "输出"
OUT_XLSX3 = OUT_DIR / "result3.xlsx"
OUT_JSON3 = OUT_DIR / "p3_results.json"
OUT_DETAIL3 = OUT_DIR / "p3_detail.csv"
OUT_DAILY3 = OUT_DIR / "p3_daily.csv"
OUT_COMBOS3 = OUT_DIR / "p3_combinations.csv"
# 每个策略求解完成后立刻把汇总结果落盘。整轮比较要跑四十多分钟（大头是
# 滚动标定的上万次 MILP），若不缓存，一旦后续写文件出错就全部作废。
CACHE_DIR = OUT_DIR / "p3_cache"

# ---------------------------------------------------------------- 常量
RELEASE_HOURS = (0, 6, 12, 18)          # 每天四次发布的整点
N_RELEASE = 4
BLOCK_BOUNDS = [(0, 36), (36, 72), (72, 108), (108, 144)]   # 四个六小时交付块
FOUR_HOUR_BLOCKS = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120),
                    (120, 144)]
ALL_S = (6, 12, 18)                     # 0:00 之外可选的三个发布时刻

INTRADAY_LOAD = True                    # 负载是否启用日内比例修正
MIN_KAPPA_SAMPLES = 6                   # 开启日内修正所需的最少已观测时段数

# 主计费口径下追加电量的价格系数（1.5 倍总价，不是先付原价再加 1.5 倍）
COEF_UP = 1.5
# 退款口径下调减的净效果：退回 p 再付 0.5p，故为 -0.5p
COEF_DOWN = 0.5
# 紧急购电的额外价格系数
COEF_EMG = 5.0

# 敏感性检查的计费口径。**注意命名**（见模块 docstring 的 D2 警示）：
#   "main"   —— 代码内部的**不退款**口径：x_t >= g⁰_t，调减记 0（不允许调减），
#               调整费 A_t = 1.5p(x_t-g⁰_t)_+。**它不是论文里那个"主口径"**：
#               论文问题三的主口径是退款口径。这里沿用"main"只是为了与
#               问题四 p4_microgrid.py 的 CONVENTIONS 保持同一套字符串，
#               历史原因，与论文用词无关。
#   "refund" —— 框架 3.3 节的退款口径：允许调减，下调退回 0.5p。
# 对外请用自明别名 CONV_NO_REFUND / CONV_REFUND，避免把 "main" 误读成"论文主口径"。
CONVENTIONS = ("main", "refund")
CONV_NO_REFUND = "main"      # ← 代码里的"不退款口径"（论文问题四主口径）
CONV_REFUND = "refund"       # ← 退款口径（论文问题三主口径）


# ================================================================ 模块 1：数据与版本整理
@dataclass
class ForecastPanel:
    """附件 3 的长表化结果与按版本索引的预报值。

    F[hi, n, j] 是第 n 天第 hi 次发布对"发布后 j 小时"的预测功率（kW）。
    j = 1..24 直接来自附件 3 的 24 列；j = 0 是发布时刻本身的锚点，附件
    未提供，按框架 2.3 节的约定由**同一时刻早先版本**的预报补齐：
        hi = 1,2,3 → 当天上一次发布的"预报 6 小时"（正好指向本次发布时刻）
        hi = 0     → 前一日 18:00 发布的"预报 6 小时"（指向当日 0:00）
        n  = 0     → 无更早版本，取 0（全年 0:00—0:10 的实际光伏恒为 0）
    """

    F: np.ndarray                 # (4, N_DAY, 25)
    long: pd.DataFrame            # 长表：日期 / 发布时刻 / 目标时间 / 提前时长 / 功率
    anchor_source: np.ndarray     # (4, N_DAY) 每个版本的锚点来源，供核对


def load_attach3() -> ForecastPanel:
    """读取附件 3，向下补齐日期，展开为长表并建立版本索引。"""
    raw = pd.read_excel(ATTACH3, sheet_name=0)
    if raw.shape != (N_DAY * N_RELEASE, 2 + 24):
        raise ValueError(f"附件 3 形状应为 {(N_DAY * N_RELEASE, 26)}，实际 {raw.shape}")

    # 日期列只有每天第一行有值，其余为空；只对**日期**列向下补齐，
    # 功率列绝不做任何填充（框架 2.1 节的明确要求）。
    day_col = raw.iloc[:, 0].astype("object").copy()
    filled, cur = [], None
    for v in day_col:
        if isinstance(v, str) and v.strip() not in ("", "nan"):
            cur = pd.Timestamp(v)
        elif v is not None and not (isinstance(v, float) and np.isnan(v)):
            cur = pd.Timestamp(v)
        if cur is None:
            raise ValueError("附件 3 首个数据行缺少日期")
        filled.append(cur)

    dates = pd.DatetimeIndex(filled)
    if dates.nunique() != N_DAY:
        raise ValueError(f"附件 3 日期应有 {N_DAY} 个不同值，实际 {dates.nunique()}")
    if dates[0] != pd.Timestamp("2025-01-01") or dates[-1] != pd.Timestamp("2025-12-31"):
        raise ValueError(f"附件 3 日期区间应为 2025-01-01~2025-12-31，实际 "
                         f"{dates[0].date()}~{dates[-1].date()}")

    rel_col = raw.iloc[:, 1].astype(str).str.strip()
    for k in range(N_RELEASE):
        blk = rel_col.iloc[k::N_RELEASE].unique()
        if list(blk) != [f"{RELEASE_HOURS[k]}:00"] and \
           list(blk) != [f"{RELEASE_HOURS[k]:02d}:00"]:
            raise ValueError(f"附件 3 第 {k} 行的发布时刻应恒为 "
                             f"{RELEASE_HOURS[k]}:00，实际 {blk}")

    power = raw.iloc[:, 2:].to_numpy(float)
    if np.isnan(power).any():
        raise ValueError("附件 3 功率列存在空值")
    if power.min() < 0:
        raise ValueError("附件 3 功率列存在负值")

    F = np.zeros((N_RELEASE, N_DAY, 25))
    F[:, :, 1:] = power.reshape(N_DAY, N_RELEASE, 24).transpose(1, 0, 2)

    # ---- 首端锚点 F^0^{(τ)}
    anchor_source = np.empty((N_RELEASE, N_DAY), dtype=object)
    for n in range(N_DAY):
        for hi in range(N_RELEASE):
            if hi > 0:
                F[hi, n, 0] = F[hi - 1, n, 6]
                anchor_source[hi, n] = f"{RELEASE_HOURS[hi-1]}:00 发布，预报 6 小时"
            elif n > 0:
                F[0, n, 0] = F[3, n - 1, 6]
                anchor_source[0, n] = "前一日 18:00 发布，预报 6 小时"
            else:
                # 2025-01-01 0:00 之前没有版本可用；该时刻的实际光伏为 0，
                # 且不能使用之后才得到的真实值，故取 0 并在此显式声明。
                F[0, n, 0] = 0.0
                anchor_source[0, n] = "无更早版本，取 0（0:00 实际光伏为 0）"

    # ---- 长表（模块 1 的交付物之一）
    hi_of = np.repeat(np.arange(N_RELEASE), N_DAY)
    recs = []
    for hi in range(N_RELEASE):
        base = pd.Timestamp("2025-01-01") + pd.to_timedelta(np.arange(N_DAY), "D")
        rel = base + pd.Timedelta(hours=RELEASE_HOURS[hi])
        for j in range(1, 25):
            recs.append(pd.DataFrame({
                "发布日期": base,
                "发布时间": rel,
                "目标时间": rel + pd.Timedelta(hours=j),
                "提前时长_h": j,
                "预测功率_kW": F[hi, :, j],
            }))
    long = pd.concat(recs, ignore_index=True)

    return ForecastPanel(F=F, long=long, anchor_source=anchor_source)


# ================================================================ 模块 2：预报时间转换
def _interp_hour(A: np.ndarray, rel_min: float) -> float:
    """在同一发布版本内部做分段线性插值。

    A[j] 是发布后 j 小时的预测功率（kW），j = 0..24，节点间隔 60 min。
    rel_min 是相对发布时刻的分钟数，取值 [0, 1440]。
    """
    if rel_min <= 0.0:
        return float(A[0])
    if rel_min >= 1440.0:
        return float(A[24])
    j = int(rel_min // 60)
    th = (rel_min - 60.0 * j) / 60.0
    return float((1.0 - th) * A[j] + th * A[j + 1])


def forecast_energy_slots(fp: ForecastPanel, hi: int, n: int) -> np.ndarray:
    """把某次发布的整点功率预报积分成当天各十分钟时段的光伏电量（kWh）。

    返回长度 144 的数组；发布时刻之前（已经执行过）的时段记为 NaN。
    十分钟边界与整点对齐，每个区间都落在同一段线性插值内，故
    v̂_t = (V̂(a_t) + V̂(b_t)) / 2 · Δt 精确等于该区间上插值曲线的积分。
    """
    t0 = 36 * hi
    out = np.full(N, np.nan)
    A = fp.F[hi, n, :]
    rel0 = 60 * 6 * hi            # 发布时刻相对当天 0:00 的分钟数
    for t in range(t0, N):
        ra = t * 10.0 - rel0
        rb = ra + 10.0
        out[t] = 0.5 * (_interp_hour(A, ra) + _interp_hour(A, rb)) * TAU
    return out


def load_forecast_at(l_hat_day: np.ndarray, l_kwh: np.ndarray,
                     hi: int) -> np.ndarray:
    """决策时刻 hi 的负载预测（kWh）。

    hi = 0 用历史外推的日形状；hi > 0 时再用当天**已经观测完**的时段算一个
    比例修正 kappa，作用在尚未执行的时段上（框架 4.1 节）。已观测时段过少
    时不启用修正，避免小样本放大噪声。
    """
    t0 = 36 * hi
    out = l_hat_day.copy()
    if hi == 0 or not INTRADAY_LOAD or t0 < MIN_KAPPA_SAMPLES:
        return out
    pred = float(l_hat_day[:t0].sum())
    obs = float(l_kwh[:t0].sum())
    if pred <= 1e-9:
        return out
    kappa = obs / pred
    out[t0:] = l_hat_day[t0:] * kappa
    return out


# ================================================================ 模块 3：负载与误差更新
def build_eps3(LOAD: np.ndarray, PV: np.ndarray, fp: ForecastPanel,
               fo: Forecaster) -> np.ndarray:
    """按发布版本维护可验证的净负荷预测残差。

    eps3[hi, n, t] = N_act(n,t) - N̂_t^{(hi,n)}，只在 t >= 36·hi 上有定义。
    hi > 0 的样本使用当日的日内比例修正——该修正只取当天 0:00 至发布时刻
    之间的实际负载，样本被后续日期使用时整日早已观测完毕，不会引入未来信息。
    """
    eps = np.full((N_RELEASE, N_DAY, N), np.nan)
    l_kwh_all = LOAD * TAU
    n_act_all = (LOAD - PV) * TAU
    for n in range(1, N_DAY):
        l_hat_day, _, _ = fo.energy(n)
        l_kwh = l_kwh_all[n]
        for hi in range(N_RELEASE):
            t0 = 36 * hi
            l_hat = load_forecast_at(l_hat_day, l_kwh, hi)
            v_hat = forecast_energy_slots(fp, hi, n)
            eps[hi, n, t0:] = n_act_all[n, t0:] - (l_hat - v_hat)[t0:]
    return eps


def forecast_skill(LOAD: np.ndarray, PV: np.ndarray, fp: ForecastPanel,
                   fo: Forecaster) -> dict:
    """各发布版本在正式区间内的净负荷预测误差。

    三个口径分开报，避免把「逐时段绝对偏差之和」当成「全天电量偏差」：
      * 逐时段绝对偏差之和 = Σ_t |N_t - Ñ_t|（kWh/日），衡量十分钟尺度的错位；
      * 全天电量偏差       = |Σ_t (N_t - Ñ_t)|（kWh/日），衡量日总量口径；
      * 符号偏差           = Σ_t (N_t - Ñ_t)（kWh/日），正表示净负荷被低估。
    另给出「对照_历史外推」，即问题二那套光伏外推预测在同一区间的表现，
    用于说明附件 3 的 0:00 版本并不比历史外推更准——这正是后续发布时刻
    具有价值的原因。
    """
    n_days = REPORT_END - REPORT_START
    out, acc = {}, {}
    keys = list(RELEASE_HOURS) + ["hist"]
    for k in keys:
        acc[k] = [0.0, 0.0, 0.0]          # |逐时段|之和 / |全天|之和 / 符号和
    denom = 0.0
    for n in range(REPORT_START, REPORT_END):
        n_act = (LOAD[n] - PV[n]) * TAU
        l_hat_day, _, n_hat_hist = fo.energy(n)
        for hi, hr in enumerate(RELEASE_HOURS):
            t0 = 36 * hi
            l_hat = load_forecast_at(l_hat_day, LOAD[n] * TAU, hi)
            v_hat = forecast_energy_slots(fp, hi, n)
            d = n_act[t0:] - (l_hat - v_hat)[t0:]
            acc[hr][0] += float(np.abs(d).sum())
            acc[hr][1] += abs(float(d.sum()))
            acc[hr][2] += float(d.sum())
        d = n_act - n_hat_hist
        acc["hist"][0] += float(np.abs(d).sum())
        acc["hist"][1] += abs(float(d.sum()))
        acc["hist"][2] += float(d.sum())
        denom += float(n_act.sum())
    mean_net = denom / n_days
    for hr, (a, b, c) in acc.items():
        name = "对照_历史外推" if hr == "hist" else hr
        out[name] = {
            "逐时段绝对偏差之和_kWh每日": a / n_days,
            "全天电量偏差_kWh每日": b / n_days,
            "符号偏差_kWh每日": c / n_days,
            "相对日净负荷": (b / n_days) / mean_net,
        }
    out["平均日净负荷_kWh"] = mean_net
    return out


def risk_margin3(eps: np.ndarray, hi: int, n: int, alpha: float | None,
                 window: int = 28, min_samples: int = 10) -> np.ndarray:
    """Q_{α,τ,t}：只用第 n 天之前、且版本 hi 的历史残差。"""
    t0 = 36 * hi
    out = np.zeros(N)
    if alpha is None or n == 0:
        return out
    lo = max(0, n - window)
    hist = eps[hi, lo:n, t0:]
    hist = hist[~np.isnan(hist).all(axis=1)]
    k = hist.shape[0]
    if k >= min_samples:
        out[t0:] = np.quantile(hist, alpha, axis=0)
        return out
    if k >= 3:
        # 样本不足时合并相邻时段（±2 个十分钟），仍然只用过去数据
        m = hist.shape[1]
        pooled = np.empty_like(hist)
        for s in range(m):
            a, b = max(0, s - 2), min(m, s + 3)
            pooled[:, s] = hist[:, a:b].mean(axis=1)
        out[t0:] = np.quantile(pooled, alpha, axis=0)
    return out


# ================================================================ 模块 4/5：滚动规划 MILP
_PC3: dict[int, dict] = {}


def _precomp3(m: int) -> dict:
    """为"剩余 m 个时段"的调整问题装配 MILP 结构（与日期无关，缓存复用）。

    变量分块（顺序即下标顺序）：
        y(m) 候选购电量 | a(m) 上调量 | b(m) 下调量 | c(m) 充电 | d(m) 放电
        | w(m) 弃电 | r(m) 规划缺口 | E(m) 参考储电量 | z(m) 充放电互斥 | ξ

    y - a + b = g⁰ 把分段调整费用线性化：
        不退款口径（token="main"）→ ub[b] = 0，lb[y] = g⁰_t，于是 a = (y-g⁰)_+
        退款口径（token="refund"）→ lb[y] = 0，a,b ≥ 0，目标中 b 的系数为 -0.5p
    最小化时不可能出现 a、b 同时为正（同增 δ 使费用增加 1.0pδ），故无需整数
    变量即可精确表达该分段函数。
    """
    if m in _PC3:
        return _PC3[m]

    nvar = 9 * m + 1
    iY, iA, iB, iC, iD, iW, iR, iE, iZ, iXi = (
        0, m, 2 * m, 3 * m, 4 * m, 5 * m, 6 * m, 7 * m, 8 * m, 9 * m)

    rows, cols, vals = [], [], []

    def add(r, c, v):
        rows.append(r); cols.append(c); vals.append(v)

    # (1) 风险净负荷平衡：y + r + d - c - w = Ñ_t          行 0..m-1
    for i in range(m):
        add(i, iY + i, 1.0); add(i, iR + i, 1.0); add(i, iD + i, 1.0)
        add(i, iC + i, -1.0); add(i, iW + i, -1.0)

    # (2) 状态递推：E_t - E_{t-1} - ηc_t + d_t/η = 0       行 m..2m-1
    for i in range(m):
        r = m + i
        add(r, iE + i, 1.0)
        if i > 0:
            add(r, iE + i - 1, -1.0)
        add(r, iC + i, -ETA); add(r, iD + i, 1.0 / ETA)

    # (3) 调整量分解：y - a + b = g⁰_t                      行 2m..3m-1
    for i in range(m):
        r = 2 * m + i
        add(r, iY + i, 1.0); add(r, iA + i, -1.0); add(r, iB + i, 1.0)

    A_eq = csr_matrix((vals, (rows, cols)), shape=(3 * m, nvar))

    ur, uc, uv = [], [], []

    def uadd(r, c, v):
        ur.append(r); uc.append(c); uv.append(v)

    for i in range(m):
        uadd(2 * i, iC + i, 1.0); uadd(2 * i, iZ + i, -M_ENERGY)
        uadd(2 * i + 1, iD + i, 1.0); uadd(2 * i + 1, iZ + i, M_ENERGY)
    uadd(2 * m, iXi, -1.0); uadd(2 * m, iE + m - 1, -1.0)

    A_ub = csr_matrix((uv, (ur, uc)), shape=(2 * m + 1, nvar))

    lb = np.concatenate([
        np.zeros(m),            # y（求解时抬到 g⁰_t 或保持 0）
        np.zeros(m),            # a
        np.zeros(m),            # b
        np.zeros(m),            # c
        np.zeros(m),            # d
        np.zeros(m),            # w
        np.zeros(m),            # r
        np.full(m, E_MIN),      # E
        np.zeros(m),            # z
        [0.0],                  # ξ
    ])
    ub = np.concatenate([
        np.full(m, np.inf),     # y
        np.full(m, np.inf),     # a
        np.full(m, np.inf),     # b（主口径求解时压到 0）
        np.full(m, M_ENERGY),   # c
        np.full(m, M_ENERGY),   # d
        np.full(m, np.inf),     # w
        np.full(m, np.inf),     # r
        np.full(m, E_MAX),      # E
        np.ones(m),             # z
        [np.inf],               # ξ
    ])
    integ = np.zeros(nvar)
    integ[iZ:iZ + m] = 1

    d = {"nvar": nvar, "A_eq": A_eq, "A_ub": A_ub, "lb": lb, "ub": ub,
         "integ": integ, "iY": iY, "iA": iA, "iB": iB, "iR": iR, "iE": iE,
         "iXi": iXi, "m": m}
    _PC3[m] = d
    return d


@dataclass
class AdjustPlan:
    y: np.ndarray        # 剩余时段最终生效的完整购电量（含展望部分）
    up: np.ndarray       # 上调量 a_t
    down: np.ndarray     # 下调量 b_t
    Ebar: np.ndarray     # 参考储电量轨迹
    r_plan: np.ndarray   # 规划缺口
    fee: float           # 本次求解出的调整费（不含已确定的原计划费）


def solve_adjust(ntilde: np.ndarray, g0_rem: np.ndarray, e0: float,
                 price_rem: np.ndarray, rp: RiskParams,
                 convention: str = "main", etar: float = E_TAR) -> AdjustPlan:
    """在剩余时段上求解调整模型（框架 4.3 节）。

    目标 = Σ A_t(y_t; g⁰_t) + Σ 5p r̄_t + λξ，原计划费是常数，不重复计入。
    """
    if convention not in CONVENTIONS:
        raise ValueError(f"未知计费口径 {convention!r}")
    m = len(ntilde)
    if not (E_MIN - 1e-9 <= e0 <= E_MAX + 1e-9):
        raise ValueError(f"日初储电量 e0={e0:.6f} 超出 [{E_MIN}, {E_MAX}] kWh")

    d = _precomp3(m)
    iY, iA, iB, iR, iE, iXi = (d["iY"], d["iA"], d["iB"], d["iR"], d["iE"],
                               d["iXi"])

    b_eq = np.empty(3 * m)
    b_eq[:m] = ntilde
    b_eq[m] = e0
    b_eq[m + 1:2 * m] = 0.0
    b_eq[2 * m:] = g0_rem

    b_ub = np.empty(2 * m + 1)
    b_ub[:2 * m] = np.tile([0.0, M_ENERGY], m)
    b_ub[2 * m] = -etar

    lb = d["lb"].copy()
    ub = d["ub"].copy()
    if convention == "main":
        lb[iY:iY + m] = g0_rem          # x_t ≥ g⁰_t，a 自动等于上调量
        ub[iB:iB + m] = 0.0             # 禁掉下调量
    else:
        lb[iY:iY + m] = 0.0             # 退款口径允许双向调整

    cvec = np.zeros(d["nvar"])
    cvec[iA:iA + m] = COEF_UP * price_rem
    cvec[iB:iB + m] = -COEF_DOWN * price_rem
    cvec[iR:iR + m] = COEF_EMG * price_rem
    cvec[iXi] = rp.lam

    res = milp(cvec,
               constraints=[LinearConstraint(d["A_eq"], b_eq, b_eq),
                            LinearConstraint(d["A_ub"], -np.inf, b_ub)],
               integrality=d["integ"], bounds=Bounds(lb, ub))
    if not res.success:
        raise RuntimeError(f"调整 MILP 求解失败：{res.message}")

    x = res.x
    a, b = x[iA:iA + m], x[iB:iB + m]
    fee = float(np.sum(COEF_UP * price_rem * a - COEF_DOWN * price_rem * b))
    return AdjustPlan(y=x[iY:iY + m], up=a, down=b, Ebar=x[iE:iE + m],
                      r_plan=x[iR:iR + m], fee=fee)


# ================================================================ 模块 7：实际执行回放
class DayRunner:
    """按交付块推进的十分钟执行器，规则与问题二 5.2 节完全一致。

    b_t = x_t + v_t - ℓ_t 为使用储能前的盈余；储备线 R_t = 1200 + ρ(Ē_t-1200)
    取**当前最新一次求解**给出的参考轨迹。分块推进的原因是新预报到达时
    参考轨迹会整体刷新，后面的时段必须用新的 R_t。
    """

    def __init__(self, l_act: np.ndarray, v_act: np.ndarray,
                 e0: float, rho: float):
        self.l, self.v = l_act, v_act
        self.rho = rho
        self.E0 = float(e0)
        self.Ep = float(e0)
        self.c = np.zeros(N)
        self.d = np.zeros(N)
        self.r = np.zeros(N)
        self.w = np.zeros(N)
        self.E = np.zeros(N)

    def run(self, a: int, b: int, x: np.ndarray, Ebar: np.ndarray) -> None:
        for t in range(a, b):
            bt = x[t] + self.v[t] - self.l[t]
            R = E_MIN + self.rho * (Ebar[t] - E_MIN)
            if bt > 0:
                self.c[t] = min(bt, M_ENERGY, (E_MAX - self.Ep) / ETA)
                self.w[t] = bt - self.c[t]
            else:
                head = max(0.0, self.Ep - R)
                self.d[t] = min(-bt, M_ENERGY, ETA * head)
                self.r[t] = max(0.0, -bt - self.d[t])
            self.Ep = self.Ep + ETA * self.c[t] - self.d[t] / ETA
            self.E[t] = self.Ep

    @property
    def E_end(self) -> float:
        return float(self.E[-1])


@dataclass
class DayRecord3:
    n: int
    date: str
    g0: np.ndarray            # 0:00 冻结的初始计划（永久保存）
    x: np.ndarray             # 最终生效的完整购电量
    c: np.ndarray
    d: np.ndarray
    r: np.ndarray
    w: np.ndarray
    E: np.ndarray
    E0: float
    Ebar: np.ndarray          # 拼接后的参考轨迹（诊断用）
    cost_plan: float          # Σ p g⁰
    cost_adj: float           # Σ A_t(x;g⁰)
    cost_emg: float           # Σ 5p r
    n_solve: int              # 当天实际执行的 MILP 求解次数
    n_submit: int             # 当天正式提交调整的交付块数
    S: tuple                  # 当天使用的预报组合（用于校验提交范围）
    l_hat0: np.ndarray
    v_hat0: np.ndarray
    n_hat0: np.ndarray
    margin0: np.ndarray
    n_risk0: np.ndarray

    @property
    def E_end(self) -> float:
        return float(self.E[-1])

    @property
    def cost_total(self) -> float:
        return self.cost_plan + self.cost_adj + self.cost_emg

    @property
    def g_initial(self) -> float:
        return float(self.g0.sum())

    @property
    def g_effective(self) -> float:
        return float(self.x.sum())

    @property
    def g_emg(self) -> float:
        return float(self.r.sum())


# ---------------------------------------------------------------- 初始计划缓存
_PLAN0_CACHE: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def initial_plan(n: int, ntilde0: np.ndarray, e0: float, price: np.ndarray,
                 rp: RiskParams) -> tuple[np.ndarray, np.ndarray]:
    """0:00 初始计划的带缓存求解。

    计划只依赖 (n, α, λ, e0) 与当天的 0:00 预报；在滚动标定的多次回放中
    (n, α, λ) 会大量重复，而 e0 由回放起点决定、在同一窗口内唯一，故缓存
    键取 (n, α, λ, e0)。ρ 只影响执行层，不进缓存键。
    """
    key = (n, rp.alpha, rp.lam, round(float(e0), 6))
    hit = _PLAN0_CACHE.get(key)
    if hit is not None:
        return hit[0].copy(), hit[1].copy()
    if len(_PLAN0_CACHE) > 40000:      # 上界保护：约 92 MB，超出则整体清空
        _PLAN0_CACHE.clear()
    plan = solve_dayahead(ntilde0, e0, price, rp)
    _PLAN0_CACHE[key] = (plan.g.copy(), plan.Ebar.copy())
    return plan.g, plan.Ebar


# ================================================================ 单日仿真
def run_day3(n: int, e0: float, S: tuple, params: RiskParams,
             use_new_forecast: bool, LOAD: np.ndarray, PV: np.ndarray,
             price: np.ndarray, fp: ForecastPanel, eps: np.ndarray,
             fo: Forecaster, convention: str = "main") -> DayRecord3:
    """回放第 n 天：0:00 定计划 → 逐块执行 → 到达发布时刻则滚动调整。"""
    l_act = LOAD[n, :] * TAU
    v_act = PV[n, :] * TAU
    date = str(np.datetime64("2025-01-01") + np.timedelta64(n, "D"))

    if n == 0:
        # 冷启动：与问题二一致，无历史可用，计划购电为零，缺口全部紧急补购
        runner = DayRunner(l_act, v_act, e0, params.rho)
        z = np.zeros(N)
        runner.run(0, N, z, np.full(N, E_INIT))
        return DayRecord3(
            n=n, date=date, g0=z.copy(), x=z.copy(), c=runner.c, d=runner.d,
            r=runner.r, w=runner.w, E=runner.E, E0=float(e0),
            Ebar=np.full(N, E_INIT), cost_plan=0.0, cost_adj=0.0,
            cost_emg=float(np.sum(COEF_EMG * price * runner.r)), n_solve=0,
            n_submit=0, S=(), l_hat0=z, v_hat0=z, n_hat0=z, margin0=z,
            n_risk0=z)

    # ---------------- 0:00：全天初始计划（永远使用 0:00 发布的预报）
    l_hat_day, _, _ = fo.energy(n)
    l_hat0 = load_forecast_at(l_hat_day, l_act, 0)
    v_hat0 = forecast_energy_slots(fp, 0, n)
    margin0 = risk_margin3(eps, 0, n, params.alpha)
    n_hat0 = l_hat0 - v_hat0
    n_risk0 = n_hat0 + margin0
    g0, Ebar = initial_plan(n, n_risk0, e0, price, params)
    x = g0.copy()

    runner = DayRunner(l_act, v_act, e0, params.rho)
    n_solve, n_submit = 1, 0

    # ---------------- 六个小时一个交付块
    for hi, (a, b) in enumerate(BLOCK_BOUNDS):
        if hi > 0 and RELEASE_HOURS[hi] in S:
            # 使用最新风险净负荷重新求解；对照策略只换状态、不换预报版本
            efor = hi if use_new_forecast else 0
            l_hat_h = load_forecast_at(l_hat_day, l_act, hi)
            v_hat_h = forecast_energy_slots(fp, efor, n)
            margin_h = risk_margin3(eps, efor, n, params.alpha)
            n_risk_h = (l_hat_h - v_hat_h) + margin_h
            res = solve_adjust(n_risk_h[a:], g0[a:], runner.Ep, price[a:],
                               params, convention)
            x[a:b] = res.y[:b - a]          # 只正式提交当前交付块
            Ebar[a:] = res.Ebar             # 参考轨迹整体刷新（含展望部分）
            n_solve += 1
            n_submit += 1
        runner.run(a, b, x, Ebar)

    cost_plan = float(np.sum(price * g0))
    if convention == "main":
        cost_adj = float(np.sum(COEF_UP * price * np.maximum(x - g0, 0.0)))
    else:
        cost_adj = float(np.sum(COEF_UP * price * np.maximum(x - g0, 0.0)
                                - COEF_DOWN * price * np.maximum(g0 - x, 0.0)))
    cost_emg = float(np.sum(COEF_EMG * price * runner.r))

    return DayRecord3(
        n=n, date=date, g0=g0, x=x, c=runner.c, d=runner.d, r=runner.r,
        w=runner.w, E=runner.E, E0=float(e0), Ebar=Ebar, cost_plan=cost_plan,
        cost_adj=cost_adj, cost_emg=cost_emg, n_solve=n_solve,
        n_submit=n_submit, S=tuple(S), l_hat0=l_hat0, v_hat0=v_hat0,
        n_hat0=n_hat0, margin0=margin0, n_risk0=n_risk0)


# ================================================================ 整段回放
_SIM: dict = {}


def setup(LOAD, PV, price, fp, fo) -> None:
    _SIM.update(LOAD=LOAD, PV=PV, price=price, fp=fp, fo=fo,
                eps=build_eps3(LOAD, PV, fp, fo))


def replay3(n0: int, n1: int, e0: float, S: tuple, params: RiskParams,
            use_new_forecast: bool = True,
            convention: str = "main") -> tuple[list[DayRecord3], float]:
    """从 e0 出发回放 [n0, n1) 天，返回 (逐日记录, 末日储电量)。"""
    d = _SIM
    recs = []
    e = float(e0)
    for n in range(n0, n1):
        rec = run_day3(n, e, S, params, use_new_forecast, d["LOAD"], d["PV"],
                       d["price"], d["fp"], d["eps"], d["fo"], convention)
        recs.append(rec)
        e = rec.E_end
    return recs, e


def totals3(recs: list[DayRecord3]) -> dict:
    """按记录集合汇总费用与电量（框架 8.1 节要求同时报告期末储电量）。"""
    cp = sum(r.cost_plan for r in recs)
    ca = sum(r.cost_adj for r in recs)
    ce = sum(r.cost_emg for r in recs)
    gi = sum(r.g_initial for r in recs)
    ge = sum(r.g_effective for r in recs)
    gem = sum(r.g_emg for r in recs)
    return {
        "天数": len(recs),
        "初始计划量_kWh": gi,
        "最终常规量_kWh": ge,
        "紧急购电量_kWh": gem,
        "收到总电量_kWh": ge + gem,
        "计划费_元": cp,
        "调整费_元": ca,
        "紧急费_元": ce,
        "合计费用_元": cp + ca + ce,
        "弃电量_kWh": sum(float(r.w.sum()) for r in recs),
        "充电量_kWh": sum(float(r.c.sum()) for r in recs),
        "放电量_kWh": sum(float(r.d.sum()) for r in recs),
        "期初储电量_kWh": float(recs[0].E0),
        "期末储电量_kWh": float(recs[-1].E[-1]),
        "调整提交次数": sum(r.n_submit for r in recs),
        "MILP求解次数": sum(r.n_solve for r in recs),
    }


# ================================================================ 参数标定
@dataclass(frozen=True)
class CalConfig3:
    # 网格下探到 α=0.30：主计费口径下追加电量的边际成本高于问题二，
    # 最优风险余量本就偏小，若只从 0.60 起扫会把最优值压在边界上。
    alphas: tuple = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
    rhos: tuple = (0.0, 0.25, 0.5, 1.0)
    lams: tuple = (0.60,)
    window: int = 35           # 标定回放窗口天数
    every: int = 42            # 每隔多少天重新标定一次
    start: int = REPORT_START  # 首次标定发生在正式区间首日
    S: tuple = ALL_S           # 标定所用的预报组合
    # 下面两项只影响 CalConfig3.grid() 造出来的 RiskParams，供问题四复用标定
    # 网格时对齐内核口径；问题三自己的 run_day3 直接调 risk_margin3 的默认值，
    # 故这两项的默认值(28, 10)保持问题三原行为不变。
    risk_window: int = 28      # 误差分位数的回看窗口（RiskParams.window）
    min_samples: int = 10      # 误差分位数的最少样本数

    def grid(self) -> list[RiskParams]:
        return [RiskParams(alpha=a, rho=r, lam=l, window=self.risk_window,
                           min_samples=self.min_samples)
                for a in self.alphas for r in self.rhos for l in self.lams]


def calibrate3(n0: int, e_at_window_start: float,
               cal: CalConfig3, use_new_forecast: bool = True,
               convention: str = "main") -> tuple[RiskParams, list[dict]]:
    """在第 n0 天 0:00 用此前数据选择参数。

    对网格中每个组合，从窗口起点回放窗口内的历史日期，比较**实际总费用**
    （含调整费与五倍紧急费），取最小者。窗口初值取主运行在该日 0:00 的
    实际储电量，不使用第 n0 天（窗口末尾）的状态，避免引入未来信息。

    use_new_forecast 与 convention 必须由调用方传入并原样转交给 replay3：
    标定是在**该策略自己的信息集与计费口径**下进行的，否则对照策略（不看
    新预报）与退款口径敏感性会用另一套策略的参数，对照就失去意义。
    """
    lo = max(0, n0 - cal.window)
    rows, best, best_cost = [], None, np.inf
    for rp in cal.grid():
        recs, _ = replay3(lo, n0, e_at_window_start, cal.S, rp,
                          use_new_forecast, convention)
        cost = sum(r.cost_total for r in recs)
        rows.append({"标定日": _date_of(n0), "窗口起": _date_of(lo),
                     "参数": rp.label(), "窗口实际总费用_元": cost})
        if cost < best_cost - 1e-9:
            best_cost, best = cost, rp
    assert best is not None
    for row in rows:
        row["选中"] = row["参数"] == best.label()
    return best, rows


def _date_of(n: int) -> str:
    return str(np.datetime64("2025-01-01") + np.timedelta64(int(n), "D"))


def run_strategy3(cal: CalConfig3, SOFTS: tuple, e_init: float = E_INIT,
                  use_new_forecast: bool = True, convention: str = "main",
                  verbose: bool = False) -> tuple[list[DayRecord3], list[dict]]:
    """整年滚动：预热 1 月，正式区间内每隔 cal.every 天重新标定一次参数。"""
    recs, cal_rows = [], []
    e = float(e_init)
    e_at = {0: e}
    params = RiskParams()
    for n in range(N_DAY):
        if n >= cal.start and (n - cal.start) % cal.every == 0:
            params, rows = calibrate3(n, e_at[max(0, n - cal.window)], cal,
                                      use_new_forecast, convention)
            cal_rows.extend(rows)
            if verbose:
                print(f"    [{_date_of(n)}] 选中 {params.label()}", flush=True)
        rec = run_day3(n, e, SOFTS, params, use_new_forecast, _SIM["LOAD"],
                       _SIM["PV"], _SIM["price"], _SIM["fp"], _SIM["eps"],
                       _SIM["fo"], convention)
        recs.append(rec)
        e = rec.E_end
        e_at[n + 1] = e
    return recs, cal_rows


# ================================================================ 校验
def validate_day3(rec: DayRecord3, price: np.ndarray,
                  convention: str = "main", tol: float = 1e-6) -> dict:
    """逐日复核，按框架 8.2 节的七项检查分组返回问题清单。"""
    info, tm, lock, cost, power, chain, consist = [], [], [], [], [], [], []
    l = _SIM["LOAD"][rec.n, :] * TAU
    v = _SIM["PV"][rec.n, :] * TAU

    # 5. 储能与供电：逐段能量守恒、边界、互斥
    resid = rec.x + rec.r + v + rec.d - l - rec.c - rec.w
    scale = max(1.0, float(l.max()))
    if np.abs(resid).max() > tol * scale:
        power.append(f"供需平衡残差 {np.abs(resid).max():.3e} kWh")
    if min(rec.c.min(), rec.d.min(), rec.r.min(), rec.w.min()) < -tol:
        power.append("存在负的充电/放电/紧急购电/弃电")
    if rec.c.max() > M_ENERGY + tol or rec.d.max() > M_ENERGY + tol:
        power.append("充放电越限")
    if ((rec.c > tol) & (rec.d > tol)).any():
        power.append("存在同时充放电时段")
    Eseq = np.concatenate([[rec.E0], rec.E])
    if Eseq.min() < E_MIN - tol or Eseq.max() > E_MAX + tol:
        power.append(f"储电量越界 [{Eseq.min():.4f}, {Eseq.max():.4f}]")

    # 3. 计划锁定：x ≥ g⁰（主口径）且两者均为 144 维非负
    if rec.g0.shape != (N,) or rec.x.shape != (N,):
        lock.append("计划/调整数组维度非法")
    if rec.g0.min() < -tol or rec.x.min() < -tol:
        lock.append("存在负的购电量")
    if convention == "main" and (rec.x - rec.g0).min() < -tol:
        lock.append(f"主口径下出现下调 {(rec.x - rec.g0).min():.3e} kWh")

    # 4. 费用核对：按定义独立复算
    cp = float(np.sum(price * rec.g0))
    if convention == "main":
        ca = float(np.sum(COEF_UP * price * np.maximum(rec.x - rec.g0, 0.0)))
    else:
        ca = float(np.sum(COEF_UP * price * np.maximum(rec.x - rec.g0, 0.0)
                          - COEF_DOWN * price * np.maximum(rec.g0 - rec.x, 0.0)))
    ce = float(np.sum(COEF_EMG * price * rec.r))
    for name, a, b in (("计划费", cp, rec.cost_plan), ("调整费", ca, rec.cost_adj),
                       ("紧急费", ce, rec.cost_emg)):
        if abs(a - b) > tol * max(1.0, abs(a)):
            cost.append(f"{name}复算不符 {a:.6f} vs {b:.6f}")

    # 6. 状态衔接：日末电量 = 日初 + ηc·Σc - Σd/η
    lhs = rec.E[-1] - rec.E0
    rhs = ETA * rec.c.sum() - rec.d.sum() / ETA
    if abs(lhs - rhs) > tol * max(1.0, abs(rhs)):
        chain.append(f"状态累计不符：ΔE={lhs:.6f} vs {rhs:.6f}")

    # 7. 结果一致性：初始计划不被覆盖——出现差异的时段必须落在当天
    #    正式提交过的交付块内（第 0 块永远按初始计划执行），且提交次数
    #    必须与组合 S 一致。
    diff = np.abs(rec.x - rec.g0) > tol
    if rec.n != 0 and rec.n_submit != len(rec.S):
        consist.append(f"提交次数 {rec.n_submit} 与组合 {rec.S} 不符")
    allowed = np.zeros(N, bool)
    for h in rec.S:
        b = h // 6
        allowed[36 * b:36 * (b + 1)] = True
    stray = diff & ~allowed
    if stray.any():
        consist.append(f"存在 {int(stray.sum())} 段未提交却生效的调整")

    # 1. 信息可用性 / 2. 时间转换：结构由实现保证，此处校验可核对的量
    if np.isnan(rec.v_hat0[36:]).any() or np.isnan(rec.l_hat0).any():
        info.append("0:00 计划的输入含空值")
    if not np.all(np.diff(rec.E) > -1e9):
        tm.append("储电量序列异常")

    return {"信息可用性": info, "时间转换": tm, "计划锁定": lock,
            "费用核对": cost, "储能与供电": power, "状态衔接": chain,
            "结果一致性": consist}


def validation_metrics3(recs: list[DayRecord3], price: np.ndarray,
                        convention: str = "main") -> dict:
    """汇总七项校验的**数值**口径，供论文按实测值陈述。"""
    m = {"供需平衡最大残差_kWh": 0.0, "储电量越界最大量_kWh": 0.0,
         "充放电越限最大量_kWh": 0.0, "同时充放电时段数": 0,
         "状态累计最大绝对偏差_kWh": 0.0, "计划费最大复算偏差_元": 0.0,
         "调整费最大复算偏差_元": 0.0, "紧急费最大复算偏差_元": 0.0,
         "主口径最大下调量_kWh": 0.0}
    for rec in recs:
        l = _SIM["LOAD"][rec.n, :] * TAU
        v = _SIM["PV"][rec.n, :] * TAU
        resid = rec.x + rec.r + v + rec.d - l - rec.c - rec.w
        m["供需平衡最大残差_kWh"] = max(m["供需平衡最大残差_kWh"],
                                        float(np.abs(resid).max()))
        Eseq = np.concatenate([[rec.E0], rec.E])
        m["储电量越界最大量_kWh"] = max(m["储电量越界最大量_kWh"],
                                        float(max(0.0, E_MIN - Eseq.min())),
                                        float(max(0.0, Eseq.max() - E_MAX)))
        m["充放电越限最大量_kWh"] = max(m["充放电越限最大量_kWh"],
                                        float(max(0.0, rec.c.max() - M_ENERGY)),
                                        float(max(0.0, rec.d.max() - M_ENERGY)))
        m["同时充放电时段数"] += int(((rec.c > 1e-6) & (rec.d > 1e-6)).sum())
        m["状态累计最大绝对偏差_kWh"] = max(
            m["状态累计最大绝对偏差_kWh"],
            abs(float(rec.E[-1] - rec.E0 - (ETA * rec.c.sum()
                                            - rec.d.sum() / ETA))))
        cp = float(np.sum(price * rec.g0))
        ca = float(np.sum(COEF_UP * price * np.maximum(rec.x - rec.g0, 0.0)
                          - COEF_DOWN * price * np.maximum(rec.g0 - rec.x, 0.0)))
        ce = float(np.sum(COEF_EMG * price * rec.r))
        m["计划费最大复算偏差_元"] = max(m["计划费最大复算偏差_元"],
                                        abs(cp - rec.cost_plan))
        m["调整费最大复算偏差_元"] = max(m["调整费最大复算偏差_元"],
                                        abs(ca - rec.cost_adj))
        m["紧急费最大复算偏差_元"] = max(m["紧急费最大复算偏差_元"],
                                        abs(ce - rec.cost_emg))
        m["主口径最大下调量_kWh"] = max(m["主口径最大下调量_kWh"],
                                        float(max(0.0, (rec.g0 - rec.x).max())))
    return m


def check_all3(recs: list[DayRecord3], price: np.ndarray,
               convention: str = "main") -> dict[str, int]:
    """返回七项检查中各项的**失败天数**。"""
    counts = {"信息可用性": 0, "时间转换": 0, "计划锁定": 0, "费用核对": 0,
              "储能与供电": 0, "状态衔接": 0, "结果一致性": 0}
    for rec in recs:
        for k, v in validate_day3(rec, price, convention).items():
            if v:
                counts[k] += 1
    return counts


# ================================================================ 结果整理
def emergency_events3(r: np.ndarray, eps: float = EMG_EPS) -> list[dict]:
    """同日相邻的非零紧急购电合并为一个事件；跨午夜天然按日拆分。"""
    out, t = [], 0
    while t < N:
        if r[t] <= eps:
            t += 1
            continue
        a = t
        while t < N and r[t] > eps:
            t += 1
        out.append({"时段起": fmt_time(a * 10), "时段止": fmt_time(t * 10),
                    "区间标签": f"{fmt_time(a * 10)}-{fmt_time(t * 10)}",
                    "段数": t - a, "购电量_kWh": float(r[a:t].sum())})
    return out


def day_summary3(rec: DayRecord3, price: np.ndarray) -> dict:
    idx = {interval_label(i): i for i in range(N)}
    table1 = [{"时间段": lab, "计划购电量_kWh": float(rec.g0[idx[lab]]),
               "调整购电量_kWh": float(rec.x[idx[lab]]),
               "增量_kWh": float(rec.x[idx[lab]] - rec.g0[idx[lab]]),
               "紧急购电量_kWh": float(rec.r[idx[lab]])}
              for lab in WANT_LABELS]
    # 末段必须是 "20:00-24:00"。这里不能用 fmt_time：它是给十分钟区间标签用的
    # 约定，fmt_time(1440) 会返回 "0:00+1"，于是末段被写成 "20:00-0:00+1"，与
    # 题目表 2 及附件 5 模板都不一致。block_label 正是为此实现的（见问题一），
    # 问题二的 table2 也走它。
    table2 = [{"时间段": block_label(a, z),
               "充电量_kWh": float(rec.c[a:z].sum()),
               "放电量_kWh": float(rec.d[a:z].sum())}
              for a, z in FOUR_HOUR_BLOCKS]
    return {
        "date": rec.date, "table1": table1, "table2": table2,
        "events": emergency_events3(rec.r),
        "g_initial": rec.g_initial, "g_effective": rec.g_effective,
        "g_emg": rec.g_emg, "g_received": rec.g_effective + rec.g_emg,
        "cost_plan": rec.cost_plan, "cost_adj": rec.cost_adj,
        "cost_emg": rec.cost_emg, "cost_total": rec.cost_total,
        "charge_kwh": float(rec.c.sum()), "dischg_kwh": float(rec.d.sum()),
        "dump_kwh": float(rec.w.sum()), "E0": rec.E0, "E144": float(rec.E[-1]),
        "E_min": float(np.concatenate([[rec.E0], rec.E]).min()),
        "E_max": float(np.concatenate([[rec.E0], rec.E]).max()),
        "n_submit": rec.n_submit, "n_solve": rec.n_solve,
        "emg_segments": int((rec.r > EMG_EPS).sum()),
        "emg_events": len(emergency_events3(rec.r)),
        "load_kwh": float((_SIM["LOAD"][rec.n] * TAU).sum()),
        "pv_kwh": float((_SIM["PV"][rec.n] * TAU).sum()),
    }


def detail_frame3(rec: DayRecord3, price: np.ndarray) -> pd.DataFrame:
    E_prev = np.concatenate([[rec.E0], rec.E[:-1]])
    return pd.DataFrame({
        "日期": rec.date,
        "时段起": [fmt_time(i * 10) for i in range(N)],
        "时段止": [fmt_time((i + 1) * 10) for i in range(N)],
        "电价_元每kWh": price,
        "预测负载_kWh": rec.l_hat0,
        "预测光伏_0点版本_kWh": rec.v_hat0,
        "净负荷预测_kWh": rec.n_hat0,
        "风险余量_kWh": rec.margin0,
        "风险净负荷_kWh": rec.n_risk0,
        "参考储电量_kWh": rec.Ebar,
        "实际负载_kWh": _SIM["LOAD"][rec.n] * TAU,
        "实际光伏_kWh": _SIM["PV"][rec.n] * TAU,
        "初始计划购电_kWh": rec.g0,
        "最终购电_kWh": rec.x,
        "上调量_kWh": np.maximum(rec.x - rec.g0, 0.0),
        "下调量_kWh": np.maximum(rec.g0 - rec.x, 0.0),
        "实际充电_kWh": rec.c,
        "实际放电_kWh": rec.d,
        "紧急购电_kWh": rec.r,
        "弃电_kWh": rec.w,
        "期初储电量_kWh": E_prev,
        "期末储电量_kWh": rec.E,
        "计划费_元": price * rec.g0,
        "调整费_元": COEF_UP * price * np.maximum(rec.x - rec.g0, 0.0)
                     - COEF_DOWN * price * np.maximum(rec.g0 - rec.x, 0.0),
        "紧急费_元": COEF_EMG * price * rec.r,
    })


def write_result3(summaries: list[dict], recs: list[DayRecord3] | None,
                  dates: list[str], path: Path) -> None:
    """按附件 5 的 result3.xlsx 模板写出四张表。

    模板前两张表的时间标签整体错位一格（首列 '0:10-0:20'、末列 '0:00-0:10+1'），
    这里按正文口径统一改写为 '0:00-0:10' … '23:50-0:00+1'，行序与模板一一对应，
    数值不会错位（与问题二 result2.xlsx 的处理一致）。
    「计划购电量」写 0:00 冻结的 g⁰ 与初始计划费；「调整购电量」写最终生效的 x
    与**已包含初始计划费**的完整实际总费用——两表费用不能再次相加。
    """
    import openpyxl
    import shutil

    # 模板必须先落到输出路径。此前漏了这一步，导致整轮比较在最后一步崩在
    # FileNotFoundError 上，把四十多分钟的求解结果全部丢掉。
    if not path.exists():
        if not TEMPLATE3.exists():
            raise FileNotFoundError(f"缺少 result3.xlsx 模板：{TEMPLATE3}")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE3, path)

    wb = openpyxl.load_workbook(path)

    def fill_slot_sheet(name: str, series_key: str, total_key: str,
                        fee_key: str) -> None:
        ws = wb[name]
        ws.cell(row=1, column=1, value="日期\\时间")
        for i in range(N):
            ws.cell(row=1, column=2 + i, value=interval_label(i))
        ws.cell(row=1, column=2 + N, value="全天购电量")
        ws.cell(row=1, column=3 + N, value="全天购电费")
        for k, s in enumerate(summaries):
            r = 2 + k
            ws.cell(row=r, column=1, value=dates[REPORT_START + k])
            for i in range(N):
                ws.cell(row=r, column=2 + i,
                        value=round(float(s[series_key][i]), 6))
            ws.cell(row=r, column=2 + N, value=round(s[total_key], 6))
            ws.cell(row=r, column=3 + N, value=round(s[fee_key], 6))

    if recs is not None:
        for k, rec in enumerate(recs):
            summaries[k]["list_g0"] = rec.g0
            summaries[k]["list_x"] = rec.x
    else:
        # 只读缓存重建时，逐段数组由 p3_detail.csv 提供，已挂在 summaries 上
        for k, s in enumerate(summaries):
            for key in ("list_g0", "list_x"):
                if key not in s:
                    raise KeyError(f"第 {k} 天的汇总缺少 {key}，"
                                   "无法重建 result3.xlsx")
    fill_slot_sheet("计划购电量", "list_g0", "g_initial", "cost_plan")
    fill_slot_sheet("调整购电量", "list_x", "g_effective", "cost_total")

    # ---- 充放电量：每天六段，全区间展开
    ws2 = wb["充放电量"]
    for row in range(ws2.max_row, 1, -1):
        ws2.delete_rows(row)
    ws2.cell(row=1, column=1, value="日期")
    ws2.cell(row=1, column=2, value="时间段")
    ws2.cell(row=1, column=3, value="充电量")
    ws2.cell(row=1, column=4, value="放电量")
    ws2.cell(row=1, column=5, value="时刻")
    ws2.cell(row=1, column=6, value="储电量")
    r = 2
    for k, s in enumerate(summaries):
        a0 = r
        for blk in s["table2"]:
            ws2.cell(row=r, column=2, value=blk["时间段"])
            ws2.cell(row=r, column=3, value=round(blk["充电量_kWh"], 6))
            ws2.cell(row=r, column=4, value=round(blk["放电量_kWh"], 6))
            r += 1
        ws2.cell(row=a0, column=1, value=dates[REPORT_START + k])
        ws2.cell(row=a0, column=5, value="0:00")
        ws2.cell(row=a0, column=6, value=round(s["E0"], 6))
        ws2.cell(row=a0 + 5, column=5, value="24:00")
        ws2.cell(row=a0 + 5, column=6, value=round(s["E144"], 6))

    # ---- 紧急购电量：按实际事件展开
    ws3 = wb["紧急购电量"]
    for row in range(ws3.max_row, 1, -1):
        ws3.delete_rows(row)
    ws3.cell(row=1, column=1, value="日期")
    ws3.cell(row=1, column=2, value="购电时间段")
    ws3.cell(row=1, column=3, value="购电量")
    r, n_ev = 2, 0
    for k, s in enumerate(summaries):
        for j, e in enumerate(s["events"]):
            ws3.cell(row=r, column=1,
                     value=dates[REPORT_START + k] if j == 0 else None)
            ws3.cell(row=r, column=2, value=e["区间标签"])
            ws3.cell(row=r, column=3, value=round(e["购电量_kWh"], 6))
            r += 1
            n_ev += 1

    # ---- 全天汇总（新增表，不改变原模板）
    if "全天汇总" in wb.sheetnames:
        del wb["全天汇总"]
    ws4 = wb.create_sheet("全天汇总")
    hdr = ["日期", "初始计划量_kWh", "最终常规量_kWh", "紧急购电量_kWh",
           "收到总电量_kWh", "计划费_元", "调整费_元", "紧急费_元",
           "合计费用_元", "弃电量_kWh", "0:00储电量_kWh", "24:00储电量_kWh",
           "调整提交次数"]
    for j, h in enumerate(hdr, start=1):
        ws4.cell(row=1, column=j, value=h)
    for k, s in enumerate(summaries):
        vals = [dates[REPORT_START + k], s["g_initial"], s["g_effective"],
                s["g_emg"], s["g_received"], s["cost_plan"], s["cost_adj"],
                s["cost_emg"], s["cost_total"], s["dump_kwh"], s["E0"],
                s["E144"], s["n_submit"]]
        for j, val in enumerate(vals, start=1):
            ws4.cell(row=2 + k, column=j,
                     value=round(val, 6) if isinstance(val, float) else val)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print(f"  计划购电量 / 调整购电量：{len(summaries)} 天 × {N} 段")
    print(f"  充放电量  ：{len(summaries) * 6} 行")
    print(f"  紧急购电量：{n_ev} 个事件行")


# ================================================================ 主流程
def combo_name(S: tuple) -> str:
    return "∅" if not S else "{" + ",".join(str(h) for h in S) + "}"


def all_combos() -> list[tuple]:
    out = []
    for k in range(4):
        out.extend(combinations(ALL_S, k))
    return out


MAIN_TAG = "{6,12,18}"
CTRL_TAG = "对照：沿用0:00预报版本"
REFUND_TAG = "敏感性：退款口径"


def load_caches() -> dict[str, dict]:
    """读回 p3_cache/ 下每个策略的汇总结果（--report-only 用）。"""
    if not CACHE_DIR.exists():
        raise FileNotFoundError(
            f"没有缓存目录 {CACHE_DIR}，请先运行一次完整求解")
    out = {}
    for p in sorted(CACHE_DIR.glob("*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        out[c["tag"]] = c
    return out


CORE = "hybrid"          # 历史外推内核；由 main() 的 --core 设定


def _forecaster_for(core: str, LOAD: np.ndarray, PV: np.ndarray) -> Forecaster:
    """按 --core 构造负荷/光伏历史外推预测器。

    "jia" 与问题二主运行 p2_microgrid.py --core=jia 使用同一套预测器参数，
    这样问题三里的「历史外推」对照与问题二报告的结果才是同一件事。
    """
    if core == "jia":
        from p2_microgrid import JIA_LOAD_FORECAST, JIA_PV_FORECAST
        return Forecaster(LOAD, PV, JIA_LOAD_FORECAST, JIA_PV_FORECAST)
    return Forecaster(LOAD, PV)


def main_arrays_from_detail() -> tuple[np.ndarray, np.ndarray]:
    """从 p3_detail.csv 还原主策略逐日逐段的 g⁰ 与 x（供重建 l3 表用）。

    detail_frame3 按"日期、时段起"排序输出，reshape 前必须再排一次序，
    否则跨日回放中偶发的乱序会让整张表错行。
    """
    if not OUT_DETAIL3.exists():
        raise FileNotFoundError(f"缺少 {OUT_DETAIL3}，无法重建 result3.xlsx")
    det = pd.read_csv(OUT_DETAIL3, encoding="utf-8-sig")
    det = det.sort_values(["日期", "时段起"], kind="stable")
    g0 = det["初始计划购电_kWh"].to_numpy(float).reshape(-1, N)
    xs = det["最终购电_kWh"].to_numpy(float).reshape(-1, N)
    return g0, xs


def run_task(task: dict) -> dict:
    """一个完整策略：载入数据 → 滚动标定 → 全年回放 → 汇总。

    每个进程各自持有一份数据副本与独立的计划缓存；主策略额外回传逐日记录，
    供写出 result3.xlsx 与明细文件使用。
    """
    from p1_microgrid import load_attach1
    price = load_attach1()["电价"].to_numpy(float)
    LOAD, PV, dates = load_attach2()
    fp = load_attach3()
    fo = _forecaster_for(task.get("core", "hybrid"), LOAD, PV)
    _SIM.clear()
    _PLAN0_CACHE.clear()
    setup(LOAD, PV, price, fp, fo)

    # 标定必须用**该策略自己**的组合回放，否则参数是按另一套信息集选的
    cal = CalConfig3(S=task["S"], **task["cal"])
    recs, cal_rows = run_strategy3(cal, task["S"], E_INIT,
                                   task["use_new"], task["convention"])
    rep = [r for r in recs if REPORT_START <= r.n < REPORT_END]
    t = totals3(rep)
    out = {"tag": task["tag"], "S": task["S"], "total": t,
           "cal_rows": cal_rows, "records": rep if task["keep"] else None}
    if task["convention"] == "main":
        out["failures"] = check_all3(rep, price)
        out["vmetrics"] = validation_metrics3(rep, price)

    # 汇总结果立刻落盘：后续的报告阶段只读这些文件，出任何错都不必重算
    # 四十多分钟的滚动标定。records 体积很大，单独走 p3_detail.csv。
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = {
        "tag": task["tag"], "S": list(task["S"]), "core": CORE,
        "use_new": task["use_new"], "convention": task["convention"],
        "total": t, "cal_rows": cal_rows,
        "failures": out.get("failures"), "vmetrics": out.get("vmetrics"),
        "combo_row": combo_row(task["tag"], t, task["S"]),
        # 逐日汇总只对主策略留档（论文的指定日期表由它生成），其余策略
        # 的体积不值得占用磁盘
        "summaries": ([day_summary3(r, price) for r in rep]
                      if task["keep"] else None),
    }
    tmp = CACHE_DIR / f"{_safe_tag(task['tag'])}.json.tmp"
    tmp.write_text(json.dumps(cache, ensure_ascii=False, default=float),
                   encoding="utf-8")
    tmp.replace(CACHE_DIR / f"{_safe_tag(task['tag'])}.json")
    return out


def _safe_tag(tag: str) -> str:
    """把 \"{6,12}\" 这类标签变成安全的文件名。"""
    return (tag.replace("{", "").replace("}", "").replace(",", "_")
            .replace(":", "").replace(" ", "") or "empty")


def combo_row(tag: str, t: dict, S: tuple) -> dict:
    """组合比较表的一行：标签、使用到的发布时刻、以及全部汇总指标。"""
    return {"组合": tag, "使用预报": ",".join(str(h) for h in (0,) + tuple(S)),
            **t}


def main() -> None:
    ap = argparse.ArgumentParser(description="2026 CUMCM C题 问题三 求解")
    ap.add_argument("--quick", action="store_true", help="只跑主策略，不写交付文件")
    ap.add_argument("--no-cal", action="store_true", help="跳过标定，用默认参数")
    ap.add_argument("--jobs", type=int, default=1, help="组合比较的并行进程数")
    ap.add_argument("--report-only", action="store_true",
                    help="不求解，直接读 06_支撑材料/p3_cache/ 重建全部交付文件")
    ap.add_argument("--core", choices=("hybrid", "jia"), default="hybrid",
                    help="负荷/光伏历史外推内核；须与问题二主运行 "
                         "p2_microgrid.py 的选择保持一致，否则两者不可比")
    args = ap.parse_args()
    global CORE
    CORE = args.core

    t_start = time.time()
    from p1_microgrid import load_attach1
    price = load_attach1()["电价"].to_numpy(float)
    LOAD, PV, dates = load_attach2()
    fp = load_attach3()
    fo = _forecaster_for(CORE, LOAD, PV)
    setup(LOAD, PV, price, fp, fo)
    eps = _SIM["eps"]

    print("=" * 78)
    print(f"附件 3 载入：{fp.long.shape[0]} 条预报 "
          f"= {N_DAY} 天 × {N_RELEASE} 次发布")
    print(f"  锚点约定示例：2025-03-20 6:00 版本首端取自 "
          f"{fp.anchor_source[1, 78]}")
    print(f"  预报功率 {fp.F[:, :, 1:].min():.2f} ~ {fp.F[:, :, 1:].max():.2f} kW；"
          f"残差表可用天数 {int(np.sum(~np.isnan(eps[0]).all(axis=1)))}")

    # ---- 预报精度：各发布版本在正式区间内的净负荷预测误差
    prec = forecast_skill(LOAD, PV, fp, fo)
    print("\n各发布版本的净负荷预测精度（正式区间 "
          f"{dates[REPORT_START]} 至 {dates[REPORT_END-1]}，"
          "仅统计发布时刻之后的时段）：")
    print(f"  {'版本':>6s}  {'逐时段绝对偏差之和':>18s}  {'全天电量偏差':>14s}  "
          f"{'符号偏差':>12s}  {'相对日净负荷':>12s}")
    for hr in RELEASE_HOURS:
        v = prec[hr]
        print(f"  {hr:4d}:00  {v['逐时段绝对偏差之和_kWh每日']:18,.1f}  "
              f"{v['全天电量偏差_kWh每日']:14,.1f}  "
              f"{v['符号偏差_kWh每日']:+12,.1f}  "
              f"{v['相对日净负荷']*100:11.2f}%")
    print(f"  对照：若改用问题二的历史外推光伏预测，全天电量偏差 "
          f"{prec['对照_历史外推']['全天电量偏差_kWh每日']:,.1f} kWh/日")

    if args.report_only:
        caches = load_caches()
        print(f"\n--report-only：从 {CACHE_DIR.name}/ 读到 {len(caches)} 个策略")
        for c in caches.values():
            print(f"    {c['tag']:>22s}  {c['total']['合计费用_元']:,.0f} 元")
        by_tag = caches
        report = None
    else:
        cal_kwargs = {} if not args.no_cal else {
            "alphas": (None,), "rhos": (1.0,), "lams": (0.60,)}
        tasks = [{"tag": combo_name(S), "S": S, "use_new": True,
                  "convention": "main", "cal": cal_kwargs,
                  "core": CORE,
                  "keep": combo_name(S) == MAIN_TAG}
                 for S in all_combos()]
        tasks.append({"tag": CTRL_TAG, "S": tuple(ALL_S), "use_new": False,
                      "convention": "main", "cal": cal_kwargs, "core": CORE,
                      "keep": False})
        tasks.append({"tag": REFUND_TAG, "S": tuple(ALL_S), "use_new": True,
                      "convention": "refund", "cal": cal_kwargs, "core": CORE,
                      "keep": False})
        if args.quick:
            tasks = [t for t in tasks if t["tag"] == MAIN_TAG]

        print(f"\n开始比较 {len(tasks)} 个策略（并行进程数 {args.jobs}）：",
              flush=True)
        t0 = time.time()
        if args.jobs > 1:
            from concurrent.futures import ProcessPoolExecutor, as_completed
            # 每个策略含 8 次滚动标定（每次 24 组参数 × 35 天回放），单个
            # 策略就要跑十几分钟；用 as_completed 逐个汇报才能判断进度。
            done = {}
            with ProcessPoolExecutor(max_workers=args.jobs) as ex:
                futs = {ex.submit(run_task, t): t for t in tasks}
                for fu in as_completed(futs):
                    r = fu.result()
                    done[r["tag"]] = r
                    print(f"    [{time.time()-t0:6.0f}s] {r['tag']} 完成"
                          f"（合计费用 {r['total']['合计费用_元']:,.0f} 元）",
                          flush=True)
            results = [done[t["tag"]] for t in tasks]
        else:
            results = []
            for task in tasks:
                if task["tag"] != MAIN_TAG:
                    _SIM.clear()
                    _PLAN0_CACHE.clear()
                    setup(LOAD, PV, price, fp, fo)
                results.append(run_task(task))
                print(f"    {task['tag']} 完成（累计 {time.time()-t0:.0f}s）",
                      flush=True)

        by_tag = {r["tag"]: r for r in results}
        report = by_tag[MAIN_TAG]["records"]

    main_res = by_tag[MAIN_TAG]
    main_tot = main_res["total"]
    failures, vmetrics = main_res["failures"], main_res["vmetrics"]
    cal_rows = main_res["cal_rows"]

    print(f"\n主策略 {MAIN_TAG}（使用全部发布时刻）：")
    for k, v in main_tot.items():
        print(f"    {k}: {v:,.2f}" if isinstance(v, float) else f"    {k}: {v}")
    print("\n逐日校验（各检查项的失败天数与实测最坏值）：")
    for k, v in failures.items():
        print(f"    {k}: {v} 天")
    for k, v in vmetrics.items():
        print(f"    {k}: {v:.3e}")

    if args.quick:
        print(f"\n--quick 模式结束，总用时 {time.time() - t_start:.0f}s")
        return

    def save(tag: str) -> float:
        """组合比较表使用的一行；缺了某个策略就报错，不用假数据顶替。"""
        if tag not in by_tag:
            raise KeyError(f"缺少策略 {tag} 的结果，无法生成完整比较表")
        return by_tag[tag]["total"]["合计费用_元"]

    base = save(combo_name(()))
    print("\n八种预报组合：")
    combo_rows = []
    for S in all_combos():
        t = by_tag[combo_name(S)]["total"]
        combo_rows.append(combo_row(combo_name(S), t, S))
        print(f"  {combo_name(S):>10s}  合计 {t['合计费用_元']/1e4:10.2f} 万元  "
              f"计划 {t['计划费_元']/1e4:10.2f}  调整 {t['调整费_元']/1e4:8.2f}  "
              f"紧急 {t['紧急费_元']/1e4:9.2f}  期末储电 "
              f"{t['期末储电量_kWh']:8.1f}")
    print("\n各发布时刻在已有组合下的边际费用改善（正值为加入后更省）：")
    for h in ALL_S:
        for S in all_combos():
            if h in S:
                continue
            d = save(combo_name(S)) - save(combo_name(tuple(sorted(S + (h,)))))
            print(f"   Δ_{h}({combo_name(S) or '∅'}) = {d/1e4:8.2f} 万元")

    ctrl = by_tag[CTRL_TAG]["total"]
    rf_tot = by_tag[REFUND_TAG]["total"]
    info_gain = ctrl["合计费用_元"] - save(MAIN_TAG)
    reopt_gain = base - ctrl["合计费用_元"]
    print(f"\n{CTRL_TAG}：合计 {ctrl['合计费用_元']/1e4:.2f} 万元")
    print(f"    重新优化收益 = {reopt_gain/1e4:.2f} 万元；"
          f"新预报信息收益 = {info_gain/1e4:.2f} 万元")
    print(f"{REFUND_TAG}：合计 {rf_tot['合计费用_元']/1e4:.2f} 万元；"
          f"调整费 {rf_tot['调整费_元']/1e4:.2f} 万元")

    # ---- 交付物
    if report is not None:
        _SIM.clear()
        _PLAN0_CACHE.clear()
        setup(LOAD, PV, price, fp, fo)
        summaries = [day_summary3(r, price) for r in report]
    else:
        summaries = main_res["summaries"]
        if summaries is None:
            raise KeyError(f"缓存 {MAIN_TAG} 中没有逐日汇总")
        g0, xs = main_arrays_from_detail()
        if len(g0) != len(summaries):
            raise ValueError(f"p3_detail.csv 有 {len(g0)} 天，"
                             f"缓存有 {len(summaries)} 天")
        for k, s in enumerate(summaries):
            s["list_g0"], s["list_x"] = g0[k].tolist(), xs[k].tolist()

    # 指定日期的三张表（论文表 1—表 3 的数据源）一并落进 JSON
    special = {s["date"]: s for s in summaries}
    special_dates = {}
    for d in SPECIAL_DATES:
        s = special[d]
        special_dates[d] = {
            "table1": s["table1"], "table2": s["table2"], "events": s["events"],
            "初始计划量_kWh": s["g_initial"], "最终常规量_kWh": s["g_effective"],
            "紧急购电量_kWh": s["g_emg"],
            "计划费_元": s["cost_plan"], "调整费_元": s["cost_adj"],
            "紧急费_元": s["cost_emg"], "合计费用_元": s["cost_total"],
            "弃电量_kWh": s["dump_kwh"], "期初储电量_kWh": s["E0"],
            "期末储电量_kWh": s["E144"], "调整提交次数": s["n_submit"],
        }
    pd.DataFrame(summaries).drop(
        columns=["table1", "table2", "events"]).to_csv(
        OUT_DAILY3, index=False, encoding="utf-8-sig")
    if report is not None:
        pd.concat([detail_frame3(r, price) for r in report],
                  ignore_index=True).to_csv(OUT_DETAIL3, index=False,
                                            encoding="utf-8-sig")
    pd.DataFrame(combo_rows).to_csv(OUT_COMBOS3, index=False,
                                    encoding="utf-8-sig")

    payload = {
        "口径": "主计费口径：J = Σp·g⁰ + Σ1.5p(x-g⁰)_+ + Σ5p·r",
        "评价区间": f"{dates[REPORT_START]} 至 {dates[REPORT_END-1]}",
        "预报精度_净负荷MAE_kWh每日": prec,
        "主策略": {"组合": MAIN_TAG, **main_tot},
        "指定日期": special_dates,
        "逐日校验失败天数": failures,
        "校验数值口径": vmetrics,
        "八种组合": combo_rows,
        "对照_沿用0点预报版本": ctrl,
        "敏感性_退款口径": rf_tot,
        "标定记录": cal_rows,
    }
    OUT_JSON3.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                    default=float), encoding="utf-8")
    # 工作簿最后写：它依赖 openpyxl，是最容易出错的一步，放在 JSON 之后
    # 可以保证即使写表失败，论文要用的全部数字也已经落盘。
    write_result3(summaries, report, dates, OUT_XLSX3)
    print(f"\n写入 {OUT_XLSX3.name} / {OUT_JSON3.name} / "
          f"{OUT_DAILY3.name} / {OUT_DETAIL3.name} / {OUT_COMBOS3.name}")
    print(f"总用时 {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
