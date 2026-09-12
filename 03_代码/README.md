# 03_代码 文件说明

本目录是论文的**全部建模、求解、分析与绘图代码**。随支撑材料提交的副本位于
`06_支撑材料/源码/`（$21$ 个脚本，与本目录逐字节相同，仅排除下面标注为
"已废弃"的两个文件）。

所有脚本均从**仓库根目录**运行，例如：

```bash
python3 03_代码/p3_backtest.py       # 生成 06_支撑材料/result3.xlsx 与内部结果文件
python3 03_代码/p3_tables.py         # 读结果文件，生成 05_论文/CUMCMThesis/p3_tables*.tex
```

依赖：`numpy`、`scipy`（`scipy.optimize.milp`，用于问题一、二、四的混合整数
模型）、`pulp`（内置 CBC 求解器，用于问题三的两个线性规划）、`pandas`、
`openpyxl`、`matplotlib`。

---

## 一、四个问题的主求解器

| 文件 | 作用 |
| --- | --- |
| `p1_microgrid.py` | **问题一**：单日 $144$ 段 LP/MILP，储能与光伏联调。同时定义全局常量（`N`、`E_MIN`、`E_MAX`、`E_INIT`、`P_MAX`、`M_ENERGY`、`EC`、`ED`、`TAU`）与 `BLOCKS`／`block_label`／`interval_label` 等公共工具，被其余所有脚本 import。 |
| `p2_microgrid.py` | **问题二**：风险余量 + 日前 MILP + 因果执行规则的全年滚动回放。定义 `N_DAY`、`REPORT_START`、`REPORT_END`、`load_attach2`、`Forecaster` 等，被问题三、问题四复用。 |
| `p3_microgrid.py` | **问题三**：多版本预报驱动的滚动购电与调整模型（模型、附件 3 载入、因果分段线性插值、负载外推、计划 LP、调整 LP、实时执行规则）。**这是论文问题三交付件 `result3.xlsx` 的生成链源头。** |
| `p4_microgrid.py` | **问题四**：价格预测器 + 风险分位数 + 场景策略（4-1 价格预测、4-2 分位数余量、4-3 网格标定）。**计费主口径为退款**（与问题三一致），由 `CONVENTIONS` 的 `"refund"` 分支实现；`"main"` 这一字符串仍是**不退款**公式（4-2 无口径，该参数对它无效），改名会动到计划缓存键与既有 JSON 的键名，故保留。`--refund-main` 把 4-3 主结果、策略对照与预报组合一并切到退款口径；`--refund` 只重建退款臂。两个开关各自独立标定、独立回放，不与主口径混合。 |

`p3_microgrid.py` 与下面 `p3_rolling_microgrid.py` 是**两套不同的**问题三实现，
注意区分（见第三节）。

## 二、结果生成（问题三链路，论文数字的唯一来源）

| 文件 | 作用 |
| --- | --- |
| `p3_backtest.py` | 全年因果滚动回放：维护最近 $W$ 天的合并误差分位数，在 $6{:}00/12{:}00/18{:}00$ 三个发布时刻重解调整 LP，只提交当前六小时交付块。 |
| `p3_export.py` | 写出 `06_支撑材料/result3.xlsx`（从官方模板 `附件5/result3.xlsx` 重新拷贝后写入）与 `p3_spec.json`，并逐日执行**九项强制校验**。 |
| `p3_analysis.py` | 主结果、八种预报使用方式（消融）、两处口径敏感性、$14$ 个单参数扰动、九项校验汇总、四个发布版本的预报精度。写出 `p3_analysis.json`、`p3_main_daily.csv`、`p3_main_arrays.npz`、`p3_forecast_skill.csv`。运行时会自动生成 `_p3_variants/` 下的口径变体源码。 |
| `p3_calibration.py` | $1$ 月网格标定（$5\times3\times3=45$ 点）与 $\lambda$、$W$ 单独扫描，以及"用 $1$ 月最优参数直接外推"的**样本外检验**。写出 `p3_calibration.json`。 |
| `p3_alignment_scan.py` | 附件 3 的**时间口径判定**：用全年数据做对齐扫描，确认 $24$ 个值对应发布后 $1$–$24$ 小时的整点功率。写出 `p3_alignment_scan.json`。 |

## 三、`p3_microgrid.py` 与 `p3_rolling_microgrid.py` 的区别（重要）

- **`p3_microgrid.py`** —— 贾的最终版实现，**论文问题三的全部数字出自它**。
  附件 3 载入方式、预报插值口径、调整 LP 的退款口径、交付块提交规则、九项
  校验都以它为准。
- **`p3_rolling_microgrid.py`** —— 问题三早期版本的建模库。它**不再产生论文中
  的任何数字**，但问题四的求解器 `p4_microgrid.py:115` 直接 import 了它
  （`ForecastPanel`、`load_attach3`、`forecast_energy_slots`、`load_forecast_at`、
  `build_eps3`、`solve_adjust`、`DayRunner`、`CalConfig3`、`ALL_S`、
  `RELEASE_HOURS`、`BLOCK_BOUNDS`、`COEF_UP`、`COEF_DOWN`、`COEF_EMG`），
  因此**必须一并提交**，否则问题四无法运行。

## 四、出图与出表

| 文件 | 作用 |
| --- | --- |
| `p1_figures.py` / `p2_figures.py` / `p3_figures.py` / `p4_figures.py` | 生成 `04_图/` 下的正文插图。全部从结果文件读取，不含手工填数。 |
| `p2_tables.py` / `p3_tables.py` / `p4_tables.py` | 生成 `05_论文/CUMCMThesis/` 下的 `*.tex` 表格。`p3_tables.py` 输出 `p3_tables.tex`（正文）与 `p3_tables_appendix.tex`（附录）；`p4_tables.py --split` 输出 `p4_tables.tex`（正文）、`p4_tables_appendix.tex`、`p4_tables_refund.tex`（附录：不退款口径敏感性）与 `p4_combo_detail.tex`（附录：八种组合的边际价值明细）。 |
| `cumcm_plot.py` | 绘图样式与中文字体配置，被四个绘图脚本 import。 |

## 五、独立复核与辅助脚本

| 文件 | 作用 |
| --- | --- |
| `solve2_final.py` | **问题二的独立参考实现**，由另一位成员独立编写（标定网格、重选周期、回放窗口均独立设定），用于与 `p2_microgrid.py` 相互印证。 |
| `p2_alphasweep.py` | 问题二的 $\alpha$ 灵敏度扫描。 |
| `p4_price_scan.py` | 附件 4 价格结构的独立复核。 |

## 六、已废弃（不随支撑材料提交）

| 文件 | 说明 |
| --- | --- |
| `p3_rolling_figures.py` | 问题三早期版本的出图脚本。它引用了 `p3_rolling_microgrid` 中后来被删除的函数名，且读取的 `p3_results.json`／`p3_detail.csv`／`p3_daily.csv`／`p3_combo_fees.csv` 已随旧版结果一并删除，**当前不可运行**。 |
| `p3_rolling_tables.py` | 同上，问题三早期版本的出表脚本，读取的旧结果文件已删除。 |

保留这两个文件仅为存档对照，论文与支撑材料中均不使用。
