"""CUMCM figure helper: Chinese fonts, 300 dpi, Word/LaTeX-ready export."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


# 仓库根目录 = 本文件的上一级（03_代码/ 的上一级）。
# 这样 Windows（D:\数学建模国赛）和 macOS（本仓库）解析到的是同一个 04_图。
FIGURE_DIR = Path(__file__).resolve().parents[1] / "04_图"


def setup_plot(font_size: int = 11) -> None:
    candidates = [
        # Windows
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        # Linux / 跨平台
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        # macOS
        "PingFang SC",
        "Hiragino Sans GB",
        "STHeiti",
        "Arial Unicode MS",
    ]
    available = {f.name for f in mpl.font_manager.fontManager.ttflist}
    zh = next((name for name in candidates if name in available), "DejaVu Sans")
    mpl.rcParams.update(
        {
            "font.sans-serif": [zh, "DejaVu Sans"],
            "font.family": "sans-serif",
            "axes.unicode_minus": False,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "font.size": font_size,
            "axes.labelsize": font_size,
            "axes.titlesize": font_size + 1,
            "legend.fontsize": font_size - 1,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def savefig(name: str, close: bool = True) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    if close:
        plt.close()
    return path


setup_plot()
