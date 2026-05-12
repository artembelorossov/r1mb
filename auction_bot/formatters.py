from __future__ import annotations

from html import escape

from auction_bot.storage.models import FavoriteLot, Lot


def format_username(username: str | None) -> str:
    if username:
        if username.startswith("@"):
            return username
        return f"@{username}"
    return "без_ника"


def format_lot_caption(lot: Lot) -> str:
    title = escape(lot.title)
    description = escape(lot.description)
    start_price = f"{lot.start_price}р"

    if lot.current_bid is None:
        current_bid_line = "—"
    else:
        current_bid_line = f"{lot.current_bid}р ({escape(format_username(lot.current_bid_username))})"

    return (
        f"📦 <b>Лот #{lot.lot_number}</b>\n"
        f"📝 <b>{title}</b>\n"
        f"📄 {description}\n\n"
        f"💰 Начальная цена: <b>{start_price}</b>\n"
        f"🏁 Текущая ставка: <b>{current_bid_line}</b>"
    )


def build_message_link(channel_id: int, message_id: int) -> str:
    # Для приватных каналов Telegram использует формат /c/<internal_id>/<message_id>.
    if channel_id < 0 and str(abs(channel_id)).startswith("100"):
        internal_id = str(abs(channel_id))[3:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return f"https://t.me/{channel_id}/{message_id}"


def format_favorites_text(favorites: list[FavoriteLot], channel_id: int) -> str:
    if not favorites:
        return "Пока нет лотов с ❤️. Ставьте сердечко в канале или делайте ставку."

    leading = [item for item in favorites if item.is_leading]
    watching = [item for item in favorites if not item.is_leading]

    lines: list[str] = []
    leading_total = 0

    for lot in leading:
        price = lot.current_bid if lot.current_bid is not None else lot.start_price
        link = build_message_link(channel_id=channel_id, message_id=lot.channel_message_id)
        lines.append(
            f"❤️‍🔥 <a href=\"{link}\">лот #{lot.lot_number} {escape(lot.title)} - {price}р</a>"
        )
        leading_total += price

    if leading:
        lines.append(f"Сумма - <b>{leading_total}р</b>")

    for lot in watching:
        price = lot.current_bid if lot.current_bid is not None else lot.start_price
        link = build_message_link(channel_id=channel_id, message_id=lot.channel_message_id)
        suffix = ""
        if lot.current_bid_username:
            suffix = f" ({escape(format_username(lot.current_bid_username))})"
        lines.append(
            f"❤️ <a href=\"{link}\">лот #{lot.lot_number} {escape(lot.title)} - {price}р</a>{suffix}"
        )

    return "\n".join(lines)
