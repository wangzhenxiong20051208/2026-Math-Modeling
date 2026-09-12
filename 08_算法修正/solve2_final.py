# -*- coding: utf-8 -*-
"""
问题二 最终版（一步到位：标定→运行→生成Excel）
融合优化：纯LP骨架 + lam日末软惩罚 + 细ρ网格 + 1月联合标定
合规：所有参数只用1月数据选定，2-12月滚动标定只用过去数据
输出：06_支撑材料/result2.xlsx（计划购电量 + 紧急购电量，144时段×334天）
"""
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import time
import os

# ==================== 路径（仓库内相对路径） ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)  # 上级目录即仓库根
DATA_DIR = os.path.join(ROOT_DIR, '01_题目', 'C题', '附件')
OUTPUT_DIR = os.path.join(ROOT_DIR, '08_算法修正', '输出')
os.makedirs(OUTPUT_DIR, exist_ok=True)

PRICE_FILE = os.path.join(DATA_DIR, '附件1.xlsx')
LOADPV_FILE = os.path.join(DATA_DIR, '附件2.xlsx')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'result2.xlsx')

# ==================== 常量 ====================
N = 144
DT = 1 / 6
ETA = 0.9
EMIN = 1200.0
EMAX = 10800.0
E_INIT = 6000.0
PMAX = 5000.0
M = PMAX * DT
REPORT_START = 31
N_DAY = 365
CAL_EVERY = 42
CAL_WINDOW = 35

# ==================== 数据加载 ====================
print("加载数据...")
df1 = pd.read_excel(PRICE_FILE)
price = df1['电价'].astype(float).values

load_df = pd.read_excel(LOADPV_FILE, sheet_name='小区负载')
pv_df = pd.read_excel(LOADPV_FILE, sheet_name='光伏发电实际功率')
dates_all = pd.to_datetime(load_df.iloc[:, 0]).tolist()
load_mat = load_df.iloc[:, 1:].astype(float).values
pv_mat = pv_df.iloc[:, 1:].astype(float).values
load_e = load_mat * DT
pv_e = pv_mat * DT
print(f"  数据加载完成：{N_DAY}天 × {N}时段")


def weekday_of(n):
    return (n + 2) % 7


# ==================== 预测函数 ====================
def predict_day(n, load_win=28, load_decay=0.3, pv_win=7, pv_decay=0.3):
    # n=0（1月1日）无历史数据可用，返回零向量；其误差在 build_eps 中标记为 NaN，
    # 不参与后续分位数计算，因此不影响正式区间（2-12月）的风险余量。
    if n == 0:
        return np.zeros(N)
    lo = max(0, n - load_win)
    idx = np.arange(lo, n)
    same = np.array([weekday_of(i) == weekday_of(n) for i in idx])
    idx_same = idx[same] if same.any() else idx
    w = load_decay ** ((n - 1 - idx_same) / 7.0)
    w = w / w.sum()
    pl = (w[:, None] * load_e[idx_same, :]).sum(axis=0)
    lo2 = max(0, n - pv_win)
    idx2 = np.arange(lo2, n)
    w2 = pv_decay ** ((n - 1 - idx2) / 7.0)
    w2 = w2 / w2.sum()
    pp = (w2[:, None] * pv_e[idx2, :]).sum(axis=0)
    return pl - pp


# ==================== 安全裕度（分时段风险准备） ====================
def safety_margin(eps_table, n, alpha, window=28, min_samples=8):
    if n == 0:
        return np.zeros(N)
    lo = max(0, n - window)
    hist = eps_table[lo:n, :]
    valid = ~np.isnan(hist).all(axis=1)
    hist = hist[valid]
    k = hist.shape[0]
    if k >= min_samples:
        return np.nanquantile(hist, alpha, axis=0)
    if k >= 3:
        pooled = np.empty((k, N))
        for t in range(N):
            a, b = max(0, t - 2), min(N, t + 3)
            pooled[:, t] = np.nanmean(hist[:, a:b], axis=1)
        return np.nanquantile(pooled, alpha, axis=0)
    return np.zeros(N)


