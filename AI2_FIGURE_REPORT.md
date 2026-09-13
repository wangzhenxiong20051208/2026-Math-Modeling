# AI-2 图表重构报告（Fig.6–Fig.10）

> 交付日期：2026-09-13　|　负责范围：Fig.6–Fig.10
> 前序：AI-1 已完成 Fig.1–Fig.5 并建立全篇视觉规范（`03_代码/figures/figstyle.py`）
> 状态：**五张图全部渲染完成，并通过四项强制 QA（碰撞 / 字形 / 多面板对齐 / 图内禁成句文字），
> 题注已按"图题 + 注"格式写入正文。**

---

## 0. 一句话结论

论文原先把"问题三"压成一张"四条预测曲线"，把"问题四"压成一张"价格折线"，
读者看不到**机制**。本次新增的五张图各回答一个**不看图就想不明白**的问题：

| 图 | 一句话论断 | 关键读数 |
|---|---|---|
| Fig.6 | 已提交的 6 h 交付块**永久冻结**，新预报只改变未来 | 第一交付块调整量 **0.000 MWh**，334 天中 0 天有调整 |
| Fig.7 | 预测信息的价值 = 已有信息集下**新增信息让成本降多少** | 全信息价值 **155.92 万元**；12 条格边**全部**单调递减 |
| Fig.8 | 价格 = 附件 1 日内形状 + **星期几的缓慢漂移**，故同星期加权成立 | 形状一致 5.15e−05；周五六低 **0.1913 元/kWh**；MAE **0.0446** |
| Fig.9 | 允许**滚动调整**后，尾部代价（紧急购电费）**减半** | 紧急费 69.89 → **15.31 万元（−78.1%）**；总费用 −3.99% |
| Fig.10 | 四问逐层叠加，**每层都相对自己的朴素基线更省** | 费用指数 **73.1 / 93.5 / 89.6 / 99.7 %** |

**未改动任何数学模型、任何原始数据、任何 AI-1 的图件。** 五张图全部从
`06_支撑材料/` 与 `01_题目/C题/附件/` 的真实输出读取，只做减法、差分与加权平均，
**不重算、不编造**。

---

## 0.1 修订（2026-09-13 下午）：去图内成句文字 + 字体 + 题注入正文

按评审意见做的一轮**纯版面**修订，不触碰任何数值与模型。

| 项 | 修订前 | 修订后 |
|---|---|---|
| **图内文字** | 顶部大标题、图内结论句、底部脚注都画在图里 | **图内只留**坐标轴标签 / 刻度数字 / panel 字母 / 图例 / 数据标签；**全部成句文字移入 `\caption` 与图下"注"** |
| **字体** | 中文回退链 + 全图禁用 mathtext（用普通 Unicode 拼公式） | **中文宋体（SimSun）+ 西文/数字 Times New Roman**；回退链补 `SimHei`（宋体无粗体面）与 `STIXGeneral`（补 `∅` 等 Times 缺字）；mathtext 走 `cm` 与正文公式同源 |
| **图幅** | 五张宽度 158 mm | 五张宽度 **157 mm**（去掉大标题后纵向收紧，见下表高度） |
| **题注落位** | 无 | 每图生成 `\caption{}` + `\label{}` + `\footnotesize 注：…`，并**按语义锚点插入正文** |

**新增的四道工序**（全部脚本化、可一键重跑）：

```
图脚本  ──save_figure(caption=, note=)──▶  04_图/captions.json
        ──build_captions.py──────────▶  04_图/fig_captions.tex + captions.md
        ──insert_into_paper.py────────▶  05_论文/final_new/{p3,p4}_section.tex
                                        + 同步 figures/*.pdf
```

**新增的第 4 道 QA 门：图内禁文字（prose gate）**

在 `figstyle.save_figure()` 内**导出前**强制执行。判定对象是**图内"自由文字"**——
即 `ax.text` / `ax.annotate` / `fig.text` 显式写上去的那些；坐标轴标签、刻度标签、
panel 字母、图例**天然不在这个集合里**，因而自动豁免（参考画法里中文刻度标签
`预测均值策略（不加风险余量）` 是合法的）。

判定规则（`_forbidden_reason()`）：

- 出现**任何汉字**，或任何允许字符集之外的字符（全角括号、全角标点）→ 违规；
- 或英文单词数 > 3 → 违规（判为英文句子）。

**判据是字符类别，不是句子长度。** 首版按长度判（汉字 ≥ 9 才算"成句"），
于是 `紧急费 69.9 → 15.3 万元`（5 个汉字）一路放行，直接进了交付图——
这是本轮返工的直接原因。违规时抛 `ProseInFigureError` **阻断导出**，
并把违规项与理由写入 `04_图/qa/<stem>.prose-audit.json`。

五张图实测：首扫 **16 处违规**（Fig.6 一处 `已执行冻结`、Fig.7 六处、Fig.8 三处、
Fig.9 一处 `紧急费 69.9 → 15.3 万元`、Fig.10 五处），逐一移入 `\caption`/注后
**0 处（PASS）**。图内最终只剩：坐标轴标签、刻度标签、panel 字母、图例，
以及纯数值读数（`1,474`、`+99`、`−78.1%`、`{6,12}`、`MAE 48 kW`）。

