# Business Requirements

**Simulated client:** GulfMart Retail Group — UAE retail/e-commerce, operating
in Dubai, Abu Dhabi, Sharjah, Ajman and Ras Al Khaimah.
**Status:** v1.0 — Phase 0, Week 1.

This document is the business half of Phase 0. It exists so that every later
decision (schema design, KPI formula, model choice, dashboard page) traces
back to a stated need, not to "what a dashboard usually has." See
[`docs/kpi_dictionary.md`](kpi_dictionary.md) for the KPI-level answer to
these requirements, and [`docs/data_dictionary.md`](data_dictionary.md) for
the PUBLIC/SYNTHETIC/DERIVED labeling convention referenced throughout.

---

## 1. Business context

GulfMart is a fictional UAE retail/e-commerce group. Management does not
currently have a single, governed view across sales, inventory, suppliers and
logistics — decisions are made from disconnected exports. This platform is
commissioned to close that gap: take raw multi-source data and turn it into
governed, queryable, forecastable, risk-scored decision support.

No public dataset represents real UAE retail operations end to end. This is
disclosed up front (see §5) rather than hidden — the project demonstrates
multi-source integration and synthetic-data generation as a deliberate
engineering exercise, not as a stand-in for real GulfMart data.

## 2. Business objectives

The platform must let management answer, with evidence rather than
anecdote:

| # | Objective question | Primarily served by |
|---|---|---|
| 1 | What products and regions are driving revenue? | Sales KPIs, SQL analytics (Phase 3–4) |
| 2 | Where are we experiencing stockouts and excess inventory? | Inventory KPIs, EDA (Phase 3–4) |
| 3 | Which suppliers are creating operational risk? | Supplier risk scoring (Phase 7) |
| 4 | Can we forecast future demand? | Demand forecasting (Phase 6) |
| 5 | What unusual transactions/inventory movements need investigation? | Anomaly detection (Phase 8) |
| 6 | What happens if demand, lead time, or transport cost change? | Scenario engine (Phase 9) |
| 7 | Which operational decisions improve service levels while controlling cost? | Executive report recommendations (Phase 11), grounded in the above |

Every KPI, model and dashboard page built in later phases must trace to at
least one of these seven questions. A metric that doesn't answer one of
these is scope creep, not a requirement.

## 3. Stakeholders and their requirements

### 3.1 Chief Operations Officer (COO)

- **Role in the business:** owns end-to-end supply chain performance across
  all five emirates.
- **Needs:** a single supply-chain overview — revenue and volume trend,
  inventory efficiency, supplier performance, cost trends — without having
  to reconcile numbers across tools.
- **Key questions:** Are we growing? Are we efficient? Are costs under
  control? Where is the business most exposed to risk right now?
- **Decisions supported:** where to focus operational attention this
  quarter; which region/category to invest in or deprioritize.
- **Consumes:** `Total Revenue`, `Gross Margin`, `Inventory Turnover`,
  `Supplier OTD`, `Transport Cost`, `Supplier Risk Score` (see
  [`kpi_dictionary.md`](kpi_dictionary.md)).
- **Primary BI page:** Power BI "Executive Overview" (Phase 10).

### 3.2 Supply Chain Manager

- **Role in the business:** owns day-to-day inventory availability and
  supplier delivery performance.
- **Needs:** stockout information, supplier delays, inventory risk, demand
  forecast, at a granularity fine enough to act on (product × warehouse ×
  week).
- **Key questions:** Which SKUs are at risk of stocking out in the next
  2–4 weeks? Which suppliers are consistently late? Is excess stock tying up
  capital anywhere?
- **Decisions supported:** reorder timing and quantity; which suppliers to
  put on a corrective plan; which warehouses need rebalancing.
- **Consumes:** `Stockout Rate`, `Fill Rate`, `Average Lead Time`,
  `Supplier OTD`, demand forecast output + prediction intervals, anomaly
  flags.
- **Primary BI pages:** "Inventory", "Supplier & Logistics" (Phase 10).

### 3.3 Procurement Manager

- **Role in the business:** owns supplier selection and contract
  performance.
- **Needs:** supplier comparison, lead-time variability, supplier risk,
  cost trends by supplier.
- **Key questions:** Which suppliers are most reliable vs. most volatile?
  Is any supplier's risk trending upward? Are we paying more for the same
  reliability elsewhere?
