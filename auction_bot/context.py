from __future__ import annotations

from dataclasses import dataclass

from auction_bot.config import Settings
from auction_bot.services.google_sheets import GoogleSheetsExporter
from auction_bot.storage.database import Database


@dataclass(slots=True)
class AppContext:
    settings: Settings
    db: Database
    sheets: GoogleSheetsExporter
    bot_username: str