**最终尺寸与四项 QA（重跑实测）**

| 图 | 页宽×高 (mm) | 碰撞 | 字形 | 对齐 | 图内文字 |
|---|---|---|---|---|---|
| Fig.6 滚动时间轴 | 157 × 105 | PASS | 6.0 pt PASS | PASS | **0 处 PASS** |
| Fig.7 信息价值格 | 157 × 78 | PASS | 6.0 pt PASS | PASS | **0 处 PASS** |
| Fig.8 价格结构分解 | 157 × 107 | PASS | 6.2 pt PASS | PASS | **0 处 PASS** |
| Fig.9 P4 策略对照 | 157 × 107 | PASS | 6.2 pt PASS | PASS | **0 处 PASS** |
| Fig.10 全文总结 | 157 × 81 | PASS | 6.3 pt PASS | PASS | **0 处 PASS** |

**题注落位与标签**（全部已写入正文，且**全篇 label 唯一、无未定义引用**）

| 图 | 落位 | 标签 | 图题 |
|---|---|---|---|
| Fig.6 | `p3_section.tex` §模型框架 | `fig:p3-rolling-timeline` | 问题三的滚动决策时间轴：新预报只改变未来，已提交的 6 h 交付块永久冻结 |
| Fig.7 | `p3_section.tex` §结果分析（1） | `fig:p3-info-value` | 预测信息的价值取决于已掌握的信息：边际价值递减，但始终为正 |
| Fig.8 | `p4_section.tex` §附件 4 的电价结构 | `fig:p4-price-structure` | 附件 4 电价的结构分解：价格 = 附件 1 的日内形状 + 星期几的缓慢漂移 |
| Fig.9 | `p4_section.tex` §策略对照 | `fig:p4-strategy-roll` | 允许滚动调整后，尾部代价（紧急购电费）减半，全年总费用因此降 3.99% |
| Fig.10 | `p4_section.tex` §本节小结末 | `fig:summary` | 四问逐层叠加：每一层都相对自己的朴素基线更省，尾部代价同步压缩 |

> **⚠️ 插入时发现并修正的一处真缺陷（`\label` 撞名）**
> Fig.9 首版沿用了 `\label{fig:p4-strategy}`，而该标签**已存在于附录**
> （`moved_body.tex` 的 `p4_fig3_strategy.png`）。因 `p4_section.tex` 在 `main.tex`
> 中**先于** `moved_body.tex` 被 `\input`，LaTeX 会取**后定义**的那个 —— 结果是正文
> 第 316/331 行与附录清单（`main.tex:2230`）三处 `\ref{fig:p4-strategy}` **全部悄悄
> 指向了附录的旧图**，且编译只给一条容易忽略的 multiply-defined 警告。
> 已把新图标签改为唯一的 `fig:p4-strategy-roll`，并把原句改写为
> "…见图~\ref{fig:p4-strategy-roll}，逐分支的原始记录见附录图~\ref{fig:p4-strategy}。"，
> 使新旧引用各归其位。**这是"插入新图"这一类操作最容易踩的坑：先查 `\label` 是否撞名。**

**顺带补齐的交叉引用**：五张新图原先在正文里**都没有被 `\ref` 引用**（只是一张漂浮的图）。
已各补一句引用（"…见图~\ref{...}。"），使每张图都有正文出处。

---

## 0.2 修订（2026-09-13 晚）：图内汉字清零 —— 判据改为"字符类别"

评审指出 Fig.9 图内仍留有 `紧急费 69.9 → 15.3 万元`。复查后确认问题在**闸门判据**
而非个别遗漏：按长度判句，短标签天然漏网。本轮把判据换成字符类别（见 0.1 末节），
并逐图清掉所有图内汉字。

| 图 | 清掉的图内汉字 | 去处 |
|---|---|---|
| Fig.6 | panel (b) 灰带内 `已执行` / `冻结` | 移入注；灰带改染 `C_FROZEN`，与 panel (a) 图例同色，靠颜色映射表意 |
| Fig.7 | 格图左沿四行层级名（空信息 / 单条预报 / 两条预报 / 三条全用）、`0（基线）`、`单条最好 117.8` | 层级名移入注；后两处各只留数值 `0`、`117.8` |
| Fig.8 | `峰价 1.40`、`谷价 0.37`、`均价 0.77` | 只留 `1.40` / `0.37` / `0.77`，各自贴住所标注的峰、谷与均值线；口径移入注 |
| Fig.9 | `紧急费 69.9 → 15.3 万元`、`−78.1%` | 移入注；降幅读数改挂到 4-3 组正上方（有锚点，不再悬在面板右缘） |
| Fig.10 | 柱顶第二行 `(省 26.9%)`、左下角 `基线 = 100%` | 前者移入注；后者本已由纵轴标签 `费用指数（各自朴素基线 = 100%）` 完整表述，直接删 |

**顺带的两处版式收紧**（文字腾出了留白）：

- Fig.7 去掉左侧四行层级名后把 `XLO` 从 −1.36 收到 −0.88，格体放大约 10%
  （左/右仍保留 ≈0.8 / ≈0.5 个单位的净空，供边标签按法向 0.54 + 半宽 0.23 外推）。
