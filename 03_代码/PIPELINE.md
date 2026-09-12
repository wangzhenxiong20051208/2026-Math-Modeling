# 溯源链：论文每个数字出自哪个脚本、哪个文件

本文件回答评委最可能问的一个问题：**论文里的数，是哪一行代码算出来的？**

阅读方式：每个问题一条链，箭头方向即数据流向。

```
    求解脚本  ──►  06_支撑材料/ 下的结果文件  ──►  出表/出图脚本  ──►  05_论文/CUMCMThesis/*.tex
```

约定：所有命令均从**仓库根目录**执行。`05_论文/CUMCMThesis/` 下的 `.tex`
全部由脚本生成、由 `main.tex` 以 `\input` 引入，**论文正文不手抄数字**。

---

## 问题一

| 环节 | 文件 |
| --- | --- |
| 求解 | `p1_microgrid.py` |
| 结果 | `06_支撑材料/result1.xlsx`（按附件 5 模板写出）、`p1_results.json`、`p1_detail.csv` |
| 出图 | `p1_figures.py` → `04_图/p1_fig1_profiles.png`、`p1_fig2_purchase.png`、`p1_fig3_storage.png`、`p1_fig4_balance.png` |
| 出表 | **无独立出表脚本**，问题一各表直接写在 `main.tex` 内 |

```bash
python 03_代码/p1_microgrid.py
python 03_代码/p1_figures.py
```

> `p1_results.json` 同时存放 MILP 最优值与两套 LP 松弛的下界
> （LP-1 结构松弛、LP-2 标准松弛），供正文的三者大小关系引用。

---

## 问题二

| 环节 | 文件 |
| --- | --- |
| 求解 | `p2_microgrid.py --core jia` |
| 结果 | `06_支撑材料/p2_results.json` |
| 出表 | `p2_tables.py` → `p2_tables.tex`（正文 3 张）、`p2_tables_appendix.tex`（附录 4 张） |
| 出图 | `p2_figures.py` → `04_图/p2_*.png` |

```bash
python 03_代码/p2_microgrid.py --core jia    # 必须带 --core jia
python 03_代码/p2_tables.py
python 03_代码/p2_figures.py
```

> **`--core jia` 是论文正文所用的内核，现已改为默认值**，因此直接
> `python 03_代码/p2_microgrid.py` 即可复现论文数字。
> 指纹校验：输出里 `1月离线选参.候选数` 应为 **180**（另一内核 `hybrid` 为 72）。
> 见 `README.md` 第七节 D1 行。

### 附录 λ 节（独立链路）

| 环节 | 文件 |
| --- | --- |
| 消融仿真 | `p2_lambda_ablation.py` → `p2_lambda_ablation.json` |
| 退化诊断 | `p2_lambda_diag.py` → `p2_lambda_diag.json`（**只读交付数据，不重跑仿真**） |
| 出表 | `p2_lambda_tables.py` → `p2_lambda_appendix.tex` |

```bash
python 03_代码/p2_lambda_ablation.py    # 须在 p2_microgrid.py 之后
python 03_代码/p2_lambda_diag.py
python 03_代码/p2_lambda_tables.py
```

> ⚠️ 这三份脚本此前**不在** `06_支撑材料/源码/` 内，该附录的数字无法由已提交
> 材料复现。见 `README.md` 第 6.2 节。

---

## 问题三

论文问题三的全部数字出自**下面这条链路**，与本目录的
`p3_rolling_microgrid.py` **无关**。

| 环节 | 文件 |
| --- | --- |
| 模型库 | `p3_microgrid.py` |
| 全年滚动回放 | `p3_backtest.py` |
| 汇总分析（主结果、8 种预报用法消融、敏感性与扰动、校验汇总、预报精度） | `p3_analysis.py` → `p3_analysis.json`、`p3_main_daily.csv`、`p3_main_arrays.npz`、`p3_forecast_skill.csv` |
| 交付件导出（逐日九项强制校验） | `p3_export.py` → `06_支撑材料/result3.xlsx`、`p3_spec.json` |
| 出表 | `p3_tables.py` → `p3_tables.tex`（正文表 1/2/3）、`p3_tables_appendix.tex`（附录） |
| 出图 | `p3_figures.py` → `04_图/p3_*.png` |
| 超参标定 | `p3_calibration.py` → `p3_calibration.json` |
| 附件 3 时间口径判定 | `p3_alignment_scan.py` → `p3_alignment_scan.json` |

