# 安全修复计划与验证记录

**目标：**修复已审计的结果一致性、纯用限制、预算状态和展示口径问题。

**基线：**`main@8e465fa`。在 `codex/safe-decision-contract-fixes` 分支内实施，不自动提交或推送；保留已有 E2E 产物变更。

**依据：**当前计算规格第 10 节及第 697 行的 B100 限制，以及本次双智能体审计。现有用户要求为制定计划并直接修复。

**技术范围：**Python dataclass/JSON/FastAPI、原生 JavaScript、unittest/Playwright。

## 不变项与取舍

- 不修改排放公式、默认因子、港口制度规则、质量混兑口径或年度目标。
- 不增加换汇、证书认证、年度结算、多燃料联合优化或案例持久化。
- 保留导出服务端重算。浏览器仅发送与屏幕结果绑定的输入快照。
- 保留可计算但超约束的参考场景；未验证预算不得被表述为已满足所有约束。
- 纯用未允许时，显式 B100 返回候选级结构化错误；自动边界为 1 时不生成 B100，不伪造 `1-epsilon`。
- 不增加任意近似混兑上限。连续边界仍作为数学参考，能否成为报告/推荐场景另行判断。

## 执行步骤

### 1. 复现与回归测试

- [x] 跑现有测试，记录基线结果。
- [x] 增加 `tests/test_decision_safety.py`：显式/自动 B100、预算缺价格、推荐排除、API/CSV/PDF 状态一致性。
- [x] 增加 `tests/e2e/test_decision_safety.py`：输入修改、候选增删、响应乱序、显示精度、导出快照、业务阻断和币种/证据标签。
- [x] 先确认新增测试在旧实现上失败，区分环境错误与实际断言失败。

### 2. 内核与接口最小修复

- [x] `contracts.py`、`models.py`、`json_io.py`：沿用 `INVALID_BLEND_RATIO`，禁止未允许的显式纯用；API 定位到指定比例字段，并保持其他候选可计算。
- [x] `calculator.py`：统一报告集合的纯用过滤；预算无法评估且比例大于零时标记 `CONSTRAINT_UNVERIFIED`，已明确超约束仍优先标记不可行。
- [x] `case_comparison.py`：预算未验证的最大改善建议不可用，并返回具体原因；保留 B0 和不受影响候选。
- [x] 聚焦测试通过，确认默认公式和已知基准结果不变。

### 3. 页面与导出一致性

- [x] `app.js`：记录输入版本、计算请求序号、成功输入快照；输入/候选增删/港口选择使结果失效。
- [x] 丢弃过期成功或失败响应，防止并发请求覆盖；无有效基准时禁止导出。
- [x] 导出使用成功输入快照和当前显示精度；返回前再检查版本，避免下载与当前屏幕不一致。
- [x] `index.html`：初始禁用导出；显示精度、页签切换不使结果失效。
- [x] Playwright 验证桌面和移动端，截图写入忽略目录 `output/`。

### 4. 口径与文档

- [x] 页面显式展示计算、约束、执行状态；预算未知显示中文提示。
- [x] 将结果中的 `x_cap` 标签改为“综合约束上限”；保留输入最大比例。
- [x] 页面注明统一案例币种、无换汇、FuelEU 指示性金额为 EUR；PDF 保持同样边界，CSV 保留独立币种字段。
- [x] 页面区分目录 RFNBO 默认资格与高级自定义，说明来源状态由提供方声明、系统不自动认证证书。
- [x] README 补充内核/API/页面/报告差异和本次新增状态。

### 5. 最终验证

- [x] Python 非 E2E：`python -m unittest discover -s tests -p test_*.py`（使用仅顶层测试加载，避免与 E2E 重复）。
- [x] E2E：`tests.e2e.test_decision_safety`、现有流程和精度测试；产物目录重定向至 `output/`。
- [x] Node：`node --test port-identity-mapping.test.mjs port-scope-rates.test.mjs`。
- [x] `node --check src/voyage_fuel/static/app.js`、`python -m compileall -q src tests`、`git diff --check`。
- [x] 检查最终 diff；启动本地服务供复核，报告验证结果与仍未处理的范围。

## 验证记录

本轮验证结果：

- Python 安全回归：`6 passed`
- 网页安全回归：`6 passed`
- 页面契约测试：`16 passed`
- Python 非 E2E 全量：`216 passed`
- E2E 全量：`21 passed`
- Node 港口测试：`29 passed`
- JavaScript 语法检查：通过
- 全量 Python 测试和最终 `git diff --check` 在修复完成后执行并记录在交付消息中。
