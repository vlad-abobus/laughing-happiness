from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.context import AppContext
from bot.utils.parsing import parse_command_args

logger = logging.getLogger(__name__)

router = Router(name="ai")


@router.message(Command("ai"))
async def cmd_ai(message: Message, ctx: AppContext) -> None:
    if not message.from_user:
        return
    if await ctx.repo.is_globally_bot_blocked(message.from_user.id):
        await message.reply("Вы заблокированы в использовании AI-функций бота.")
        return

    _, args = parse_command_args(message.text or "")
    prompt = " ".join(args).strip()
    if not prompt:
        await message.reply("Напишите: <code>/ai ваш вопрос</code>", parse_mode="HTML")
        return

    try:
        answer = await ctx.ai.chat(prompt)
        await message.reply(answer[:4090])
    except Exception as e:
        logger.exception("ai command failed")
        await message.reply(f"Ошибка AI: {e}")


@router.message(F.text, F.reply_to_message)
async def ai_reply_chain(message: Message, ctx: AppContext, **data: Any) -> None:
    if not message.from_user or not message.text:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return
    if message.reply_to_message.from_user.id != ctx.bot_user_id:
        return
    if await ctx.repo.is_globally_bot_blocked(message.from_user.id):
        await message.reply("Вы заблокированы в использовании AI-функций бота.")
        return

    me = await message.bot.get_me()
    if message.reply_to_message.from_user.id != me.id:
        return

    bot_text = message.reply_to_message.text or message.reply_to_message.caption or "[media]"
    user_text = message.text
    user_first_name = message.from_user.first_name or "user"
    extra = f'Ответ на ваш текст от {user_first_name}: "{bot_text}", далее сообщение пользователя: {user_text}'

    try:
        answer = await ctx.ai.chat(user_text, extra_system=extra)
        await message.reply(answer[:4090])
    except Exception as e:
        logger.exception("ai reply failed")
        await message.reply(f"Ошибка AI: {e}")
