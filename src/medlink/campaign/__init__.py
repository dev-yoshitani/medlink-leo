"""Local multi-satellite management game; engineering APIs remain independent."""

from .models import CampaignState, DailyPlan, GameError
from .saves import load_campaign
from .service import apply_command, begin_day, claim_day, commit_day, preview_day

__all__ = [
    "CampaignState",
    "DailyPlan",
    "GameError",
    "apply_command",
    "begin_day",
    "claim_day",
    "commit_day",
    "load_campaign",
    "preview_day",
]
