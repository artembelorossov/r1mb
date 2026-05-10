from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import InputMediaPhoto, Message

from auction_bot.context import AppContext
from auction_bot.formatters import format_lot_caption
from auction_bot.keyboards import lot_keyboard

router = Router(name="admin")
NEW_LOT_FORMAT_HINT = "/new_lot &lt;номер&gt;|&lt;название&gt;|&lt;описание&gt;|&lt;начальная_цена&gt;|[шаг_ставки]"
MAX_LOT_PHOTOS = 10
MEDIA_GROUP_DEBOUNCE_SECONDS = 1.2


@dataclass(slots=True)
class PendingMediaGroupLot:
    photos_by_message_id: dict[int, str] = field(default_factory=dict)
    command_caption: str | None = None
    command_message: Message | None = None
    timer_task: asyncio.Task[None] | None = None


_PENDING_MEDIA_GROUP_LOTS: dict[str, PendingMediaGroupLot] = {}


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


async def _publish_lot(
    message: Message,
    app_ctx: AppContext,
    lot_number: int,
    title: str,
    description: str,
    start_price: int,
    bid_step: int | None,
    photo_file_ids: list[str],
) -> None:
    if not photo_file_ids:
        await message.answer("Не удалось получить фото лота.")
        return
    if len(photo_file_ids) > MAX_LOT_PHOTOS:
        await message.answer(f"Можно добавить максимум {MAX_LOT_PHOTOS} фото в одном лоте.")
        return

    existing = await app_ctx.db.get_lot_by_number(lot_number)
    if existing is not None:
        await message.answer(f"Лот #{lot_number} уже существует.")
        return

    preview_lot_id = await app_ctx.db.create_lot(
        lot_number=lot_number,
        title=title,
        description=description,
        photo_file_id=photo_file_ids[0],
        start_price=start_price,
        channel_message_id=None,
        bid_step=bid_step or app_ctx.settings.default_bid_step,
    )
    preview_lot = await app_ctx.db.get_lot_by_id(preview_lot_id)
    if preview_lot is None:
        await message.answer("Не удалось создать лот в базе.")
        return

    try:
        if len(photo_file_ids) == 1:
            posted_message = await message.bot.send_photo(
                chat_id=app_ctx.settings.auction_channel_id,
                photo=photo_file_ids[0],
                caption=format_lot_caption(preview_lot),
                parse_mode="HTML",
                reply_markup=lot_keyboard(lot=preview_lot, bot_username=app_ctx.bot_username),
            )
            channel_message_id = posted_message.message_id
        else:
            media: list[InputMediaPhoto] = []
            for index, file_id in enumerate(photo_file_ids):
                if index == 0:
                    media.append(InputMediaPhoto(media=file_id))
                else:
                    media.append(InputMediaPhoto(media=file_id))

            posted_messages = await message.bot.send_media_group(
                chat_id=app_ctx.settings.auction_channel_id,
                media=media,
            )
            if not posted_messages:
                await message.answer("Не удалось получить отправленные сообщения лота.")
                return
            channel_message_id = posted_messages[0].message_id
    except Exception as error:  # noqa: BLE001
        await message.answer(f"Не удалось отправить лот в канал: {error}")
        return

    await app_ctx.db.set_lot_channel_message_id(preview_lot.id, channel_message_id)

    lot = await app_ctx.db.get_lot_by_id(preview_lot.id)
    if lot is None:
        await message.answer("Лот создан, но не удалось перечитать запись.")
        return

    if len(photo_file_ids) > 1:
        try:
            await message.bot.edit_message_caption(
                chat_id=app_ctx.settings.auction_channel_id,
                message_id=channel_message_id,
                caption=format_lot_caption(lot),
                parse_mode="HTML",
                reply_markup=lot_keyboard(lot=lot, bot_username=app_ctx.bot_username),
            )
        except TelegramBadRequest as error:
            # Повторная попытка установки тех же данных не должна считаться фатальной.
            if "message is not modified" not in str(error).lower():
                await message.answer(
                    "Лот опубликован как альбом, но не удалось добавить кнопки.\n"
                    f"Ошибка: {error}"
                )
                return
        except Exception as error:  # noqa: BLE001
            await message.answer(
                "Лот опубликован как альбом, но не удалось добавить кнопки.\n"
                f"Ошибка: {error}"
            )
            return

    await app_ctx.sheets.export_lot_snapshot(lot)
    await message.answer(
        f"Лот #{lot.lot_number} опубликован в канале. "
        f"Фото: {len(photo_file_ids)}"
    )


