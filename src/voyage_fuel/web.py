"""HTTP boundary for voyage fuel decision cases and short-lived exports."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
import os
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .case_calculator import calculate_parsed_decision_case
from .factors import builtin_path_ids
from .json_io import decision_case_result_to_dict, parse_decision_case
from .ports import load_port_table
from .formatting import DisplayConfig
from .reports import decision_case_to_csv, decision_case_to_pdf


app = FastAPI(title="Voyage Fuel Decision API", version="0.1.0")
_PACKAGE_DIR = Path(__file__).resolve().parent
_templates = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(_PACKAGE_DIR / "static")), name="static")


@dataclass(frozen=True)
class _ResultSnapshot:
    result: Any
    created_at: float


_SNAPSHOT_TTL_SECONDS = 30 * 60
_SNAPSHOT_LIMIT = 32
_VIEW_MODES = frozenset({"legacy", "workbench"})
_result_snapshots: OrderedDict[str, _ResultSnapshot] = OrderedDict()
_snapshot_lock = Lock()


def _store_snapshot(result: Any) -> str:
    snapshot_id = uuid4().hex
    now = monotonic()
    with _snapshot_lock:
        expired = [
            key for key, snapshot in _result_snapshots.items()
            if now - snapshot.created_at > _SNAPSHOT_TTL_SECONDS
        ]
        for key in expired:
            _result_snapshots.pop(key, None)
        _result_snapshots[snapshot_id] = _ResultSnapshot(result=result, created_at=now)
        while len(_result_snapshots) > _SNAPSHOT_LIMIT:
            _result_snapshots.popitem(last=False)
    return snapshot_id


def _load_snapshot(snapshot_id: str) -> Any | None:
    now = monotonic()
    with _snapshot_lock:
        snapshot = _result_snapshots.get(snapshot_id)
        if snapshot is None:
            return None
        if now - snapshot.created_at > _SNAPSHOT_TTL_SECONDS:
            _result_snapshots.pop(snapshot_id, None)
            return None
        _result_snapshots.move_to_end(snapshot_id)
        return snapshot.result


def _snapshot_error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=409, content={"issues": [{
        "code": code,
        "scope": "CASE",
        "field": "resultSnapshotId",
        "blocking": True,
        "message": message,
        "candidate_id": None,
        "scenario_id": None,
        "component": None,
    }]})


def _view_mode(view: str | None) -> str:
    """Resolve a whitelisted view, keeping the legacy shell as the default."""
    configured = os.environ.get("VOYAGE_FUEL_UI", "legacy").strip().lower()
    requested = (view if view is not None else configured).strip().lower()
    if requested not in _VIEW_MODES:
        raise HTTPException(status_code=422, detail="view must be legacy or workbench")
    return requested


@app.get("/", response_class=HTMLResponse)
def index(request: Request, view: str | None = Query(default=None)) -> HTMLResponse:
    """Serve the operational calculator shell."""
    return _templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"view_mode": _view_mode(view)},
    )


@app.get("/examples/guide", response_class=HTMLResponse)
def examples_guide(request: Request) -> HTMLResponse:
    """Serve the optional short guide for the two synthetic examples."""
    return _templates.TemplateResponse(
        request=request,
        name="examples_guide.html",
        context={},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Provide a minimal liveness check without creating server state."""
    return {"status": "ok"}


@app.get("/api/fuels")
def fuels() -> dict[str, list[str]]:
    """Expose the navigational built-in fuel catalog only."""
    return {"pathIds": list(builtin_path_ids())}


@app.get("/api/ports")
def ports(q: str = Query(default="", max_length=100)) -> dict[str, list[dict[str, str]]]:
    """Return a small identity search result rather than the formal port table."""
    query = q.strip().casefold()
    if not query:
        return {"ports": []}
    matches = [
        {
            "unlocode": port["unlocode"],
            "portName": port["portName"],
            "countryCode": port["countryCode"],
            "territoryType": port["territoryType"],
            "euEtsStatus": port["euEtsStatus"],
            "fuelEuStatus": port["fuelEuStatus"],
        }
        for port in load_port_table().values()
        if query in port["unlocode"].casefold() or query in port["portName"].casefold()
    ]
    return {"ports": matches[:20]}


@app.post("/api/calculate")
def calculate(payload: Any = Body(...)) -> JSONResponse:
    """Calculate a single request, projecting business errors as structured data."""
    parsed = parse_decision_case(payload)
    result_object = calculate_parsed_decision_case(parsed)
    result = decision_case_result_to_dict(result_object)
    if parsed.request is None:
        return JSONResponse(status_code=422, content={"issues": result["issues"]})
    result["result_snapshot_id"] = (
        _store_snapshot(result_object) if result_object.baseline_scenario is not None else None
    )
    return JSONResponse(status_code=200, content=result)


def _display_config(payload: Any) -> DisplayConfig:
    """Read presentation precision from an optional request section only."""
    if not isinstance(payload, dict) or not isinstance(payload.get("displayConfig"), dict):
        return DisplayConfig()
    raw = payload["displayConfig"]
    fields = (
        "fuel_mass_decimals", "energy_decimals", "ratio_decimals", "scope_rate_decimals",
        "intensity_decimals", "gas_decimals", "price_decimals", "factor_decimals",
    )
    values = {field: raw[field] for field in fields if field in raw}
    try:
        return DisplayConfig(**values)
    except (TypeError, ValueError):
        return DisplayConfig()


def _export_result(payload: Any) -> tuple[Any, DisplayConfig] | JSONResponse:
    """Resolve the exact result produced by the preceding calculate request."""
    if not isinstance(payload, dict) or not isinstance(payload.get("resultSnapshotId"), str):
        return _snapshot_error(
            "RESULT_SNAPSHOT_REQUIRED",
            "Complete a calculation before exporting the result.",
        )
    result = _load_snapshot(payload["resultSnapshotId"])
    if result is None:
        return _snapshot_error(
            "RESULT_SNAPSHOT_EXPIRED",
            "The calculated result is unavailable or expired; calculate again before exporting.",
        )
    return result, _display_config(payload)


@app.post("/api/export/csv")
def export_csv(payload: Any = Body(...)) -> Response:
    exported = _export_result(payload)
    if isinstance(exported, JSONResponse):
        return exported
    result, display_config = exported
    return Response(
        content=decision_case_to_csv(result, display_config),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=voyage-fuel-decision.csv"},
    )


@app.post("/api/export/pdf")
def export_pdf(payload: Any = Body(...)) -> Response:
    exported = _export_result(payload)
    if isinstance(exported, JSONResponse):
        return exported
    result, display_config = exported
    return Response(
        content=decision_case_to_pdf(result, display_config),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=voyage-fuel-decision.pdf"},
    )


def main() -> None:
    """Start the local service with conventional host and port overrides."""
    parser = argparse.ArgumentParser(description="Run the voyage fuel web service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()

    import uvicorn

    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
