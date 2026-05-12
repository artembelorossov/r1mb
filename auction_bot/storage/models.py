from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Lot:
    id: int
    lot_number: int
    title: str
    description: str
    photo_file_id: str
    start_price: int
    current_bid: int | None
    current_bid_user_id: int | None
    current_bid_username: str | None
    channel_message_id: int | None
    bid_step: int
    is_active: bool


@dataclass(slots=True)
class FavoriteLot:
    lot_id: int
    lot_number: int
    title: str
    current_bid: int | None
    start_price: int
    current_bid_username: str | None
    channel_message_id: int
    is_leading: bool
