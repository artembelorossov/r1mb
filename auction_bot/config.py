from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    auction_channel_id: int
    admin_user_ids: set[int]
    default_bid_step: int
    database_path: Path
    google_sheets_spreadsheet_id: str | None
    google_service_account_json: str | None


def _parse_admin_ids(raw: str) -> set[int]:
    values: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.add(int(chunk))
    return values


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("BOT_TOKEN is required")

    auction_channel_id = int(os.getenv("AUCTION_CHANNEL_ID", "0").strip())
    if not auction_channel_id:
        raise ValueError("AUCTION_CHANNEL_ID is required")

    admin_user_ids = _parse_admin_ids(os.getenv("ADMIN_USER_IDS", ""))
    if not admin_user_ids:
        raise ValueError("ADMIN_USER_IDS must contain at least one Telegram user id")

    default_bid_step = int(os.getenv("DEFAULT_BID_STEP", "50"))
    if default_bid_step < 1:
        raise ValueError("DEFAULT_BID_STEP must be positive")

    database_path = Path(os.getenv("DATABASE_PATH", "auction.db")).expanduser()
    google_sheets_spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    google_service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    return Settings(
        bot_token=bot_token,
        auction_channel_id=auction_channel_id,
        admin_user_ids=admin_user_ids,
        default_bid_step=default_bid_step,
        database_path=database_path,
        google_sheets_spreadsheet_id=google_sheets_spreadsheet_id,
        google_service_account_json=google_service_account_json,
    )
