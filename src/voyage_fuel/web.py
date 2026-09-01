"""Stateless HTTP boundary for voyage fuel decision cases."""

from __future__ import annotations

import argparse
from typing import Any

from fastapi import Body, FastAPI, Query
from fastapi.responses import JSONResponse, Response

from .case_calculator import calculate_parsed_decision_case
from .factors import builtin_path_ids
from .json_io import decision_case_result_to_dict, parse_decision_case
from .ports import load_port_table
from .formatting import DisplayConfig
from .reports import decision_case_to_csv, decision_case_to_pdf


app = FastAPI(title="Voyage Fuel Decision API", version="0.1.0")


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
    result = decision_case_result_to_dict(calculate_parsed_decision_case(parsed))
    if parsed.request is None:
        return JSONResponse(status_code=422, content={"issues": result["issues"]})
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
    """Calculate exactly once for an export and return the shared result object."""
    parsed = parse_decision_case(payload)
    result = calculate_parsed_decision_case(parsed)
    if parsed.request is None:
        return JSONResponse(status_code=422, content={"issues": decision_case_result_to_dict(result)["issues"]})
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
