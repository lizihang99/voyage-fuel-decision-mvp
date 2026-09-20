# 文档配图

本目录保存 README 使用的 SVG 配图。图表由仓库内的生成脚本统一排版，避免自动布局造成的交叉、错位和文字换行。

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe .\tools\diagrams\generate_diagrams.py
```

修改图表时，编辑 [generate_diagrams.py](../../tools/diagrams/generate_diagrams.py) 后重新运行脚本。不要直接编辑 SVG。

文件职责：

- `product-overview.svg`：产品定位和结果边界总览；
- `user-journey.svg`：一次航次决策的操作路径；
- `calculation-flow.svg`：计算链路、规则基础和交付关系。
