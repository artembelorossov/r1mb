from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from auction_bot.context import AppContext
from auction_bot.keyboards import my_lots_menu_keyboard

router = Router(name="common")


@router.message(CommandStart())
async def start_deeplink_handler(
    message: Message,
    command: CommandObject,
    app_ctx: AppContext,
) -> None:
    payload = command.args or ""
    if payload == "my_lots":
        from auction_bot.handlers.my_lots import send_my_lots  # local import to avoid cycle

        await send_my_lots(message=message, app_ctx=app_ctx)
        return

    text = (
        "Привет! Я бот аукциона.\n\n"
        "В канале можно делать ставки и ставить ❤️ на интересные лоты.\n"
        "Здесь можно открыть раздел «Мои лоты»."
    )
    await message.answer(text, reply_markup=my_lots_menu_keyboard())
