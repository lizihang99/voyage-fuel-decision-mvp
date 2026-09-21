"""Generate the README diagrams as fixed-layout, accessible SVG files."""

from __future__ import annotations

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "diagrams"

FONT = "Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif"
BG = "#F4F6F7"
INK = "#1F2933"
MUTED = "#52616C"
LINE = "#D4DADF"
WHITE = "#FFFFFF"
BLUE = "#3E6F98"
GREEN = "#4E7B63"
GOLD = "#956524"
PLUM = "#7A5F8E"
TEAL = "#347C7B"


def svg_text(
    x: float,
    y: float,
    lines: str | list[str],
    *,
    size: int = 18,
    weight: int = 400,
    color: str = INK,
    anchor: str = "middle",
    line_height: int = 27,
) -> str:
    values = [lines] if isinstance(lines, str) else list(lines)
    spans = "".join(
        f'<tspan x="{x}" y="{y + index * line_height}">{escape(value)}</tspan>'
        for index, value in enumerate(values)
    )
    return (
        f'<text text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{color}">{spans}</text>'
    )


def card(
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    body: list[str],
    accent: str,
) -> str:
    return "".join([
        f'<g data-card="{escape(title, quote=True)}">',
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" '
        f'fill="{WHITE}" stroke="{LINE}"/>',
        f'<rect x="{x}" y="{y}" width="{width}" height="5" rx="2" fill="{accent}"/>',
        svg_text(x + width / 2, y + 39, title, size=22, weight=700),
        svg_text(x + width / 2, y + 77, body, color=MUTED),
        "</g>",
    ])


def arrow(path: str, *, dashed: bool = False) -> str:
    dash = ' stroke-dasharray="6 6"' if dashed else ""
    return (
        f'<path data-connector="{"support" if dashed else "flow"}" d="{path}" '
        f'fill="none" stroke="#84919B" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"{dash} '
        f'marker-end="url(#arrow)"/>'
    )


def header(title: str, subtitle: str) -> list[str]:
    return [
        svg_text(40, 48, title, size=30, weight=700, anchor="start"),
        svg_text(40, 84, subtitle, color=MUTED, anchor="start"),
    ]


def footer(y: float, text: str) -> list[str]:
    return [
        f'<path d="M 40 {y} H 960" stroke="{LINE}"/>',
        svg_text(500, y + 34, text, size=17, color=MUTED),
    ]


def document(height: int, title: str, description: str, parts: list[str]) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title description">
<title id="title">{escape(title)}</title>
<desc id="description">{escape(description)}</desc>
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#84919B"/>
  </marker>
