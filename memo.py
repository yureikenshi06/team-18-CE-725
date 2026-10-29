"""Rule-based investment memo. Every sentence is built from model output; no free-text generation."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Thresholds:
    min_equity_irr: float = 0.15       # annual; assumption, set equal to the discount rate
    min_profit_on_cost: float = 0.20   # assumption

def recommendation(o, th: Thresholds):
    irr = o["equity_irr_annual"]
    npv_ok = o["equity_npv"] > 0
    irr_ok = irr is not None and irr >= th.min_equity_irr
    poc_ok = o["profit_on_cost"] >= th.min_profit_on_cost
    if npv_ok and irr_ok and poc_ok: return "GO", (npv_ok, irr_ok, poc_ok)
    if (not npv_ok) and (not poc_ok): return "NO-GO", (npv_ok, irr_ok, poc_ok)
    return "REVIEW", (npv_ok, irr_ok, poc_ok)

def _pct(x): return "undefined" if x is None else f"{x*100:.1f}%"

def build_memo(o, th: Thresholds, break_even=None, tornado_rows=None, warnings=()):
    rec, (npv_ok, irr_ok, poc_ok) = recommendation(o, th)
    L = [f"INVESTMENT MEMO: RESIDENTIAL PROJECT FEASIBILITY", f"Recommendation: {rec}", ""]
    L.append("Summary")
    L.append(f"The project books Rs {o['revenue']:.1f} crore of sales against Rs {o['total_cost']:.1f} crore of total cost "
             f"including Rs {o['interest']:.1f} crore of interest, giving a pre-tax profit of Rs {o['profit_before_tax']:.1f} crore "
             f"({_pct(o['profit_on_cost'])} on cost) and Rs {o['profit_after_tax']:.1f} crore after tax.")
    L.append("")
    L.append("Returns")
    L.append(f"Equity NPV at the hurdle rate is Rs {o['equity_npv']:.1f} crore and equity IRR is {_pct(o['equity_irr_annual'])} a year. "
             f"Project NPV before financing and tax is Rs {o['project_npv']:.1f} crore with a project IRR of {_pct(o['project_irr_annual'])}.")
    pb = o["payback_month"]
    L.append(f"Equity pays back in month {pb}." if pb is not None else "Equity does not pay back within the model horizon.")
    L.append(f"Peak equity invested is Rs {o['peak_equity']:.1f} crore and the peak loan balance is Rs {o['peak_loan']:.1f} crore.")
    if break_even is not None:
        L.append(f"The break-even sale price, where equity NPV is zero, is Rs {break_even:,.0f} per sq ft of carpet area.")
    L.append("")
    L.append("Decision tests")
    L.append(f"NPV above zero: {'met' if npv_ok else 'not met'}. "
             f"Equity IRR of at least {_pct(th.min_equity_irr)}: {'met' if irr_ok else 'not met'}. "
             f"Profit on cost of at least {_pct(th.min_profit_on_cost)}: {'met' if poc_ok else 'not met'}.")
    L.append("The thresholds are user-set assumptions, not market data. GO needs all three tests; NO-GO needs NPV and profit on cost both to fail; anything else is REVIEW.")
    if tornado_rows:
        top = tornado_rows[:2]
        L.append("")
        L.append("Main risks")
        L.append("The two drivers that move equity NPV most for a 10% change are "
                 + " and ".join(f"{r['driver'].lower()} (swing Rs {r['swing']:.1f} crore)" for r in top) + ".")
    ws = list(warnings)
    if o.get("equity_irr_root_count", 1) > 1:
        ws.append(f"The equity cash flow has {o['equity_irr_root_count']} IRR roots; the positive root is reported.")
    if o["equity_irr_annual"] is None:
        ws.append("Equity IRR could not be computed for this cash flow.")
    if not o["check_collections"]: ws.append("Collections do not equal booking value.")
    if not o["check_loan_zero"]: ws.append("The loan is not fully repaid by the end of the horizon.")
    if ws:
        L.append(""); L.append("Warnings")
        L.extend(f"- {w}" for w in ws)
    L.append("")
    L.append("Limitations: single phase, single tax rate with no loss carry-forward, no RERA escrow modelling, GST treated as pass-through, "
             "inputs are user-supplied and unverified unless sourced.")
    return rec, "\n".join(L)
