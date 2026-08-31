"""Python implementation of the voyage fuel decision calculation kernel."""

from decimal import getcontext


# Keep the process context above the specification's 34 significant digits.
getcontext().prec = max(getcontext().prec, 50)

from .models import EtsResult, FuelAmount, FuelComponent, FuelFactor, ScopeRates

__all__ = ["EtsResult", "FuelAmount", "FuelComponent", "FuelFactor", "ScopeRates"]
