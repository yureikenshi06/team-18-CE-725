import io
from dataclasses import replace
import pandas as pd
import streamlit as st
from engine import Inputs, run, break_even_price, CR
from sensitivity import tornado, two_way, plot_tornado
from memo import Thresholds, build_memo

st.set_page_config(page_title="Real Estate Feasibility Tool", layout="wide")
st.title("Real Estate Project Feasibility Appraisal")
st.caption("CE725 Construction Economics and Finance, Topic 2. All inputs are editable. Defaults are the group's approved benchmark case; "
           "figures marked unverified have not been checked against primary sources.")

d = Inputs()
with st.sidebar:
    st.header("Inputs")
    with st.expander("Land and areas", True):
        plot = st.number_input("Plot area (sq ft)", 1000.0, 1e7, float(d.plot_area), 1000.0)
        fsi = st.number_input("FSI", 0.5, 10.0, d.fsi, 0.1)
        cr = st.slider("Carpet to built-up ratio", 0.5, 0.9, d.carpet_ratio, 0.01)
        land = st.number_input("Land price (Rs per sq ft of plot)", 0.0, 1e6, float(d.land_price), 500.0)
        stamp = st.number_input("Stamp duty incl. metro cess (%) [unverified]", 0.0, 15.0, d.stamp_duty * 100, 0.5) / 100
    with st.expander("Costs", True):
        cc = st.number_input("Construction cost (Rs per sq ft built-up)", 0.0, 50000.0, float(d.construction_cost), 100.0)
        appr = st.number_input("Approvals and premiums (% of land + construction)", 0.0, 100.0, d.approvals * 100, 1.0) / 100
        cont = st.number_input("Contingency (% of construction)", 0.0, 50.0, d.contingency * 100, 0.5) / 100
        mkt = st.number_input("Marketing and brokerage (% of sales)", 0.0, 20.0, d.marketing * 100, 0.5) / 100
    with st.expander("Sales and timing", True):
        price = st.number_input("Sale price (Rs per sq ft carpet)", 0.0, 500000.0, float(d.sale_price), 500.0)
        esc = st.number_input("Price escalation (% a year)", 0.0, 20.0, 0.0, 0.5) / 100
        cm = st.number_input("Construction months", 6, 60, d.construction_months, 1)
        s0 = st.number_input("First sales month", 1, 60, d.sales_start, 1)
        s1 = st.number_input("Last sales month", int(s0), 72, d.sales_end, 1)
    with st.expander("Finance and tax", True):
        lr = st.number_input("Construction loan rate (% a year, nominal)", 0.0, 40.0, d.loan_rate * 100, 0.5) / 100
        cap = st.number_input("Maximum loan (Rs crore, 0 = no limit)", 0.0, 10000.0, 0.0, 5.0)
        dr = st.number_input("Discount rate (% a year, effective)", 0.0, 50.0, d.discount_rate * 100, 0.5) / 100
        tax = st.number_input("Income tax rate (%) [unverified]", 0.0, 60.0, d.tax_rate * 100, 0.5) / 100
    with st.expander("Decision thresholds (assumptions)", False):
        t_irr = st.number_input("Minimum equity IRR (% a year)", 0.0, 100.0, 15.0, 1.0) / 100
        t_poc = st.number_input("Minimum profit on cost (%)", 0.0, 200.0, 20.0, 1.0) / 100

n = int(cm)
p = Inputs(plot_area=plot, fsi=fsi, carpet_ratio=cr, land_price=land, stamp_duty=stamp, construction_cost=cc,
           approvals=appr, contingency=cont, marketing=mkt, sale_price=price, escalation=esc,
           construction_months=n, sales_start=int(s0), sales_end=int(s1), holdback_month=n + 1,
           loan_rate=lr, max_loan=(cap * CR if cap > 0 else float("inf")), discount_rate=dr, tax_rate=tax,
           horizon=max(36, int(s1) + 1, n + 6), tax_month=max(36, int(s1) + 1, n + 6))
if s1 < s0 or int(s1) - int(s0) + 1 < 1:
    st.error("Last sales month must be on or after the first sales month."); st.stop()

o, s = run(p)
be = break_even_price(p)
rows = tornado(p)
rec, memo = build_memo(o, Thresholds(t_irr, t_poc), be, rows)

