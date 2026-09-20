# 示例就地教程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 状态：已实施；自动验证完成，真人新手验收待执行。实际结果见 [示例就地教程验证报告](../../validation/contextual-example-tutorial-report.md)。
>
> 下方保留原计划的步骤复选框；实施完成证据以验证报告和本次最终测试输出为准，真人试用部分仍不作为已完成项。

**Goal:** 让新用户通过现有两个示例、就地框选及短文案读懂结果，并找到自己的输入、计算与导出路径，不安排改条件练习。

**Architecture:** 使用既有示例加载器、API及工作台结果模型；增加纯教程状态/文案模块和轻量DOM指引模块。请求序号保护、失效、目标选择与导出继续由现有产品负责；独立参考只用于测试，不进入浏览器。

**Tech Stack:** FastAPI/Jinja2、原生JavaScript ES modules、CSS、Node test runner、Python unittest、Playwright、现有business-case独立核验器。

**Spec:** [示例就地教程设计规格](../specs/2026-09-20-contextual-example-tutorial-design.md)

## Global Constraints

- 实施得到明确指令后开始；保留现有工作区修改并遵循TDD顺序。
- 保留“选择示例后自动计算”，不增加一次计算点击。
- 不安排修改条件练习，包括“自愿修改HVO供应量”。
- 不增加下一步、打卡、进度、强制点击、测验、登录或教学弹窗链。
- 浏览器不读取`expected.json`，不加载独立计算器，不求最优比例、成本或约束。
- 数值来自当前API快照/现有展示模型；增量直接使用服务端delta，使用现有格式化函数和精度设置。
- 修改输入立即撤下案例专属说明与框选；选择方案及精度调整不退出教程。
- 同一时间最多一个主框选，不抢焦点、不自动滚屏。
- 教程加载/运行失败不能使正常计算失败。
- legacy只保留原有产品功能与可选说明，不复制完整高亮教程。
- 不修改计算公式、推荐规则、业务请求、CSV/PDF数据合同。
- 保留用户和其他任务的已有修改；不自动提交、不重置、不覆盖冻结期望。

## 0. 实施前检查

- [ ] 读取规格全文及其R01-R12、V01-V16，确认最新用户指令没有改变范围。
- [ ] 执行`git status --short`，记录已有修改；阅读本次目标文件的实际内容与差异。
- [ ] 特别检查`workbench-view.mjs`的并行修改，按稳定语义接入，不还原标题或旧布局。
- [ ] 确认`.\.venv\Scripts\python.exe`、Node、Playwright运行条件；使用测试自带临时端口，不停止8000端口服务。
- [ ] 先运行下列既有聚焦测试并记录基线，失败先定位，不把旧失败记为教程回归。

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_teaching_examples tests.test_workbench_page -v
node --test tests/frontend/display-values.test.mjs tests/frontend/workbench-model.test.mjs
```

不将“未运行”写成通过；不沿用历史272/41/61等数量作为本轮统计。

## 1. 文件与接口地图

| 文件 | 动作及责任 |
|---|---|
| `src/voyage_fuel/static/teaching-guide.mjs` | 新增纯状态、请求匹配、文案投影 |
| `src/voyage_fuel/static/teaching-guide-view.mjs` | 新增就地挂载、观察与高亮 |
| `src/voyage_fuel/static/app.js` | 小范围生命周期接入、可选模块降级 |
| `src/voyage_fuel/static/workbench-view.mjs` | 稳定锚点、渲染完成回调 |
| `src/voyage_fuel/static/workbench-model.mjs` | 只读复用展示模型、scenarioById与候选状态，不修改 |
| `src/voyage_fuel/static/workbench.css` | 样式、移动端、减少动态效果 |
| `src/voyage_fuel/templates/index.html` | 指引开关及说明页新标签链接 |
| `src/voyage_fuel/templates/workbench_results.html` | 非业务表单内的教程背景槽 |
| `src/voyage_fuel/templates/examples_guide.html` | 两例速览、实际使用清单、边界 |
| `tests/frontend/teaching-guide.test.mjs` | 新增纯状态与文案测试 |
| `tests/e2e/test_teaching_guide.py` | 新增教程浏览器与独立对照测试 |
| `tests/test_teaching_examples.py` | 扩展说明页及资源合同 |
| `docs/validation/contextual-example-tutorial-report.md` | 验证后新建，记录实际证据与未完成项 |

冻结输入资源及`tests/fixtures/business-cases/`均只读。截图和运行报告写入`output/contextual-example-tutorial/`，不覆盖既有e2e截图。

拟定接口与事件严格使用规格第7.2节。所有DOM渲染使用普通文本或现有转义函数；不拼接未转义的候选文本。

### Task 1: 教程状态与请求匹配

**Files:** 新增`teaching-guide.mjs`、`tests/frontend/teaching-guide.test.mjs`。

**Consumes:** 已校验的分发请求、实际提交请求、现有请求序号。

**Produces:** `createGuideState()`、`reduceGuide(state, event)`、`sameExampleRequest(submitted, frozenRequest)`。

- [ ] 写失败测试，至少包括以下骨架：

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import {
  createGuideState, reduceGuide, sameExampleRequest,
} from "../../src/voyage_fuel/static/teaching-guide.mjs";

test("a late response cannot restore invalidated guidance", () => {
  let state = reduceGuide(createGuideState(),
    { type: "APPLIED", caseId: "A-2025", requestId: 1 });
  state = reduceGuide(state, { type: "INVALIDATED" });
  const next = reduceGuide(state,
    { type: "RESOLVED", requestId: 1, matched: true });
  assert.equal(next.phase, "modified");
});

test("closing guidance survives a different example", () => {
  let state = reduceGuide(createGuideState(),
    { type: "VISIBILITY", visible: false });
  state = reduceGuide(state,
    { type: "APPLIED", caseId: "B-default", requestId: 2 });
  assert.equal(state.visible, false);
});

test("matching ignores object key order but preserves exact inputs", () => {
  assert.equal(sameExampleRequest(
    { baseline: { massTonnes: "1000", pathId: "MDO" }, candidates: [] },
    { candidates: [], baseline: { pathId: "MDO", massTonnes: "1000" } },
  ), true);
  assert.equal(sameExampleRequest({ mass: "1000" }, { mass: "1001" }), false);
  assert.equal(sameExampleRequest({ mass: null }, { mass: "0" }), false);
});
```

