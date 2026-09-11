# -*- coding: utf-8 -*-
<<<<<<< Updated upstream
"""问题四：二维电价、费用口径、导出路径。先于 p4_export 实现编写。"""
=======
"""问题四：二维电价、重计价、三臂分解。"""
>>>>>>> Stashed changes
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

<<<<<<< Updated upstream
ROOT = Path(__file__).resolve().parents[1]
=======
>>>>>>> Stashed changes
sys.path.insert(0, str(Path(__file__).resolve().parent))

from p4_export import (  # noqa: E402
    ATT4,
    OUT_P42,
    OUT_P43,
    OUT_P3,
<<<<<<< Updated upstream
    P2_FIXED_TOTAL,
    P3_FIXED_TOTAL,
    bill_p2,
    bill_p3,
    day_price,
    load_attach4,
    p2_params_for_day,
=======
    bill_p2,
    bill_p3,
    day_price,
    decompose,
    load_attach4,
    p2_params_for_day,
    rebill_p3_day,
>>>>>>> Stashed changes
)


def test_day_price_1d_unchanged():
    p = np.arange(144, dtype=float)
    got = day_price(p, 12)
    assert got.shape == (144,)
    assert np.array_equal(got, p)
    got[0] = -1
<<<<<<< Updated upstream
    assert p[0] == 0.0  # 返回副本，避免改到全年电价
=======
    assert p[0] == 0.0
>>>>>>> Stashed changes


def test_day_price_2d_picks_that_day():
    p = np.arange(365 * 144, dtype=float).reshape(365, 144)
    got = day_price(p, 7)
    assert np.array_equal(got, p[7])
    got[3] = 0.0
    assert p[7, 3] != 0.0


def test_load_attach4_shape_and_range():
    p4 = load_attach4()
    assert p4.shape == (365, 144)
    assert np.isfinite(p4).all()
    assert abs(float(p4.min()) - 0.0076) < 1e-9
    assert abs(float(p4.max()) - 1.7936) < 1e-9
    assert ATT4.exists()


def test_bill_p2_plan_plus_five_times_emergency():
    p = np.array([0.4, 0.8, 1.2])
    g = np.array([10.0, 0.0, 5.0])
    r = np.array([0.0, 2.0, 1.0])
    plan, emg, tot = bill_p2(p, g, r)
<<<<<<< Updated upstream
    assert abs(plan - (0.4 * 10 + 0.8 * 0 + 1.2 * 5)) < 1e-12
=======
    assert abs(plan - (0.4 * 10 + 1.2 * 5)) < 1e-12
>>>>>>> Stashed changes
    assert abs(emg - 5 * (0.8 * 2 + 1.2 * 1)) < 1e-12
    assert abs(tot - (plan + emg)) < 1e-12


def test_bill_p3_up_1p5_down_0p5_emg_5():
    p = np.array([1.0, 2.0])
    gP = np.array([10.0, 8.0])
<<<<<<< Updated upstream
    gA = np.array([12.0, 5.0])  # +2 上调, -3 下调
    r = np.array([1.0, 0.0])
    pa, emg, tot = bill_p3(p, gP, gA, r)
    expect_pa = (1.0 * 10 + 1.5 * 1.0 * 2) + (2.0 * 8 - 0.5 * 2.0 * 3)
    expect_emg = 5 * 1.0 * 1.0
    assert abs(pa - expect_pa) < 1e-12
    assert abs(emg - expect_emg) < 1e-12
=======
    gA = np.array([12.0, 5.0])
    r = np.array([1.0, 0.0])
    pa, emg, tot = bill_p3(p, gP, gA, r)
    expect_pa = (1.0 * 10 + 1.5 * 1.0 * 2) + (2.0 * 8 - 0.5 * 2.0 * 3)
    assert abs(pa - expect_pa) < 1e-12
    assert abs(emg - 5.0) < 1e-12
>>>>>>> Stashed changes
    assert abs(tot - (pa + emg)) < 1e-12


def test_p2_frozen_schedule_matches_calibration_log():
<<<<<<< Updated upstream
    # 1 月默认 λ=0.60；2/1 起用已标定日程，不再按波动电价重标定
=======
>>>>>>> Stashed changes
    jan = p2_params_for_day(0)
    assert jan.alpha == 0.80 and jan.rho == 1.0 and jan.lam == 0.60
    assert p2_params_for_day(30).lam == 0.60
    feb = p2_params_for_day(31)
    assert feb.alpha == 0.80 and feb.rho == 1.0 and feb.lam == 0.00