- Fig.9 panel (b) `ylim` 92 → 86；Fig.10 panel (a) `ylim` 126 → 116。

**同轮修掉的两个工具/流程缺陷**：

1. **闸门的豁免机制本身不可靠。** 首版用 `fig.findobj(Text)` 反选（先按 Id 收集
   豁免集、再排除），而刻度标签会在 draw 前后被重建 → Id 匹配失效，**17 处合法
   中文刻度标签被误判**，真违规项反而淹没在噪声里。改为**正向收集**
   `ax.texts` / `fig.texts`（"人手写进图里的文字"才是判据），误报清零。
2. **`insert_into_paper.py` 是"见词即跳过"，改了注论文纹丝不动。** 已改为
   用 `\includegraphics{<stem>.pdf}` 定位并**整体替换**原 figure 环境，内容一致
   才算跳过；`--dry-run` 仍可用。本轮 5 张图的题注/注即由此同步进正文。

**⚠️ 连带影响（需你决定，见 §6）**：闸门收紧后，**AI-1 的 Fig.1–Fig.5 会在重渲染
时被拦下**——实测有 71 处图内汉字（Fig.1 47 处、Fig.2 5 处、Fig.3 7 处、
Fig.4 6 处、Fig.5 6 处），且仍带顶部大标题与底部"注"脚注。它们的既有产物
**未被改动**。为避免整批重出中断，`make_all_figures.py` 的 `FIGURES` 表新增第 5 列
`prose` 开关：这 5 张登记为 `False`，重出时对子进程设 `FIG_PROSE_GATE=0` 临时跳过
该门（其余三道门照跑），并在输出里明确打印"已豁免"；**单张手跑不加这个环境变量，
门照常生效**——迁移到哪张，就在哪张报错。这是临时豁免，不是长期选项。

---

## 0.3 修订（2026-09-13 晚二轮）：字体回退链定稿 + 一起合并冲突事故

### 起因

核对导出字体时发现 Fig.7 里有 4 个字符落到了 **DejaVu Sans**——一个无衬线体，
夹在 Times 中间一眼可辨。定位到全部是空集符号 `∅`（U+2205）：**Times New Roman
与宋体都不含这个字形**，逐字形回退于是落到了链尾的兜底字体。

### 根因：`figstyle.py` 里残留了一段未解决的 git 合并冲突

更严重的是排查过程中发现：`figstyle.py` **有三处 `<<<<<<< HEAD … >>>>>>>` 冲突块**
（字体块、`font.family`、mathtext 块），`make_all_figures.py` 有一处。冲突标记是
**合法文本**，Python 只在真正执行到那一行才 `SyntaxError`——前两处落在 docstring
附近、后几处落在常量区，所以"只改一行字体"这种小动作会在离现场很远的地方炸，
期间还可能先静默写坏一批产物。

按其中更成熟的一支（`FONT_CHAIN` + `_register_cjk_bold_face()` + `mathtext="cm"`）
解决冲突，并在此基础上补 `STIXGeneral`。三条并存的事实因此各归其位：

| 事实 | 处置 |
|---|---|
| 宋体无粗体面，`weight=700` 静默退化为常规体 | 保留 `_register_cjk_bold_face()`：把 SimHei 注册成 SimSun 的粗体面 |
| Times / 宋体缺 `∅` 等数学符号 | `FONT_CHAIN` 增 `STIXGeneral`（随 matplotlib 分发、按 Times 设计），排在 `DejaVu Serif` **之前** |
| 论文公式是 Computer Modern（`main.pdf` 实测嵌入 CMR/CMMI/CMSY/CMEX/MSBM） | mathtext 用 `cm` 而非指向 Times 的 `custom`——图内符号要与正文公式同源 |

定稿链：`("Times New Roman", "SimSun", "SimHei", "STIXGeneral", "DejaVu Serif")`

### 加了一道防回归

`make_all_figures.py` 的 `main()` 现在**先扫描本目录所有 `.py` 的冲突标记**，命中即
`return 3` 中止（`scan_conflict_markers()`）。一次全目录扫描比逐个 `SyntaxError` 便宜得多。
另做了一次全仓扫描（`.py/.tex/.cls/.sty/.md/…`）：**当前 0 处残留**。

### 复核

五张图重出，字体集合为 `{TimesNewRomanPSMT, TimesNewRomanPS-BoldMT, SimSun}`
（Fig.7 另有 `STIXGeneral-{Regular,Bold}`），**DejaVu 残留 0 处**；四道门仍全过。

---

## 1. 视觉规范：100% 复用 AI-1 的 `figstyle.py`

没有新增任何颜色、字号、线宽或图幅。每个脚本开头统一：

```python
import figstyle as S
S.apply_style()
...
S.save_figure(fig, "figNN_<name>")      # 内部自动跑 1.5 pt 对齐门 + 导出 PDF/SVG/PNG
```

- **色板**：`C_PRICE / C_FORECAST / C_RISK / C_ACTUAL / C_GRID / C_EMERGENCY /
  C_CHARGE / C_DISCHARGE / C_SOC / C_REF / C_SAVE / C_LOSS` 全部沿用。
  同一物理量全文同色：电价恒为红褐 `C_PRICE`、紧急购电恒为红 `C_EMERGENCY`。
