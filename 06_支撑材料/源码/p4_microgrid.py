# -*- coding: utf-8 -*-
r"""
2026 CUMCM C 题 问题四 —— 实时波动电价下的购电策略

问题四要求在实时波动的外网电价下重新建立当天购电策略模型，并**重新计算
问题二和问题三**，分别输出 result4-2.xlsx 与 result4-3.xlsx。两个分支不是
同一套策略的两种写法，而是各自独立回放的策略：

  4-2  沿用问题二规则：0:00 定全天计划 g，日内不得修改常规购电量
  4-3  沿用问题三规则：0:00 定初始计划 g⁰，6/12/18 时可按新预报滚动调整

主线是**用决策当时能知道的信息预测价格来做决策，再用实际价格结算真实
运行结果**。这条分离是本题的核心：把问题二、三已经得到的购电量直接乘附件 4
的电价，只能得到旧策略在新价格下的账单，不能代表已经适应波动电价的新策略。

价格信息边界（框架 2.2 节）
    题目只说电价实时波动，没有说当天价格在 0:00 已经公布。基础方案因此采用
    明确假设：**未来实际价格在决策时不可见，只能用此前已观测价格预测；电量
    提前确定，费用按对应交付时段的实际电价结算。** 不额外假设 0:00 已锁定
    全天成交价。若题目补充说明价格曲线在 0:00 已全部公开，该情形应作为另一种
    信息条件**单独报告**——本文件的 "oracle" 价格模式就是这个对照，它量化
    "更准确的价格信息值多少钱"，但绝不作为主策略。

三个价格模式（框架 6.1 节的三种策略）
    forecast  决策用当时的历史与预测价，结算用实际价   ← 本文主策略
    fixed     决策用附件 1 的固定分时电价，结算用实际价 ← 原有价格判断直接
              搬到新环境会怎样的参照
    oracle    决策用当天未来实际价，结算用实际价       ← 信息增强对照
    三者都在**同一条实际价格路径**上各自独立回放，改善量
    ΔJ = J(fixed) − J(forecast) 才是有意义的。绝不能用"旧策略在固定价下的
    费用"减"新策略在实际价下的费用"再称其为优化收益（框架 6.1 节明令禁止）。

价格预测（框架 3.1 节）
    先做简单、可追踪的预测，不引入复杂网络。本实现用**同星期加权**：
        p̂⁰_{n,t} = Σ_k w_k · p_{n−7k, t}
    历史不足时退化为可取历史日的等权均值。日内按已完成时段的**对数价格
    偏差**修正后续时段：
        p̂^{(τ)}_{n,t} = p̂⁰_{n,t} · exp(β · mean_{s<τ} log(p_{n,s} / p̂⁰_{n,s}))
    滞后集合、权重与 β 由 select_forecast_params() 在**1 月预热期**（第 1--30
    天，落在正式评价区间之外）标定一次，随后整段评价区间冻结复用——参数不在
    评价区间上再调，避免样本内选型。正式区间上的 price_forecast_compare() 与
    price_beta_sweep() 只做样本外复核展示，不参与选型。

联合风险（框架 3.2 与 3.3 节）
    框架 3.2 节强调 E[PR] = E[P]E[R] + Cov(P,R)，**不能**把两个期望直接相乘，
    并且明确要求"不能在未分析数据前就认定其一定存在或一定为正"。本文件的
    risk_price_correlation() 就是这一步，实测（正式区间，48096 个时段样本）：

        corr(净负荷预测误差, 实际电价) = +0.0826            → 为正
        按电价分档（合并全部时段）：最高 20% 误差均值 +38.5 kW、P(ε>0)=0.526，
        最低 20% 为 −72.7 kW、P(ε>0)=0.412，两端差 +111.2 kW

    但合并口径会**低估**这种关系：把误差按目标时段固定住再看，逐时段相关系数
    均值达 **+0.206**（区间 0.083~0.401），明显高于合并口径的 0.083。原因是
    电价的主要变动来自"时段之间"（傍晚贵、凌晨便宜），合并口径里这一层掩盖了
    "同一天同一时段、价格偏高时负载也偏高"这一层。**协方差为正且是同时段内
    的性质**，因此风险余量必须逐时段计算，不能对全年做一次汇总——这也正是
    框架 3.4 节要求按 t 单独求分位数的原因。

    据此，风险余量取**价格加权分位数**（框架 3.3 节 F_P(z) = E[P·1{N≤z}]/E[P]
    的经验版本，框架 3.4 节），权重是同一目标时段的历史实际电价：
        Ñ = N̂ + Q^P_α(ε)
    risk_weight_effect() 给出加权与不加权的对照。效应是**方向正确、幅度温和**的：
    α=0.6 抬高 3.00 kWh（+25.6%），α=0.7 抬高 3.57 kWh（+13.8%），α=0.8 抬高
    4.31 kWh（+10.0%）——即每时段约 +3~4 kWh。之所以不算大，是因为同一时段的
    价格在日与日之间变动有限（日内同一时段的日间变异系数均值仅 0.17）；但方向上
    它把余量推向高代价时段，且实现成本极低，故保留为主口径。--unweighted 可退回
    普通分位数供对照。

    注意对照口径：加权一侧按**加权经验分布的下确界**取值（论文问题四"价格加权
    分位数"一节的公式），不加权一侧用 np.quantile 的默认线性插值约定（与问题二
    一致）。因此表中的"抬高"同时含**加权**与**取值约定**两层差别，不是纯粹的
    加权效应；两者的量级由 test_weighted_quantile() 与 risk_weight_effect() 分别
    核验。

计费（框架 5.3 节）
    全部系数乘**对应交付时段的实际电价**，不乘 0:00 的预测价：
        主口径  C = Σ_t p_t g⁰_t + 1.5 Σ_t p_t (x_t − g⁰_t)₊ + 5 Σ_t p_t r_t
        退款口径 C = Σ_t p_t g⁰_t + 1.5 Σ_t p_t (x_t − g⁰_t)₊
                       − 0.5 Σ_t p_t (g⁰_t − x_t)₊ + 5 Σ_t p_t r_t
    首项是**初始计划 g⁰**，不是最终生效量 x：1.5p_t 是上调部分的**总价**，不是
    "先付 p_t 再加 1.5p_t"成为 2.5p_t（问题三 7.3 节已就此说明）。
    主口径下 g⁰ 已全额付费，故令 x_t ≥ g⁰_t、下调恒为零，第二式退化为 0；
    退款口径作为独立敏感性由 --refund 运行，不与主口径混合。
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from p1_microgrid import (  # noqa: E402
    N, TAU, E_MIN, E_MAX, E_INIT, M_ENERGY, ETA, interval_label, block_label,
    BLOCKS, load_attach1,
)
from p2_microgrid import (  # noqa: E402
    ROOT, N_DAY, REPORT_START, REPORT_END, EMG_EPS,
    Forecaster, RiskParams, load_attach2, solve_dayahead, execute_day,
    build_error_table, LOAD_FORECAST, PV_FORECAST, CalConfig, LAMBDA_DEFAULT,
    ForecastParams, JIA_LOAD_FORECAST, JIA_PV_FORECAST, JIA_ALPHAS, JIA_RHOS,
    JIA_LAMS, JIA_MIN_SAMPLES,
)
from p3_rolling_microgrid import (  # noqa: E402
    ForecastPanel, load_attach3, forecast_energy_slots, load_forecast_at,
    build_eps3, solve_adjust, DayRunner, CalConfig3, ALL_S,
    RELEASE_HOURS, BLOCK_BOUNDS, COEF_UP, COEF_DOWN, COEF_EMG,
)

# ================================================================ 路径与常量
ATTACH4 = ROOT / "01_题目" / "C题" / "附件" / "附件4.xlsx"
TEMPLATE42 = ROOT / "01_题目" / "C题" / "附件" / "附件5" / "result4-2.xlsx"
TEMPLATE43 = ROOT / "01_题目" / "C题" / "附件" / "附件5" / "result4-3.xlsx"
OUT_DIR = ROOT / "06_支撑材料"
OUT_XLSX42 = OUT_DIR / "result4-2.xlsx"
OUT_XLSX43 = OUT_DIR / "result4-3.xlsx"
OUT_JSON4 = OUT_DIR / "p4_results.json"
OUT_DETAIL42 = OUT_DIR / "p4_detail_42.csv"
OUT_DETAIL43 = OUT_DIR / "p4_detail_43.csv"
OUT_DAILY42 = OUT_DIR / "p4_daily_42.csv"
OUT_DAILY43 = OUT_DIR / "p4_daily_43.csv"
OUT_COMBOS4 = OUT_DIR / "p4_combinations.csv"
OUT_STRAT4 = OUT_DIR / "p4_strategies.csv"
OUT_PFCAND = OUT_DIR / "p4_price_forecast_candidates.csv"
OUT_PBETA = OUT_DIR / "p4_price_beta.csv"
OUT_RWEIGHT = OUT_DIR / "p4_risk_weight.csv"
CACHE_DIR = OUT_DIR / "p4_cache"

CONVENTIONS = ("main", "refund")
PRICE_MODES = ("forecast", "fixed", "oracle")

MODE_LABEL = {
    "forecast": "波动电价预测策略",
    "fixed": "固定电价参考策略",
    "oracle": "未来价格已知参考",
}


# ================================================================ 问题二内核
# 4-2 / 4-3 的骨架就是问题二那一套（预测 → 风险余量 → 日前 LP → 因果执行 + 滚动
# 标定），差别只在价格与调整时点。所以问题二换内核时，两问必须一起重算：否则
# 三问的参数选择逻辑不一致，跨问对照（4-2 与 4-3 的 ΔJ）就失去意义。
#
#   legacy —— 本仓旧行为，仅用于复现历史数字（4-2 = 14,763,159.83 元）：
#             预测器取模块默认、预热期参数硬编码、第 0 天冷启动、min_samples=10。
#   jia    —— 对照实现 origin/q2-jia 最终版的配方，也是当前默认：
#             * 预测器写死 负荷近 28 天/0.30、光伏近 7 天/0.30；
#             * 预热期参数不再硬编码，改在 5×6×6 = 180 组 (α,ρ,λ) 上按 1 月
#               总费用联合选出；
#             * λ 在 1 月选定后**整年冻结**，正式区间只在 (α,ρ) 的 30 组上重选；
#             * min_samples=8。
# 各问的 1 月联合标定都用**各自的**日回放与计费口径进行，所以 α/ρ/λ 会按本问的
# 代价结构自然取到不同的值——移植的是配方，不是他那一组数字。
#
# **不移植的一项是他第 0 天走日 LP 的口径。** 那一项在问题二里能让计划层照常
# 求解，是因为电价是题面给定的固定曲线，第 0 天也有价可用；问题四的电价要靠
# 历史外推（附件 1 那条曲线只是"固定电价参考策略"，不是预测），第 0 天既无价格
# 历史也无负载/光伏历史，日前 LP 拿不到任何可用的决策价格。因此 4-2 / 4-3 的
# 第 0 天一律按冷启动作业（计划量为零、储能待机、缺口 5 倍补购），三种价格模式
# 用同一口径，ΔJ 才只反映评价区间内的价格信息之差。


@dataclass(frozen=True)
class CorePreset:
    """问题二内核的配置包：预测器与风险参数网格。

    不含第 0 天口径——见上方说明，问题四第 0 天一律冷启动。
    """

    name: str
    load_fp: ForecastParams
    pv_fp: ForecastParams
    risk_window: int
    min_samples: int
    warmup_alphas: tuple
    warmup_rhos: tuple
    warmup_lams: tuple
    warmup_n_days: int = REPORT_START

    def warmup_grid(self) -> list[RiskParams]:
        """1 月联合标定的 (α,ρ,λ) 网格。"""
        return [RiskParams(alpha=a, rho=r, lam=l, window=self.risk_window,
                           min_samples=self.min_samples)
                for a in self.warmup_alphas for r in self.warmup_rhos
                for l in self.warmup_lams]


CORE_LEGACY = CorePreset(
    name="legacy", load_fp=LOAD_FORECAST, pv_fp=PV_FORECAST, risk_window=28,
    min_samples=10, warmup_alphas=(), warmup_rhos=(), warmup_lams=())

CORE_JIA = CorePreset(
    name="jia", load_fp=JIA_LOAD_FORECAST, pv_fp=JIA_PV_FORECAST,
    risk_window=28, min_samples=JIA_MIN_SAMPLES,
    warmup_alphas=JIA_ALPHAS, warmup_rhos=JIA_RHOS, warmup_lams=JIA_LAMS)

CORES = {c.name: c for c in (CORE_LEGACY, CORE_JIA)}


# ================================================================ 模块 1：数据对齐
def load_attach4() -> np.ndarray:
    """读取附件 4 的全年实际电价，返回 (365, 144) 的元/kWh 数组。

    附件 4 的版式与附件 2 一致：首列为日期，其后 144 列是 "0:10" … "23:50"
    与末尾的 "0:00+1"。按前文统一的右端点命名口径，第 j 列（0 起）对应区间
    [10j, 10(j+1)) 分钟，与附件 1、2 的第 j 行逐段对齐——论文 3.1 节已就该
    时间口径作过说明，此处沿用同一假设。

    同时做框架 8.1 节要求的数据核对：无空值、无非数值、电价全部为正、
    日期序列与 2025-01-01 起的连续日期一致。
    """
    raw = pd.read_excel(ATTACH4, header=0)
    if raw.shape[0] != N_DAY:
        raise ValueError(f"附件 4 应有 {N_DAY} 天，实际 {raw.shape[0]} 天")
    if raw.shape[1] != N + 1:
        raise ValueError(f"附件 4 应有 {N + 1} 列，实际 {raw.shape[1]} 列")
    last = str(raw.columns[-1]).strip()
    if last not in ("0:00+1", "0:00:00+1", "24:00"):
        raise ValueError(f"附件 4 末列标签异常：{last!r}，预期 0:00+1")

    price = raw.iloc[:, 1:].to_numpy(dtype=float)
    if price.shape != (N_DAY, N):
        raise ValueError(f"附件 4 数据区形状异常：{price.shape}")
    if np.isnan(price).any():
        raise ValueError("附件 4 存在空值或非数值")
    if (price <= 0).any():
        raise ValueError(f"附件 4 出现非正电价，最小 {price.min():.4f}")

    dates = pd.to_datetime(raw.iloc[:, 0])
    expect = pd.date_range("2025-01-01", periods=N_DAY, freq="D")
    if not (dates.values == expect.values).all():
        raise ValueError("附件 4 日期序列与 2025-01-01 起的连续日期不一致")
    return price


def shape_ratio(PRICE: np.ndarray) -> float:
    """单一固定日内形状能解释的总方差比例，衡量价格的可预测性。"""
    shape = PRICE.mean(axis=0)
    return float(1.0 - (PRICE - shape).var() / PRICE.var())


def price_summary(PRICE: np.ndarray) -> dict:
    """附件 4 的价格统计，供论文说明"实时波动"到底有多大。"""
    return {
        "最小_元每kWh": float(PRICE.min()),
        "最大_元每kWh": float(PRICE.max()),
        "均值_元每kWh": float(PRICE.mean()),
        "标准差_元每kWh": float(PRICE.std()),
        "日中位峰谷比": float(np.median(PRICE.max(axis=1) / PRICE.min(axis=1))),
        "日内形状解释方差比": shape_ratio(PRICE),
        "日间水平离散度": float(PRICE.mean(axis=1).std() / PRICE.mean()),
    }


# ================================================================ 模块 2：价格预测
@dataclass(frozen=True)
class PriceForecastParams:
    """框架 3.1 节的简单可追踪价格预测参数。

    这个预测器不是试出来的，而是从一个可验证的价格结构直接推出来的。把附件 4
    记为 P、附件 1 的固定曲线记为 F、残差 R = P − F，实测（见 verify_price_
    structure()，四个断言都被逐年数据证实）：

      断言 1  附件 4 的 365 天逐段均值 == 附件 1 的曲线（最大偏差 5.2e-05）。
              即波动电价与固定电价**年平均值相同**，日内的 144 段骨架也相同。
      断言 2  R 与 F 正交（相关 −0.0000），故 R 就是"波动"本身。
      断言 3  R 有明显的**星期结构**，且是两水平的：周五、周六 −0.1368 元/kWh，
              其余五天 +0.0545 元/kWh，相差 0.1913 元/kWh，相当于均价（0.766）
              的 25.0%。周五周六便宜符合用电侧需求走低的常识。
      断言 4  这个星期结构解释了 R 总方差的 41.7%。

    于是正确的预测式不是"对近期价格做平滑"，而是**把骨架和星期偏移分开**：

        p̂⁰_{n,t} = F_t + Σ_k w_k · R_{n−7k, t}

    断言 2 保证这一步是恒等式，实测偏差 4.4e-16。也就是说：同星期加权 ==
    附件 1 曲线 + 同星期残差的加权平均。滞后取 7/14/21 天（三个同星期样本），
    权重偏向最近一期——因为星期偏移本身是缓慢漂移的，越近的样本越可信。这也
    解释了为什么"近 N 天滚动均值"（0.0827~0.0867）反而比不动脑筋用固定曲线
    （0.0961）只好一点点：把不同星期几混在一起平均，恰恰把这个 0.19 元/kWh
    的偏移平均掉了。候选对比见 price_forecast_compare()。

    日内再用对数偏差修正（β，见 price_beta_sweep()）：当天已完成时段的实际
    价格高于预测，说明当天整体水平偏高，按比例外推到剩余时段。

    这里的 lags/weights/beta 只是**候选模板的默认值**；正式计算用的是
    select_forecast_params() 在 1 月预热期选出的冻结参数。
    """
    lags: tuple = (7, 14, 21)
    weights: tuple = (0.6, 0.3, 0.1)
    beta: float = 0.5
    name: str = "同星期加权"
    # (β@6:00, β@12:00, β@18:00)。None 表示三个时点一律取 beta。允许逐时点取值
    # 是因为各时点可用于估计偏差的已完成时段数不同（6:00 只有 36 段、18:00 有
    # 108 段），最优收缩系数本就未必相同。
    beta_by_hour: tuple | None = None

    def beta_at(self, hi: int) -> float:
        """第 hi 个发布时刻的 β；hi = 0/1/2/3 对应 0:00/6:00/12:00/18:00。"""
        if self.beta_by_hour is None or not 1 <= hi <= len(self.beta_by_hour):
            return self.beta
        return float(self.beta_by_hour[hi - 1])

    def label(self) -> str:
        w = "/".join(f"{x:g}" for x in self.weights)
        if self.beta_by_hour is None:
            b = f"β={self.beta:g}"
        else:
            b = "β=" + "/".join(f"{x:g}" for x in self.beta_by_hour)
        return (f"{self.name}(滞后{','.join(map(str, self.lags))};"
                f"权重{w};{b})")


PRICE_FORECAST = PriceForecastParams()


class PriceForecaster:
    """因果价格预测器：只用第 n 天之前已完整观测的历史价格。"""

    def __init__(self, PRICE: np.ndarray,
                 pp: PriceForecastParams = PRICE_FORECAST):
        self.PRICE, self.pp = PRICE, pp
        self._f0 = [self._compute0(n) for n in range(N_DAY)]

    def _compute0(self, n: int) -> np.ndarray | None:
        """同星期加权；不足一个滞后时退化为已有历史的等权均值。

        第 0 天没有任何已观测价格，返回 None —— 该日按冷启动处理（计划量为
        零、缺口全部紧急补购），与问题二、三的预热日约定一致；它也不在
        2025-02-01 起的正式评价区间内。
        """
        if n == 0:
            return None
        idx, w = [], []
        for lag, wt in zip(self.pp.lags, self.pp.weights):
            if n - lag >= 0:
                idx.append(n - lag)
                w.append(wt)
        if not idx:
            return self.PRICE[:n].mean(axis=0)
        w = np.asarray(w, dtype=float)
        w = w / w.sum()
        return (self.PRICE[idx] * w[:, None]).sum(axis=0)

    def forecast0(self, n: int) -> np.ndarray:
        f = self._f0[n]
        if f is None:
            raise ValueError(f"第 {n} 天无历史价格，不能给出 0:00 预测")
        return f.copy()

    def forecast_at(self, n: int, hi: int) -> np.ndarray:
        """第 hi 个发布时刻的价格预测（框架 3.1 式的对数偏差修正）。

        hi = 0 直接返回 0:00 预测；hi > 0 时只用当天 s < 36·hi 的**实际**
        价格算偏差，绝不用到尚未交付时段的价格。已完成样本过少时不修正。
        """
        base = self.forecast0(n)
        b = self.pp.beta_at(hi)
        if hi == 0 or b == 0.0:
            return base
        t0 = 36 * hi
        obs, pred = self.PRICE[n, :t0], base[:t0]
        m = (obs > 0) & (pred > 0)
        if m.sum() < 6:
            return base
        bias = float(np.mean(np.log(obs[m] / pred[m])))
        out = base.copy()
        out[t0:] = base[t0:] * np.exp(b * bias)
        return np.maximum(out, 1e-6)


# ---------------------------------------------------------------- 预测器选型
def _cand_forecast(PRICE: np.ndarray, n: int, lags: tuple,
                   weights: tuple) -> np.ndarray:
    idx, w = [], []
    for lag, wt in zip(lags, weights):
        if n - lag >= 0:
            idx.append(n - lag)
            w.append(wt)
    if not idx:
        return PRICE[:n].mean(axis=0)
    w = np.asarray(w, float)
    return (PRICE[idx] * (w / w.sum())[:, None]).sum(axis=0)


def price_forecast_compare(PRICE: np.ndarray) -> pd.DataFrame:
    """价格预测候选方案在**正式评价区间**上的逐一对表（样本外复核）。

    框架 3.1 节要求"先做简单、可追踪的预测，并明确误差评价方式"，同时允许
    "只有在给出明确理由时才引入更复杂模型"。这张表展示各候选在正式区间上
    的样本外表现，**不参与选型**——选型由 select_forecast_params() 在 1 月
    预热期完成并冻结。候选包含：

      昨天同时段            最朴素的持续预测
      同星期（上周同一天）   捕捉星期效应，但只用一个样本
      近 7/14/28 天滚动均值  平滑但抹掉了星期结构
      同星期等权 1/3        用于确认"加权"本身有没有用
      同星期加权 0.5/0.3/0.2 / 0.6/0.3/0.1
                          用于确认权重怎么给
      全样本固定日内形状     把形状与水平分开、水平取全样本均值（含未来信息，
                          是事后口径，仅作下界参照，不是可用策略）
    """
    lo, hi = REPORT_START, REPORT_END
    rows = []
    for name, lags, w in CANDIDATES:
        err = [float(np.abs(PRICE[n] - _cand_forecast(PRICE, n, lags, w)).mean())
               for n in range(lo, hi)]
        rows.append({"预测器": name, "平均绝对误差_元每kWh": float(np.mean(err))})
    shape = PRICE[lo:hi].mean(axis=0)
    rows.append({"预测器": "全样本固定日内形状（事后口径，仅作下界）",
                 "平均绝对误差_元每kWh": float(np.abs(PRICE[lo:hi] - shape).mean())})
    df = pd.DataFrame(rows)
    df["相对均价"] = df["平均绝对误差_元每kWh"] / float(PRICE[lo:hi].mean())
    return df.sort_values("平均绝对误差_元每kWh").reset_index(drop=True)


CANDIDATES = [
    ("昨天同时段", (1,), (1.0,)),
    ("同星期(上周同一天)", (7,), (1.0,)),
    ("近 7 天滚动均值", tuple(range(1, 8)), (1.0,) * 7),
    ("近 14 天滚动均值", tuple(range(1, 15)), (1.0,) * 14),
    ("近 28 天滚动均值", tuple(range(1, 29)), (1.0,) * 28),
    ("同星期等权 1/3", (7, 14, 21), (1 / 3, 1 / 3, 1 / 3)),
    ("同星期加权 0.5/0.3/0.2", (7, 14, 21), (0.5, 0.3, 0.2)),
    ("同星期加权 0.6/0.3/0.1", (7, 14, 21), (0.6, 0.3, 0.1)),
]


def select_forecast_params(PRICE: np.ndarray, lo: int, hi: int
                           ) -> tuple[PriceForecastParams, dict]:
    """在**预期间** [lo, hi) 上一次性选定价格预测器的权重与 β。

    框架第八节第 2 条要求"选参同样只用过去数据"。因此预测器超参数**只在正式
    评价区间之前的窗口上选一次**，随后整段评价区间冻结使用；评价区间上报出的
    精度与费用因此是真正的样本外结果，不存在"用考试答案选方法"的问题。

    β 逐发布时刻单独选：6:00 只有 36 段已完成样本、18:00 有 108 段，可用于
    估计偏差的样本量不同，最优收缩系数本就未必相同。选择准则统一为"该版本对
    剩余时段的 MAE 最小"。

    返回 (选中参数, 选型记录)；选型记录原样进入结果文件，供论文报告选型窗口、
    候选对照与最终取值。
    """
    scored = [(
        name, lags, w,
        float(np.mean([np.abs(PRICE[n] - _cand_forecast(PRICE, n, lags, w)).mean()
                       for n in range(lo, hi)])),
    ) for name, lags, w in CANDIDATES]
    scored.sort(key=lambda r: r[3])
    rows = [{"预测器": s[0], "平均绝对误差_元每kWh": s[3]} for s in scored]
    best_name, lags, weights, best_err = scored[0]

    # 稳健性：1 月只有 30 天，且前 21 天的滞后 14/21 天样本尚不可用（_cand_forecast
    # 会按可用样本重归一权重）。为确认结论不是这段"退化期"造成的，把预热期再切成
    # 三个子窗口重跑候选对照；若排序不变，选型就可以放心冻结。
    robust = []
    for rlo, rhi, rlab in ((lo, hi, f"全窗口（第 {lo}--{hi - 1} 天）"),
                           (lo + 21, hi, f"后段（第 {lo + 21}--{hi - 1} 天，"
                                         f"滞后样本齐备）"),
                           (lo + 14, hi, f"后半（第 {lo + 14}--{hi - 1} 天）")):
        if rhi - rlo < 5:
            continue
        rr = sorted(
            (float(np.mean([np.abs(PRICE[n]
                                   - _cand_forecast(PRICE, n, l, w)).mean()
                            for n in range(rlo, rhi)])), nm)
            for nm, l, w in CANDIDATES)
        robust.append({"子窗口": rlab, "天数": rhi - rlo,
                       "最优预测器": rr[0][1],
                       "最优平均绝对误差_元每kWh": rr[0][0],
                       "前三": [{"预测器": nm, "平均绝对误差_元每kWh": e}
                                for e, nm in rr[:3]]})

    # β 在**同一预期间**上对表，且用**选中的权重**——此前写死 0.6/0.3/0.1，
    # 权重一旦改变选型就与预测器不一致。
    def _beta_sweep(wlo: int, whi: int) -> tuple[list, dict]:
        rws = []
        for beta in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25):
            pf = PriceForecaster(PRICE, PriceForecastParams(lags, weights, beta))
            perl = []
            for h in (0, 1, 2, 3):
                t0 = 36 * h
                perl.append(float(np.mean(
                    [np.abs(PRICE[n][t0:] - pf.forecast_at(n, h)[t0:]).mean()
                     for n in range(wlo, whi)])))
            rws.append({"β": beta, "各版本_元每kWh": perl})
        bb = {int(h): min(rws, key=lambda r: r["各版本_元每kWh"][h])["β"]
              for h in (1, 2, 3)}
        return rws, bb

    beta_rows, best_beta = _beta_sweep(lo, hi)
    # β 的稳健性：滞后样本齐备的后段窗口上重扫一次，看最优 β 是否漂移。
    if hi - (lo + 21) >= 5:
        _, rbb = _beta_sweep(lo + 21, hi)
        robust.append({"子窗口": f"后段 β 重扫（第 {lo + 21}--{hi - 1} 天）",
                       "天数": hi - (lo + 21), "最优预测器": "（β 逐时刻）",
                       "最优平均绝对误差_元每kWh": None,
                       "前三": [{"预测器": f"{RELEASE_HOURS[h]} 版本 β",
                                 "平均绝对误差_元每kWh": rbb[h]}
                                for h in (1, 2, 3)]})
    pp = PriceForecastParams(
        lags, weights, beta=0.5,
        beta_by_hour=tuple(best_beta[h] for h in (1, 2, 3)))
    record = {
        "窗口": f"第 {lo}--{hi - 1} 天（正式评价区间之外）",
        "候选": rows,
        "最优预测器": best_name,
        "最优平均绝对误差_元每kWh": best_err,
        "选中滞后": list(lags),
        "选中权重": list(weights),
        "β对照": beta_rows,
        "β最优": {RELEASE_HOURS[h]: b for h, b in best_beta.items()},
        "稳健性": robust,
        "选中的参数": pp.label(),
    }
    return pp, record


def verify_price_structure(PRICE: np.ndarray, FIXED: np.ndarray,
                           pp: PriceForecastParams = PRICE_FORECAST) -> dict:
    """验证价格分解 P = F + R 的四个断言（PriceForecastParams 的推导依据）。

    这不是自选动作：框架 8.1/8.2 节要求对价格数据的结构做检查并如实报告，而
    "波动电价与固定电价年平均值相同"这一条直接决定了策略对照该怎么解读——
    如果附件 4 只是把附件 1 的曲线整体抬高或压低，那么费用差异里就混了水平
    效应；实测两者水平相同，费用差异**纯粹来自波动**，对照才是干净的。

    同时报告"同星期加权 == 附件1曲线 + 同星期残差加权"这个恒等式的数值残差。
    """
    R = PRICE - FIXED
    d0 = datetime.date(2025, 1, 1)
    wd = np.array([(d0 + datetime.timedelta(days=n)).weekday()
                   for n in range(N_DAY)])   # 0=周一 … 6=周日
    means = {int(w): float(R[wd == w].mean()) for w in range(7)}
    eff = np.array([means[int(w)] for w in wd])[:, None]
    # 恒等式残差
    gaps = []
    for n in range(REPORT_START, REPORT_END):
        idx = [n - lag for lag in pp.lags if n - lag >= 0]
        w = np.array(pp.weights[:len(idx)], float)
        w = w / w.sum()
        lhs = (PRICE[idx] * w[:, None]).sum(axis=0)
        rhs = FIXED + (R[idx] * w[:, None]).sum(axis=0)
        gaps.append(float(np.abs(lhs - rhs).max()))
    return {
        "断言1_附件4逐段均值与附件1最大偏差": float(
            np.abs(PRICE.mean(axis=0) - FIXED).max()),
        "断言1_年平均值_附件1": float(FIXED.mean()),
        "断言1_年平均值_附件4": float(PRICE.mean()),
        "断言2_残差与固定曲线相关": float(
            np.corrcoef(R.ravel(), np.tile(FIXED, N_DAY))[0, 1]),
        "断言3_残差星期均值_元每kWh": {
            ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][k]: v
            for k, v in means.items()},
        "断言3_周五六均值": float((means[4] + means[5]) / 2),
        "断言3_其余五天均值": float(np.mean([means[k] for k in
                                       (0, 1, 2, 3, 6)])),
        "断言3_两水平差_元每kWh": float(np.mean([means[k] for k in
                                            (0, 1, 2, 3, 6)])
                                  - (means[4] + means[5]) / 2),
        "断言3_相对均价": float((np.mean([means[k] for k in (0, 1, 2, 3, 6)])
                             - (means[4] + means[5]) / 2) / FIXED.mean()),
        "断言4_残差总方差": float(R.var()),
        "断言4_扣除星期效应后方差": float((R - eff).var()),
        "断言4_星期效应解释比例": float(1 - (R - eff).var() / R.var()),
        "断言2_同星期加权恒等式最大残差": float(max(gaps)),
    }


def price_beta_sweep(PRICE: np.ndarray, pp: PriceForecastParams) -> pd.DataFrame:
    """日内对数偏差修正系数 β 的扫描。

    β = 0 相当于不做日内修正。修正用当天已完成时段的平均对数偏差外推，捕捉的
    是**水平的日内漂移**；β 过大则把已实现偏差过度外推，在偏差只是噪声时反而
    变差。表中每个 β 下各列是"在对应发布时刻更新后、对剩余时段的 MAE"。
    """
    rows = []
    for beta in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25):
        pf = PriceForecaster(PRICE, PriceForecastParams(pp.lags, pp.weights,
                                                        beta))
        row = {"β": beta}
        for hi in (0, 1, 2, 3):
            t0 = 36 * hi
            e = [float(np.abs(PRICE[n, t0:] - pf.forecast_at(n, hi)[t0:]).mean())
                 for n in range(REPORT_START, REPORT_END)]
            row[f"{RELEASE_HOURS[hi]}点版本_元每kWh"] = float(np.mean(e))
        rows.append(row)
    return pd.DataFrame(rows)


def price_forecast_skill(PRICE: np.ndarray, pf: PriceForecaster) -> dict:
    """价格预测精度：0:00 版本与各发布时刻更新后的版本（框架 6.3 节）。

    除平均绝对误差外，单独报告**高价时段**的识别情况——框架 6.3 节要求
    "除平均误差外，检查对高价时段及高费用日期的识别情况"。高费用才是真正
    影响账单的部分，平均误差小不代表高价时段看得准。

    另设**共同时段**一列：第 hi 个版本只能修正它发布之后的时段，故四个版本
    的"平均绝对误差"覆盖的时段互不相同（0:00 版覆盖全天 144 段，18:00 版只
    覆盖最后 36 段），直接比大小是错的。共同时段一列把四个版本都限制在
    18:00--24:00（索引 108--143，四个版本都覆盖）上求平均绝对误差，才是可比的。
    两列都保留：前者说明各版本在自己负责的时段上的绝对水平，后者才是版本间排序。
    """
    mae = {hi: [] for hi in (0, 1, 2, 3)}
    hi_mae = {hi: [] for hi in (0, 1, 2, 3)}
    comm = {hi: [] for hi in (0, 1, 2, 3)}
    T_COMMON = 108                              # 18:00 对应的时段索引
    for n in range(REPORT_START, REPORT_END):
        act = PRICE[n]
        thr = float(np.quantile(act, 0.8))      # 当天实际价格的高价阈值
        for hi in (0, 1, 2, 3):
            t0 = 36 * hi
            seg_a = act[t0:]
            seg_h = pf.forecast_at(n, hi)[t0:]
            mae[hi].append(float(np.abs(seg_a - seg_h).mean()))
            m = seg_a >= thr
            if m.sum() > 0:
                hi_mae[hi].append(float(np.abs(seg_a[m] - seg_h[m]).mean()))
            comm[hi].append(float(np.abs(act[T_COMMON:] -
                                        pf.forecast_at(n, hi)[T_COMMON:]).mean()))
    mean_price = float(PRICE[REPORT_START:REPORT_END].mean())
    out = {}
    for hi in (0, 1, 2, 3):
        out[f"{RELEASE_HOURS[hi]}点版本"] = {
            "平均绝对误差_元每kWh": float(np.mean(mae[hi])),
            "相对均价": float(np.mean(mae[hi])) / mean_price,
            "高价时段平均绝对误差_元每kWh": (
                float(np.mean(hi_mae[hi])) if hi_mae[hi] else None),
            "共同时段平均绝对误差_元每kWh": float(np.mean(comm[hi])),
        }
    # 对照：把价格预测换成"全天用同一个均价"，衡量形状信息有没有用
    flat = [float(np.abs(PRICE[n] - PRICE[n].mean()).mean())
            for n in range(REPORT_START, REPORT_END)]
    out["对照_全天均价"] = {
        "平均绝对误差_元每kWh": float(np.mean(flat)),
        "相对均价": float(np.mean(flat)) / mean_price,
        "高价时段平均绝对误差_元每kWh": None,
    }
    return out


# ================================================================ 模块 3：联合风险
def _weighted_quantile(x: np.ndarray, q: float, w: np.ndarray) -> np.ndarray:
    """按列的价格加权分位数 Q^P_q（框架 3.3/3.4 节）。

    x, w 形状均为 (k, m)：k 个历史样本、m 个目标时段。权重是同一目标时段的
    历史**实际电价**，因此加权后的分布 F_P(z) = E[P·1{N≤z}]/E[P] 在
    "价格高 ⇒ 缺电代价大"的方向上给误差更大的权重。权重全为零的列退回
    普通分位数，避免除零。

    定义取**加权经验分布的下确界**（与论文问题四"价格加权分位数"一节的公式
    逐字一致）：

        Q^P_q = inf{ z : Σ_i w_i·1[x_i ≤ z] / Σ_i w_i ≥ q }

    即排序后累积权重比例首次达到 q 的那一个**样本值**。这是临界比规则所要的
    分位数：按此取值，加权意义下的覆盖率恰好达到 q。权重全相等时它精确退化
    为经验分布分位数（np.quantile 的 inverted_cdf 约定）。

    注意不要退回"在累积权重轴上线性插值"（np.interp）的写法：插值出的值可能
    落在两个样本之间，其加权覆盖率并不等于 q（例如样本 [0,10] 等权、q=0.8 时
    插值给 6，而加权覆盖率在该点只有 0.5），且权重全相等时也不退回任何标准
    分位数。见本文件 test_weighted_quantile() 的自检。
    """
    o = np.argsort(x, axis=0)
    xs = np.take_along_axis(x, o, axis=0)
    ws = np.take_along_axis(w, o, axis=0)
    cw = np.cumsum(ws, axis=0)
    tot = cw[-1]
    plain = np.quantile(x, q, axis=0)
    ok = np.isfinite(tot) & (tot > 0)
    # 权重和无效的列目标阈值取 +inf，于是 reached 恒为 False、走普通分位数；
    # argmax 在整列为 False 时返回 0，由 hit 掩掉，不会误取第 0 个样本。
    tgt = np.where(ok, q * tot, np.inf)[None, :]
    reached = cw >= tgt
    hit = reached.any(axis=0)
    idx = reached.argmax(axis=0)
    out = xs[idx, np.arange(x.shape[1])]
    return np.where(hit, out, plain)


def test_weighted_quantile() -> list[str]:
    """加权分位数定义的自检，返回失败项列表（空 = 全部通过）。

    三条性质，缺一不可：
      1) 权重全相等时精确退回经验分布分位数（inverted_cdf 约定）；
      2) 取值必是某个样本值（下确界定义不允许落在样本之间）；
      3) 该点处的加权覆盖率 >= q，且是满足此条件的最小样本值。
    """
    bad: list[str] = []
    checks = []
    for x, w, q in [
        (np.array([[0.0], [10.0]]), np.array([[1.0], [1.0]]), 0.8),
        (np.array([[0.0], [10.0]]), np.array([[1.0], [1.0]]), 0.5),
        (np.array([[0.0], [10.0]]), np.array([[3.0], [1.0]]), 0.8),
        (np.arange(28.0).reshape(-1, 1), np.ones((28, 1)), 0.9),
    ]:
        checks.append((x, w, q))
    for i, (x, w, q) in enumerate(checks):
        got = _weighted_quantile(x, q, w)[0]
        xs = np.sort(x[:, 0])
        ws = w[np.argsort(x[:, 0]), 0]
        # 1) 等权退回 inverted_cdf
        if np.allclose(w[:, 0], w[0, 0]):
            ref = float(np.quantile(x, q, axis=0, method="inverted_cdf")[0])
            if not np.isclose(got, ref):
                bad.append(f"自检{i}: 等权未退回 inverted_cdf（{got} vs {ref}）")
        # 2) 取值必是样本值
        if not np.any(np.isclose(got, xs)):
            bad.append(f"自检{i}: 取值 {got} 不在样本中")
        # 3) 覆盖率 >= q 且最小
        cw = np.cumsum(ws)
        cov = cw[np.isclose(xs, got)][0] / cw[-1]
        if cov < q - 1e-12:
            bad.append(f"自检{i}: 覆盖率 {cov:.4f} < q={q}")
        smaller = xs[xs < got - 1e-12]
        if smaller.size:
            cws = np.cumsum(ws)[np.isclose(xs, smaller[-1])][0] / cw[-1]
            if cws >= q - 1e-12:
                bad.append(f"自检{i}: 存在更小的满足点 {smaller[-1]}")
    # 4) 权重和为零退回普通分位数（不除零、不出 NaN）
    z = _weighted_quantile(np.arange(28.0).reshape(-1, 1), 0.8,
                           np.zeros((28, 1)))
    if not np.isfinite(z[0]):
        bad.append("自检4: 零权重未退回普通分位数（出现 NaN）")
    return bad


def _pool_slots(hist: np.ndarray, wp: np.ndarray | None, span: int = 2):
    """样本不足时合并相邻 ±span 个十分钟时段，再取分位数。

    合并的是**同一批历史日期**的相邻时段，不引入未来信息。
    """
    m = hist.shape[1]
    pooled = np.empty_like(hist)
    pooled_w = None if wp is None else np.empty_like(wp)
    for s in range(m):
        a, b = max(0, s - span), min(m, s + span + 1)
        pooled[:, s] = hist[:, a:b].mean(axis=1)
        if wp is not None:
            pooled_w[:, s] = wp[:, a:b].mean(axis=1)
    return pooled, pooled_w


def _margin_from(hist: np.ndarray, wp: np.ndarray | None, alpha: float,
                 min_samples: int, weighted: bool, span: int = 2
                 ) -> np.ndarray:
    """在给定历史残差上取（价格加权）分位数，样本不足则先合并相邻时段。"""
    if hist.shape[0] >= min_samples:
        if weighted:
            return _weighted_quantile(hist, alpha, wp)
        return np.quantile(hist, alpha, axis=0)
    pooled, pooled_w = _pool_slots(hist, wp if weighted else None, span)
    if weighted:
        return _weighted_quantile(pooled, alpha, pooled_w)
    return np.quantile(pooled, alpha, axis=0)


def risk_margin4(eps: np.ndarray, n: int, alpha: float | None,
                 PRICE: np.ndarray, window: int = 28, min_samples: int = 10,
                 weighted: bool = True) -> np.ndarray:
    """4-2 的风险余量：价格加权分位数（框架 3.4 节）。

    eps 是 (365,144) 的净负荷预测残差（问题二口径：光伏也靠历史外推，
    因为框架 2.1 节规定附件 3 只进入 4-3）。权重取同一目标时段的历史实际
    电价 PRICE[lo:n, t]，全部是第 n 天之前已观测完的数据，满足信息边界。
    """
    out = np.zeros(N)
    if alpha is None or n == 0:
        return out
    lo = max(0, n - window)
    hist = eps[lo:n, :]
    keep = ~np.isnan(hist).all(axis=1)
    hist = hist[keep]
    if hist.shape[0] < 3:
        return out
    wp = PRICE[lo:n, :][keep] if weighted else None
    return _margin_from(hist, wp, alpha, min_samples, weighted)


def risk_margin4_ver(eps3: np.ndarray, hi: int, n: int, alpha: float | None,
                     PRICE: np.ndarray, window: int = 28,
                     min_samples: int = 10, weighted: bool = True
                     ) -> np.ndarray:
    """4-3 的按发布版本价格加权风险余量。

    与 risk_margin4 同构，只是残差取 eps3[hi] 且只在 t ≥ 36·hi 上有定义。
    逻辑与 p3 的 risk_margin3 一致，只把"分位数"换成"价格加权分位数"。
    """
    t0 = 36 * hi
    out = np.zeros(N)
    if alpha is None or n == 0:
        return out
    lo = max(0, n - window)
    hist = eps3[hi, lo:n, t0:]
    keep = ~np.isnan(hist).all(axis=1)
    hist = hist[keep]
    if hist.shape[0] < 3:
        return out
    wp = PRICE[lo:n, t0:][keep] if weighted else None
    out[t0:] = _margin_from(hist, wp, alpha, min_samples, weighted)
    return out


def risk_weight_effect(eps: np.ndarray, PRICE: np.ndarray,
                       alphas=(0.5, 0.6, 0.7, 0.8)) -> pd.DataFrame:
    """价格加权与普通分位数的对照表，支撑框架 3.3 节的判断。

    在正式区间内抽样逐日求两种口径的风险余量，报告均值与被加权口径抬高的
    幅度。若加权与不加权几乎一样，框架 3.3 节就可以一句话带过；实测差别
    显著，故必须作为模型的一部分写进论文。
    """
    rows = []
    ones = np.ones_like(PRICE)
    ns = range(REPORT_START, REPORT_END, 7)
    for a in alphas:
        w = [risk_margin4(eps, n, a, PRICE, weighted=True) for n in ns]
        p = [risk_margin4(eps, n, a, PRICE, weighted=False) for n in ns]
        # 与加权口径**同约定**的等权基线：权重恒为 1 的加权分位数精确等于经验
        # 分布分位数（inverted_cdf），且走完全相同的合并时段逻辑。用它作分母，
        # "相对抬升"才是纯粹的加权效应；用 p（问题二的线性插值约定）作分母则
        # 会混入取值约定之差。两列都报，读者可自行核对。
        q = [risk_margin4(eps, n, a, ones, weighted=True) for n in ns]
        wm, pm = float(np.mean(w)), float(np.mean(p))
        qm = float(np.mean(q))
        rows.append({"α": a, "价格加权均值_kWh": wm,
                     "普通分位数均值_kWh": pm, "抬高_kWh": wm - pm,
                     "相对抬升": (wm / pm - 1.0) if pm > 1e-9 else None,
                     "等权下确界均值_kWh": qm,
                     "纯加权相对抬升": (wm / qm - 1.0) if qm > 1e-9 else None})
    # pm 可能在 α≤0.5 时为负（误差中位数本身为负），此时"相对抬升"无意义，
    # 上面已置 None，避免 NaN 进入 JSON。
    return pd.DataFrame(rows)


def risk_price_correlation(eps: np.ndarray, PRICE: np.ndarray) -> dict:
    """框架 3.2 节的协方差检查：残差与电价到底有没有关系。

    这是框架明确要求"不能在未分析数据前就认定"的那一步，因此报告两种口径：

      合并口径  把全部 (日期, 时段) 样本混在一起算。这一口径会被"时段之间的
                电价差异"主导——傍晚电价高、误差也大——看起来相关，但分不清
                是"同时段内价格高伴随误差大"还是单纯"贵时段误差本来就大"。
      逐时段口径  对每个目标时段单独算相关，再看这 144 个系数的分布。这才是
                风险余量真正的建模对象，因为余量是逐时段加的。

    实测逐时段的相关系数明显高于合并口径，说明这种关系**是同时段内的性质**，
    不是时段间的成分。eps 是 kWh/时段，此处换算成 kW 再报告，与负载同量纲。
    """
    e_all = eps[REPORT_START:REPORT_END, :] / TAU          # kWh/时段 → kW
    p_all = PRICE[REPORT_START:REPORT_END, :]
    m = np.isfinite(e_all)
    e, p = e_all[m], p_all[m]
    hi = e[p >= float(np.quantile(p, 0.8))]
    lo = e[p <= float(np.quantile(p, 0.2))]
    r = float(np.corrcoef(e, p)[0, 1])
    # 逐时段相关：只保留两端都有变异的时段，避免常数序列产生 NaN
    cs = []
    for t in range(N):
        a, b = e_all[:, t], p_all[:, t]
        ok = np.isfinite(a)
        if ok.sum() > 10 and np.std(a[ok]) > 1e-9 and np.std(b[ok]) > 1e-9:
            cs.append(float(np.corrcoef(a[ok], b[ok])[0, 1]))
    cs = np.array(cs)
    return {
        "样本数": int(e.size),
        "合并相关系数": r,
        "合并协方差_kW元每kWh": float(np.cov(e, p)[0, 1]),
        "逐时段相关系数均值": float(cs.mean()),
        "逐时段相关系数最小": float(cs.min()),
        "逐时段相关系数最大": float(cs.max()),
        "逐时段相关为正的比例": float((cs > 0).mean()),
        "低价20%_误差均值_kW": float(lo.mean()),
        "低价20%_正误差概率": float((lo > 0).mean()),
        "高价20%_误差均值_kW": float(hi.mean()),
        "高价20%_正误差概率": float((hi > 0).mean()),
        "两端误差均值差_kW": float(hi.mean() - lo.mean()),
        "结论": ("协方差为正，忽略会低估紧急购电风险" if r > 0
                 else "协方差为负，忽略会高估风险"),
    }


# ================================================================ 决策价格
class PriceBook:
    """按价格模式给出决策时刻应当使用的价格（框架 6.1 节的三种策略）。

    三种模式在**结算**时都使用附件 4 的实际价格，区别只在于**做决策时**看得
    到什么价格。这正是"用当时能知道的信息决策、用实际价格结算"的具体落实。
    """

    def __init__(self, PRICE: np.ndarray, FIXED: np.ndarray,
                 pf: PriceForecaster):
        self.PRICE, self.FIXED, self.pf = PRICE, FIXED, pf

    def decide(self, n: int, hi: int, mode: str) -> np.ndarray:
        if mode == "oracle":
            # 信息增强对照：假设当天价格已完全公布。仍不读取未来负载、光伏
            # 或未发布的预报（框架 6.1 节末段）。
            return self.PRICE[n].copy()
        if mode == "fixed":
            # 沿用附件 1 的固定分时电价——"把原有价格判断直接搬到新环境"
            return self.FIXED.copy()
        if mode == "forecast":
            return self.pf.forecast_at(n, hi)
        raise ValueError(f"未知价格模式 {mode!r}")


# ================================================================ 模块 4：4-2
@dataclass
class DayRecord42:
    """4-2 的单日记录。price_hat 是决策用价，price_act 是结算用价。"""

    n: int
    date: str
    g: np.ndarray
    c: np.ndarray
    d: np.ndarray
    r: np.ndarray
    w: np.ndarray
    E: np.ndarray
    E0: float
    Ebar: np.ndarray
    price_hat: np.ndarray
    price_act: np.ndarray
    l_hat: np.ndarray
    v_hat: np.ndarray
    n_hat: np.ndarray
    margin: np.ndarray
    n_risk: np.ndarray
    l_act: np.ndarray
    v_act: np.ndarray
    mode: str

    @property
    def E_end(self) -> float:
        return float(self.E[-1])

    @property
    def cost_plan(self) -> float:
        return float(np.sum(self.price_act * self.g))

    @property
    def cost_emg(self) -> float:
        return float(np.sum(COEF_EMG * self.price_act * self.r))

    @property
    def cost_total(self) -> float:
        return self.cost_plan + self.cost_emg

    @property
    def cost_plan_hat(self) -> float:
        """同一个计划量若按**当时预测的价格**计费会是多少（框架 8 节第 7 条）。

        优化器的目标值与真实账单是两个不同的量：前者用预测价，后者用实际价。
        两者之差就是"预计便宜"与"实际便宜"的差距，必须在账本里能直接看出来。
        """
        return float(np.sum(self.price_hat * self.g))

    @property
    def cost_total_hat(self) -> float:
        return self.cost_plan_hat + float(
            np.sum(COEF_EMG * self.price_hat * self.r))


def forecast_energy_slots_p2(fo: Forecaster, n: int) -> np.ndarray:
    """4-2 的光伏预测：问题二口径的历史外推，不用附件 3。"""
    if n == 0:
        return np.zeros(N)
    _, v_hat, _ = fo.energy(n)
    return v_hat


def run_day42(n: int, e0: float, params: RiskParams, book: PriceBook,
              mode: str, LOAD: np.ndarray, PV: np.ndarray, eps: np.ndarray,
              fo: Forecaster, weighted: bool = True) -> DayRecord42:
    """回放 4-2 的第 n 天：0:00 用预测价定计划，日内按实际价结算。

    框架 4.1 节：负载与光伏都按历史外推预测（**不使用附件 3**）；把原固定
    价格系数替换为当时预测的价格，并使用价格加权的风险净负荷。计划一旦
    定下，日内不因价格变化而修改。

    第 0 天一律冷启动：既无价格历史（日前 LP 拿不到决策价格）也无负载/光伏
    历史，故计划购电为零、储能不越储备线，缺口全部紧急补购。三种价格模式
    同此口径，ΔJ 才只反映评价区间内的价格信息之差。
    """
    l_act = LOAD[n, :] * TAU
    v_act = PV[n, :] * TAU
    date = _date_of(n)
    price_act = book.PRICE[n]

    if n == 0:
        z = np.zeros(N)
        runner = DayRunner(l_act, v_act, e0, params.rho)
        runner.run(0, N, z, np.full(N, E_INIT))
        return DayRecord42(
            n=n, date=date, g=z.copy(), c=runner.c, d=runner.d, r=runner.r,
            w=runner.w, E=runner.E, E0=float(e0), Ebar=np.full(N, E_INIT),
            price_hat=z.copy(), price_act=price_act, l_hat=z.copy(),
            v_hat=z.copy(), n_hat=z.copy(), margin=z.copy(), n_risk=z.copy(),
            l_act=l_act, v_act=v_act, mode=mode)

    l_hat_day, _, _ = fo.energy(n)
    l_hat = load_forecast_at(l_hat_day, l_act, 0)
    v_hat = forecast_energy_slots_p2(fo, n)
    n_hat = l_hat - v_hat
    margin = risk_margin4(eps, n, params.alpha, book.PRICE,
                          window=params.window, min_samples=params.min_samples,
                          weighted=weighted)
    n_risk = n_hat + margin

    price_hat = book.decide(n, 0, mode)
    plan = solve_dayahead(n_risk, e0, price_hat, params)
    # 执行层不接受价格输入：储能按当前已观测的供需因果响应（问题二 5.2 节），
    # 价格只影响 0:00 的计划与随后的费用统计。
    ex = execute_day(plan.g, plan.Ebar, l_act, v_act, e0, price_act, params)

    return DayRecord42(
        n=n, date=date, g=plan.g, c=ex.c, d=ex.d, r=ex.r, w=ex.w, E=ex.E,
        E0=float(e0), Ebar=plan.Ebar, price_hat=price_hat,
        price_act=price_act, l_hat=l_hat, v_hat=v_hat, n_hat=n_hat,
        margin=margin, n_risk=n_risk, l_act=l_act, v_act=v_act, mode=mode)


def replay42(n0: int, n1: int, e0: float, params: RiskParams, book: PriceBook,
             mode: str, LOAD: np.ndarray, PV: np.ndarray, eps: np.ndarray,
             fo: Forecaster, weighted: bool = True
             ) -> tuple[list[DayRecord42], float]:
    """从 e0 出发回放 [n0, n1) 天，返回 (逐日记录, 末日储电量)。"""
    recs, e = [], float(e0)
    for n in range(n0, n1):
        rec = run_day42(n, e, params, book, mode, LOAD, PV, eps, fo, weighted)
        recs.append(rec)
        e = rec.E_end
    return recs, e


def calibrate42(n0: int, e_at_window_start: float, cal: CalConfig,
                book: PriceBook, mode: str, LOAD: np.ndarray, PV: np.ndarray,
                eps: np.ndarray, fo: Forecaster, weighted: bool = True
                ) -> tuple[RiskParams, list[dict]]:
    """4-2 的滚动参数标定：在窗口内回放，取**实际结算总费用**最小者。

    窗口初值取主运行在窗口起点日 0:00 的实际储电量（不是第 n0 天，第 n0 天
    在窗口末尾），避免把未来状态信息带入。标定目标是实际价格结算的费用，
    不是预测目标值——框架 8.7 节要求"预测费用、规划中的补购量和日末储备惩罚
    不能直接当作真实结果"。
    """
    lo = max(0, n0 - cal.window)
    rows, best, best_cost = [], None, np.inf
    for rp in cal.grid():
        recs, _ = replay42(lo, n0, e_at_window_start, rp, book, mode,
                           LOAD, PV, eps, fo, weighted)
        cost = sum(r.cost_total for r in recs)
        rows.append({"标定日": _date_of(n0), "窗口起": _date_of(lo),
                     "参数": rp.label(), "窗口实际总费用_元": cost,
                     "选中": False})
        if cost < best_cost - 1e-9:
            best, best_cost = rp, cost
    assert best is not None
    for row in rows:
        row["选中"] = row["参数"] == best.label()
    return best, rows


def select_warmup42(core: CorePreset, book: PriceBook, mode: str,
                    LOAD: np.ndarray, PV: np.ndarray, eps: np.ndarray,
                    fo: Forecaster, weighted: bool = True
                    ) -> tuple[RiskParams, list[dict]]:
    """4-2 的 1 月联合标定：只用 1 月数据在 (α,ρ,λ) 上选预热期参数。

    准则与滚动标定一致——1 月 31 天上回放、取**实际结算总费用**最小者；
    第 0 天对所有候选相同，故不影响比较。选出的 λ 随后整年冻结。
    """
    rows: list[dict] = []
    best: RiskParams | None = None
    best_cost = np.inf
    for rp in core.warmup_grid():
        cost = 0.0
        e = float(E_INIT)
        for n in range(core.warmup_n_days):
            rec = run_day42(n, e, rp, book, mode, LOAD, PV, eps, fo, weighted)
            cost += rec.cost_total
            e = rec.E_end
        rows.append({"参数": rp.label(), "1月总费用_元": cost,
                     "2月1日储电量_kWh": e, "选中": False})
        if cost < best_cost - 1e-9:
            best, best_cost = rp, cost
    assert best is not None, "4-2 的 1 月联合标定：没有任何可行组合"
    for row in rows:
        row["选中"] = row["参数"] == best.label()
    return best, rows


def run_strategy42(cal: CalConfig, book: PriceBook, mode: str,
                   LOAD: np.ndarray, PV: np.ndarray, eps: np.ndarray,
                   fo: Forecaster, e_init: float = E_INIT,
                   weighted: bool = True, verbose: bool = False,
                   warmup: RiskParams | None = None
                   ) -> tuple[list[DayRecord42], list[dict]]:
    """4-2 全年滚动：预热 1 月，正式区间内每隔 cal.every 天重新标定一次。

    `warmup` 给出 1 月预热期参数，由 `select_warmup42` 在 1 月数据上离线选出；
    传 None 时退回旧的硬编码值（α=0.80/ρ=1.0/λ=0.60），仅供复现历史数字。
    """
    recs, cal_rows = [], []
    e = float(e_init)
    e_at = np.full(N_DAY + 1, np.nan)
    e_at[0] = e
    params = (warmup if warmup is not None
              else RiskParams(alpha=0.80, rho=1.0, lam=LAMBDA_DEFAULT))
    for n in range(N_DAY):
        if n >= cal.start and (n - cal.start) % cal.every == 0:
            params, rows = calibrate42(n, e_at[max(0, n - cal.window)], cal,
                                       book, mode, LOAD, PV, eps, fo, weighted)
            cal_rows.extend(rows)
            if verbose:
                print(f"    [4-2 {_date_of(n)}] 选中 {params.label()}",
                      flush=True)
        rec = run_day42(n, e, params, book, mode, LOAD, PV, eps, fo, weighted)
        recs.append(rec)
        e = rec.E_end
        e_at[n + 1] = e
    return recs, cal_rows


# ================================================================ 模块 5：4-3
@dataclass
class DayRecord43:
    n: int
    date: str
    g0: np.ndarray            # 0:00 冻结的初始计划
    x: np.ndarray             # 最终生效的完整购电量
    c: np.ndarray
    d: np.ndarray
    r: np.ndarray
    w: np.ndarray
    E: np.ndarray
    E0: float
    Ebar: np.ndarray
    price_hat0: np.ndarray    # 0:00 决策价
    price_act: np.ndarray     # 结算价
    l_hat0: np.ndarray
    v_hat0: np.ndarray
    n_hat0: np.ndarray
    margin0: np.ndarray
    n_risk0: np.ndarray
    l_act: np.ndarray
    v_act: np.ndarray
    n_solve: int
    n_submit: int
    S: tuple
    mode: str
    convention: str

    @property
    def E_end(self) -> float:
        return float(self.E[-1])

    @property
    def cost_plan(self) -> float:
        return float(np.sum(self.price_act * self.g0))

    @property
    def cost_adj(self) -> float:
        up = np.maximum(self.x - self.g0, 0.0)
        if self.convention == "main":
            return float(np.sum(COEF_UP * self.price_act * up))
        dn = np.maximum(self.g0 - self.x, 0.0)
        return float(np.sum(COEF_UP * self.price_act * up
                            - COEF_DOWN * self.price_act * dn))

    @property
    def cost_emg(self) -> float:
        return float(np.sum(COEF_EMG * self.price_act * self.r))

    @property
    def cost_total(self) -> float:
        return self.cost_plan + self.cost_adj + self.cost_emg

    @property
    def cost_plan_hat(self) -> float:
        """初始计划与最终量若都按 **0:00 的预测价**计费（框架 8 节第 7 条）。

        与 cost_plan + cost_adj 的差别：那里用实际价结算，这里用当时预测价，
        故差额 = ``预测觉得自己省了多少''与``账本上真的省了多少''的差。
        """
        up = np.maximum(self.x - self.g0, 0.0)
        dn = np.maximum(self.g0 - self.x, 0.0)
        base = float(np.sum(self.price_hat0 * self.g0))
        if self.convention == "main":
            return base + float(np.sum(COEF_UP * self.price_hat0 * up))
        return base + float(np.sum(COEF_UP * self.price_hat0 * up
                                   - COEF_DOWN * self.price_hat0 * dn))

    @property
    def cost_total_hat(self) -> float:
        return self.cost_plan_hat + float(
            np.sum(COEF_EMG * self.price_hat0 * self.r))

    @property
    def g_initial(self) -> float:
        return float(self.g0.sum())

    @property
    def g_effective(self) -> float:
        return float(self.x.sum())

    @property
    def g_emg(self) -> float:
        return float(self.r.sum())

    @property
    def up(self) -> float:
        return float(np.maximum(self.x - self.g0, 0.0).sum())

    @property
    def down(self) -> float:
        return float(np.maximum(self.g0 - self.x, 0.0).sum())


_PLAN0_CACHE4: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def initial_plan4(n: int, ntilde0: np.ndarray, e0: float,
                  price: np.ndarray, rp: RiskParams, tag: str
                  ) -> tuple[np.ndarray, np.ndarray]:
    """0:00 初始计划的带缓存求解。

    缓存键比 p3 多一个 tag：问题四里**同一天、同一个 (α,λ,e0) 在不同价格模式
    下会得到不同的计划**（预测价 vs 固定价 vs 已知未来价），若沿用 p3 的
    (n, α, λ, e0) 键会把三种策略的计划互相污染。
    """
    key = (tag, n, rp.alpha, rp.lam, round(float(e0), 6))
    hit = _PLAN0_CACHE4.get(key)
    if hit is not None:
        return hit[0].copy(), hit[1].copy()
    if len(_PLAN0_CACHE4) > 60000:
        _PLAN0_CACHE4.clear()
    plan = solve_dayahead(ntilde0, e0, price, rp)
    _PLAN0_CACHE4[key] = (plan.g.copy(), plan.Ebar.copy())
    return plan.g, plan.Ebar


def run_day43(n: int, e0: float, S: tuple, params: RiskParams,
              book: PriceBook, mode: str, LOAD: np.ndarray, PV: np.ndarray,
              fp: ForecastPanel, eps3: np.ndarray, fo: Forecaster,
              convention: str = "main", weighted: bool = True) -> DayRecord43:
    """回放 4-3 的第 n 天：0:00 定初始计划，6/12/18 时按新预报调整。

    与问题三的差别集中在"价格"二字上，规则本身不变（框架 5.1 节："实时电价
    每十分钟波动，并不自动增加普通购电调整时点"）：
      * 0:00 用当时的预测价定 g⁰；
      * 第 hi 个交付块若在使用集合 S 内，用**该时刻更新的价格预测**重解剩余
        时段的调整问题，只正式提交当前交付块，更远时段只是内部展望；
      * 全部费用按实际价格结算，包括初始计划费（框架 5.3 节）。

    第 0 天一律冷启动，理由同 4-2（见 `run_day42`）：无价格历史即无决策价格。
    """
    l_act = LOAD[n, :] * TAU
    v_act = PV[n, :] * TAU
    date = _date_of(n)
    price_act = book.PRICE[n]

    if n == 0:
        z = np.zeros(N)
        runner = DayRunner(l_act, v_act, e0, params.rho)
        runner.run(0, N, z, np.full(N, E_INIT))
        return DayRecord43(
            n=n, date=date, g0=z.copy(), x=z.copy(), c=runner.c, d=runner.d,
            r=runner.r, w=runner.w, E=runner.E, E0=float(e0),
            Ebar=np.full(N, E_INIT), price_hat0=z.copy(), price_act=price_act,
            l_hat0=z.copy(), v_hat0=z.copy(), n_hat0=z.copy(),
            margin0=z.copy(), n_risk0=z.copy(), l_act=l_act, v_act=v_act,
            n_solve=0, n_submit=0, S=(), mode=mode, convention=convention)

    l_hat_day, _, _ = fo.energy(n)
    l_hat0 = load_forecast_at(l_hat_day, l_act, 0)
    v_hat0 = forecast_energy_slots(fp, 0, n)
    margin0 = risk_margin4_ver(eps3, 0, n, params.alpha, book.PRICE,
                               window=params.window,
                               min_samples=params.min_samples,
                               weighted=weighted)
    n_hat0 = l_hat0 - v_hat0
    n_risk0 = n_hat0 + margin0
    price_hat0 = book.decide(n, 0, mode)
    tag = f"{mode}|{convention}|{S}"      # 计划缓存必须区分策略
    g0, Ebar = initial_plan4(n, n_risk0, e0, price_hat0, params, tag)
    x = g0.copy()

    runner = DayRunner(l_act, v_act, e0, params.rho)
    n_solve, n_submit = 1, 0

    for hi, (a, b) in enumerate(BLOCK_BOUNDS):
        if hi > 0 and RELEASE_HOURS[hi] in S:
            l_hat_h = load_forecast_at(l_hat_day, l_act, hi)
            v_hat_h = forecast_energy_slots(fp, hi, n)
            margin_h = risk_margin4_ver(eps3, hi, n, params.alpha,
                                        book.PRICE, window=params.window,
                                        min_samples=params.min_samples,
                                        weighted=weighted)
            n_risk_h = (l_hat_h - v_hat_h) + margin_h
            # 关键：调整目标用**该发布时刻更新的价格预测**，而不是 0:00 的
            # 预测价；结算仍走 price_act。
            price_h = book.decide(n, hi, mode)
            res = solve_adjust(n_risk_h[a:], g0[a:], runner.Ep, price_h[a:],
                               params, convention)
            x[a:b] = res.y[:b - a]          # 只正式提交当前交付块
            Ebar[a:] = res.Ebar             # 参考轨迹整体刷新（含展望部分）
            n_solve += 1
            n_submit += 1
        runner.run(a, b, x, Ebar)

    return DayRecord43(
        n=n, date=date, g0=g0, x=x, c=runner.c, d=runner.d, r=runner.r,
        w=runner.w, E=runner.E, E0=float(e0), Ebar=Ebar,
        price_hat0=price_hat0, price_act=price_act, l_hat0=l_hat0,
        v_hat0=v_hat0, n_hat0=n_hat0, margin0=margin0, n_risk0=n_risk0,
        l_act=l_act, v_act=v_act, n_solve=n_solve, n_submit=n_submit,
        S=tuple(S), mode=mode, convention=convention)


def replay43(n0: int, n1: int, e0: float, S: tuple, params: RiskParams,
             book: PriceBook, mode: str, LOAD: np.ndarray, PV: np.ndarray,
             fp: ForecastPanel, eps3: np.ndarray, fo: Forecaster,
             convention: str = "main", weighted: bool = True
             ) -> tuple[list[DayRecord43], float]:
    recs, e = [], float(e0)
    for n in range(n0, n1):
        rec = run_day43(n, e, S, params, book, mode, LOAD, PV, fp, eps3, fo,
                        convention, weighted)
        recs.append(rec)
        e = rec.E_end
    return recs, e


def calibrate43(n0: int, e_at_window_start: float, cal: CalConfig3,
                book: PriceBook, mode: str, LOAD: np.ndarray, PV: np.ndarray,
                fp: ForecastPanel, eps3: np.ndarray, fo: Forecaster,
                convention: str = "main", weighted: bool = True
                ) -> tuple[RiskParams, list[dict]]:
    """4-3 的滚动标定，目标同样是窗口内的**实际结算总费用**。

    mode / convention 必须原样转交 replay43：标定是在**该策略自己的信息集与
    计费口径**下进行的，否则固定电价对照与退款口径敏感性会用另一套策略的
    参数，对照就失去意义（沿用 p3 的同一原则）。
    """
    lo = max(0, n0 - cal.window)
    rows, best, best_cost = [], None, np.inf
    for rp in cal.grid():
        recs, _ = replay43(lo, n0, e_at_window_start, cal.S, rp, book, mode,
                           LOAD, PV, fp, eps3, fo, convention, weighted)
        cost = sum(r.cost_total for r in recs)
        rows.append({"标定日": _date_of(n0), "窗口起": _date_of(lo),
                     "参数": rp.label(), "窗口实际总费用_元": cost,
                     "选中": False})
        if cost < best_cost - 1e-9:
            best, best_cost = rp, cost
    assert best is not None
    for row in rows:
        row["选中"] = row["参数"] == best.label()
    return best, rows


def select_warmup43(core: CorePreset, book: PriceBook, mode: str,
                    LOAD: np.ndarray, PV: np.ndarray, fp: ForecastPanel,
                    eps3: np.ndarray, fo: Forecaster, convention: str = "main",
                    weighted: bool = True
                    ) -> tuple[RiskParams, list[dict]]:
    """4-3 的 1 月联合标定：只用 1 月数据在 (α,ρ,λ) 上选预热期参数。

    S 固定取空集：1 月预热期不触发调整（REPORT_START 之前没有标定，也没有
    调整时点的信息可用），故预热期参数与后续使用集合无关，可以离线一次选定。
    """
    rows: list[dict] = []
    best: RiskParams | None = None
    best_cost = np.inf
    for rp in core.warmup_grid():
        cost = 0.0
        e = float(E_INIT)
        for n in range(core.warmup_n_days):
            rec = run_day43(n, e, (), rp, book, mode, LOAD, PV, fp, eps3, fo,
                            convention, weighted)
            cost += rec.cost_total
            e = rec.E_end
        rows.append({"参数": rp.label(), "1月总费用_元": cost,
                     "2月1日储电量_kWh": e, "选中": False})
        if cost < best_cost - 1e-9:
            best, best_cost = rp, cost
    assert best is not None, "4-3 的 1 月联合标定：没有任何可行组合"
    for row in rows:
        row["选中"] = row["参数"] == best.label()
    return best, rows


def run_strategy43(cal: CalConfig3, book: PriceBook, mode: str,
                   LOAD: np.ndarray, PV: np.ndarray, fp: ForecastPanel,
                   eps3: np.ndarray, fo: Forecaster, S: tuple | None = None,
                   e_init: float = E_INIT, convention: str = "main",
                   weighted: bool = True, verbose: bool = False,
                   warmup: RiskParams | None = None
                   ) -> tuple[list[DayRecord43], list[dict]]:
    """整年滚动：预热 1 月，正式区间内每隔 cal.every 天重新标定一次参数。

    `warmup` 给出 1 月预热期参数，由 `select_warmup43` 在 1 月数据上离线选出；
    传 None 时退回旧的硬编码值（α=0.60/ρ=0.5/λ=0.60），仅供复现历史数字。
    """
    S = cal.S if S is None else tuple(S)
    recs, cal_rows = [], []
    e = float(e_init)
    e_at = np.full(N_DAY + 1, np.nan)
    e_at[0] = e
    params = (warmup if warmup is not None
              else RiskParams(alpha=0.60, rho=0.5, lam=LAMBDA_DEFAULT))
    for n in range(N_DAY):
        if n >= cal.start and (n - cal.start) % cal.every == 0:
            params, rows = calibrate43(n, e_at[max(0, n - cal.window)], cal,
                                       book, mode, LOAD, PV, fp, eps3, fo,
                                       convention, weighted)
            cal_rows.extend(rows)
            if verbose:
                print(f"    [4-3 {_date_of(n)}] 选中 {params.label()}",
                      flush=True)
        rec = run_day43(n, e, S, params, book, mode, LOAD, PV, fp, eps3, fo,
                        convention, weighted)
        recs.append(rec)
        e = rec.E_end
        e_at[n + 1] = e
    return recs, cal_rows


# ================================================================ 模块 6：汇总与校验
def _sum(recs, attr: str) -> float:
    return float(sum(getattr(r, attr) for r in recs))


def _wavg(recs, qty: str, price: str) -> float:
    """按电量加权的均价（框架 6.3 节：要能看出充放电发生在什么价位）。

    不能用简单平均：均价必须按各时段的电量加权，否则低压低谷时段的零星
    充放电会与高峰时段的大量充放电等权，掩盖"低价充电、高价放电"的实际情况。
    """
    q = sum(float(getattr(r, qty).sum()) for r in recs)
    if q <= 1e-9:
        return 0.0
    num = sum(float((getattr(r, price) * getattr(r, qty)).sum()) for r in recs)
    return float(num / q)


def totals42(recs: list[DayRecord42]) -> dict:
    cp, ce = _sum(recs, "cost_plan"), _sum(recs, "cost_emg")
    return {
        "天数": len(recs),
        "计划量_kWh": float(sum(r.g.sum() for r in recs)),
        "紧急购电量_kWh": float(sum(r.r.sum() for r in recs)),
        "收到总电量_kWh": float(sum((r.g + r.r).sum() for r in recs)),
        "计划费_元": cp,
        "调整费_元": 0.0,
        "紧急费_元": ce,
        "合计费用_元": cp + ce,
        "弃电量_kWh": float(sum(r.w.sum() for r in recs)),
        "充电量_kWh": float(sum(r.c.sum() for r in recs)),
        "放电量_kWh": float(sum(r.d.sum() for r in recs)),
        "期初储电量_kWh": float(recs[0].E0),
        "期末储电量_kWh": float(recs[-1].E[-1]),
        "调整提交次数": 0,
        "MILP求解次数": len(recs),
        # 框架第八节第 7 条：优化器的目标值（按预测价）与真实账单（按实际价）
        "预估费用_元": _sum(recs, "cost_total_hat"),
        # 框架 6.3 节：充放电与紧急补购各自发生在什么价位
        "充电加权均价_元每kWh": _wavg(recs, "c", "price_act"),
        "放电加权均价_元每kWh": _wavg(recs, "d", "price_act"),
        "紧急购电加权均价_元每kWh": _wavg(recs, "r", "price_act"),
    }


def totals43(recs: list[DayRecord43]) -> dict:
    cp, ca, ce = (_sum(recs, "cost_plan"), _sum(recs, "cost_adj"),
                  _sum(recs, "cost_emg"))
    return {
        "天数": len(recs),
        "计划量_kWh": float(sum(r.g0.sum() for r in recs)),
        "初始计划量_kWh": float(sum(r.g0.sum() for r in recs)),
        "最终常规量_kWh": float(sum(r.x.sum() for r in recs)),
        "上调量_kWh": _sum(recs, "up"),
        "下调量_kWh": _sum(recs, "down"),
        "紧急购电量_kWh": float(sum(r.r.sum() for r in recs)),
        "收到总电量_kWh": float(sum((r.x + r.r).sum() for r in recs)),
        "计划费_元": cp,
        "调整费_元": ca,
        "紧急费_元": ce,
        "合计费用_元": cp + ca + ce,
        "弃电量_kWh": float(sum(r.w.sum() for r in recs)),
        "充电量_kWh": float(sum(r.c.sum() for r in recs)),
        "放电量_kWh": float(sum(r.d.sum() for r in recs)),
        "期初储电量_kWh": float(recs[0].E0),
        "期末储电量_kWh": float(recs[-1].E[-1]),
        "调整提交次数": sum(r.n_submit for r in recs),
        "MILP求解次数": sum(r.n_solve for r in recs),
        # 框架第八节第 7 条：优化器的目标值（按预测价）与真实账单（按实际价）
        "预估费用_元": _sum(recs, "cost_total_hat"),
        # 框架 6.3 节：充放电与紧急补购各自发生在什么价位
        "充电加权均价_元每kWh": _wavg(recs, "c", "price_act"),
        "放电加权均价_元每kWh": _wavg(recs, "d", "price_act"),
        "紧急购电加权均价_元每kWh": _wavg(recs, "r", "price_act"),
    }


CHECK_KEYS_42 = ("信息边界", "计划冻结", "物理可行性", "状态累计", "费用一致性")
CHECK_KEYS_43 = ("信息边界", "调整权限", "物理可行性", "状态累计", "费用一致性")


def check_day42(rec: DayRecord42, tol: float = 1e-6) -> dict[str, list[str]]:
    """4-2 单日校验：框架第八节八项要求中可逐日核验的部分。

    返回的是**具体问题清单**而非布尔值，便于论文如实报告失败天数与原因。
    """
    p: dict[str, list[str]] = {k: [] for k in CHECK_KEYS_42}
    if rec.n == 0:
        return p
    if not np.isfinite(rec.price_hat).all() or (rec.price_hat <= 0).any():
        p["信息边界"].append("决策价格非正或非有限")
    if not np.isfinite(rec.n_risk).all():
        p["信息边界"].append("风险净负荷出现非有限值")
    # 计划冻结的可核验内容就是逐段电量平衡：执行层唯一的外部购电来源是 0:00
    # 定下的 g（加上日内紧急补购 r），日内不存在别的常规购电。平衡式为
    #     g + v + d + r = l + c + w
    # 即"来源 = 用途"：购电、光伏、放电、紧急购电 供给 负载、充电、弃电。
    # 注意 r 与 d 同为供给侧，符号为正——写成减号会把"缺口用储能与紧急购电
    # 共同补足"误判为不平衡。
    resid = (rec.g + rec.v_act + rec.d + rec.r
             - rec.c - rec.w - rec.l_act)
    if np.abs(resid).max() > 1e-5:
        p["计划冻结"].append(f"逐段电量平衡残差 {np.abs(resid).max():.3e} kWh")
    E = rec.E
    if E.min() < E_MIN - 1e-4 or E.max() > E_MAX + 1e-4:
        p["物理可行性"].append(f"储电量越界 [{E.min():.4f},{E.max():.4f}]")
    if (rec.r < -tol).any() or (rec.w < -tol).any():
        p["物理可行性"].append("紧急量或弃电量出现负值")
    if (rec.c > M_ENERGY + 1e-4).any() or (rec.d > M_ENERGY + 1e-4).any():
        p["物理可行性"].append("充放电功率超限")
    Ep = rec.E0
    for t in range(N):
        Ep = Ep + ETA * rec.c[t] - rec.d[t] / ETA
        if abs(Ep - rec.E[t]) > 1e-4:
            p["状态累计"].append(f"第 {t} 段储电量递推不一致")
            break
    cp = float(np.sum(rec.price_act * rec.g))
    ce = float(np.sum(COEF_EMG * rec.price_act * rec.r))
    if abs(cp - rec.cost_plan) > 1e-4 or abs(ce - rec.cost_emg) > 1e-4:
        p["费用一致性"].append("费用重算不符")
    return p


def check_day43(rec: DayRecord43, tol: float = 1e-6) -> dict[str, list[str]]:
    p: dict[str, list[str]] = {k: [] for k in CHECK_KEYS_43}
    if rec.n == 0:
        return p
    if not np.isfinite(rec.price_hat0).all() or (rec.price_hat0 <= 0).any():
        p["信息边界"].append("0:00 决策价格非正或非有限")
    # 调整权限：主口径下 x ≥ g⁰；且只有 S 内的交付块允许 x ≠ g⁰
    if rec.convention == "main" and (rec.x < rec.g0 - 1e-6).any():
        p["调整权限"].append("主口径出现调减")
    for hi, (a, b) in enumerate(BLOCK_BOUNDS):
        if np.abs(rec.x[a:b] - rec.g0[a:b]).max() <= 1e-6:
            continue
        if not (hi > 0 and RELEASE_HOURS[hi] in rec.S):
            p["调整权限"].append(f"第 {hi} 块发生未授权的调整")
    if float(np.max(np.abs(rec.x - rec.g0))) > tol and rec.S == ():
        p["调整权限"].append("未使用任何更新时刻却调整了购电量")
    # 平衡式同 check_day42，只是常规购电改用最终生效的 x：
    #     x + v + d + r = l + c + w
    resid = (rec.x + rec.v_act + rec.d + rec.r
             - rec.c - rec.w - rec.l_act)
    if np.abs(resid).max() > 1e-5:
        p["物理可行性"].append(f"逐段电量平衡残差 {np.abs(resid).max():.3e} kWh")
    E = rec.E
    if E.min() < E_MIN - 1e-4 or E.max() > E_MAX + 1e-4:
        p["物理可行性"].append(f"储电量越界 [{E.min():.4f},{E.max():.4f}]")
    if (rec.r < -tol).any() or (rec.w < -tol).any():
        p["物理可行性"].append("紧急量或弃电量出现负值")
    Ep = rec.E0
    for t in range(N):
        Ep = Ep + ETA * rec.c[t] - rec.d[t] / ETA
        if abs(Ep - rec.E[t]) > 1e-4:
            p["状态累计"].append(f"第 {t} 段储电量递推不一致")
            break
    # 费用一致性：全部系数乘**对应交付时段的实际电价**
    cp = float(np.sum(rec.price_act * rec.g0))
    up = np.maximum(rec.x - rec.g0, 0.0)
    ca = (float(np.sum(COEF_UP * rec.price_act * up))
          if rec.convention == "main" else
          float(np.sum(COEF_UP * rec.price_act * up
                       - COEF_DOWN * rec.price_act
                       * np.maximum(rec.g0 - rec.x, 0.0))))
    ce = float(np.sum(COEF_EMG * rec.price_act * rec.r))
    if (abs(cp - rec.cost_plan) > 1e-4 or abs(ca - rec.cost_adj) > 1e-4
            or abs(ce - rec.cost_emg) > 1e-4):
        p["费用一致性"].append("费用重算不符")
    return p


def check_all4(recs, kind: str) -> dict[str, int]:
    """返回每一类检查的**失败天数**；全为零才说明通过。"""
    fn = check_day42 if kind == "42" else check_day43
    keys = CHECK_KEYS_42 if kind == "42" else CHECK_KEYS_43
    out = {k: 0 for k in keys}
    for r in recs:
        for k, v in fn(r).items():
            if v:
                out[k] += 1
    return out


def validation_metrics4(recs, kind: str) -> dict:
    """数值口径的最坏情形指标，供论文以数字而非布尔值报告校验结果。

    布尔"通过"掩盖差异的量级；这里给出最大残差与储电量极值，读者可以据此
    判断约束是被满足到浮点精度，还是被近似满足。
    """
    e_lo = min(float(r.E.min()) for r in recs)
    e_hi = max(float(r.E.max()) for r in recs)
    out = {
        "全局最小储电量_kWh": e_lo,
        "全局最大储电量_kWh": e_hi,
        "储电下界余量_kWh": e_lo - E_MIN,
        "储电上界余量_kWh": E_MAX - e_hi,
        "跨日衔接最大偏差_kWh": _cross_day_gap(recs),
    }
    if kind == "42":
        out["逐段平衡最大残差_kWh"] = _max_abs(
            np.abs(r.g + r.v_act + r.d + r.r - r.c - r.w - r.l_act).max()
            for r in recs)
        out["计划费重算最大偏差_元"] = _max_abs(
            np.sum(r.price_act * r.g) - r.cost_plan for r in recs)
        out["调整费重算最大偏差_元"] = 0.0
    else:
        out["逐段平衡最大残差_kWh"] = _max_abs(
            np.abs(r.x + r.v_act + r.d + r.r - r.c - r.w - r.l_act).max()
            for r in recs)
        out["计划费重算最大偏差_元"] = _max_abs(
            np.sum(r.price_act * r.g0) - r.cost_plan for r in recs)
        out["调整费重算最大偏差_元"] = _max_abs(
            (np.sum(COEF_UP * r.price_act * np.maximum(r.x - r.g0, 0.0))
             - (0.0 if r.convention == "main" else
                np.sum(COEF_DOWN * r.price_act
                       * np.maximum(r.g0 - r.x, 0.0)))) - r.cost_adj
            for r in recs)
    out["紧急费重算最大偏差_元"] = _max_abs(
        np.sum(COEF_EMG * r.price_act * r.r) - r.cost_emg for r in recs)
    return out


def _max_abs(it) -> float:
    vals = [abs(float(v)) for v in it]
    return max(vals) if vals else 0.0


def _cross_day_gap(recs) -> float:
    """框架 8.5 节：每个分支独立保存实际状态，次日日初 = 前日日末。"""
    if len(recs) < 2:
        return 0.0
    return float(max(abs(recs[i + 1].E0 - recs[i].E[-1])
                     for i in range(len(recs) - 1)))


def emergency_events4(rec, eps: float = EMG_EPS) -> list[dict]:
    """合并相邻的紧急购电时段为一个事件，事件费用逐十分钟求和。

    框架 7.3 节明令：事件费用必须 Σ 5·p_actual·r 逐段累加，**不能**用事件
    起点价格、全天平均价格或预测价格乘整个事件电量。
    """
    r, price, out, i = rec.r, rec.price_act, [], 0
    while i < N:
        if r[i] > eps:
            j = i
            while j + 1 < N and r[j + 1] > eps:
                j += 1
            out.append({
                "时段": f"{interval_label(i).split('-')[0]}-"
                        f"{interval_label(j).split('-')[1]}",
                "电量_kWh": float(r[i:j + 1].sum()),
                "费用_元": float(np.sum(COEF_EMG * price[i:j + 1]
                                       * r[i:j + 1])),
            })
            i = j + 1
        else:
            i += 1
    return out


# ================================================================ 模块 7：导出
def summaries42(recs: list[DayRecord42]) -> list[dict]:
    out = []
    for r in recs:
        out.append({
            "日期": r.date, "计划量_kWh": float(r.g.sum()),
            "紧急电量_kWh": float(r.r.sum()), "计划费_元": r.cost_plan,
            "调整费_元": 0.0, "紧急费_元": r.cost_emg,
            "合计费用_元": r.cost_total, "弃电量_kWh": float(r.w.sum()),
            "期初储电量_kWh": float(r.E0), "期末储电量_kWh": float(r.E[-1]),
            "block_charge": [float(r.c[a:b].sum()) for a, b in BLOCKS],
            "block_discharge": [float(r.d[a:b].sum()) for a, b in BLOCKS],
            "events": emergency_events4(r),
            "plan_arr": r.g, "g0_arr": r.g, "x_arr": r.g,
        })
    return out


def summaries43(recs: list[DayRecord43]) -> list[dict]:
    out = []
    for r in recs:
        out.append({
            "日期": r.date, "计划量_kWh": r.g_initial,
            "初始计划量_kWh": r.g_initial, "最终常规量_kWh": r.g_effective,
            "上调量_kWh": r.up, "下调量_kWh": r.down,
            "紧急电量_kWh": r.g_emg, "计划费_元": r.cost_plan,
            "调整费_元": r.cost_adj, "紧急费_元": r.cost_emg,
            "合计费用_元": r.cost_total, "弃电量_kWh": float(r.w.sum()),
            "期初储电量_kWh": float(r.E0), "期末储电量_kWh": float(r.E[-1]),
            "调整提交次数": r.n_submit,
            "block_charge": [float(r.c[a:b].sum()) for a, b in BLOCKS],
            "block_discharge": [float(r.d[a:b].sum()) for a, b in BLOCKS],
            "events": emergency_events4(r),
            "plan_arr": r.g0, "g0_arr": r.g0, "x_arr": r.x,
        })
    return out


def _slot_labels() -> tuple[list[str], list[str]]:
    """时段起止标签，与问题二、三的明细表列名保持一致（便于交叉核对）。"""
    lab = [interval_label(t) for t in range(N)]
    return ([s.split("-")[0] for s in lab], [s.split("-")[1] for s in lab])


def detail_frame42(rec: DayRecord42) -> pd.DataFrame:
    a, b = _slot_labels()
    return pd.DataFrame({
        "日期": rec.date,
        "时段起": a,
        "时段止": b,
        "预测电价_元每kWh": rec.price_hat,
        "实际电价_元每kWh": rec.price_act,
        "实际负载_kWh": rec.l_act,
        "实际光伏_kWh": rec.v_act,
        "预测负载_kWh": rec.l_hat,
        "预测光伏_kWh": rec.v_hat,
        "净负荷预测_kWh": rec.n_hat,
        "价格加权风险余量_kWh": rec.margin,
        "风险净负荷_kWh": rec.n_risk,
        "参考储电量_kWh": rec.Ebar,
        "计划购电_kWh": rec.g,
        "实际充电_kWh": rec.c,
        "实际放电_kWh": rec.d,
        "紧急购电_kWh": rec.r,
        "弃电_kWh": rec.w,
        "储电量_kWh": rec.E,
        "计划费_元": rec.price_act * rec.g,
        "紧急费_元": COEF_EMG * rec.price_act * rec.r,
        # 同一计划量若按当时预测价计费（框架第八节第 7 条：目标与账单分开）
        "预估计划费_元": rec.price_hat * rec.g,
    })


def detail_frame43(rec: DayRecord43) -> pd.DataFrame:
    a, b = _slot_labels()
    return pd.DataFrame({
        "日期": rec.date,
        "时段起": a,
        "时段止": b,
        "0点预测电价_元每kWh": rec.price_hat0,
        "实际电价_元每kWh": rec.price_act,
        "实际负载_kWh": rec.l_act,
        "实际光伏_kWh": rec.v_act,
        "预测负载_kWh": rec.l_hat0,
        "预测光伏_kWh": rec.v_hat0,
        "净负荷预测_kWh": rec.n_hat0,
        "价格加权风险余量_kWh": rec.margin0,
        "风险净负荷_kWh": rec.n_risk0,
        "参考储电量_kWh": rec.Ebar,
        "初始计划购电_kWh": rec.g0,
        "最终购电_kWh": rec.x,
        "上调量_kWh": np.maximum(rec.x - rec.g0, 0.0),
        "下调量_kWh": np.maximum(rec.g0 - rec.x, 0.0),
        "实际充电_kWh": rec.c,
        "实际放电_kWh": rec.d,
        "紧急购电_kWh": rec.r,
        "弃电_kWh": rec.w,
        "储电量_kWh": rec.E,
        "计划费_元": rec.price_act * rec.g0,
        "紧急费_元": COEF_EMG * rec.price_act * rec.r,
        # 同一初始计划与最终量若都按 0:00 预测价计费（框架第八节第 7 条）
        "预估计划费_元": rec.price_hat0 * rec.g0
        + COEF_UP * rec.price_hat0 * np.maximum(rec.x - rec.g0, 0.0),
    })


# ---------------------------------------------------------------- Excel 写出
def _clear(ws) -> None:
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row)


def _write_slot_sheet(ws, arr: np.ndarray, summaries: list[dict],
                      total_key: str, fee_key: str) -> None:
    """144 列 × 每日一行的购电表，表头沿用论文统一的区间标签。"""
    _clear(ws)
    ws.cell(row=1, column=1, value="日期\\时间")
    for t in range(N):
        ws.cell(row=1, column=2 + t, value=interval_label(t))
    ws.cell(row=1, column=2 + N, value="全天购电量")
    ws.cell(row=1, column=3 + N, value="全天费用")
    for k, s in enumerate(summaries):
        ws.cell(row=2 + k, column=1, value=s["日期"])
        for t in range(N):
            ws.cell(row=2 + k, column=2 + t, value=float(arr[k, t]))
        ws.cell(row=2 + k, column=2 + N, value=s[total_key])
        ws.cell(row=2 + k, column=3 + N, value=s[fee_key])


def _write_block_sheet(wb, name: str, summaries: list[dict]) -> None:
    """6 个 4 小时区间的充放电量：每天 6 行，首行写日期与 0:00 储电量。"""
    ws = wb[name]
    _clear(ws)
    for c, v in enumerate(("日期", "时间段", "充电量", "放电量", "时刻",
                           "储电量"), start=1):
        ws.cell(row=1, column=c, value=v)
    for k, s in enumerate(summaries):
        for j, (a, b) in enumerate(BLOCKS):
            r = 2 + 6 * k + j
            if j == 0:
                ws.cell(row=r, column=1, value=s["日期"])
                ws.cell(row=r, column=5, value="0:00")
                ws.cell(row=r, column=6, value=round(s["期初储电量_kWh"], 4))
            ws.cell(row=r, column=2, value=block_label(a, b))
            ws.cell(row=r, column=3, value=round(s["block_charge"][j], 4))
            ws.cell(row=r, column=4, value=round(s["block_discharge"][j], 4))
            if j == 5:
                ws.cell(row=r, column=5, value="24:00")
                ws.cell(row=r, column=6, value=round(s["期末储电量_kWh"], 4))


def _write_emg_sheet(wb, name: str, summaries: list[dict]) -> None:
    """紧急购电事件表：同一天连续非零的十分钟时段合并为一个事件。"""
    ws = wb[name]
    _clear(ws)
    for c, v in enumerate(("日期", "购电时间段", "购电量"), start=1):
        ws.cell(row=1, column=c, value=v)
    row = 2
    for s in summaries:
        for j, ev in enumerate(s["events"]):
            ws.cell(row=row, column=1, value=s["日期"] if j == 0 else None)
            ws.cell(row=row, column=2, value=ev["时段"])
            ws.cell(row=row, column=3, value=round(ev["电量_kWh"], 4))
            row += 1


def _write_summary_sheet(wb, title: str, summaries: list[dict],
                         cols: list[tuple[str, str]]) -> None:
    if title in wb.sheetnames:
        del wb[title]
    ws = wb.create_sheet(title)
    for c, (hdr, _) in enumerate(cols, start=1):
        ws.cell(row=1, column=c, value=hdr)
    for k, s in enumerate(summaries):
        for c, (_, key) in enumerate(cols, start=1):
            v = s.get(key)
            ws.cell(row=2 + k, column=c,
                    value=round(v, 4) if isinstance(v, float) else v)


SUMMARY_COLS_42 = [
    ("日期", "日期"), ("计划购电量_kWh", "计划量_kWh"),
    ("紧急购电量_kWh", "紧急电量_kWh"), ("计划购电费_元", "计划费_元"),
    ("紧急购电费_元", "紧急费_元"), ("合计购电费_元", "合计费用_元"),
    ("弃电量_kWh", "弃电量_kWh"), ("0:00储电量_kWh", "期初储电量_kWh"),
    ("24:00储电量_kWh", "期末储电量_kWh"),
]

SUMMARY_COLS_43 = SUMMARY_COLS_42[:1] + [
    ("初始计划量_kWh", "初始计划量_kWh"), ("最终常规量_kWh", "最终常规量_kWh"),
    ("上调量_kWh", "上调量_kWh"), ("下调量_kWh", "下调量_kWh"),
    ("紧急购电量_kWh", "紧急电量_kWh"), ("计划费_元", "计划费_元"),
    ("调整费_元", "调整费_元"), ("紧急费_元", "紧急费_元"),
    ("合计费用_元", "合计费用_元"), ("弃电量_kWh", "弃电量_kWh"),
    ("0:00储电量_kWh", "期初储电量_kWh"),
    ("24:00储电量_kWh", "期末储电量_kWh"),
    ("调整提交次数", "调整提交次数"),
]


def _open_template(template: Path, path: Path):
    from openpyxl import Workbook, load_workbook
    path.parent.mkdir(parents=True, exist_ok=True)
    if template.exists():
        shutil.copyfile(template, path)
        return load_workbook(path)
    wb = Workbook()
    wb.remove(wb.active)
    for name in ("计划购电量", "调整购电量", "充放电量", "紧急购电量",
                 "全天汇总"):
        wb.create_sheet(name)
    return wb


def write_result42(summaries: list[dict], path: Path = OUT_XLSX42) -> None:
    """写 result4-2.xlsx：计划购电量 / 充放电量 / 紧急购电量 / 全天汇总。"""
    wb = _open_template(TEMPLATE42, path)
    _write_slot_sheet(wb["计划购电量"],
                      np.array([s["plan_arr"] for s in summaries]),
                      summaries, "计划量_kWh", "计划费_元")
    _write_block_sheet(wb, "充放电量", summaries)
    _write_emg_sheet(wb, "紧急购电量", summaries)
    _write_summary_sheet(wb, "全天汇总", summaries, SUMMARY_COLS_42)
    wb.save(path)


def write_result43(summaries: list[dict], path: Path = OUT_XLSX43) -> None:
    """写 result4-3.xlsx：计划购电量 / 调整购电量 / 充放电量 / 紧急购电量。

    框架 7.2 节：调整购电表填**每段最终生效的完整 x**，不是正负调整幅度；
    未调整的时段仍然填 x = g⁰，不能填零。
    """
    wb = _open_template(TEMPLATE43, path)
    _write_slot_sheet(wb["计划购电量"],
                      np.array([s["g0_arr"] for s in summaries]),
                      summaries, "初始计划量_kWh", "计划费_元")
    _write_slot_sheet(wb["调整购电量"],
                      np.array([s["x_arr"] for s in summaries]),
                      summaries, "最终常规量_kWh", "合计费用_元")
    _write_block_sheet(wb, "充放电量", summaries)
    _write_emg_sheet(wb, "紧急购电量", summaries)
    _write_summary_sheet(wb, "全天汇总", summaries, SUMMARY_COLS_43)
    wb.save(path)


def _daily_frame(summaries: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{k: v for k, v in s.items()
                          if not k.startswith("block_") and k != "events"
                          and not k.endswith("_arr")}
                         for s in summaries])


def write_side_files(recs42, recs43, sm42, sm43, result: dict) -> None:
    if recs42:
        pd.concat([detail_frame42(r) for r in recs42],
                  ignore_index=True).to_csv(OUT_DETAIL42, index=False)
        _daily_frame(sm42).to_csv(OUT_DAILY42, index=False)
    if recs43:
        pd.concat([detail_frame43(r) for r in recs43],
                  ignore_index=True).to_csv(OUT_DETAIL43, index=False)
        _daily_frame(sm43).to_csv(OUT_DAILY43, index=False)
    OUT_JSON4.write_text(json.dumps(result, ensure_ascii=False, indent=1,
                                    default=float), encoding="utf-8")


# ================================================================ 模块 8：组合比较
def combo_name(S: tuple) -> str:
    return "∅" if not S else "{" + ",".join(str(h) for h in S) + "}"


def all_combos() -> list[tuple]:
    out = []
    for k in range(len(ALL_S) + 1):
        out.extend(combinations(ALL_S, k))
    return out


def run_combo4(S: tuple, cal43: CalConfig3, book: PriceBook,
               LOAD, PV, fp, eps3, fo, weighted: bool = True,
               warmup: RiskParams | None = None) -> dict:
    """4-3 的一个预报使用组合在波动电价下的整年回放（框架 6.2 节）。

    **每个组合必须用"它自己的信息集"标定参数。** CalConfig3 带着一个 S 字段，
    calibrate43 是按 cal.S 回放标定窗口的；若只把 S 传给部署用的
    run_strategy43、却让标定继续用 cal43 原来的 S（默认 {6,12,18}），那么
    "仅 0:00"这类组合就会被强加上"全套预报"选出的参数，组合之间比出来的差额
    里混进了调参差异——这正是问题三 7.5 节明确禁止的做法。故此处先把 cal 的
    S 换成当前组合，再同时用于标定与部署。
    """
    cal = _replace(cal43, S=tuple(S))
    recs_all, cal_rows = run_strategy43(cal, book, "forecast", LOAD, PV,
                                        fp, eps3, fo, S=S, weighted=weighted,
                                        warmup=warmup)
    recs = recs_all[REPORT_START:REPORT_END]
    t = totals43(recs)
    t["使用预报"] = combo_name(S)
    t["标定记录数"] = len(cal_rows)
    t["校验失败天数"] = sum(1 for v in check_all4(recs, "43").values() if v > 0)
    return t


# ================================================================ 缓存
def _safe_tag(tag: str) -> str:
    return "".join("_" if ch in '<>:"/\\|?*：' else ch for ch in tag)


def save_cache(tag: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{_safe_tag(tag)}.json").write_text(
        json.dumps(payload, ensure_ascii=False, default=float),
        encoding="utf-8")


def _date_of(n: int) -> str:
    return str(np.datetime64("2025-01-01") + np.timedelta64(int(n), "D"))


# ================================================================ 主流程
def build_inputs(core: CorePreset = CORE_JIA) -> dict:
    """装载全部输入，并构造问题四新增的价格面。

    预测器超参数直接取自问题二内核（`core.load_fp`/`core.pv_fp`）：问题四的
    负载与光伏预测沿用问题二口径，不另立一套。
    """
    LOAD, PV, dates = load_attach2()
    PRICE = load_attach4()
    FIXED = load_attach1()["电价"].to_numpy(float)
    if FIXED.shape != (N,):
        raise ValueError(f"附件 1 电价长度异常：{FIXED.shape}")
    fp = load_attach3()
    fo = Forecaster(LOAD, PV, core.load_fp, core.pv_fp)
    eps = build_error_table(LOAD, PV, fo)
    eps3 = build_eps3(LOAD, PV, fp, fo)
    # 预测器超参数**只在预期间（1 月，第 1--30 天）选一次**，随后整段评价区间
    # 冻结。这样评价区间上的精度与费用才是样本外结果。
    pf_params, pf_select = select_forecast_params(PRICE, 1, REPORT_START)
    pf = PriceForecaster(PRICE, pf_params)
    return dict(LOAD=LOAD, PV=PV, dates=dates, PRICE=PRICE, FIXED=FIXED,
                fp=fp, fo=fo, eps=eps, eps3=eps3, pf=pf,
                pf_params=pf_params, pf_select=pf_select,
                book=PriceBook(PRICE, FIXED, pf))


def _replace(cal, **kw):
    """字段级复制：标定时要临时换掉网格/窗口，但不能改到主策略的配置。

    CalConfig / CalConfig3 是 frozen dataclass，不能 setattr；用
    dataclasses.replace 生成新实例，原配置对象保持不被修改。
    """
    return dataclasses.replace(cal, **kw)


def run_main_strategies(S: dict, cal42: CalConfig, cal43: CalConfig3,
                        weighted: bool, result: dict,
                        warmup42: RiskParams | None = None,
                        warmup43: RiskParams | None = None
                        ) -> tuple[list, list, list[dict], list[dict]]:
    """跑 4-2 与 4-3 的主策略，写两个交付 xlsx。"""
    recs42_all, cal42_rows = run_strategy42(
        cal42, S["book"], "forecast", S["LOAD"], S["PV"], S["eps"], S["fo"],
        weighted=weighted, verbose=True, warmup=warmup42)
    recs42 = recs42_all[REPORT_START:REPORT_END]
    sm42 = summaries42(recs42)
    result["4-2 主策略"] = totals42(recs42)
    result["4-2 校验失败天数"] = check_all4(recs42, "42")
    result["4-2 校验数值口径"] = validation_metrics4(recs42, "42")
    result["4-2 标定记录"] = cal42_rows
    write_result42(sm42)
    print(f"[4-2] 合计 {result['4-2 主策略']['合计费用_元']:,.2f} 元 "
          f"→ {OUT_XLSX42.name}", flush=True)

    recs43_all, cal43_rows = run_strategy43(
        cal43, S["book"], "forecast", S["LOAD"], S["PV"], S["fp"], S["eps3"],
        S["fo"], weighted=weighted, verbose=True, warmup=warmup43)
    recs43 = recs43_all[REPORT_START:REPORT_END]
    sm43 = summaries43(recs43)
    result["4-3 主策略"] = totals43(recs43)
    result["4-3 校验失败天数"] = check_all4(recs43, "43")
    result["4-3 校验数值口径"] = validation_metrics4(recs43, "43")
    result["4-3 标定记录"] = cal43_rows
    write_result43(sm43)
    print(f"[4-3] 合计 {result['4-3 主策略']['合计费用_元']:,.2f} 元 "
          f"→ {OUT_XLSX43.name}", flush=True)
    return recs42, recs43, sm42, sm43


def run_strategy_comparison(S: dict, cal42: CalConfig, cal43: CalConfig3,
                            weighted: bool,
                            warmup42: RiskParams | None = None,
                            warmup43: RiskParams | None = None) -> pd.DataFrame:
    """框架 6.1 节的三种策略对照：同一条实际价格路径，各自独立回放。

    ΔJ = J(固定电价参考) − J(波动电价预测)，即"适应波动电价值多少钱"。
    绝不用"旧策略在固定价下的账单"减"新策略在实际价下的账单"。

    三个价格模式共用同一组 1 月预热期参数：预热期的信息集与价格模式无关，
    固定住它，ΔJ 才只反映评价区间内价格信息之差，而不掺入预热期的漂移。
    """
    rows = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {m: ex.submit(run_strategy42, cal42, S["book"], m, S["LOAD"],
                             S["PV"], S["eps"], S["fo"], E_INIT, weighted,
                             False, warmup42)
                for m in PRICE_MODES}
        t42 = {m: totals42(f.result()[0][REPORT_START:REPORT_END])
               for m, f in futs.items()}
    for m in PRICE_MODES:
        rows.append({"分支": "4-2", "策略": MODE_LABEL[m], "模式": m, **t42[m]})
    d42 = t42["fixed"]["合计费用_元"] - t42["forecast"]["合计费用_元"]
    rows.append({"分支": "4-2", "策略": "ΔJ（固定电价 − 波动电价）", "模式": "",
                 "合计费用_元": d42,
                 "相对降幅": d42 / t42["fixed"]["合计费用_元"]})

    t43 = {}
    for m in PRICE_MODES:
        recs, _ = run_strategy43(cal43, S["book"], m, S["LOAD"], S["PV"],
                                 S["fp"], S["eps3"], S["fo"], weighted=weighted,
                                 warmup=warmup43)
        t43[m] = totals43(recs[REPORT_START:REPORT_END])
        rows.append({"分支": "4-3", "策略": MODE_LABEL[m], "模式": m, **t43[m]})
    d43 = t43["fixed"]["合计费用_元"] - t43["forecast"]["合计费用_元"]
    rows.append({"分支": "4-3", "策略": "ΔJ（固定电价 − 波动电价）", "模式": "",
                 "合计费用_元": d43,
                 "相对降幅": d43 / t43["fixed"]["合计费用_元"]})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="2026 CUMCM C题 问题四 求解（实时波动电价）")
    ap.add_argument("--quick", action="store_true",
                    help="缩短标定窗口，快速自检")
    ap.add_argument("--no-cal", action="store_true", help="跳过标定，用默认参数")
    ap.add_argument("--strategies", action="store_true",
                    help="额外跑三种价格模式对照（框架 6.1 节）")
    ap.add_argument("--sweep", action="store_true",
                    help="额外跑 4-3 的 8 种预报组合（框架 6.2 节）")
    ap.add_argument("--unweighted", action="store_true",
                    help="把价格加权分位数退回普通分位数（对照用）")
    ap.add_argument("--refund", action="store_true",
                    help="额外跑 4-3 的退款计费口径（框架 5.3 节敏感性）")
    ap.add_argument("--report-only", action="store_true",
                    help="只重算价格预测与风险统计，不跑寻优")
    ap.add_argument("--core", default="jia", choices=sorted(CORES),
                    help="问题二内核（4-2/4-3 随之重算）。jia（默认）=对照实现 "
                         "origin/q2-jia 最终版：1 月联合标定 (α,ρ,λ)、λ 整年冻结、"
                         "预测器写死、第 0 天走日 LP、min_samples=8；"
                         "legacy=本仓旧行为，仅用于复现历史数字")
    args = ap.parse_args()

    t_start = time.time()
    core = CORES[args.core]
    S = build_inputs(core)
    PRICE, weighted = S["PRICE"], not args.unweighted

    print("=" * 78)
    print(f"附件 4 载入：{PRICE.min():.4f}–{PRICE.max():.4f} 元/kWh，"
          f"均值 {PRICE.mean():.4f}，标准差 {PRICE.std():.4f}")
    print(f"  单一日内形状解释方差 {shape_ratio(PRICE):.1%}；"
          f"日中位峰谷比 {np.median(PRICE.max(axis=1) / PRICE.min(axis=1)):.2f}")
    print(f"价格预测器：{S['pf'].pp.label()}")

    result: dict = {
        "问题二内核": core.name,
        "价格数据": price_summary(PRICE),
        "价格预测器": S["pf"].pp.label(),
        "评价区间": f"2025-02-01 至 2025-12-31"
                    f"（{REPORT_END - REPORT_START} 天）",
        "风险口径": "价格加权分位数" if weighted else "普通分位数（对照）",
    }
    print(f"问题二内核：{core.name}"
          f"（{core.load_fp.label()}；{core.pv_fp.label()}；"
          f"min_samples={core.min_samples}；第 0 天冷启动）")

    # ---- 价格加权分位数定义的自检（论文公式 ↔ 实现一致性）
    wq_bad = test_weighted_quantile()
    result["风险_加权分位数自检"] = {"失败项": wq_bad, "通过": not wq_bad}
    print("\n价格加权分位数定义自检（下确界定义 ↔ 实现）：")
    if wq_bad:
        for b in wq_bad:
            print(f"  [失败] {b}")
    else:
        print("  等权退回 inverted_cdf、取值必为样本值、覆盖率单调 —— 通过")

    # ---- 价格结构分解：P = 附件1曲线 + 星期偏移（预测器的推导依据）
    ps = verify_price_structure(PRICE, S["FIXED"], S["pf"].pp)
    result["价格结构"] = ps
    print("\n价格结构分解 P = 附件1曲线 + 残差：")
    print(f"  附件1 年平均 {ps['断言1_年平均值_附件1']:.6f} 元/kWh，"
          f"附件4 年平均 {ps['断言1_年平均值_附件4']:.6f} 元/kWh"
          f"（逐段均值最大偏差 {ps['断言1_附件4逐段均值与附件1最大偏差']:.2e}）")
    print(f"  残差星期均值："
          + "  ".join(f"{k}={v:+.4f}"
                      for k, v in ps["断言3_残差星期均值_元每kWh"].items()))
    print(f"  周五六 {ps['断言3_周五六均值']:+.4f} vs 其余五天 "
          f"{ps['断言3_其余五天均值']:+.4f}，相差 "
          f"{ps['断言3_两水平差_元每kWh']:+.4f} 元/kWh"
          f"（{ps['断言3_相对均价']:.1%}），解释残差方差 "
          f"{ps['断言4_星期效应解释比例']:.1%}")
    print(f"  '同星期加权 == 附件1曲线 + 同星期残差加权' 最大残差 "
          f"{ps['断言2_同星期加权恒等式最大残差']:.2e}")

    # ---- 预测器与风险的诊断（不依赖寻优，先跑，供论文取数）
    cmp_df = price_forecast_compare(PRICE)
    cmp_df.to_csv(OUT_PFCAND, index=False)
    print("\n价格预测候选（正式区间 MAE，元/kWh）：")
    print(cmp_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    beta_df = price_beta_sweep(PRICE, S["pf"].pp)
    beta_df.to_csv(OUT_PBETA, index=False)
    print("\n日内对数修正系数 β 扫描（对剩余时段的 MAE）：")
    print(beta_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    result["价格预测精度"] = price_forecast_skill(PRICE, S["pf"])
    result["价格预测候选"] = cmp_df.to_dict("records")
    result["β扫描"] = beta_df.to_dict("records")

    # 选型窗口与选中的参数：预测器超参数只在 1 月（评价区间之外）选一次，
    # 上面 价格预测候选 / β扫描 两张表因此是**样本外**复核，不是选型依据。
    sel = S["pf_select"]
    result["预测器选型"] = sel
    print("\n预测器选型——只在 1 月预热期（第 1--30 天，评价区间之外）选一次，"
          "随后整段评价区间冻结：")
    print(f"  选中 {sel['选中的参数']}（1 月 MAE "
          f"{sel['最优平均绝对误差_元每kWh']:.4f} 元/kWh）")
    print("  正式区间上的 价格预测候选 / β扫描 两表是样本外复核，不参与选型。")
    corr = risk_price_correlation(S["eps"], PRICE)
    result["风险_价格协方差"] = corr
    rw = risk_weight_effect(S["eps"], PRICE)
    rw.to_csv(OUT_RWEIGHT, index=False)
    result["风险_加权对照"] = rw.to_dict("records")
    print("\n风险余量：价格加权 vs 普通分位数（正式区间抽样均值）")
    print(rw.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"  协方差检查：{corr['结论']}")
    print(f"    合并口径 corr={corr['合并相关系数']:+.4f}；"
          f"逐时段 corr 均值 {corr['逐时段相关系数均值']:+.3f}"
          f"（{corr['逐时段相关系数最小']:+.3f}~{corr['逐时段相关系数最大']:+.3f}，"
          f"为正占 {corr['逐时段相关为正的比例']:.1%}）")
    print(f"    电价高档 20% 误差 {corr['高价20%_误差均值_kW']:+.1f} kW "
          f"vs 低档 {corr['低价20%_误差均值_kW']:+.1f} kW，"
          f"两端差 {corr['两端误差均值差_kW']:+.1f} kW")

    if args.report_only:
        # 诊断部分很便宜（<1s），而寻优很贵。因此 --report-only 是**增量更新**：
        # 若已有求解结果，只覆盖诊断相关的键，保留主策略、标定、策略对照等
        # 需要长时间才能重算的内容。
        if OUT_JSON4.exists():
            try:
                old = json.loads(OUT_JSON4.read_text(encoding="utf-8"))
                old.update(result)
                result = old
                print(f"\n--report-only：已合并进既有 {OUT_JSON4.name}"
                      f"（保留 {sum(1 for k in old if k.startswith(('4-2', '4-3')))}"
                      f" 项求解结果）")
            except (json.JSONDecodeError, OSError) as e:
                print(f"  既有 {OUT_JSON4.name} 不可读（{e}），改为只写诊断")
        OUT_JSON4.write_text(json.dumps(result, ensure_ascii=False, indent=1,
                                        default=float), encoding="utf-8")
        print(f"--report-only 完成，用时 {time.time() - t_start:.1f}s")
        return

    # ---- 1 月联合标定：预热期参数在正式区间开始前离线选定，此后整年冻结。
    # 只用 1 月数据，第 0 天对所有候选相同；λ 选定后不再由滚动标定改动。
    warmup42 = warmup43 = None
    warmup42_rows: list[dict] = []
    warmup43_rows: list[dict] = []
    if core.warmup_grid():
        print("\n" + "=" * 78)
        print(f"1 月联合标定（内核 {core.name}，"
              f"{len(core.warmup_grid())} 组 (α,ρ,λ)，只用 1 月数据）")
        t_w = time.time()
        warmup42, warmup42_rows = select_warmup42(
            core, S["book"], "forecast", S["LOAD"], S["PV"], S["eps"], S["fo"],
            weighted)
        print(f"  [4-2] 选中 {warmup42.label()}，1 月费用 "
              f"{warmup42_rows[[r['选中'] for r in warmup42_rows].index(True)]['1月总费用_元']:,.2f} 元，"
              f"2 月 1 日储电量 "
              f"{warmup42_rows[[r['选中'] for r in warmup42_rows].index(True)]['2月1日储电量_kWh']:,.2f} kWh",
              flush=True)
        warmup43, warmup43_rows = select_warmup43(
            core, S["book"], "forecast", S["LOAD"], S["PV"], S["fp"],
            S["eps3"], S["fo"], "main", weighted)
        print(f"  [4-3] 选中 {warmup43.label()}，1 月费用 "
              f"{warmup43_rows[[r['选中'] for r in warmup43_rows].index(True)]['1月总费用_元']:,.2f} 元，"
              f"2 月 1 日储电量 "
              f"{warmup43_rows[[r['选中'] for r in warmup43_rows].index(True)]['2月1日储电量_kWh']:,.2f} kWh"
              f"（用时 {time.time() - t_w:.1f}s）", flush=True)
        result["4-2 1月联合标定"] = {"选中": warmup42.label(),
                                     "明细": warmup42_rows}
        result["4-3 1月联合标定"] = {"选中": warmup43.label(),
                                     "明细": warmup43_rows}
    else:
        print("\n内核 legacy：预热期参数沿用硬编码值，不做 1 月联合标定")

    base42 = CalConfig(min_samples=core.min_samples,
                       alphas=core.warmup_alphas or CalConfig.alphas,
                       rhos=core.warmup_rhos or CalConfig.rhos,
                       lams=(warmup42.lam,) if warmup42 else CalConfig.lams)
    base43 = CalConfig3(min_samples=core.min_samples,
                        alphas=core.warmup_alphas or CalConfig3.alphas,
                        rhos=core.warmup_rhos or CalConfig3.rhos,
                        lams=(warmup43.lam,) if warmup43 else CalConfig3.lams)
    cal42 = _replace(base42, window=10, every=42) if args.quick else base42
    cal43 = _replace(base43, window=10, every=42) if args.quick else base43
    if args.no_cal:
        # 网格塌缩成一个固定参数，等价于不做标定
        cal42 = _replace(cal42, alphas=(None,), rhos=(1.0,),
                         lams=(LAMBDA_DEFAULT,))
        cal43 = _replace(cal43, alphas=(None,), rhos=(1.0,),
                         lams=(LAMBDA_DEFAULT,))

    recs42, recs43, sm42, sm43 = run_main_strategies(S, cal42, cal43, weighted,
                                                     result, warmup42, warmup43)

    if args.strategies:
        print("\n" + "=" * 78)
        print("三种价格模式对照（同一实际价格路径，各自独立标定）")
        strat = run_strategy_comparison(S, cal42, cal43, weighted,
                                        warmup42, warmup43)
        strat.to_csv(OUT_STRAT4, index=False)
        result["策略对照"] = strat.to_dict("records")
        print(strat[["分支", "策略", "计划费_元", "调整费_元", "紧急费_元",
                     "合计费用_元"]].to_string(
            index=False, float_format=lambda v: f"{v:,.0f}"))

    if args.sweep:
        print("\n" + "=" * 78)
        print("4-3 八种预报组合（波动电价下重算，框架 6.2 节）")
        combos = all_combos()
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(run_combo4, c, cal43, S["book"], S["LOAD"],
                              S["PV"], S["fp"], S["eps3"], S["fo"], weighted,
                              warmup43)
                    for c in combos]
            rows = []
            for c, f in zip(combos, futs):
                row = f.result()
                rows.append(row)
                print(f"    {combo_name(c):>12s}  "
                      f"{row['合计费用_元']:>14,.0f} 元", flush=True)
        combos_df = pd.DataFrame(rows)
        combos_df.to_csv(OUT_COMBOS4, index=False)
        result["预报组合"] = combos_df.to_dict("records")

    # 先落盘主结果：退款口径只是敏感性，万一它出错也不该让几个小时的
    # 主策略结果付诸东流。
    write_side_files(recs42, recs43, sm42, sm43, result)
    print(f"\n主结果已写出，用时 {time.time() - t_start:.1f}s → {OUT_JSON4.name}")

    if args.refund:
        # 框架 5.3 节：调减部分原价是否退回是题面未说明的歧义，主口径取
        # "不退款、只追加"。这里把 4-3 在退款口径下**重新标定并重新回放**，
        # 作为独立敏感性报告——同一套模型、同一套执行规则，只换费用函数。
        print("\n" + "=" * 78)
        print("退款计费口径敏感性（4-3，独立标定与回放）")
        recs_rf, _ = run_strategy43(cal43, S["book"], "forecast", S["LOAD"],
                                    S["PV"], S["fp"], S["eps3"], S["fo"],
                                    convention="refund", weighted=weighted,
                                    verbose=True, warmup=warmup43)
        trf = totals43(recs_rf[REPORT_START:REPORT_END])
        trf["校验失败天数"] = check_all4(recs_rf[REPORT_START:REPORT_END], "43")
        # validation_metrics4 自己按 r.convention 选公式，无需额外传参
        trf["校验数值口径"] = validation_metrics4(
            recs_rf[REPORT_START:REPORT_END], "43")
        result["4-3 退款口径"] = trf
        print(f"[4-3 退款口径] 合计 {trf['合计费用_元']:,.2f} 元，"
              f"其中计划费 {trf['计划费_元']:,.2f}、"
              f"调整费 {trf['调整费_元']:,.2f}、"
              f"紧急费 {trf['紧急费_元']:,.2f}；"
              f"下调量 {trf['下调量_kWh']:,.2f} kWh")
        OUT_JSON4.write_text(json.dumps(result, ensure_ascii=False, indent=1,
                                        default=float), encoding="utf-8")

    print(f"\n全部完成，用时 {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
