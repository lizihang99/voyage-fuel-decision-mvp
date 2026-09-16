"""Single-voyage orchestration for the first Python calculation slice."""

from decimal import Decimal

from .emissions import calculate_eu_ets, calculate_fueleu
from .constraints import calculate_constraints
from .economics import build_economics
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
    constraints = calculate_constraints(
        report_year=request.report_year,
        baseline_mass_tonnes=request.baseline_mass_tonnes,
        baseline=request.baseline_component,
        candidate=request.candidate_component,
        scope=scope_rates,
        candidate_supply_tonnes=request.candidate_supply_tonnes,
        incremental_budget=request.incremental_budget,
        max_blend_ratio=request.max_blend_ratio,
        eua_price_per_tco2e=request.eua_price_per_tco2e,
        baseline_energy_mj=baseline_energy,
    )
    requested = (Decimal("0"), *request.specified_blend_ratios)
    if request.candidate_allows_pure_use:
        requested = (*requested, Decimal("1"))
    # Report points are a finite, deduplicated projection of the continuous search.
    if constraints.x_cap != Decimal("1") or request.candidate_allows_pure_use:
        requested = (*requested, constraints.x_cap)
    if request.incremental_budget is not None and constraints.x_budget is not None:
        requested = (*requested, constraints.x_budget)
    if request.candidate_supply_tonnes is not None and constraints.x_supply is not None:
        requested = (*requested, constraints.x_supply)
    if constraints.x_target_min is not None:
        requested = (*requested, constraints.x_target_min)
    if (constraints.x_target_min_cost is not None
            and (constraints.x_target_min_cost != Decimal("1") or request.candidate_allows_pure_use)):
        # A cheaper worsening candidate can have a compliance upper endpoint
        # distinct from both the minimum target ratio and the constraint cap.
        requested = (*requested, constraints.x_target_min_cost)
    if (constraints.x_max_improvement is not None
            and (constraints.x_max_improvement != Decimal("1") or request.candidate_allows_pure_use)):
        requested = (*requested, constraints.x_max_improvement)
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
                constraint_status=("FEASIBLE" if ratio <= constraints.x_cap else "CONSTRAINT_INFEASIBLE"),
            )
        )
    economics, enriched_scenarios = build_economics(
        report_year=request.report_year,
        baseline=request.baseline_component,
        candidate=request.candidate_component,
        scope=scope_rates,
        eua_price_per_tco2e=request.eua_price_per_tco2e,
        scenarios=tuple(scenarios),
        comparison_value=request.compliance_improvement_value,
    )
    return VoyageResult(
        report_year=request.report_year,
        departure_port=request.departure_port,
        arrival_port=request.arrival_port,
        baseline_energy_mj=baseline_energy,
        scope_rates=scope_rates,
        scenarios=enriched_scenarios,
        constraints=constraints,
        economics=economics,
        baseline_factor=request.baseline_component.factor,
        candidate_factor=request.candidate_component.factor,
        baseline_qualification_status=request.baseline_component.qualification_status,
        candidate_qualification_status=request.candidate_component.qualification_status,
    )