- **字号**：刻度 7.5 / 轴标签 8 / 标注 8 / panel 字母 9；实证最小实绘字号 **6 pt**
  （脚注 6.2、柱顶读数 6.3–6.8），**全部 ≥ 5 pt**，字形审计通过。
- **图幅**：`FIG_W_FULL = 160 mm`；实测五张图 PDF 宽度均为 **157 mm**（去图内大标题后收紧，
  未被超宽文字撑开）。
- **字体（2026-09-13 定稿）**：字体真源是 `figstyle.FONT_CHAIN`
  `= ("Times New Roman", "SimSun", "SimHei", "STIXGeneral", "DejaVu Serif")`
  —— 西文/数字走 Times New Roman，中文走**宋体**，与 `cumcmthesis.cls` 的
  `\setmainfont{Times New Roman}` + `\songti` 题注一致。链上另两档各解决一个实测问题：
  - **`SimHei`**：宋体只有 weight=400，请求粗体时 matplotlib 既不报错也不回退，
    粗体中文会静默退化成常规体；`_register_cjk_bold_face()` 把黑体注册成宋体的
    粗体面，中文 `fontweight="bold"` 自动落到黑体（与正文 FandolSong+FandolHei 配对一致）。
  - **`STIXGeneral`**：Times 与宋体都缺少数数学符号（实测缺 `U+2205 ∅`），逐字形回退
    原本落到 `DejaVu Serif`；STIXGeneral 随 matplotlib 分发、按 Times 设计，补这类
    符号视觉上与正文同族。顺序不可颠倒——`SimSun` 必须在它之前，否则汉字会被截走。
  - **mathtext 走 `cm`**（Computer Modern），与论文成品同源：`main.pdf` 实测嵌入
    `CMR/CMMI/CMSY/CMEX/MSBM` 系列，即 LaTeX 默认数学字体。图内数学符号因此与正文公式
    同体。（旧方案 `fontset="custom"` 指向 Times 与正文公式并不一致。）
  - 实测五张图导出的 PDF 字体集合为 `{TimesNewRomanPSMT, TimesNewRomanPS-BoldMT,
    SimSun}`（Fig.7 另有 `STIXGeneral-{Regular,Bold}` 承接 `∅`），**无 DejaVu 残留**。
- **导出**：`04_图/pdf/<stem>.pdf`（矢量，主）+ `.svg`（可编辑）+ `04_图/<stem>.png`（300 dpi 预览）。

### 1.1 复用 AI-1 的"五个坑"清单（**2026-09-13 起其中两条已被上面的字体方案取代**）

1. 中文回退只用 `font.family` 列表 —— 五张图无豆腐块。**（仍然照做，且已把回退链
   首位定为 Times New Roman、中文定到 SimSun，并补 SimHei / STIXGeneral 两档。）**
2. ~~**全图不使用 mathtext**~~ → **已修订**。旧结论"`$...$` 会绕过字体回退链让中文变
   dummy symbol"只在 **mathtext 用默认字体集（DejaVu）** 时成立。现 mathtext 设
   `fontset="cm"` 与正文公式（CMR/CMMI/CMSY）同源，**中文仍不进 `$...$`**
   （中文一律留在普通文本里走 SimSun）。实测导出 **0 条缺字警告**。
   本批五张图实际**未用到 mathtext**（全部符号如 `∅ ⊆ → ±` 都是普通 Unicode）。
3. 只用实测可用的字形集。
4. 每个 panel 先 `ax.grid(False)` 再放轴内文字。
5. 所有 `bar / axvspan` 显式 `edgecolor="none"`。

---

## 2. 逐图说明

### Fig.6　问题三：0/6/12/18 时滚动决策时间轴

| 项 | 内容 |
|---|---|
| **新版作用** | 把"滚动"讲成一条**信息随时间推进**的决策时间轴：(a) 机制甘特——每个发布时刻哪些时段已冻结、哪些本轮提交、哪些只是暂定；(b) 个例 2025-12-21 的调整量 Δ = g − g⁰ 逐段曲线；(c) 全体——把 (b) 推广到全部 334 天的逐交付块 \|Δ\| 合计。 |
| **核心读数** | 第一交付块（0:00 发布时尚未开始、6:00 发布时已过去的那一块）的调整量 **0.000 MWh**，334 天中 **0 天**有调整；块 2–4 分别为 519.9 / 669.4 / 242.6 MWh，分别有 269 / 334 / 334 天发生调整。 |
| **数据来源** | `06_支撑材料/p3_main_arrays.npz`（逐日 gP_d / gA_d，各 144 段）、`p3_forecast_skill.csv`（四个发布时刻的净负荷预报 MAE）、`p3_calibration.json`（全年上调 656,263.05 / 下调 775,660.56 kWh，用于交叉核对分块合计 519.9+669.4+242.6 = 1,431.9 MWh）。**只读。** |
| **代码文件** | `03_代码/figures/fig06_rolling_timeline.py` |
| **输出文件** | `04_图/pdf/fig06_rolling_timeline.pdf` / `.svg`、`04_图/fig06_rolling_timeline.png` |
| **正文位置** | 问题三 §"滚动决策机制"（建议新增引用）。"不能偷看未来"在代码里只是一条约束，肉眼看不出；本图把它变成**可复算的 0.000**。 |

