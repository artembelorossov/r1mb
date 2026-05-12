from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, MessageReactionUpdated, ReactionTypeEmoji

from auction_bot.context import AppContext
from auction_bot.formatters import format_lot_caption
from auction_bot.keyboards import lot_keyboard

router = Router(name="channel")


def _username_for_lot(callback: CallbackQuery) -> str:
    user = callback.from_user
    if user.username:
        return user.username
    return user.full_name


async def _refresh_lot_post(
    callback: CallbackQuery,
    app_ctx: AppContext,
    lot_number: int,
) -> None:
    lot = await app_ctx.db.get_lot_by_number(lot_number)
    if lot is None or lot.channel_message_id is None:
        return

    await callback.bot.edit_message_caption(
        chat_id=app_ctx.settings.auction_channel_id,
        message_id=lot.channel_message_id,
        caption=format_lot_caption(lot),
        parse_mode="HTML",
        reply_markup=lot_keyboard(lot=lot, bot_username=app_ctx.bot_username),
    )
    await app_ctx.sheets.export_lot_snapshot(lot)


@router.callback_query(F.data.startswith("bid:"))
async def bid_callback_handler(callback: CallbackQuery, app_ctx: AppContext) -> None:
    if callback.message is None:
        await callback.answer("Не удалось определить сообщение лота.", show_alert=True)
        return

    _, lot_number_raw = (callback.data or "").split(":", maxsplit=1)
    lot_number = int(lot_number_raw)
    lot = await app_ctx.db.get_lot_by_number(lot_number)
    if lot is None or not lot.is_active:
        await callback.answer("Лот не найден или уже закрыт.", show_alert=True)
        return

    user = callback.from_user
    if lot.current_bid is None:
        next_bid = lot.start_price
    else:
        next_bid = lot.current_bid + lot.bid_step

    await app_ctx.db.place_bid(
        lot_id=lot.id,
        user_id=user.id,
        username=_username_for_lot(callback),
        amount=next_bid,
    )
    await app_ctx.db.register_favorite(user_id=user.id, lot_id=lot.id)
    await callback.bot.set_message_reaction(
        chat_id=app_ctx.settings.auction_channel_id,
        message_id=lot.channel_message_id or callback.message.message_id,
        reaction=[ReactionTypeEmoji(emoji="❤")],
    )

    await _refresh_lot_post(callback=callback, app_ctx=app_ctx, lot_number=lot_number)
    await callback.answer(f"Ставка принята: {next_bid}р")


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_bid_callback_handler(callback: CallbackQuery, app_ctx: AppContext) -> None:
    if callback.message is None:
        await callback.answer("Не удалось определить сообщение лота.", show_alert=True)
        return

    _, lot_number_raw = (callback.data or "").split(":", maxsplit=1)
    lot_number = int(lot_number_raw)
    lot = await app_ctx.db.get_lot_by_number(lot_number)
    if lot is None or not lot.is_active:
        await callback.answer("Лот не найден или уже закрыт.", show_alert=True)
        return

    user = callback.from_user
    ok = await app_ctx.db.cancel_leading_bid(
        lot_id=lot.id,
        user_id=user.id,
        username=_username_for_lot(callback),
    )
    if not ok:
        await callback.answer("Можно отменить только свою лидирующую ставку.", show_alert=True)
        return

    await _refresh_lot_post(callback=callback, app_ctx=app_ctx, lot_number=lot_number)
    await callback.answer("Лидирующая ставка отменена")


def _has_heart(reactions: list[object]) -> bool:
    for reaction in reactions:
        if isinstance(reaction, ReactionTypeEmoji) and reaction.emoji == "❤":
            return True
    return False


@router.message_reaction()
async def reaction_handler(update: MessageReactionUpdated, app_ctx: AppContext) -> None:
    if update.user is None:
        return
    if update.chat.id != app_ctx.settings.auction_channel_id:
        return

    lot = await app_ctx.db.get_lot_by_message_id(update.message_id)
    if lot is None:
        return

    user_id = update.user.id
    old_has_heart = _has_heart(update.old_reaction)
    new_has_heart = _has_heart(update.new_reaction)

    if not old_has_heart and new_has_heart:
        await app_ctx.db.register_favorite(user_id=user_id, lot_id=lot.id)
    elif old_has_heart and not new_has_heart:
        await app_ctx.db.unregister_favorite(user_id=user_id, lot_id=lot.id)