<<<<<<< Updated upstream
    jun = p2_params_for_day(157)  # 2025-06-07
    assert jun.alpha == 0.90 and jun.rho == 1.0 and jun.lam == 0.00
    aug = p2_params_for_day(241)  # 2025-08-30
    assert aug.alpha == 0.70 and aug.rho == 0.0
    assert p2_params_for_day(324).alpha == 0.80
    assert p2_params_for_day(325).alpha == 0.80  # 11-22 仍是 0.80
=======
    jun = p2_params_for_day(157)
    assert jun.alpha == 0.90 and jun.rho == 1.0
    aug = p2_params_for_day(241)
    assert aug.alpha == 0.70 and aug.rho == 0.0
    assert p2_params_for_day(325).alpha == 0.80
>>>>>>> Stashed changes


def test_export_paths_never_result3():
    assert OUT_P42.name == "result4-2.xlsx"
    assert OUT_P43.name == "result4-3.xlsx"
    assert OUT_P3.name == "result3.xlsx"
    assert OUT_P42.resolve() != OUT_P3.resolve()
    assert OUT_P43.resolve() != OUT_P3.resolve()
<<<<<<< Updated upstream
    assert "result3.xlsx" not in {OUT_P42.name, OUT_P43.name}


def test_fixed_totals_are_the_locked_baselines():
    assert abs(P2_FIXED_TOTAL - 14021565.119404145) < 1.0
    assert abs(P3_FIXED_TOTAL - 13384828.869660389) < 1.0
=======


def test_rebill_p3_day_uses_settlement_price_only():
    gP = np.array([10.0, 8.0])
    gA = np.array([12.0, 5.0])
    r = np.array([1.0, 0.0])
    p4 = np.array([2.0, 0.5])
    pa, emg, tot = rebill_p3_day({"gP": gP, "gA": gA, "r": r}, p4)
    expect = bill_p3(p4, gP, gA, r)
    assert abs(pa - expect[0]) < 1e-12
    assert abs(emg - expect[1]) < 1e-12
    assert abs(tot - expect[2]) < 1e-12


def test_decompose_splits_reprice_and_strategy():
    p1 = np.array([1.0, 1.0])
    p4 = np.array([2.0, 0.4])
    g = np.array([10.0, 5.0])
    r = np.array([1.0, 0.0])
    g_new = np.array([1.0, 14.0])
    r_new = np.array([0.0, 0.0])
    s1 = bill_p2(p1, g, r)[2]
    s2 = bill_p2(p4, g, r)[2]
    s3 = bill_p2(p4, g_new, r_new)[2]
    d = decompose(s1, s2, s3)
    assert abs(d["reprice"] - (s2 - s1)) < 1e-12
    assert abs(d["strategy"] - (s3 - s2)) < 1e-12
    assert abs(d["total"] - (s3 - s1)) < 1e-12
    assert abs(d["reprice"] - (np.sum((p4 - p1) * g) + 5 * np.sum((p4 - p1) * r))) < 1e-12


def test_p3_backtest_2d_identical_to_1d():
    from p1_microgrid import load_attach1
    from p3_microgrid import load_all
    from p3_backtest import run_backtest
    from p3_export import BEST
    p1 = load_attach1()["电价"].to_numpy(float)
    _p, dates, load_kw, pv_kw, fc = load_all()
    p2d = np.tile(p1, (365, 1))
    kw = dict(day_range=range(0, 2), use_adjust=True, adjust_mask=(True, True, True), **BEST)
    r1 = run_backtest(p1, dates, load_kw, pv_kw, fc, **kw)
    r2 = run_backtest(p2d, dates, load_kw, pv_kw, fc, **kw)
    for d in range(2):
        assert abs(r1[d]["cost_total"] - r2[d]["cost_total"]) < 1e-6
        assert r2[d]["cost_total"] < 1e6
>>>>>>> Stashed changes


if __name__ == "__main__":
    tests = [
        test_day_price_1d_unchanged,
        test_day_price_2d_picks_that_day,
        test_load_attach4_shape_and_range,
        test_bill_p2_plan_plus_five_times_emergency,
        test_bill_p3_up_1p5_down_0p5_emg_5,
        test_p2_frozen_schedule_matches_calibration_log,
        test_export_paths_never_result3,
<<<<<<< Updated upstream
        test_fixed_totals_are_the_locked_baselines,
=======
        test_rebill_p3_day_uses_settlement_price_only,
        test_decompose_splits_reprice_and_strategy,
        test_p3_backtest_2d_identical_to_1d,
>>>>>>> Stashed changes
    ]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print("all", len(tests), "passed")
