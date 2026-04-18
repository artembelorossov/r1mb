from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from auction_bot.context import AppContext
from auction_bot.formatters import format_lot_caption
from auction_bot.keyboards import lot_keyboard

router = Router(name="admin")


def _ensure_admin(message: Message, app_ctx: AppContext) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in app_ctx.settings.admin_user_ids


def _parse_create_lot(text: str) -> tuple[int, str, str, int, int | None]:
    """
    Формат:
    /new_lot <номер>|<название>|<описание>|<начальная_цена>|[шаг_ставки]
    """
    payload = text.split(maxsplit=1)
    if len(payload) != 2:
        raise ValueError("Нет данных лота после команды")

    parts = [chunk.strip() for chunk in payload[1].split("|")]
    if len(parts) < 4:
        raise ValueError("Недостаточно полей, нужно 4 или 5")
    if len(parts) > 5:
        raise ValueError("Слишком много полей, нужно максимум 5")

    lot_number = int(parts[0])
    title = parts[1]
    description = parts[2]
    start_price = int(parts[3])
    bid_step = int(parts[4]) if len(parts) == 5 and parts[4] else None

    if lot_number < 1:
        raise ValueError("Номер лота должен быть > 0")
    if start_price < 0:
        raise ValueError("Начальная цена не может быть отрицательной")
    if bid_step is not None and bid_step < 1:
        raise ValueError("Шаг ставки должен быть > 0")
    if not title:
        raise ValueError("Название не может быть пустым")

    return lot_number, title, description, start_price, bid_step


@router.message(Command("new_lot"))
async def new_lot_handler(message: Message, app_ctx: AppContext) -> None:
    if not _ensure_admin(message=message, app_ctx=app_ctx):
        await message.answer("Только администратор может создавать лоты.")
        return

    if message.photo is None:
        await message.answer(
            "Отправьте команду с фото.\n"
            "Формат:\n"
            "/new_lot <номер>|<название>|<описание>|<начальная_цена>|[шаг_ставки]"
        )
        return

    try:
        lot_number, title, description, start_price, bid_step = _parse_create_lot(message.caption or "")
    except ValueError as error:
        await message.answer(
            "Не удалось распарсить лот.\n"
            "Формат:\n"
            "/new_lot <номер>|<название>|<описание>|<начальная_цена>|[шаг_ставки]\n\n"
            f"Ошибка: {error}"
        )
        return

    existing = await app_ctx.db.get_lot_by_number(lot_number)
    if existing is not None:
        await message.answer(f"Лот #{lot_number} уже существует.")
        return

    photo_file_id = message.photo[-1].file_id
    preview_lot_id = await app_ctx.db.create_lot(
        lot_number=lot_number,
        title=title,
        description=description,
        photo_file_id=photo_file_id,
        start_price=start_price,
        channel_message_id=None,
        bid_step=bid_step or app_ctx.settings.default_bid_step,
    )
    preview_lot = await app_ctx.db.get_lot_by_id(preview_lot_id)
    if preview_lot is None:
        await message.answer("Не удалось создать лот в базе.")
        return

    try:
        posted = await message.bot.send_photo(
            chat_id=app_ctx.settings.auction_channel_id,
            photo=photo_file_id,
            caption=format_lot_caption(preview_lot),
            parse_mode="HTML",
            reply_markup=lot_keyboard(lot=preview_lot, bot_username=app_ctx.bot_username),
        )
    except Exception as error:  # noqa: BLE001
        await message.answer(f"Не удалось отправить лот в канал: {error}")
        return

    await app_ctx.db.set_lot_channel_message_id(preview_lot.id, posted.message_id)

    lot = await app_ctx.db.get_lot_by_id(preview_lot.id)
    if lot is None:
        await message.answer("Лот создан, но не удалось перечитать запись.")
        return

    await app_ctx.sheets.export_lot_snapshot(lot)
    await message.answer(f"Лот #{lot.lot_number} опубликован в канале.")
