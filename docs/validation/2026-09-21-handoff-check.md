# 交接前检查

日期：2026-09-21。检查对象：`5f491d8` 加本地 README、配图及相关测试改动；本轮未修改业务代码，未创建提交。

结论：下列本地技术检查通过，未发现阻断本地单用户试用交接的问题。该结论不代表生产部署、安全审计、真人新手试用或真实业务验收完成。

## 检查结果

| 检查 | 本轮结果 |
| --- | --- |
| Python 默认全量测试（含浏览器 E2E 与配图测试） | 292 通过，105 个子测试通过 |
| Node 港口及前端测试 | 51 通过 |
| `tools/validation/` 核验工具测试 | 122 通过，1,053 个子测试通过 |
| 独立业务案例全量核验 | 61/61 通过，412,517 个断言，0 差异；参考进程未导入生产模块 |
| 独立案例导出 | CSV、PDF 各 60 份通过核验 |
| 安装与依赖 | wheel 构建、独立 venv 安装通过；开发与独立环境 `pip check` 均通过 |
| 安装包完整性 | 35 个代码与资源文件逐字节匹配源码；全部静态资源通过实际 HTTP 请求核对 |
| 启动 | 从独立环境运行安装后的 `voyage-fuel-web.exe`，`/health` 返回 `{"status":"ok"}` |
| 安装后浏览器检查 | 5 组通过；工作台基础/比较示例、旧版基础示例；1440/390/320px 无页面横向溢出 |
| 文档 | README 的 13 个本地目标有效；图源与 SVG 一致；`git diff --check` 通过 |

浏览器检查实际执行：加载示例、核对请求与冻结案例一致、开关结果指引、下载并解析 CSV/PDF、新标签打开案例说明、修改输入后禁用导出并撤下专属说明、重新计算生成新快照。5 组均未捕获脚本异常或 API/静态资源错误响应，并检查了桌面和窄屏截图。

本轮使用的 8000 端口临时服务已在检查后正常关闭；正式试用按 README 启动。

## 复查入口

在仓库根目录、按 README 安装测试依赖后执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/frontend/*.test.mjs port-scope-rates.test.mjs port-identity-mapping.test.mjs
.\.venv\Scripts\python.exe -m pytest tools/validation -q
.\.venv\Scripts\python.exe tools/validation/business_case_runner.py --output output/handoff-final/business-results.json
```

本机证据位于 `output/handoff-final/`：`pytest.xml`、`validation-tools.xml`、`business-results.json`、`installed-smoke.json`、截图、导出文件与 `smoke_check.py`。该目录被 Git 忽略，不会随提交交付。安装包为 `dist/voyage_fuel-0.1.0-py3-none-any.whl`，SHA-256：

```text
50bed7c938abcff1ae1efe55626cbc8e624b5cf4d9263817f6532978e75c8175
```

## 交接保留项

- 测试出现 Starlette/httpx 和 AnyIO 接口弃用警告；本轮无失败，未为消除警告升级或替换项目依赖。独立安装验证不等于未来依赖版本均兼容，当前没有固定全部依赖版本的锁文件。
- 浏览器默认请求 `/favicon.ico` 返回 404，属于缺少站点图标；计算、页面资源及导出请求均正常。
- 基础示例仅有 B0，三类目标卡片会显示“暂无可用方案”，下方基准结果仍正常。新手是否误以为计算失败，应纳入真人试用；不应据此宣称新手可用性验收完成。
- 当前无账户权限、历史案例存储或生产多用户部署保证；导出快照仅保存在进程内存中，最多 32 份、有效期 30 分钟。
- 真实报价、燃料资格、兼容性、供应和交付仍需人工确认；航次级结果不能替代年度 FuelEU 结算或采购审批。
- README、三张图、生成脚本及相关测试仍有未提交改动。交接 Git 仓库前需将这些文件和本记录纳入确认后的提交；本轮没有自动提交或推送。