async def _finalize_media_group_lot(media_group_id: str, app_ctx: AppContext) -> None:
    await asyncio.sleep(MEDIA_GROUP_DEBOUNCE_SECONDS)
    pending = _PENDING_MEDIA_GROUP_LOTS.pop(media_group_id, None)
    if pending is None or pending.command_message is None or pending.command_caption is None:
        return

    ordered_photo_ids = [
        file_id
        for _, file_id in sorted(
            pending.photos_by_message_id.items(),
            key=lambda item: item[0],
        )
    ]
    try:
        lot_number, title, description, start_price, bid_step = _parse_create_lot(
            pending.command_caption
        )
    except ValueError as error:
        await pending.command_message.answer(
            "Не удалось распарсить лот.\n"
            "Формат:\n"
            f"{NEW_LOT_FORMAT_HINT}\n\n"
            f"Ошибка: {error}"
        )
        return

    await _publish_lot(
        message=pending.command_message,
        app_ctx=app_ctx,
        lot_number=lot_number,
        title=title,
        description=description,
        start_price=start_price,
        bid_step=bid_step,
        photo_file_ids=ordered_photo_ids,
    )


def _collect_media_group_item(message: Message, app_ctx: AppContext) -> None:
    if message.photo is None or message.media_group_id is None:
        return

    media_group_id = message.media_group_id
    pending = _PENDING_MEDIA_GROUP_LOTS.get(media_group_id)
    if pending is None:
        pending = PendingMediaGroupLot()
        _PENDING_MEDIA_GROUP_LOTS[media_group_id] = pending

    pending.photos_by_message_id[message.message_id] = message.photo[-1].file_id

    caption = (message.caption or "").strip()
    if caption.startswith("/new_lot"):
        pending.command_caption = caption
        pending.command_message = message

    if pending.timer_task is not None and not pending.timer_task.done():
        pending.timer_task.cancel()
    pending.timer_task = asyncio.create_task(_finalize_media_group_lot(media_group_id, app_ctx))


@router.message(Command("new_lot"))
async def new_lot_handler(message: Message, app_ctx: AppContext) -> None:
    if not _ensure_admin(message=message, app_ctx=app_ctx):
        await message.answer("Только администратор может создавать лоты.")
        return

    if message.media_group_id is not None:
        # Первый элемент альбома с /new_lot может быть перехвачен этим хендлером.
        # Поэтому регистрируем его в буфере здесь, иначе лот не соберется.
        _collect_media_group_item(message=message, app_ctx=app_ctx)
        return

    if message.photo is None:
        await message.answer(
            "Отправьте команду с фото.\n"
            "Формат:\n"
            f"{NEW_LOT_FORMAT_HINT}"
        )
        return

    try:
        lot_number, title, description, start_price, bid_step = _parse_create_lot(message.caption or "")
    except ValueError as error:
        await message.answer(
            "Не удалось распарсить лот.\n"
            "Формат:\n"
            f"{NEW_LOT_FORMAT_HINT}\n\n"
            f"Ошибка: {error}"
        )
        return

    await _publish_lot(
        message=message,
        app_ctx=app_ctx,
        lot_number=lot_number,
        title=title,
        description=description,
        start_price=start_price,
        bid_step=bid_step,
        photo_file_ids=[message.photo[-1].file_id],
    )


@router.message(F.media_group_id)
async def new_lot_media_group_handler(message: Message, app_ctx: AppContext) -> None:
    if not _ensure_admin(message=message, app_ctx=app_ctx):
        return
    _collect_media_group_item(message=message, app_ctx=app_ctx)
