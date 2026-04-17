from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_int(name: str, default: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        if default is None:
            raise ValueError(f"Environment variable {name} is required")
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _parse_admin_ids(name: str) -> set[int]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return set()
    values = set()
    for token in raw_value.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.add(int(token))
        except ValueError as exc:
            raise ValueError(
                f"Environment variable {name} must be a comma separated list of integers"
            ) from exc
    return values


@dataclass(frozen=True)
class Settings:
    bot_token: str
    auction_chat_id: int
    admin_topic_id: int
    info_topic_id: int
    auction_topic_id: int
    stats_topic_id: int
    my_lots_topic_id: int
    bid_step: int
    database_path: str
    admin_user_ids: set[int]


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Environment variable BOT_TOKEN is required")

    return Settings(
        bot_token=token,
        auction_chat_id=_parse_int("AUCTION_CHAT_ID"),
        admin_topic_id=_parse_int("ADMIN_TOPIC_ID"),
        info_topic_id=_parse_int("INFO_TOPIC_ID"),
        auction_topic_id=_parse_int("AUCTION_TOPIC_ID"),
        stats_topic_id=_parse_int("STATS_TOPIC_ID", default=0),
        my_lots_topic_id=_parse_int("MY_LOTS_TOPIC_ID"),
        bid_step=_parse_int("BID_STEP", default=50),
        database_path=os.getenv("DATABASE_PATH", "auction.db"),
        admin_user_ids=_parse_admin_ids("ADMIN_USER_IDS"),
    )
