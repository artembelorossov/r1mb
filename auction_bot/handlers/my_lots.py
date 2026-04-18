from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from auction_bot.context import AppContext
from auction_bot.formatters import format_favorites_text
from auction_bot.keyboards import my_lots_menu_keyboard, my_lots_refresh_keyboard

router = Router(name="my_lots")


async def send_my_lots(message: Message, app_ctx: AppContext) -> None:
    user = message.from_user
    if user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    favorites = await app_ctx.db.get_favorite_lots_for_user(user.id)
    text = format_favorites_text(favorites=favorites, channel_id=app_ctx.settings.auction_channel_id)
    await message.answer(text, reply_markup=my_lots_refresh_keyboard())


@router.message(Command("my_lots"))
async def my_lots_command(message: Message, app_ctx: AppContext) -> None:
    await send_my_lots(message=message, app_ctx=app_ctx)


@router.callback_query(F.data == "my_lots:show")
async def my_lots_callback(callback: CallbackQuery, app_ctx: AppContext) -> None:
    user = callback.from_user
    favorites = await app_ctx.db.get_favorite_lots_for_user(user.id)
    text = format_favorites_text(favorites=favorites, channel_id=app_ctx.settings.auction_channel_id)

    if callback.message is None:
        await callback.answer("Откройте чат с ботом и нажмите /start.")
        return

    await callback.message.answer(text, reply_markup=my_lots_refresh_keyboard())
    await callback.answer("Список обновлен")


@router.message(F.text == "Мои лоты")
async def my_lots_text_button(message: Message) -> None:
    await message.answer("Нажмите кнопку ниже", reply_markup=my_lots_menu_keyboard())
