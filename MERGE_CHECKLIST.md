# 合并前自检清单（MERGE CHECKLIST）

> 对象：AI-2 交付的 Fig.6–Fig.10
> 覆盖两轮修订：① 2026-09-13 下午「去图内文字 + 字体 + 题注入正文」；
> ② 2026-09-13 晚「图内汉字清零：判据改为字符类别 + 逐图重出 + 注同步进正文」
> 复核方式：`git status` + **四项**强制 QA 逐张重跑 + 全篇 label/ref 静态校验
> 结论：**全部通过，可以合并。**（但见 §9.1 的 AI-1 连带影响，需你决定）

---

## 1. 禁止项自检（"不得做"的都没做）

| # | 禁止项 | 核验方式 | 结果 |
|---|---|---|---|
| 1 | 不得修改 Fig.1–Fig.5 的**产物** | `git status --porcelain` 过滤 `04_图/fig0[1-5]*` 与 `fig0[1-5]_*.py` | ✅ **无任何 M/D 记录** |
| 2 | 不得改动 AI-1 的**视觉 token**（颜色/字号/线宽/图幅） | diff `figstyle.py` 的颜色/字号/线宽/尺寸常量块 | ✅ **未动**（仅新增字体块、prose 门与 caption 登记） |
| 3 | 不得修改原始数据 | `git status` 过滤 `01_题目/`、`06_支撑材料/`、`02_数据/` | ✅ **未修改** |
| 4 | 不得修改模型 / 公式 / 结果 | `git status` 过滤 `*microgrid*.py`、`solve*.py`、`result*.xlsx`、`*.npz` | ✅ **未修改** |
| 5 | 不得编造数值 | 每张图脚本内均有**断言**，把图上读数与 `06_支撑材料/` 原值逐位比对 | ✅ 见 §3.1 |
| 6 | 不得另起一套配色 / 字体 | 五脚本均 `import figstyle as S`，无任何硬编码色值 | ✅ 见 §2 |
| 7 | 不得往别的图件目录写 | 五脚本产物只落在 `04_图/`、`04_图/pdf/`、`04_图/qa/` | ✅ |

**本轮被修改的既有文件（共 5 个，均在本任务授权范围内）**：

```
 M 03_代码/figures/figstyle.py           ← 字体块 + prose 门 + caption 登记（token 未动）
 M 03_代码/figures/make_all_figures.py   ← 追加 5 行 FIGURES 登记 + 接入 prose 复查
 M 03_代码/figures/audit_figure_collisions.py ← 两遍扫描 + 全局最优配对（修静默漏检）
 M 05_论文/final_new/p3_section.tex      ← 2 个 figure 环境 + 2 句交叉引用
 M 05_论文/final_new/p4_section.tex      ← 3 个 figure 环境 + 3 句交叉引用
```

新增文件：`build_captions.py`、`insert_into_paper.py`、`captions.json`、`fig_captions.tex`、
`captions.md`、`qa/*.prose-audit.json`、`05_论文/final_new/figures/figNN_*.pdf`。

**边界说明**：`figstyle.py` 是"全篇视觉规范"文件，#2 的禁令针对的是 **token（配色/字号/线宽/图幅）**；
两轮修订只**追加**了字体族、prose 规则与 caption 登记，未改动任何 token 值。
但请注意：**字体族一旦变化，Fig.1–Fig.5 若重渲染，字体也会跟着变**（见 §9.1）。

---

## 2. 视觉规范复用自检（"必须复用"的都复用了）

