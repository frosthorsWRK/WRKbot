# keyboards.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список групп", callback_data="admin_groups")],
        [InlineKeyboardButton(text="➕ Добавить группу", callback_data="admin_add_group")],
        [InlineKeyboardButton(text="⚙️ Настройки правил", callback_data="admin_rules")],
        [InlineKeyboardButton(text="👥 Администраторы", callback_data="admin_admins")],
    ])

def admin_admins_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="del_admin")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])

def back_to_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])