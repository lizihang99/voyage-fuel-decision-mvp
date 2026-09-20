"""Synthetic business cases for mechanical export by a separate runner.

Frozen authority: docs/superpowers/specs/
2026-08-07-voyage-fuel-decision-calculation-spec.md, sections 3-5, 9-13;
and 燃料因子库规范.md, tables II/III and sections 4.2-4.4, 5.
No production/reference imports, file reads, fixture writes, or network access.
Fractions in snapshots are exact rational numbers, not JSON request values.

Snapshots contain successfully resolvable factors only. Invalid candidates remain
in the request and expected_issues, never as fabricated resolved factors.
For a case-level confirmation failure the snapshot describes its intended inputs,
not a successful calculation. expected_issues includes required input errors and
nonblocking price/budget warnings; a runner must also collect nested reason codes.
It is not an exhaustive list of target-search outcomes or scenario null reasons.
Built-in equipment IDs follow the existing API spelling, not equipment approval.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F


_NOT = "NOT_DEMONSTRATED"
_ASSUMED = "ASSUMED_ELIGIBLE"
_VERIFIED = "VERIFIED_ELIGIBLE"
_COMMON_ASSUMPTIONS = (
    "全部案例为合成测试，报价、供应量、预算和资格声明不代表市场或真实认证。",
    "冻结本地规范独立声明因子；不读取生产因子表、参考计算器或历史输出。",
    "仅验证同等物理能源下的法规情景；不证明设备适配、燃料可得性或混兑兼容性。",
)
_B_ASSUMPTION = (
    "鹿特丹至汉堡使用1000吨MDO只是合成能源测试，不代表该航段真实燃料需求。"
)
_GAS_ASSUMPTION = (
    "仅比较相同设备类型的化石LNG、生物LNG和e-LNG情景；不暗示液体燃料混兑兼容性。"
)


def _factor(path_id, lcv, wtt, co2, ch4="0.00005", n2o="0.00018",
            *, slip=None, methane=False, rwd="1", biomass="0",
            status="FIXED", qualification=_NOT, mode="STATIC",
            equipment=None, **extra):
    return {
        "path_id": path_id, "lcv": lcv, "wtt": wtt, "co2": co2,
        "ch4": ch4, "n2o": n2o, "slip": slip, "methane": methane,
        "rwd": rwd, "biomass": biomass, "factor_status": status,
        "qualification": qualification, "mode": mode,
        "equipment_id": equipment or path_id,
        "csf_co2": "0", "csf_ch4": "1" if methane else "0", "csf_n2o": "0",
        **extra,
    }


# Input-independent frozen rows transcribed from the local specification.
# Default non-RFNBO estimates use section 4.2, not table III's certified LCVs.
# Cslip NA still follows table III and rule 5.1; website zeros cannot erase NA.
def _catalog():
    rows = [
        _factor("HFO", "0.0405", "13.5", "3.114"),
        _factor("LFO", "0.041", "13.2", "3.151"),
        _factor("MDO", "0.0427", "14.4", "3.206"),
        _factor("MGO", "0.0427", "14.4", "3.206"),
        _factor("METHANOL_NG", "0.0199", "31.3", "1.375"),
        _factor("H2_NG_FC", "0.12", "132", "0", "0", "0"),
        _factor("H2_NG_ICE", "0.12", "132", "0", "0", "0.00018"),
        _factor("LPG_PROPANE", "0.046", "7.8", "3.000", slip="0", status="ESTIMATED"),
        _factor("LPG_BUTANE", "0.046", "7.8", "3.030", slip="0", status="ESTIMATED"),
        _factor("NH3_NG_FC", "0.0186", "121", "0", slip="0", status="ESTIMATED"),
        _factor("NH3_NG_ICE", "0.0186", "121", "0", slip="0", status="ESTIMATED"),
        _factor("BIOETHANOL", "0.02685", "20", "1.913",
                status="ESTIMATED", mode="BIO_E"),
        _factor("BIODIESEL", "0.037", "20", "2.834",
                status="ESTIMATED", mode="BIO_E"),
        _factor("HVO", "0.044", "15", "3.115",
                status="ESTIMATED", mode="BIO_E"),
        _factor("BIOMETHANOL", "0.01986", "18", "1.375",
                status="ESTIMATED", mode="BIO_E"),
        _factor("BIOH2_FC", "0.120", "25", "0", "0", "0",
                status="ESTIMATED", mode="CERTIFIED"),
        _factor("BIOH2_ICE", "0.120", "25", "0", "0", "0.00002",
                status="ESTIMATED", mode="CERTIFIED"),
        _factor("UCO_FAME", "0.037", str(F("14.9") - F("2.834") / F("0.037")),
                "2.834", mode="BIO_E", status="ESTIMATED", e="14.9"),
    ]
    result = {row["path_id"]: row for row in rows}
    for suffix, full_suffix, slip in _gas_equipment():
        fossil = "LNG_" + full_suffix
        result[fossil] = _factor(
            fossil, "0.0491", "18.5", "2.750", "0", "0.00011",
            slip=slip, methane=True, equipment="LNG_" + suffix,
        )
        bio = "BIOLNG_" + suffix
        result[bio] = _factor(
            bio, "0.0491", "10", "2.750", "0", "0.00011",
            slip=slip, methane=True, status="ESTIMATED", mode="BIO_E",
        )
    # Specification section 4.4: full fossil fallback, not just removal of RWD.
    fallbacks = {
        "E_DIESEL": "MDO", "E_METHANOL": "METHANOL_NG",
        "E_H2_FC": "H2_NG_FC", "E_H2_ICE": "H2_NG_ICE",
        "E_NH3_FC": "NH3_NG_FC", "E_NH3_ICE": "NH3_NG_ICE",
    }
    for _, full_suffix, _ in _gas_equipment():
        fallbacks["E_LNG_" + full_suffix] = "LNG_" + full_suffix
    for requested, fallback in fallbacks.items():
        result[requested] = deepcopy(result[fallback])
    return result


def _gas_equipment():
    return (
        ("OTTO_MS", "OTTO_MEDIUM_SPEED", "3.1"),
        ("OTTO_SS", "OTTO_SLOW_SPEED", "1.7"),
        ("DIESEL_SS", "DIESEL_SLOW_SPEED", "0.2"),
        ("LBSI", "LBSI", "2.6"),
    )


def _bio_factor(path, e, qualification=_ASSUMED, biomass="1"):
    # Only the explicit E-based test paths; certified table III values.
    liquid = {
        "UCO_FAME": ("0.037", "2.834"),
        "HVO": ("0.044", "3.115"),
        "BIODIESEL": ("0.037", "2.834"),
    }
    if path in liquid:
        lcv, co2 = liquid[path]
        ch4, n2o, slip, methane = "0.00005", "0.00018", None, False
    else:
        slips = {"BIOLNG_" + suffix: slip for suffix, _, slip in _gas_equipment()}
        lcv, co2, ch4, n2o = "0.050", "2.750", "0", "0.00011"
        slip, methane = slips[path], True
    return _factor(
        path, lcv, str(F(e) - F(co2) / F(lcv)), co2, ch4, n2o,
        slip=slip, methane=methane, mode="BIO_E", e=e,
        qualification=qualification,
        biomass=biomass if qualification in {_ASSUMED, _VERIFIED} else "0",
        status="VERIFIED" if qualification == _VERIFIED else "ESTIMATED",
    )


def _rfnbo_factor(path, qualification=_ASSUMED, e="28.2"):
    if qualification in {_NOT, "INELIGIBLE"}:
        factor = _catalog()[path]
        factor["qualification"] = qualification
        return factor
    if path == "E_DIESEL":
        lcv, co2, ch4, n2o, eu = "0.0427", "3.206", "0.00005", "0.00018", "73.2"
        slip, methane, equipment = None, False, path
    else:
        equipment_rows = {"E_LNG_" + full: ("E_LNG_" + short, slip)
                          for short, full, slip in _gas_equipment()}
        equipment, slip = equipment_rows[path]
        lcv, co2, ch4, n2o, eu, methane = "0.0491", "2.750", "0", "0.00011", "56.2", True
    return _factor(
        path, lcv, str(F(e) - F(eu)), co2, ch4, n2o,
        slip=slip, methane=methane, equipment=equipment,
        rwd="2", qualification=qualification, mode="RFNBO_E", e=e, eu=eu,
        status="VERIFIED" if qualification == _VERIFIED else "ESTIMATED",
    )


def _request(*, year=2030, ports=("NLRTM", "DEHAM"), baseline=None):
    return {
        "reportYear": year, "departurePort": ports[0], "arrivalPort": ports[1],
        "adjacentValidPortOfCallConfirmed": True, "currency": "EUR",
        "baseline": deepcopy(baseline) if baseline is not None else {
            "pathId": "MDO", "massTonnes": "1000", "pricePerTonne": "700",
        },
        "euaPricePerTCO2e": "80", "candidates": [],
    }


def _candidate(candidate_id, path, price="1000", **fields):
    return {
        "candidateId": candidate_id, "pathId": path, "pricePerTonne": price,
        "specifiedBlendRatios": ["0.01", "0.05"],
        "maxBlendRatio": "0.5", "candidateAllowsPureUse": False,
        **fields,
    }


def _issue(code, candidate_id=None):
    return {"code": code, "scope": "CASE" if candidate_id is None else "CANDIDATE",
            "candidate_id": candidate_id}


def _case(case_id, name, purpose, request, baseline, candidates, coverage, *,
          compact=False, assumptions=(), issues=(), http=200):
    # Deliberately limited to three manually frozen supported pairs.
    geo = {("CNSHG", "NLRTM"): "0.5", ("NLRTM", "DEHAM"): "1",
           ("CNSHG", "SGSIN"): "0"}[(request["departurePort"], request["arrivalPort"])]
    year = request["reportYear"]
    return deepcopy({
        "id": case_id, "family": case_id[0], "name": name, "purpose": purpose,
        "compact": compact, "synthetic": True,
        "assumptions": [*_COMMON_ASSUMPTIONS, *assumptions],
        "coverage": list(coverage), "request": request,
        "snapshot": {
            "scope": {"geo": geo, "surrender": {2024: "0.4", 2025: "0.7"}.get(year, "1"),
                      "fueleu": None if year == 2024 else geo},
            "baseline": baseline, "candidates": candidates,
        },
        "expected_issues": list(issues), "expected_http_status": http,
    })


def _custom(mode, *, zero=False):
    path = "SYNTHETIC_" + ("ZERO" if zero else mode)
    payload = {
        "custom": True, "pathId": path, "equipmentId": "SYNTHETIC_TEST_ICE",
        "wtTMode": mode, "lcv": "0.04",
        "cfCO2": "0" if zero else "3", "cfCH4": "0", "cfN2O": "0",
        "cslip": "NA", "methaneSlipApplicable": False,
        "rwd": "2" if mode == "RFNBO_E" else "1",
        "eligibleBiomassFraction": "1" if mode == "BIO_E" else "0",
        "qualificationStatus": _ASSUMED if mode in {"BIO_E", "RFNBO_E"} else _NOT,
    }
    units = {
        "lcv": "MJ/gFuel", "cfCO2": "gGHG/gFuel", "cfCH4": "gGHG/gFuel",
        "cfN2O": "gGHG/gFuel", "cslip": "%", "methaneSlipApplicable": "boolean",
        "rwd": "ratio", "eligibleBiomassFraction": "fraction",
    }
    if mode in {"STATIC", "CERTIFIED"}:
        payload["wtT"] = "0" if zero else "12" if mode == "CERTIFIED" else "10"
        units["wtT"] = "gCO2eq/MJ"
        wtt = payload["wtT"]
    elif mode == "BIO_E":
        payload["E"] = "25"
        units["E"] = "gCO2eq/MJ"
        wtt = "-50"  # Independently frozen: 25 - 3 / .04.
    else:
        payload.update(E="20", eu="70")
        units.update(E="gCO2eq/MJ", eu="gCO2eq/MJ")
        wtt = "-50"
    payload["sourceEvidence"] = {
        field: {
            "sourceId": f"SYNTHETIC:{path}:{field}", "sourceType": "SA",
            "unit": unit, "verificationStatus": "ESTIMATED",
        } for field, unit in units.items()
    }
    factor = _factor(
        path, "0.04", wtt, "0" if zero else "3", "0", "0",
        mode=mode, equipment="SYNTHETIC_TEST_ICE", status="ESTIMATED",
        qualification=payload["qualificationStatus"], rwd=payload["rwd"],
        biomass=payload["eligibleBiomassFraction"],
        source_ids=[entry["sourceId"] for entry in payload["sourceEvidence"].values()],
    )
    if "E" in payload:
        factor["e"] = payload["E"]
    if "eu" in payload:
        factor["eu"] = payload["eu"]
    return payload, factor


def _a_cases():
    baseline = _catalog()["MDO"]
    result = []
    for year in (2024, 2025, 2030):
        result.append(_case(
            f"A-{year}", f"{year}年无候选基准", "冻结半范围、年度清缴比例和空候选行为",
            _request(year=year, ports=("CNSHG", "NLRTM")), baseline, {},
            ["baseline_only", "year_boundary", "half_scope"], compact=year == 2024,
        ))
    result.append(_case(
        "A-zero-scope", "范围外基准", "范围为零时区分零清缴量与不适用的FuelEU结果",
        _request(ports=("CNSHG", "SGSIN")), baseline, {},
        ["baseline_only", "zero_scope", "zero_baseline"],
    ))
    for suffix, field in (("fuel", "pricePerTonne"), ("eua", "euaPricePerTCO2e")):
        request = _request()
        (request["baseline"] if suffix == "fuel" else request)[field] = None
        result.append(_case(
            "A-missing-" + suffix + "-price", "基准缺少价格", "缺价保留能源和排放计算",
            request, baseline, {}, ["baseline_only", "missing_price"],
            issues=[_issue("PRICE_REQUIRED_FOR_COMPARISON")],
        ))
    payload, factor = _custom("STATIC", zero=True)
    request = _request(baseline={**payload, "massTonnes": "1000", "pricePerTonne": "0"})
    request["euaPricePerTCO2e"] = "0"
    result.append(_case(
        "A-manual-zero", "手算零排放锚点", "以四千万MJ能源、零排放和零成本检查零基准语义",
        request, factor, {}, ["baseline_only", "manual_zero_anchor", "zero_baseline"],
        compact=True,
        assumptions=["手算锚点：1000吨乘一百万再乘0.04，能源为40000000 MJ；排放与成本均为零。"],
    ))
    return result


def _six_quotes():
    candidates = [
        _candidate("uco-limited", "UCO_FAME", "950", candidateSupplyTonnes="30",
                   qualificationStatus=_ASSUMED, eligibleBiomassFraction="1", e="14.9"),
        _candidate("uco-bulk", "UCO_FAME", "1150",
                   qualificationStatus=_ASSUMED, eligibleBiomassFraction="1", e="14.9"),
        _candidate("hvo", "HVO", "1100",
                   qualificationStatus=_ASSUMED, eligibleBiomassFraction="1", e="20"),
        _candidate("bio", "BIODIESEL", "1200",
                   qualificationStatus=_ASSUMED, eligibleBiomassFraction="1", e="35"),
        _candidate("e-diesel", "E_DIESEL", "1600", maxBlendRatio="0.7",
                   qualificationStatus=_ASSUMED),
        _candidate("uco-high", "UCO_FAME", "1400",
                   qualificationStatus=_ASSUMED, eligibleBiomassFraction="1", e="14.9"),
    ]
    factors = {
        "uco-limited": _bio_factor("UCO_FAME", "14.9"),
        "uco-bulk": _bio_factor("UCO_FAME", "14.9"),
        "hvo": _bio_factor("HVO", "20"),
        "bio": _bio_factor("BIODIESEL", "35"),
        "e-diesel": _rfnbo_factor("E_DIESEL"),
        "uco-high": _bio_factor("UCO_FAME", "14.9"),
    }
    return candidates, factors


def _b_cases():
    variants = (
        ("default", "六报价基准", "比较同一路径不同报价、能源守恒和全局经济切换"),
        ("eua0", "零EUA价格", "隔离燃料采购成本对排序的影响"),
        ("eua200", "高EUA价格", "检查碳价变化导致的成本排序切换"),
        ("hvo-budget0", "HVO零增量预算", "检查预算零值与未提供预算的区别"),
        ("hvo-budget1000", "HVO有限预算", "检查增量预算限制达标与最大改善比例"),
        ("hvo-supply0", "HVO零供应", "检查零供应仍保留B0和数学参考"),
        ("hvo-supply50", "HVO有限供应", "检查供应约束使用完整航段实际候选质量"),
        ("hvo-cap005", "HVO低混兑上限", "检查上限边界与用户指定比例相等"),
        ("rfnbo-unqualified", "电柴油资格未证明", "检查RFNBO完整化石回退"),
        ("all-budgets1000", "全部报价有限预算", "检查所有候选约束下的全局比较"),
        ("hvo-price600", "低价HVO", "检查等能源便宜候选的负增量成本"),
        ("reverse", "反序输入", "检查报价顺序不改变经济比较结论"),
        ("reference-value100", "合规改善参考价值", "检查非零合规改善参考价值只进入条件式成本线"),
        ("combined-constraints", "共同施加约束", "同时施加预算、供应和比例上限并取可行交集"),
        ("missing-price-budget", "缺价且有预算", "保留排放计算并声明预算不可评估"),
        ("b100-allowed", "明确允许纯用", "在明确许可下生成纯候选参考方案"),
        ("b100-forbidden", "明确禁止纯用", "指定纯用比例仅阻断该候选，其他报价继续计算"),
        ("duplicate-ties", "重复报价并列", "不同候选标识具有相同输入，检查稳定并列处理"),
    )
    result = []
    for suffix, name, purpose in variants:
        candidates, factors = _six_quotes()
        request = _request()
        request["candidates"] = candidates
        by_id = {candidate["candidateId"]: candidate for candidate in candidates}
        hvo = by_id["hvo"]
        issues = []
        coverage = ["six_quotes", "energy_conservation", suffix]
        if suffix in {"eua0", "eua200"}:
            request["euaPricePerTCO2e"] = "0" if suffix == "eua0" else "200"
        elif suffix in {"hvo-budget0", "hvo-budget1000"}:
            hvo["incrementalBudget"] = "0" if suffix.endswith("budget0") else "1000"
        elif suffix in {"hvo-supply0", "hvo-supply50"}:
            hvo["candidateSupplyTonnes"] = "0" if suffix.endswith("supply0") else "50"
        elif suffix == "hvo-cap005":
            hvo["maxBlendRatio"] = "0.05"
        elif suffix == "rfnbo-unqualified":
            by_id["e-diesel"]["qualificationStatus"] = _NOT
            factors["e-diesel"] = _rfnbo_factor("E_DIESEL", _NOT)
        elif suffix == "all-budgets1000":
            for candidate in candidates:
                candidate["incrementalBudget"] = "1000"
        elif suffix == "hvo-price600":
            hvo["pricePerTonne"] = "600"
        elif suffix == "reverse":
            candidates.reverse()
        elif suffix == "reference-value100":
            hvo["complianceImprovementValue"] = "100"
        elif suffix == "combined-constraints":
            hvo.update(incrementalBudget="1000", candidateSupplyTonnes="50", maxBlendRatio="0.05")
        elif suffix == "missing-price-budget":
            hvo.update(pricePerTonne=None, incrementalBudget="1000")
            issues = [_issue("PRICE_REQUIRED_FOR_COMPARISON", "hvo"),
                      _issue("BUDGET_UNAVAILABLE_WITHOUT_PRICES", "hvo")]
        elif suffix in {"b100-allowed", "b100-forbidden"}:
            hvo.update(maxBlendRatio="1", specifiedBlendRatios=["0.01", "0.05", "1"],
                       candidateAllowsPureUse=suffix == "b100-allowed")
            if suffix == "b100-forbidden":
                del factors["hvo"]
                issues = [_issue("INVALID_BLEND_RATIO", "hvo")]
        elif suffix == "duplicate-ties":
            twin = deepcopy(by_id["uco-bulk"])
            twin["candidateId"] = "uco-bulk-twin"
            candidates.append(twin)
            factors["uco-bulk-twin"] = deepcopy(factors["uco-bulk"])
        result.append(_case(
            "B-" + suffix, name, purpose, request, _catalog()["MDO"], factors, coverage,
            compact=suffix in {"default", "combined-constraints"},
            assumptions=[_B_ASSUMPTION], issues=issues,
        ))
        if suffix == "reference-value100":
            result[-1]["coverage"].append("reference_value")
    return result


def _c_cases():
    result = []
    for short, full, _ in _gas_equipment():
        fossil, bio, renewable = "LNG_" + full, "BIOLNG_" + short, "E_LNG_" + full
        for year in (2025, 2026):
            request = _request(year=year, baseline={
                "pathId": fossil, "massTonnes": "1000", "pricePerTonne": "700",
            })
            factors = {}
            for label, qualification in (("unqualified", _NOT), ("assumed", _ASSUMED),
                                         ("verified", _VERIFIED)):
                cid = "bio-" + label
                fraction = "0" if qualification == _NOT else "1"
                request["candidates"].append(_candidate(
                    cid, bio, "1100", qualificationStatus=qualification,
                    eligibleBiomassFraction=fraction, e="20",
                ))
                factors[cid] = _bio_factor(bio, "20", qualification, fraction)
            for label, qualification in (("unqualified", _NOT), ("assumed", _ASSUMED),
                                         ("verified", _VERIFIED), ("ineligible", "INELIGIBLE")):
                cid = "e-" + label
                overrides = {"e": "20", "eu": "56.2"} if qualification == _VERIFIED else {}
                request["candidates"].append(_candidate(
                    cid, renewable, "1400", qualificationStatus=qualification, **overrides,
                ))
                factors[cid] = _rfnbo_factor(
                    renewable, qualification, "20" if qualification == _VERIFIED else "28.2",
                )
            result.append(_case(
                f"C-{short}-{year}", f"{year}年{short}气体设备比较",
                "同设备比较生物资格、RFNBO回退与奖励及2026年三气体清缴变化",
                request, _catalog()[fossil], factors,
                ["methane_slip", "same_equipment", "ets_gas_year", "bio_qualification",
                 "rfnbo_qualification", "rfnbo_fallback"],
                compact=short == "OTTO_MS",
                assumptions=[_GAS_ASSUMPTION, "VERIFIED分支仅模拟接口资格声明，不提供真实批次认证。"],
            ))
    return result


def _d_cases():
    result = []
    baseline = _catalog()["MDO"]
    for mode in ("STATIC", "BIO_E", "RFNBO_E", "CERTIFIED"):
        payload, factor = _custom(mode)
        request = _request()
        request["candidates"] = [_candidate("custom", payload["pathId"], **{
            key: value for key, value in payload.items() if key != "pathId"
        })]
        result.append(_case(
            "D-custom-" + mode.lower(), f"自定义{mode}完整证据", "逐字段合成来源和单位可追踪",
            request, baseline, {"custom": factor}, ["custom", mode, "field_evidence"],
            compact=mode == "RFNBO_E",
            assumptions=["CERTIFIED是公式模式；合成来源均为SA，结果应保持ESTIMATED。"],
        ))
    for label, qualification, fraction in (
        ("unqualified", _NOT, "0"), ("assumed", _ASSUMED, "0.5"),
        ("verified", _VERIFIED, "1"),
    ):
        request = _request()
        request["candidates"] = [_candidate(
            "bio", "UCO_FAME", qualificationStatus=qualification,
            eligibleBiomassFraction=fraction, e="14.9",
        )]
        result.append(_case(
            "D-bio-" + label, "内置生物燃料资格分支", "检查有效合格生物质比例仅影响适用CO2处理",
            request, baseline, {"bio": _bio_factor("UCO_FAME", "14.9", qualification, fraction)},
            ["builtin_bio", "bio_qualification", label],
            assumptions=["资格和批次E是合成输入，不代表RED认证；CH4和N2O不归零。"],
        ))
    for label, qualification in (("unqualified", _NOT), ("assumed", _ASSUMED),
                                 ("verified", _VERIFIED), ("ineligible", "INELIGIBLE")):
        request = _request()
        fields = {"e": "20", "eu": "73.2"} if qualification == _VERIFIED else {}
        request["candidates"] = [_candidate(
            "renewable", "E_DIESEL", qualificationStatus=qualification, **fields,
        )]
        result.append(_case(
            "D-rfnbo-" + label, "内置电柴油资格分支", "检查完整回退、保守E假设与认证E输入",
            request, baseline,
            {"renewable": _rfnbo_factor("E_DIESEL", qualification,
                                       "20" if qualification == _VERIFIED else "28.2")},
            ["builtin_rfnbo", "rfnbo_qualification", label],
            assumptions=["核验资格仅为测试接口分支，不是有效认证凭据；FuelEU资格不自动赋予ETS零CO2。"],
        ))
    invalids = (
        ("negative-co2", "STATIC", "cfCO2", "-1", "INVALID_EMISSION_FACTOR", "负CO2因子"),
        ("negative-ch4", "STATIC", "cfCH4", "-0.1", "INVALID_EMISSION_FACTOR", "负CH4因子"),
        ("negative-n2o", "STATIC", "cfN2O", "-0.1", "INVALID_EMISSION_FACTOR", "负N2O因子"),
        ("missing-evidence", "STATIC", None, None, "MISSING_REQUIRED_FACTOR", "缺少逐字段证据"),
        ("wrong-unit", "STATIC", None, None, "MISSING_REQUIRED_FACTOR", "错误热值单位"),
        ("nonmethane-slip", "STATIC", "cslip", "1", "INVALID_CSLIP", "非甲烷路径滑移"),
        ("rwd2-2024", "RFNBO_E", None, None, "MISSING_REQUIRED_FACTOR", "奖励超出年份"),
        ("e283", "RFNBO_E", "E", "28.3", "RFNBO_E_EXCEEDS_LIMIT", "超过RFNBO强度门槛"),
        ("unknown-path", "STATIC", None, None, "MISSING_REQUIRED_FACTOR", "未知且不完整路径"),
    )
    for suffix, mode, field, value, code, name in invalids:
        payload, _ = _custom(mode)
        if field:
            payload[field] = value
        if suffix == "missing-evidence":
            del payload["sourceEvidence"]["cfCH4"]
        elif suffix == "wrong-unit":
            payload["sourceEvidence"]["lcv"]["unit"] = "MJ/kg"
        elif suffix == "unknown-path":
            payload = {"pathId": "SYNTHETIC_UNKNOWN"}
        request = _request(year=2024 if suffix == "rwd2-2024" else 2030)
        request["candidates"] = [
            _candidate("invalid", payload["pathId"], **{
                key: value for key, value in payload.items() if key != "pathId"
            }),
            _candidate("control", "MDO", "700"),
        ]
        assumptions = ["无效候选不提供解析快照；保留独立有效对照和B0。"]
        if suffix == "rwd2-2024":
            assumptions.append(
                "规范禁止2024年RWD=2；当前JSON边界将该自定义年份错误映射为MISSING_REQUIRED_FACTOR。"
            )
        result.append(_case(
            "D-" + suffix, name, "检查候选局部阻断，不影响独立对照与共享基准",
            request, baseline, {"control": baseline},
            ["invalid_candidate", suffix], issues=[_issue(code, "invalid")],
            assumptions=assumptions, compact=suffix == "missing-evidence",
        ))
    request = _request()
    request["candidates"] = [_candidate("missing", "MDO", None)]
    result.append(_case(
        "D-missing-price", "候选缺少报价", "保持因子和排放可计算，经济比较不可用",
        request, baseline, {"missing": baseline}, ["missing_price", "calculable"],
        issues=[_issue("PRICE_REQUIRED_FOR_COMPARISON", "missing")],
    ))
    request = _request()
    request["adjacentValidPortOfCallConfirmed"] = False
    result.append(_case(
        "D-confirmation-false", "未确认有效挂靠", "案例级必要确认失败，返回HTTP422",
        request, baseline, {}, ["invalid_case", "confirmation"],
        issues=[_issue("PORT_OF_CALL_CONFIRMATION_REQUIRED")], http=422,
        assumptions=["因子和范围快照仅描述预定输入；整个案例在确认步骤阻断。"],
    ))
    result.extend(_smoke_cases())
    return result


def _smoke_cases():
    catalog = _catalog()
    # Batch pure-reference smoke inputs by related pathways; no liquid/gas blend claim.
    groups = (
        ("liquid", "传统液体燃料", ("HFO", "LFO", "MDO", "MGO", "METHANOL_NG")),
        ("fossil-gas", "化石气体路径", (
            "LNG_OTTO_MEDIUM_SPEED", "LNG_OTTO_SLOW_SPEED", "LNG_DIESEL_SLOW_SPEED", "LNG_LBSI",
            "H2_NG_FC", "H2_NG_ICE", "LPG_PROPANE", "LPG_BUTANE", "NH3_NG_FC", "NH3_NG_ICE",
        )),
        ("bio-liquid", "生物液体路径", ("BIOETHANOL", "BIODIESEL", "HVO", "BIOMETHANOL", "UCO_FAME")),
        ("bio-gas", "生物气体路径", (
            "BIOLNG_OTTO_MS", "BIOLNG_OTTO_SS", "BIOLNG_DIESEL_SS", "BIOLNG_LBSI",
            "BIOH2_FC", "BIOH2_ICE",
        )),
        ("renewable-liquid", "未证明资格电燃料", ("E_DIESEL", "E_METHANOL")),
        ("renewable-gas", "未证明资格气体电燃料", (
            "E_LNG_OTTO_MEDIUM_SPEED", "E_LNG_OTTO_SLOW_SPEED", "E_LNG_DIESEL_SLOW_SPEED",
            "E_LNG_LBSI", "E_H2_FC", "E_H2_ICE", "E_NH3_FC", "E_NH3_ICE",
        )),
    )
    result = []
    for suffix, name, paths in groups:
        request = _request()
        factors = {}
        for path in paths:
            cid = "smoke-" + path.lower()
            request["candidates"].append(_candidate(
                cid, path, qualificationStatus=_NOT, specifiedBlendRatios=[],
                maxBlendRatio="0", candidateAllowsPureUse=True,
            ))
            factors[cid] = catalog[path]
        result.append(_case(
            "D-smoke-" + suffix, name + "冒烟检查", "独立冻结默认解析值与完整化石回退映射",
            request, catalog["MDO"], factors, ["builtin_smoke", suffix],
            assumptions=[
                "按路径分组仅为缩减请求数量；混兑上限为零，只保留纯用数学参考，不证明执行兼容性。",
                "RFNBO默认未证明资格，快照path_id为实际化石回退路径；请求保留原始路径。",
                "归一化排放NA按零参与算术；slip保留null与零的语义区别。",
            ],
        ))
    return result


def cases() -> list[dict]:
    """Return fresh JSON-compatible inputs and independently frozen snapshots."""
    return [*_a_cases(), *_b_cases(), *_c_cases(), *_d_cases()]