- [ ] 执行`node --test tests/frontend/teaching-guide.test.mjs`，确认因导出尚不存在而失败。
- [ ] 实现无副作用的状态转换和递归结构比较。`RESOLVED`的序号不匹配时返回原状态；输入失效清除请求关联；`VISIBILITY`只改变visible。
- [ ] 增加对象参数不被修改、匹配失败不进入ready、失败响应、候选数组顺序与十进制类型测试。
- [ ] 重跑上述命令，记录通过结果；审查模块没有DOM、fetch或生产计算逻辑。

状态实现的关键分支应遵循：

```javascript
if (event.type === "VISIBILITY") {
  return { ...state, visible: event.visible };
}
if (event.type === "RESOLVED" && event.requestId !== state.requestId) {
  return state;
}
```

### Task 2: 案例文案与显示字段合同

**Files:** 扩展`teaching-guide.mjs`及其测试；只读复用`workbench-model.mjs`。

**Consumes:** ready状态、`buildWorkbenchDisplayModel`的display、实际提交和分发请求。

**Produces:** `buildGuideNotes({ state, display, displayConfig, submittedInput, frozenRequest })`返回`{id, anchor, title, text}[]`。

- [ ] 为未ready、已修改、请求不一致写失败测试，三种情况结果均为空数组。

```javascript
import { buildGuideNotes } from "../../src/voyage_fuel/static/teaching-guide.mjs";

test("modified inputs never retain example-specific copy", () => {
  const state = reduceGuide(createGuideState(), { type: "INVALIDATED" });
  assert.deepEqual(buildGuideNotes({
    state, display: null, displayConfig: { mass: 3, energy: 3, ratio: 4, price: 2 },
    submittedInput: {}, frozenRequest: {},
  }), []);
});
```

- [ ] 从现有workbench-model测试的最小产品结果形状构建局部测试数据，先通过`buildWorkbenchDisplayModel`生成display再测文案；覆盖cost/target/improvement目标、selectedDetail.changes及sensitivity.candidates。
- [ ] 固定基础三种note ID、比较三种note ID与规格锚点的对应关系，缺字段只退化当前说明，不让整个模块抛错。
- [ ] 运行Node聚焦测试确认缺失文案或错误字段定位导致失败。
- [ ] 实现规格第4节文案，复用现有数字格式化；不给浏览器写入789768等冻结答案。赢家从goalCards.scenarioId关联scenarioRows得到；金额、比例及delta读取display；资格/约束通过现有服务端状态说明。
- [ ] 对“缺口”“未达到”“供应下不可达”等判断使用服务端状态，前端仅作展示映射；缺状态时显示中性解释。
- [ ] 增加空值、不认识的状态、被阻断候选、错误赢家、当前查看与推荐不同、调整精度测试。
- [ ] 增加恶意候选名称测试，将`<img onerror=...>`作为纯文本传递，后续视图不得执行。
- [ ] 重跑新旧model和display-values测试；检查新代码没有独立排序、优化或财务计算。

