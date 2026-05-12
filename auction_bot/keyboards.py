from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from auction_bot.storage.models import Lot


def lot_keyboard(
    lot: Lot,
    bot_username: str,
) -> InlineKeyboardMarkup:
    step_label = "повысить ставку - 0р" if lot.current_bid is None else f"повысить ставку - {lot.bid_step}р"
    buttons = [[InlineKeyboardButton(text=step_label, callback_data=f"bid:{lot.lot_number}")]]
    if lot.current_bid_user_id is not None:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="отменить ставку",
                    callback_data=f"cancel:{lot.lot_number}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="мои лоты",
                url=f"https://t.me/{bot_username}?start=my_lots",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def my_lots_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть", callback_data="my_lots:show")],
        ]
    )


def my_lots_refresh_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обновить", callback_data="my_lots:show")],
        ]
    )
