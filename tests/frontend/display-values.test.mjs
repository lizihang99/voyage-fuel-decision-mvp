import test from "node:test";
import assert from "node:assert/strict";

import {
  formatDecimalStringScaled,
  percentInputToRatio,
  ratioToPercentInput,
} from "../../src/voyage_fuel/static/display-values.mjs";


test("percent input preserves exact mass ratio", () => {
  assert.equal(percentInputToRatio("20"), "0.2");
  assert.equal(percentInputToRatio("0"), "0");
  assert.equal(percentInputToRatio("100"), "1");
  assert.equal(percentInputToRatio("2.2130676682982508109"), "0.022130676682982508109");
  assert.equal(ratioToPercentInput("0.022130676682982508109"), "2.2130676682982508109");
  assert.equal(percentInputToRatio(""), null);
  assert.throws(() => percentInputToRatio("100.01"), /PERCENT_OUT_OF_RANGE/);
  assert.throws(() => percentInputToRatio("-0.1"), /PERCENT_OUT_OF_RANGE/);
  assert.throws(() => percentInputToRatio("abc"), /INVALID_PERCENT/);
});


test("existing display precision behavior is preserved", () => {
  assert.equal(formatDecimalStringScaled("0.022130676682982508109", 4, 2), "2.2131");
  assert.equal(formatDecimalStringScaled("1.005", 2), "1.01");
});
