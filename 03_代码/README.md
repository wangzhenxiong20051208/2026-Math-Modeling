# 03_代码 文件说明

本目录是论文的**全部建模、求解、分析与绘图代码**，共 $26$ 个 Python 脚本。

随支撑材料提交的副本位于 `06_支撑材料/源码/`，已与本目录的 $26$ 个 `.py`
脚本同步（含附录 λ 节三脚本与两份问题三早期出图表脚本）。复现以本目录为准。

> **想知道论文里某个数字出自哪个脚本、哪个文件？** 见 [`PIPELINE.md`](PIPELINE.md)，
> 那里按问题画出了「求解脚本 → 结果文件 → 出表脚本 → `.tex`」的完整溯源链，
> 并给出一条命令跑完全部支撑材料的复现顺序。

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
| `p4_microgrid.py` | **问题四**：价格预测器 + 风险分位数 + 场景策略（4-1 价格预测、4-2 分位数余量、4-3 网格标定）。 |

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
| `p2_tables.py` / `p3_tables.py` / `p4_tables.py` | 生成 `05_论文/CUMCMThesis/` 下的 `*.tex` 表格。`p3_tables.py` 输出 `p3_tables.tex`（正文）与 `p3_tables_appendix.tex`（附录）。 |
| `cumcm_plot.py` | 绘图样式与中文字体配置，被四个绘图脚本 import。 |

## 五、独立复核与辅助脚本

| 文件 | 作用 |
| --- | --- |
| `solve2_final.py` | **问题二的独立参考实现**，由另一位成员独立编写（标定网格、重选周期、回放窗口均独立设定），用于与 `p2_microgrid.py` 相互印证。 |
| `p2_alphasweep.py` | 问题二的 $\alpha$ 灵敏度扫描。 |
| `p4_price_scan.py` | 附件 4 价格结构的独立复核。 |

## 六、未随支撑材料提交的脚本

### 6.1 已废弃（论文与支撑材料均不使用）

| 文件 | 说明 |
| --- | --- |
| `p3_rolling_figures.py` | 问题三早期版本的出图脚本。它引用了 `p3_rolling_microgrid` 中后来被删除的函数名，且读取的 `p3_results.json`／`p3_detail.csv`／`p3_daily.csv`／`p3_combo_fees.csv` 已随旧版结果一并删除，**当前不可运行**。 |
| `p3_rolling_tables.py` | 同上，问题三早期版本的出表脚本，读取的旧结果文件已删除。 |

保留这两个文件仅为存档对照，论文与支撑材料中均不使用。

### 6.2 论文附录 λ 节的生成链（**需要补交**）

| 文件 | 说明 |
| --- | --- |
| `p2_lambda_ablation.py` | 问题二日末储备惩罚 $\lambda$ 的全年消融：$5$ 个 $\lambda$ × $3$ 组 $(\alpha,\rho)$ 共 $15$ 臂，固定 $(\alpha,\rho)$、关闭滚动标定以隔离 $\lambda$ 单一变量；另反解 1 月选参准则的库存盈亏平衡单价 $v^*$。写出 `p2_lambda_ablation.json`。 |
| `p2_lambda_diag.py` | $\lambda=0$ 冻结后参考轨迹 $\bar E$ 的退化诊断与储备线 $R_t$ 卡住放电的机制分解。**只读已有交付数据、不重跑仿真**，因此可在交付数据上独立复核。写出 `p2_lambda_diag.json`。 |
| `p2_lambda_tables.py` | 由上述两个 json 生成论文附录 λ 节的两张表；`05_论文/CUMCMThesis/p2_lambda_appendix.tex` 由它自动生成（见该文件首行注释）。 |

这三份脚本是论文附录 λ 节的生成链，已纳入 `06_支撑材料/源码/`。

## 七、本轮代码修正清单

论文正文与附录中的部分表述与代码不一致，已以代码为准修正。下列修正**改变了
输出数字**，论文相应段落需同步改写；列出"影响"一列便于定位。

