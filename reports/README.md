# Reports

Curated outputs of each phase, plus the Phase 11 executive report.

- [`executive_report/`](executive_report/) — the 10-15 page executive report
  (`executive_report.pdf`; readable version `executive_report.md`): summary,
  business problem, architecture, data quality, sales/inventory/supplier
  findings, forecasting, anomaly detection, scenario analysis,
  recommendations, limitations, future improvements. Every recommendation
  cites the metric or test behind it. Rebuild with
  `python reports/executive_report/build_report.py` (needs the
  `powerbi/data/` extract and Microsoft Edge for the PDF step); the
  numbers it cites are recomputed on every build, and `evidence/` holds the
  tables the recommendations rest on.
- [`data_quality/`](data_quality/) — Phase 1 data-quality report.
- [`supplier_risk/`](supplier_risk/) — Phase 7 supplier risk scores.
- [`anomaly_detection/`](anomaly_detection/) — Phase 8 High-severity anomalies.
- [`scenario_analysis/`](scenario_analysis/) — Phase 9 scenario comparison.