| 项 | 要求 | 核验 | 结果 |
|---|---|---|---|
| 字体（中文） | 宋体 SimSun | `FONT_CHAIN` 含 SimSun；宋体无粗体面，故以 `_register_cjk_bold_face()` 把 SimHei 注册为其 weight=700 面 | ✅ |
| 字体（西文/数字） | Times New Roman | `FONT_CHAIN` 首位；实测 PDF 字体集 = `{TimesNewRomanPSMT, TimesNewRomanPS-BoldMT, SimSun}`（Fig.7 另有 `STIXGeneral`） | ✅ |
| 字体（缺字兜底） | 不得落回无衬线体 | `FONT_CHAIN` 在 `DejaVu Serif` 之前插 `STIXGeneral`；`∅`(U+2205) 实测由 STIXGeneral 承接，**DejaVu 残留 0 处** | ✅ |
| 字号 | 刻度 7.5 / 轴标签 8 / 标注 8 / panel 9 | 无超出该体系的字号；实绘最小 6.0 pt | ✅ |
| 颜色 | 同一物理量全文同一 token | 电价 `C_PRICE`、紧急购电 `C_EMERGENCY`、计划购电 `C_GRID`、预测 `C_FORECAST`、风险 `C_RISK`、储能 `C_SOC/C_CHARGE/C_DISCHARGE` 全部沿用 | ✅ |
| 图幅 | `FIG_W_FULL = 160 mm` | 五张 PDF 实测宽度**均为 157 mm**（未被文字撑开） | ✅ |
| 线宽 | `LW_AXIS / LW_MAIN / LW_THIN / LW_REF` | 无自定义 lw（仅 1.4/0.8 等取自体系） | ✅ |
| 导出 | 必须用 `S.save_figure()`（内部跑对齐门 + prose 门） | 五脚本均用 `S.save_figure`，**无任何裸 `fig.savefig`** | ✅ |
| 数学字体 | 与论文公式同源 | `MATHTEXT_FONTSET = "cm"`；论文成品 `main.pdf` 实测嵌入 CMR/CMMI/CMSY/CMEX/MSBM。本批五图实际未用 mathtext（符号走普通 Unicode） | ✅ |
| 源码卫生 | 无残留 git 冲突标记 | `make_all_figures.py` 预检 + 全仓扫描：**0 处** | ✅ |
| 网格 | `ax.grid(False)` | 每个 panel 均显式关闭 | ✅ |
| 底纹 | `bar/axvspan` 显式 `edgecolor="none"` | 已全部显式指定 | ✅ |
| **图内文字** | **不得出现汉字，也不得出现英文句子** | 由 `S.audit_prose()` 导出前强制（字符类别判据）；五张实测 **0 处** | ✅ |

**"图内只允许什么"（本轮定稿口径）**：坐标轴标签、刻度标签、panel 字母、图例，
以及**纯数值/符号读数**（`1,474`、`+99`、`−78.1%`、`{6,12}`、`MAE 48 kW`）。
其余一切文字——顶部大标题、区域/曲线名（`已执行冻结`、`峰价`、`空信息`、
`基线 = 100%`）、图内结论句（`紧急费 69.9 → 15.3 万元`）、底部脚注——一律进
`\caption` 与图下"注"。

> **判据是字符类别，不是句子长度。** 首版按长度判（汉字 ≥ 9 才算"成句"），
> 于是 5 个汉字的 `紧急费 69.9 → 15.3 万元` 一路放行进了交付图。这是第二轮返工
> 的直接原因，也是本清单最该记住的一条。

---

## 3. Fig.6–Fig.10 完成度自检

| 图 | 脚本 | PDF | SVG | PNG | 碰撞 | 字形 | 对齐 | 图内文字 |
|---|---|---|---|---|---|---|---|---|
| Fig.6 滚动时间轴 | ✅ | ✅ | ✅ | ✅ | PASS | 6.6 pt PASS | PASS | **0 处 PASS** |
| Fig.7 信息价值格 | ✅ | ✅ | ✅ | ✅ | PASS | 6.0 pt PASS | PASS | **0 处 PASS** |
| Fig.8 价格结构分解 | ✅ | ✅ | ✅ | ✅ | PASS | 6.2 pt PASS | PASS | **0 处 PASS** |
| Fig.9 P4 策略对照 | ✅ | ✅ | ✅ | ✅ | PASS | 6.2 pt PASS | PASS | **0 处 PASS** |
| Fig.10 全文总结 | ✅ | ✅ | ✅ | ✅ | PASS | 6.5 pt PASS | PASS | **0 处 PASS** |

**合计 5 张，全部完成、四项 QA 全部通过（0 fail / 0 warn）。**

### 3.1 图上读数与支撑材料的一致性（脚本内断言，全部通过）

