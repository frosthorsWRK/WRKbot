# db.py

import sqlite3
from datetime import datetime

DB_PATH = 'bot.db'

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY,
            title TEXT,
            rules_text TEXT DEFAULT 'Правила не установлены.',
            added_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(added_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            user_id INTEGER,
            chat_id INTEGER,
            message_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, chat_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        );

        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_id INTEGER,
            target_id INTEGER,
            chat_id INTEGER,
            vote_type INTEGER CHECK(vote_type IN (1, -1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(voter_id, target_id, chat_id),
            FOREIGN KEY(voter_id) REFERENCES users(id),
            FOREIGN KEY(target_id) REFERENCES users(id),
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            target_id INTEGER,
            chat_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new',
            FOREIGN KEY(reporter_id) REFERENCES users(id),
            FOREIGN KEY(target_id) REFERENCES users(id),
            FOREIGN KEY(chat_id) REFERENCES chats(id)
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    ''')
    conn.commit()
    # Добавляем владельца как администратора, если его ещё нет
    from config import OWNER_ID
    cur.execute("INSERT OR IGNORE INTO users (id, first_name) VALUES (?, 'Owner')", (OWNER_ID,))
    cur.execute("INSERT OR IGNORE INTO admins (user_id, role) VALUES (?, 'owner')", (OWNER_ID,))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    rows = cur.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]

def is_global_admin(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None