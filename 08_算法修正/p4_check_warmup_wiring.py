# -*- coding: utf-8 -*-
r"""D3 接线自检：验证 run_strategy_comparison 是否按论文「各自独立标定」接线。

用 monkeypatch 把标定/回放替换成记录桩，便宜的检查：
  · independent_warmup=True  → select_warmup42/43 各被调用 3 次（每个 mode 一次），
    且每个 mode 收到的 warmup 是它自己那份；
  · independent_warmup=False → 两者各调用 0 次，三个 mode 共用同一份。
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p4_microgrid as M  # noqa

calls = {"sel42": [], "sel43": [], "run42": [], "run43": []}


def fake_sel42(core, book, mode, *a, **k):
    calls["sel42"].append(mode)
    return M.RiskParams(alpha=0.8, rho=1.0, lam=0.0 + len(mode) * 0.01), []


def fake_sel43(core, book, mode, *a, **k):
    calls["sel43"].append(mode)
    return M.RiskParams(alpha=0.7, rho=1.0, lam=0.0 + len(mode) * 0.01), []


class _Rec:
    pass


def fake_run42(cal, book, mode, *a, **k):
    w = k.get("warmup", a[7] if len(a) > 7 else None)   # warmup 是第 11 个位置参数
    calls["run42"].append((mode, None if w is None else round(w.lam, 4)))
    return ([_Rec() for _ in range(M.REPORT_END)], None)


def fake_run43(cal, book, mode, *a, **k):
    w = k.get("warmup")
    calls["run43"].append((mode, None if w is None else round(w.lam, 4)))
    return ([_Rec() for _ in range(M.REPORT_END)], None)


# 桩掉 totals 与线程池结果解析
M.select_warmup42 = fake_sel42
M.select_warmup43 = fake_sel43
M.run_strategy42 = fake_run42
M.run_strategy43 = fake_run43
M.totals42 = lambda recs: {"计划费_元": 0, "调整费_元": 0, "紧急费_元": 0, "合计费用_元": 1.0}
M.totals43 = lambda recs: {"计划费_元": 0, "调整费_元": 0, "紧急费_元": 0, "合计费用_元": 1.0}

S = {"book": None, "LOAD": np.zeros((M.N_DAY, M.N)), "PV": np.zeros((M.N_DAY, M.N)),
     "eps": None, "eps3": None, "fo": None, "fp": None}
core = M.CORES["jia"]
shared = M.RiskParams(alpha=0.9, rho=1.0, lam=0.123)


def clear():
    for k in calls:
        calls[k].clear()


print("== independent_warmup=True ==")
clear()
M.run_strategy_comparison(S, None, None, True, shared, shared, core, True)
print("  select42 收到 mode:", calls["sel42"])
print("  select43 收到 mode:", calls["sel43"])
print("  run42 各 mode 的 λ  :", calls["run42"])
print("  run43 各 mode 的 λ  :", calls["run43"])
ok1 = (calls["sel42"] == list(M.PRICE_MODES) and calls["sel43"] == list(M.PRICE_MODES)
       and len({w for _, w in calls["run42"]}) > 1)

print("\n== independent_warmup=False（旧行为）==")
clear()
M.run_strategy_comparison(S, None, None, True, shared, shared, core, False)
print("  select42 调用次数:", len(calls["sel42"]))
print("  run42 各 mode 的 λ:", calls["run42"])
ok2 = (len(calls["sel42"]) == 0 and
       {w for _, w in calls["run42"]} == {round(shared.lam, 4)})

print(f"\n结论: 独立标定接线 {'通过' if ok1 else '失败'}；"
      f"共用回退 {'通过' if ok2 else '失败'}")