**实测排版坑（已记入脚本 docstring，供后续复用）**
- 交付块边界线若画成贯穿整个面板的 `axvline`，会穿过图例与标注文字被判 `text-stroke`；
  改用 `vlines` **限定在数据带内**即消除（首版实测 14 条 FAIL）。
- `add_gridspec(..., hspace=0.40)` 与 constrained layout 叠加会把行间距放大到画布高度的
  **30%**，上下两行被挤成窄条并触发 "axes sizes collapsed to zero"。**行间距交给
  constrained layout 自己算**（不传 `hspace`）即恢复正常。

---

### Fig.7　问题三：8 个信息集的布尔格与边际信息价值

| 项 | 内容 |
|---|---|
| **新版作用** | 把 8 个预报组合 `S ⊆ {6,12,18}` 画成**布尔格（Hasse 图）**，每条格边标注**边际信息价值 ΔJ**（新增该发布时刻后成本降多少），并配总价值柱图。回答的是"**预测信息的价值不是谁预测最准，而是已有信息集下新增信息后成本降多少**"。 |
| **核心读数** | 8 个组合全年总费用（元）：∅ = 14,977,809；{6} = 14,479,959；{12} = 14,031,892；{18} = 13,799,589；{6,12} = 13,880,879；{6,18} = 13,533,015；{12,18} = 13,580,206；{6,12,18} = 13,418,626。**全信息价值 J(∅) − J(全) = 1,559,183 元 = 155.92 万元**；12 条格边**全部**为负（成本单调递减）。 |
| **数据来源** | `06_支撑材料/p3_analysis.json` → `configs`（8 条真实求解记录）。**只读。** |
| **代码文件** | `03_代码/figures/fig07_information_value.py` |
| **输出文件** | `04_图/pdf/fig07_information_value.pdf` / `.svg`、`04_图/fig07_information_value.png` |
| **正文位置** | 问题三 §"预测信息的价值"（建议新增引用）。 |

**排版说明**
- 格边标签会天然挤在节点中点，首版 19 条 FAIL。改为**贪心避让放置器**
  （`_place_labels()`：用 `fig.canvas.draw()` 取 points-per-unit，候选 `t / side / off`
  三级搜索），并把节点费用**移入节点框内**、格边在节点框边界处**截断**（`_trim()`）。
- 层间距由 1.0 调到 **1.3**：1.0 时留给标签的带高只有 0.27 单位（标签高 0.27），
  必然相切；1.3 后才满足。
- 单位统一为**万元**（`−49.8 万` 而非 `−498,000`），避免长数字压线。

---

### Fig.8　问题四：价格结构分解 P(d,t) = F_t + R(d,t)

| 项 | 内容 |
|---|---|
| **新版作用** | 先解释"为什么同星期加权是合理的"，再给公式。(a) 附件 1 固定曲线 F 的日内结构（深夜低谷、傍晚尖峰，峰谷比 **3.76**）与附件 4 逐时段均值几乎重合；(b) 残差 R = P − F 按星期几平均——周五、周六比其余五天低 **0.1913 元/kWh**（均价的 **25.0%**），星期效应解释残差方差的 **41.7%**；(c) 冻结预测器 R̂ = 0.5R(d−7) + 0.3R(d−14) + 0.2R(d−21) 的逐时段对比。 |
| **核心读数** | 水平一致 `max_t \|mean_d P − F\| = 5.151e−05`；残差正交 `corr(R,F) = −1.48e−05`；族 A（周一~四+日）**+0.0545**、族 B（周五、六）**−0.1368**，差 **0.1913**；复算 MAE **0.044573976837991 元/kWh**（均价的 **5.88%**），与候选表**逐位一致**。 |
| **数据来源** | `01_题目/C题/附件/附件1.xlsx`（F，144 段）、`附件4.xlsx`（P，365×144）、`06_支撑材料/p4_price_forecast_candidates.csv`（候选表 MAE，用于交叉核对）。**只读。** |
| **代码文件** | `03_代码/figures/fig08_price_forecast.py` |
| **输出文件** | `04_图/pdf/fig08_price_forecast.pdf` / `.svg`、`04_图/fig08_price_forecast.png` |
| **正文位置** | 问题四 §"价格结构分解与预测器"（建议新增引用）。 |

**信息边界（图内已明确标出）**：预测只读 **d−7 / d−14 / d−21 的实际价格**，全部落在过去；
当日任何实际价格都不进入决策；图中"实际"曲线仅用于**事后评估**。

**⚠️ 复核中发现并已修正的两处实现错误（均在本图脚本内，未影响任何数据与模型）**
1. **时间轴步长错误**：`DT_H` 曾误写 `0.5 h`（应为 `10/60 = 1/6 h`）。后果是横轴被拉长 3 倍，
   而 `xlim=(0,24)` 把曲线**裁掉 2/3**——面板 (a) 只画了 144 段中的前 49 段，
   且被裁掉的那段路径几何仍延伸到画布右缘，**伪造出两条 `text-stroke` 假告警**（穿过 y 轴标签）。
   改为 `10/60` 后曲线恢复完整、假告警消失。**已核对全仓：`10/60` 是项目统一口径
   （`p1_microgrid.py` 的 `TAU = 10/60`、AI-1 的 fig02/fig04 均一致），错误仅存在于本图首版脚本。**
