# -*- coding: utf-8 -*-
r"""
问题二 日末储备惩罚 λ 的退化诊断（只读已有交付数据，不重跑仿真）

背景
----
日前 MILP 的目标是  min Σ p_t g_t + λ ξ,  ξ ≥ E_tar − Ē_144,  ξ ≥ 0。
当 λ = 0 时 ξ 在经济上完全自由：终端约束不再产生任何定价信号，
Ē_144 由求解器在最优面上任选，参考轨迹 Ē 因此**不再是"一条有终端价值的计划"**，
而是"当日最省钱的调度"。

本脚本量化完整的因果链，供论文如实交代机制：
  λ=0 → ξ ≡ E_tar − E_MIN 逐日恒定 → Ē 退化（贴上限/贴下限）
       → 储备线 R_t = E_MIN + ρ(Ē_t − E_MIN) 被抬高
       → 执行层在部分时段**结构性无法放电** → 转为紧急购电

--------------------------------------------------------------------------
**判据修正说明（务必注意）**
上一版把"被结构性禁止放电"定义为   E_{t-1} < R_t 且 d_t = 0 ，
但 d_t = 0 也可能只是因为该时段**根本不需要放电**（b_t ≥ 0，即
计划购电 + 实际光伏已覆盖实际负载）。这样统计会把"无需放电"混入"被禁放"，
**高估**了储备线的实际影响。

execute_day 的真实逻辑是（见 p2_microgrid.execute_day）：
    当 b_t < 0（有缺口）时，head = max(0, E_{t-1} − R_t)，d_t = min(−b_t, M, η·head)
    故**只有 b_t < 0 且 E_{t-1} ≤ R_t 的时段才真正被结构性禁止放电**。
本版据此重算，并保留旧口径的键以便与既有论文数字对照，两者都列出。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from p2_microgrid import (E_MAX, E_MIN, E_TAR, ETA, M_ENERGY, N, REPORT_END,
                          REPORT_START)

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "06_支撑材料" / "p2_detail.csv"
DAILY = ROOT / "06_支撑材料" / "p2_daily.csv"
ABLATION = ROOT / "06_支撑材料" / "p2_lambda_ablation.json"
OUT = ROOT / "06_支撑材料" / "p2_lambda_diag.json"

EDGE_TOL = 1.0          # 储电量是连续变量，1 kWh 以内视为"贴边"
HI_BUT_BLOCKED = 3000.0  # 诊断用：储电量仍高于该值却未能放电，说明"明明有电"
# p2_detail.csv 的量列只保留 6 位小数，故重建 d_t 至多只能吻合到舍入量级
# （b_t 由三个 6 位小数量相加减，误差上限约 1.5e-6；再经 min 与 η·head 传播）。
# 1e-4 kWh 相对 12000 kWh 的全量程是 8e-9，足以判"重建与实跑同源"。
RECON_TOL = 1e-4


def _ratio(a: float, b: float) -> float:
    """分组比值的统一出口：分母为 0 或无定义时返回 NaN，不抛异常、不造假。"""
    if not (np.isfinite(a) and np.isfinite(b)) or b <= 0:
        return float("nan")
    return float(a / b)


def parse_rho(params: str) -> float:
    """从 p2_daily.csv 的 params 串（如 'α=0.75, ρ=0.9, λ=0.00'）取当日 ρ。"""
    for part in params.replace("，", ",").split(","):
        part = part.strip()
        if part.startswith("ρ") or part.startswith("rho"):
            return float(part.split("=")[1])
    raise ValueError(f"无法从参数串解析 ρ：{params!r}")


def main() -> None:
    # 注意：控制台多按 GBK 编码，中文与希腊字母（α/ρ/ξ/η）都在 GBK 内，
    # 但 Ē（U+0112，拉丁扩展-A）不在，直接打印会抛 UnicodeEncodeError。
    # 故打印串一律用 ASCII 的 "Ebar" 指代参考轨迹，不改动全局 stdout 编码。
    df = pd.read_csv(DETAIL)
    # p2_detail.csv 只含正式区间（2025-02-01 ~ 2025-12-31）的逐时段明细，
    # 不再往前带 1 月，故直接从第 0 行起取整天，不能按 REPORT_START 偏移。
    n_day = df.shape[0] // N
    rep = df.iloc[:n_day * N]

    day = pd.read_csv(DAILY)
    # 按日期对齐取出逐日实际标定的 ρ（主运行 ρ 并非恒为 0.9，而是 8 次滚动标定
    # 的结果：0.9 / 0.5 / 0.8 都出现过）。硬编码单一 ρ 会算错储备线。
    rho_by_date = {str(r.date): parse_rho(str(r.params)) for r in day.itertuples()}
    rho_day = np.array([rho_by_date[d] for d in rep["日期"].astype(str)],
                       dtype=float)                       # 每个时段所属日的 ρ
    rho_used = np.unique(rho_day)
    # 报告区间内逐日 ρ 的取值分布（**按天计数**）。注意 rho_day 是逐时段的，
    # 对它直接 np.unique 得到的是时段数（×144），不能当作天数报出。
    day_rho = np.array([rho_by_date[str(dt)] for dt in
                        pd.unique(rep["日期"].astype(str))], dtype=float)
    rho_vals, rho_day_counts = np.unique(day_rho, return_counts=True)
    _, rho_slot_counts = np.unique(rho_day, return_counts=True)

    Ebar = rep["参考储电量_kWh"].to_numpy(float)
    g = rep["计划购电_kWh"].to_numpy(float)
    d = rep["实际放电_kWh"].to_numpy(float)
    r = rep["紧急购电_kWh"].to_numpy(float)
    l_act = rep["实际负载_kWh"].to_numpy(float)
    v_act = rep["实际光伏_kWh"].to_numpy(float)
    n_slot = Ebar.size

    # 时段初储电量 = 上一时段末；日首取该日 E0 列
    E0_col = rep["期初储电量_kWh"].to_numpy(float)
    starts = np.empty_like(d)
    starts[1:] = rep["期末储电量_kWh"].to_numpy(float)[:-1]
    starts[0::N] = E0_col[0::N]

    # execute_day 中的盈余 b_t = 计划购电 + 实际光伏 − 实际负载
    b = g + v_act - l_act
    needs_discharge = b < -1e-9

    R = E_MIN + rho_day * (Ebar - E_MIN)        # 逐日 ρ 构造的储备线

    # ---- 自校验：重建的放电量必须与实际执行一致，否则诊断不可信 ----
    head = np.maximum(0.0, starts - R)
    d_recon = np.where(needs_discharge,
                       np.minimum(np.minimum(-b, M_ENERGY), ETA * head), 0.0)
    recon_err = float(np.abs(d_recon - d).max())

    # 重建式取 min(-b, M, η·head)：只有当 η·head 真的成为**约束项**时，
    # 重建结果才携带 ρ 的信息。若该情形一次都没出现，则"重建吻合"只说明
    # b_t 对，不能证明 ρ 对。故须单独统计，否则自校验是空转。
    cap_energy = ETA * head
    head_binding = needs_discharge & (cap_energy < -b - 1e-9) & (cap_energy < M_ENERGY)
    n_head_binding = int(head_binding.sum())

    # ---- 反证：把 ρ 硬编码为 0.9（论文现用口径）会差多少 ----
    # 若本项偏差远大于 RECON_TOL，则说明"全区间 ρ=0.9"与实跑不符，
    # 据其算出的储备线占比不能对外引用。
    R_wrong = E_MIN + 0.9 * (Ebar - E_MIN)
    d_wrong = np.where(needs_discharge,
                       np.minimum(np.minimum(-b, M_ENERGY),
                                  ETA * np.maximum(0.0, starts - R_wrong)), 0.0)
    recon_err_fixed09 = float(np.abs(d_wrong - d).max())
    n_periods_rho_diff = int((np.abs(d_wrong - d) > RECON_TOL).sum())

    # ---- 两个口径要分开讲，它们回答的是不同问题 ----
    # (a) "站在储备线下"：E_{t-1} < R_t。此时 head = 0，d 必为 0——
    #     储备线**禁止**该时段放电（但该时段未必需要放电）。这是评审引用的口径。
    below = starts < R - 1e-6
    # (b) "真的被卡住"：既需要放电（b<0）又站在储备线下。
    #     只有这一口径才把缺口推给紧急购电，才对应真实费用。
    needs_and_below = needs_discharge & (starts <= R + 1e-6)
    # 仍有电却被禁放的（说明不是"没电可放"，而是"有电不让放"）
    blocked_high = needs_and_below & (starts > HI_BUT_BLOCKED)
    blocked_emg_kwh = float(r[needs_and_below].sum())

    # 数学上的必然：below ⟹ head=0 ⟹ d=0，故"站在线下"的时段必然未放电。
    # 论文若报出"低于 R 的占比"与"其中未放电的占比"两个**不等**的数，
    # 那只能是储备线用错了 ρ（见下），而不是执行层另有行为。
    below_implies_no_discharge = bool((below & (d > 1e-9)).sum() == 0)

    # ---- 机制分解 ----
    # 直接驱动"被拒"的量是储备线 R_t 的高低，而 R_t = E_MIN + ρ(Ē_t − E_MIN)
    # 随 Ē 水涨船高。故按 R_t 的水平分档看被拒率，比按 Ē 是否贴上限更能说明
    # 机制；Ē 贴上限只是 R 高的一种成因，两者都报。
    bar_at_ceiling = np.abs(Ebar - E_MAX) <= EDGE_TOL
    rate_if_ceiling = (float(needs_and_below[bar_at_ceiling].mean())
                       if bar_at_ceiling.any() else float("nan"))
    rate_if_not = (float(needs_and_below[~bar_at_ceiling].mean())
                   if (~bar_at_ceiling).any() else float("nan"))
    r_med = float(np.median(R))
    r_hi = R > r_med
    rate_r_hi = (float(needs_and_below[r_hi].mean())
                 if r_hi.any() else float("nan"))
    rate_r_lo = (float(needs_and_below[~r_hi].mean())
                 if (~r_hi).any() else float("nan"))

    diag = {
        "口径": {
            "数据源": "06_支撑材料/p2_detail.csv + p2_daily.csv（仅含正式区间）",
            "正式区间天数": int(n_day),
            "正式区间时段数": int(n_slot),
            "ρ_逐日实际取值": sorted(float(x) for x in rho_used),
            "ρ_各取值天数": {str(float(k)): int(v) for k, v in
                             zip(rho_vals, rho_day_counts)},
            "ρ_各取值时段数": {str(float(k)): int(v) for k, v in
                               zip(rho_vals, rho_slot_counts)},
            "ρ_说明": "按 p2_daily.csv 逐日实际标定结果构造储备线：每日的 ρ 取"
                      "该日 params 串中的标定值（见『ρ_各取值天数』），"
                      "**并非全区间恒为同一常数**。若自行按固定 ρ 重算，"
                      "与实跑不对应（见『反证』）",
            "贴边容差_kWh": EDGE_TOL,
            "储备线": "R_t = E_MIN + ρ_日(Ē_t − E_MIN)",
            "口径a_站在线下": "E_{t-1} < R_t（此时 head=0，放电被禁止；"
                             "但该时段未必需要放电）",
            "口径b_真的被卡住": "b_t < 0 且 E_{t-1} <= R_t（缺口的放电被禁止，"
                               "只能转紧急购电，对应真实费用）",
        },
        "重建自校验": {
            "重建放电量与实际最大偏差_kWh": recon_err,
            "容差_kWh": RECON_TOL,
            "通过": bool(recon_err < RECON_TOL),
            "储备线成为约束项的时段数": n_head_binding,
            "说明": "用 execute_day 的公式凭明细列重建 d_t，与实际执行逐位比对。"
                    "关键是『储备线成为约束项的时段数』必须为正——只有 η·head "
                    "真的卡住过放电，重建吻合才反过来证明逐日 ρ 用对了；"
                    "若该数为 0，则吻合只说明 b_t 对，不能证明 ρ 对",
        },
        "反证_论文现用的ρ=0.9口径": {
            "若全区间硬编码ρ为0.9的重建最大偏差_kWh": recon_err_fixed09,
            "因此判错口径的时段数": n_periods_rho_diff,
            "结论": ("偏差远超舍入量级，说明『全区间 ρ=0.9』与实跑不符"
                     if recon_err_fixed09 > RECON_TOL else
                     "偏差在舍入量级内，硬编码 0.9 与逐日 ρ 无实质差别"),
            "影响": "论文附录报出的『低于 R 占 9.13%、其中 7.81% 未能放电』"
                    "即出自该口径，两个数不该不等——因为 E_{t-1}<R_t 时 "
                    "head=0，放电必然为 0；出现 9.13%≠7.81% 正是储备线"
                    "用错 ρ 留下的痕迹",
        },
        "逻辑必然性检查": {
            "站在线下却仍在放电的时段数": int((below & (d > 1e-9)).sum()),
            "通过": below_implies_no_discharge,
            "说明": "E_{t-1} < R_t ⟹ head=0 ⟹ d_t=0 是 execute_day 的恒等推论，"
                    "若不为 0 则说明储备线 ρ 与实跑不一致",
        },
        "参考储电量_退化": {
            "贴上限_E_MAX_时段占比": float(bar_at_ceiling.mean()),
            "贴下限_E_MIN_时段占比": float((np.abs(Ebar - E_MIN) <= EDGE_TOL).mean()),
            "Ē_均值_kWh": float(Ebar.mean()),
            "Ē_标准差_kWh": float(Ebar.std()),
            "Ē_日末均值_kWh": float(Ebar.reshape(-1, N)[:, -1].mean()),
            "Ē_日末贴下限占比": float(
                (np.abs(Ebar.reshape(-1, N)[:, -1] - E_MIN) <= EDGE_TOL).mean()),
            "ξ_逐日恒定值_kWh": float(E_TAR - E_MIN),
        },
        "储备线影响_口径a_站在线下": {
            "E_低于R_时段占比": float(below.mean()),
            "其中储电量仍高于3000_时段占比": float((below & (starts > HI_BUT_BLOCKED)).mean()),
            "含义": "该时段头寸为 0，一旦需要放电必然被拒；但其中多数时段"
                    "本来就不需要放电，故此占比**不等于**真实影响",
        },
        "储备线影响_口径b_真的被卡住": {
            "需要放电的时段占比": float(needs_discharge.mean()),
            "放电被结构性拒绝_时段占比": float(needs_and_below.mean()),
            "占需要放电时段的比例": float(
                needs_and_below.sum() / max(1, needs_discharge.sum())),
            "其中储电量仍高于3000_时段占比": float(blocked_high.mean()),
            "被拒时段的紧急购电量_kWh": blocked_emg_kwh,
            "占全部紧急购电量比例": float(blocked_emg_kwh / max(1e-9, r.sum())),
            "含义": "只有这一口径对应真实费用：缺口因禁放而全部转为紧急购电",
        },
        "机制分解_储备线为何卡住放电": {
            "按R水平分档": {
                "R中位数_kWh": r_med,
                "R高于中位数时段的放电被拒率": rate_r_hi,
                "R低于中位数时段的放电被拒率": rate_r_lo,
                "倍数": _ratio(rate_r_hi, rate_r_lo),
            },
            "按Ē是否贴上限分档": {
                "Ē贴上限时段的放电被拒率": rate_if_ceiling,
                "Ē未贴上限时段的放电被拒率": rate_if_not,
                "倍数": _ratio(rate_if_ceiling, rate_if_not),
            },
            "R_在Ē贴上限时的值_kWh": float(E_MIN + max(rho_used) * (E_MAX - E_MIN)),
            "说明": "R_t = E_MIN + ρ(Ē_t − E_MIN) 随 Ē 水涨船高：Ē 贴上限且 "
                    "ρ=0.9 时 R_t 达 9840 kWh，执行层须先守住该线才准放电。"
                    "按 R 水平分档的倍数即该机制的强度；Ē 贴上限只是 R 高的"
                    "一种成因，未必是唯一的，故两个分档都列出、不合并解释",
        },
        "实际储电量": {
            "E_均值_kWh": float(rep["期末储电量_kWh"].mean()),
            "E_贴下限占比": float(
                (np.abs(rep["期末储电量_kWh"].to_numpy(float) - E_MIN)
                 <= EDGE_TOL).mean()),
        },
        "规模参照": {
            "紧急购电量_kWh": float(r.sum()),
            "实际放电量_kWh": float(d.sum()),
            "计划购电量_kWh": float(g.sum()),
        },
    }

    diag["λ敏感性_提高λ能否治退化"] = _lambda_sweep()

    OUT.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- 打印
    print("=" * 78)
    print(f"λ=0 退化诊断（正式区间 {n_day} 天，逐日实际 ρ，"
          f"取值 {[round(x, 2) for x in rho_used]}）")
    print("=" * 78)
    print("ρ 逐日取值分布：" + "  ".join(
        f"ρ={k:.1f} 共 {v} 天" for k, v in
        zip(rho_vals, rho_day_counts)))
    v = diag["重建自校验"]
    print(f"重建自校验：重建 d 与实际最大偏差 {v['重建放电量与实际最大偏差_kWh']:.3e} kWh"
          f"  —— {'通过' if v['通过'] else '未通过，诊断不可信！'}")
    print(f"            储备线真正卡住放电的时段数 {v['储备线成为约束项的时段数']}"
          f"  （须 > 0，否则 ρ 未被数据检验）")
    lv = diag["逻辑必然性检查"]
    print(f"            站在线下却仍在放电的时段数 {lv['站在线下却仍在放电的时段数']}"
          f"  —— {'通过' if lv['通过'] else '不通过'}")
    w = diag["反证_论文现用的ρ=0.9口径"]
    print(f"反证：若全区间按 ρ=0.9 重建，最大偏差 "
          f"{w['若全区间硬编码ρ为0.9的重建最大偏差_kWh']:.3e} kWh，"
          f"判错 {w['因此判错口径的时段数']} 个时段")
    print("-" * 78)
    d1 = diag["参考储电量_退化"]
    print(f"参考轨迹 Ebar 贴上限 {E_MAX:.0f} : {d1['贴上限_E_MAX_时段占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ebar 贴下限 {E_MIN:.0f}  : {d1['贴下限_E_MIN_时段占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ebar 日末贴下限      : {d1['Ē_日末贴下限占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ebar 日末均值        : {d1['Ē_日末均值_kWh']:9.2f} kWh")
    print(f"ξ 逐日恒定值                 : {d1['ξ_逐日恒定值_kWh']:9.2f} kWh"
          f"   (= E_tar - E_min)")
    print("-" * 78)
    da = diag["储备线影响_口径a_站在线下"]
    print(f"口径a 站在储备线下           : {da['E_低于R_时段占比'] * 100:6.2f}%"
          f"   （放电必被拒，但多数时段本就不需要放电）")
    print(f"      其中 E>3000 仍有电      : {da['其中储电量仍高于3000_时段占比'] * 100:6.2f}%")
    db = diag["储备线影响_口径b_真的被卡住"]
    print(f"口径b 真的被卡住             : {db['放电被结构性拒绝_时段占比'] * 100:6.2f}%"
          f"   （占需要放电时段的 {db['占需要放电时段的比例'] * 100:.2f}%）"
          f"  ← 对应真实费用")
    print(f"      其中 E>3000 仍有电      : {db['其中储电量仍高于3000_时段占比'] * 100:6.2f}%")
    print(f"      被拒时段紧急购电        : {db['被拒时段的紧急购电量_kWh']:,.0f} kWh"
          f"（占全部紧急购电 {db['占全部紧急购电量比例'] * 100:.2f}%）")
    print("-" * 78)
    dm = diag["机制分解_储备线为何卡住放电"]
    d_r = dm["按R水平分档"]
    print(f"放电被拒率（按储备线 R 水平分档，R 中位数 {d_r['R中位数_kWh']:,.0f} kWh）：")
    print(f"    R 高于中位数 {d_r['R高于中位数时段的放电被拒率'] * 100:5.2f}%"
          f"  vs R 低于中位数 {d_r['R低于中位数时段的放电被拒率'] * 100:5.2f}%"
          f"  → 倍数 {d_r['倍数']:.2f}×")
    d_b = dm["按Ē是否贴上限分档"]
    print(f"    （对照）Ebar 贴上限 {d_b['Ē贴上限时段的放电被拒率'] * 100:5.2f}%"
          f"  vs 其余 {d_b['Ē未贴上限时段的放电被拒率'] * 100:5.2f}%"
          f"  → 倍数 {d_b['倍数']:.2f}×")
    print(f"    Ebar 贴上限且 ρ=0.9 时 R_t 高达 "
          f"{dm['R_在Ē贴上限时的值_kWh']:,.0f} kWh")
    print("-" * 78)
    ls = diag["λ敏感性_提高λ能否治退化"]
    print("提高 λ 能否治退化（读自消融，滚动标定关闭以隔离 λ）：")
    # 表头里的 'Ebar…' 是**被打印出来的值**（不是字典键），故不能写成 Ē：
    # Ē（U+0112）不在 GBK 内，中文控制台重定向输出时会中断整个脚本。
    # 列宽按显示宽度对齐：'Ebar日末'=8，'Ebar上限%'/'Ebar下限%'=9。
    print(f"  {'α':>4} {'ρ':>4} {'λ':>5} {'费用/元':>14} {'Ebar日末':>8} "
          f"{'Ebar上限%':>10} {'Ebar下限%':>10} {'禁放%':>7}")
    for row in ls["明细"]:
        print(f"  {row['α']:>4} {row['ρ']:>4} {row['λ']:>5} {row['总费用_元']:>14,.0f} "
              f"{row['Ē日末均值_kWh']:>8,.0f} {row['Ē贴上限占比'] * 100:>10.2f} "
              f"{row['Ē贴下限占比'] * 100:>10.2f} {row['禁放占比'] * 100:>7.2f}")
    print()
    for k in ls["关键事实"]:
        print(f"  · {k}")
    print(f"\n已写出 {OUT.relative_to(ROOT)}")


def _lambda_sweep() -> dict:
    """从消融结果提取 λ 扫描下的因果链，判断提高 λ 能否治退化。"""
    if not ABLATION.exists():
        return {"说明": "未找到 p2_lambda_ablation.json，跳过"}
    ab = json.loads(ABLATION.read_text(encoding="utf-8"))
    rows = []
    for a in ab.get("臂", []):
        r = a.get("报告区间", {})
        t = r.get("参考轨迹", {})
        s = r.get("储备线", {})
        rows.append({
            "α": a.get("α"), "ρ": a.get("ρ"), "λ": a.get("λ"),
            "总费用_元": r.get("总费用_元"),
            "Ē日末均值_kWh": t.get("日末均值_kWh"),
            "Ē贴上限占比": t.get("全时段贴上限占比"),
            "Ē贴下限占比": t.get("全时段贴下限占比"),
            "站在线下占比": s.get("E_低于R_时段占比"),
            "禁放占比": s.get("放电被结构性拒绝_时段占比"),
        })
    # 消融 JSON 若由旧版脚本产出，会缺少「放电被结构性拒绝_时段占比」。此时
    # 不静默降级也不抛 TypeError，而是显式告知需重跑哪一个脚本。
    required = ("总费用_元", "Ē日末均值_kWh", "Ē贴上限占比", "禁放占比")
    stale = [i for i, r in enumerate(rows)
             if any(r[k] is None for k in required)]
    if stale:
        return {"说明": "p2_lambda_ablation.json 缺少新判据字段，需重跑 "
                        "`python p2_lambda_ablation.py` 后再运行本脚本",
                "缺失臂数": len(stale), "明细": rows, "关键事实": []}

    rows.sort(key=lambda x: (x["α"] or 0, x["ρ"] or 0, x["λ"] or 0))

    facts = []
    for α in sorted({r["α"] for r in rows}):
        for ρ in sorted({r["ρ"] for r in rows if r["α"] == α}):
            grp = [r for r in rows if r["α"] == α and r["ρ"] == ρ]
            lo = [r for r in grp if r["λ"] == 0.0]
            hi = [r for r in grp if r["λ"] and r["λ"] >= 0.5]
            if not lo or not hi:
                continue
            lo, hi = lo[0], hi[0]
            facts.append(
                f"α={α}, ρ={ρ}：λ 由 0 提到 {hi['λ']}，Ē 日末 "
                f"{lo['Ē日末均值_kWh']:,.0f} → {hi['Ē日末均值_kWh']:,.0f} kWh"
                f"（已修复），但贴上限占比 "
                f"{lo['Ē贴上限占比'] * 100:.2f}% → {hi['Ē贴上限占比'] * 100:.2f}%"
                f"（几乎不变），禁放占比 "
                f"{lo['禁放占比'] * 100:.2f}% → {hi['禁放占比'] * 100:.2f}%"
                f"（仅小幅下降）；费用变化 "
                f"{(hi['总费用_元'] - lo['总费用_元']) / lo['总费用_元'] * 100:+.3f}%")
    # 结论从数据推，不写死任何数字——否则换了判据就会与明细自相矛盾。
    pairs = []
    for α in sorted({r["α"] for r in rows}):
        for ρ in sorted({r["ρ"] for r in rows if r["α"] == α}):
            grp = [r for r in rows if r["α"] == α and r["ρ"] == ρ]
            lo = [r for r in grp if r["λ"] == 0.0]
            hi = [r for r in grp if r["λ"] and r["λ"] >= 0.5]
            if lo and hi:
                pairs.append((lo[0], max(hi, key=lambda x: x["λ"])))
    if pairs:
        ceil_lo = min(p[0]["Ē贴上限占比"] for p in pairs)
        ceil_hi = max(p[1]["Ē贴上限占比"] for p in pairs)
        blk_lo = min(p[0]["禁放占比"] for p in pairs)
        blk_hi = max(p[1]["禁放占比"] for p in pairs)
        end_lo = min(p[0]["Ē日末均值_kWh"] for p in pairs)
        end_hi = max(p[1]["Ē日末均值_kWh"] for p in pairs)
        facts.append(
            f"结论：提高 λ 把 Ebar 的**日末值**从 {end_lo:,.0f} 修复到 "
            f"{end_hi:,.0f} kWh，但 Ebar 贴上限的时段占比在 "
            f"{ceil_lo * 100:.2f}%~{ceil_hi * 100:.2f}% 之间几乎不动"
            f"（与 λ 无关），执行层的结构性禁放也只从 {blk_lo * 100:.2f}% 变到 "
            f"{blk_hi * 100:.2f}%。故 λ=0 的后果**不止**是日末储备值："
            f"论文若称其『不影响执行层』，与数据不符。")
    return {"说明": "读自 06_支撑材料/p2_lambda_ablation.json（滚动标定关闭，"
                    "单一 λ 变量）", "明细": rows, "关键事实": facts}


if __name__ == "__main__":
    main()
