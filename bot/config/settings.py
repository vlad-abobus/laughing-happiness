from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_AI_PROMPT = (
    "Ты вежливый и полезный ассистент. Отвечай кратко и по делу на русском, "
    "если пользователь пишет по-русски."
)


def _parse_admin_ids_csv(raw: str) -> frozenset[int]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return frozenset(int(p) for p in parts)


class Settings(BaseSettings):
    """Application configuration loaded from environment (.env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    openrouter_api_key: str = Field(validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field("deepseek-chat", validation_alias="OPENROUTER_MODEL")
    openrouter_vision_model: str = Field(
        "openai/gpt-4o-mini", validation_alias="OPENROUTER_VISION_MODEL"
    )
    admin_ids_csv: str = Field(validation_alias="ADMIN_IDS")

    database_path: Path = Field(Path("bot.db"), validation_alias="DATABASE_PATH")
    rules_json_path: Path = Field(Path("rules.json"), validation_alias="RULES_JSON_PATH")
    admin_log_path: Path = Field(
        Path("logs/admin_actions.log"), validation_alias="ADMIN_LOG_PATH"
    )

    ping_host: str = Field("0.0.0.0", validation_alias="PING_HOST")
    ping_port: int = Field(8080, validation_alias="PING_PORT")

    rate_limit_window_sec: int = Field(30, validation_alias="RATE_LIMIT_WINDOW_SEC")
    rate_limit_max_messages: int = Field(25, validation_alias="RATE_LIMIT_MAX_MESSAGES")

    ai_system_prompt: str = Field(_DEFAULT_AI_PROMPT, validation_alias="AI_SYSTEM_PROMPT")

    @field_validator("ai_system_prompt")
    @classmethod
    def _ai_prompt_non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        return v if v else _DEFAULT_AI_PROMPT

    @field_validator("database_path", "rules_json_path", "admin_log_path", mode="before")
    @classmethod
    def _coerce_path(cls, v: Any) -> Path:
        return Path(v)

    @property
    def admin_ids(self) -> frozenset[int]:
        return _parse_admin_ids_csv(self.admin_ids_csv)

    def resolve_chat_model_id(self) -> str:
        alias = self.openrouter_model.strip().lower()
        mapping: dict[str, str] = {
            "deepseek-chat": "deepseek/deepseek-chat",
            "gemini": "google/gemini-2.0-flash-001",
            "mistral": "mistralai/mistral-small-3.1-24b-instruct",
            "claude": "anthropic/claude-3.5-sonnet",
            "gpt": "openai/gpt-4o-mini",
            "openai/gpt": "openai/gpt-4o-mini",
        }
        if alias in mapping:
            return mapping[alias]
        if "/" in self.openrouter_model:
            return self.openrouter_model
        raise ValueError(
            f"Unknown OPENROUTER_MODEL alias: {self.openrouter_model!r}. "
            f"Use one of {sorted(mapping)} or a full OpenRouter model id."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def model_alias_help() -> str:
    return json.dumps(
        {
            "deepseek-chat": "deepseek/deepseek-chat",
            "gemini": "google/gemini-2.0-flash-001",
            "mistral": "mistralai/mistral-small-3.1-24b-instruct",
            "claude": "anthropic/claude-3.5-sonnet",
            "gpt": "openai/gpt-4o-mini",
        },
        ensure_ascii=False,
        indent=2,
    )