2. **MAE 复算口径错误**：`main()` 曾把"预测残差 R̂"直接与"整价 P"相减（`|R̂ − P|`），
   得到 ≈ `F` 的均值 0.7663 而非 0.0446。正确口径是 `|R̂ − R|`（整价两端 F 相消）。
   修正后复算值与候选表**逐位一致**，脚本内以断言锁死。

---

### Fig.9　问题四：两种合同口径下的策略对照

| 项 | 内容 |
|---|---|
| **新版作用** | 证明问题四的关键**不在预测得多准，而在合同允许不允许滚动调整**。(a) 六个策略的实际费用拆成 计划费 / 调整费 / 紧急费；(b) 把"增量费用"（调整费+紧急费）单独放大；(c) 相对降幅。 |
| **核心读数** | 同策略 4-3 相对 4-2 **省 58.75 万元（−3.99%）**；**紧急购电费 69.89 → 15.31 万元（−78.1%）**；代价只是 **19.72 万元调整费**。三策略合计（万元）——4-2：预测 1474.08 / 固定 1476.10 / 已知未来 1464.67；4-3：预测 1415.33 / 固定 1418.95 / 已知未来 1407.57。相对固定参考省 0.14%（4-2）/ 0.26%（4-3）；距"已知未来"下界仍差 0.64% / 0.55%。 |
| **数据来源** | `06_支撑材料/p4_strategies.csv`（6 行真实求解输出）、`p4_strategy_fees.csv`（万元口径，逐行交叉核对，脚本内断言）。**只读。** |
| **代码文件** | `03_代码/figures/fig09_p4_strategy.py` |
| **输出文件** | `04_图/pdf/fig09_p4_strategy.pdf` / `.svg`、`04_图/fig09_p4_strategy.png` |
| **正文位置** | 问题四 §4.2 / §4.3 策略对照处（建议新增引用）。 |

**必须写进正文的一句话**：滚动调整**不是买得更少**，而是用**低价的计划内改动**
（19.72 万元调整费）替换了**5 倍价的尾部抢购**（紧急费少 54.58 万元）。

**口径说明**："未来价格已知参考"是**理论上界**（完全预知），仅用于给出下界，
**不是可行方案**——图内已标注。

---

### Fig.10　全文总结：四问逐层叠加

| 项 | 内容 |
|---|---|
| **新版作用** | 收束全篇：把每一问的本文策略与**该问自己的朴素基线**相比，证明"层层加能力、层层都不亏"，并展示尾部代价同步压缩。 |
| **核心读数** | 费用指数（各自朴素基线 = 100%）：**P1 73.10% / P2 93.53% / P3 89.59% / P4 99.74%**。尾部代价（紧急购电费）：P2 **270.89 → 75.55 万元（−72.1%）**，P3 **238.27 → 27.29 万元（−88.5%）**。 |
| **数据来源** | `p1_results.json`（主模型 + benchmarks.无储能）、`p2_results.json`（对照策略）、`p3_analysis.json`（configs）、`p4_strategies.csv`（4-3 分支）。**只读。** |
| **代码文件** | `03_代码/figures/fig10_summary.py` |
| **输出文件** | `04_图/pdf/fig10_summary.pdf` / `.svg`、`04_图/fig10_summary.png` |
| **正文位置** | 结论章 / 模型总览处（建议新增引用）。 |

**⚠️ 口径纪律（请正文严格遵守）**
**四问的费用绝对值不可直接横比。** P1 用附件 1 的给定曲线做**单日**确定性调度；P2、P3
做**全年**滚动；**P4 换用附件 4 的波动电价**。口径与电价情景都不同。因此本图统一用
"相对该问朴素基线的百分比"，并把**基线定义**写在脚注里：
P1 无储能、P2 预测均值（不加风险余量）、P3 只用 0:00 预报、P4 固定电价参考——
**同一模型、少一项能力**。面板 (b) 只列**同为附件 1 情景**的 P2、P3，保证可比。

---

## 3. 全量 QA 结果

对五张图的**最终导出版 PDF**逐张执行四项强制检查：

```
fig06_rolling_timeline   碰撞 PASS（0 fail / 0 warn）   字形 6.0 pt PASS   对齐 PASS   图内文字 0 处 PASS
fig07_information_value  碰撞 PASS（0 fail / 0 warn）   字形 6.0 pt PASS   对齐 PASS   图内文字 0 处 PASS
fig08_price_forecast     碰撞 PASS（0 fail / 0 warn）   字形 6.2 pt PASS   对齐 PASS   图内文字 0 处 PASS
fig09_p4_strategy        碰撞 PASS（0 fail / 0 warn）   字形 6.2 pt PASS   对齐 PASS   图内文字 0 处 PASS
fig10_summary            碰撞 PASS（0 fail / 0 warn）   字形 6.3 pt PASS   对齐 PASS   图内文字 0 处 PASS

合计 5 张，通过 5 张
```