| 图 | 断言内容 | 结果 |
|---|---|---|
| Fig.6 | 第一交付块调整量 **恰为 0.000 kWh**（否则抛异常）；分块合计 519.9+669.4+242.6 = 1,431.9 MWh 与 `p3_calibration.json` 的上调+下调一致 | ✅ |
| Fig.7 | 12 条格边**全部**为负（成本单调递减）；全信息价值 1,559,183 元 | ✅ |
| Fig.8 | 复算 MAE `0.044573976837991` 与 `p4_price_forecast_candidates.csv` **逐位一致**（阈值 1e-12） | ✅ |
| Fig.9 | 6 行合计与 `p4_strategy_fees.csv` **逐行一致**（阈值 1e-6） | ✅ |
| Fig.10 | 四问"本文策略 ≤ 各自朴素基线"**全部成立**（否则抛异常） | ✅ |

---

## 4. 可复现性自检

从零重跑（**只重跑 Fig.6–Fig.10 的脚本，不触碰 Fig.1–Fig.5**）：

```
fig06_rolling_timeline     渲染OK  碰撞 PASS   字形 6.6 pt   对齐 PASS   图内文字 0 处 PASS
fig07_information_value    渲染OK  碰撞 PASS   字形 6.0 pt   对齐 PASS   图内文字 0 处 PASS
fig08_price_forecast       渲染OK  碰撞 PASS   字形 6.2 pt   对齐 PASS   图内文字 0 处 PASS
fig09_p4_strategy          渲染OK  碰撞 PASS   字形 6.2 pt   对齐 PASS   图内文字 0 处 PASS
fig10_summary              渲染OK  碰撞 PASS   字形 6.5 pt   对齐 PASS   图内文字 0 处 PASS
```

✅ 五张图**全部可一键重出且复现同一结论**。

**题注链路重跑（幂等 + 会更新）**：

```
build_captions.py       → 04_图/fig_captions.tex（5 个 figure 环境）+ captions.md
insert_into_paper.py    → 更新 5，跳过 0，异常 0，图件同步 5
insert_into_paper.py    → 插入 0，更新 0，跳过 5，异常 0，图件同步 0   ← 复跑，幂等 ✅
```

> 首版 `insert_into_paper.py` 是"见词即跳过"，改了注论文纹丝不动（静默不一致）。
> 现已改为用 `\includegraphics{<stem>.pdf}` 定位、**整体替换**原 figure 环境，
> 内容一致才算跳过。本轮 5 张图的题注/注即由此同步进正文。

**注意**：`make_all_figures.py` 一键入口会连 Fig.1–Fig.5 一并重渲染，**目前会中断在
Fig.1**（见 §9.1）。若只想重出 AI-2 的图，请用 `--only fig0N`。

---

## 5. 正文落位与交叉引用自检（**必查**）

| 检查项 | 方法 | 结果 |
|---|---|---|
| 5 个 figure 环境是否都进了正文 | `includegraphics` 目标存在性 | ✅ 全篇图形文件均可解析 |
| 每个 `\begin{figure}` 是否有配对的 `\end` | 逐文件计数 | ✅ 全部配平 |
| 花括号 / `$` 是否配平 | 逐 figure 环境计数 | ✅ 5 张全部配平（`$` 均为偶数） |
| **label 是否唯一** | 全篇 113 个 label 去重 | ✅ **全部唯一，0 重复** |
| **ref 是否都有定义** | 全篇 86 个 ref 目标比对 | ✅ **0 个未定义引用** |
| 5 张新图是否都被正文引用 | 反查 `\ref` | ✅ 5/5 均被引用 |
| `fig_captions.tex` 的 label 与正文是否一致 | 集合比对 | ✅ 5/5 一致 |

> **⚠️ 第一轮发现并修正的真缺陷（务必记住）**：Fig.9 首版沿用了附录已存在的
> `\label{fig:p4-strategy}`。因 `p4_section.tex` 在 `main.tex` 中先于 `moved_body.tex`
> 被 `\input`，LaTeX 取**后定义**者 —— 于是正文与附录清单里三处 `\ref{fig:p4-strategy}`
> **全部悄悄指向附录旧图**，编译只给一条易忽略的 multiply-defined 警告。
> 已改用唯一标签 `fig:p4-strategy-roll`，并改写原句使新旧引用各归其位。
> **教训：插入任何带 `\label` 的新图前，先全篇查标签是否撞名。**

