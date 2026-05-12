from __future__ import annotations

from dataclasses import dataclass

from bot.ai.openrouter import OpenRouterClient
from bot.config.rules import CommunityRules
from bot.config.settings import Settings
from bot.database.repository import Repository
from bot.moderation.service import ModerationService
from bot.utils.admin_log import AdminActionLogger
from bot.utils.rate_limit import SlidingWindowRateLimiter


@dataclass(slots=True)
class AppContext:
    settings: Settings
    rules: CommunityRules
    repo: Repository
    ai: OpenRouterClient
    moderation: ModerationService
    rate_limiter: SlidingWindowRateLimiter
    admin_logger: AdminActionLogger
    bot_user_id: int