基准/当前方案状态直接读取`display.scenarioById.get(id).result.fuel_eu.status`；`DEFICIT_ESTIMATE`、`SURPLUS_ESTIMATE`、`ON_TARGET_ESTIMATE`对应缺口、盈余和参考线一致。候选状态读取`display.sensitivity.candidates`对应candidateId的targetStatus。不得新增业务状态或用教程内浮点比较代替现有目标判定。

### Task 3: 稳定锚点与非阻塞高亮

**Files:** 新增`teaching-guide-view.mjs`；修改`workbench-view.mjs`、`workbench.css`；新增`tests/e2e/test_teaching_guide.py`。

**Consumes:** `{ state, notes }`及规格第7.3节锚点。

**Produces:** `createTeachingGuideView({ root, onVisibilityChange })`返回`render({state, notes})`、`destroy()`；工作台回调`onRendered({display, displayConfig, selectedScenarioId})`。root为当前document，仅对声明的锚点操作。

- [ ] 用`BrowserAppMixin`新增不发产品计算请求的视图测试：在浏览器`page.evaluate`内动态导入新模块，构造带锚点的小型DOM，通过固定notes测试挂载、高亮和销毁。
- [ ] 首先断言缺模块/缺锚点时失败；不通过加载生产计算结果绕过这一步。
- [ ] 在工作台添加稳定`data-guide-anchor`，按candidate_id为限量UCO打标，不能以候选数组位置区分。
- [ ] 增加`onRendered`回调，默认无操作；每次innerHTML重绘后调用，教程异常在调用边界隔离。清理旧观察器后才能重新绑定。
- [ ] 实现短注释挂载和样式；DOM合同为`data-guide-note="<id>"`和当前目标`data-guide-active="true"`。inactive目标移除active属性；缺锚点时跳过，不能框选body作为替代。
- [ ] 按规格视口40%焦点线计算可见note的最近目标，rAF合并滚动读取；fallback只保留初始框选及说明。

核心DOM操作约束：

```javascript
const paragraph = document.createElement("p");
paragraph.dataset.guideNote = note.id;
paragraph.textContent = note.text;
// Attach next to the semantic anchor; never append to a numeric cell.
```

- [ ] 用桌面、390px、320px布局验证一次最多一个框选；说明不压住表头、金额、单位和按钮。移动端只挂到可见的卡片布局，不向隐藏桌面表格重复插入。
- [ ] 在滚动前后记录`document.activeElement`，确保教程不改变焦点；关闭时清除所有note和active属性。
- [ ] 重绘三次并验证说明数量不增长；destroy后滚动不重新生成框选。
- [ ] 执行新浏览器模块测试和既有workbench浏览器聚焦测试，人工打开本次截图检查遮挡。

### Task 4: 接入真实加载、关闭和失效流程

**Files:** 修改`app.js`、`index.html`、`workbench_results.html`；扩展新教程e2e。

**Consumes:** Tasks 1-3接口、`loadExample`/`calculate`/`invalidateResults`和`requestSerial`。

**Produces:** 两例加载后自动呈现教程，教程始终不改变业务工作流。

- [ ] 增加失败浏览器测试：加载A/B只请求一次`/api/calculate`；`#teaching-guide-toggle`在`#case-form`之外；关闭、恢复不产生新API请求、不修改结果快照。
- [ ] 工作台按需导入模块，初始化失败采用`null`教程对象并保留普通工作台；不要把导入放在会阻断`calculate`的await链上。
- [ ] 将新复选框绑定`VISIBILITY`。loadExample成功替换输入后，由calculate创建有效requestId时发APPLIED；有效响应保存实际输入/结果/快照后、renderResults前发RESOLVED，实际请求用sameExampleRequest判断。缺基准或快照时不发RESOLVED。
- [ ] 模块初始化晚于计算完成时，同步已有快照并挂载一次，不重算；重绘回调必须传当前displayConfig，确保初次与精度变更使用同一数据合同。
- [ ] clearResults仅清除旧DOM，不把正常“计算中”误写为FAILED；真正失败发FAILED；任何用户业务输入修改发INVALIDATED，包括尚未生成结果的修改。
- [ ] 手动重算未修改的示例可以重新ready；已modified的示例即使数值恢复也不自动恢复教程，重新加载例子才解除modified。
- [ ] 捕获API响应时保存实际request和result，以新测试核对数据。不得为了教程改动payload来源；若发现原有表单提交合同缺陷，另记阻断并先补失败回归，不能用教程分支掩盖。
- [ ] 阻断旧请求返回，验证不会复活旧教程；资源请求失败/无效资源/取消覆盖保留原教程。已替换输入但计算失败时不能保留旧结论。
- [ ] 切换目标、点击方案与调整精度后核对说明和高亮重新绑定，关闭状态仍保留。
- [ ] 屏蔽教程模块网络请求或故意让教程render抛错，验证正常计算、推荐与导出仍可用。

