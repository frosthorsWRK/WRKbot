# main.py

import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OWNER_ID
from db import init_db, get_connection
from handlers import group, private

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Middleware для регистрации пользователей и подсчёта сообщений
@dp.message.outer_middleware()
async def track_user_middleware(handler, event: types.Message, data: dict):
    # Регистрируем пользователя (в любом чате)
    user = event.from_user
    if user:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (id, username, first_name) VALUES (?, ?, ?)",
                    (user.id, user.username, user.first_name))
        conn.commit()
        conn.close()

    # Если это группа, регистрируем чат и увеличиваем счётчик сообщений
    if event.chat.type in ['group', 'supergroup']:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO chats (id, title) VALUES (?, ?)",
                    (event.chat.id, event.chat.title))
        cur.execute("""
            INSERT INTO messages (user_id, chat_id, message_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET message_count = message_count + 1
        """, (user.id, event.chat.id))
        conn.commit()
        conn.close()

    return await handler(event, data)

# Регистрация роутеров
dp.include_router(group.router)
dp.include_router(private.router)

async def main():
    init_db()
    # Удаляем вебхук, если был
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())