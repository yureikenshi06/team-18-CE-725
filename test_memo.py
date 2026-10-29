from dataclasses import replace
from engine import Inputs, run
from memo import *

def memo_for(**kw):
    o = run(replace(Inputs(), **kw))[0]
    return o, build_memo(o, Thresholds())

def test_numbers_come_from_model():
    o, (rec, text) = memo_for()
    assert f"{o['revenue']:.1f}" in text and f"{o['equity_npv']:.1f}" in text and rec in text

def test_loss_case_is_no_go():
    o, (rec, text) = memo_for(sale_price=15000)
    assert rec == "NO-GO" and "not met" in text

def test_thresholds_drive_recommendation():
    o = run(Inputs())[0]
    assert recommendation(o, Thresholds(min_equity_irr=0.0, min_profit_on_cost=0.0))[0] == "GO" or o["equity_npv"] <= 0
    assert recommendation(o, Thresholds(min_equity_irr=9.0, min_profit_on_cost=9.0))[0] in ("REVIEW", "NO-GO")

def test_zero_sales_does_not_crash():
    o, (rec, text) = memo_for(sale_price=0)
    assert rec == "NO-GO" and "could not be computed" in text

def test_multiple_root_warning():
    o = dict(run(Inputs())[0]); o["equity_irr_root_count"] = 2
    assert "2 IRR roots" in build_memo(o, Thresholds())[1]

if __name__ == "__main__":
    f = 0
    for n, fn in list(globals().items()):
        if n.startswith("test_"):
            try: fn(); print("PASS", n)
            except AssertionError as e: f += 1; print("FAIL", n, e)
            except Exception as e: f += 1; print("ERROR", n, repr(e))
    print("failures:", f)
