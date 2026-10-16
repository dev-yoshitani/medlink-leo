"""Small vector scene for the offline routing mission UI."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

from medlink.routing import RouteResult

ASSET_DIR = Path(__file__).resolve().parent / "assets"
STATIONS = (
    ("gs-seoul", "ソウル", 300),
    ("gs-sapporo", "札幌", 600),
    ("gs-tokyo", "東京", 900),
)


@lru_cache(maxsize=8)
def _asset_uri(name: str) -> str:
    encoded = base64.b64encode((ASSET_DIR / f"{name}.svg").read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _image(name: str, x: int, y: int, width: int, height: int) -> str:
    return (
        f'<image href="{_asset_uri(name)}" x="{x}" y="{y}" '
        f'width="{width}" height="{height}" />'
    )


def build_scene(result: RouteResult | None = None) -> str:
    """Return a self-contained SVG; colors encode a selected route only."""
    selected = result.selected_ground_station if result and result.delivered else None
    candidate_stations = (
        {candidate.ground_station_id for candidate in result.candidates} if result else set()
    )
    routes = []
    stations = []
    for station_id, label, x in STATIONS:
        active = station_id == selected
        stroke = (
            "#2f8374" if active else "#8aa8a0" if station_id in candidate_stations else "#b3c2b8"
        )
        width = 5 if active else 2
        routes.append(
            f'<path d="M600 190 Q {x} 212 {x} 276" fill="none" '
            f'stroke="{stroke}" stroke-width="{width}" '
            f'stroke-dasharray="{0 if active else 7} {0 if active else 7}" />'
        )
        if active:
            routes.append(
                f'<path d="M{x} 418 Q {x + 70} 470 996 444" fill="none" '
                'stroke="#2f8374" stroke-width="5" />'
            )
        stations.append(
            f'<circle cx="{x}" cy="321" r="72" fill="{stroke}" opacity=".12" />'
            + _image("ground_station", x - 57, 280, 114, 84)
            + f'<text x="{x}" y="389" text-anchor="middle" class="node-label">{label}</text>'
            + f'<text x="{x}" y="409" text-anchor="middle" class="node-sub">'
            + (
                "選択した地上局"
                if active
                else "候補" if station_id in candidate_stations else "地上局"
            )
            + "</text>"
        )
    if selected:
        selected_label = next(label for station_id, label, _ in STATIONS if station_id == selected)
        status = f"{selected_label}を経由"
    elif result:
        status = "病院まで届かず"
    else:
        status = "開始前"
    packet = (
        "medical_packet_critical"
        if result and result.priority.name == "CRITICAL"
        else "medical_packet_normal"
    )
    packet_image = _image(packet, 1050, 70, 96, 72) if selected else ""
    packet_label = (
        '<text x="1098" y="159" text-anchor="middle" class="node-sub">選択中のデータ</text>'
        if selected
        else ""
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 520"
        role="img" aria-label="{escape(status)}。衛星通信経路の模式図。">
      <title>{escape(status)} — 衛星通信経路の模式図</title>
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M40 0H0V40" fill="none" stroke="#dfe6dc" stroke-width="1"/>
        </pattern>
        <style>
          .node-label {{font: 700 19px 'Yu Gothic','Noto Sans JP',sans-serif; fill: #253f43}}
          .node-sub {{font: 600 13px 'Yu Gothic','Noto Sans JP',sans-serif; fill: #4d6c6b}}
          .scene-text {{font: 700 15px 'Yu Gothic','Noto Sans JP',sans-serif; fill: #45665f}}
        </style>
      </defs>
      <rect width="1200" height="520" rx="14" fill="#f4f3e9"/>
      <rect width="1200" height="520" rx="14" fill="url(#grid)"/>
      <path d="M0 379 Q600 217 1200 379v141H0Z" fill="#dbe9dc"/>
      <path d="M0 379 Q600 217 1200 379" fill="none" stroke="#7ba795" stroke-width="3"/>
      <text x="40" y="41" class="scene-text">保存済みの軌道による通信経路</text>
      <text x="1160" y="41" text-anchor="end" class="scene-text">{escape(status)}</text>
      {packet_label}
      <path d="M151 437 Q 270 234 600 190" fill="none" stroke="#8da99d"
        stroke-width="2" stroke-dasharray="7 8"/>
      {''.join(routes)}
      {_image('satellite', 515, 80, 170, 127)}
      <text x="600" y="219" text-anchor="middle" class="node-label">低軌道衛星</text>
      <text x="600" y="239" text-anchor="middle" class="node-sub">衛星 1機</text>
      {''.join(stations)}
      {_image('remote_clinic', 67, 380, 152, 114)}
      <text x="143" y="507" text-anchor="middle" class="node-sub">遠隔地の診療所</text>
      {_image('hospital', 977, 380, 132, 108)}
      <text x="1043" y="507" text-anchor="middle" class="node-sub">病院側の中継点</text>
      {packet_image}
      <text x="259" y="466" class="node-sub">送信区間は省略</text>
    </svg>'''
    return svg