- 碰撞审计：`audit_figure_collisions.py`（text-stroke / text-text / text-fill-edge）
- 字形下限：`audit_pdf_text.py --min-pt 5`（最小实绘字号 6.0 pt）
- 多面板对齐：`audit_panel_alignment.py`（1.5 pt 容差，由 `S.save_figure` 内部强制）
- **图内禁文字（汉字 / 英文句子）**：`S.audit_prose()`（导出前强制，读 `qa/<stem>.prose-audit.json`）
- **五张图均 0 fail 且 0 warn**（AI-1 的 Fig.2/Fig.4 各有 4 条刻意保留的浅底纹相切 WARN）。

留档：`04_图/qa/<stem>.alignment.json / .alignment.svg / .collision-audit.json / .prose-audit.json`
（Fig.8/9/10 另有 `.collision-audit.pdf` 可视叠加件）。

**⚠️ 本轮同时修掉的一个审计工具缺陷（影响过全部历史结论）**
`audit_figure_collisions.py` 原先把"文字行"与"文字框"按**先到先得**配对：两条文字
一旦重叠，第一条行会同时抓走两条 trace 并**合并成一个大 bbox**，重叠因此**被掩盖**，
报出 PASS。修法：改为**两遍扫描 + 全局最优配对**——先收全部行（松动框），再为每条
trace 选择**重叠率最大**的那一行（阈值 0.3）。回归验证：把修好的工具跑在**当时的**
fig08 上，立刻报出 `[FAIL] text-text … 95.6%`——而这处重叠（图例第二行 vs "峰价"
标注）在旧工具下**一直是 PASS**。已同步修复到
`~/.workbuddy/skills/nature-figure/scripts/audit_figure_collisions.py`（md5 一致）。
**结论：旧工具"过"不等于真过；碰撞类工具必须做"能否复现已知坏例"的回归测试。**

**静态预检 `validate_figure.py`**：沿用 AI-1 的结论——该工具是正则扫描器、不跟随 import，
看不到定义在 `figstyle.py` 的字体与可编辑文本设置、也看不到 `save_figure()` 内部的对齐门，
其 FAIL 均为工具误报。实证：字形审计能逐条读出 PDF 文本（TrueType 可编辑）、
`qa/*.alignment.json` 全部 `verdict: PASS`。

---

## 4. 交付物清单

```
03_代码/figures/
  fig06_rolling_timeline.py     ← Fig.6
  fig07_information_value.py    ← Fig.7
  fig08_price_forecast.py       ← Fig.8
  fig09_p4_strategy.py          ← Fig.9
  fig10_summary.py              ← Fig.10
  build_captions.py             ← 【新】captions.json → fig_captions.tex + captions.md
  insert_into_paper.py          ← 【新】按语义锚点把图题插进正文 + 同步 figures/*.pdf
  make_all_figures.py           ← 已把上述 5 个脚本追加进 FIGURES（并接入 prose 门）

04_图/pdf/fig0N_*.pdf|.svg      ← 矢量交付件（PDF 主用于 LaTeX，SVG 可编辑）
04_图/fig0N_*.png               ← 300 dpi 预览
04_图/captions.json             ← 【新】save_figure 落盘的图题/注登记表（唯一真源）
04_图/fig_captions.tex          ← 【新】可直接编译的 figure 环境（含 \caption/\label/注）
04_图/captions.md               ← 【新】同一内容的人读版
04_图/qa/*.json|.svg|.pdf       ← 碰撞/字形/对齐/图内文字 审计留档（非交付件）
05_论文/final_new/figures/fig0N_*.pdf  ← 【新】正文实际引用的矢量图
06_支撑材料/fig0N_*.pdf …       ← 部分图件同时归档到支撑材料

AI2_FIGURE_REPORT.md            ← 本文件
MERGE_CHECKLIST.md              ← 合并前自检清单
```

**重出全部图**：`python 03_代码/figures/make_all_figures.py`
**只重出单张**：`python 03_代码/figures/make_all_figures.py --only fig08`

> ⚠️ **"重出全部图"目前会中断在 Fig.1**：AI-1 的五张图尚未迁移到新的"图内禁文字"
> 规则，会被闸门拦下（报错在导出之前，不会写坏既有产物）。要重出 Fig.6–Fig.10，
> 请用 `--only figNN`，或在 §6.1 里选定 AI-1 的迁移方案。

**改图题/注 → 更新正文（三步，全部可重跑、幂等）**：

```bash
python 03_代码/figures/make_all_figures.py --only fig08   # 1. 重渲染（题注写进 captions.json）
python 03_代码/figures/build_captions.py                  # 2. 生成 fig_captions.tex
python 03_代码/figures/insert_into_paper.py               # 3. 插进正文 + 同步 PDF
python 03_代码/figures/insert_into_paper.py --dry-run     # 只看落位，不改文件
```

---

## 5. 边界声明

- **未改动**任何数学模型、任何 `.py` 模型文件（`p1/p2/p3/p4_microgrid.py` 等）、
  任何 `06_支撑材料/` 数据、任何 `01_题目/` 附件。
