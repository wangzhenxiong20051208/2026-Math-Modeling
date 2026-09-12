# -*- coding: utf-8 -*-
r"""
问题二 日末储备惩罚 λ 的退化诊断（只读已有交付数据，不重跑仿真）

背景
----
日前 MILP 的目标是  min Σ p_t g_t + λ ξ,  ξ ≥ E_tar − Ē_144,  ξ ≥ 0。
当 λ = 0 时 ξ 在经济上完全自由：终端约束不再产生任何定价信号，
Ē_144 由求解器在最优面上任选，参考轨迹 Ē 因此**不再是"一条有终端价值的计划"**，
而是"当日最省钱的调度"。

本脚本从 06_支撑材料/p2_detail.csv 直接量化三件事：
  1. Ē 贴到上/下限的时段占比（退化程度）
  2. 实际储电量 E 低于储备线 R_t 的时段占比（执行层被结构性禁止放电的比例）
  3. R_t 实际起作用的比例（即"若把 R_t 降到 E_MIN 会改变执行的时段"）

输出 JSON 供论文引用。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from p2_microgrid import E_MIN, E_MAX, E_TAR, N, REPORT_START, REPORT_END

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "06_支撑材料" / "p2_detail.csv"
OUT = ROOT / "06_支撑材料" / "p2_lambda_diag.json"

# 判定"贴上下限"的容差：储电量是连续变量，取 1 kWh 以内视为贴边
EDGE_TOL = 1.0
# 主策略在 8 次滚动标定中取到的 ρ 分布（论文表 tab:p2-calib）
RHO_MAIN = 0.9


def main() -> None:
    df = pd.read_csv(DETAIL)
    # p2_detail.csv 本身只含正式区间（2025-02-01 ~ 2025-12-31）的逐时段明细，
    # 不再往前带 1 月，故直接从第 0 行起取整天，不能按 REPORT_START 偏移——
    # 之前的 iloc[31*144 : 365*144] 会在 334 天的表上截成 303 天。
    n_day = df.shape[0] // N
    rep = df.iloc[:n_day * N]

    Ebar = rep["参考储电量_kWh"].to_numpy(float)
    E = rep["期末储电量_kWh"].to_numpy(float)
    g = rep["计划购电_kWh"].to_numpy(float)
    d = rep["实际放电_kWh"].to_numpy(float)
    r = rep["紧急购电_kWh"].to_numpy(float)
    n_slot = Ebar.size

    # 储备线口径与 p2_microgrid.execute_day 一致：R_t = E_MIN + ρ(Ē_t − E_MIN)
    # execute_day 用**时段初**储电量 E_{t-1} 与 R_t 比较，此处用期末值最近似地
    # 前移一格重建：starts[t] = E[t-1]，starts[0] 由当日 E0 列给出。
    E0_col = rep["期初储电量_kWh"].to_numpy(float)
    starts = np.empty_like(E)
    starts[1:] = E[:-1]                 # 时段初 = 上一时段末
    starts[0::N] = E0_col[0::N]         # 日首例外，取该日 E0

    R = E_MIN + RHO_MAIN * (Ebar - E_MIN)

    below = starts < R - 1e-6                     # 实际储能已在储备线之下
    blocked_discharge = below & (d <= 1e-9)       # 且在需要放电的时段没能放电
    high_but_blocked = below & (starts > 3000.0)  # 明明有电却被禁放

    diag = {
        "口径": {
            "数据源": "06_支撑材料/p2_detail.csv（仅含正式区间）",
            "正式区间天数": int(n_day),
            "正式区间时段数": int(n_slot),
            "ρ": RHO_MAIN,
            "贴边容差_kWh": EDGE_TOL,
            "储备线": "R_t = E_MIN + ρ(Ē_t − E_MIN)",
        },
        "参考储电量_退化": {
            "贴上限_E_MAX_时段占比": float((np.abs(Ebar - E_MAX) <= EDGE_TOL).mean()),
            "贴下限_E_MIN_时段占比": float((np.abs(Ebar - E_MIN) <= EDGE_TOL).mean()),
            "Ē_均值_kWh": float(Ebar.mean()),
            "Ē_标准差_kWh": float(Ebar.std()),
            "Ē_日末均值_kWh": float(Ebar.reshape(-1, N)[:, -1].mean()),
            "Ē_日末贴下限占比": float(
                (np.abs(Ebar.reshape(-1, N)[:, -1] - E_MIN) <= EDGE_TOL).mean()),
        },
        "实际储电量_相对储备线": {
            "E_低于R_时段占比": float(below.mean()),
            "E_低于R_且未放电_时段占比": float(blocked_discharge.mean()),
            "E_高于3000却仍被禁放_时段占比": float(high_but_blocked.mean()),
            "E_均值_kWh": float(E.mean()),
            "E_贴下限占比": float((np.abs(E - E_MIN) <= EDGE_TOL).mean()),
        },
        "规模参照": {
            "紧急购电量_kWh": float(r.sum()),
            "实际放电量_kWh": float(d.sum()),
            "计划购电量_kWh": float(g.sum()),
        },
    }

    OUT.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    print(f"λ=0 退化诊断（正式区间 2025-02-01 ~ 2025-12-31，{n_day} 天，ρ=0.9）")
    print("=" * 70)
    d1 = diag["参考储电量_退化"]
    print(f"参考轨迹 Ē 贴上限 {E_MAX:.0f} : {d1['贴上限_E_MAX_时段占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ē 贴下限 {E_MIN:.0f}  : {d1['贴下限_E_MIN_时段占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ē 日末贴下限        : {d1['Ē_日末贴下限占比'] * 100:6.2f}%")
    print(f"参考轨迹 Ē 日末均值          : {d1['Ē_日末均值_kWh']:9.2f} kWh"
          f"   (目标 E_TAR = {E_TAR:.0f})")
    print(f"参考轨迹 Ē 均值 / 标准差     : {d1['Ē_均值_kWh']:9.2f} / {d1['Ē_标准差_kWh']:.2f} kWh")
    print("-" * 70)
    d2 = diag["实际储电量_相对储备线"]
    print(f"实际 E 低于 R_t 的时段       : {d2['E_低于R_时段占比'] * 100:6.2f}%")
    print(f"其中未能放电（被结构性禁止） : {d2['E_低于R_且未放电_时段占比'] * 100:6.2f}%")
    print(f"其中 E>3000 仍被禁放         : {d2['E_高于3000却仍被禁放_时段占比'] * 100:6.2f}%")
    print(f"实际 E 均值 / 贴下限占比     : {d2['E_均值_kWh']:9.2f} kWh / "
          f"{d2['E_贴下限占比'] * 100:.2f}%")
    print("-" * 70)
    d3 = diag["规模参照"]
    print(f"紧急购电 {d3['紧急购电量_kWh']:,.0f} kWh   "
          f"实际放电 {d3['实际放电量_kWh']:,.0f} kWh   "
          f"计划购电 {d3['计划购电量_kWh']:,.0f} kWh")
    print(f"\n已写出 {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
