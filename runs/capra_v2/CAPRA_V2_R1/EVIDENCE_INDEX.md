# CAPRA v2 evidence

- `results.csv/json`: six same-version cells, 80/80 each, no mixing with v1.
- `saturn-*/{SIA-P,CAPRA-Fixed,CAPRA}/events.jsonl.gz`: full raw events; complete commands in process.json.
- Per cell `summary.json`, `per_job.csv`, `node_resources.csv`, `v2_audit.json`, `output_hashes.json`, `audit_hashes.json`.
- `paired_jobs.csv`: all 160 jobs, all positive/negative paired differences.
- `average_node_allocations.csv`, `supplementary_metrics.json`, `raw_opportunity_analysis.json`, `application_time_and_jct.csv`.
- `v1_historical_reference.csv`: reference only; original v1 files unchanged.
- `frozen_source.zip`, `freeze_receipt.json`: exact runtime source and manifest, code commit 2517e5cd6bfd93f094b728e226478d4cf56cc45f.
- `figures/`: final PNG/PDF; report_revisions/ preserves initial render and report.
- `analysis_tools/`: post-experiment read-only analysis and delivery producers, not runtime algorithm changes.
- `final_verification.json`, `evidence_hashes.json`: final source/history/arithmetic/figure checks.
- Parent development/: pilot raw events and all test logs, including fixture failure and correction.
- Parent budget_ledger.json: pilot+six formal cells 1413.832s, plus60s validation reserve, below7200s limit.

Design/report: docs/CAPRA_V2_DESIGN.md and docs/CAPRA_V2_RESULTS.md.
Manifest: configs/experiment_manifest_v2.json. No remote push, extra cohort, tuning, optional ablation, or deterministic repetition was performed.
