from __future__ import annotations

import sqlite3
from typing import Iterable

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageReactionUpdated, ReactionTypeEmoji

from .config import Settings
from .db import AuctionDatabase, Lot
from .formatters import format_lot_caption, format_my_lots_report
from .keyboards import build_lot_keyboard, build_my_lots_keyboard
from .states import AddLotStates

router = Router(name="auction-router")

HEART_EMOJIS = {"❤", "❤️"}


def _is_admin(user_id: int, settings: Settings) -> bool:
    return not settings.admin_user_ids or user_id in settings.admin_user_ids


def _is_admin_topic(message: Message, settings: Settings) -> bool:
    return message.message_thread_id == settings.admin_topic_id


def _contains_heart(reactions: Iterable[object]) -> bool:
    for reaction in reactions:
        reaction_type = getattr(reaction, "type", None)
        emoji = getattr(reaction, "emoji", None)
        if reaction_type == "emoji" and emoji in HEART_EMOJIS:
            return True
    return False


async def _refresh_lot_message(*, bot: Bot, lot: Lot, settings: Settings) -> None:
    if lot.auction_chat_id is None or lot.auction_message_id is None:
        return
    await bot.edit_message_caption(
        chat_id=lot.auction_chat_id,
        message_id=lot.auction_message_id,
        caption=format_lot_caption(lot),
        parse_mode="HTML",
        reply_markup=build_lot_keyboard(
            lot_id=lot.id,
            has_bids=lot.current_bid is not None,
            bid_step=settings.bid_step,
        ),
    )


async def _send_my_lots_report(
    *,
    message: Message | None,
    callback: CallbackQuery | None,
    db: AuctionDatabase,
    settings: Settings,
    user_id: int,
) -> None:
    rows = await db.get_user_favorite_lots(user_id=user_id)
    report = format_my_lots_report(user_id=user_id, rows=rows)

    if callback is not None and callback.message is not None:
        await callback.message.bot.send_message(
            chat_id=settings.auction_chat_id,
            message_thread_id=settings.my_lots_topic_id,
            text=report,
        )
        return

    assert message is not None
    await message.bot.send_message(
        chat_id=settings.auction_chat_id,
        message_thread_id=settings.my_lots_topic_id,
        text=report,
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/add_lot — добавить лот (только админ, в админ-топике)\n"
        "/cancel — отменить текущий шаг добавления лота\n"
        "/publish_my_lots_panel — опубликовать кнопку 'Посмотреть' в топике 'Мои лоты'\n"
        "/publish_info <текст> — опубликовать закрепленный инфо-пост\n"
        "/my_lots — вывести ваши избранные лоты"
    )


@router.message(Command("publish_my_lots_panel"))
async def publish_my_lots_panel(
    message: Message, settings: Settings
) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id, settings):
        return
    await message.bot.send_message(
        chat_id=settings.auction_chat_id,
        message_thread_id=settings.my_lots_topic_id,
        text="Нажмите кнопку, чтобы получить список ваших отслеживаемых лотов:",
        reply_markup=build_my_lots_keyboard(),
    )
    await message.answer("Панель 'Мои лоты' опубликована.")


@router.message(Command("publish_info"))
async def publish_info(
    message: Message,
    settings: Settings,
) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id, settings):
        return
    payload = (message.text or "").split(maxsplit=1)
    if len(payload) < 2:
        await message.answer("Использование: /publish_info <текст>")
        return
    await message.bot.send_message(
        chat_id=settings.auction_chat_id,
        message_thread_id=settings.info_topic_id,
        text=payload[1],
    )
    await message.answer("Информация опубликована.")


@router.message(Command("my_lots"))
async def my_lots_command(message: Message, db: AuctionDatabase, settings: Settings) -> None:
    if message.from_user is None:
        return
    await _send_my_lots_report(
        message=message,
        callback=None,
        db=db,
        settings=settings,
        user_id=message.from_user.id,
    )


@router.callback_query(F.data == "my_lots:open")
async def my_lots_callback(
    callback: CallbackQuery,
    db: AuctionDatabase,
    settings: Settings,
) -> None:
    if callback.from_user is None:
        return
    await _send_my_lots_report(
        message=None,
        callback=callback,
        db=db,
        settings=settings,
        user_id=callback.from_user.id,
    )
    await callback.answer("Список отправлен в топик 'Мои лоты'")


@router.message(Command("add_lot"))
async def add_lot_start(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.from_user is None or not _is_admin(message.from_user.id, settings):
        return
    if not _is_admin_topic(message, settings):
        await message.answer("Добавление лотов доступно только в админ-топике.")
        return
    await state.set_state(AddLotStates.waiting_photo)
    await message.answer("Шаг 1/5: отправьте фото лота.")


@router.message(Command("cancel"))
async def cancel_state(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного сценария.")
        return
    await state.clear()
    await message.answer("Сценарий добавления лота отменен.")


@router.message(AddLotStates.waiting_photo, F.photo)
async def add_lot_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_id)
    await state.set_state(AddLotStates.waiting_number)
    await message.answer("Шаг 2/5: укажите номер лота (целое число).")


@router.message(AddLotStates.waiting_photo)
async def add_lot_photo_invalid(message: Message) -> None:
    await message.answer("Нужно отправить именно фото лота.")


@router.message(AddLotStates.waiting_number)
async def add_lot_number(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Номер лота должен быть целым числом.")
        return
    await state.update_data(lot_number=int(text))
    await state.set_state(AddLotStates.waiting_title)
    await message.answer("Шаг 3/5: напишите название лота.")


@router.message(AddLotStates.waiting_title)
async def add_lot_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=title)
    await state.set_state(AddLotStates.waiting_description)
    await message.answer("Шаг 4/5: напишите описание лота.")


@router.message(AddLotStates.waiting_description)
async def add_lot_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=description)
    await state.set_state(AddLotStates.waiting_start_price)
    await message.answer("Шаг 5/5: укажите стартовую цену (целое число в рублях).")