```bash
python 03_代码/p3_backtest.py
python 03_代码/p3_analysis.py
python 03_代码/p3_export.py
python 03_代码/p3_tables.py
python 03_代码/p3_figures.py
```

### `p3_rolling_microgrid.py` 是什么

它是问题三的**早期版本实现**，`__main__` 流程会写 `p3_results.json` /
`p3_detail.csv` / `p3_daily.csv` / `p3_cache/`，但**这些文件不在交付材料内，
该流程也从未作为论文依据运行过**。

它被提交的唯一原因：问题四的求解器 `p4_microgrid.py` 直接 import 了它的内核
（`ForecastPanel`、`load_attach3`、`forecast_energy_slots`、`load_forecast_at`、
`build_eps3`、`solve_adjust`、`DayRunner`、`CalConfig3`、`ALL_S`、
`RELEASE_HOURS`、`BLOCK_BOUNDS`、`COEF_UP`、`COEF_DOWN`、`COEF_EMG`）。
**删掉它问题四就跑不起来。**

> ⚠️ **口径命名不要混淆。** 该文件里 `convention="norefund"` 表示计划费全额照付、
> 不允许调减退款；`convention="refund"` 是退款口径。论文
> `p3_section.tex` 所称的"主口径（退款）"对应的是**上面那条链路的
> `p3_microgrid.py`**，与该文件的 `norefund` 不是一回事。
> 该文件刻意不使用 `main` 这个词命名，以免被误读成论文主口径。

---

## 问题四

| 环节 | 文件 |
| --- | --- |
| 求解（价格预测、风险分位、两分支场景策略） | `p4_microgrid.py` |
| 结果 | `06_支撑材料/result4-2.xlsx`、`result4-3.xlsx`、`p4_results.json`、`p4_detail_42/43.csv`、`p4_daily_42/43.csv`、`p4_combinations.csv`、`p4_strategies.csv`、`p4_price_forecast_candidates.csv`、`p4_price_beta.csv`、`p4_risk_weight.csv` |
| 出表 | `p4_tables.py` → `p4_tables.tex`（正文）、`p4_tables_appendix.tex`（附录）、`p4_tables_refund.tex`（退款口径敏感性附录）、`p4_combo_detail.tex`（八组合边际价值明细） |
| 出图 | `p4_figures.py` → `04_图/p4_*.png` |
| 价格结构独立复核 | `p4_price_scan.py` |

```bash
python 03_代码/p4_microgrid.py     # 耗时最长，含两轮 1 月联合标定
python 03_代码/p4_tables.py
python 03_代码/p4_figures.py
```

> `p4_tables.py` 只读 `p4_results.json` 一个文件，**输入单一**；
> `p4_price_scan.py` 是对附件 4 价格结构的独立复核，不参与出表。

---

## 独立复核（与主链互不依赖）

| 文件 | 作用 |
| --- | --- |
| `solve2_final.py` | 问题二的独立参考实现，由另一位成员独立编写（标定网格、重选周期、回放窗口均独立设定），用于与 `p2_microgrid.py` 相互印证 |
| `p2_alphasweep.py` | 问题二 $\alpha$ 灵敏度扫描 |

---

## 已废弃、不参与任何链路

`p3_rolling_figures.py`、`p3_rolling_tables.py` —— 问题三早期版本的出图/出表
脚本，读取的旧结果文件已删除，**当前不可运行**。保留仅为存档对照。

---

## 复现顺序（一条命令跑完全部支撑材料）

```bash
python 03_代码/p1_microgrid.py
python 03_代码/p2_microgrid.py --core jia
python 03_代码/p2_lambda_ablation.py
python 03_代码/p2_lambda_diag.py
python 03_代码/p3_backtest.py
python 03_代码/p3_analysis.py
python 03_代码/p3_calibration.py
python 03_代码/p3_export.py
python 03_代码/p3_alignment_scan.py
python 03_代码/p4_microgrid.py

# 出表与出图
python 03_代码/p1_figures.py
python 03_代码/p2_tables.py
python 03_代码/p2_lambda_tables.py
python 03_代码/p3_tables.py
python 03_代码/p3_figures.py
python 03_代码/p4_tables.py
python 03_代码/p4_figures.py
```

> 顺序约束只有两条：`p2_lambda_ablation.py` 必须在 `p2_microgrid.py` 之后
> （它读 `p2_results.json`）；`*_tables.py` / `*_figures.py` 必须在对应的
> 求解脚本之后。其余可并行。
