"""Japanese presentation labels for the bundled offline scenarios."""

from __future__ import annotations

from medlink.routing import RouteFailureReason, RouteResult

ROUTING_LABELS = {
    "next-contact": "次の通信機会を使う",
    "earliest-arrival": "病院への到着を早める",
    "deadline-aware": "期限内の到着を優先",
}
SCHEDULER_LABELS = {
    "fifo": "到着順（FIFO）",
    "priority": "優先度順（説明用）",
    "edf": "期限が近い順（EDF）",
}
PRIORITY_LABELS = {
    "CRITICAL": "最優先",
    "HIGH": "高",
    "NORMAL": "通常",
    "LOW": "低",
}
DATA_LABELS = {
    "synthetic_archive_batch": "保存記録",
    "synthetic_vital_sign_summary": "バイタル概要",
    "synthetic_waveform_segment": "波形データ",
    "synthetic_medical_image": "医療画像",
}
STATION_LABELS = {
    "gs-seoul": "ソウル",
    "gs-sapporo": "札幌",
    "gs-tokyo": "東京",
}
STATION_NAME_LABELS = {
    "Seoul Reference Ground Station": "ソウル",
    "Sapporo Reference Ground Station": "札幌",
    "Tokyo Reference Ground Station": "東京",
}
FAILURE_LABELS = {
    RouteFailureReason.NO_CONTACT: "通信機会なし",
    RouteFailureReason.INSUFFICIENT_CAPACITY: "通信容量不足",
    RouteFailureReason.DEADLINE_INFEASIBLE: "期限に間に合わない",
    RouteFailureReason.OUTSIDE_SIMULATION_HORIZON: "計算時間外",
}


def station_label(station_id: str | None, fallback: str | None = None) -> str:
    if station_id is None:
        return fallback or "—"
    return STATION_LABELS.get(station_id, fallback or station_id)


def station_name_label(name: str) -> str:
    return STATION_NAME_LABELS.get(name, name)


def outcome_label(result: RouteResult) -> str:
    if result.delivered:
        return "到着"
    return FAILURE_LABELS[result.failure_reason] if result.failure_reason else "未到着"


def route_explanation(result: RouteResult) -> str:
    """Explain the visible result without replacing the engine's detailed audit text."""
    if result.delivered:
        explanations = {
            "next-contact": "送信を最も早く始められる通信機会を選びました。",
            "earliest-arrival": (
                "送信と地上回線の遅延を含め、病院への到着が最も早い候補を選びました。"
            ),
            "deadline-aware": (
                "期限内に届く候補から、病院への到着が最も早いものを選びました。"
            ),
        }
        return explanations[result.strategy.value]
    explanations = {
        RouteFailureReason.NO_CONTACT: "このデータを送れる通信機会が残っていません。",
        RouteFailureReason.INSUFFICIENT_CAPACITY: (
            "通信機会はありますが、残りの容量では送り切れません。"
        ),
        RouteFailureReason.DEADLINE_INFEASIBLE: (
            "送れる経路はありますが、病院への到着は期限を過ぎます。"
        ),
        RouteFailureReason.OUTSIDE_SIMULATION_HORIZON: (
            "計算対象の時間内に病院へ届く候補がありません。"
        ),
    }
    return explanations.get(result.failure_reason, "病院への配送は完了していません。")
