"""Generate the README diagrams as fixed-layout SVG files."""

from __future__ import annotations

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "diagrams"

FONT = "Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif"
BG = "#F4F6F7"
INK = "#1F2933"
MUTED = "#66717C"
LINE = "#D4DADF"
WHITE = "#FFFFFF"
BLUE = "#3E6F98"
GREEN = "#4E7B63"
GOLD = "#B47B32"
PLUM = "#7A5F8E"
TEAL = "#347C7B"
RED = "#B05B5B"


def svg_text(
    x: float,
    y: float,
    lines: str | list[str],
    *,
    size: int = 16,
    weight: int = 400,
    color: str = INK,
    anchor: str = "middle",
    line_height: int | None = None,
) -> str:
    values = [lines] if isinstance(lines, str) else list(lines)
    line_height = line_height or max(20, round(size * 1.42))
    if anchor == "middle":
        first_y = y - (len(values) - 1) * line_height / 2
    elif anchor == "end":
        first_y = y - (len(values) - 1) * line_height
    else:
        first_y = y
    spans = "".join(
        f'<tspan x="{x}" y="{first_y + index * line_height}">{escape(value)}</tspan>'
        for index, value in enumerate(values)
    )
    return (
        f'<text x="{x}" y="{first_y}" text-anchor="{anchor}" '
        f'font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}">{spans}</text>'
    )


def card(
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    body: list[str],
    accent: str,
    *,
    number: str | None = None,
    fill: str = WHITE,
) -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" '
        f'fill="{fill}" stroke="{LINE}" filter="url(#card-shadow)"/>',
        f'<rect x="{x}" y="{y}" width="{width}" height="5" rx="2.5" fill="{accent}"/>',
    ]
    title_x = x + width / 2
    if number:
        parts.extend(
            [
                f'<circle cx="{x + 34}" cy="{y + 38}" r="17" fill="{accent}"/>',
                svg_text(x + 34, y + 38, number, size=15, weight=700, color=WHITE),
                svg_text(
                    x + 64,
                    y + 38,
                    title,
                    size=20,
                    weight=700,
                    color=INK,
                    anchor="start",
                ),
            ]
        )
    else:
        parts.append(svg_text(title_x, y + 39, title, size=20, weight=700, color=INK))
    body_y = y + (85 if number else max(72, height * 0.62))
    parts.append(svg_text(title_x, body_y, body, size=16, color=MUTED, line_height=23))
    return "".join(parts)


def arrow(
    path: str,
    *,
    color: str = "#84919B",
    width: int = 2,
    dashed: bool = False,
    marker: str = "arrow",
) -> str:
    dash = ' stroke-dasharray="6 6"' if dashed else ""
    return (
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round"{dash} '
        f'marker-end="url(#{marker})"/>'
    )


def straight_arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = "#84919B",
    dashed: bool = False,
) -> str:
    return arrow(f"M {x1} {y1} L {x2} {y2}", color=color, dashed=dashed)


def chip(x: float, y: float, width: float, text: str, accent: str) -> str:
    return "".join(
        [
            f'<rect x="{x}" y="{y}" width="{width}" height="48" rx="8" '
            f'fill="{WHITE}" stroke="{LINE}"/>',
            f'<rect x="{x}" y="{y}" width="5" height="48" rx="2.5" fill="{accent}"/>',
            svg_text(x + width / 2 + 2, y + 24, text, size=16, weight=600, color=INK),
        ]
    )