# ==================== 日LP（含lam日末软惩罚） ====================
def solve_plan_lam(net_load, e0, lam):
    iG, iC, iD, iS, iE, iXi = 0, N, 2 * N, 3 * N, 4 * N, 5 * N
    nv = 5 * N + 1
    c_obj = np.zeros(nv)
    c_obj[iG:iG + N] = price
    c_obj[iXi] = lam

    A_eq = np.zeros((2 * N, nv))
    b_eq = np.zeros(2 * N)
    for t in range(N):
        A_eq[t, iG + t] = 1
        A_eq[t, iD + t] = 1
        A_eq[t, iC + t] = -1
        A_eq[t, iS + t] = -1
        b_eq[t] = net_load[t]
    for t in range(N):
        A_eq[N + t, iE + t] = 1
        if t > 0:
            A_eq[N + t, iE + t - 1] = -1
        A_eq[N + t, iC + t] = -ETA
        A_eq[N + t, iD + t] = 1.0 / ETA
        if t == 0:
            b_eq[N + t] = e0

    A_ub = np.zeros((1, nv))
    A_ub[0, iE + N - 1] = -1
    A_ub[0, iXi] = -1
    b_ub = np.array([-E_INIT])

    bounds = ([(0, None)] * N + [(0, M)] * N + [(0, M)] * N
              + [(0, None)] * N + [(EMIN, EMAX)] * N + [(0, None)])
    res = linprog(c_obj, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub,
                  bounds=bounds, method='highs')
    if not res.success:
        return None, None, None, None
    return (res.x[iG:iG + N].copy(), res.x[iC:iC + N].copy(),
            res.x[iD:iD + N].copy(), res.x[iE:iE + N].copy())


# ==================== 执行层 ====================
def execute_day(g_plan, E_ref, l_act, v_act, e0, rho):
    c = np.zeros(N)
    d = np.zeros(N)
    r = np.zeros(N)
    w = np.zeros(N)
    E = np.zeros(N)
    soc = e0
    for t in range(N):
        b = g_plan[t] + v_act[t] - l_act[t]
        R = EMIN + rho * (E_ref[t] - EMIN)
        if b >= 0:
            cmax = min(b, M, (EMAX - soc) / ETA)
            c[t] = max(0, cmax)
            w[t] = b - c[t]
        else:
            head = max(0.0, soc - R)
            dmax = min(-b, M, ETA * head)
            d[t] = max(0, dmax)
            r[t] = max(0, -b - d[t])
        soc = soc + ETA * c[t] - d[t] / ETA
        E[t] = soc
    return c, d, r, w, E, float(np.sum(price * g_plan)), float(np.sum(5.0 * price * r))


# ==================== 结果校验 ====================
def validate_day(rec, tol=1e-6):
    """对单天执行结果做 6 项校验，返回问题列表（空 = 全部通过）。"""
    problems = []
    n = rec['n']
    g, c, d, r, w, E = rec['g'], rec['c'], rec['d'], rec['r'], rec['w'], rec['E']
    c_ref, d_ref = rec['c_ref'], rec['d_ref']
    e0, E_end = rec['E0'], rec['E_end']
    l_act = load_e[n]
    v_act = pv_e[n]

    # 1) 逐段供需平衡：g + r + v_act + d = l_act + c + w
    lhs = g + r + v_act + d
    rhs = l_act + c + w
    resid = np.abs(lhs - rhs)
    if resid.max() > tol * max(1.0, l_act.max()):
        problems.append(f"供需平衡残差过大：{resid.max():.3e} kWh（第{n}天）")

    # 2) 储电量递推自洽
    Erec = [e0]
    for t in range(N):
        Erec.append(Erec[-1] + ETA * c[t] - d[t] / ETA)
    err = np.abs(np.array(Erec[1:]) - E).max()
    if err > tol:
        problems.append(f"储电量递推偏差 {err:.3e} kWh（第{n}天）")

    # 3) 储电量上下界
    Eseq = np.concatenate([[e0], E])
    if Eseq.min() < EMIN - tol:
        problems.append(f"储电量低于下界 {Eseq.min():.4f} < {EMIN}（第{n}天）")
    if Eseq.max() > EMAX + tol:
        problems.append(f"储电量高于上界 {Eseq.max():.4f} > {EMAX}（第{n}天）")

    # 4) 执行层充放电互斥（if-else 保证，数值复核）
    both = (c > tol) & (d > tol)
    if both.any():
        problems.append(f"执行层存在 {int(both.sum())} 个时段同时充放电（第{n}天）")

    # 5) LP 规划层互斥：参考充电量 ā 与参考放电量 d̄ 不应同时为正
    lp_both = (c_ref > tol) & (d_ref > tol)
    if lp_both.any():
        problems.append(f"LP规划层存在 {int(lp_both.sum())} 个时段 ā/d̄ 同时为正（第{n}天）")

    # 6) 紧急购电费一致性：逐段计算 vs 记录值
    emg_check = float(np.sum(5.0 * price * r))
    if abs(emg_check - rec['cost_emg']) > tol * max(1.0, abs(rec['cost_emg'])):
        problems.append(f"紧急购电费不一致：{emg_check:.4f} vs {rec['cost_emg']:.4f}（第{n}天）")

    return problems


