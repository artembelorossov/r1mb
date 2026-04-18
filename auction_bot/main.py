from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from auction_bot.config import load_settings
from auction_bot.context import AppContext
from auction_bot.handlers import admin, channel, common, my_lots
from auction_bot.services.google_sheets import GoogleSheetsExporter, SheetsConfig
from auction_bot.storage.database import Database


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = load_settings()
    db = Database(db_path=str(settings.database_path))
    await db.init()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    if not me.username:
        raise RuntimeError("У бота должен быть username")

    app_ctx = AppContext(
        settings=settings,
        db=db,
        sheets=GoogleSheetsExporter(
            config=SheetsConfig(
                spreadsheet_id=settings.google_sheets_spreadsheet_id,
                service_account_json=settings.google_service_account_json,
            )
        ),
        bot_username=me.username,
    )

    dp = Dispatcher()
    dp.include_router(common.router)
    dp.include_router(my_lots.router)
    dp.include_router(admin.router)
    dp.include_router(channel.router)

    await dp.start_polling(bot, app_ctx=app_ctx)


if __name__ == "__main__":
    asyncio.run(main())
