# 文档配图

本目录保存 README 使用的 SVG 配图。图表由仓库内的生成脚本统一排版，避免自动布局造成的交叉、错位和文字换行。

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe .\tools\diagrams\generate_diagrams.py
```

修改图表时，编辑 [generate_diagrams.py](../../tools/diagrams/generate_diagrams.py) 后重新运行脚本。不要直接编辑 SVG。

文件职责：

- `product-overview.svg`：产品定位和结果边界总览；
- `user-journey.svg`：自行填写与合成示例两个入口，以及修改输入后的重新计算路径；
- `calculation-flow.svg`：四步计算主线与侧面的规则数据支撑，不表示具体代码调用顺序。

图中统一使用“模型成本最低、达到参考线的最低成本、最大合规改善”三类目标；模型成本不含 FuelEU 指示性金额。更新后须核对 README 图注，并检查 SVG 文字是否越界、连线是否穿过文字。
