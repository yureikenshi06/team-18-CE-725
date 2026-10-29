"""Real estate feasibility engine (CE725 Topic 2). Rules follow G3 benchmark spec.
Money internally in Rs; results reported in Rs crore. Months 0..36."""
from dataclasses import dataclass, replace, asdict
from scipy.optimize import brentq

CR = 1e7
SQM_PER_SQFT = 0.092903

@dataclass(frozen=True)
class Inputs:
    plot_area: float = 40000
    fsi: float = 2.5
    carpet_ratio: float = 0.70
    land_price: float = 25000
    stamp_duty: float = 0.06
    reg_rate: float = 0.01
    reg_cap: float = 30000
    construction_cost: float = 3200
    contingency: float = 0.05
    approvals: float = 0.20          # fraction of (land + construction)
    approvals_m1: float = 0.5
    approvals_m3: float = 0.5
    marketing: float = 0.03
    rera_rate: float = 10
    rera_min: float = 50000
    rera_month: int = 5
    sale_price: float = 32000
    escalation: float = 0.0          # per year, applied to sale price by booking month
    construction_months: int = 30
    sales_start: int = 6
    sales_end: int = 35
    holdback_month: int = 31
    loan_rate: float = 0.12
    discount_rate: float = 0.15
    tax_rate: float = 0.25168
    tax_month: int = 36
    horizon: int = 36
    max_loan: float = float("inf")   # Rs; shortfall above this is an equity capital call

def progress(t, n):
    if t <= 0: return 0.0
    if t >= n: return 1.0
    x = t / n
    return 3 * x**2 - 2 * x**3

def npv(rate, flows):
    return sum(f / (1 + rate) ** t for t, f in enumerate(flows))

def irr_roots(flows, lo=-0.5, hi=1.0, step=0.001):
    """All monthly IRR roots in [lo, hi], found by scanning for sign changes."""
    roots, r = [], lo
    prev = npv(r, flows)
    while r < hi - 1e-12:
        nxt = r + step
        cur = npv(nxt, flows)
        if prev == 0:
            roots.append(r)
        elif prev * cur < 0:
            roots.append(brentq(lambda x: npv(x, flows), r, nxt, xtol=1e-14))
        r, prev = nxt, cur
    return roots

def irr_monthly(flows):
    """Primary IRR: the smallest non-negative root, else the first root; None if no root."""
    roots = irr_roots(flows)
    if not roots: return None
    pos = [x for x in roots if x >= 0]
    return pos[0] if pos else roots[0]

def sign_changes(flows):
    s = [f for f in flows if abs(f) > 1e-12]
    return sum(1 for a, b in zip(s, s[1:]) if a * b < 0)

def run(p: Inputs):
    T, n = p.horizon, p.construction_months
    built = p.plot_area * p.fsi
    carpet = built * p.carpet_ratio
    land = p.plot_area * p.land_price
    stamp = p.stamp_duty * land
    reg = min(p.reg_rate * land, p.reg_cap)
    constr_total = built * p.construction_cost
    cont_total = p.contingency * constr_total
    appr_total = p.approvals * (land + constr_total)
    rera = max(p.rera_rate * carpet * SQM_PER_SQFT, p.rera_min)
    n_sales = p.sales_end - p.sales_start + 1
    P = [progress(t, n) for t in range(T + 1)]
    dP = [0.0] + [P[t] - P[t - 1] for t in range(1, T + 1)]
    S, C = [0.0] * (T + 1), [0.0] * (T + 1)
    for t in range(T + 1):
        if p.sales_start <= t <= p.sales_end:
            price = p.sale_price * (1 + p.escalation) ** ((t - p.sales_start) / 12)
            S[t] = carpet / n_sales * price
        C[t] = (C[t - 1] if t else 0) + S[t]
    coll = [0.0] * (T + 1)
    for t in range(1, T + 1):
        if t < p.holdback_month:
            if S[t] or dP[t]:
                coll[t] = 0.10 * S[t] + 0.80 * (S[t] * P[t] + C[t - 1] * dP[t])
        elif t == p.holdback_month:
            coll[t] = 0.10 * C[t - 1] + S[t]
        else:
            coll[t] = S[t]
    costs = [dict(land=0, stamp=0, reg=0, approvals=0, construction=0,
                  contingency=0, marketing=0, rera=0) for _ in range(T + 1)]
    costs[0].update(land=land, stamp=stamp, reg=reg)
    costs[1]["approvals"] += p.approvals_m1 * appr_total
    costs[3]["approvals"] += p.approvals_m3 * appr_total
    for t in range(1, T + 1):
        costs[t]["construction"] = constr_total * dP[t]
        costs[t]["contingency"] = cont_total * dP[t]
        costs[t]["marketing"] = p.marketing * S[t]
    costs[p.rera_month]["rera"] += rera
    tot = [sum(c.values()) for c in costs]
    proj = [-tot[0]] + [coll[t] - tot[t] for t in range(1, T + 1)]
    B, I, E = [0.0] * (T + 1), [0.0] * (T + 1), [0.0] * (T + 1)
    for t in range(1, T + 1):
        I[t] = p.loan_rate / 12 * B[t - 1]
        X = B[t - 1] + I[t] - proj[t]
        if X > p.max_loan:
            B[t] = p.max_loan
            E[t] = p.max_loan - X      # negative: equity capital call
        else:
            B[t] = max(X, 0.0)
            E[t] = max(-X, 0.0)        # positive: surplus released to equity
    interest = sum(I)
    revenue = C[T]
    cost_ex = sum(tot)
    profit = revenue - cost_ex - interest
    tax = p.tax_rate * max(profit, 0.0)
    eq = [-tot[0]] + E[1:]
    eq[p.tax_month] -= tax
    r = (1 + p.discount_rate) ** (1 / 12) - 1
    cum, run_sum, payback = [], 0.0, None
    for t, f in enumerate(eq):
        run_sum += f; cum.append(run_sum)
        if payback is None and run_sum >= 0 and t > 0: payback = t
    pi, ei = irr_monthly(proj), irr_monthly(eq)
    ann = lambda m: None if m is None else (1 + m) ** 12 - 1
    out = dict(
        revenue=revenue / CR, cost_ex_interest=cost_ex / CR, interest=interest / CR,
        total_cost=(cost_ex + interest) / CR, profit_before_tax=profit / CR,
        profit_on_cost=profit / (cost_ex + interest), tax=tax / CR,
        profit_after_tax=(profit - tax) / CR, monthly_rate=r,
        project_npv=npv(r, proj) / CR, project_irr_monthly=pi, project_irr_annual=ann(pi),
        equity_npv=npv(r, eq) / CR, equity_irr_monthly=ei, equity_irr_annual=ann(ei),
        payback_month=payback, peak_loan=max(B) / CR, peak_equity=-min(cum) / CR,
        check_collections=abs(sum(coll) - revenue) < 1e-3,
        check_loan_zero=B[T] < 1e-3,
        irr_sign_changes=sign_changes(eq),
        equity_irr_root_count=len(irr_roots(eq)),
        project_irr_root_count=len(irr_roots(proj)),
    )
    series = dict(P=P, dP=dP, S=S, C=C, coll=coll, costs=costs, proj=proj,
                  B=B, I=I, E=E, eq=eq, cum=cum)
    return out, series

def break_even_price(p: Inputs):
    f = lambda x: run(replace(p, sale_price=x))[0]["equity_npv"]
    return brentq(f, 1000, 200000, xtol=1e-6)
