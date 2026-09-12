# -*- coding: utf-8 -*-
"""附件 3 的时间口径判定：整点瞬时功率，还是小时平均功率？

附件 3 的每条记录给出"预报 1 小时"至"预报 24 小时"共 24 个功率值，但没有说明
它对应目标整点的瞬时功率，还是目标小时内的平均功率。这个口径决定了整点之间该
如何取值（分段线性插值 vs 整小时内取常值），必须先判定。

判定方法：把两种口径分别铺成十分钟功率序列，与附件 2 的实际光伏按不同时间平移
对齐，比较正式区间（2025-02-01 至 2025-12-31）内的全天平均绝对偏差（MAE，kW）。
偏差最小的口径即为正确口径；同时报告"前移一小时"作为反例，用以说明对齐方式确实
被区分开了。

输出：06_支撑材料/p3_alignment_scan.json

论文正文引用的三个数字即由本脚本产生。运行：
    python3 03_代码/p3_alignment_scan.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_microgrid as m  # noqa: E402
from p1_microgrid import N, TAU, interval_label  # noqa: E402
from p2_microgrid import (N_DAY, REPORT_END, REPORT_START,  # noqa: E402
                          load_attach2)
# 附件 3 的载入与版本索引在滚动脚本里（p3_microgrid 只负责单版本求解，
# 不导出 load_attach3）。此处必须从滚动脚本取，否则 AttributeError。
from p3_rolling_microgrid import load_attach3  # noqa: E402

OUT = m.OUT_DIR / "p3_alignment_scan.json"
RELEASE_HOURS = (0, 6, 12, 18)


def _interp(A: np.ndarray, minutes: float) -> float:
    """在整点功率序列 A[0..24] 上按分钟作分段线性插值。"""
    x = minutes / 60.0
    if x <= 0:
        return float(A[0])
    if x >= 24:
        return float(A[24])
    k = int(np.floor(x))
    theta = x - k
    return float((1 - theta) * A[k] + theta * A[k + 1])


def _step(A: np.ndarray, minutes: float) -> float:
    """小时平均口径：A[j] 是第 j 个小时（(j-1)*60 ~ j*60 分钟）内的平均功率。"""
    if minutes <= 0:
        return float(A[0])
    if minutes >= 24 * 60:
        return float(A[24])
    j = int(np.ceil(minutes / 60.0))
    return float(A[min(max(j, 1), 24)])


def scan() -> dict:
    LOAD, PV, dates = load_attach2()
    fp = load_attach3(PV)

    # load_attach2 返回的 (LOAD, PV) 单位已经是 kW（求解器用 PV * TAU 换算成
    # 十分钟电量），故这里直接就是十分钟平均功率，不要再除 TAU。
    pv_kw = PV

    variants = {
        "整点对齐（分段线性插值）": (_interp, 0),
        "前移一小时": (_interp, -60),
        "按小时平均（整小时内取常值）": (_step, 0),
    }
    acc = {k: [] for k in variants}
    per_release = {k: {h: [] for h in RELEASE_HOURS} for k in variants}

    for n in range(REPORT_START, min(REPORT_END, N_DAY)):
        for hi, rel_h in enumerate(RELEASE_HOURS):
            A = fp.F[hi, n, :]
            t0 = 36 * hi                       # 发布时刻之前的时段该版本不预测
            for t in range(t0, N):
                ra = t * 10.0 - 60.0 * rel_h   # 相对发布时刻的分钟数
                actual = pv_kw[n, t]
                if not np.isfinite(actual):
                    continue
                for name, (fn, shift) in variants.items():
                    if ra + shift < 0:
                        continue               # 平移后落到发布前，无定义
                    dev = abs(fn(A, ra + shift) - actual)
                    acc[name].append(dev)
                    per_release[name][rel_h].append(dev)

    rep = {}
    for name in variants:
        rep[name] = {
            "MAE_kW": float(np.mean(acc[name])),
            "样本数": int(len(acc[name])),
            "分版本MAE_kW": {
                f"{h}:00": round(float(np.mean(per_release[name][h])), 2)
                for h in RELEASE_HOURS},
        }

    best = min(rep, key=lambda k: rep[k]["MAE_kW"])
    return {
        "区间": f"{dates[REPORT_START]} 至 {dates[REPORT_END - 1]}",
        "各口径MAE_kW": {k: round(v["MAE_kW"], 2) for k, v in rep.items()},
        "分版本MAE_kW": {k: v["分版本MAE_kW"] for k, v in rep.items()},
        "判定": best,
        "明细": rep,
    }


def main() -> None:
    res = scan()
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"区间：{res['区间']}")
    print(f"{'口径':<28}{'MAE/kW':>10}")
    for k, v in res["各口径MAE_kW"].items():
        mark = "   <-- 最小，判定为该口径" if k == res["判定"] else ""
        print(f"{k:<28}{v:>10.2f}{mark}")
    print("\n分发布版本 MAE/kW：")
    for k, d in res["分版本MAE_kW"].items():
        print(f"  {k:<28}" + "  ".join(f"{h}:00={v:.2f}" for h, v in d.items()))
    print(f"\n判定：附件 3 为{res['判定']}")
    print(f"写入 {OUT}")


if __name__ == "__main__":
    main()
