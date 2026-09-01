# Task 9 Report: Single-Page Web Calculator

## Scope

Implemented the stateless operational web calculator at `/` for the voyage-fuel decision MVP.
The page consumes the existing fuel and port lookup APIs, the shared `POST /api/calculate`
contract, and the CSV/PDF export endpoints. It keeps case input, raw result data, and display
precision in JavaScript memory for the current page only. No cookie, browser storage, database,
or server-side session was added.

## Changes

- `src/voyage_fuel/templates/index.html`
  - Added the complete Chinese-language calculator shell with stable accessible IDs for voyage
    fields, port searches, Port of Call confirmation, baseline and candidate inputs, calculation,
    results, comparison, recommendations, evidence, precision settings, and exports.
  - Added Overview, Scenarios, Thresholds, and Evidence tabs.
- `src/voyage_fuel/static/app.js`
  - Added in-memory workflow state, fuel and port lookup, repeatable candidate rows, inline
    case/candidate issue rendering, calculation, result comparison, conditional recommendations,
    threshold/evidence views, and CSV/PDF downloads.
  - Uses structured issue properties (`issue.code`, `issue.field`, `issue.blocking`,
    `issue.message`, `issue.scope`, and `issue.candidate_id`) directly; it does not derive codes
    by parsing human-readable messages.
  - Display precision controls only format already returned values and are never sent to the
    calculation endpoint. Export requests carry `displayConfig` only for report presentation.
- `src/voyage_fuel/static/styles.css`
  - Added restrained work-focused styling, accessible focus states, stable table dimensions,
    inline issue panels, responsive grids, and horizontal table scrolling for narrow screens.
- `src/voyage_fuel/web.py`
  - Mounted package static assets and added the Jinja-rendered `/` route while preserving the
    existing stateless API and export routes.
- `tests/test_web_page.py`
  - Added page contract tests for the route, stable IDs, static assets, and structured issue
    handling.

## Verification

Commands run from the `python-calculation-kernel` worktree:

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_page -v
```

Result: 2 tests passed.

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_page tests.test_web_api -v
```

Result: 12 tests passed, including calculation, blocked-candidate isolation, no-session-cookie,
CSV export, PDF export, and structured API issue tests.

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

Both commands completed successfully.

## Status boundary

Task 9 component and API tests are implemented and passing. Browser-level visual and interaction
verification remains Task 10 work; this report does not claim that browser verification is complete.

## Review follow-up

Addressed the Task 9 review findings in the page layer:

- Failed calculation requests now clear `state.result` and all rendered result sections before
  showing structured issues, preventing stale results from being exported or mistaken as current.
- Candidate runtime issues are matched to their affected row by indexed fields or structured
  `candidate_id`, and the combined case/candidate issue list is deduplicated by structured identity.
- Candidate add/remove actions synchronize the DOM rows back into `state.candidates` before mutation
  and rerendering.
- The candidate `legend` is the direct first child of its `fieldset` for native fieldset semantics.
- CSV/PDF export failures now have a user-visible structured fallback and network-error catch path.

Focused verification from this worktree:

```powershell
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest tests.test_web_page tests.test_web_api -v
```

Result: 15 tests passed.

```powershell
node --check src/voyage_fuel/static/app.js
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m compileall -q src tests
git diff --check
```

All commands completed successfully. Browser-level visual verification remains Task 10 work.
