# -*- coding: utf-8 -*-
"""问题四：因果电价预测、计划/结算拆分、三臂分解。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from p4_export import (  # noqa: E402
    ATT4,
    OUT_P42,
    OUT_P43,
    OUT_P3,
    bill_p2,
    bill_p3,
    day_price,
    decompose,
    forecast_attach4,
    load_attach4,
    p2_params_for_day,
    rebill_p3_day,
)


def test_day_price_2d_picks_that_day():
    p = np.arange(365 * 144, dtype=float).reshape(365, 144)
    got = day_price(p, 7)
    assert np.array_equal(got, p[7])
    got[3] = 0.0
    assert p[7, 3] != 0.0


def test_load_attach4_shape_and_range():
    p4 = load_attach4()
    assert p4.shape == (365, 144)
    assert abs(float(p4.min()) - 0.0076) < 1e-9
    assert abs(float(p4.max()) - 1.7936) < 1e-9
    assert ATT4.exists()


def test_forecast_does_not_see_today():
    from p1_microgrid import load_attach1
    from p2_microgrid import load_attach2
    price1 = load_attach1()["电价"].to_numpy(float)
    price4 = load_attach4()
    _, _, dates = load_attach2()
    hat = forecast_attach4(price4, price1, dates)
    assert hat.shape == (365, 144)
    assert np.allclose(hat[0], price1)
    p4b = price4.copy()
    p4b[80] = 9.9
    hat2 = forecast_attach4(p4b, price1, dates)
    assert np.allclose(hat[80], hat2[80])  # 当天预测看不见当天实际
    assert not np.allclose(hat[87], hat2[87])  # 7 天后同星期会用到第 80 天


def test_bill_and_rebill():
    p = np.array([1.0, 2.0])
    gP = np.array([10.0, 8.0])
    gA = np.array([12.0, 5.0])
    r = np.array([1.0, 0.0])
    assert rebill_p3_day({"gP": gP, "gA": gA, "r": r}, p) == bill_p3(p, gP, gA, r)


def test_decompose_splits_reprice_and_strategy():
    p1 = np.array([1.0, 1.0])
    p4 = np.array([2.0, 0.4])
    g = np.array([10.0, 5.0])
    r = np.array([1.0, 0.0])
    s1 = bill_p2(p1, g, r)[2]
    s2 = bill_p2(p4, g, r)[2]
    s3 = bill_p2(p4, np.array([1.0, 14.0]), np.zeros(2))[2]
    d = decompose(s1, s2, s3)
    assert abs(d["reprice"] - (s2 - s1)) < 1e-12
    assert abs(d["strategy"] - (s3 - s2)) < 1e-12


def test_p2_frozen_schedule():
    assert p2_params_for_day(0).lam == 0.60
    assert p2_params_for_day(31).lam == 0.00
    assert p2_params_for_day(157).alpha == 0.90


def test_export_paths_never_result3():
    assert OUT_P42.name == "result4-2.xlsx"
    assert OUT_P43.name == "result4-3.xlsx"
    assert OUT_P3.name == "result3.xlsx"


def test_p3_plan_forecast_bill_actual_identity_when_same():
    """计划价=结算价时，应退化为原来的一维回测。"""
    from p1_microgrid import load_attach1
    from p3_microgrid import load_all
    from p3_backtest import run_backtest
    from p3_export import BEST
    p1 = load_attach1()["电价"].to_numpy(float)
    _p, dates, load_kw, pv_kw, fc = load_all()
    kw = dict(day_range=range(0, 2), use_adjust=True, adjust_mask=(True, True, True), **BEST)
    r1 = run_backtest(p1, dates, load_kw, pv_kw, fc, **kw)
    r2 = run_backtest(p1, dates, load_kw, pv_kw, fc, bill_price=p1, **kw)
    for d in range(2):
        assert abs(r1[d]["cost_total"] - r2[d]["cost_total"]) < 1e-6


if __name__ == "__main__":
    tests = [
        test_day_price_2d_picks_that_day,
        test_load_attach4_shape_and_range,
        test_forecast_does_not_see_today,
        test_bill_and_rebill,
        test_decompose_splits_reprice_and_strategy,
        test_p2_frozen_schedule,
        test_export_paths_never_result3,
        test_p3_plan_forecast_bill_actual_identity_when_same,
    ]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print("all", len(tests), "passed")