@router.message(AddLotStates.waiting_start_price)
async def add_lot_price(
    message: Message,
    state: FSMContext,
    db: AuctionDatabase,
    settings: Settings,
) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Стартовая цена должна быть целым числом.")
        return
    start_price = int(text)
    if start_price < 0:
        await message.answer("Стартовая цена не может быть отрицательной.")
        return

    data = await state.get_data()
    try:
        lot_id = await db.create_lot(
            lot_number=data["lot_number"],
            title=data["title"],
            description=data["description"],
            start_price=start_price,
            photo_file_id=data["photo_file_id"],
        )
    except sqlite3.IntegrityError:
        await message.answer("Лот с таким номером уже есть. Начните заново: /add_lot")
        await state.clear()
        return

    lot = await db.get_lot(lot_id)
    assert lot is not None
    sent = await message.bot.send_photo(
        chat_id=settings.auction_chat_id,
        message_thread_id=settings.auction_topic_id,
        photo=lot.photo_file_id,
        caption=format_lot_caption(lot),
        parse_mode="HTML",
        reply_markup=build_lot_keyboard(lot_id=lot_id, has_bids=False, bid_step=settings.bid_step),
    )
    await db.set_lot_message(
        lot_id=lot_id, auction_chat_id=sent.chat.id, auction_message_id=sent.message_id
    )
    await message.answer(f"Лот #{lot.lot_number} опубликован в аукционном топике.")
    await state.clear()


@router.callback_query(F.data.startswith("bid:"))
async def bid_callback(
    callback: CallbackQuery,
    db: AuctionDatabase,
    settings: Settings,
) -> None:
    if callback.from_user is None:
        return
    try:
        lot_id = int(callback.data.split(":", maxsplit=1)[1])  # type: ignore[union-attr]
    except (ValueError, IndexError, AttributeError):
        await callback.answer("Некорректный идентификатор лота", show_alert=True)
        return

    lot = await db.get_lot(lot_id)
    if lot is None:
        await callback.answer("Лот не найден", show_alert=True)
        return

    username = callback.from_user.username
    bid_result = await db.place_bid(
        lot_id=lot_id,
        user_id=callback.from_user.id,
        username=username,
        bid_step=settings.bid_step,
    )
    await db.add_favorite(
        user_id=callback.from_user.id,
        username=username,
        lot_id=lot_id,
        source="bid",
    )

    try:
        await _refresh_lot_message(bot=callback.bot, lot=bid_result.lot, settings=settings)
    except Exception:
        # Сообщение могли изменить вручную — продолжаем без падения обработчика.
        pass

    if bid_result.lot.auction_chat_id and bid_result.lot.auction_message_id:
        try:
            await callback.bot.set_message_reaction(
                chat_id=bid_result.lot.auction_chat_id,
                message_id=bid_result.lot.auction_message_id,
                reaction=[ReactionTypeEmoji(emoji="❤️")],
            )
        except Exception:
            pass

    await callback.answer(f"Ставка принята: {bid_result.new_bid}р")


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_bid_callback(
    callback: CallbackQuery,
    db: AuctionDatabase,
    settings: Settings,
) -> None:
    if callback.from_user is None:
        return
    try:
        lot_id = int(callback.data.split(":", maxsplit=1)[1])  # type: ignore[union-attr]
    except (ValueError, IndexError, AttributeError):
        await callback.answer("Некорректный идентификатор лота", show_alert=True)
        return

    try:
        updated_lot = await db.cancel_leader_bid(lot_id=lot_id, user_id=callback.from_user.id)
    except PermissionError:
        await callback.answer("Отменить можно только лидирующую ставку", show_alert=True)
        return
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    try:
        await _refresh_lot_message(bot=callback.bot, lot=updated_lot, settings=settings)
    except Exception:
        pass

    await callback.answer("Ваша лидирующая ставка отменена")


@router.message_reaction()
async def track_reactions(
    event: MessageReactionUpdated, db: AuctionDatabase, settings: Settings
) -> None:
    if event.chat.id != settings.auction_chat_id:
        return
    if event.user is None:
        return

    lot = await db.get_lot_by_message(chat_id=event.chat.id, message_id=event.message_id)
    if lot is None:
        return

    had_heart = _contains_heart(event.old_reaction)
    has_heart = _contains_heart(event.new_reaction)

    if has_heart and not had_heart:
        await db.add_favorite(
            user_id=event.user.id,
            username=event.user.username,
            lot_id=lot.id,
            source="reaction",
        )
    elif had_heart and not has_heart:
        await db.remove_favorite(user_id=event.user.id, lot_id=lot.id)
