"""Single-voyage orchestration for the first Python calculation slice."""

from decimal import Decimal

from .emissions import calculate_eu_ets, calculate_fueleu
from .energy import baseline_energy_mj, blend_masses_tonnes, fuel_cost, sum_known_costs
from .models import FuelAmount, VoyageInput, VoyageResult, ScenarioResult
from .ports import calculate_scope_rates


def calculate_voyage(request: VoyageInput) -> VoyageResult:
    scope_rates = calculate_scope_rates(
        request.report_year,
        request.departure_port,
        request.arrival_port,
    )
    baseline_energy = baseline_energy_mj(request.baseline_mass_tonnes, request.baseline_component.factor)
    requested = (Decimal("0"), *request.specified_blend_ratios)
    if request.candidate_allows_pure_use:
        requested = (*requested, Decimal("1"))
    ratios = tuple(dict.fromkeys(requested))
    scenarios = []
    for ratio in ratios:
        baseline_mass, candidate_mass = blend_masses_tonnes(
            baseline_energy,
            request.baseline_component,
            request.candidate_component,
            ratio,
        )
        amounts = (
            FuelAmount(request.baseline_component, baseline_mass),
            FuelAmount(request.candidate_component, candidate_mass),
        )
        baseline_cost = fuel_cost(baseline_mass, request.baseline_component)
        candidate_cost = fuel_cost(candidate_mass, request.candidate_component)
        fuel_total_cost = sum_known_costs(baseline_cost, candidate_cost)
        ets = calculate_eu_ets(request.report_year, amounts, scope_rates, request.eua_price_per_tco2e)
        fuel_eu = calculate_fueleu(request.report_year, amounts, scope_rates.fuel_eu_scope_rate)
        total_cost = sum_known_costs(fuel_total_cost, ets.eua_cost)
        scenarios.append(
            ScenarioResult(
                ratio=ratio,
                baseline_mass_tonnes=baseline_mass,
                candidate_mass_tonnes=candidate_mass,
                physical_energy_mj=baseline_energy,
                fuel_cost=fuel_total_cost,
                eu_ets=ets,
                fuel_eu=fuel_eu,
                model_cost=total_cost,
                execution_status="EXECUTION_CONDITIONS_PENDING",
            )
        )
    return VoyageResult(
        baseline_energy_mj=baseline_energy,
        scope_rates=scope_rates,
        scenarios=tuple(scenarios),
    )