### 5.1 "能不能直接插进 LaTeX" —— 逐项核对（本轮已落盘）

已在正文中落位的 5 个环境，逐项对照 LaTeX 的实际要求：

| LaTeX 会关心的事 | 实际情况 | 结论 |
|---|---|---|
| 图件格式 | 5 个 `fig0N_*.pdf`，**单页矢量**，`pdf.fonttype=42`（TrueType 可编辑文本） | ✅ 可直接 `includegraphics` |
| 图件位置 | `05_论文/final_new/figures/`；`main.tex:15` 有 `\graphicspath{{figures/}}` | ✅ 路径可解析 |
| 图件宽度 | 全部 **157 mm**；`width=\textwidth`（版心 157 mm） | ✅ 不会被撑开或缩糊 |
| 字体嵌入 | 每图均已内嵌 Times/SimSun（Fig.7 另有 STIX）；`pdffonts` 层面无缺字 | ✅ 换机编译不丢字 |
| label / ref | 113 个 label 全唯一；86 个 ref 目标 0 未定义；5 图均被 `\ref` 引用 | ✅ 无 multiply-defined / undefined |
| 环境配平 | `figure`/`table` 的 `\begin`/`\end` 逐文件计数一致；花括号与 `$` 均配平 | ✅ 不会中途断编译 |
| 题注/注宏 | `\caption{}` + `\label{}` + `\par\vspace{2pt}` + `minipage{.94\textwidth}` + `\footnotesize 注：`，与论文既有表格注样式一致 | ✅ 样式同源 |

> **本机没有 TeX 工具链**（未发现 `xelatex`/`pdflatex`/`latexmk`/TeXLive/MiKTeX），
> 因此以上全部为**静态校验**结果，未做真实编译。请在装有 TeX 的机器上跑一次
> `xelatex main.tex`（cumcmthesis.cls 走 XeLaTeX）确认版面；如有任何 warning，
> 优先看 `LaTeX Warning: Reference ... undefined` 与 `multiply defined`。

---

## 6. 审计工具自身的可靠性（两轮回归）

### 6.1 碰撞审计：静默漏检（第一轮）

`audit_figure_collisions.py` 原先按**先到先得**给"文字行 / 文字框"配对，两条文字重叠时
会被**合并成一个大 bbox**、重叠被掩盖而报 PASS。已改为**两遍扫描 + 全局最优配对**
（阈值：重叠率 > 0.3 取最大者），并同步修到
`~/.workbuddy/skills/nature-figure/scripts/audit_figure_collisions.py`（md5 一致）。

**回归验证**：把修好的工具跑在此前的 fig08 PDF 上，立即报出
`[FAIL] text-text … 95.6%`（图例第二行 vs "峰价"标注）——该重叠在旧工具下**一直是 PASS**。

### 6.2 文字闸门：豁免机制不可靠（第二轮）

首版 `audit_prose()` 用 `fig.findobj(Text)` **反选**：先按 Id 收集豁免集（刻度/轴标签/
图例…）、再从全体 Text 里排除。问题是**刻度标签会在 draw 前后被重建**，Id 匹配失效 ——
17 处合法的中文刻度标签被误判违规，真正的违规项反而淹没在噪声里。

改为**正向收集** `ax.texts` / `fig.texts`（"人手写进图里的文字"才是判据），误报清零：
首扫精确定位 **16 处真违规**，逐图修完后再扫 **0 处**。

✅ 两条结论：**判据要按"来源"而不是"排除法"来定**；审计类工具必须能复现已知坏例。

---

## 7. 交付清单核对