关键浏览器断言：

```python
self.assertEqual(
    page.locator("#case-form #teaching-guide-toggle").count(), 0
)
page.locator("#teaching-guide-toggle").uncheck()
self.assertEqual(page.locator("[data-guide-note]").count(), 0)
self.assertEqual(page.locator('[data-guide-active="true"]').count(), 0)
self.assertFalse(page.locator("#export-csv").is_disabled())
```

迟到响应测试使用Playwright路由延迟和现有请求序号，不以固定sleep作为正确性的依据。

### Task 5: 配套说明与实际使用衔接

**Files:** 修改`examples_guide.html`、`index.html`及`tests/test_teaching_examples.py`，扩展教程e2e。

**Consumes:** 规格第4节已确认的内容。

**Produces:** 两例短说明、开始自己的计算清单、不丢状态的帮助链接。

- [ ] 先增加失败模板测试：

```python
def test_guide_has_real_input_checklist_without_exercise(self):
    html = self.client.get("/examples/guide").text
    self.assertIn("开始自己的计算", html)
    for label in ("报告年份", "候选", "资格", "重新计算"):
        self.assertIn(label, html)
    for old_prompt in ("HVO 供应量改为 0", "完成练习", "下一步"):
        self.assertNotIn(old_prompt, html)
```

- [ ] 为两个入口视图中的说明链接增加`target="_blank"`与`rel="noopener"`断言。
- [ ] 修改说明页：删除修改供应量指令；使用规格中的两例内容和四步输入清单；保留1000吨非典型油耗、合成输入、资格和年度边界。
- [ ] 在工作台的方案列表/地图/切换点/导出/编辑输入附近增加规格规定的短注释，仅在开启教程且原始示例有效时显示。
- [ ] 页面仅补充简短解释，不复制具体冻结金额，不新增加载按钮或教程页面。
- [ ] 浏览器使用`expect_popup`验证说明打开后原页输入、选择、结果快照与导出状态保留。
- [ ] legacy回归：有说明链接且正常加载计算，无工作台教程锚点查找异常。

### Task 6: 独立参考、故障注入与完整回归

**Files:** 扩展`tests/e2e/test_teaching_guide.py`，验证后新增交付报告。

**Consumes:** 现有`prepare_reference`、`validate_product_result`，A-2025/B-default冻结请求和期望。

**Produces:** 输入/API完整结果/就地说明/导出一致性的实际运行证据。

- [ ] 在新测试类中先prepare_reference再启动产品服务：

```python
@classmethod
def setUpClass(cls):
    reference = prepare_reference(ROOT / "tests/fixtures/business-cases")
    if reference["production_modules_loaded"]:
        raise AssertionError(reference["production_modules_loaded"])
    cls.reference_cases = {
        entry["case"]["id"]: entry for entry in reference["results"]
    }
    super().setUpClass()
```

`prepare_reference`、`ROOT`、`BrowserAppMixin`的导入沿用`test_teaching_examples.py`的现有路径方式；不在参考worker中导入产品模块。不改旧测试的运行历史。