- **未改动** AI-1 的 Fig.1–Fig.5 的**产物**（脚本、PDF、SVG、PNG、qa 全部原样，
  `git status` 已核对）。
- **`figstyle.py` 已修订（三轮，属全篇共用规范）**：① 字体链定稿
  `FONT_CHAIN = (Times New Roman, SimSun, SimHei, STIXGeneral, DejaVu Serif)`、
  `MATHTEXT_FONTSET = "cm"`，并解决三处残留的 git 合并冲突（见 §0.3）；
  ② 新增 `audit_prose()` / `_forbidden_reason()` / `ProseInFigureError`；
  ③ `save_figure()` 增加 `caption/note/prose_gate` 参数 + `record_caption()` /
  `captions.json` 登记。**配色 / 字号 / 线宽 / 图幅 token 一字未动**，
  故 AI-1 五张图的**视觉规格**不受影响。
- **`make_all_figures.py` 已修订**：`FIGURES` 表新增 `prose` 开关列、
  `main()` 增加冲突标记预检（`scan_conflict_markers()`）。AI-1 的 5 张图登记为
  `prose=False`（临时豁免，见 §0.2 末）。
- ⚠️ **但闸门收紧会让 AI-1 的五张图在单张手跑时被拦下**：实测图内汉字 71 处
  （Fig.1 47 / Fig.2 5 / Fig.3 7 / Fig.4 6 / Fig.5 6），且仍带顶部大标题与
  底部"注"脚注。它们的既有产物**未被改动**；报错前置在导出之前，
  **不会写坏任何既有文件**。迁移方案见 §6。
- **`05_论文/final_new/{p3,p4}_section.tex` 已修改**：各插入 figure 环境 + 各补一句
  交叉引用（这是"把题注落进正文"这个任务的固有代价，已逐处记录在本报告 §0.1）。
- **`moved_body.tex` 未改动**（附录旧图原样保留，见 §6 待决事项）。
- `git status` 核对：除上述登记/正文文件外，**全部为新增未跟踪文件**。

---

## 6. 待决事项（需人工取舍，脚本**不代删**）

`insert_into_paper.py` 的 `OVERLAPS` 会提示"新图与哪张旧图内容重叠"。当前有 4 处，
**脚本一律不删**，因"新旧图取舍"属正文决策：

| 新图 | 与之重叠的旧图 | 关系判断 |
|---|---|---|
| Fig.6 | `p3_fig1_versions.png`（`fig:p3-versions`） | 视角不同：旧图是四条预测曲线，新图是"冻结机制"时间轴。**建议都留**，新图解释机制。 |
| Fig.7 | `p3_fig4_combos.png`（`fig:p3-combo`） | 主题相关但不重复：旧图是费用柱状图，新图是布尔格+边际价值。**建议都留**。 |
| Fig.8 | `p4_fig1_price_structure.png`（`fig:p4-struct`） | **内容重叠**：都是 P = F + R 分解。新图多出预测误差面板 (c)。**建议删旧留新。** |
| Fig.9 | `p4_fig3_strategy.png`（`fig:p4-strategy`） | **内容重叠**：都是策略费用分解。新图多出"增量费用放大"与"降幅下界"两个面板。**建议删旧留新。** |

> 若决定删旧图，需同时处理：`moved_body.tex` 的 figure 环境 + 其 `\caption`/`\label`
> + 引用它的 `\ref`（`p4_section.tex:42` 引 `fig:p4-struct`；`main.tex:2230`、
> `p4_section.tex` 引 `fig:p4-strategy`）。**删图不改引用会造成未定义引用。**

### 6.1 【新】AI-1 的 Fig.1–Fig.5 要不要一并按同一套规范迁移？

闸门收紧后，Fig.1–Fig.5 与 Fig.6–Fig.10 已不在同一套规则下。三条路，各有代价：

| 方案 | 做法 | 代价 |
|---|---|---|
| **A. 全量迁移**（推荐） | 按 Fig.6–Fig.10 的做法清掉图内汉字：顶部大标题 → `\caption`，图内结论句与底部"注" → 图下注，框内名词/区域名保留但打 `_prose_exempt` 标记 | 要改 5 个脚本（属 AI-1 的交付物）；**顺带把字体统一成宋体+Times**（现在还是旧的回退链） |
| **B. 只标豁免** | 给 AI-1 图内确有必要的标签打 `_prose_exempt=True`，其余不动 | 改动最小，但顶部大标题/底部脚注会**继续留在图里**，与评阅意见不一致 |
| **C. 暂不处理** | 维持现状 | `make_all_figures.py` 全量重跑会中断在 Fig.1；Fig.1–Fig.5 与 Fig.6–Fig.10 **字体也不统一** |

注：三者都需要有人决定**是否让 Fig.1–Fig.5 也换成宋体 + Times**——`figstyle.py`
的字体块是全篇共用的，一旦重渲染，它们的字体就会跟着变（视觉 token 不变）。
`fig01_framework.py`（框架图，47 处）与 `fig03/04/05`（剖面图/瀑布图）里的框内名词
属于"图的内容"，按上一轮约定应当保留，只是需要显式豁免。**等你点头再动。**

---
