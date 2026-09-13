# -*- coding: utf-8 -*-
r"""
把 04_图/captions.json 里的"图题 + 注"编译成可直接放进论文的 LaTeX 片段
================================================================================

为什么需要它
------------
按全篇规范，**图里不出现成句文字**：坐标轴/刻度/panel 字母/图例与纯数值标签留在
图内，而顶部大标题、图内结论句、底部脚注一律移出图外，交给 LaTeX 排版。这样做的
直接好处是：这些文字随论文字号统一缩放、可被正文检索与交叉引用，且不会因为
`bbox_inches="tight"` 的裁剪而改变图的物理尺寸。

各图脚本用 `S.save_figure(fig, stem, caption=..., note=...)` 把文字登记进
`04_图/captions.json`；本脚本读它，逐图生成一个完整的 figure 环境：

    \begin{figure}[htbp]
      \centering
      \includegraphics[width=\textwidth]{fig06_rolling_timeline.pdf}
      \caption{...}
      \label{fig:...}
      \par\vspace{2pt}
      \begin{minipage}{.94\textwidth}
        \footnotesize 注：...
      \end{minipage}
    \end{figure}

"注"的写法照抄论文既有惯例（见 05_论文/final_new/appendix_discussion.tex 的表格注：
`\par\vspace{2pt}` + `\footnotesize` minipage）。论文的 cls 用
`\captionsetup{font=small,labelsep=quad}`，编号"图 N"由 LaTeX 自动生成，故
`\caption{}` 里**不再写"图 N"**。

Unicode → LaTeX 转义
--------------------
图内文字是给 matplotlib 用的，用的是 Unicode 直排字符（`−` `×` `⊆` `∅` `Δ` `σ`
`→` `⁰` `R̂` `%` `{}`）。XeLaTeX 直排 Unicode 符号依赖字体是否含该字形（`⊆` 在
Times New Roman 里就未必有），而 `%` `{` `}` `_` `&` `#` 在 LaTeX 里是**语法字符**，
直排会编译报错或静默吞掉。因此本脚本统一把符号换成数学模式的 LaTeX 写法、
把语法字符转义 —— 生成的 tex 用 XeLaTeX 直编即可。

用法
----
    python 03_代码/figures/build_captions.py
    # → 04_图/fig_captions.tex   （全部图的 figure 环境，按图号排好）
    # → 04_图/captions.md        （同一内容的人类可读版，便于核对）

只处理 captions.json 里登记过的图；未登记的图会在报告里列出，便于发现漏登记。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figstyle as S  # noqa: E402

OUT_TEX = S.FIG_DIR / "fig_captions.tex"
OUT_MD = S.FIG_DIR / "captions.md"

#: 图序 + 交付元信息：(stem, 正文标签, 插图宽度, 建议落位文件)
#: 顺序即论文中出现的顺序；新增图时在此登记，未登记但有 caption 的图会被单独提示。
DELIVERY: list[tuple[str, str, str, str]] = [
    ("fig06_rolling_timeline", "fig:p3-rolling-timeline", r"\textwidth",
     "p3_section.tex"),
    ("fig07_information_value", "fig:p3-info-value", r"\textwidth",
     "p3_section.tex"),
    ("fig08_price_forecast", "fig:p4-price-structure", r"\textwidth",
     "p4_section.tex"),
    ("fig09_p4_strategy", "fig:p4-strategy-roll", r"\textwidth",
     "p4_section.tex"),
    ("fig10_summary", "fig:summary", r"\textwidth",
     "p4_section.tex"),
]

#: 正文标题（图题）里允许出现的中文标题句；留空表示直接用 captions.json 的 caption。

# --------------------------------------------------------------------------- #
# Unicode → LaTeX。顺序重要：先长串后单字符，避免 "R̂" 被拆成 "R" + 组合符。
# --------------------------------------------------------------------------- #
UNICODE_MAP: tuple[tuple[str, str], ...] = (
    ("R\u0302", r"$\hat{R}$"),      # R̂  = R + COMBINING CIRCUMFLEX
    ("P\u0302", r"$\hat{P}$"),      # P̂
    ("N\u0302", r"$\hat{N}$"),      # N̂
    ("\u0302", ""),                 # 兜底：丢掉落单的组合符
    ("\u2212", r"$-$"),             # −  U+2212 MINUS SIGN
    ("\u2264", r"$\le$"),           # ≤
    ("\u2265", r"$\ge$"),           # ≥
    ("\u2248", r"$\approx$"),       # ≈
    ("\u00d7", r"$\times$"),        # ×
    ("\u2192", r"$\rightarrow$"),   # →
    ("\u2286", r"$\subseteq$"),     # ⊆
    ("\u2205", r"$\emptyset$"),     # ∅
    ("\u2208", r"$\in$"),           # ∈
    ("\u0394", r"$\Delta$"),        # Δ
    ("\u03c3", r"$\sigma$"),        # σ
    ("\u03b1", r"$\alpha$"),        # α
    ("\u03b7", r"$\eta$"),          # η
    ("\u00b1", r"$\pm$"),           # ±
    ("\u00b7", r"$\cdot$"),         # ·
    ("\u2070", r"$^{0}$"),          # ⁰
    ("\uff1d", r"$=$"),             # ＝ 全角等号（走数学模式，避免依赖 CJK 字体）
    ("\uff05", r"\%"),              # ％ 全角百分号
    ("\uff0b", r"$+$"),             # ＋ 全角加号
    ("\uff0d", r"$-$"),             # － 全角减号
    ("\u2032", r"$'$"),             # ′
)

#: LaTeX 语法字符的转义
TEX_ESCAPE: tuple[tuple[str, str], ...] = (
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)

_SYMBOL_TEX: dict[str, str] = dict(UNICODE_MAP)
_ESCAPE_TEX: dict[str, str] = dict(TEX_ESCAPE)

#: 长 token 优先（`R̂` 是 2 个码位，须排在单字符之前），单趟扫描，互不递归。
_ALL_PATTERN = re.compile(
    "|".join(re.escape(tok)
             for tok in sorted(_SYMBOL_TEX, key=len, reverse=True)
             + sorted(_ESCAPE_TEX, key=len, reverse=True))
)


def to_tex(text: str) -> str:
    """把图内 Unicode 文字转成可被 XeLaTeX 直编的 LaTeX 片段。

    **必须单趟完成**。第一版的做法是「先把符号换成占位符 `\\x00{序号}\\x00`，转义完
    语法字符再还原」——这个方案有个隐蔽的索引碰撞：还原 `\\x001\\x00` 时，若串里
    另有 `\\x0017\\x00`，替换仍是安全的；但 `to_tex` 对**每个**映射项都会
    `_stash()` 一次（含未命中的项），一旦映射表增删，序号就与预期错位。实测
    `±1σ` 被换成了 `\\x0017$\\hat{P}$14\\x00`（保留字面占位符，编号错到别的符号上）。
    改为一次 `re.sub` 扫描：命中哪个字符就用哪个替换，不存在二次解析。
    """
    if not text:
        return ""

    def _sub(m: re.Match) -> str:
        token = m.group(0)
        return _SYMBOL_TEX.get(token) or _ESCAPE_TEX[token]

    return _ALL_PATTERN.sub(_sub, text)


def figure_block(stem: str, caption: str, note: str, label: str, width: str,
                 target: str) -> str:
    """生成一个完整的 figure 环境。"""
    lines = [
        f"% ======== {stem}  （建议落位：05_论文/final_new/{target}）========",
        r"\begin{figure}[htbp]",
        r"  \centering",
        f"  \\includegraphics[width={width}]{{{stem}.pdf}}",
        f"  \\caption{{{to_tex(caption)}}}",
        f"  \\label{{{label}}}",
    ]
    if note:
        lines += [
            r"  \par\vspace{2pt}",
            r"  \begin{minipage}{.94\textwidth}",
            r"    \footnotesize " + to_tex(note),
            r"  \end{minipage}",
        ]
    lines.append(r"\end{figure}")
    return "\n".join(lines)


def main() -> int:
    if not S.CAPTION_FILE.exists():
        print(f"找不到 {S.CAPTION_FILE}；请先运行各 figNN 脚本完成登记。")
        return 2
    caps: dict[str, dict[str, str]] = json.loads(
        S.CAPTION_FILE.read_text(encoding="utf-8"))

    blocks: list[str] = []
    md: list[str] = [
        "# 论文插图题注与图下注（由 build_captions.py 生成，勿手改）",
        "",
        "对应图内**不含**任何成句文字；下列文字全部由 LaTeX 在 figure 环境内排版。",
        "",
    ]
    consumed: set[str] = set()
    for stem, label, width, target in DELIVERY:
        entry = caps.get(stem)
        if entry is None:
            print(f"! {stem} 尚未登记 caption，已跳过")
            continue
        consumed.add(stem)
        caption, note = entry.get("caption", ""), entry.get("note", "")
        blocks.append(figure_block(stem, caption, note, label, width, target))
        md += [
            f"## {stem}",
            "",
            f"- 落位：`05_论文/final_new/{target}`　标签：`\\ref{{{label}}}`",
            f"- 图题：{caption}",
            f"- 图下注：{note or '（无）'}",
            "",
        ]

    stray = sorted(set(caps) - consumed)
    if stray:
        print("以下图已登记 caption 但未在 DELIVERY 中登记，未写入 tex：", stray)

    header = (
        "% ==============================================================================\n"
        "% 论文插图题注与图下注 —— 由 03_代码/figures/build_captions.py 自动生成\n"
        "% 生成源：04_图/captions.json（各 figNN 脚本通过 S.save_figure(..., caption=, note=) 登记）\n"
        "% 说明：图内不含成句文字；编号\"图 N\"由 LaTeX 自动生成，故 \\caption 内不写编号。\n"
        "% ==============================================================================\n\n"
    )
    OUT_TEX.write_text(header + "\n\n".join(blocks) + "\n", encoding="utf-8")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"已写出 {OUT_TEX.relative_to(S.ROOT)}（{len(blocks)} 个 figure 环境）")
    print(f"已写出 {OUT_MD.relative_to(S.ROOT)}")
    for stem, label, _, target in DELIVERY:
        if stem in consumed:
            print(f"  · {stem:28s} → {target}  [{label}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