def document(
    width: int,
    height: int,
    parts: list[str],
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
  <filter id="card-shadow" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#1F2933" flood-opacity="0.10"/>
  </filter>
  <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#84919B"/>
  </marker>
  <marker id="arrow-gold" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="#B47B32"/>
  </marker>
</defs>
<rect width="{width}" height="{height}" fill="{BG}"/>
{''.join(parts)}
</svg>
"""


def build_product_overview() -> str:
    parts = [
        svg_text(56, 50, "产品全景", size=32, weight=700, anchor="start"),
        svg_text(
            56,
            84,
            "从一条航段的燃料问题，到可比较、可复核的航次级决策结果",
            size=16,
            color=MUTED,
            anchor="start",
        ),
        card(
            60,
            135,
            340,
            170,
            "业务问题",
            ["这条航段继续使用 B0，", "还是加入候选燃料或混兑方案？"],
            GOLD,
        ),
        card(
            430,
            135,
            340,
            170,
            "航次决策案例",
            [
                "报告年份 · 两个相邻有效 Port of Call",
                "基准燃料 · 候选燃料",
                "价格 · 币种 · 约束",
            ],
            BLUE,
        ),
        card(
            800,
            135,
            340,
            170,
            "统一计算",
            [
                "港口范围 + 燃料因子",
                "能源 · 排放 · EU ETS · FuelEU",
                "成本 · 约束",
            ],
            GREEN,
        ),
        card(
            800,
            405,
            340,
            170,
            "方案比较",
            [
                "B0 与候选方案",
                "成本 · 合规 · 约束状态",
                "目标比例 · 边界 · 切换点",
            ],
            PLUM,
        ),
        card(
            430,
            405,
            340,
            170,
            "条件式建议",
            [
                "成本优先 · 达标优先",
                "达到 GHGI 参考线",
                "最大合规改善",
            ],
            GOLD,
        ),
        card(
            60,
            405,
            340,
            170,
            "结果交付",
            [
                "决策工作台 · 依据",
                "CSV / PDF",
                "同一份成功计算结果",
            ],
            TEAL,
        ),
        straight_arrow(400, 220, 430, 220),
        straight_arrow(770, 220, 800, 220),
        straight_arrow(970, 305, 970, 405),
        straight_arrow(800, 490, 770, 490),
        straight_arrow(430, 490, 400, 490),
        f'<rect x="60" y="635" width="1080" height="90" rx="8" fill="#FBFCFC" stroke="{LINE}"/>',
        svg_text(82, 665, "所有结果共享同一边界", size=17, weight=700, anchor="start"),
        chip(82, 684, 320, "航次级法规口径估算", BLUE),
        chip(416, 684, 334, "FuelEU 指示性金额仅用于参考比较", GOLD),
        chip(764, 684, 356, "认证、船舶兼容性、供应和交付待确认", RED),
    ]
    return document(1200, 760, parts)


def build_user_journey() -> str:
    parts = [
        svg_text(56, 50, "一次航次决策：用户路径", size=32, weight=700, anchor="start"),
        svg_text(
            56,
            84,
            "六个步骤形成闭环，条件变化后可以随时回到候选方案重新计算",
            size=16,
            color=MUTED,
            anchor="start",
        ),
        card(
            60,
            130,
            340,
            170,
            "建立航次案例",
            ["报告年份 · 两个相邻有效港口", "基准燃料 · 用量 · 价格"],
            BLUE,
            number="1",
        ),
        card(
            430,
            130,
            340,
            170,
            "添加候选与约束",
            ["候选燃料 · 报价", "比例 · 供应量 · 预算"],
            BLUE,
            number="2",
        ),
        card(
            800,
            130,
            340,
            170,
            "运行计算",
            ["B0 与候选方案", "使用同一能源口径"],
            GREEN,
            number="3",
        ),
        card(
            800,
            410,
            340,
            170,
            "选择决策目标",
            ["成本优先", "达到 GHGI 参考线", "最大合规改善"],
            GOLD,
            number="4",
        ),
        card(
            430,
            410,
            340,
            170,
            "查看比较与边界",
            ["方案差异 · 排名", "临界点 · 执行状态"],
            PLUM,
            number="5",
        ),
        card(
            60,
            410,
            340,
            170,
            "复核与导出",
            ["检查依据和限制", "导出 CSV / PDF"],
            TEAL,
            number="6",
        ),
        straight_arrow(400, 215, 430, 215),
        straight_arrow(770, 215, 800, 215),
        straight_arrow(970, 300, 970, 410),
        straight_arrow(800, 495, 770, 495),
        straight_arrow(430, 495, 400, 495),
        arrow("M 230 580 L 230 650 L 600 650 L 600 300", dashed=True),
        svg_text(620, 640, "调整条件后重新计算", size=15, weight=600, color=GOLD, anchor="start"),
        f'<rect x="60" y="690" width="1080" height="65" rx="8" fill="#FBFCFC" stroke="{LINE}"/>',
        svg_text(
            600,
            723,
            "每个结果都保留：航次级估算 · 执行条件待确认 · 依据可追溯",
            size=16,
            weight=600,
            color=INK,
        ),
    ]
    return document(1200, 790, parts)


def lane(
    y: float,
    height: float,
    title: str,
    *,
    fill: str = "#EDF1F3",
) -> list[str]:
    return [
        f'<rect x="40" y="{y}" width="1120" height="{height}" rx="8" fill="{fill}"/>',
        svg_text(110, y + height / 2, title, size=18, weight=700, color=INK),
    ]


def build_calculation_flow() -> str:
    parts = [
        svg_text(56, 50, "计算流程与支撑关系", size=32, weight=700, anchor="start"),
        svg_text(
            56,
            84,
            "先统一计算基础，再逐个计算方案，最后比较、提示并形成可追溯结果",
            size=16,
            color=MUTED,
            anchor="start",
        ),
    ]

    parts.extend(lane(130, 170, "输入与基础", fill="#EEF3F6"))
    parts.extend(
        [
            card(
                220,
                150,
                220,
                130,
                "航次信息",
                ["年份 · 港口 · 基准燃料", "候选 · 价格 · 限制条件"],
                BLUE,
            ),
            card(
                460,
                150,
                220,
                130,
                "适用范围",
                ["判断航段适用的规则", "EU ETS / FuelEU 比例"],
                GREEN,
            ),
            card(
                700,
                150,
                220,
                130,
                "燃料数据",
                ["热值 · 排放参数", "资格与默认数据"],
                GOLD,
            ),
            card(
                940,
                150,
                220,
                130,
                "法规与数据来源",
                ["法规原文 · 来源索引", "核对记录 · 验证文件"],
                PLUM,
            ),
            arrow("M 1050 280 L 1050 305 L 570 305 L 570 280", dashed=True),
            arrow("M 1050 305 L 810 305 L 810 280", dashed=True),
            svg_text(885, 292, "提供规则和数据来源", size=14, weight=600, color=PLUM),
        ]
    )

    parts.extend(lane(330, 120, "统一口径", fill="#F4F7F5"))
    parts.extend(
        [
            card(
                220,
                350,
                940,
                80,
                "统一计算口径",
                ["同一年份、同一航段、同一能源需求、同一币种"],
                GREEN,
            ),
        ]
    )

    parts.extend(lane(480, 170, "逐方案计算", fill="#F6F7F8"))
    parts.extend(
        [
            card(
                220,
                505,
                280,
                120,
                "准备比较的方案",
                ["基准方案 · 用户指定比例", "关键比例和限制边界"],
                BLUE,
            ),
            card(
                530,
                505,
                280,
                120,
                "逐个方案计算",
                ["能源 · 燃料用量 · 排放", "EU ETS · FuelEU · 成本"],
                GREEN,
            ),
            card(
                840,
                505,
                280,
                120,
                "每个方案的结果",
                ["用量、成本、排放和合规结果", "计算保留完整精度"],
                TEAL,
            ),
            straight_arrow(500, 565, 530, 565),
            straight_arrow(810, 565, 840, 565),
        ]
    )

    parts.extend(lane(680, 170, "比较与提示", fill="#F8F5EF"))
    parts.extend(
        [
            card(
                840,
                705,
                280,
                120,
                "方案放在一起比较",
                ["相对基准方案的变化", "更低成本 · 更大改善"],
                PLUM,
            ),
            card(
                530,
                705,
                280,
                120,
                "价格临界点",
                ["燃料或 EUA 价格", "改变方案判断的临界值"],
                GOLD,
            ),
            card(
                220,
                705,
                280,
                120,
                "目标下的结果提示",
                ["成本优先 · 达标优先", "合规改善优先"],
                GOLD,
            ),
            straight_arrow(840, 765, 810, 765),
            straight_arrow(530, 765, 500, 765),
        ]
    )

    parts.extend(lane(880, 170, "结果交付", fill="#F1F4F8"))
    parts.extend(
        [
            card(
                220,
                905,
                280,
                120,
                "决策工作台",
                ["结论 · 方案比较", "边界与切换点"],
                TEAL,
            ),
            card(
                530,
                905,
                280,
                120,
                "CSV / PDF",
                ["同一次成功计算结果", "展示精度不改变计算值"],
                BLUE,
            ),
            card(
                840,
                905,
                280,
                120,
                "计算依据和问题说明",
                ["数据来源 · 规则版本", "阻断或警告原因"],
                PLUM,
            ),
        ]
    )

    parts.extend(
        [
            straight_arrow(600, 300, 600, 350),
            straight_arrow(600, 450, 600, 505),
            straight_arrow(980, 625, 980, 705),
            straight_arrow(360, 825, 360, 905),
            f'<rect x="40" y="1090" width="1120" height="60" rx="8" fill="#FBFCFC" stroke="{LINE}"/>',
            svg_text(
                600,
                1122,
                "所有结果都只用于航次级测算，执行条件待确认，数据来源和问题说明可追溯",
                size=16,
                weight=600,
                color=INK,
            ),
        ]
    )
    return document(1200, 1180, parts)


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
