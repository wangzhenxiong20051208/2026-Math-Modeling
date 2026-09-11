# -*- coding: utf-8 -*-
"""问题四：二维电价、费用口径、导出路径。先于 p4_export 实现编写。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from p4_export import (  # noqa: E402
    ATT4,
    OUT_P42,
    OUT_P43,
    OUT_P3,
    P2_FIXED_TOTAL,
    P3_FIXED_TOTAL,
    bill_p2,
    bill_p3,
    day_price,
    load_attach4,
    p2_params_for_day,
)


def test_day_price_1d_unchanged():
    p = np.arange(144, dtype=float)
    got = day_price(p, 12)
    assert got.shape == (144,)
    assert np.array_equal(got, p)
    got[0] = -1
    assert p[0] == 0.0  # 返回副本，避免改到全年电价


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
    assert abs(plan - (0.4 * 10 + 0.8 * 0 + 1.2 * 5)) < 1e-12
    assert abs(emg - 5 * (0.8 * 2 + 1.2 * 1)) < 1e-12
    assert abs(tot - (plan + emg)) < 1e-12


def test_bill_p3_up_1p5_down_0p5_emg_5():
    p = np.array([1.0, 2.0])
    gP = np.array([10.0, 8.0])
    gA = np.array([12.0, 5.0])  # +2 上调, -3 下调
    r = np.array([1.0, 0.0])
    pa, emg, tot = bill_p3(p, gP, gA, r)
    expect_pa = (1.0 * 10 + 1.5 * 1.0 * 2) + (2.0 * 8 - 0.5 * 2.0 * 3)
    expect_emg = 5 * 1.0 * 1.0
    assert abs(pa - expect_pa) < 1e-12
    assert abs(emg - expect_emg) < 1e-12
    assert abs(tot - (pa + emg)) < 1e-12


def test_p2_frozen_schedule_matches_calibration_log():
    # 1 月默认 λ=0.60；2/1 起用已标定日程，不再按波动电价重标定
    jan = p2_params_for_day(0)
    assert jan.alpha == 0.80 and jan.rho == 1.0 and jan.lam == 0.60
    assert p2_params_for_day(30).lam == 0.60
    feb = p2_params_for_day(31)
    assert feb.alpha == 0.80 and feb.rho == 1.0 and feb.lam == 0.00
    jun = p2_params_for_day(157)  # 2025-06-07
    assert jun.alpha == 0.90 and jun.rho == 1.0 and jun.lam == 0.00
    aug = p2_params_for_day(241)  # 2025-08-30
    assert aug.alpha == 0.70 and aug.rho == 0.0
    assert p2_params_for_day(324).alpha == 0.80
    assert p2_params_for_day(325).alpha == 0.80  # 11-22 仍是 0.80


def test_export_paths_never_result3():
    assert OUT_P42.name == "result4-2.xlsx"
    assert OUT_P43.name == "result4-3.xlsx"
    assert OUT_P3.name == "result3.xlsx"
    assert OUT_P42.resolve() != OUT_P3.resolve()
    assert OUT_P43.resolve() != OUT_P3.resolve()
    assert "result3.xlsx" not in {OUT_P42.name, OUT_P43.name}


def test_fixed_totals_are_the_locked_baselines():
    assert abs(P2_FIXED_TOTAL - 14021565.119404145) < 1.0
    assert abs(P3_FIXED_TOTAL - 13384828.869660389) < 1.0


if __name__ == "__main__":
    tests = [
        test_day_price_1d_unchanged,
        test_day_price_2d_picks_that_day,
        test_load_attach4_shape_and_range,
        test_bill_p2_plan_plus_five_times_emergency,
        test_bill_p3_up_1p5_down_0p5_emg_5,
        test_p2_frozen_schedule_matches_calibration_log,
        test_export_paths_never_result3,
        test_fixed_totals_are_the_locked_baselines,
    ]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print("all", len(tests), "passed")
