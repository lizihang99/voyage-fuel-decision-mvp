# Task 7 Report

## Changed files

- `tests/test_spec_matrix.py`
  - Added focused public-contract coverage for B0 current-model minimums and dominated global switch intersections.
  - Added structured-factor validation cases for unproven RFNBO, 2024 `rwd=2`, missing `BIO_E` `cfCO2`, invalid Cslip, and non-biomass zero-rating claims.
  - Added `TARGET_NO_SOLUTION` maximum-improvement boundary coverage and empty-candidate case validation.
  - Added 2024 ETS excluded-gas mapping, factor equipment/evidence provenance, CSV constraints/economics records, web custom-baseline submission, execution-pending status, and page/PDF/README boundary-language checks.

No calculation implementation files were changed. Existing generated E2E artifacts remain uncommitted.

## Verification

Exact focused command from the brief:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_spec_matrix tests.test_regressions -v
```

Output summary:

```text
Ran 20 tests in 2.717s

OK
```

The runtime emitted an existing FastAPI/Starlette `httpx` deprecation warning; it did not affect the result.

## Remaining concerns

- The requested full repository acceptance suite is intentionally deferred to the controller/final plan gate.
- E2E artifact modifications already present in the worktree were left untouched and excluded from the commit.

## Review fix round

- Strengthened the counterexample fixtures so RFNBO and `BIO_E` cases include all unrelated required fields and assert the targeted qualification, year-window, and `cfCO2` messages.
- Made the dominated-intersection test assert a real lower-envelope transition and independently verify that a synthetic LNG intersection is omitted from the global envelope.
- Asserted ETS CH4/N2O exclusion values, non-empty web scenarios, case-level maximum-improvement recommendation exposure, and key CSV/evidence fields.
- Focused verification after the review fixes: `Ran 20 tests in 2.842s; OK`.
