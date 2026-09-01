# Task 10: Browser E2E and Responsive Verification

## Scope

Implemented repeatable Python Playwright acceptance tests for the complete single-voyage browser workflow. Tests start `voyage-fuel-web` on an automatically selected local port, use isolated browser contexts, and keep application state memory-only. No files under `output/` were modified.

## Coverage

- Desktop flow at `1440x900`: port lookup and Port of Call confirmation, EUR case, MDO baseline, UCO FAME and LNG candidates, calculation, scenario IDs, target reachability, execution-pending status, cost ordering, and evidence panel.
- RFNBO candidate without qualification proof: evidence panel includes `RFNBO_QUALIFICATION_NOT_DEMONSTRATED` and factor resolution trace.
- Display precision: visible formatting changes while server raw scenario IDs, ordering, and decimal result values stay stable.
- CSV and PDF downloads: nonempty artifacts with `record_type` CSV header and `%PDF` signature.
- Reload reset: result status and overview return to the initial empty state.
- Mobile flow at `390x844`: controls remain inside viewport; table and tab areas expose intentional horizontal scrolling; screenshot captures the rendered state.
- Blocked-candidate flow: an unknown/custom candidate is `BLOCKED` while a built-in UCO candidate remains `COMPARABLE` and its issue is rendered.

## Changes

- `tests/e2e/test_mvp_flow.py`: server lifecycle, browser fixture, desktop/mobile flow, exports, evidence, reset, and blocked-candidate test.
- `tests/e2e/test_display_precision.py`: precision-only presentation test.
- `src/voyage_fuel/static/app.js`: render factor resolution traces in Evidence and include per-scenario execution status in the comparison table.
- `pyproject.toml`: test path configuration; Playwright remains part of the `dev` extra.
- `README.md`: browser test installation and execution instructions.

## Verification Evidence

Generated artifacts:

- `tests/e2e/artifacts/desktop-results.png`
- `tests/e2e/artifacts/mobile-results.png`
- `tests/e2e/artifacts/desktop-blocked-candidate.png`
- `tests/e2e/artifacts/desktop-result.csv`
- `tests/e2e/artifacts/desktop-result.pdf`

Focused browser command:

```text
python -m unittest discover -s tests/e2e -v
Ran 3 tests ... OK
```

The complete verification command required by the delivery brief was run after the focused suite. Its final counts and any residual concerns are recorded in the task handoff.

## Review Fix Round 1

Addressed review findings:

- Scenario assertions now compare visible scenario IDs, model-cost values, and contiguous cost ranks against the API's raw cost ordering, and assert the target minimum-cost ratio/status (`2.2131%`, `TARGET_REACHABLE`).
- Desktop precision changes capture scenario rows before and after formatting updates and assert IDs/ranks are unchanged; API raw scenario ordering remains asserted as well.
- Mobile checks explicitly verify horizontal scrolling on both `#scenarios-panel .table-scroll` and `#thresholds-panel .table-scroll`, while requiring zero document overflow and an in-viewport calculate button.
- Blocked-candidate flow now fills year, Port of Call confirmation, currency, both ports, MDO baseline mass/price, and EUA price before introducing the blocked candidate.
- Removed unused `PlaywrightTimeoutError` import.

Focused verification command:

```text
python -m unittest discover -s tests/e2e -v
Ran 3 tests ... OK
python -m compileall -q src tests
git diff --check
```

All commands completed successfully after the review fixes.

Review fix commit: `8d1d6f5cf38a7c17131b60bfad2070a113bb4b36`.

## Review Fix Round 2

The precision-only browser flow now independently captures visible scenario rows before and after changing price/ratio decimals, asserts unchanged scenario IDs and ranks, and verifies the visible order against raw API model-cost ordering.

Focused verification command:

```text
python -m unittest discover -s tests/e2e -v
Ran 3 tests ... OK
python -m compileall -q src tests
git diff --check
```

All commands completed successfully after the second review fix.