| 编号 | 文件 | 修正内容 | 对数字的影响 |
| --- | --- | --- | --- |
| C3 | `p1_microgrid.py` | 问题一决策变量统一为**电量口径（kWh）**：功率输入先乘 $\Delta t$，与论文"决策变量为电量"一致（原实现为功率）。 | 结果值不变，量纲口径与论文对齐 |
| C4 | `p1_microgrid.py` | 区分两套 LP 松弛并各自命名：**LP-1 结构松弛**（删去 $z_t$ 与 $288$ 条互斥约束，$n=720$）与 **LP-2 标准松弛**（保留 $z_t$、仅令 $0\le z_t\le1$，$n=864$）。三者满足 $\text{LP-1}\le\text{LP-2}\le\text{MILP}$。 | 下界值不变，但论文须写明用的是哪一套 |
| C5 | `p1_microgrid.py` | 大 $M$ 改用**电量上界** $M=P_{\max}\Delta t=2500/3\approx833.333$ kWh（原实现误把 $P_{\max}=5000$ 当作 kWh 上界，是 $6$ 倍单位错误）。 | $A_{ub}$ 非零系数集由 $\{0,\pm1,\pm5000\}$ 变为 $\{0,\pm1,\pm833.333\}$，与论文所列系数集一致 |
| C6 | `p3_rolling_microgrid.py` | 预报锚点改为**发布时刻已实现的实际功率**（`pv_kw[n, 36*hi-1]`），与其余问题三脚本一致（原为上一版预报）。 | 全年 MAE $191.51\to189.81$；对照值 $808.67\to808.24$、$268.02\to267.40$ |
| C1 | `p2_lambda_diag.py` | 储备线卡放电的机制分解改为**数据驱动的双向分档**（按 $R$ 水平、按 $\bar E$ 是否贴上限），不再断言未经检验的"显著高于"；$\rho$ 的取值分布**按天计数**报出（原误把时段数当天数）；新增 NaN 安全的比值出口。 | 原引用的 $9.13\%/7.81\%$ 复现不出，改报 $5.37\%$（口径a）与真实被卡住的 $1.42\%$／占紧急购电 $24.71\%$ |
| C2 | `p2_microgrid.py` | 三个对照策略的储电量不再只报期末值：`strategy_totals` 统一输出**期初／期末／净动用／可比费用**，并以全时段平均电价 $p_{\text{ref}}$ 折算库存变动。参考电价抽成 `reference_price()` 供各脚本共用，保证汇总表可比。 | 新增可比费用列；各策略期初值 $2287.68/7097.30/0$ 显式报出 |
| C2′ | `p2_microgrid.py` | “事后理想”对照此前把 `计划购电量`、`弃电量` 及逐日的 `plan_kwh`／`E_end` 硬编码为 `nan`，却同时报出费用，**费用无量支撑**。现由每日 MILP 的 `plan.g`／`plan.wb` 实际累加（与 `计划购电费 = Σ p·g` 同源）。 | 该行不再是 NaN；全表已无 NaN |
| C2″ | `p2_tables.py` | **待改（属论文表）**：对照表目前只列「期末储电量」，未列期初储电量与可比费用，C2 的核心（各策略进入评价区间时储电量不同）仍未呈现。数据侧已具备所需字段。 | 另：「事后理想」的期末储电量原为 `nan` 故表里渲染成 `---`，现为 $1\,200.0$，**重跑 `p2_tables.py` 后该格会由 `---` 变为 $1{,}200.0$** |
| D1 | `p2_microgrid.py`、`p2_alphasweep.py` | `--core` 默认值由 `hybrid` 改为 **`jia`**（论文正文所用内核）。原先按默认参数运行得到的是另一个内核的结果，**复现不出论文任何数字**。 | 默认运行即复现论文数字；`hybrid` 仅供对照 |
| D2 | `p3_rolling_microgrid.py`、`p4_microgrid.py` | 两件事：①文件头明确声明**本文件不是问题三论文数字的来源**（真实链路是 `p3_microgrid.py` → `p3_backtest.py` → `p3_analysis.py` → `p3_export.py`），它仅为问题四提供内核；②计费口径枚举 **`"main"` 改名为 `"norefund"`**（共 $30$ 处：p3 侧 $18$、p4 侧 $12$），消除与论文"主口径（退款）"的歧义。 | **无**（纯改名，行为逐字等价；两文件 `py_compile` 通过，改后无残留 `"main"`） |
| D2′ | `03_代码/PIPELINE.md` | 新增。按问题画出「求解脚本 → 结果文件 → 出表/出图脚本 → `.tex`」的完整溯源链，附一条命令跑完全部支撑材料的复现顺序。 | 无（文档） |
| — | `p3_alignment_scan.py` | 修正失效的 import（原引用 `p3_microgrid.load_attach2`，该函数在 `p2_microgrid` 中），脚本此前完全无法运行。 | 见 C6 行 |
| — | `p2_lambda_ablation.py`、`p2_alphasweep.py` | 修正 `strategy_totals` 签名变更后遗留的调用点（少传参考电价），两脚本此前均因 `TypeError` 无法运行。 | 无（修复运行能力） |
| — | `p4_microgrid.py` 等 $6$ 个文件 | 清除 `print` 输出中的非 GBK 字符（`↔`、`Ē`、`−`、`∅`、`⚠`）。这类字符在中文 Windows 控制台**重定向输出时会抛 `UnicodeEncodeError` 并中断整个求解**。 | 无（修复可运行性；P4 此前完全无法运行） |

> 注：`p2_lambda_diag.py`、`p2_lambda_ablation.py` 的 JSON 键名与注释中仍保留
> $\bar E$ 等符号（JSON 按 UTF-8 写盘、注释不参与输出，均无编码风险）；仅
> **会到达 stdout 的字符串**做了 ASCII 化。

> 注（D2 改名的一处副作用）：`p4_microgrid.py` 的计划缓存 `06_支撑材料/p4_cache/`
> 以 `模式|口径|集合` 为标签、经 `_safe_tag()` 变换后作文件名。改名后旧条目
> （`..._main_...`）不会被命中，只会**多算一次**，不存在读到旧口径结果的风险。
> 若想省这一次重算，可自行删除 `06_支撑材料/p4_cache/` 后重跑——本清单不代为删除。