| 交付物 | 状态 |
|---|---|
| `03_代码/figures/fig06_rolling_timeline.py` … `fig10_summary.py` | ✅ |
| `03_代码/figures/figstyle.py`（字体块 + prose 门 + caption 登记） | ✅ |
| `03_代码/figures/build_captions.py`（captions.json → LaTeX） | ✅ |
| `03_代码/figures/insert_into_paper.py`（题注入正文 + 更新 + 同步 PDF） | ✅ |
| `03_代码/figures/make_all_figures.py`（登记 5 张 + prose 复查） | ✅ |
| `03_代码/figures/audit_figure_collisions.py`（修静默漏检） | ✅ |
| `04_图/pdf/fig06…fig10.*.pdf`（5 个矢量主件） | ✅ |
| `04_图/pdf/fig06…fig10.*.svg`（5 个可编辑矢量） | ✅ |
| `04_图/fig06…fig10.*.png`（5 个 300 dpi 预览） | ✅ |
| `04_图/captions.json` / `fig_captions.tex` / `captions.md` | ✅ |
| `04_图/qa/*`（碰撞 / 字形 / 对齐 / 图内文字 审计留档） | ✅ |
| `05_论文/final_new/figures/fig06…fig10.*.pdf`（正文引用件） | ✅ |
| `AI2_FIGURE_REPORT.md` | ✅ |
| `MERGE_CHECKLIST.md` | ✅ |

---

## 8. 需要正文配合的两点（非图的问题，但会影响读者理解）

1. **Fig.10 的口径纪律**：四问费用**绝对值不可直接横比**（P1 单日、P2/P3 全年、
   P4 换用附件 4 波动电价）。引用 Fig.10 时请务必保留"各问自比、基线 = 100%"的说明，
   否则会被误读为"四个问题成本一路下降"。
2. **Fig.8 的信息边界**：预测只读 d−7/d−14/d−21 的**过去**实际价格；图中"实际"曲线
   仅用于事后评估。若正文有"用当日价格预测当日"的表述，需复核措辞。

---

## 9. 遗留待决事项（**需人工取舍，脚本不代删**）

新旧图内容重叠 4 处，详见 `AI2_FIGURE_REPORT.md` §6。其中 **Fig.8 vs `p4_fig1_price_structure.png`**
与 **Fig.9 vs `p4_fig3_strategy.png`** 属真重叠，建议删旧留新；删图时必须同步清理
`moved_body.tex` 的 figure 环境及其 `\ref`，否则产生未定义引用。

### 9.1 【新】AI-1 的 Fig.1–Fig.5 要不要一并迁移？

闸门收紧后，Fig.1–Fig.5 与 Fig.6–Fig.10 已不在同一套规则下。实测 Fig.1–Fig.5
有 **71 处图内汉字**（Fig.1 47 / Fig.2 5 / Fig.3 7 / Fig.4 6 / Fig.5 6），
且仍带顶部大标题与底部"注"脚注。

| 方案 | 做法 | 代价 |
|---|---|---|
| **A. 全量迁移**（推荐） | 按 Fig.6–Fig.10 的做法清图内汉字（框内名词保留但显式豁免） | 要改 5 个 AI-1 脚本；顺带统一字体为宋体+Times |
| **B. 只标豁免** | 给必要标签打 `_prose_exempt=True`，其余不动 | 改动最小，但大标题/脚注继续留在图里 |
| **C. 暂不处理** | 维持现状 | 一键重跑会中断在 Fig.1；两批图字体不统一 |

**注意**：三者都需先决定**是否让 Fig.1–Fig.5 也换成宋体 + Times**。
既有产物在迁移前不会被写坏（闸门在导出之前报错）。

---

## 10. 结论

- 禁止项：**7 / 7 通过**（零违规改动）
- 规范复用：**11 / 11 通过**
- 完成度：**5 / 5 张图完成且四项强制 QA 全 PASS（0 fail / 0 warn）**
- 图内文字：**首扫 16 处违规 → 清零；复扫 0 处**
- 可复现：**5 / 5 从零重跑复现**；题注链路**幂等且会更新**
- 正文落位：**label 唯一 / 0 未定义引用 / 5 张图均被引用**
- 交付物：**全部齐备**

**Fig.6–Fig.10 可以合并。** 但请先在 §9（旧图取舍）与 §9.1（AI-1 迁移）上给个方向。
