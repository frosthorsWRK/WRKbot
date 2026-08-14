# handlers/group.py

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from db import get_connection

router = Router()

# Вспомогательная функция для получения пользователя по reply или username/id
async def get_target_user(message: types.Message):
    target = None
    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif message.text and len(message.text.split()) > 1:
        arg = message.text.split()[1]
        if arg.startswith('@'):
            username = arg[1:]
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cur.fetchone()
            conn.close()
            if row:
                target = types.User(
                    id=row['id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    is_bot=False
                )
        else:
            try:
                user_id = int(arg)
                # пытаемся получить информацию из чата
                member = await message.bot.get_chat_member(message.chat.id, user_id)
                target = member.user
            except (ValueError, TelegramBadRequest):
                pass
    return target

@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("Эта команда доступна только в группе.")
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT rules_text FROM chats WHERE id = ?", (message.chat.id,))
    row = cur.fetchone()
    conn.close()
    if row:
        await message.answer(f"📜 Правила:\n\n{row['rules_text']}")
    else:
        await message.answer("Правила не установлены.")

@router.message(Command("i", "info"))
async def cmd_info(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("Эта команда доступна только в группе.")
        return

    target = await get_target_user(message)
    if not target:
        target = message.from_user

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            (SELECT message_count FROM messages WHERE user_id = ? AND chat_id = ?) as msg_count,
            (SELECT SUM(vote_type) FROM votes WHERE target_id = ? AND chat_id = ?) as reputation,
            (SELECT created_at FROM users WHERE id = ?) as registered
    """, (target.id, message.chat.id, target.id, message.chat.id, target.id))
    row = cur.fetchone()
    conn.close()

    msg_count = row['msg_count'] or 0
    reputation = row['reputation'] or 0
    registered = row['registered'] or "неизвестно"

    text = (
        f"👤 <b>{target.full_name}</b>\n"
        f"Username: @{target.username or 'нет'}\n"
        f"ID: <code>{target.id}</code>\n"
        f"Сообщений в группе: {msg_count}\n"
        f"Репутация: {reputation:+d}\n"
        f"Зарегистрирован: {registered}"
    )
    await message.answer(text, parse_mode='HTML')

@router.message(Command("rep+"))
async def cmd_rep_plus(message: types.Message):
    await process_rep(message, vote_type=1)

@router.message(Command("rep-"))
async def cmd_rep_minus(message: types.Message):
    await process_rep(message, vote_type=-1)

async def process_rep(message: types.Message, vote_type: int):
    if message.chat.type == 'private':
        await message.answer("Команда доступна только в группе.")
        return

    target = await get_target_user(message)
    if not target:
        await message.answer("Пользователь не найден. Используйте ответ на сообщение или @username.")
        return
    if target.id == message.from_user.id:
        await message.answer("Нельзя менять репутацию самому себе.")
        return

    conn = get_connection()
    cur = conn.cursor()

    # Проверяем, голосовал ли уже этот пользователь за цель в этой группе
    cur.execute("""
        SELECT id FROM votes 
        WHERE voter_id = ? AND target_id = ? AND chat_id = ?
    """, (message.from_user.id, target.id, message.chat.id))
    existing = cur.fetchone()

    # Проверяем, является ли пользователь глобальным админом
    is_admin = False
    cur.execute("SELECT role FROM admins WHERE user_id = ?", (message.from_user.id,))
    admin_row = cur.fetchone()
    if admin_row:
        is_admin = True

    if existing and not is_admin:
        await message.answer("Вы уже голосовали за этого пользователя в этой группе.")
        conn.close()
        return

    # Если голос уже был, но админ хочет изменить — удаляем старый
    if existing and is_admin:
        cur.execute("DELETE FROM votes WHERE id = ?", (existing['id'],))

    # Вставляем новый голос
    cur.execute("""
        INSERT INTO votes (voter_id, target_id, chat_id, vote_type)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, target.id, message.chat.id, vote_type))
    conn.commit()

    # Получаем новую репутацию
    cur.execute("SELECT SUM(vote_type) FROM votes WHERE target_id = ? AND chat_id = ?",
                (target.id, message.chat.id))
    rep = cur.fetchone()[0] or 0
    conn.close()

    action = "повысили" if vote_type == 1 else "понизили"
    await message.answer(
        f"✅ Вы {action} репутацию {target.full_name}.\nТекущая репутация: {rep:+d}"
    )

@router.message(Command("report"))
async def cmd_report(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("Команда доступна только в группе.")
        return

    target = None
    reason = None

    if message.reply_to_message:
        target = message.reply_to_message.from_user
        if message.text and len(message.text.split()) > 1:
            reason = ' '.join(message.text.split()[1:])
        else:
            reason = "Не указана"
    else:
        parts = message.text.split(maxsplit=2)
        if len(parts) >= 2:
            arg = parts[1]
            if arg.startswith('@'):
                username = arg[1:]
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id, first_name, username FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                conn.close()
                if row:
                    target = types.User(id=row['id'], username=row['username'], first_name=row['first_name'], is_bot=False)
            else:
                try:
                    user_id = int(arg)
                    member = await message.bot.get_chat_member(message.chat.id, user_id)
                    target = member.user
                except (ValueError, TelegramBadRequest):
                    pass
            if len(parts) == 3:
                reason = parts[2]
            else:
                reason = "Не указана"
        else:
            await message.answer("Используйте: /report @username [причина] или ответьте на сообщение нарушителя.")
            return

    if not target:
        await message.answer("Пользователь не найден.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (reporter_id, target_id, chat_id, reason)
        VALUES (?, ?, ?, ?)
    """, (message.from_user.id, target.id, message.chat.id, reason))
    conn.commit()
    conn.close()

    await message.answer("✅ Репорт отправлен. Спасибо за бдительность!")

    # Отправляем уведомление глобальным админам
    from db import get_all_admins
    admins = get_all_admins()
    for admin_id in admins:
        try:
            await message.bot.send_message(
                admin_id,
                f"🚨 Новый репорт!\n"
                f"Группа: {message.chat.title} (ID: {message.chat.id})\n"
                f"От: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"На: {target.full_name} (@{target.username})\n"
                f"Причина: {reason}"
            )
        except Exception:
            pass

@router.message(Command("toprep"))
async def cmd_toprep(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("Команда доступна только в группе.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.first_name, u.username, SUM(v.vote_type) as rep
        FROM votes v
        JOIN users u ON u.id = v.target_id
        WHERE v.chat_id = ?
        GROUP BY v.target_id
        ORDER BY rep DESC
        LIMIT 10
    """, (message.chat.id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет голосов.")
        return

    text = "🏆 Топ-10 по репутации:\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row['first_name']} (@{row['username'] or 'нет'}) — {row['rep']:+d}\n"
    await message.answer(text)

# Обработка сообщений вида "WRK / Поиск Исполнителей / Minecraft"
@router.message(F.text.startswith('WRK /'))
async def handle_wrk(message: types.Message):
    parts = message.text.split('/')
    if len(parts) >= 2:
        category = parts[1].strip()
        await message.reply(
            f"🔍 Вы ищете исполнителя в категории: <b>{category}</b>\n"
            f"Используйте команды /rep+ и /rep- для оценки исполнителей.",
            parse_mode='HTML'
        )