def run_day(n, e0, alpha, rho, lam, pred_params, eps_table):
    lw, ld, pw, pd = pred_params
    pnet = predict_day(n, lw, ld, pw, pd)
    sm = safety_margin(eps_table, n, alpha)
    ntilde = pnet + sm
    g, c_ref, d_ref, E_ref = solve_plan_lam(ntilde, e0, lam)
    if g is None:
        return None
    c, d, r, w, E, cp, ce = execute_day(g, E_ref, load_e[n], pv_e[n], e0, rho)
    return {
        'n': n, 'g': g, 'c_ref': c_ref, 'd_ref': d_ref,
        'c': c, 'd': d, 'r': r, 'w': w, 'E': E,
        'E0': e0, 'E_end': E[-1], 'cost_plan': cp, 'cost_emg': ce,
        'cost_total': cp + ce
    }


# ==================== 构建全年误差表 ====================
def build_eps(pred_params):
    lw, ld, pw, pd = pred_params
    eps = np.full((N_DAY, N), np.nan)
    for n in range(1, N_DAY):
        pnet = predict_day(n, lw, ld, pw, pd)
        eps[n] = (load_e[n] - pv_e[n]) - pnet
    return eps


# ==================== 第一阶段：1月联合标定 α、ρ、lam ====================
print("\n" + "=" * 70)
print("第一阶段：1月联合标定 α、ρ、lam（合规：只用1月数据）")
print("=" * 70)

PRED_PARAMS = (28, 0.3, 7, 0.3)  # 预测参数（1月16组网格标定选出）
eps_full = build_eps(PRED_PARAMS)

ALPHAS = [0.70, 0.75, 0.80, 0.85, 0.90]
RHOS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
LAMS = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8]


def jan_cost(alpha, rho, lam):
    e = E_INIT
    total = 0.0
    for n in range(31):
        rec = run_day(n, e, alpha, rho, lam, PRED_PARAMS, eps_full)
        if rec is None:
            return np.inf
        total += rec['cost_total']
        e = rec['E_end']
    return total


t0 = time.time()
grid_results = []
for a in ALPHAS:
    for r in RHOS:
        for lam in LAMS:
            cost = jan_cost(a, r, lam)
            grid_results.append((a, r, lam, cost))

grid_results.sort(key=lambda x: x[3])
best_a, best_r, best_lam, best_jan = grid_results[0]
print(f"  标定完成，用时 {time.time()-t0:.1f}s，共 {len(grid_results)} 组")
print(f"  ★ 1月最优: α={best_a}, ρ={best_r}, lam={best_lam}, 1月费={best_jan:.2f}元")

# ==================== 第二阶段：1月预热 ====================
print("\n" + "=" * 70)
print("第二阶段：1月预热（不计费）")
print("=" * 70)

e = E_INIT
e_at_start = np.zeros(N_DAY + 1)
e_at_start[0] = E_INIT
for n in range(0, REPORT_START):
    rec = run_day(n, e, best_a, best_r, best_lam, PRED_PARAMS, eps_full)
    e = rec['E_end']
    e_at_start[n + 1] = e
print(f"  1月预热完成，2月1日期初储电量={e:.2f} kWh")

