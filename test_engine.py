import math
from dataclasses import replace
from engine import *

base = Inputs()
out, s = run(base)

def test_areas_and_land():
    assert abs(sum(c["land"] for c in s["costs"]) / CR - 100.0) < 1e-9
    assert abs(sum(c["stamp"] for c in s["costs"]) / CR - 6.0) < 1e-9
    assert sum(c["reg"] for c in s["costs"]) == 30000

def test_approvals_and_construction():
    assert abs(sum(c["approvals"] for c in s["costs"]) / CR - 26.4) < 1e-9
    assert abs(sum(c["construction"] for c in s["costs"]) / CR - 32.0) < 1e-9
    assert abs(sum(c["contingency"] for c in s["costs"]) / CR - 1.6) < 1e-9

def test_progress_curve():
    assert progress(0, 30) == 0 and progress(30, 30) == 1 and progress(45, 30) == 1
    assert abs(progress(15, 30) - 0.5) < 1e-12
    assert all(d >= 0 for d in s["dP"])

def test_sales_and_collections():
    assert abs(out["revenue"] - 224.0) < 1e-9
    assert out["check_collections"]
    assert s["S"][5] == 0 and s["S"][36] == 0 and s["S"][6] > 0 and s["S"][35] > 0

def test_loan_clears():
    assert out["check_loan_zero"]
    assert all(b >= 0 for b in s["B"])

def test_rera_min_applies():
    small = replace(base, plot_area=1000)
    assert abs(sum(c["rera"] for c in run(small)[1]["costs"]) - 50000) < 1e-6

def test_npv_irr_consistency():
    r = out["monthly_rate"]
    assert abs(r - (1.15 ** (1 / 12) - 1)) < 1e-15
    assert abs(npv(out["equity_irr_monthly"], s["eq"])) < 1e-3
    assert abs(npv(out["project_irr_monthly"], s["proj"])) < 1e-3

def test_zero_rate_npv_is_sum():
    assert abs(npv(0, s["eq"]) - sum(s["eq"])) < 1e-6

def test_break_even_gives_zero_npv():
    be = break_even_price(base)
    assert abs(run(replace(base, sale_price=be))[0]["equity_npv"]) < 1e-6

def test_monotonic_in_price():
    assert run(replace(base, sale_price=36000))[0]["equity_npv"] > out["equity_npv"] > run(replace(base, sale_price=28000))[0]["equity_npv"]

def test_loss_pays_no_tax():
    assert run(replace(base, sale_price=15000))[0]["tax"] == 0

def test_zero_sales_edge():
    o = run(replace(base, sale_price=0))[0]
    assert o["revenue"] == 0 and o["tax"] == 0 and o["equity_irr_monthly"] is None

def test_small_hand_case():
    # hand check: plot 100, FSI 1, carpet 100%, no costs except land at 10/sqft, 1 month sale
    p = Inputs(plot_area=100, fsi=1, carpet_ratio=1, land_price=10, stamp_duty=0, reg_cap=0,
               construction_cost=0, contingency=0, approvals=0, marketing=0, rera_min=0, rera_rate=0,
               sale_price=20, sales_start=6, sales_end=6, tax_rate=0, construction_months=30)
    o, ss = run(p)
    assert abs(ss["S"][6] - 2000) < 1e-9          # 100 sq ft x 20
    assert abs(ss["coll"][6] - 2000 * (0.1 + 0.8 * progress(6, 30))) < 1e-6
    assert abs(sum(ss["coll"]) - 2000) < 1e-6

def test_multiple_root_flagged():
    # classic -100, +230, -132 has two IRRs (10% and 20%)
    roots = irr_roots([-100, 230, -132], lo=-0.5, hi=1.0)
    assert len(roots) == 2 and abs(roots[0] - 0.10) < 1e-6 and abs(roots[1] - 0.20) < 1e-6

def test_equity_irr_is_positive_root():
    assert out["equity_irr_monthly"] is not None and out["equity_irr_monthly"] > 0

def test_default_loan_cap_changes_nothing():
    assert run(replace(base, max_loan=1e15))[0] == out

def test_loan_cap_binds_and_balances():
    cap = 20 * CR
    o, ss = run(replace(base, max_loan=cap))
    assert max(ss["B"]) <= cap + 1e-6
    assert min(ss["E"]) < 0                      # a capital call happens
    for t in range(1, 37):                       # cash identity: B - E = B_prev + I - project CF
        assert abs((ss["B"][t] - ss["E"][t]) - (ss["B"][t-1] + ss["I"][t] - ss["proj"][t])) < 1e-3
    assert o["check_loan_zero"]
    assert o["peak_equity"] > out["peak_equity"]

if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try: fn(); print("PASS", name)
            except AssertionError as e: fails += 1; print("FAIL", name, e)
            except Exception as e: fails += 1; print("ERROR", name, repr(e))
    print("failures:", fails)