- **Decisions supported:** supplier renegotiation, diversification,
  onboarding new suppliers, escalation of underperforming ones.
- **Consumes:** `Supplier Risk Score` and risk level (Low/Medium/High/
  Critical), `Average Lead Time`, lead-time standard deviation, `Supplier
  OTD`, cost variability.
- **Primary BI page:** "Supplier & Logistics" (Phase 10).

### 3.4 Finance Manager

- **Role in the business:** owns inventory valuation, logistics cost, and
  revenue reporting.
- **Needs:** inventory value, logistics cost, revenue impact of supply
  chain decisions.
- **Key questions:** How much capital is tied up in inventory right now?
  What is transport cost doing over time? What is the revenue-at-risk from
  current stockouts or supplier delays?
- **Decisions supported:** working-capital planning; whether a proposed
  operational change (e.g. faster shipping, safety-stock increase) is worth
  its cost — answered concretely via the scenario engine (Phase 9).
- **Consumes:** `Inventory Value`, `Transport Cost`, `Total Revenue`,
  `Gross Margin`, scenario engine's revenue-at-risk output.
- **Primary BI pages:** "Executive Overview", "Scenario Simulator"
  (Phase 10).

## 4. Scope

**In scope:**
- Sales, inventory, supplier, logistics and macro (UAE trade/CPI) data,
  integrated into one warehouse.
- KPI reporting, statistical analysis, demand forecasting, supplier risk
  scoring, anomaly detection, and what-if scenario modelling.
- A queryable API and BI layer over all of the above.

**Out of scope (stated explicitly, not silently dropped):**
- Real GulfMart transactional data — none exists; all "GulfMart" data is
  public data re-labeled for context or synthetically generated (§5,
  [`data_dictionary.md`](data_dictionary.md)).
- Production drift monitoring / automated model retraining — noted as a
  future improvement in the executive report (Phase 11), not built here.
- Multi-tenant, multi-currency, or multi-language support — single
  simulated retailer, AED context only.

## 5. Data source labeling convention

Every table, column, and derived metric in this project must carry exactly
one of these labels, enforced from Phase 1 onward:

| Label | Meaning | Examples |
|---|---|---|
| **PUBLIC** | Sourced from a real public dataset, unmodified in meaning (values may be cleaned/standardized, not fabricated) | Olist orders, DataCo shipments, M5 sales, UAE Open Data trade/CPI |
| **SYNTHETIC** | Generated by this project, with distributions derived from PUBLIC data, but not real observations | `inventory.csv`, `purchase_orders.csv`, `warehouses.csv` |
| **DERIVED** | Computed from PUBLIC and/or SYNTHETIC data | KPIs, supplier risk scores, forecasts, anomaly flags |

Rules:
1. No output (chart, KPI, report line) may be presented without its label
   being knowable from `docs/data_dictionary.md` or inline schema comments.
2. SYNTHETIC data must never be presented as if it were an observed
   GulfMart fact — always framed as "modelled" or "simulated" in the
   executive report.
3. This convention is defined once, here and in
   [`data_dictionary.md`](data_dictionary.md), and referenced everywhere
   else — it is not restated with different wording elsewhere.

## 6. Success criteria

This phase (and the project) is done against the checklist in
[`implementation_plan.md`](implementation_plan.md) and the PRD's Definition
of Done. For Phase 0 specifically:

- [ ] Every stakeholder in §3 has documented needs, key questions, and a
      named set of consuming KPIs.
- [ ] Every KPI in [`kpi_dictionary.md`](kpi_dictionary.md) has a formula,
      an owning table, and a data-source label.
- [ ] The labeling convention in §5 is the single source of truth (no
      contradicting definitions elsewhere in `docs/`).

## 7. Risks and limitations (carried forward to the executive report)

- No public dataset represents real UAE retail operations — disclosed
  throughout, not hidden.
- Synthetic inventory/procurement data is rule-generated from real-data
  distributions, not independently validated against real operations.
- Forecasting and risk models are demonstrative at this data volume;
  production deployment would need drift monitoring and periodic
  retraining, out of scope here.
- Seasonal/holiday effects (Ramadan, Eid, etc.) will be tested
  statistically in Phase 4/5, never assumed — a null result is a valid,
  reportable finding.