# ==================== 第三阶段：2-12月滚动标定+运行 ====================
print("\n" + "=" * 70)
print("第三阶段：2-12月滚动标定+运行（合规：只用过去数据）")
print("=" * 70)


def replay_window(n_start, n_end, e_start, alpha, rho, lam):
    e = e_start
    total = 0.0
    for n in range(n_start, n_end):
        rec = run_day(n, e, alpha, rho, lam, PRED_PARAMS, eps_full)
        if rec is None:
            return np.inf, e
        total += rec['cost_total']
        e = rec['E_end']
    return total, e


all_records = []
current_alpha = best_a
current_rho = best_r
t1 = time.time()
cal_count = 0
val_failures = 0

for n in range(REPORT_START, N_DAY):
    if (n - REPORT_START) % CAL_EVERY == 0:
        lo = max(0, n - CAL_WINDOW)
        e_win_start = e_at_start[lo]
        bc = np.inf
        bar = None
        for a in ALPHAS:
            for r in RHOS:
                cost, _ = replay_window(lo, n, e_win_start, a, r, best_lam)
                if cost < bc - 1e-9:
                    bc = cost
                    bar = (a, r)
        current_alpha, current_rho = bar
        cal_count += 1
    rec = run_day(n, e, current_alpha, current_rho, best_lam, PRED_PARAMS, eps_full)
    # 逐日校验
    vp = validate_day(rec)
    if vp:
        val_failures += 1
        for msg in vp:
            print(f"  !! {msg}")
    all_records.append(rec)
    e = rec['E_end']
    e_at_start[n + 1] = e

print(f"  运行完成，用时 {time.time()-t1:.1f}s，滚动标定 {cal_count} 次")
print(f"  校验结果：{val_failures} 天有问题，{len(all_records) - val_failures} 天通过")

# 跨日连续性校验：E_{n+1,0} == E_{n,144}
cross_day_err = 0.0
for i in range(len(all_records) - 1):
    e_end_today = all_records[i]['E_end']
    e_start_tmr = all_records[i + 1]['E0']
    err = abs(e_end_today - e_start_tmr)
    if err > cross_day_err:
        cross_day_err = err
if cross_day_err > 1e-9:
    print(f"  !! 跨日连续性偏差最大值：{cross_day_err:.3e} kWh")
else:
    print(f"  跨日连续性校验通过（最大偏差 {cross_day_err:.3e} kWh）")

# ==================== 费用汇总 ====================
total_plan = sum(r['cost_plan'] for r in all_records)
total_emg = sum(r['cost_emg'] for r in all_records)
total_all = total_plan + total_emg

print("\n" + "=" * 70)
print("最终结果（2025-02-01 至 2025-12-31，共334天）")
print("=" * 70)
print(f"  参数: α(1月)={best_a}, ρ(1月)={best_r}, lam={best_lam}")
print(f"  计划购电费: {total_plan:,.2f} 元")
print(f"  紧急购电费: {total_emg:,.2f} 元")
print(f"  合计购电费: {total_all:,.2f} 元 = {total_all/1e4:.2f} 万元")
print(f"  紧急费占比: {total_emg/total_all*100:.2f}%")

# 缓存计算结果，避免调整Excel格式时重跑优化
import pickle
CACHE_FILE = os.path.join(OUTPUT_DIR, 'result2_cache.pkl')
with open(CACHE_FILE, 'wb') as f:
    pickle.dump({
        'records': all_records, 'best_a': best_a, 'best_r': best_r,
        'best_lam': best_lam, 'total_plan': total_plan, 'total_emg': total_emg,
    }, f)
print(f"  计算结果已缓存：{CACHE_FILE}")

# ==================== 第四阶段：按附件5模板格式生成Excel ====================
print("\n" + "=" * 70)
print(f"第四阶段：按模板生成Excel → {OUTPUT_FILE}")
print("=" * 70)

import shutil
from openpyxl import load_workbook
from datetime import time as dtime

TEMPLATE_FILE = os.path.join(DATA_DIR, '附件5', 'result2.xlsx')

# 检测输出文件是否被Excel占用，被占用则自动用备用文件名
def is_locked(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'ab'):
            pass
        return False
    except PermissionError:
        return True

