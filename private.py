# handlers/private.py

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import get_connection, is_global_admin, get_all_admins
from keyboards import admin_main_keyboard, admin_admins_keyboard, back_to_admin_keyboard

router = Router()

# Состояния для добавления группы
class AddGroup(StatesGroup):
    waiting_for_chat_id = State()

# Состояния для редактирования правил
class SetRules(StatesGroup):
    waiting_for_group = State()
    waiting_for_text = State()

# Состояния для добавления/удаления админов
class AddAdmin(StatesGroup):
    waiting_for_user_id = State()

class DelAdmin(StatesGroup):
    waiting_for_user_id = State()

# Команда /admin в личке
@router.message(Command("admin"), F.chat.type == "private")
async def admin_panel(message: types.Message):
    if not is_global_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await message.answer("Админ-панель:", reply_markup=admin_main_keyboard())

# Обработчики callback-запросов

@router.callback_query(F.data == "admin_groups")
async def admin_groups(callback: types.CallbackQuery):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM chats")
    groups = cur.fetchall()
    conn.close()
    if not groups:
        await callback.message.edit_text("Бот ещё не добавлен ни в одну группу.", reply_markup=back_to_admin_keyboard())
    else:
        text = "📋 Группы:\n\n"
        for g in groups:
            text += f"• {g['title']} (ID: {g['id']})\n"
        await callback.message.edit_text(text, reply_markup=back_to_admin_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_add_group")
async def admin_add_group(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Отправьте ID группы или перешлите любое сообщение из этой группы.",
        reply_markup=back_to_admin_keyboard()
    )
    await state.set_state(AddGroup.waiting_for_chat_id)
    await callback.answer()

@router.message(AddGroup.waiting_for_chat_id, F.chat.type == "private")
async def process_add_group(message: types.Message, state: FSMContext):
    chat_id = None
    title = None
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title
    elif message.text and message.text.isdigit():
        chat_id = int(message.text)
        try:
            chat = await message.bot.get_chat(chat_id)
            title = chat.title
        except Exception:
            await message.answer("Не удалось получить информацию о чате. Убедитесь, что бот добавлен в этот чат.")
            await state.clear()
            return
    else:
        await message.answer("Неверный формат. Отправьте числовой ID или перешлите сообщение.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO chats (id, title, added_by) VALUES (?, ?, ?)",
                (chat_id, title, message.from_user.id))
    conn.commit()
    conn.close()
    await message.answer(f"Группа '{title}' добавлена.", reply_markup=back_to_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "admin_rules")
async def admin_rules_start(callback: types.CallbackQuery, state: FSMContext):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM chats")
    groups = cur.fetchall()
    conn.close()
    if not groups:
        await callback.message.edit_text("Нет добавленных групп.", reply_markup=back_to_admin_keyboard())
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=g['title'], callback_data=f"setrules_{g['id']}")] for g in groups
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    await callback.message.edit_text("Выберите группу:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("setrules_"))
async def admin_rules_choose_group(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split('_')[1])
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text("Отправьте новый текст правил:")
    await state.set_state(SetRules.waiting_for_text)
    await callback.answer()

@router.message(SetRules.waiting_for_text, F.chat.type == "private")
async def admin_rules_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data['chat_id']
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE chats SET rules_text = ? WHERE id = ?", (message.text, chat_id))
    conn.commit()
    conn.close()
    await message.answer("Правила обновлены!", reply_markup=back_to_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "admin_admins")
async def admin_admins_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Управление администраторами:", reply_markup=admin_admins_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    await callback.message.edit_text("Админ-панель:", reply_markup=admin_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "add_admin")
async def add_admin(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте Telegram ID нового администратора:")
    await state.set_state(AddAdmin.waiting_for_user_id)
    await callback.answer()

@router.message(AddAdmin.waiting_for_user_id, F.chat.type == "private")
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    user_id = int(message.text)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (id, first_name) VALUES (?, 'Admin')", (user_id,))
    cur.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, 'admin')", (user_id,))
    conn.commit()
    conn.close()
    await message.answer(f"Пользователь {user_id} добавлен как администратор.", reply_markup=back_to_admin_keyboard())
    await state.clear()

@router.callback_query(F.data == "del_admin")
async def del_admin(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте Telegram ID администратора для удаления:")
    await state.set_state(DelAdmin.waiting_for_user_id)
    await callback.answer()

@router.message(DelAdmin.waiting_for_user_id, F.chat.type == "private")
async def process_del_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом.")
        return
    user_id = int(message.text)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await message.answer(f"Пользователь {user_id} удалён из администраторов.", reply_markup=back_to_admin_keyboard())
    await state.clear()

# Команда /start в личке
@router.message(Command("start"), F.chat.type == "private")
async def cmd_start_private(message: types.Message):
    await message.answer(
        "Привет! Я бот для рабочего чата Minecraft.\n"
        "Используйте /admin для доступа к админ-панели."
    )