"""One-liner for notebooks: from matplotlib_chinese import setup; setup()"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(r"D:\数学建模国赛\03_代码")))
from cumcm_plot import setup_plot as setup, savefig  # noqa: F401
