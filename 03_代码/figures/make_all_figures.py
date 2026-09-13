# -*- coding: utf-8 -*-
r"""
论文插图总入口 / 全量 QA
================================================================================

一句话重出全部插图并跑完全部强制检查：

    python 03_代码/figures/make_all_figures.py            # 全部
    python 03_代码/figures/make_all_figures.py --only fig03   # 只做某一张

每张图依次执行：
  1. 渲染（脚本内部已先跑多面板对齐门，未通过会抛异常并阻断导出）
  2. PDF 渲染期碰撞审计  audit_figure_collisions.py
  3. PDF 字形下限审计    audit_pdf_text.py --min-pt 5
  4. 物理尺寸检查（防止 bbox_inches="tight" 被超宽文字撑开）

任何一步非 0 退出即计入失败，最后汇总并以非 0 退出码返回，可直接接 CI。

============ AI-2 接口（做 Fig.6–Fig.10 时照抄这一套即可）============
1. 新建 `figNN_<name>.py`，开头 `import figstyle as S`，调用 `S.apply_style()`。
2. 颜色/字号/线宽/尺寸**一律取自 figstyle**，不要自己写死；同一物理量必须沿用
   同一 token（见 figstyle 模块 docstring 的语义色表）。
3. 导出统一用 `S.save_figure(fig, "figNN_<name>")`，它会自动跑对齐门并写
   PDF + SVG + PNG 到 04_图/ 与 04_图/pdf/。
4. 多面板图若用了非常规布局（不等宽、跨行 hero、inset、colorbar），把
   `alignment={...}` 传给 `save_figure` 显式声明分组/豁免，**不要**放宽容差。
5. 把新脚本追加到下面的 FIGURES 列表，即可自动纳入全量 QA。
================================================================================

AI-1 完成的五张图（Fig.1–Fig.5）已登记在 FIGURES 中。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figstyle as S  # noqa: E402

ROOT = S.ROOT

#: (输出主干, 脚本文件名, 期望页宽上限 mm, 期望页高上限 mm)
#: 主干必须与 `S.save_figure(fig, <主干>)` 一致，否则找不到产物。
#: 尺寸上限用于兜住"某行文字超宽把整页撑开"这类静默事故——它不会报错，
#: 只会让版心推算失效、并让碰撞审计产生成串假重叠。
FIGURES: list[tuple[str, str, float, float]] = [
    # fig01 收紧版面后高约 143 mm，上限给到 160 以便及早发现"又被撑开"。
    ("fig01_framework", "fig01_framework.py", 175.0, 160.0),
    ("fig02_p1_dispatch", "fig02_p1_dispatch.py", 175.0, 145.0),
    ("fig03_q80_mechanism", "fig03_q80_mechanism.py", 175.0, 110.0),
    ("fig04_risk_execution", "fig04_risk_execution.py", 175.0, 150.0),
    ("fig05_cost_waterfall", "fig05_cost_waterfall.py", 175.0, 110.0),
]


def _run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def page_size_mm(pdf: Path) -> tuple[float, float]:
    import fitz
    r = fitz.open(str(pdf))[0].rect
    return r.width / 72 * 25.4, r.height / 72 * 25.4


def check_one(stem: str, script: str, w_max: float, h_max: float) -> list[str]:
    """渲染一张图并跑完全部检查；返回问题清单（空 = 通过）。"""
    problems: list[str] = []

    rc, out = _run([sys.executable, str(HERE / script)])
    if rc != 0:
        return [f"渲染失败（退出码 {rc}）：{out.strip().splitlines()[-1:]}"]
    print(f"  [渲染] OK")

    pdf = S.FIG_PDF / f"{stem}.pdf"
    if not pdf.exists():
        return [f"未生成 {pdf}"]

    w, h = page_size_mm(pdf)
    print(f"  [尺寸] {w:.0f} × {h:.0f} mm")
    if w > w_max or h > h_max:
        problems.append(f"页面 {w:.0f}×{h:.0f} mm 超出上限 {w_max}×{h_max} mm"
                        f"（通常是一行超宽文字把 tight bbox 撑开）")

    rc, out = _run([sys.executable, str(HERE / "audit_figure_collisions.py"),
                    str(pdf), "--json-out",
                    str(S.FIG_QA / f"{stem}.collision-audit.json")])
    verdict = next((l.strip() for l in out.splitlines() if "verdict:" in l), "?")
    print(f"  [碰撞] {verdict}")
    if rc == 1:
        fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
        problems.append("碰撞审计 FIX BEFORE DELIVERY：" + " | ".join(fails[:3]))
    elif rc == 2:
        problems.append("碰撞审计 NOT AUDITABLE（PDF 或依赖不可读）")

    rc, out = _run([sys.executable, str(HERE / "audit_pdf_text.py"),
                    str(pdf), "--min-pt", "5"])
    gv = next((l.strip() for l in out.splitlines() if "verdict:" in l), "?")
    mn = next((l.strip() for l in out.splitlines() if "minimum found" in l), "?")
    print(f"  [字形] {mn} / {gv}")
    if rc != 0:
        problems.append(f"字形下限审计未通过：{mn}")

    js = S.FIG_QA / f"{stem}.alignment.json"
    if js.exists():
        import json
        d = json.loads(js.read_text(encoding="utf-8"))
        print(f"  [对齐] {d.get('verdict')}（比较组 {d.get('comparisons')}，"
              f"豁免 {d.get('exemptions')}）")
        if str(d.get("verdict", "")).upper().startswith(("FIX", "NOT AUDITABLE")):
            problems.append(f"对齐门未通过：{d.get('verdict')}")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="重出全部论文插图并跑全量 QA")
    ap.add_argument("--only", default=None,
                    help="只处理短名以该串开头的图，例如 fig03")
    args = ap.parse_args()

    targets = [f for f in FIGURES if not args.only or f[0].startswith(args.only)]
    if not targets:
        print(f"没有匹配 {args.only!r} 的图")
        return 2

    all_problems: dict[str, list[str]] = {}
    for stem, script, w_max, h_max in targets:
        print(f"\n=== {stem}  ({script})")
        all_problems[stem] = check_one(stem, script, w_max, h_max)

    print("\n" + "=" * 66)
    bad = {k: v for k, v in all_problems.items() if v}
    for stem, probs in all_problems.items():
        print(f"{stem}: {'通过' if not probs else '存在问题'}")
        for p in probs:
            print(f"    - {p}")
    print("=" * 66)
    print(f"合计 {len(targets)} 张，通过 {len(targets) - len(bad)} 张，"
          f"存在问题 {len(bad)} 张")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
