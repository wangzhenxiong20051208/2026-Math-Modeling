# -*- coding: utf-8 -*-
r"""
================================================================================
全篇统一视觉规范（Project-wide visual specification）  —— AI-1 制定，AI-2 必须直接复用
================================================================================

本模块是 Fig.1–Fig.10 唯一的样式真源（single source of truth）。任何绘图脚本
都不得自行定义颜色、字号、线宽或图形尺寸；一律 `from figstyle import ...`。

设计原则
--------
1. **同一物理量，全文同一视觉编码。** 电价永远是红褐、紧急购电永远是红、
   充电永远是绿。读者在第 2 张图学会的编码，在第 9 张图仍然成立。
2. **一个 panel 只回答一个问题。** 不把两个量纲硬塞进一个双轴面板。
3. **蓝色家族 = 先验信息与先验决策**（预测、日前计划购电）；**近黑 = 实际发生**
   （实际净负荷、实际储电量）；**橙 = 风险修正**；**红 = 尾部风险与紧急支出**。
   这条语义线贯穿四个问题：先验 → 修正 → 实际 → 尾部代价。
4. 少用 legend，优先直接标注（direct label）。
5. 白底、无 3D、无装饰性渐变。

颜色语义表
----------
==============  ==========  ==========  ================================
token           中文         Hex         用途与图元
==============  ==========  ==========  ================================
C_PRICE         电价        #A0522D     阶梯线（step），细，红褐
C_FORECAST      预测        #3775BA     虚线；净负荷/光伏/电价预测
C_RISK          风险修正    #E28E2C     实线或色带；风险余量、风险净负荷
C_ACTUAL        实际        #272727     实线，全图最重；实际净负荷/储电量
C_GRID          计划购电    #0F4D92     柱/填充；日前计划购电量与其费用
C_EMERGENCY     紧急购电    #D1495B     斜纹柱/填充；5 倍价紧急购电
C_CHARGE        充电        #3F8F4F     零轴以上柱
C_DISCHARGE     放电        #7C6CCF     零轴以下柱
C_SOC           储电量      #33B5A5     粗实线；SOC 轨迹
C_REF           参考轨迹    #8E8E8E     点线；日前参考轨迹 Ē、物理边界
C_BAND          区间底纹    #F0F0F0     极浅灰底纹（不可作数据编码）
C_SAVE          节约        #2E9E44     仅用于"费用下降"方向性提示
==============  ==========  ==========  ================================

注：C_FORECAST 与 C_GRID 同属蓝色家族（先验），但取不同明度以便同图出现时
仍可区分；若二者同时出现，预测用浅蓝、计划购电用深蓝，不得互换。

字体与可编辑文本
----------------
**中文回退必须写成 `font.family` 的列表，不能写 `font.sans-serif` 列表。**

    font.family = ['Arial', 'Microsoft YaHei', 'DejaVu Sans']   # ✓ 正确
    font.sans-serif = ['Arial', 'Microsoft YaHei']              # ✗ 无效，中文变豆腐块

matplotlib 的逐字形回退只认 `font.family` 列表；把候选字体放在 `font.sans-serif`
里时它只取第一个能解析的字体（Arial），缺字直接画成空白/豆腐块且**不报错**
（只在 savefig 时给 UserWarning）。本仓库已实测：拉丁字形走 Arial、中文回退到
微软雅黑，两者共用一条 `font.family` 列表；该行为由 `_font_probe.py` 像素级校验。

`pdf.fonttype = 42` / `svg.fonttype = 'none'` 保证导出后文字仍可编辑、可检索。

字号下限
--------
正文/刻度 7.5 pt，图注 8 pt，panel 标签 9 pt（粗体）。**任何字号不得低于 7.5 pt**，
且必须通过 `audit_pdf_text.py --min-pt 5` （含上下标缩放后仍 ≥ 5 pt）。

图形尺寸
--------
正文版心宽 160 mm（A4，25 mm 四边距）。`FIG_W_FULL = 160`、`FIG_W_HALF = 78`。
所有图以 mm 定义物理尺寸，导出后由 LaTeX 按 `\textwidth` 缩放，不产生二次缩放失真。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无头批处理：必须在 import pyplot 之前设置
import matplotlib as mpl
import matplotlib.pyplot as plt

# ================================================================ 路径

# 本文件位于 03_代码/figures/，仓库根目录是上两级。
ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "04_图"          # 论文插图（LaTeX 直接引用）
FIG_PDF = FIG_DIR / "pdf"         # 矢量 PDF 主输出
FIG_QA = FIG_DIR / "qa"           # 对齐/碰撞审计产物（仅供检查，非交付件）
SUP_DIR = ROOT / "06_支撑材料"     # 模型真实输出（只读）

for _d in (FIG_DIR, FIG_PDF, FIG_QA):
    _d.mkdir(parents=True, exist_ok=True)
del _d

# ================================================================ 颜色

#: 语义色板：一个物理量一个颜色，全文复用。
PALETTE = {
    # —— 价格 ——
    "C_PRICE":      "#A0522D",   # 电价：红褐
    # —— 先验：预测与日前计划（蓝色家族）——
    "C_FORECAST":   "#3775BA",   # 预测（净负荷/光伏/电价）
    "C_GRID":       "#0F4D92",   # 日前计划购电量与其费用
    # —— 风险修正 ——
    "C_RISK":       "#E28E2C",   # 风险余量、风险修正净负荷
    # —— 实际发生 ——
    "C_ACTUAL":     "#272727",   # 实际净负荷 / 实际储电量
    # —— 尾部代价 ——
    "C_EMERGENCY":  "#D1495B",   # 紧急购电（5 倍价）
    # —— 储能 ——
    "C_CHARGE":     "#3F8F4F",   # 充电
    "C_DISCHARGE":  "#7C6CCF",   # 放电
    "C_SOC":        "#33B5A5",   # 储电量 SOC
    # —— 辅助 ——
    "C_REF":        "#8E8E8E",   # 参考轨迹、物理边界
    "C_BAND":       "#F0F0F0",   # 底纹（非数据编码）
    "C_SAVE":       "#2E9E44",   # 节约方向
    "C_LOSS":       "#C0392B",   # 增加方向
    "C_NEUTRAL":    "#767676",   # 中性文字
}

# 便于 `from figstyle import C_PRICE` 直接取用
globals().update(PALETTE)

#: 中文量与英文术语对照（图注/报告复用，避免同一概念多种译法）
TERMS = {
    "电价": "price",
    "预测净负荷": "forecast net load",
    "风险修正净负荷": "risk-adjusted net load",
    "实际净负荷": "actual net load",
    "风险余量": "risk margin",
    "计划购电量": "day-ahead purchase",
    "紧急购电量": "emergency purchase",
    "充电": "charge",
    "放电": "discharge",
    "储电量": "state of charge",
}

# ================================================================ 尺寸（mm）

FIG_W_FULL = 160.0   # 通栏
FIG_W_HALF = 78.0    # 半栏
MM_PER_IN = 25.4


def mm2in(mm: float) -> float:
    """毫米转英寸。"""
    return mm / MM_PER_IN


# ================================================================ 字号与线宽

FS_TICK = 7.5      # 刻度
FS_LABEL = 8.0     # 轴标签
FS_ANNOT = 8.0     # 图内标注
FS_PANEL = 9.0     # panel 标签 (a)(b)(c)
FS_TITLE = 8.5     # panel 小标题
FS_LEGEND = 7.5    # 图例
FS_NOTE = 7.5      # 脚注式说明

LW_AXIS = 0.8      # 轴框
LW_MAIN = 1.6      # 主曲线
LW_THIN = 1.0      # 细曲线
LW_REF = 0.9       # 参考/边界线

MS_MARKER = 3.2    # marker 尺寸

# ================================================================ rcParams

def apply_style() -> None:
    """应用全篇统一 rcParams。每个绘图脚本在建立 figure 之前调用一次。"""
    mpl.rcParams.update({
        # —— 字体：拉丁走 Arial，中文逐字形回退到微软雅黑 ——
        # 必须用 font.family 列表；放进 font.sans-serif 不会触发回退（见模块 docstring）。
        "font.family": ["Arial", "Microsoft YaHei", "DejaVu Sans"],
        "axes.unicode_minus": False,   # 中文字体下负号正常显示

        # —— 可编辑文本：PDF 嵌入 TrueType，SVG 保留 <text> 节点 ——
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",

        # —— 字号 ——
        "font.size": FS_LABEL,
        "axes.labelsize": FS_LABEL,
        "axes.titlesize": FS_TITLE,
        "xtick.labelsize": FS_TICK,
        "ytick.labelsize": FS_TICK,
        "legend.fontsize": FS_LEGEND,

        # —— 轴与网格 ——
        "axes.linewidth": LW_AXIS,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.grid": True,
        "grid.alpha": 0.22,
        "grid.linewidth": 0.6,
        "grid.color": "#B8B8B8",
        "axes.axisbelow": True,       # 网格永远在数据之下
        "axes.edgecolor": "#4D4D4D",
        "xtick.major.width": LW_AXIS,
        "ytick.major.width": LW_AXIS,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.color": "#4D4D4D",
        "ytick.color": "#4D4D4D",
        "axes.labelcolor": "#272727",
        "text.color": "#272727",

        # —— 图例：无边框、紧凑 ——
        "legend.frameon": False,
        "legend.handlelength": 1.6,
        "legend.handletextpad": 0.6,
        "legend.columnspacing": 1.2,
        "legend.labelspacing": 0.35,

        # —— 线与 marker ——
        "lines.linewidth": LW_MAIN,
        "lines.solid_capstyle": "round",
        "lines.dash_capstyle": "round",

        # —— 输出 ——
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
        "axes.facecolor": "white",

        # —— 数学文本：不调用外部 LaTeX（环境无保证），用 mathtext ——
        "mathtext.fontset": "dejavusans",
        "mathtext.default": "regular",
    })


# ================================================================ 绘图助手

def add_panel_label(ax, label: str, x: float = 0.0, y: float = 1.0,
                    dx_pt: float = -14.0, dy_pt: float = 3.0,
                    fontsize: float = FS_PANEL, **kw):
    """在 axes 锚点处以**固定物理偏移**放置 panel 标签。

    固定点偏移（而非 `y=1.02` 这类 axes 分数偏移）保证跨行 panel 高度不同时，
    标签仍在同一物理高度上，对齐审计才能通过。
    """
    from matplotlib.transforms import ScaledTranslation
    offset = ScaledTranslation(dx_pt / 72, dy_pt / 72, ax.figure.dpi_scale_trans)
    kw.setdefault("fontweight", "bold")
    kw.setdefault("ha", "left")
    kw.setdefault("va", "bottom")
    return ax.text(x, y, label, transform=ax.transAxes + offset,
                   fontsize=fontsize, **kw)


def panel_title(ax, text: str, **kw):
    """panel 小标题：左对齐，紧贴面板上沿。"""
    kw.setdefault("loc", "left")
    kw.setdefault("fontsize", FS_TITLE)
    kw.setdefault("pad", 4.0)
    return ax.set_title(text, **kw)


def direct_label(ax, x, y, text, color, **kw):
    """直接标注：优先于图例，减少视线往返。"""
    kw.setdefault("fontsize", FS_ANNOT)
    kw.setdefault("color", color)
    kw.setdefault("fontweight", "bold")
    kw.setdefault("va", "center")
    return ax.text(x, y, text, **kw)


def zero_line(ax, **kw):
    """零点基准线。"""
    kw.setdefault("color", "#4D4D4D")
    kw.setdefault("lw", 0.8)
    return ax.axhline(0, **kw)


# ================================================================ 导出

def save_figure(fig, stem: str, *, formats=("pdf", "svg", "png"), dpi: int = 600,
                pad: float = 0.02, alignment: dict | None = None,
                close: bool = True) -> list[Path]:
    """统一导出：先跑多面板对齐门，再写 PDF(矢量) + PNG(300dpi 预览)。

    Parameters
    ----------
    fig   : matplotlib Figure（已完成全部布局，勿再改动）
    stem  : 文件名主干，例如 ``fig01_framework``
    alignment : 传给 ``require_matplotlib_panel_alignment`` 的额外参数
                （显式 row_groups / column_groups / exemptions）。
                单面板图会自行判定为 NOT APPLICABLE（退出码 0，视为通过）。

    多面板图必须先通过 1.5 pt 对齐门；不通过会抛 PanelAlignmentError，
    从而阻断导出——这是刻意的，不要 try/except 掉。
    """
    from audit_panel_alignment import require_matplotlib_panel_alignment

    out_pdf = FIG_PDF / f"{stem}.pdf"
    out_png = FIG_DIR / f"{stem}.png"

    require_matplotlib_panel_alignment(
        fig,
        json_out=str(FIG_QA / f"{stem}.alignment.json"),
        overlay_svg=str(FIG_QA / f"{stem}.alignment.svg"),
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        strict=True,
        **(alignment or {}),
    )

    saved: list[Path] = []
    if "pdf" in formats:
        fig.savefig(out_pdf, bbox_inches="tight", pad_inches=pad)
        saved.append(out_pdf)
    if "svg" in formats:
        # SVG 为可编辑矢量备份：文字保持 <text> 节点（svg.fonttype='none'），
        # 便于在 Illustrator / Inkscape 里改字而不必回到脚本。
        out_svg = FIG_PDF / f"{stem}.svg"
        fig.savefig(out_svg, bbox_inches="tight", pad_inches=pad)
        saved.append(out_svg)
    if "png" in formats:
        fig.savefig(out_png, dpi=300, bbox_inches="tight", pad_inches=pad)
        saved.append(out_png)
    if close:
        plt.close(fig)
    return saved


def audit_collisions(pdf_stem: str, *, strict: bool = False) -> int:
    """对已导出的 PDF 跑强制碰撞审计，返回退出码。

    0 = 通过；1 = FIX BEFORE DELIVERY（必须修）；2 = NOT AUDITABLE。
    """
    pdf = FIG_PDF / f"{pdf_stem}.pdf"
    cmd = [sys.executable, str(Path(__file__).parent / "audit_figure_collisions.py"),
           str(pdf),
           "--json-out", str(FIG_QA / f"{pdf_stem}.collision-audit.json"),
           "--overlay-pdf", str(FIG_QA / f"{pdf_stem}.collision-audit.pdf")]
    if strict:
        cmd.append("--strict")
    return subprocess.call(cmd)


def audit_glyphs(pdf_stem: str, min_pt: float = 5.0) -> int:
    """对已导出的 PDF 跑 5 pt 字形下限审计，返回退出码。"""
    pdf = FIG_PDF / f"{pdf_stem}.pdf"
    cmd = [sys.executable, str(Path(__file__).parent / "audit_pdf_text.py"),
           str(pdf), "--min-pt", str(min_pt),
           "--json", str(FIG_QA / f"{pdf_stem}.glyph-audit.json")]
    return subprocess.call(cmd)


def wrap_cjk(text: str, *, fontsize: float, fig_width_mm: float = FIG_W_FULL,
             margin_mm: float = 6.0) -> str:
    """把长中文说明折成不超过版心宽度的多行。

    为什么必须折行：`save_figure` 用 `bbox_inches="tight"` 导出，**任何一行超宽
    的文字都会把整页横向撑开**——实测把 160 mm 的图撑成 196 mm，后续所有版面
    推算随之失效，且碰撞审计会报出成串的假重叠。

    中文没有空格，`textwrap` 对其无效，故按「字宽 = 字号」估算每行字数：
    6.2 pt 汉字实测步进 2.19 mm（= 6.2 × 25.4 / 72），与估算一致。
    尽量在标点后断行，避免把「α ∈ [0.70」这类整体截断。
    """
    if not text:
        return text
    char_mm = fontsize * MM_PER_IN / 72.0
    per_line = max(8, int((fig_width_mm - 2 * margin_mm) / char_mm))
    lines, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= per_line - 8 and ch in "；，。、）」":
            lines.append(cur)
            cur = ""
        elif len(cur) >= per_line:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\n".join(lines)


__all__ = [
    "ROOT", "FIG_DIR", "FIG_PDF", "FIG_QA", "SUP_DIR",
    "PALETTE", "TERMS",
    "FIG_W_FULL", "FIG_W_HALF", "mm2in",
    "FS_TICK", "FS_LABEL", "FS_ANNOT", "FS_PANEL", "FS_TITLE",
    "FS_LEGEND", "FS_NOTE",
    "LW_AXIS", "LW_MAIN", "LW_THIN", "LW_REF", "MS_MARKER",
    "apply_style", "add_panel_label", "panel_title", "direct_label",
    "zero_line", "save_figure", "audit_collisions", "audit_glyphs", "wrap_cjk",
    *PALETTE.keys(),
]