</defs>
<rect width="1000" height="{height}" fill="{BG}"/>
{''.join(parts)}
</svg>
"""


def build_product_overview() -> str:
    parts = header("产品全景", "同一航段换用燃料：多花多少钱、改善多少、哪些条件仍需确认？")
    parts.extend([
        card(40, 125, 280, 160, "业务问题", [
            "继续使用基准燃料（B0），",
            "还是换用或混兑候选燃料？",
        ], GOLD),
        card(360, 125, 280, 160, "建立航次案例", [
            "年份 · 两个相邻有效挂靠港",
            "基准燃料 · 候选报价",
            "价格 · 币种 · 限制条件",
        ], BLUE),
        card(680, 125, 280, 160, "同一能源需求下计算", [
            "燃料用量 · 排放",
            "EU ETS 配额成本",
            "FuelEU 强度与合规余额",
        ], GREEN),
        card(680, 355, 280, 165, "方案比较", [
            "各候选分别与基准比较",
            "成本变化 · 合规改善",
            "预算 · 供应 · 混兑比例限制",
        ], PLUM),
        card(360, 355, 280, 165, "按目标给出建议", [
            "模型成本最低",
            "达到参考线的最低成本",
            "报告方案内最大合规改善",
        ], GOLD),
        card(40, 355, 280, 165, "复核与交付", [
            "工作台查看结论与依据",
            "CSV / PDF 导出",
            "共享同一次计算结果",
        ], TEAL),
        arrow("M 320 205 H 360"),
        arrow("M 640 205 H 680"),
        arrow("M 820 285 V 355"),
        arrow("M 680 437 H 640"),
        arrow("M 360 437 H 320"),
        svg_text(500, 565, "参考线指 FuelEU 温室气体强度（GHGI）目标，不代表年度合规已完成。",
                 size=17, color=MUTED),
    ])
    parts.extend(footer(590, "航次级估算 · FuelEU 金额单列参考 · 认证、兼容性、供应与交付待确认"))
    return document(655, "产品全景", "业务问题、案例输入、计算、比较、三类建议和结果交付。", parts)


def build_user_journey() -> str:
    parts = header("一次航次决策：用户路径", "从自己的条件或合成示例开始，两种入口共用计算与导出流程。")
    parts.extend([
        card(40, 125, 430, 155, "自行填写", [
            "确认航段，填写基准燃料与用量",
            "按需添加候选报价、供应与预算",
            "点击计算；没有候选也可只算基准",
        ], BLUE),
        card(530, 125, 430, 155, "试用示例（合成）", [
            "基础计算 / 多燃料比较",
            "自动填入示例条件并计算",
            "不代表真实报价、供应或认证",
        ], TEAL),
        arrow("M 255 280 V 315 H 180 V 365"),
        arrow("M 745 280 V 315 H 180"),
        card(40, 365, 280, 160, "查看计算结果", [
            "模型成本 · 排放强度",
            "合规盈余或缺口",
            "示例解释与结果相邻",
        ], GREEN),
        card(360, 365, 280, 160, "按目标比较方案", [
            "成本 / 参考线 / 合规改善",
            "查看推荐，也可手动看方案",
            "仅有基准时查看基准结果",
        ], GOLD),
        card(680, 365, 280, 160, "复核与导出", [
            "检查来源、警告与限制",
            "导出 CSV / PDF",
            "执行条件仍需人工确认",
        ], PLUM),
        arrow("M 320 445 H 360"),
        arrow("M 640 445 H 680"),
        arrow("M 500 525 V 580 H 20 V 203 H 40", dashed=True),
        svg_text(275, 570, "修改输入后，旧结果与导出入口失效", size=17, color=GOLD),
        svg_text(500, 632, "示例可关闭“显示指引”；修改示例输入后撤下专属解释，需重新计算。",
                 size=17, color=MUTED),
    ])
    parts.extend(footer(659, "切换查看方案不改变输入；修改输入才需要重新计算。"))
    return document(722, "用户路径", "自行填写或加载合成示例，查看计算结果、比较方案并复核导出；修改输入后重新计算。", parts)


def build_calculation_flow() -> str:
    parts = header("计算流程与支撑关系", "主线看结果如何形成；右侧看计算依赖的规则与数据。")
    parts.extend([
        card(40, 125, 620, 130, "1  输入与统一口径", [
            "同一年份、同一航段、同一能源需求",
            "基准燃料 · 候选报价 · 供应 / 预算 / 比例限制",
        ], BLUE),
        card(40, 300, 620, 185, "2  逐方案计算", [
            "各候选分别计算，不把多个候选同时混兑",
            "计算燃料用量、排放与合规结果",
            "模型成本 = 燃料成本 + EU ETS 配额成本",
            "FuelEU 指示性金额以欧元单列，不计入模型成本或预算",
        ], GREEN),
        card(40, 530, 620, 130, "3  比较与条件式建议", [
            "按成本、GHGI 参考线和合规改善目标比较",
            "同时分析供应限制、所需混兑比例及价格变化的影响",
        ], GOLD),
        card(40, 705, 620, 130, "4  展示与导出", [
            "工作台与 CSV / PDF 使用同一次计算结果",
            "保留数据来源、规则版本和问题说明",
        ], TEAL),
        arrow("M 350 255 V 300"),
        arrow("M 350 485 V 530"),
        arrow("M 350 660 V 705"),
        card(720, 300, 240, 185, "规则与数据支撑", [
            "港口身份与适用比例",
            "燃料热值与排放参数",
            "燃料资格与来源版本",
            "法规来源与核对记录",
        ], PLUM),
        arrow("M 720 392 H 660", dashed=True),
        svg_text(720, 157, "共同前提", size=20, weight=700, color=BLUE, anchor="start"),
        svg_text(720, 194, [
            "输入价格和预算",
            "使用同一币种；",
            "系统不自动换汇。",
        ], color=MUTED, anchor="start"),
        svg_text(720, 566, "怎样理解比较？", size=20, weight=700, color=GOLD, anchor="start"),
        svg_text(720, 603, [
            "成本最低、达到参考线、",
            "改善最大，可能对应",
            "不同方案。",
        ], color=MUTED, anchor="start"),
        svg_text(720, 741, "说明与引导", size=20, weight=700, color=TEAL, anchor="start"),
        svg_text(720, 778, [
            "示例指引解释已有结果，",
            "不另设计算链路。",
        ], color=MUTED, anchor="start"),
    ])
    parts.extend(footer(865, "实线：结果形成主线 · 虚线：规则与数据支撑 · 所有结果均为航次级估算"))
    return document(930, "计算流程与支撑关系", "输入、逐方案计算、比较与建议、展示与导出构成主线；规则与数据从侧面支撑计算，不表示具体代码调用顺序。", parts)


def write(name: str, content: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(content, encoding="utf-8")


def main() -> None:
    write("product-overview.svg", build_product_overview())
    write("user-journey.svg", build_user_journey())
    write("calculation-flow.svg", build_calculation_flow())
    print("Generated product-overview.svg, user-journey.svg, and calculation-flow.svg")


if __name__ == "__main__":
    main()
