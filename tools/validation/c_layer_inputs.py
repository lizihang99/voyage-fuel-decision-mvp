"""Reproducible synthetic input generator; no product dependencies."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import random


def decimal(value):
    v = F(value)
    with localcontext() as ctx:
        ctx.prec = 70
        return str(Decimal(v.numerator) / Decimal(v.denominator))


def fuel(lcv=".04", ghgi="95", price="600", co2="3", rwd="1"):
    # This is fixture construction, not a certified factor/qualification.
    return dict(lcv=lcv, wtt=decimal(F(ghgi) * F(rwd) - F(co2) / F(lcv)),
                co2=co2, ch4="0", n2o="0", slip="0", rwd=rwd, price=price)


def inputs():
    base = dict(id="C-LP-01", label="普通双燃料", year=2026,
                scope=".5", surrender="1", fueleu_scope=".5",
                mass="100", cap="1", supply=None, budget=None, eua="80",
                baseline=fuel(), candidate=fuel(".02", "60", "500", "1"))
    cases = []

    def add(label, **kw):
        c = deepcopy(base)
        c.update(kw, id=f"C-LP-{len(cases)+1:02d}", label=label)
        cases.append(c)
        return c

    add("普通双燃料")
    add("候选同能源更便宜", candidate=fuel(".05", "60", "500", "1"))
    add("候选吨价高但同能源便宜", candidate=fuel(".05", "60", "650", "1"))
    add("最大混兑上限", cap=".1")
    add("供应上限", supply="10")
    add("增量预算上限", budget="5000")
    add("三个约束同时施加", cap=".4", supply="10", budget="5000")
    add("零供应", supply="0")
    add("零预算且成本增加", budget="0")
    add("零预算且成本下降", budget="0", candidate=fuel(".05", "60", "500", "1"))
    add("双方均不达标", candidate=fuel(".02", "110", "500", "1"))
    add("虽改善但仍无数学解", candidate=fuel(".02", "92", "500", "1"))
    add("B0已达标且候选更差更便宜", baseline=fuel(ghgi="80", price="1000"),
        candidate=fuel(".04", "100", "400", "3"))
    add("B0已达标且候选继续改善", baseline=fuel(ghgi="80"))
    add("候选端点恰好达标", candidate=fuel(".04", "89.3368", "500", "1"))
    exact = dict(baseline=fuel(ghgi="100"), candidate=fuel(".04", "78.6736", "900", "1"))
    add("目标恰好等于混兑上限", cap=".5", **exact)
    add("目标高于混兑上限1e-20", cap=".49999999999999999999", **exact)
    add("目标低于混兑上限1e-20", cap=".50000000000000000001", **exact)
    add("RWD=2分式目标", candidate=fuel(".02", "30", "500", "1", "2"))
    add("RWD回退后的普通分母", candidate=fuel(".02", "60", "500", "1", "1"))
    add("缺候选价格且有预算", budget="5000", candidate=fuel(price=None))
    add("缺EUA价格且有预算", budget="5000", eua=None)
    add("2024 FuelEU不适用", year=2024, surrender=".4", fueleu_scope=None)
    add("2025 CO2-only", year=2025, surrender=".7")
    add("2030目标", year=2030)
    add("范围为零", scope="0", fueleu_scope="0")
    add("成本和GHGI均并列", candidate=fuel())
    methane = fuel(".05", "60", "500", "2.75")
    methane.update(ch4=".00005", n2o=".0001", slip="3.1")
    add("甲烷设备滑移与三气体", candidate=methane)
    rng = random.Random(20260907)
    for i in range(32):
        c = deepcopy(base)
        c.update(id=f"C-RND-{i+1:02d}", label="固定种子合成案例",
                 cap=str(rng.choice([".1", ".3", ".5", "1"])),
                 budget=rng.choice([None, "0", "2000", "15000"]),
                 supply=rng.choice([None, "5", "50", "200"]),
                 baseline=fuel(ghgi=str(rng.randint(70, 110)), price=str(rng.randint(400, 900))),
                 candidate=fuel(rng.choice([".02", ".04", ".05"]), str(rng.randint(20, 130)),
                                str(rng.randint(200, 1400)), rng.choice(["1", "2", "3"]),
                                rng.choice(["1", "2"])))
        cases.append(c)
    lines = [
        ("单次切换与支配交点", [("a", "0", "0"), ("b", "10", "1"), ("c", "30", "3"), ("d", "100", "2")]),
        ("两次有效切换", [("a", "0", "0"), ("b", "10", "2"), ("c", "40", "4")]),
        ("全平行", [("a", "0", "1"), ("b", "10", "1"), ("c", "20", "1")]),
        ("全重合", [("a", "10", "1"), ("b", "10", "1"), ("c", "10", "1")]),
        ("零价值交点", [("a", "0", "0"), ("b", "0", "1")]),
        ("仅负交点", [("a", "10", "0"), ("b", "0", "1")]),
        ("极近交点1e-31", [("a", "0", "0"), ("b", "1", "1"),
                          ("c", "2.0000000000000000000000000000001", "2")]),
        ("改善为负", [("a", "0", "0"), ("b", "-10", "-1")]),
    ]
    builtin = deepcopy(base)
    builtin.update(id="C-BUILTIN-01", label="内置UCO_FAME基准与便宜MGO候选",
                   baseline=dict(lcv=".037", wtt="-61.694594594594594594594594594594594594594594594595",
                                 co2="2.834", ch4=".00005", n2o=".00018", slip="0", rwd="1",
                                 price="1000"),
                   candidate=dict(lcv=".0427", wtt="14.4", co2="3.206", ch4=".00005",
                                  n2o=".00018", slip="0", rwd="1", price="400"))
    return dict(schema_version=1, seed=20260907, synthetic=True, constraints=cases,
                builtin_reproduction=dict(case=builtin, source="2026-09-07 local factor snapshot; no new factor audit",
                    payload=dict(reportYear=2026, departurePort="CNSHG", arrivalPort="NLRTM",
                                 adjacentValidPortOfCallConfirmed=True, currency="EUR",
                                 baseline=dict(pathId="UCO_FAME", massTonnes="100", pricePerTonne="1000"),
                                 euaPricePerTCO2e="80",
                                 candidates=[dict(candidateId="mgo", pathId="MGO", pricePerTonne="400",
                                                  allowsPureUse=True, maxBlendRatio="1")])),
                envelope=[dict(id=f"C-ENV-{i+1:02d}", label=label, lines=rows)
                          for i, (label, rows) in enumerate(lines)])
