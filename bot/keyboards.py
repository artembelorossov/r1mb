from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_lot_keyboard(*, lot_id: int, has_bids: bool, bid_step: int) -> InlineKeyboardMarkup:
    increment_text = f"Повысить ставку +{bid_step}р" if has_bids else "Повысить ставку +0р"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=increment_text, callback_data=f"bid:{lot_id}")],
            [InlineKeyboardButton(text="Отменить мою ставку", callback_data=f"cancel:{lot_id}")],
        ]
    )


def build_my_lots_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть", callback_data="my_lots:open")],
        ]
    )