- [ ] A/B产品请求前已有独立期望；实际post_data等于冻结请求，调用validate_product_result逐字段比较完整API结果，不能只检查教程提到的数字。
- [ ] 教程可见值通过显示配置与API原值核对；案例特定结论同时与独立期望核对。记录费用、目标、比例、余额、供应状态，保留未四舍五入的比较依据。
- [ ] 用`copy.deepcopy(actual)`分别篡改赢家、HVO比例、金额、UCO目标状态；每次要求validate_product_result报告失败，正常对照则通过。
- [ ] 浏览器路由注入被改金额或赢家的响应，确认就地文字随API改变且对应独立断言失败；不得被硬编码文案“修正”。注入null或BLOCKED时显示中性/阻断说明。
- [ ] 通过真实导出按钮生成A/B的CSV和PDF，沿用business-case导出校验机制与同一快照核对。导出不包含教程文本。
- [ ] 新测试截图输出到`output/contextual-example-tutorial/`，覆盖基础成本、三类推荐、供应边界、关闭后、移动端和错误状态，人工查看后记录检查结论。
- [ ] 运行下列命令，逐条记录实际结果和耗时；遇失败先定位，不自动freeze期望。

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_teaching_examples tests.test_workbench_page -v
node --test tests/frontend/teaching-guide.test.mjs tests/frontend/display-values.test.mjs tests/frontend/workbench-model.test.mjs
.\.venv\Scripts\python.exe -m unittest tests.e2e.test_teaching_guide tests.e2e.test_teaching_examples tests.e2e.test_workbench_flow -v
.\.venv\Scripts\python.exe tools/validation/business_case_runner.py --mode full --output output/contextual-example-tutorial/business-results.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node --test tests/frontend/*.test.mjs port-scope-rates.test.mjs port-identity-mapping.test.mjs
.\.venv\Scripts\python.exe -m compileall -q src
git diff --check
```

- [ ] 构建wheel，并检查新静态模块、模板随包发布：

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir output/contextual-example-tutorial/wheel
```

将wheel解包到本次唯一临时目录，设置独立进程PYTHONPATH并从项目外启动已安装包；请求两个模块、工作台与说明页应为200。不要使用源码目录作为回退，否则无法证明包完整。

- [ ] 记录reference_production_imports为空、差异数、请求数、断言数、CSV/PDF次数、浏览器检查次数及未覆盖面，不用历史数量代替。
- [ ] 审查git diff，确认没有修改冻结输入/期望、公式、请求/导出合同及无关文件。
- [ ] 写`docs/validation/contextual-example-tutorial-report.md`，明确自动验证、仅内部验证、失败、未覆盖、范围外和真实业务验收未完成。

## 2. 新手验收与人工检查

- [ ] 开发者使用键盘和移动端完成加载、阅读、关闭、查看说明和导出；这一步仅算内部检查。
- [ ] 按规格第8.2节安排至少3名新用户，记录是否能无口头帮助找到输入/计算/导出，解释三类推荐和限制。
- [ ] 不向受试者布置改条件练习，不用“点过全部提示”作为会用产品的证据。
- [ ] 未安排真人试用就标记待验证；不能以浏览器自动测试代替新手验收。
- [ ] 发现障碍优先调整入口、术语与结果关联，避免不断添加说明文字。

## 3. 覆盖与评审检查点

| 需求/验收 | 实施任务 |
|---|---|
| R01-R04、R07：两例、自动算、画面就地框选与业务含义 | Tasks 2-4 |
| R05-R06：无练习、无强制步骤 | Tasks 2、5、浏览器与模板否定断言 |
| R08、R10：开关、修改失效 | Tasks 1、3、4 |
| R09：独立依据 | Task 6 |
| R11：实际使用清单与可用性 | Task 5、人工验收 |
| R12：先文档后开发 | 文档状态及实施前检查 |
| V01-V05：真实请求、计算、文案与独立值 | Tasks 2、4、6 |
| V06-V09：重绘、异常、状态与无任务负担 | Tasks 1、3-5 |
| V10-V12：响应式、框选及可访问性 | Task 3、Task 6截图与键盘检查 |
| V13-V14：说明页、legacy、模块降级、打包 | Tasks 4-6 |
| V15-V16：故障注入与导出 | Task 6 |

评审检查点：

1. Task 1完成：状态事件与迟到响应隔离。
2. Task 2完成：与独立案例对应的教学内容、动态数据来源。
3. Tasks 3-4完成：桌面/移动画面、无强制步骤、状态安全。
4. Task 5完成：新手能找到真实输入与计算入口，旧练习文案已撤下。
5. Task 6完成：以本次实际证据填写报告，再区分真人验收状态。

## 4. 文档自审与交付边界

- 本规格在旧示例加载功能之上增量设计，未宣称已实现框选。
- 取消教学练习不删除原有修改功能或`B-hvo-supply0`测试。
- 接口、状态、定位属性在规格和计划中一致。
- 所有结果说明来自本次有效快照，不硬编码产品答案。
- 计划中的测试步骤全部保持未勾选；文档审阅不等于功能验收。
- 用户审阅后另行下达实施指令。本轮不执行计划、不提交代码、不启动新服务。
