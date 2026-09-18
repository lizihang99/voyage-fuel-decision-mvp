const FUEL_LABELS = Object.freeze({
  HFO: "重质燃油",
  LFO: "轻质燃油",
  MDO: "船用柴油",
  MGO: "船用 Gas Oil",
  LNG_OTTO_MEDIUM_SPEED: "LNG · Otto 中速机",
  LNG_OTTO_SLOW_SPEED: "LNG · Otto 低速机",
  LNG_DIESEL_SLOW_SPEED: "LNG · 柴油低速机",
  LNG_LBSI: "LNG · LBSI",
  METHANOL_NG: "化石甲醇",
  H2_NG_FC: "化石氢 · 燃料电池",
  H2_NG_ICE: "化石氢 · 内燃机",
  LPG_PROPANE: "LPG 丙烷",
  LPG_BUTANE: "LPG 丁烷",
  NH3_NG_FC: "化石氨 · 燃料电池",
  NH3_NG_ICE: "化石氨 · 内燃机",
  BIOETHANOL: "生物乙醇",
  BIODIESEL: "生物柴油",
  HVO: "HVO",
  BIOLNG_OTTO_MS: "生物 LNG · Otto 中速机",
  BIOLNG_OTTO_SS: "生物 LNG · Otto 低速机",
  BIOLNG_DIESEL_SS: "生物 LNG · 柴油低速机",
  BIOLNG_LBSI: "生物 LNG · LBSI",
  BIOMETHANOL: "生物甲醇",
  BIOH2_FC: "生物氢 · 燃料电池",
  BIOH2_ICE: "生物氢 · 内燃机",
  UCO_FAME: "UCO 生物柴油",
  E_DIESEL: "电制柴油",
  E_METHANOL: "电制甲醇",
  E_LNG_OTTO_MEDIUM_SPEED: "电制 LNG · Otto 中速机",
  E_LNG_OTTO_SLOW_SPEED: "电制 LNG · Otto 低速机",
  E_LNG_DIESEL_SLOW_SPEED: "电制 LNG · 柴油低速机",
  E_LNG_LBSI: "电制 LNG · LBSI",
  E_H2_FC: "电制氢 · 燃料电池",
  E_H2_ICE: "电制氢 · 内燃机",
  E_NH3_FC: "电制氨 · 燃料电池",
  E_NH3_ICE: "电制氨 · 内燃机",
});

const STATUS_LABELS = Object.freeze({
  BLOCKED: "阻断",
  CALCULABLE: "可计算",
  COMPARABLE: "可比较",
  FEASIBLE: "满足约束",
  CONSTRAINT_UNVERIFIED: "约束未验证",
  CONSTRAINT_INFEASIBLE: "超出约束",
  TARGET_REACHABLE: "目标可达",
  TARGET_NOT_APPLICABLE: "目标不适用",
  TARGET_NO_SOLUTION: "无达标方案",
  TARGET_UNREACHABLE_UNDER_CONSTRAINTS: "约束下不可达",
  CONDITIONAL: "条件式建议",
  UNAVAILABLE: "暂无可用方案",
  EXECUTION_CONDITIONS_PENDING: "执行条件待确认",
  AVAILABLE: "可用",
  PRICE_REQUIRED_FOR_COMPARISON: "需要价格后才能比较",
  FINITE_NON_NEGATIVE: "已得到有效临界值",
  NEGATIVE_THRESHOLD: "临界值不适用",
  NO_FINITE_POINT: "没有可绘制的完整点",
  BUDGET_UNAVAILABLE_WITHOUT_PRICES: "缺少价格，预算暂无法验证",
});

const REASON_LABELS = Object.freeze({
  MODEL_COST_MINIMUM: "当前模型成本最低",
  CONSTRAINT_RESULT: "由约束条件筛选出的方案",
  LOWER_ENVELOPE_SWITCH: "参考价值变化导致方案排序切换",
  REFERENCE_VALUE_SENSITIVITY: "参考价值敏感性结果",
});

const WARNING_LABELS = Object.freeze({
  BUDGET_UNAVAILABLE_WITHOUT_PRICES: "缺少价格，预算边界暂无法验证",
  TARGET_UNREACHABLE_UNDER_CONSTRAINTS: "当前约束下目标不可达",
  TARGET_NO_SOLUTION: "当前候选燃料没有可用达标方案",
  CONSTRAINT_UNVERIFIED: "约束尚未完成验证",
});

export function fuelLabel(pathId) {
  return FUEL_LABELS[pathId] || pathId || "未知燃料";
}

export function statusLabel(status) {
  const raw = String(status || "");
  return STATUS_LABELS[raw] || (raw ? "状态待核对" : "状态未提供");
}

export function reasonLabel(reason) {
  const raw = String(reason || "");
  return REASON_LABELS[raw] || (raw ? "结果依据待核对" : "结果依据未提供");
}

export function warningLabel(warning) {
  const raw = String(warning || "");
  return WARNING_LABELS[raw] || (raw ? "存在待核对的约束提示" : "约束提示未提供");
}
