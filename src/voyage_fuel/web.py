"""Stateless HTTP boundary for voyage fuel decision cases."""

from __future__ import annotations

import argparse
from typing import Any

from fastapi import Body, FastAPI, Query
from fastapi.responses import JSONResponse

from .case_calculator import calculate_parsed_decision_case
from .factors import builtin_path_ids
from .json_io import decision_case_result_to_dict, parse_decision_case
from .ports import load_port_table


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