if is_locked(OUTPUT_FILE):
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'result2_新.xlsx')
    print(f"  ⚠ result2.xlsx 被占用（请关闭Excel），改存为: {OUTPUT_FILE}")

shutil.copy(TEMPLATE_FILE, OUTPUT_FILE)
wb = load_workbook(OUTPUT_FILE)

# ---------- Sheet1: 计划购电量（模板已预填334天日期和147列表头） ----------
ws1 = wb['计划购电量']
# 模板列顺序：列2=t1(0:10-0:20)...列144=t143(23:50-0:00+1)，列145=t0(0:00-0:10+1)
# 即列j(2..145) 对应 t=(j-1)%144
for i, rec in enumerate(all_records):
    row = i + 2
    g = rec['g']
    for j in range(2, 146):
        t = (j - 1) % N
        ws1.cell(row=row, column=j, value=round(float(g[t]), 4))
    ws1.cell(row=row, column=146, value=round(float(g.sum()), 4))       # 全天购电量
    ws1.cell(row=row, column=147, value=round(float((price * g).sum()), 4))  # 全天购电费
print("  [计划购电量] 334天 × 144时段 + 全天购电量/购电费 已填入")

# ---------- Sheet2: 充放电量（每天6行，4小时一段） ----------
ws2 = wb['充放电量']
if ws2.max_row > 1:
    ws2.delete_rows(2, ws2.max_row - 1)
seg_labels = ['0:00-4:00', '4:00-8:00', '8:00-12:00',
              '12:00-16:00', '16:00-20:00', '20:00-24:00']
seg_ranges = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
row = 2
for rec in all_records:
    dt = dates_all[rec['n']]
    c, d = rec['c'], rec['d']
    for k in range(6):
        s, e = seg_ranges[k]
        if k == 0:
            ws2.cell(row=row, column=1, value=dt)
            ws2.cell(row=row, column=5, value=dtime(0, 0))
            ws2.cell(row=row, column=6, value=round(float(rec['E0']), 4))
        elif k == 1:
            ws2.cell(row=row, column=5, value='24:00')
            ws2.cell(row=row, column=6, value=round(float(rec['E_end']), 4))
        ws2.cell(row=row, column=2, value=seg_labels[k])
        ws2.cell(row=row, column=3, value=round(float(c[s:e].sum()), 4))
        ws2.cell(row=row, column=4, value=round(float(d[s:e].sum()), 4))
        row += 1
print(f"  [充放电量] {len(all_records)}天 × 6段 = {row-2}行 已填入")

# ---------- Sheet3: 紧急购电量（只记录连续非零的紧急购电段） ----------
ws3 = wb['紧急购电量']
if ws3.max_row > 1:
    ws3.delete_rows(2, ws3.max_row - 1)
row = 2
n_emg_seg = 0
for rec in all_records:
    r = rec['r']
    dt = dates_all[rec['n']]
    t = 0
    first = True
    while t < N:
        if r[t] > 1e-9:
            start = t
            while t < N and r[t] > 1e-9:
                t += 1
            end = t  # 连续段 [start, end)
            h1, m1 = divmod(start * 10, 60)
            h2, m2 = divmod(end * 10, 60)
            label = f'{h1}:{m1:02d}-{h2}:{m2:02d}'
            amount = float(r[start:end].sum())
            if first:
                ws3.cell(row=row, column=1, value=dt)
                first = False
            ws3.cell(row=row, column=2, value=label)
            ws3.cell(row=row, column=3, value=round(amount, 4))
            row += 1
            n_emg_seg += 1
        else:
            t += 1
print(f"  [紧急购电量] 共 {n_emg_seg} 个连续紧急购电段 已填入")

# ---------- 统一设置A列宽度与日期格式（避免日期显示为##########） ----------
for _ws in (ws1, ws2, ws3):
    _ws.column_dimensions['A'].width = 12
    for _r in range(2, _ws.max_row + 1):
        _c = _ws.cell(row=_r, column=1)
        if _c.value is not None:
            _c.number_format = 'yyyy-mm-dd'

wb.save(OUTPUT_FILE)
print(f"\n  Excel已保存：{OUTPUT_FILE}")

print("\n" + "=" * 70)
print("全部完成！")
print("=" * 70)
