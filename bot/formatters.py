from __future__ import annotations

from html import escape
from typing import Any

from .db import Lot


def user_mention(user_id: int, username: str | None) -> str:
    if username:
        return f"@{username}"
    return f'<a href="tg://user?id={user_id}">участник</a>'


def format_lot_caption(lot: Lot) -> str:
    lines = [
        f"<b>Лот #{lot.lot_number}</b>",
        f"<b>Название:</b> {escape(lot.title)}",
        f"<b>Описание:</b> {escape(lot.description)}",
        f"<b>Начальная цена:</b> {lot.start_price}р",
    ]
    if lot.current_bid is None or lot.current_bid_user_id is None:
        lines.append("<b>Текущая ставка:</b> нет")
    else:
        bidder = user_mention(lot.current_bid_user_id, lot.current_bid_username)
        lines.append(f"<b>Текущая ставка:</b> {lot.current_bid}р ({bidder})")
    return "\n".join(lines)


def format_my_lots_report(*, user_id: int, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Пока нет избранных лотов. Поставьте ❤️ на лот или сделайте ставку."

    result_lines: list[str] = []
    total_leading = 0

    for row in rows:
        lot_number = row["lot_number"]
        title = row["title"]
        current_bid = row["current_bid"]
        current_user_id = row["current_bid_user_id"]
        current_username = row["current_bid_username"]

        if current_bid is None:
            result_lines.append(f"❤️ Лот #{lot_number} {title} — нет ставок")
            continue

        if current_user_id == user_id:
            total_leading += current_bid
            result_lines.append(f"❤️‍🔥 Лот #{lot_number} {title} — {current_bid}р")
            continue

        leader = f"@{current_username}" if current_username else "без username"
        result_lines.append(f"❤️ Лот #{lot_number} {title} — {current_bid}р ({leader})")

    result_lines.append(f"\nСумма лидирующих ставок: {total_leading}р")
    return "\n".join(result_lines)
