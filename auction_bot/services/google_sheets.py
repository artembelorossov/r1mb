from __future__ import annotations

from dataclasses import dataclass

from auction_bot.storage.models import Lot


@dataclass(slots=True)
class SheetsConfig:
    spreadsheet_id: str | None
    service_account_json: str | None


class GoogleSheetsExporter:
    """
    Заглушка для экспорта статистики.
    Можно реализовать позже через gspread или Google API.
    """

    def __init__(self, config: SheetsConfig) -> None:
        self.config = config

    async def export_lot_snapshot(self, lot: Lot) -> None:
        # MVP: пока без реальной отправки.
        _ = lot
        return None
