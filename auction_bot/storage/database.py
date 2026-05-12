from __future__ import annotations

import aiosqlite

from auction_bot.storage.models import FavoriteLot, Lot


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_number INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    photo_file_id TEXT NOT NULL,
                    start_price INTEGER NOT NULL,
                    current_bid INTEGER,
                    current_bid_user_id INTEGER,
                    current_bid_username TEXT,
                    channel_message_id INTEGER UNIQUE,
                    bid_step INTEGER NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS favorites (
                    user_id INTEGER NOT NULL,
                    lot_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, lot_id),
                    FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lot_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    amount INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lot_id) REFERENCES lots(id) ON DELETE CASCADE
                );
                """
            )
            await db.commit()

    async def create_lot(
        self,
        lot_number: int,
        title: str,
        description: str,
        photo_file_id: str,
        start_price: int,
        channel_message_id: int | None,
        bid_step: int,
    ) -> int:
        query = """
            INSERT INTO lots (
                lot_number,
                title,
                description,
                photo_file_id,
                start_price,
                current_bid,
                current_bid_user_id,
                current_bid_username,
                channel_message_id,
                bid_step,
                is_active
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, 1)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                query,
                (
                    lot_number,
                    title,
                    description,
                    photo_file_id,
                    start_price,
                    channel_message_id,
                    bid_step,
                ),
            )
            await db.commit()
            return int(cursor.lastrowid)

    async def set_lot_channel_message_id(self, lot_id: int, channel_message_id: int) -> None:
        query = "UPDATE lots SET channel_message_id = ? WHERE id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (channel_message_id, lot_id))
            await db.commit()

    async def delete_lot(self, lot_id: int) -> None:
        query = "DELETE FROM lots WHERE id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (lot_id,))
            await db.commit()

    async def get_lot_by_number(self, lot_number: int) -> Lot | None:
        query = """
            SELECT id, lot_number, title, description, photo_file_id, start_price,
                   current_bid, current_bid_user_id, current_bid_username,
                   channel_message_id, bid_step, is_active
            FROM lots
            WHERE lot_number = ?
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute(query, (lot_number,))).fetchone()
            if row is None:
                return None
            return self._row_to_lot(row)

    async def get_lot_by_message_id(self, message_id: int) -> Lot | None:
        query = """
            SELECT id, lot_number, title, description, photo_file_id, start_price,
                   current_bid, current_bid_user_id, current_bid_username,
                   channel_message_id, bid_step, is_active
            FROM lots
            WHERE channel_message_id = ?
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute(query, (message_id,))).fetchone()
            if row is None:
                return None
            return self._row_to_lot(row)

    async def get_lot_by_id(self, lot_id: int) -> Lot | None:
        query = """
            SELECT id, lot_number, title, description, photo_file_id, start_price,
                   current_bid, current_bid_user_id, current_bid_username,
                   channel_message_id, bid_step, is_active
            FROM lots
            WHERE id = ?
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute(query, (lot_id,))).fetchone()
            if row is None:
                return None
            return self._row_to_lot(row)

    async def register_favorite(self, user_id: int, lot_id: int) -> None:
        query = """
            INSERT OR IGNORE INTO favorites (user_id, lot_id) VALUES (?, ?)
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (user_id, lot_id))
            await db.commit()

    async def unregister_favorite(self, user_id: int, lot_id: int) -> None:
        query = "DELETE FROM favorites WHERE user_id = ? AND lot_id = ?"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, (user_id, lot_id))
            await db.commit()

    async def has_favorite(self, user_id: int, lot_id: int) -> bool:
        query = "SELECT 1 FROM favorites WHERE user_id = ? AND lot_id = ? LIMIT 1"
        async with aiosqlite.connect(self.db_path) as db:
            row = await (await db.execute(query, (user_id, lot_id))).fetchone()
            return row is not None

    async def get_favorite_lots_for_user(self, user_id: int) -> list[FavoriteLot]:
        query = """
            SELECT
                l.id AS lot_id,
                l.lot_number,
                l.title,
                l.current_bid,
                l.start_price,
                l.current_bid_username,
                l.channel_message_id,
                CASE WHEN l.current_bid_user_id = ? THEN 1 ELSE 0 END AS is_leading
            FROM favorites f
            JOIN lots l ON l.id = f.lot_id
            WHERE f.user_id = ? AND l.is_active = 1 AND l.channel_message_id IS NOT NULL
            ORDER BY l.lot_number ASC
        """
        result: list[FavoriteLot] = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (await db.execute(query, (user_id, user_id))).fetchall()
            for row in rows:
                result.append(
                    FavoriteLot(
                        lot_id=int(row["lot_id"]),
                        lot_number=int(row["lot_number"]),
                        title=str(row["title"]),
                        current_bid=int(row["current_bid"]) if row["current_bid"] is not None else None,
                        start_price=int(row["start_price"]),
                        current_bid_username=str(row["current_bid_username"])
                        if row["current_bid_username"] is not None
                        else None,
                        channel_message_id=int(row["channel_message_id"]),
                        is_leading=bool(row["is_leading"]),
                    )
                )
        return result

    async def place_bid(self, lot_id: int, user_id: int, username: str | None, amount: int) -> None:
        update_lot_query = """
            UPDATE lots
            SET current_bid = ?, current_bid_user_id = ?, current_bid_username = ?
            WHERE id = ?
        """
        bid_query = """
            INSERT INTO bids (lot_id, user_id, username, amount, action)
            VALUES (?, ?, ?, ?, 'place')
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(update_lot_query, (amount, user_id, username, lot_id))
            await db.execute(bid_query, (lot_id, user_id, username, amount))
            await db.commit()

    async def user_is_leading(self, lot_id: int, user_id: int) -> bool:
        query = "SELECT 1 FROM lots WHERE id = ? AND current_bid_user_id = ? LIMIT 1"
        async with aiosqlite.connect(self.db_path) as db:
            row = await (await db.execute(query, (lot_id, user_id))).fetchone()
            return row is not None

    async def cancel_leading_bid(self, lot_id: int, user_id: int, username: str | None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            lot_row = await (
                await db.execute(
                    """
                    SELECT current_bid_user_id, current_bid
                    FROM lots
                    WHERE id = ? AND is_active = 1
                    """,
                    (lot_id,),
                )
            ).fetchone()
            if lot_row is None:
                return False
            if lot_row["current_bid_user_id"] != user_id:
                return False

            await db.execute(
                """
                INSERT INTO bids (lot_id, user_id, username, amount, action)
                VALUES (?, ?, ?, ?, 'cancel')
                """,
                (lot_id, user_id, username, int(lot_row["current_bid"] or 0)),
            )

            previous_place = await (
                await db.execute(
                    """
                    SELECT user_id, username, amount
                    FROM bids
                    WHERE lot_id = ? AND action = 'place' AND user_id != ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (lot_id, user_id),
                )
            ).fetchone()

            if previous_place is None:
                await db.execute(
                    """
                    UPDATE lots
                    SET current_bid = NULL,
                        current_bid_user_id = NULL,
                        current_bid_username = NULL
                    WHERE id = ?
                    """,
                    (lot_id,),
                )
            else:
                await db.execute(
                    """
                    UPDATE lots
                    SET current_bid = ?,
                        current_bid_user_id = ?,
                        current_bid_username = ?
                    WHERE id = ?
                    """,
                    (
                        int(previous_place["amount"]),
                        int(previous_place["user_id"]),
                        str(previous_place["username"]) if previous_place["username"] is not None else None,
                        lot_id,
                    ),
                )

            await db.commit()
            return True

    def _row_to_lot(self, row: aiosqlite.Row) -> Lot:
        return Lot(
            id=int(row["id"]),
            lot_number=int(row["lot_number"]),
            title=str(row["title"]),
            description=str(row["description"]),
            photo_file_id=str(row["photo_file_id"]),
            start_price=int(row["start_price"]),
            current_bid=int(row["current_bid"]) if row["current_bid"] is not None else None,
            current_bid_user_id=int(row["current_bid_user_id"])
            if row["current_bid_user_id"] is not None
            else None,
            current_bid_username=str(row["current_bid_username"])
            if row["current_bid_username"] is not None
            else None,
            channel_message_id=int(row["channel_message_id"])
            if row["channel_message_id"] is not None
            else None,
            bid_step=int(row["bid_step"]),
            is_active=bool(row["is_active"]),
        )
