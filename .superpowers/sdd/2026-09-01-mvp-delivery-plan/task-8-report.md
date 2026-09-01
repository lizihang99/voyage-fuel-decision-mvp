# Task 8 Report: Complete PDF Report from the Unified Result

## Scope

Implemented the complete case-level PDF projection and stateless export endpoints.
The PDF consumes only `DecisionCaseResult` and `DisplayConfig`; calculation remains in
the existing parser/orchestrator boundary. CSV continues to emit raw fixed-point
Decimal strings and ignores presentation precision.

## Changes

- Added `decision_case_to_pdf(result, display_config)` and
  `write_decision_case_pdf(...)` in `src/voyage_fuel/reports.py`.
- Added fixed-margin landscape A4 report sections for case boundary/scope,
  conclusions and conditional recommendations, scenario comparison, FuelEU metrics
  and B0 deltas, constraints/thresholds, factor resolution/evidence, port evidence,
  issues, and methodology/version limitations.
- Added repeated table headers, wrapped `Paragraph` cells for long IDs and Decimal
  strings, explicit status fields, and voyage-level / annual-limit disclaimer text.
- Added `POST /api/export/csv` and `POST /api/export/pdf` in `src/voyage_fuel/web.py`.
  Each endpoint parses and calculates once, then serializes that same result object;
  client-supplied calculated values are ignored.
- Export errors preserve structured 422 issue records.
- Exported report functions from `voyage_fuel.__init__`.
- Added `tests/fixtures/multi_candidate_case.json` with UCO FAME and LNG candidates.
- Added focused PDF precision/content and export API tests.

## Verification Log

Commands run from the Python worktree:

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_web_api -v
```

Result: **20 tests passed**.

Generated the fixture report at `output/pdf/mvp-multi-candidate.pdf`, extracted text
with `pypdf`, and confirmed required case, scenario, metrics, evidence, status,
recommendation, disclaimer, and version fragments. Rendered all pages with Poppler:

```powershell
& pdftoppm -png -r 120 output/pdf/mvp-multi-candidate.pdf output/pdf/rendered/page
```

Result: **4 rendered pages**, each nonblank at 1404x993. Visual inspection confirmed
no clipped tables, overlapping text, missing content, or blank pages; repeated table
headers appear when long scenario tables continue on the next page.

Additional checks:

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

Result: both completed without errors.

## Concerns

- Poppler emitted environment font-registration warnings for unavailable optional
  fonts (`Symbol`, `ArialNarrow`, etc.); the generated pages rendered correctly with
  the embedded Helvetica family.
- The report is intentionally landscape A4 to keep the auditable scenario columns
  readable; long IDs still wrap within cells.

## Fix Report (review follow-up)

Addressed the Task 8 review findings without changing calculation behavior:

- CSV issue records now retain `candidate_id`, `scenario_id`, `component`,
  `issue_field`, and the compatibility alias `issue_component`.
- PDF issue records expose scope, candidate, scenario, component, code, field,
  blocking state, and message for the same location contract.
- PDF case-boundary scope now displays the actual departure/arrival EU ETS and
  FuelEU identities from `PortDecision`; EU ETS and FuelEU reasons are separate
  fields.
- PDF change reporting now includes all available scenario delta metrics from the
  case projection: baseline/candidate fuel mass, energy, fuel cost, CO2, CH4, N2O,
  MRV/pre-scope CO2e, EUAs, EUA cost, model/reference-adjusted cost, FuelEU WtT,
  TtW, GHGI, target, denominators, compliance balances, penalty equivalent, and
  compliance improvement, each with absolute, delta, and relative-to-B0 values.
- Added focused tests for identity/reason separation, complete change metric labels,
  and CSV issue location fields.

### Fix verification

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports tests.test_web_api -v
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

Result: **22 focused tests passed**; compileall and diff check completed without
errors. No full-suite regression was run per the review fix request.

## P2 Fix Report: PDF Issue Deduplication

The PDF issue deduplication identity now includes `issue.component`, matching the
CSV projection and the displayed issue location columns. Added a regression test
with two otherwise identical issues whose components differ; both component rows
remain visible in extracted PDF text.

### Post-fix PDF rendering

Regenerated `output/pdf/mvp-multi-candidate.pdf` from the multi-candidate fixture and
rendered it with:

```powershell
& pdftoppm -png -r 120 output/pdf/mvp-multi-candidate.pdf output/pdf/rendered/post-fix-page
```

Result: **13 rendered pages**, all 1404x993 and nonblank. Spot inspection of the
first and final pages confirmed the port-identity boundary and methodology sections
remain readable after the expanded change-metric tables; repeated table headers and
wrapped long IDs are preserved.

### P2 verification

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_reports -v
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

Result: **13 report tests passed**; compileall and diff check completed without
errors. Per request, no full regression suite was run.
