# Task 2 Report: Structured JSON Parsing and Error Mapping

## Scope Delivered

- Added `parse_decision_case(payload) -> ParsedDecisionCase` for the multi-candidate input contract.
- Added public `parse_component()` and retained `_component` as a private compatibility alias for legacy module-internal callers.
- Added `issue_from_exception()` in `src/voyage_fuel/issues.py` to turn recognized contract failures into explicit blocking `Issue` values.
- Added `decision_case_result_to_dict()` for Decimal-safe case-result projection.
- Kept `calculate_voyage_json()` available and covered its legacy behavior with a regression test.

## RED Evidence

Command:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_json_io -v
```

Result before implementation: `FAILED (errors=1)`.

The expected RED failure was an import error: `parse_decision_case` did not yet exist in `voyage_fuel.json_io`.

## GREEN Evidence

Focused command:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_case_json_io tests.test_json_io tests.test_factor_resolution tests.test_custom_factors -v
```

Result: `Ran 22 tests ... OK`.

Full regression command:

```powershell
$env:PYTHONPATH='src'
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

Result: `Ran 73 tests ... OK` before the final isolated-boundary correction. The correction only changes a missing `candidateId` from a case-level duplicate-ID outcome to a candidate-level invalid-ID outcome; the focused suite was rerun afterward and passed 22 tests.

## Files Changed

- `src/voyage_fuel/json_io.py`
- `src/voyage_fuel/issues.py`
- `src/voyage_fuel/__init__.py`
- `tests/test_case_json_io.py`
- `.superpowers/sdd/2026-09-01-mvp-delivery-plan/task-2-report.md`

## Self-Review

- All newly parsed monetary, mass, and ratio inputs use `Decimal(str(value))`; booleans are checked with exact `bool` type checks so strings such as `"false"` cannot acquire Python truthiness.
- Case-level invalidity returns `ParsedDecisionCase(request=None, issues=(...))` without raising expected validation failures.
- Candidate parse failures produce candidate-scoped, blocking issues and do not remove independently valid candidates.
- Duplicate valid candidate IDs are detected before candidate calculation and block the case. A missing candidate ID is deliberately candidate-scoped, since it cannot collide with another ID.
- The legacy `calculate_voyage_json()` entry point and its established regression suite remain intact.
- `git diff --check` completed without whitespace errors.

## Concerns

- Candidate issue `field` currently identifies the candidate array entry (`candidates[index]`). Task 3 or the API layer may want to enrich it to the exact nested input key when it introduces user-facing validation presentation.
- `DecisionCaseResult` construction is intentionally deferred to Task 3; Task 2 provides only the specified Decimal-safe dictionary projection.
