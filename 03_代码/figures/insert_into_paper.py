# -*- coding: utf-8 -*-
r"""
把 fig_captions.tex 里的 figure 环境按"语义落位表"插入论文
================================================================================

`build_captions.py` 只负责把图题与注编译成 LaTeX；本脚本负责把它们放到论文里
正确的位置——插在**讲这张图的那一段正文之后**，而不是笼统地堆在文末。

为什么用脚本而不是手工粘贴
--------------------------
1. **可重跑。** 图改一次，caption 就变一次；重跑本脚本即按最新文字更新论文里的
   figure 环境（锚点定位，不依赖行号）。
2. **幂等且会更新。** 图已落位时，用 `fig_captions.tex` 里的最新块**整体替换**原
   figure 环境（靠 `\includegraphics{<stem>.pdf}` 定位，不依赖行号、也不依赖
   caption 文字），内容一致才算跳过。改一次图题或"注"，重跑即同步进正文——
   首版是"见词即跳过"，改了注论文纹丝不动，属于静默不一致。
3. **图件同步。** 顺带把 `04_图/pdf/<stem>.pdf` 拷进 `05_论文/final_new/figures/`，
   保证正文引用的永远是刚渲染的那一版矢量图。
4. **落位可审。** PLACEMENT 就是一张"哪张图讲哪一段"的清单，一眼可查。

用法
----
    python 03_代码/figures/build_captions.py     # 先更新 04_图/fig_captions.tex
    python 03_代码/figures/insert_into_paper.py  # 再插进 05_论文/final_new/*.tex
    python 03_代码/figures/insert_into_paper.py --dry-run   # 只看会插到哪里

注意
----
本脚本**不删**论文里已有的旧插图（如 p4_fig1_price_structure.png）。新旧图内容
有重叠时的取舍属于正文决策，脚本不替作者做；重叠清单见 --dry-run 的提示与
AI2_FIGURE_REPORT.md 的"与旧图的关系"一节。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figstyle as S  # noqa: E402

PAPER_DIR = S.ROOT / "05_论文" / "final_new"
CAPTIONS_TEX = S.FIG_DIR / "fig_captions.tex"

#: (主干, 目标文件, 锚点正则, 落位说明)
#: 插入位置 = 锚点匹配结束处；锚点都取"讲这张图的那一段"的句末，保证图文相邻。
#: 锚点取**新增的交叉引用句句末**（"…见图~\ref{...}。"），这样重跑时图仍落在
#: 紧接其引用句之后，而不会插到句子中间。
PLACEMENT: tuple[tuple[str, str, str, str], ...] = (
    ("fig06_rolling_timeline", "p3_section.tex",
     r"时间结构见图~\\ref\{fig:p3-rolling-timeline\}。",
     "§模型框架：紧接「当前六小时立即生效、后续仅用于规划」那段"),
    ("fig07_information_value", "p3_section.tex",
     r"\\label\{fig:p3-combo\}\n\\end\{figure\}",
     "§结果分析（1）：紧随八种组合的费用柱状图"),
    ("fig08_price_forecast", "p4_section.tex",
     r"电价的结构分解、星期效应强度与预测误差见图~\\ref\{fig:p4-price-structure\}。",
     "§附件 4 的电价结构：紧随同星期加权预测式"),
    ("fig09_p4_strategy", "p4_section.tex",
     r"见附录图~\\ref\{fig:p4-strategy\}。",
     "§三种价格信息条件下的策略对照：紧随策略对照结论"),
    ("fig10_summary", "p4_section.tex",
     r"四个问题逐层叠加的总览见图~\\ref\{fig:summary\}。",
     "§本节小结末：全文总结图（若另设「模型的评价」一节，可整体搬走）"),
)

#: 与旧图内容重叠，插入后需人工决定是否移除（脚本不代删）
OVERLAPS: dict[str, str] = {
    "fig08_price_forecast": "p4_fig1_price_structure.png（图 fig:p4-struct）",
    "fig09_p4_strategy": "p4_fig3_strategy.png（图 fig:p4-strategy）",
    "fig07_information_value": "p3_fig4_combos.png（图 fig:p3-combo，主题相关但不重复）",
    "fig06_rolling_timeline": "p3_fig1_versions.png（图 fig:p3-versions，视角不同）",
    "fig10_summary": "（无对应旧图）",
}

MARKER = r"% ======== "

#: 图件 PDF 源目录（save_figure 的矢量输出）与论文图件目录
PDF_SRC = S.FIG_DIR / "pdf"
PAPER_FIG_DIR = PAPER_DIR / "figures"


def sync_pdfs(stems: list[str], *, dry_run: bool = False) -> int:
    """把 04_图/pdf/<stem>.pdf 同步进 05_论文/final_new/figures/。

    论文里的 ``\\includegraphics{figNN_....pdf}`` 走的是 ``figures/`` 目录。
    图一旦重渲染，这里就重拷一次，避免"论文引用的还是上一版图"这种静默不一致。
    """
    import shutil

    PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for stem in stems:
        src = PDF_SRC / f"{stem}.pdf"
        if not src.exists():
            print(f"! 图件缺失：{src}")
            continue
        dst = PAPER_FIG_DIR / f"{stem}.pdf"
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            print(f"= {stem}.pdf 已是最新")
            continue
        if not dry_run:
            shutil.copy2(src, dst)
        print(f"{'+' if not dry_run else '·'} {stem}.pdf 同步 → 05_论文/final_new/figures/")
        n += 1
    return n


def split_blocks(tex: str) -> dict[str, str]:
    """按 `% ======== <stem>` 标记把 fig_captions.tex 切成 {stem: 块文本}。"""
    parts = re.split(rf"(?m)^{MARKER}(?P<stem>\w+)", tex)
    blocks: dict[str, str] = {}
    # split 结果：[前言, stem1, body1, stem2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        stem, body = parts[i], parts[i + 1]
        body = body.strip()
        # 去掉紧跟标记的那半行（"  （建议落位：… )========"）
        body = body.split("========\n", 1)[-1].strip() if "========" in body.split("\n")[0] else body
        blocks[stem] = body
    return blocks


def replace_block(text: str, stem: str, block: str) -> tuple[str, bool]:
    """把论文里已落的该图 figure 环境**整体换成新块**，返回 (新文本, 是否改动)。

    定位完全靠 ``\\includegraphics{<stem>.pdf}``：从它回溯最近的
    ``\\begin{figure}``、再前伸到配对的 ``\\end{figure}``。
    这样图题或"注"改动后重跑本脚本，论文里的文字会跟着更新；而不像"见词即跳过"
    那样把旧题注永久留在正文里（首版就是这个缺陷——改了注，论文纹丝不动）。
    """
    m = re.search(rf"\\includegraphics(?:\[[^\]]*\])?\{{{re.escape(stem)}\.pdf\}}", text)
    if m is None:
        return text, False
    b = text.rfind(r"\begin{figure}", 0, m.start())
    if b < 0:
        return text, False
    e = text.find(r"\end{figure}", m.end())
    if e < 0:
        return text, False
    e += len(r"\end{figure}")
    if text[b:e].strip() == block.strip():
        return text, False
    return text[:b] + block.rstrip("\n") + text[e:], True


def main() -> int:
    ap = argparse.ArgumentParser(description="把插图题注插入论文")
    ap.add_argument("--dry-run", action="store_true", help="只显示落位，不改文件")
    args = ap.parse_args()

    if not CAPTIONS_TEX.exists():
        print(f"找不到 {CAPTIONS_TEX}；请先运行 build_captions.py")
        return 2
    if not PAPER_DIR.exists():
        print(f"找不到论文目录 {PAPER_DIR}")
        return 2

    blocks = split_blocks(CAPTIONS_TEX.read_text(encoding="utf-8"))
    print(f"fig_captions.tex 中共 {len(blocks)} 个 figure 环境：{sorted(blocks)}\n")

    files: dict[str, str] = {}
    changed: dict[str, str] = {}
    n_insert = n_update = n_skip = n_missing = 0

    for stem, target, anchor, why in PLACEMENT:
        block = blocks.get(stem)
        if block is None:
            print(f"! {stem}: fig_captions.tex 里没有这个图，跳过")
            n_missing += 1
            continue
        path = PAPER_DIR / target
        if path not in files:
            files[path] = path.read_text(encoding="utf-8")
        text = files[path]

        # 已落位 → 用最新块整体替换（图题/注改了就跟上）；内容一致才算幂等跳过。
        if re.search(rf"\\includegraphics(?:\[[^\]]*\])?\{{{re.escape(stem)}\.pdf\}}",
                     text) is not None:
            new_text, touched = replace_block(text, stem, block)
            if touched:
                files[path] = new_text
                print(f"~ {stem:26s} {target}: 已用最新题注/注替换原 figure 环境")
                n_update += 1
            else:
                print(f"= {stem:26s} {target}: 已存在且内容一致，跳过（幂等）")
                n_skip += 1
            continue

        m = re.search(anchor, text)
        if m is None:
            print(f"✗ {stem:26s} {target}: 锚点未命中 —— {anchor[:40]}")
            n_missing += 1
            continue

        insertion = "\n\n" + block + "\n"
        text = text[:m.end()] + insertion + text[m.end():]
        files[path] = text
        line_no = text[:m.end()].count("\n") + 1
        print(f"+ {stem:26s} {target}: 插在第 {line_no} 行后")
        print(f"    落位：{why}")
        if stem in OVERLAPS:
            print(f"    ⚠ 与旧图重叠：{OVERLAPS[stem]}（脚本不代删，请人工取舍）")
        n_insert += 1

    if not args.dry_run:
        for path, text in files.items():
            if path.exists() and path.read_text(encoding="utf-8") == text:
                continue
            path.write_text(text, encoding="utf-8")
            changed[str(path.relative_to(S.ROOT))] = "written"
        for p in changed:
            print(f"\n已写入 {p}")

    # 图件 PDF 同步：无论正文是否需重插，都保证论文用的是最新一版矢量图。
    print()
    n_sync = sync_pdfs([stem for stem, *_ in PLACEMENT], dry_run=args.dry_run)

    print(f"\n合计：插入 {n_insert}，更新 {n_update}，跳过 {n_skip}，异常 {n_missing}，"
          f"图件同步 {n_sync}" + ("（dry-run，未落盘）" if args.dry_run else ""))
    return 1 if n_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
