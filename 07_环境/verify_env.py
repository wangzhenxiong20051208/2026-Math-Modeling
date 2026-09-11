"""Verify CUMCM programming environment. Run: python verify_env.py"""

from __future__ import annotations

import importlib
import sys
import traceback

PACKAGES = [
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "seaborn",
    "sklearn",
    "statsmodels",
    "openpyxl",
    "networkx",
    "sympy",
    "pulp",
    "ortools",
    "pymoo",
    "SALib",
    "deap",
    "skopt",
    "pyomo",
    "cvxpy",
    "plotly",
    "numba",
    "xgboost",
    "lightgbm",
    "factor_analyzer",
    "jupyterlab",
    "IPython",
]


def main() -> int:
    print("Python", sys.version)
    print("Executable", sys.executable)
    print("-" * 60)
    failed: list[str] = []
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
            ver = getattr(mod, "__version__", "ok")
            print(f"OK   {name:18} {ver}")
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            print(f"FAIL {name:18} {type(exc).__name__}: {exc}")
    print("-" * 60)
    try:
        import matplotlib.pyplot as plt
        from pathlib import Path

        sys.path.insert(0, r"D:\数学建模国赛\03_代码")
        import cumcm_plot  # noqa: F401

        plt.figure(figsize=(4, 2.5))
        plt.plot([0, 1, 2], [0, 1, 0])
        plt.title("中文标题测试")
        plt.xlabel("自变量")
        plt.ylabel("因变量")
        out = Path(r"D:\数学建模国赛\04_图\_env_test.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out, dpi=150)
        plt.close()
        print("PLOT", out, "bytes", out.stat().st_size)
    except Exception:
        failed.append("matplotlib-chinese")
        traceback.print_exc()

    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
