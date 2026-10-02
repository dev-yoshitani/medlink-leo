"""Versioned game rules; these are synthetic gameplay settings, not measurements."""

from typing import TypedDict


class SatelliteSettings(TypedDict):
    name: str
    cost: int
    upkeep: int
    bandwidth: int
    power: int
    description: str


class OrbitSettings(TypedDict):
    name: str
    altitude_km: int
    inclination: int
    phase_offset: int
    node_offset: int
    description: str


class StationSettings(TypedDict):
    name: str
    lat: float
    lon: float
    delay: int
    cost: int
    chapter: int
    x: int
    y: int


class ResearchSettings(TypedDict):
    name: str
    effects: list[str]


CONTENT_VERSION = 1
HORIZON = 6 * 3600
STEP = 10
SATELLITE_TYPES: dict[str, SatelliteSettings] = {
    "small": {
        "name": "小型通信衛星",
        "cost": 800,
        "upkeep": 20,
        "bandwidth": 1_000_000,
        "power": 30,
        "description": "少量の定期便を安く運ぶ",
    },
    "bulk": {
        "name": "大容量通信衛星",
        "cost": 1600,
        "upkeep": 35,
        "bandwidth": 3_000_000,
        "power": 30,
        "description": "大きな画像やまとめ便に",
    },
    "power": {
        "name": "高出力通信衛星",
        "cost": 3000,
        "upkeep": 60,
        "bandwidth": 1_000_000,
        "power": 36,
        "description": "遠い通過や通信条件の悪化に強い",
    },
}
# Phase and node angles are fictional launch plans. See flight.py for the model.
ORBIT_PLANS: dict[str, OrbitSettings] = {
    "early": {
        "name": "朝の便",
        "altitude_km": 550,
        "inclination": 53,
        "phase_offset": 0,
        "node_offset": 0,
        "description": "最初の通信機会を厚くする",
    },
    "relay": {
        "name": "補完の便",
        "altitude_km": 550,
        "inclination": 53,
        "phase_offset": 180,
        "node_offset": 25,
        "description": "朝の便の後に通信機会を作る",
    },
    "wide": {
        "name": "広域の便",
        "altitude_km": 650,
        "inclination": 70,
        "phase_offset": 90,
        "node_offset": -30,
        "description": "違う角度から地域をつなぐ",
    },
}
# Coordinates for the three added sites are illustrative game locations.
STATIONS: dict[str, StationSettings] = {
    "gs-sapporo": {
        "name": "札幌",
        "lat": 43.0618,
        "lon": 141.3545,
        "delay": 45,
        "cost": 0,
        "chapter": 1,
        "x": 740,
        "y": 150,
    },
    "gs-seoul": {
        "name": "ソウル",
        "lat": 37.5665,
        "lon": 126.978,
        "delay": 180,
        "cost": 350,
        "chapter": 2,
        "x": 280,
        "y": 310,
    },
    "gs-tokyo": {
        "name": "東京",
        "lat": 35.6895,
        "lon": 139.6917,
        "delay": 5,
        "cost": 650,
        "chapter": 2,
        "x": 670,
        "y": 350,
    },
    "gs-north": {
        "name": "北の島",
        "lat": 47,
        "lon": 145,
        "delay": 80,
        "cost": 800,
        "chapter": 3,
        "x": 860,
        "y": 80,
    },
    "gs-west": {
        "name": "西の港",
        "lat": 33,
        "lon": 130,
        "delay": 20,
        "cost": 950,
        "chapter": 4,
        "x": 400,
        "y": 450,
    },
    "gs-south": {
        "name": "南の島",
        "lat": 26,
        "lon": 128,
        "delay": 100,
        "cost": 1100,
        "chapter": 4,
        "x": 220,
        "y": 550,
    },
}
RESEARCH: dict[str, ResearchSettings] = {
    "receive": {
        "name": "受信設備",
        "effects": ["受信設備を2台へ", "受信設備を3台へ", "アンテナLv.5を開放"],
    },
    "backhaul": {
        "name": "地上回線",
        "effects": ["回線Lv.3を開放", "回線Lv.4を開放", "回線Lv.5を開放"],
    },
    "operations": {
        "name": "運用",
        "effects": ["同時受注4件", "同時受注5件・継続契約", "同時受注6件"],
    },
}
CHAPTER_NAMES = ("小さな通信センター", "ふたつの衛星", "地域をつなぐ", "広域通信網", "自由な運営")
KINDS = ("regular", "urgent", "bulk", "bundle", "ongoing", "special")
KIND_NAMES = dict(
    zip(KINDS, ("定期便", "急ぎの便", "大容量便", "まとめ便", "継続契約", "臨時依頼"), strict=True)
)
EVENTS = (
    ("demand", "依頼が増える日", "臨時依頼の荷物と達成件数が増え、ボーナスも100 C増えます。"),
    ("backhaul", "地上回線の混雑", "札幌の地上回線は到着まで120秒余計にかかります。"),
    ("maintenance", "受信設備の点検", "札幌の最初の通信機会は点検のため使えません。"),
    ("weather", "通信条件の悪化", "全局の通信損失が3 dB増えます。"),
)
