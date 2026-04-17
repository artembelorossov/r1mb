from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class Lot:
    id: int
    lot_number: int
    title: str
    description: str
    start_price: int
    current_bid: int | None
    current_bid_user_id: int | None
    current_bid_username: str | None
    photo_file_id: str
    auction_chat_id: int | None
    auction_message_id: int | None


@dataclass(frozen=True)
class BidResult:
    lot: Lot
    new_bid: int


class AuctionDatabase:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    async def _connect(self) -> aiosqlite.Connection:
        connection = await aiosqlite.connect(self.database_path)
        connection.row_factory = aiosqlite.Row
        return connection

    @staticmethod
    def _row_to_lot(row: aiosqlite.Row) -> Lot:
        return Lot(
            id=row["id"],
            lot_number=row["lot_number"],
            title=row["title"],
            description=row["description"],
            start_price=row["start_price"],
            current_bid=row["current_bid"],
            current_bid_user_id=row["current_bid_user_id"],
            current_bid_username=row["current_bid_username"],
            photo_file_id=row["photo_file_id"],
            auction_chat_id=row["auction_chat_id"],
            auction_message_id=row["auction_message_id"],
        )

    async def initialize(self) -> None:
        async with await self._connect() as conn:
            await conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_number INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    start_price INTEGER NOT NULL,
                    current_bid INTEGER,
                    current_bid_user_id INTEGER,
                    current_bid_username TEXT,
                    photo_file_id TEXT NOT NULL,
                    auction_chat_id INTEGER,
                    auction_message_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    amount INTEGER NOT NULL,
                    cancelled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(lot_id) REFERENCES lots(id)
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    lot_id INTEGER NOT NULL,
                    username TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, lot_id),
                    FOREIGN KEY(lot_id) REFERENCES lots(id)
                );
                """
            )
            await conn.commit()

    async def create_lot(
        self,
        *,
        lot_number: int,
        title: str,
        description: str,
        start_price: int,
        photo_file_id: str,
    ) -> int:
        async with await self._connect() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO lots (lot_number, title, description, start_price, photo_file_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (lot_number, title, description, start_price, photo_file_id),
            )
            await conn.commit()
            return int(cursor.lastrowid)

    async def set_lot_message(
        self, *, lot_id: int, auction_chat_id: int, auction_message_id: int
    ) -> None:
        async with await self._connect() as conn:
            await conn.execute(
                """
                UPDATE lots
                SET auction_chat_id = ?, auction_message_id = ?
                WHERE id = ?
                """,
                (auction_chat_id, auction_message_id, lot_id),
            )
            await conn.commit()

    async def get_lot(self, lot_id: int) -> Lot | None:
        async with await self._connect() as conn:
            cursor = await conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_lot(row)

    async def get_lot_by_message(self, *, chat_id: int, message_id: int) -> Lot | None:
        async with await self._connect() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM lots
                WHERE auction_chat_id = ? AND auction_message_id = ?
                """,
                (chat_id, message_id),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_lot(row)

    async def place_bid(
        self,
        *,
        lot_id: int,
        user_id: int,
        username: str | None,
        bid_step: int,
    ) -> BidResult:
        async with await self._connect() as conn:
            lot_row = await (await conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))).fetchone()
            if lot_row is None:
                raise ValueError("Лот не найден")

            lot = self._row_to_lot(lot_row)
            new_bid = lot.start_price if lot.current_bid is None else lot.current_bid + bid_step
            await conn.execute(
                """
                INSERT INTO bids (lot_id, user_id, username, amount)
                VALUES (?, ?, ?, ?)
                """,
                (lot_id, user_id, username, new_bid),
            )
            await conn.execute(
                """
                UPDATE lots
                SET current_bid = ?, current_bid_user_id = ?, current_bid_username = ?
                WHERE id = ?
                """,
                (new_bid, user_id, username, lot_id),
            )
            await conn.commit()

            updated_row = await (await conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))).fetchone()
            assert updated_row is not None
            return BidResult(lot=self._row_to_lot(updated_row), new_bid=new_bid)

    async def cancel_leader_bid(self, *, lot_id: int, user_id: int) -> Lot:
        async with await self._connect() as conn:
            lot_row = await (await conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))).fetchone()
            if lot_row is None:
                raise ValueError("Лот не найден")

            lot = self._row_to_lot(lot_row)
            if lot.current_bid_user_id != user_id:
                raise PermissionError("Только лидер может отменить свою ставку")
            if lot.current_bid is None:
                raise ValueError("У лота пока нет ставок")

            bid_row = await (
                await conn.execute(
                    """
                    SELECT id FROM bids
                    WHERE lot_id = ? AND user_id = ? AND amount = ? AND cancelled = 0
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (lot_id, user_id, lot.current_bid),
                )
            ).fetchone()
            if bid_row is None:
                raise ValueError("Не удалось найти ставку для отмены")

            await conn.execute("UPDATE bids SET cancelled = 1 WHERE id = ?", (bid_row["id"],))
            await self._recalculate_leader(conn, lot_id=lot_id)
            await conn.commit()

            updated_row = await (await conn.execute("SELECT * FROM lots WHERE id = ?", (lot_id,))).fetchone()
            assert updated_row is not None
            return self._row_to_lot(updated_row)

    async def _recalculate_leader(self, conn: aiosqlite.Connection, *, lot_id: int) -> None:
        leader_row = await (
            await conn.execute(
                """
                SELECT user_id, username, amount
                FROM bids
                WHERE lot_id = ? AND cancelled = 0
                ORDER BY amount DESC, id DESC
                LIMIT 1
                """,
                (lot_id,),
            )
        ).fetchone()

        if leader_row is None:
            await conn.execute(
                """
                UPDATE lots
                SET current_bid = NULL,
                    current_bid_user_id = NULL,
                    current_bid_username = NULL
                WHERE id = ?
                """,
                (lot_id,),
            )
            return

        await conn.execute(
            """
            UPDATE lots
            SET current_bid = ?, current_bid_user_id = ?, current_bid_username = ?
            WHERE id = ?
            """,
            (leader_row["amount"], leader_row["user_id"], leader_row["username"], lot_id),
        )

    async def add_favorite(
        self, *, user_id: int, username: str | None, lot_id: int, source: str
    ) -> None:
        async with await self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO favorites (user_id, lot_id, username, source)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, lot_id)
                DO UPDATE SET username = excluded.username, source = excluded.source
                """,
                (user_id, lot_id, username, source),
            )
            await conn.commit()

    async def remove_favorite(self, *, user_id: int, lot_id: int) -> None:
        async with await self._connect() as conn:
            await conn.execute(
                "DELETE FROM favorites WHERE user_id = ? AND lot_id = ?",
                (user_id, lot_id),
            )
            await conn.commit()

    async def get_user_favorite_lots(self, *, user_id: int) -> list[dict[str, Any]]:
        async with await self._connect() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    l.id,
                    l.lot_number,
                    l.title,
                    l.start_price,
                    l.current_bid,
                    l.current_bid_user_id,
                    l.current_bid_username
                FROM favorites f
                JOIN lots l ON l.id = f.lot_id
                WHERE f.user_id = ?
                ORDER BY l.lot_number ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