fmt = lambda x: "n/a" if x is None else f"{x*100:.1f}%"
st.subheader(f"Recommendation: {rec}")
if o["equity_irr_root_count"] > 1: st.warning(f"The equity cash flow has {o['equity_irr_root_count']} IRR roots; the positive root is shown.")
if o["equity_irr_annual"] is None: st.warning("Equity IRR is undefined for this cash flow.")
if not o["check_collections"]: st.error("Check failed: collections do not equal booking value.")
if not o["check_loan_zero"]: st.warning("The loan is not fully repaid by the end of the horizon.")

c = st.columns(4)
c[0].metric("Equity NPV (Rs cr)", f"{o['equity_npv']:.1f}")
c[1].metric("Equity IRR (annual)", fmt(o["equity_irr_annual"]))
c[2].metric("Profit on cost (pre-tax)", fmt(o["profit_on_cost"]))
c[3].metric("Break-even price (Rs/sq ft)", f"{be:,.0f}")
c = st.columns(4)
c[0].metric("Project NPV (Rs cr)", f"{o['project_npv']:.1f}")
c[1].metric("Project IRR (annual)", fmt(o["project_irr_annual"]))
c[2].metric("Payback month (equity)", "none" if o["payback_month"] is None else o["payback_month"])
c[3].metric("Peak equity (Rs cr)", f"{o['peak_equity']:.1f}")

T = p.horizon
cost_keys = ["land", "stamp", "reg", "approvals", "construction", "contingency", "marketing", "rera"]
df = pd.DataFrame({"Month": range(T + 1),
    "Collections": [x / CR for x in s["coll"]],
    **{k.title(): [c_[k] / CR for c_ in s["costs"]] for k in cost_keys},
    "Project cash flow": [x / CR for x in s["proj"]],
    "Loan balance": [x / CR for x in s["B"]], "Interest": [x / CR for x in s["I"]],
    "Equity cash flow": [x / CR for x in s["eq"]], "Cumulative equity": [x / CR for x in s["cum"]]})

tab1, tab2, tab3, tab4 = st.tabs(["Cash flows", "Sensitivity", "Investment memo", "Assumptions and limits"])
with tab1:
    st.line_chart(df.set_index("Month")[["Cumulative equity", "Loan balance"]])
    st.bar_chart(df.set_index("Month")[["Collections", "Project cash flow"]])
    st.dataframe(df.style.format({c_: "{:,.2f}" for c_ in df.columns if c_ != "Month"}), width="stretch", hide_index=True)
with tab2:
    import matplotlib; matplotlib.use("Agg")
    import tempfile, os
    path = os.path.join(tempfile.gettempdir(), "tornado_app.png")
    plot_tornado(rows, path); st.image(path)
    st.caption("Change in equity NPV vs the current case for a 10% change in each driver.")
    grid = two_way(p, "Sale price", "Construction cost")
    labels = ["-10%", "-5%", "0%", "+5%", "+10%"]
    st.write("Sale price (rows) against construction cost (columns): change in equity NPV, Rs crore")
    st.dataframe(pd.DataFrame(grid, index=labels, columns=labels).style.format("{:,.2f}"))
with tab3:
    st.text(memo)
with tab4:
    st.markdown("""
- Single project phase, one tax rate, no loss carry-forward; tax is paid once at the end of the horizon.
- GST is treated as a pass-through collected from buyers and is not a project cost.
- No RERA escrow modelling (see Topic 14). Collections follow a construction-linked plan.
- Sources are mostly secondary (news and lender articles). Stamp duty, GST and income tax rates are unverified against primary sources.
- IRR can be undefined or have several roots when the cash flow changes sign more than once; the tool warns when this happens.
- Do not rely on this tool for a real investment decision without independent checking of every input.
""")

try:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Cash flows", index=False)
        pd.DataFrame({"Item": list(o.keys()), "Value": [str(v) for v in o.values()]}).to_excel(xw, sheet_name="Results", index=False)
        pd.DataFrame({"Item": list(vars(p).keys()), "Value": [str(v) for v in vars(p).values()]}).to_excel(xw, sheet_name="Inputs", index=False)
        pd.DataFrame({"Memo": memo.split("\n")}).to_excel(xw, sheet_name="Memo", index=False)
    st.download_button("Download results (Excel)", buf.getvalue(), "feasibility_results.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
except Exception as exc:  # export must never break the appraisal itself
    st.warning(f"Excel export is unavailable: {type(exc).__name__}")
