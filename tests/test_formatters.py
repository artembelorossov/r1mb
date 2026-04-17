from bot.db import Lot
from bot.formatters import format_lot_caption, format_my_lots_report


def test_format_lot_caption_without_bid() -> None:
    lot = Lot(
        id=1,
        lot_number=7,
        title="Фломастеры",
        description="Набор из 12 цветов",
        start_price=150,
        current_bid=None,
        current_bid_user_id=None,
        current_bid_username=None,
        photo_file_id="abc",
        auction_chat_id=None,
        auction_message_id=None,
    )
    text = format_lot_caption(lot)
    assert "Лот #7" in text
    assert "Текущая ставка:</b> нет" in text


def test_format_my_lots_report() -> None:
    rows = [
        {
            "lot_number": 1,
            "title": "Карандаши",
            "current_bid": 100,
            "current_bid_user_id": 10,
            "current_bid_username": "alex",
        },
        {
            "lot_number": 5,
            "title": "Ручки",
            "current_bid": 200,
            "current_bid_user_id": 20,
            "current_bid_username": "maria",
        },
    ]
    report = format_my_lots_report(user_id=10, rows=rows)
    assert "❤️‍🔥 Лот #1 Карандаши — 100р" in report
    assert "❤️ Лот #5 Ручки — 200р (@maria)" in report
    assert "Сумма лидирующих ставок: 100р" in report
