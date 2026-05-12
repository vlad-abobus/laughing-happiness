from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import aiohttp

from bot.config.settings import Settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True, slots=True)
class ModerationAIResult:
    violation: bool
    categories: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True, slots=True)
class ImageModerationResult:
    violation: bool
    categories: tuple[str, ...]
    reason: str | None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


class OpenRouterClient:
    """Universal OpenRouter-backed provider for chat and moderation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/laughing-happiness",
                    "X-Title": "laughing-happiness-bot",
                },
                timeout=aiohttp.ClientTimeout(total=120),
            )
        return self._session

    async def aclose(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def chat(
        self,
        user_text: str,
        *,
        system_prompt: str | None = None,
        extra_system: str | None = None,
        model: str | None = None,
        max_tokens: int = 768,
    ) -> str:
        model_id = model or self._settings.resolve_chat_model_id()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt or self._settings.ai_system_prompt}
        ]
        if extra_system:
            messages.append({"role": "system", "content": extra_system})
        messages.append({"role": "user", "content": user_text})

        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        data = await self._post_json(payload)
        return str(self._first_choice_text(data))

    async def moderate_text(self, text: str) -> ModerationAIResult:
        model_id = self._settings.resolve_chat_model_id()
        system = (
            "Ты модератор. Проанализируй сообщение пользователя на: спам, флуд-паттерны, "
            "токсичность, сексуальный/NSFW контент, подозрительные манипуляции (скам), "
            "экстремизм/угрозы. Ответь СТРОГО одним JSON без markdown:\n"
            '{"violation": true/false, "categories": ["spam"|"flood"|"toxicity"|"nsfw_text"|'
            '"suspicious"], "reason": "кратко"}\n'
            "Если сомнительно — лучше violation=false, categories пустой массив."
        )
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text[:6000]},
            ],
            "max_tokens": 200,
            "temperature": 0.2,
        }
        try:
            data = await self._post_json(payload)
            raw = self._first_choice_text(data)
            obj = _extract_json_object(raw)
            if not obj:
                return ModerationAIResult(False, tuple(), "unparseable_ai_output")
            violation = bool(obj.get("violation"))
            cats = obj.get("categories") or []
            if isinstance(cats, list):
                categories = tuple(str(c) for c in cats)
            else:
                categories = tuple()
            reason = obj.get("reason")
            return ModerationAIResult(violation, categories, str(reason) if reason else None)
        except Exception as e:
            logger.warning("moderate_text failed: %s", e)
            return ModerationAIResult(False, tuple(), str(e))

    async def moderate_image(
        self, image_bytes: bytes, mime: str = "image/jpeg"
    ) -> ImageModerationResult:
        model_id = self._settings.openrouter_vision_model.strip()
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        system = (
            "Ты модератор изображений. Определи: nsfw_image, shock_image (шок/насилие), "
            "forbidden_symbols (запрещённые символики/логотипы ненависти), suspicious_image. "
            "Ответь СТРОГО JSON без markdown:\n"
            '{"violation": true/false, "categories": ["nsfw_image"|"shock_image"|'
            '"forbidden_symbols"|"suspicious_image"], "reason": "кратко"}\n'
            "Если уверенности мало — violation=false."
        )
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Проанализируй изображение."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "max_tokens": 250,
            "temperature": 0.1,
        }
        try:
            data = await self._post_json(payload)
            raw = self._first_choice_text(data)
            obj = _extract_json_object(raw)
            if not obj:
                return ImageModerationResult(False, tuple(), "unparseable_ai_output")
            violation = bool(obj.get("violation"))
            cats = obj.get("categories") or []
            categories = tuple(str(c) for c in cats) if isinstance(cats, list) else tuple()
            reason = obj.get("reason")
            return ImageModerationResult(
                violation, categories, str(reason) if reason else None
            )
        except Exception as e:
            logger.warning("moderate_image failed: %s", e)
            return ImageModerationResult(False, tuple(), str(e))

    async def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = await self._get_session()
        async with session.post(OPENROUTER_URL, json=payload) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"OpenRouter HTTP {resp.status}: {body[:500]}")
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                raise RuntimeError("OpenRouter returned non-JSON") from e

    @staticmethod
    def _first_choice_text(data: dict[str, Any]) -> str:
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected OpenRouter response: {data!r}") from e
