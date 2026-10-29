from engine import Inputs, run
from sensitivity import *
p = Inputs(); base = run(p)[0]["equity_npv"]

def test_zero_shock_is_zero():
    for d in DRIVERS:
        assert abs(run(vary(p, d, 0.0))[0]["equity_npv"] - base) < 1e-9

def test_signs():
    t = {r["driver"]: r for r in tornado(p)}
    assert t["Sale price"]["plus"] > 0 > t["Sale price"]["minus"]
    assert t["Construction cost"]["plus"] < 0 < t["Construction cost"]["minus"]
    assert t["Land cost"]["plus"] < 0 < t["Land cost"]["minus"]
    assert t["Loan interest rate"]["plus"] < 0 < t["Loan interest rate"]["minus"]

def test_sorted_by_swing():
    s = [r["swing"] for r in tornado(p)]
    assert s == sorted(s, reverse=True)

def test_all_variants_run_clean():
    for d in DRIVERS:
        for sh in (-0.1, 0.1):
            o = run(vary(p, d, sh))[0]
            assert o["check_collections"] and o["check_loan_zero"], (d, sh)

def test_two_way_centre_is_zero():
    g = two_way(p, "Sale price", "Construction cost")
    assert abs(g[2][2]) < 1e-9 and g[4][2] > g[0][2]

if __name__ == "__main__":
    fails = 0
    for n, fn in list(globals().items()):
        if n.startswith("test_"):
            try: fn(); print("PASS", n)
            except AssertionError as e: fails += 1; print("FAIL", n, e)
            except Exception as e: fails += 1; print("ERROR", n, repr(e))
    print("failures:", fails)
