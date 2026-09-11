# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p4_export import forecast_attach4, load_attach4, day_price, OUT_P42, OUT_P43, OUT_P3


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
    assert np.allclose(hat[80], hat2[80])
    assert not np.allclose(hat[87], hat2[87])


def test_export_paths():
    assert OUT_P42.name == "result4-2.xlsx"
    assert OUT_P43.name == "result4-3.xlsx"
    assert OUT_P3.name == "result3.xlsx"


if __name__ == "__main__":
    test_forecast_does_not_see_today()
    print("ok forecast")
    test_export_paths()
    print("ok paths")
    print("all passed")
