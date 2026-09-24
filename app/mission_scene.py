"""Small vector scene for the offline routing mission UI."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

from medlink.routing import RouteResult

ASSET_DIR = Path(__file__).resolve().parent / "assets"
STATIONS = (
    ("gs-seoul", "SEOUL", 300),
    ("gs-sapporo", "SAPPORO", 600),
    ("gs-tokyo", "TOKYO", 900),
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
            "#67c9aa" if active else "#50718c" if station_id in candidate_stations else "#405267"
        )
        width = 5 if active else 2
        routes.append(
            f'<path d="M600 190 Q {x} 212 {x} 276" fill="none" '
            f'stroke="{stroke}" stroke-width="{width}" '
            f'stroke-dasharray="{0 if active else 7} {0 if active else 7}" />'
        )
        if active:
            routes.append(
                f'<path d="M{x} 370 Q {x + 70} 470 996 444" fill="none" '
                'stroke="#67c9aa" stroke-width="5" />'
            )
        stations.append(
            f'<circle cx="{x}" cy="321" r="72" fill="{stroke}" opacity=".08" />'
            + _image("ground_station", x - 57, 280, 114, 84)
            + f'<text x="{x}" y="389" text-anchor="middle" class="node-label">{label}</text>'
            + f'<text x="{x}" y="409" text-anchor="middle" class="node-sub">'
            + (
                "SELECTED ROUTE"
                if active
                else "CANDIDATE" if station_id in candidate_stations else "GROUND SITE"
            )
            + "</text>"
        )
    if selected:
        selected_label = next(label for station_id, label, _ in STATIONS if station_id == selected)
        status = f"{selected_label} ROUTE SELECTED"
    elif result:
        status = "NO ROUTE DELIVERED"
    else:
        status = "READY TO SIMULATE"
    packet = (
        "medical_packet_critical"
        if result and result.priority.name == "CRITICAL"
        else "medical_packet_normal"
    )
    packet_image = _image(packet, 1050, 70, 96, 72) if selected else ""
    packet_label = (
        '<text x="1098" y="159" text-anchor="middle" class="node-sub">SELECTED PAYLOAD</text>'
        if selected
        else ""
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 520"
        role="img" aria-label="{escape(status)}. Conceptual single-satellite network diagram.">
      <title>{escape(status)} — conceptual network diagram</title>
      <defs><style>
        .node-label {{font: 700 18px Arial,sans-serif; letter-spacing: 2px; fill: #e6edf2}}
        .node-sub {{font: 700 11px Arial,sans-serif; letter-spacing: 1.7px; fill: #a7bdd0}}
        .scene-text {{font: 700 13px Arial,sans-serif; letter-spacing: 2px; fill: #9bb5c6}}
      </style></defs>
      <rect width="1200" height="520" rx="24" fill="#0b1723"/>
      <path d="M0 379 Q600 217 1200 379v141H0Z" fill="#142d39"/>
      <path d="M0 379 Q600 217 1200 379" fill="none" stroke="#2d5362" stroke-width="2"/>
      <g fill="#5e839a" opacity=".7">
        <circle cx="93" cy="72" r="2"/><circle cx="209" cy="120" r="2"/>
        <circle cx="337" cy="69" r="1.5"/><circle cx="1002" cy="80" r="2"/>
        <circle cx="1083" cy="151" r="1.5"/><circle cx="784" cy="66" r="2"/>
      </g>
      <text x="40" y="41" class="scene-text">EAST ASIA / HISTORICAL ORBIT FIXTURE</text>
      <text x="1160" y="41" text-anchor="end" class="scene-text">{escape(status)}</text>
      {packet_label}
      <path d="M151 437 Q 270 234 600 190" fill="none" stroke="#54788d"
        stroke-width="2" stroke-dasharray="7 8"/>
      {''.join(routes)}
      {_image('satellite', 515, 80, 170, 127)}
      <text x="600" y="219" text-anchor="middle" class="node-label">LEO SATELLITE</text>
      <text x="600" y="239" text-anchor="middle" class="node-sub">SINGLE SPACECRAFT</text>
      {''.join(stations)}
      {_image('remote_clinic', 67, 380, 152, 114)}
      <text x="143" y="507" text-anchor="middle" class="node-sub">REMOTE CLINIC</text>
      {_image('hospital', 977, 380, 132, 108)}
      <text x="1043" y="507" text-anchor="middle" class="node-sub">HOSPITAL GATEWAY</text>
      {packet_image}
      <text x="259" y="466" class="node-sub">UPLINK ABSTRACTED</text>
    </svg>'''
    return svg
