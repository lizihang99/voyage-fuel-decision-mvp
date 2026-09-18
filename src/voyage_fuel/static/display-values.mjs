const DECIMAL_PATTERN = /^[+-]?\d+(?:\.\d+)?$/;

function decimalParts(value) {
  const raw = String(value ?? "").trim();
  const match = raw.match(/^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/);
  if (!match) return null;
  const integer = match[2];
  const fraction = match[3] || "";
  const exponent = Number.parseInt(match[4] || "0", 10);
  const digits = `${integer}${fraction}`;
  const decimalPosition = integer.length + exponent;
  const power10 = decimalPosition - digits.length;
  return { negative: match[1] === "-", digits, power10 };
}

function normalizeDecimal(digits, power10, negative = false) {
  let value = digits.replace(/^0+/, "") || "0";
  let position = value.length + power10;
  let integer;
  let fraction;
  if (position <= 0) {
    integer = "0";
    fraction = `${"0".repeat(-position)}${value}`;
  } else if (position >= value.length) {
    integer = `${value}${"0".repeat(position - value.length)}`;
    fraction = "";
  } else {
    integer = value.slice(0, position);
    fraction = value.slice(position);
  }
  fraction = fraction.replace(/0+$/, "");
  const canonical = fraction ? `${integer}.${fraction}` : integer;
  return negative && canonical !== "0" ? `-${canonical}` : canonical;
}

export function percentInputToRatio(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  if (!DECIMAL_PATTERN.test(raw)) throw new Error("INVALID_PERCENT");
  const unsigned = raw.replace(/^[+-]/, "");
  if (Number.parseFloat(unsigned) > 100) throw new Error("PERCENT_OUT_OF_RANGE");
  const parts = decimalParts(raw);
  if (!parts) throw new Error("INVALID_PERCENT");
  const canonical = normalizeDecimal(parts.digits, parts.power10 - 2, parts.negative);
  if (Number.parseFloat(canonical) < 0) throw new Error("PERCENT_OUT_OF_RANGE");
  return canonical;
}

export function ratioToPercentInput(value) {
  if (value === null || value === undefined || value === "") return "";
  const parts = decimalParts(value);
  if (!parts) throw new Error("INVALID_RATIO");
  return normalizeDecimal(parts.digits, parts.power10 + 2, parts.negative);
}

export function formatDecimalStringScaled(value, decimals, power10 = 0) {
  if (value === null || value === undefined || value === "") return "-";
  const raw = String(value).trim();
  const match = raw.match(/^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/);
  if (!match) return raw;
  const sign = match[1] === "-" ? "-" : "";
  const digits = `${match[2]}${match[3] || ""}`;
  const exponent = Number.parseInt(match[4] || "0", 10) + power10;
  const decimalPosition = match[2].length + exponent;
  const shift = decimalPosition - digits.length + decimals;
  let scaled;
  if (shift >= 0) {
    scaled = BigInt(`${digits}${"0".repeat(shift)}`);
  } else {
    const divisor = 10n ** BigInt(-shift);
    const integerPart = BigInt(digits) / divisor;
    const remainder = BigInt(digits) % divisor;
    scaled = integerPart + (remainder * 2n >= divisor ? 1n : 0n);
  }
  const scale = 10n ** BigInt(decimals);
  let integerText;
  if (decimals > 0) {
    const whole = scaled / scale;
    const fraction = String(scaled % scale).padStart(decimals, "0");
    integerText = `${whole}.${fraction}`;
  } else {
    integerText = String(scaled);
  }
  if (sign && scaled !== 0n) return `-${integerText}`;
  return integerText;
}
