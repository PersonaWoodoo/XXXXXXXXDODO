import asyncio
import html
import json
import random
import sqlite3
import string
import time
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Tuple

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile,
    ChatMemberUpdated
)
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_NOT_MEMBER, MEMBER

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8365761672:AAFNA79Or2QnBVmHdOL465Rp0Ta89nF7DPA"  # ЗАМЕНИ НА СВОЙ ТОКЕН!

# ID администраторов
ADMIN_IDS = [8478884644]  # Твой ID
OWNER_IDS = [8478884644]  # Полный доступ

# Настройки бота
DB_PATH = "data.db"
START_BALANCE = 100.0
MIN_BET = 10.0
CURRENCY_NAME = "UNIT"
CURRENCY_ICON = "💰"
BONUS_COOLDOWN_SECONDS = 12 * 60 * 60
BONUS_REWARD_MIN = 150
BONUS_REWARD_MAX = 350

# Банковские депозиты
BANK_TERMS = {
    7: 0.03,   # +3% за 7 дней
    14: 0.07,  # +7% за 14 дней
    30: 0.18,  # +18% за 30 дней
}

# Рулетка
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# Башня
TOWER_MULTIPLIERS = [1.20, 1.48, 1.86, 2.35, 2.95, 3.75, 4.85, 6.15]
GOLD_MULTIPLIERS = [1.15, 1.35, 1.62, 2.0, 2.55, 3.25, 4.2]
DIAMOND_MULTIPLIERS = [1.12, 1.28, 1.48, 1.72, 2.02, 2.4, 2.92, 3.6]

# Мины
MINES_GRID_SIZE = 25
MINES_DEFAULT_COUNT = 6
MINES_MULTIPLIER_STEP = 1.15

# Краш
CRASH_HOUSE_EDGE = 11

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== ВРЕМЕННЫЕ ХРАНИЛИЩА ====================
TOWER_GAMES: Dict[int, Dict[str, Any]] = {}
GOLD_GAMES: Dict[int, Dict[str, Any]] = {}
DIAMOND_GAMES: Dict[int, Dict[str, Any]] = {}
MINES_GAMES: Dict[int, Dict[str, Any]] = {}
OCHKO_GAMES: Dict[int, Dict[str, Any]] = {}
CRASH_COOLDOWNS: Dict[int, float] = {}
game_state: Dict[int, Dict[str, Any]] = {}
last_user_bets_cache: Dict[int, Dict[int, List[Dict]]] = {}
user_game_locks: Dict[str, asyncio.Lock] = {}

# ==================== УТИЛИТЫ ====================

def parse_amount_with_suffix(text: str) -> float:
    """Парсит числа с суффиксами k, kk, kkk, kkkk, kkkkk"""
    raw = str(text or "").strip().lower().replace(" ", "").replace(",", ".")
    
    suffixes = {
        "kkkkk": 1000000000,
        "kkkk": 1000000,
        "kkk": 1000,
        "kk": 1000000,
        "k": 1000,
    }
    
    for suffix, multiplier in suffixes.items():
        if raw.endswith(suffix):
            num_part = raw[:-len(suffix)]
            try:
                return round(float(num_part) * multiplier, 2)
            except:
                continue
    
    try:
        return round(float(raw), 2)
    except:
        raise ValueError("Invalid amount")

def fmt_money(value: float) -> str:
    """Форматирует число с суффиксами"""
    value = round(float(value), 2)
    abs_value = abs(value)
    
    if abs_value >= 1000000000:
        return f"{value/1000000000:.2f}kkkkk".rstrip("0").rstrip(".").rstrip(".")
    elif abs_value >= 1000000:
        return f"{value/1000000:.2f}kk".rstrip("0").rstrip(".").rstrip(".")
    elif abs_value >= 1000:
        return f"{value/1000:.2f}k".rstrip("0").rstrip(".").rstrip(".")
    elif abs(value - int(value)) < 1e-9:
        return str(int(value))
    else:
        return f"{value:.2f}".rstrip("0").rstrip(".")

def get_user_name(user_id: int, first_name: str = "", last_name: str = "") -> str:
    """Получает имя пользователя"""
    if first_name:
        name = first_name
        if last_name:
            name += f" {last_name}"
        return html.escape(name.strip() or f"User{user_id}")
    return f"User{user_id}"

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

def now_ts() -> int:
    return int(time.time())

def fmt_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}ч {m}м"
    if m > 0:
        return f"{m}м {s}с"
    return f"{s}с"

def escape_html(text: str) -> str:
    return html.escape(str(text or ""), quote=False)

def mention_user(user_id: int, name: str = None) -> str:
    label = escape_html(name or f"Игрок {user_id}")
    return f'<a href="tg://user?id={user_id}">{label}</a>'

# ==================== БАЗА ДАННЫХ ====================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация всех таблиц"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            coins REAL DEFAULT 100,
            name TEXT DEFAULT '',
            total_bets INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            lost_coins REAL DEFAULT 0,
            won_coins REAL DEFAULT 0,
            status INTEGER DEFAULT 0,
            checks TEXT DEFAULT '[]',
            created_at INTEGER DEFAULT 0
        )
    ''')
    
    # Ставки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            bet_amount REAL,
            choice TEXT,
            outcome TEXT,
            win INTEGER,
            payout REAL,
            ts INTEGER
        )
    ''')
    
    # Чеки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            creator_id TEXT,
            per_user REAL,
            remaining INTEGER,
            claimed TEXT,
            password TEXT
        )
    ''')
    
    # Промокоды
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward REAL,
            claimed TEXT,
            remaining_activations INTEGER
        )
    ''')
    
    # Депозиты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bank_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            principal REAL,
            rate REAL,
            term_days INTEGER,
            opened_at INTEGER,
            status TEXT,
            closed_at INTEGER
        )
    ''')
    
    # Группы (казна)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_kazna (
            chat_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            reward_per_user INTEGER DEFAULT 0,
            status INTEGER DEFAULT 0
        )
    ''')
    
    # Приглашённые
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invited_users (
            chat_id INTEGER,
            invited_id INTEGER,
            PRIMARY KEY (chat_id, invited_id)
        )
    ''')
    
    # Настройки групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_settings (
            chat_id INTEGER PRIMARY KEY,
            roulette_status INTEGER DEFAULT 1,
            crash_status INTEGER DEFAULT 1,
            mines_status INTEGER DEFAULT 1,
            casino_balance INTEGER DEFAULT 0
        )
    ''')
    
    # Администраторы групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_admins (
            chat_id INTEGER,
            user_id INTEGER,
            role TEXT,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')
    
    # JSON данные
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS json_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Настройки игр
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mine_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Игры в мины
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mine_games (
            user_id INTEGER,
            chat_id INTEGER,
            message_id INTEGER,
            bet REAL,
            mines_map TEXT,
            revealed_cells TEXT,
            last_action TEXT,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    
    # Ставки рулетки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_bets (
            user_id INTEGER,
            chat_id INTEGER,
            user_name TEXT,
            amount INTEGER,
            type TEXT,
            value TEXT
        )
    ''')
    
    # История рулетки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            number INTEGER,
            color TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Турнирная статистика
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tournament_stats (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            profit REAL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def ensure_user(user_id: int, name: str = ""):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, coins, name, created_at) VALUES (?, ?, ?, ?)",
            (str(user_id), START_BALANCE, name, now_ts())
        )
        conn.commit()
    finally:
        conn.close()

def get_user(user_id: int) -> sqlite3.Row:
    conn = get_db()
    try:
        ensure_user(user_id)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        return row
    finally:
        conn.close()

def update_balance(user_id: int, amount: float) -> float:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE id = ?",
            (round(amount, 2), str(user_id))
        )
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return round(float(row["coins"]), 2)
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def add_bet_record(user_id: int, bet: float, payout: float, choice: str, outcome: str, win: bool):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO bets (user_id, bet_amount, choice, outcome, win, payout, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(user_id), round(bet, 2), choice, outcome, 1 if win else 0, round(payout, 2), now_ts())
        )
        conn.commit()
    finally:
        conn.close()

def get_top_users(limit: int = 15) -> List[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, coins, name FROM users ORDER BY coins DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"id": int(row["id"]), "coins": float(row["coins"]), "name": row["name"] or ""} for row in rows]
    finally:
        conn.close()

def get_user_stats(user_id: int) -> Dict[str, Any]:
    conn = get_db()
    try:
        user = get_user(user_id)
        total_bets = conn.execute("SELECT COUNT(*) FROM bets WHERE user_id = ?", (str(user_id),)).fetchone()[0]
        total_wins = conn.execute("SELECT COUNT(*) FROM bets WHERE user_id = ? AND win = 1", (str(user_id),)).fetchone()[0]
        total_net = conn.execute("SELECT COALESCE(SUM(payout - bet_amount), 0) FROM bets WHERE user_id = ?", (str(user_id),)).fetchone()[0]
        
        return {
            "coins": float(user["coins"]),
            "total_bets": total_bets,
            "total_wins": total_wins,
            "total_net": total_net
        }
    finally:
        conn.close()

# ==================== КЛАВИАТУРЫ ====================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="menu_games"),
         InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton(text="🏦 Банк", callback_data="menu_bank"),
         InlineKeyboardButton(text="🧾 Чеки", callback_data="menu_checks")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="menu_promo"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="menu_top")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")]
    ])

def games_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Рулетка", callback_data="game_roulette"),
         InlineKeyboardButton(text="📈 Краш", callback_data="game_crash")],
        [InlineKeyboardButton(text="🗼 Башня", callback_data="game_tower"),
         InlineKeyboardButton(text="🥇 Золото", callback_data="game_gold")],
        [InlineKeyboardButton(text="💎 Алмазы", callback_data="game_diamond"),
         InlineKeyboardButton(text="💣 Мины", callback_data="game_mines")],
        [InlineKeyboardButton(text="🎴 Очко", callback_data="game_ochko"),
         InlineKeyboardButton(text="🎲 Кубик", callback_data="game_cube")],
        [InlineKeyboardButton(text="🎯 Кости", callback_data="game_dice"),
         InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football")],
        [InlineKeyboardButton(text="🏀 Баскет", callback_data="game_basket"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="menu_back")]
    ])

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    name = message.from_user.full_name
    ensure_user(user_id, name)
    
    await message.answer(
        f"🎮 <b>Добро пожаловать в игровой бот!</b>\n\n"
        f"👤 {mention_user(user_id, name)}\n"
        f"💎 Начальный баланс: {fmt_money(START_BALANCE)}\n\n"
        f"<i>Используй кнопки ниже для навигации</i>",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "<b>Основные команды:</b>\n"
        "• /start - Главное меню\n"
        "• /balance или /bal - Баланс\n"
        "• /bonus - Ежедневный бонус\n"
        "• /top - Топ игроков\n"
        "• /profile - Мой профиль\n\n"
        "<b>Игры:</b>\n"
        "• /games - Список игр\n\n"
        "<b>Экономика:</b>\n"
        "• /bank - Банк (депозиты)\n"
        "• /checks - Система чеков\n"
        "• /promo КОД - Активация промокода\n\n"
        "<i>Поддерживаются суффиксы: 1k = 1000, 1kk = 1,000,000</i>",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )

@router.message(Command("balance"))
@router.message(Command("bal"))
async def cmd_balance(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"💰 <b>Ваш баланс</b>\n\n"
        f"{mention_user(message.from_user.id, message.from_user.full_name)}\n"
        f"💎 {fmt_money(user['coins'])} {CURRENCY_ICON}",
        parse_mode="HTML"
    )

@router.message(Command("bonus"))
async def cmd_bonus(message: Message):
    user_id = message.from_user.id
    now = now_ts()
    
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM json_data WHERE key = ?", (f"bonus_{user_id}",)).fetchone()
        last_bonus = int(row["value"]) if row else 0
        
        if now - last_bonus < BONUS_COOLDOWN_SECONDS:
            left = BONUS_COOLDOWN_SECONDS - (now - last_bonus)
            await message.answer(f"⏳ Бонус уже получен!\nСледующий через: {fmt_time(left)}")
            return
        
        reward = random.randint(BONUS_REWARD_MIN, BONUS_REWARD_MAX)
        update_balance(user_id, reward)
        
        conn.execute(
            "INSERT OR REPLACE INTO json_data (key, value) VALUES (?, ?)",
            (f"bonus_{user_id}", str(now))
        )
        conn.commit()
        
        await message.answer(
            f"🎁 <b>Ежедневный бонус!</b>\n\n"
            f"💰 Получено: {fmt_money(reward)} {CURRENCY_ICON}\n"
            f"💎 Новый баланс: {fmt_money(get_user(user_id)['coins'])}",
            parse_mode="HTML"
        )
    finally:
        conn.close()

@router.message(Command("top"))
async def cmd_top(message: Message):
    users = get_top_users(15)
    
    if not users:
        await message.answer("🏆 <b>Топ игроков</b>\n\n<blockquote>Пока нет игроков</blockquote>", parse_mode="HTML")
        return
    
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    lines = ["🌟 <b>ТОП ИГРОКОВ ПО БАЛАНСУ</b> 🌟", ""]
    
    for idx, user in enumerate(users):
        medal = medals.get(idx, f"{idx+1}️⃣")
        user_name = user["name"] or f"Игрок {user['id']}"
        if len(user_name) > 20:
            user_name = user_name[:18] + ".."
        
        balance_fmt = fmt_money(user["coins"])
        lines.append(f"{medal} <b>{user_name}</b> — {balance_fmt} {CURRENCY_ICON}")
    
    lines.append("")
    lines.append("<i>Пополни баланс и попади в топ!</i>")
    
    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    stats = get_user_stats(user_id)
    
    win_rate = (stats["total_wins"] / stats["total_bets"] * 100) if stats["total_bets"] > 0 else 0
    
    await message.answer(
        f"👤 <b>Профиль игрока</b>\n\n"
        f"<b>Имя:</b> {mention_user(user_id, message.from_user.full_name)}\n"
        f"<b>ID:</b> <code>{user_id}</code>\n\n"
        f"💎 <b>Баланс:</b> {fmt_money(user['coins'])} {CURRENCY_ICON}\n"
        f"🎲 <b>Ставок:</b> {stats['total_bets']:,}\n"
        f"🏆 <b>Побед:</b> {stats['total_wins']:,} ({win_rate:.1f}%)\n"
        f"📈 <b>Профит:</b> {fmt_money(stats['total_net'])}",
        parse_mode="HTML"
    )

@router.message(Command("games"))
async def cmd_games(message: Message):
    await message.answer(
        "🎮 <b>Выбери игру</b>\n\n"
        "<i>Нажми на кнопку ниже, чтобы начать</i>",
        parse_mode="HTML",
        reply_markup=games_kb()
    )

# ==================== MENU CALLBACKS ====================

@router.callback_query(F.data.startswith("menu_"))
async def menu_callbacks(call: CallbackQuery):
    action = call.data.split("_")[1]
    
    if action == "games":
        await call.message.edit_text(
            "🎮 <b>Выбери игру</b>",
            parse_mode="HTML",
            reply_markup=games_kb()
        )
    elif action == "profile":
        await cmd_profile(call.message)
    elif action == "bank":
        await cmd_bank(call.message)
    elif action == "checks":
        await cmd_checks(call.message)
    elif action == "promo":
        await call.message.answer("🎟 Введите промокод: <code>/promo КОД</code>", parse_mode="HTML")
    elif action == "top":
        await cmd_top(call.message)
    elif action == "help":
        await cmd_help(call.message)
    elif action == "back":
        await call.message.edit_text(
            f"🎮 <b>Главное меню</b>\n\n"
            f"👤 {mention_user(call.from_user.id, call.from_user.full_name)}\n"
            f"💎 Баланс: {fmt_money(get_user(call.from_user.id)['coins'])} {CURRENCY_ICON}",
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    
    await call.answer()

# Продолжение в ЧАСТИ 2/2...# ==================== БАНК (ДЕПОЗИТЫ) ====================

class BankStates(StatesGroup):
    waiting_amount = State()

@router.message(Command("bank"))
async def cmd_bank(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    conn = get_db()
    try:
        active_deps = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(principal), 0) FROM bank_deposits WHERE user_id = ? AND status = 'active'",
            (str(user_id),)
        ).fetchone()
    finally:
        conn.close()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Открыть депозит", callback_data="bank_open")],
        [InlineKeyboardButton(text="📋 Мои депозиты", callback_data="bank_list")],
        [InlineKeyboardButton(text="💰 Снять зрелые", callback_data="bank_withdraw")]
    ])
    
    await message.answer(
        f"🏦 <b>Банковская система</b>\n\n"
        f"💎 Баланс: {fmt_money(user['coins'])} {CURRENCY_ICON}\n"
        f"📊 Активных депозитов: {active_deps[0] or 0}\n"
        f"💵 Сумма в работе: {fmt_money(active_deps[1] or 0)}\n\n"
        f"<b>Доступные ставки:</b>\n"
        f"• 7 дней → +3%\n"
        f"• 14 дней → +7%\n"
        f"• 30 дней → +18%",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "bank_open")
async def bank_open_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(BankStates.waiting_amount)
    await call.message.answer("💰 Введите сумму депозита (мин. 100):")
    await call.answer()

@router.message(BankStates.waiting_amount)
async def bank_amount(message: Message, state: FSMContext):
    try:
        amount = parse_amount_with_suffix(message.text)
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount < 100:
        await message.answer("❌ Минимальный депозит: 100")
        return
    
    await state.update_data(amount=amount)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 дней (+3%)", callback_data="bank_term:7")],
        [InlineKeyboardButton(text="14 дней (+7%)", callback_data="bank_term:14")],
        [InlineKeyboardButton(text="30 дней (+18%)", callback_data="bank_term:30")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bank_term:cancel")]
    ])
    
    await message.answer("📅 Выберите срок депозита:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("bank_term:"))
async def bank_term_cb(call: CallbackQuery, state: FSMContext):
    term_raw = call.data.split(":")[1]
    
    if term_raw == "cancel":
        await state.clear()
        await call.message.answer("❌ Отменено")
        await call.answer()
        return
    
    term_days = int(term_raw)
    data = await state.get_data()
    amount = data.get("amount", 0)
    
    if amount <= 0:
        await call.message.answer("❌ Ошибка, начните заново")
        await state.clear()
        await call.answer()
        return
    
    user_id = call.from_user.id
    user_balance = get_user(user_id)["coins"]
    
    if user_balance < amount:
        await call.message.answer(f"❌ Недостаточно средств! Нужно: {fmt_money(amount)}")
        await state.clear()
        await call.answer()
        return
    
    rate = BANK_TERMS[term_days]
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE users SET coins = coins - ? WHERE id = ?",
            (round(amount, 2), str(user_id))
        )
        conn.execute(
            "INSERT INTO bank_deposits (user_id, principal, rate, term_days, opened_at, status) VALUES (?, ?, ?, ?, ?, 'active')",
            (str(user_id), round(amount, 2), rate, term_days, now_ts())
        )
        conn.commit()
        
        await call.message.answer(
            f"✅ <b>Депозит открыт!</b>\n\n"
            f"💰 Сумма: {fmt_money(amount)}\n"
            f"📅 Срок: {term_days} дней\n"
            f"📈 Доходность: +{int(rate * 100)}%\n"
            f"💎 Новый баланс: {fmt_money(get_user(user_id)['coins'])}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        await call.message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()
        await state.clear()
    
    await call.answer()

@router.callback_query(F.data == "bank_list")
async def bank_list_cb(call: CallbackQuery):
    user_id = call.from_user.id
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM bank_deposits WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (str(user_id),)
        ).fetchall()
        
        if not rows:
            await call.message.answer("📭 У вас нет депозитов")
            await call.answer()
            return
        
        lines = ["📋 <b>Ваши депозиты</b>", ""]
        for row in rows:
            opened = int(row["opened_at"])
            term = int(row["term_days"])
            unlock = opened + term * 86400
            now = now_ts()
            
            if row["status"] == "active":
                if now >= unlock:
                    status = "✅ Готов к выводу"
                else:
                    left = unlock - now
                    status = f"⏳ Осталось: {fmt_time(left)}"
            else:
                status = "✅ Закрыт"
            
            lines.append(
                f"#{row['id']} | {fmt_money(row['principal'])} | {term}д | +{int(row['rate'] * 100)}% | {status}"
            )
        
        await call.message.answer("\n".join(lines), parse_mode="HTML")
    finally:
        conn.close()
    
    await call.answer()

@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw_cb(call: CallbackQuery):
    user_id = call.from_user.id
    now = now_ts()
    closed_count = 0
    total_payout = 0
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT * FROM bank_deposits WHERE user_id = ? AND status = 'active'",
            (str(user_id),)
        ).fetchall()
        
        for row in rows:
            unlock_ts = int(row["opened_at"]) + int(row["term_days"]) * 86400
            if now >= unlock_ts:
                payout = round(float(row["principal"]) * (1 + float(row["rate"])), 2)
                total_payout += payout
                closed_count += 1
                conn.execute(
                    "UPDATE bank_deposits SET status = 'closed', closed_at = ? WHERE id = ?",
                    (now, int(row["id"]))
                )
        
        if total_payout > 0:
            update_balance(user_id, total_payout)
            conn.commit()
            await call.message.answer(
                f"✅ <b>Вывод депозитов</b>\n\n"
                f"📊 Закрыто: {closed_count}\n"
                f"💰 Получено: {fmt_money(total_payout)}",
                parse_mode="HTML"
            )
        else:
            await call.message.answer("📭 Нет депозитов для вывода")
    except Exception as e:
        conn.rollback()
        await call.message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()
    
    await call.answer()

# ==================== ЧЕКИ ====================

class CheckStates(StatesGroup):
    waiting_amount = State()
    waiting_count = State()
    waiting_code = State()

@router.message(Command("checks"))
async def cmd_checks(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать чек", callback_data="check_create")],
        [InlineKeyboardButton(text="💸 Активировать чек", callback_data="check_claim")],
        [InlineKeyboardButton(text="📄 Мои чеки", callback_data="check_my")]
    ])
    
    await message.answer(
        "🧾 <b>Система чеков</b>\n\n"
        "Создавайте чеки для передачи монет другим игрокам",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "check_create")
async def check_create_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_amount)
    await call.message.answer("💰 Введите сумму на 1 активацию:")
    await call.answer()

@router.message(CheckStates.waiting_amount)
async def check_amount(message: Message, state: FSMContext):
    try:
        amount = parse_amount_with_suffix(message.text)
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount < 10:
        await message.answer("❌ Минимум: 10")
        return
    
    await state.update_data(amount=amount)
    await state.set_state(CheckStates.waiting_count)
    await message.answer("🔢 Введите количество активаций (1-100):")

@router.message(CheckStates.waiting_count)
async def check_count(message: Message, state: FSMContext):
    try:
        count = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    if count < 1 or count > 100:
        await message.answer("❌ От 1 до 100")
        return
    
    data = await state.get_data()
    amount = data["amount"]
    total = amount * count
    
    user_balance = get_user(message.from_user.id)["coins"]
    
    if user_balance < total:
        await message.answer(f"❌ Недостаточно средств! Нужно: {fmt_money(total)}")
        await state.clear()
        return
    
    # Генерация кода чека
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE users SET coins = coins - ? WHERE id = ?",
            (total, str(message.from_user.id))
        )
        conn.execute(
            "INSERT INTO checks (code, creator_id, per_user, remaining, claimed) VALUES (?, ?, ?, ?, ?)",
            (code, str(message.from_user.id), amount, count, "[]")
        )
        conn.commit()
        
        await message.answer(
            f"✅ <b>Чек создан!</b>\n\n"
            f"🔑 Код: <code>{code}</code>\n"
            f"💰 Сумма: {fmt_money(amount)}\n"
            f"🎟 Активаций: {count}\n"
            f"💎 Заморожено: {fmt_money(total)}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()
        await state.clear()

@router.callback_query(F.data == "check_claim")
async def check_claim_cb(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_code)
    await call.message.answer("🔑 Введите код чека:")
    await call.answer()

@router.message(CheckStates.waiting_code)
async def check_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM checks WHERE code = ?", (code,)).fetchone()
        
        if not row:
            await message.answer("❌ Чек не найден!")
            await state.clear()
            return
        
        if row["remaining"] <= 0:
            await message.answer("❌ Чек уже использован!")
            await state.clear()
            return
        
        claimed = json.loads(row["claimed"] or "[]")
        if str(message.from_user.id) in claimed:
            await message.answer("❌ Вы уже активировали этот чек!")
            await state.clear()
            return
        
        reward = row["per_user"]
        claimed.append(str(message.from_user.id))
        
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE id = ?",
            (reward, str(message.from_user.id))
        )
        conn.execute(
            "UPDATE checks SET remaining = remaining - 1, claimed = ? WHERE code = ?",
            (json.dumps(claimed), code)
        )
        conn.commit()
        
        await message.answer(
            f"✅ <b>Чек активирован!</b>\n\n"
            f"💰 Получено: {fmt_money(reward)}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()
        await state.clear()

@router.callback_query(F.data == "check_my")
async def check_my_cb(call: CallbackQuery):
    user_id = call.from_user.id
    
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT code, per_user, remaining FROM checks WHERE creator_id = ? ORDER BY rowid DESC LIMIT 10",
            (str(user_id),)
        ).fetchall()
        
        if not rows:
            await call.message.answer("📭 У вас нет созданных чеков")
            await call.answer()
            return
        
        lines = ["📋 <b>Ваши чеки</b>", ""]
        for row in rows:
            lines.append(f"🔑 <code>{row['code']}</code> | {fmt_money(row['per_user'])} | осталось: {row['remaining']}")
        
        await call.message.answer("\n".join(lines), parse_mode="HTML")
    finally:
        conn.close()
    
    await call.answer()

# ==================== ПРОМОКОДЫ ====================

class PromoStates(StatesGroup):
    waiting_code = State()

@router.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext):
    parts = message.text.split()
    if len(parts) >= 2:
        code = parts[1].upper()
        await process_promo(message, code)
    else:
        await state.set_state(PromoStates.waiting_code)
        await message.answer("🎟 Введите промокод:")

@router.message(PromoStates.waiting_code)
async def promo_code(message: Message, state: FSMContext):
    await process_promo(message, message.text.strip().upper())
    await state.clear()

async def process_promo(message: Message, code: str):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM promos WHERE name = ?", (code,)).fetchone()
        
        if not row:
            await message.answer("❌ Промокод не найден!")
            return
        
        if row["remaining_activations"] <= 0:
            await message.answer("❌ Промокод уже закончился!")
            return
        
        claimed = json.loads(row["claimed"] or "[]")
        if str(message.from_user.id) in claimed:
            await message.answer("❌ Вы уже активировали этот промокод!")
            return
        
        reward = row["reward"]
        claimed.append(str(message.from_user.id))
        
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE id = ?",
            (reward, str(message.from_user.id))
        )
        conn.execute(
            "UPDATE promos SET claimed = ?, remaining_activations = remaining_activations - 1 WHERE name = ?",
            (json.dumps(claimed), code)
        )
        conn.commit()
        
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"🎁 Получено: {fmt_money(reward)}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()

@router.message(Command("create_promo"))
async def create_promo_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("📝 Использование: /create_promo КОД СУММА АКТИВАЦИИ\nПример: /create_promo HELLO 1000 50")
        return
    
    code = parts[1].upper()
    try:
        reward = parse_amount_with_suffix(parts[2])
        activations = int(parts[3])
    except:
        await message.answer("❌ Неверные параметры!")
        return
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO promos (name, reward, claimed, remaining_activations) VALUES (?, ?, ?, ?)",
            (code, reward, "[]", activations)
        )
        conn.commit()
        
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🔑 Код: <code>{code}</code>\n"
            f"💰 Награда: {fmt_money(reward)}\n"
            f"🎟 Активаций: {activations}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()

# ==================== КАЗНА (НАГРАДА ЗА ПРИГЛАШЕНИЯ) ====================

@router.message(F.text.lower() == "+казна")
async def enable_kazna(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    member = await message.chat.get_member(message.from_user.id)
    if member.status != "creator":
        await message.reply("❌ Только владелец группы может включить казну!")
        return
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO group_kazna (chat_id, balance, reward_per_user, status) VALUES (?, 0, 0, 1)",
            (message.chat.id,)
        )
        conn.commit()
        await message.reply("✅ <b>Казна включена!</b>\n\nУстановите награду: установить 500", parse_mode="HTML")
    finally:
        conn.close()

@router.message(F.text.lower() == "-казна")
async def disable_kazna(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    member = await message.chat.get_member(message.from_user.id)
    if member.status != "creator":
        await message.reply("❌ Только владелец группы может выключить казну!")
        return
    
    conn = get_db()
    try:
        conn.execute("UPDATE group_kazna SET status = 0 WHERE chat_id = ?", (message.chat.id,))
        conn.commit()
        await message.reply("⛔ <b>Казна выключена!</b>", parse_mode="HTML")
    finally:
        conn.close()

@router.message(F.text.lower().startswith("установить"))
async def set_kazna_reward(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    member = await message.chat.get_member(message.from_user.id)
    if member.status not in ["administrator", "creator"]:
        await message.reply("❌ Только админы могут менять настройки!")
        return
    
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("📝 Использование: установить 500")
        return
    
    reward = int(parts[1])
    
    conn = get_db()
    try:
        conn.execute(
            "UPDATE group_kazna SET reward_per_user = ? WHERE chat_id = ?",
            (reward, message.chat.id)
        )
        conn.commit()
        await message.reply(f"✅ Награда установлена: {fmt_money(reward)} за приглашение!", parse_mode="HTML")
    finally:
        conn.close()

@router.message(F.text.lower() == "казна")
async def show_kazna(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT balance, reward_per_user, status FROM group_kazna WHERE chat_id = ?",
            (message.chat.id,)
        ).fetchone()
        
        if not row or row["status"] == 0:
            await message.reply("❌ Казна не активирована!\nВладелец: +казна")
            return
        
        await message.reply(
            f"🏦 <b>Казна группы</b>\n\n"
            f"💰 Баланс: {fmt_money(row['balance'])}\n"
            f"🎁 Награда за 1 чел.: {fmt_money(row['reward_per_user'])}\n\n"
            f"<i>Админ: установить СУММА</i>",
            parse_mode="HTML"
        )
    finally:
        conn.close()

@router.message(F.text.lower().startswith("пополнить"))
async def deposit_kazna(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Использование: пополнить 1000")
        return
    
    try:
        amount = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    
    if user_balance < amount:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(amount)}")
        return
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE users SET coins = coins - ? WHERE id = ?",
            (amount, str(message.from_user.id))
        )
        conn.execute(
            "UPDATE group_kazna SET balance = balance + ? WHERE chat_id = ?",
            (amount, message.chat.id)
        )
        conn.commit()
        
        await message.reply(
            f"✅ <b>Казна пополнена!</b>\n\n"
            f"💰 Сумма: {fmt_money(amount)}\n"
            f"💎 Ваш баланс: {fmt_money(get_user(message.from_user.id)['coins'])}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        await message.reply(f"❌ Ошибка: {e}")
    finally:
        conn.close()

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(IS_NOT_MEMBER >> (MEMBER))))
async def on_user_added(event: ChatMemberUpdated):
    chat_id = event.chat.id
    inviter = event.from_user
    new_user = event.new_chat_member.user
    
    if new_user.is_bot or inviter.id == new_user.id:
        return
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        # Проверка казны
        kazna = conn.execute(
            "SELECT balance, reward_per_user, status FROM group_kazna WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()
        
        if not kazna or kazna["status"] == 0 or kazna["reward_per_user"] <= 0:
            conn.rollback()
            return
        
        if kazna["balance"] < kazna["reward_per_user"]:
            conn.rollback()
            return
        
        # Проверка дубликата
        already = conn.execute(
            "SELECT 1 FROM invited_users WHERE chat_id = ? AND invited_id = ?",
            (chat_id, new_user.id)
        ).fetchone()
        
        if already:
            conn.rollback()
            return
        
        # Начисление награды
        reward = kazna["reward_per_user"]
        conn.execute(
            "INSERT INTO invited_users (chat_id, invited_id) VALUES (?, ?)",
            (chat_id, new_user.id)
        )
        conn.execute(
            "UPDATE users SET coins = coins + ? WHERE id = ?",
            (reward, str(inviter.id))
        )
        conn.execute(
            "UPDATE group_kazna SET balance = balance - ? WHERE chat_id = ?",
            (reward, chat_id)
        )
        conn.commit()
        
        await event.bot.send_message(
            chat_id,
            f"👤 {mention_user(inviter.id, inviter.first_name)} пригласил {mention_user(new_user.id, new_user.first_name)}\n"
            f"💰 Награда: {fmt_money(reward)}",
            parse_mode="HTML"
        )
    except Exception as e:
        conn.rollback()
        logger.error(f"Kazna error: {e}")
    finally:
        conn.close()

# ==================== ИГРЫ: РУЛЕТКА ====================

def get_roulette_color(num: int) -> str:
    if num == 0:
        return "🟢"
    return "🔴" if num in RED_NUMBERS else "⚫"

@router.message(F.text.lower().startswith("рул"))
@router.message(F.text.lower().startswith("рулетка"))
async def roulette_bet(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ Рулетка только в группах!")
        return
    
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.reply("📝 Формат: рул 100 красное")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    choice_map = {
        "красное": "red", "кра": "red", "red": "red",
        "черное": "black", "чер": "black", "black": "black",
        "чет": "even", "четное": "even", "even": "even",
        "нечет": "odd", "нечетное": "odd", "odd": "odd",
        "зеленое": "zero", "зеро": "zero", "zero": "zero", "0": "zero"
    }
    
    choice = choice_map.get(parts[2])
    if not choice:
        await message.reply("❌ Неверный выбор! Варианты: красное, черное, чет, нечет, зеро")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    # Генерация числа
    num = random.randint(0, 36)
    color = get_roulette_color(num)
    
    # Определение победы
    win = False
    multiplier = 0
    
    if choice == "red" and color == "🔴":
        win, multiplier = True, 2
    elif choice == "black" and color == "⚫":
        win, multiplier = True, 2
    elif choice == "even" and num != 0 and num % 2 == 0:
        win, multiplier = True, 2
    elif choice == "odd" and num % 2 != 0:
        win, multiplier = True, 2
    elif choice == "zero" and num == 0:
        win, multiplier = True, 36
    
    payout = int(bet * multiplier) if win else 0
    new_balance = update_balance(message.from_user.id, payout - bet)
    add_bet_record(message.from_user.id, bet, payout, f"roulette:{choice}", f"num={num}", win)
    
    color_name = "ЗЕРО" if num == 0 else ("КРАСНОЕ" if color == "🔴" else "ЧЕРНОЕ")
    
    await message.answer(
        f"🎡 <b>Рулетка</b>\n\n"
        f"🎯 Выпало: <b>{num}</b> {color} ({color_name})\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"📊 Исход: {'✅ ПОБЕДА' if win else '❌ ПОРАЖЕНИЕ'}\n"
        f"💎 Выплата: {fmt_money(payout)}\n"
        f"💵 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

# ==================== ИГРЫ: КРАШ ====================

def generate_crash_point() -> float:
    r = random.random() * 100
    
    if r < CRASH_HOUSE_EDGE:
        return 1.00
    
    u = random.random() ** 1.5
    zone_roll = random.random() * 100
    
    if zone_roll < 65:
        lo, hi = 1.01, 1.5
    elif zone_roll < 85:
        lo, hi = 1.5, 3.0
    elif zone_roll < 95:
        lo, hi = 3.0, 10.0
    elif zone_roll < 98.5:
        lo, hi = 10.0, 30.0
    else:
        lo, hi = 30.0, 200.0
    
    log_lo = math.log(lo)
    log_hi = math.log(hi)
    result = math.exp(log_lo + u * (log_hi - log_lo))
    result *= random.uniform(0.96, 1.01)
    
    return round(max(min(result, 200.0), 1.0), 2)

@router.message(F.text.lower().startswith("краш"))
async def crash_game(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ Краш только в группах!")
        return
    
    user_id = message.from_user.id
    
    # Антифлуд
    now = time.time()
    if user_id in CRASH_COOLDOWNS and now - CRASH_COOLDOWNS[user_id] < 3:
        await message.reply("⏳ Подождите 3 секунды перед следующей игрой!")
        return
    CRASH_COOLDOWNS[user_id] = now
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Формат: краш 100 2.5")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
        target = float(parts[2].replace(",", "."))
    except:
        await message.reply("❌ Неверные значения!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    if target < 1.01 or target > 10:
        await message.reply("❌ Множитель от 1.01 до 10")
        return
    
    user_balance = get_user(user_id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    crash_point = generate_crash_point()
    win = crash_point >= target
    payout = int(bet * target) if win else 0
    
    new_balance = update_balance(user_id, payout - bet)
    add_bet_record(user_id, bet, payout, f"crash:{target}", f"crash={crash_point}", win)
    
    await message.answer(
        f"📈 <b>КРАШ</b>\n\n"
        f"🎯 Ваш множитель: {target}x\n"
        f"💥 Краш на: {crash_point}x\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"📊 Исход: {'✅ ПОБЕДА' if win else '❌ ПОРАЖЕНИЕ'}\n"
        f"💎 Выплата: {fmt_money(payout)}\n"
        f"💵 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

# ==================== ИГРЫ: МИНЫ ====================

def generate_mines_field(size: int = 25, mines_count: int = 6) -> List[int]:
    field = [0] * size
    mines = random.sample(range(size), mines_count)
    for m in mines:
        field[m] = 1
    return field

def get_mines_multiplier(opened: int, mines: int, total: int = 25) -> float:
    safe = total - mines
    if opened <= 0:
        return 1.0
    return round((total / safe) ** opened * 0.97, 2)

@router.message(F.text.lower().startswith("мины"))
async def mines_start(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ Мины только в группах!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Формат: мины 100")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    field = generate_mines_field(MINES_GRID_SIZE, MINES_DEFAULT_COUNT)
    
    # Сохраняем игру
    MINES_GAMES[message.from_user.id] = {
        "bet": bet,
        "field": field,
        "opened": [],
        "chat_id": message.chat.id
    }
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for i in range(0, MINES_GRID_SIZE, 5):
        row = []
        for j in range(5):
            idx = i + j
            row.append(InlineKeyboardButton(text="❓", callback_data=f"mines_cell:{idx}"))
        keyboard.inline_keyboard.append(row)
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="💰 Забрать", callback_data="mines_cashout")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="mines_cancel")])
    
    await message.answer(
        f"💣 <b>МИНЫ</b>\n\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"💣 Мин на поле: {MINES_DEFAULT_COUNT}\n"
        f"🔓 Безопасных: {MINES_GRID_SIZE - MINES_DEFAULT_COUNT}\n\n"
        f"<i>Открывай клетки и забирай выигрыш!</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("mines_"))
async def mines_callback(call: CallbackQuery):
    user_id = call.from_user.id
    game = MINES_GAMES.get(user_id)
    
    if not game:
        await call.answer("Игра не найдена!", show_alert=True)
        return
    
    action = call.data.split("_")[1]
    
    if action == "cell":
        idx = int(call.data.split(":")[1])
        
        if idx in game["opened"]:
            await call.answer("Клетка уже открыта!")
            return
        
        if game["field"][idx] == 1:  # Попали на мину
            new_balance = update_balance(user_id, -game["bet"])
            add_bet_record(user_id, game["bet"], 0, "mines", f"explode_at_{idx}", False)
            
            # Показываем все мины
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for i in range(0, MINES_GRID_SIZE, 5):
                row = []
                for j in range(5):
                    cell_idx = i + j
                    if game["field"][cell_idx] == 1:
                        row.append(InlineKeyboardButton(text="💣", callback_data="mines_noop"))
                    elif cell_idx in game["opened"]:
                        row.append(InlineKeyboardButton(text="✅", callback_data="mines_noop"))
                    else:
                        row.append(InlineKeyboardButton(text="◻️", callback_data="mines_noop"))
                keyboard.inline_keyboard.append(row)
            
            await call.message.edit_text(
                f"💥 <b>ВЗРЫВ!</b>\n\n"
                f"💰 Потеряно: {fmt_money(game['bet'])}\n"
                f"💎 Новый баланс: {fmt_money(new_balance)}",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            MINES_GAMES.pop(user_id, None)
            await call.answer("💥 БОМБА!")
            return
        
        # Алмаз
        game["opened"].append(idx)
        mult = get_mines_multiplier(len(game["opened"]), MINES_DEFAULT_COUNT, MINES_GRID_SIZE)
        potential = int(game["bet"] * mult)
        
        # Обновляем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for i in range(0, MINES_GRID_SIZE, 5):
            row = []
            for j in range(5):
                cell_idx = i + j
                if cell_idx in game["opened"]:
                    row.append(InlineKeyboardButton(text="✅", callback_data="mines_noop"))
                else:
                    row.append(InlineKeyboardButton(text="❓", callback_data=f"mines_cell:{cell_idx}"))
            keyboard.inline_keyboard.append(row)
        
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"💰 Забрать {fmt_money(potential)}", callback_data="mines_cashout")])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="mines_cancel")])
        
        # Проверка на победу (все безопасные открыты)
        safe_opened = len([x for x in game["opened"] if game["field"][x] == 0])
        total_safe = MINES_GRID_SIZE - MINES_DEFAULT_COUNT
        
        if safe_opened >= total_safe:
            payout = int(game["bet"] * mult)
            new_balance = update_balance(user_id, payout - game["bet"])
            add_bet_record(user_id, game["bet"], payout, "mines", "all_safe", True)
            
            await call.message.edit_text(
                f"🎉 <b>ПОБЕДА!</b>\n\n"
                f"💰 Ставка: {fmt_money(game['bet'])}\n"
                f"💎 Выигрыш: {fmt_money(payout)}\n"
                f"📈 Новый баланс: {fmt_money(new_balance)}",
                parse_mode="HTML"
            )
            MINES_GAMES.pop(user_id, None)
            await call.answer("🎉 ПОБЕДА!")
            return
        
        await call.message.edit_text(
            f"💣 <b>МИНЫ</b>\n\n"
            f"💰 Ставка: {fmt_money(game['bet'])}\n"
            f"💎 Открыто: {len(game['opened'])}/{total_safe}\n"
            f"📈 Множитель: {mult}x\n"
            f"💵 Потенциал: {fmt_money(potential)}",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await call.answer("💎 Алмаз!")
    
    elif action == "cashout":
        mult = get_mines_multiplier(len(game["opened"]), MINES_DEFAULT_COUNT, MINES_GRID_SIZE)
        payout = int(game["bet"] * mult)
        
        if payout <= 0:
            await call.answer("❌ Нет выигрыша!")
            return
        
        new_balance = update_balance(user_id, payout - game["bet"])
        add_bet_record(user_id, game["bet"], payout, "mines", "cashout", True)
        
        await call.message.edit_text(
            f"✅ <b>ВЫИГРЫШ ЗАБРАН!</b>\n\n"
            f"💰 Ставка: {fmt_money(game['bet'])}\n"
            f"💎 Получено: {fmt_money(payout)}\n"
            f"📈 Новый баланс: {fmt_money(new_balance)}",
            parse_mode="HTML"
        )
        MINES_GAMES.pop(user_id, None)
        await call.answer("💰 Выигрыш забран!")
    
    elif action == "cancel":
        new_balance = update_balance(user_id, game["bet"])
        await call.message.edit_text(
            f"❌ <b>Игра отменена</b>\n\n"
            f"💰 Ставка возвращена: {fmt_money(game['bet'])}\n"
            f"💎 Новый баланс: {fmt_money(new_balance)}",
            parse_mode="HTML"
        )
        MINES_GAMES.pop(user_id, None)
        await call.answer("❌ Отменено")

@router.callback_query(F.data == "mines_noop")
async def mines_noop(call: CallbackQuery):
    await call.answer()

# ==================== ИГРЫ: БАШНЯ, ЗОЛОТО, АЛМАЗЫ ====================

# КОМАНДА ДЛЯ БАШНИ
@router.message(F.text.lower().startswith("башня"))
async def tower_game(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Формат: башня 100")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    update_balance(message.from_user.id, -bet)
    
    TOWER_GAMES[message.from_user.id] = {
        "bet": bet,
        "level": 0
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣", callback_data="tower_pick:1"),
         InlineKeyboardButton(text="2️⃣", callback_data="tower_pick:2"),
         InlineKeyboardButton(text="3️⃣", callback_data="tower_pick:3")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="tower_cashout")]
    ])
    
    await message.answer(
        f"🗼 <b>БАШНЯ</b>\n\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"🏆 Этаж: 0/8\n"
        f"📈 Текущий множитель: x1.0\n"
        f"💎 Потенциал: {fmt_money(bet)}\n\n"
        f"<i>Выберите секцию (1, 2 или 3)</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("tower_"))
async def tower_callback(call: CallbackQuery):
    user_id = call.from_user.id
    game = TOWER_GAMES.get(user_id)
    
    if not game:
        await call.answer("Игра не найдена!", show_alert=True)
        return
    
    action = call.data.split("_")[1]
    
    if action == "pick":
        safe = random.randint(1, 3)
        chosen = int(call.data.split(":")[1])
        
        if chosen != safe:
            await call.message.edit_text(
                f"💥 <b>ПОРАЖЕНИЕ!</b>\n\n"
                f"💰 Потеряно: {fmt_money(game['bet'])}\n"
                f"🏆 Пройдено этажей: {game['level']}",
                parse_mode="HTML"
            )
            TOWER_GAMES.pop(user_id, None)
            await call.answer("💥 Вы проиграли!")
            return
        
        game["level"] += 1
        
        if game["level"] >= len(TOWER_MULTIPLIERS):
            mult = TOWER_MULTIPLIERS[-1]
            payout = int(game["bet"] * mult)
            update_balance(user_id, payout)
            add_bet_record(user_id, game["bet"], payout, "tower", "complete", True)
            
            await call.message.edit_text(
                f"🎉 <b>ПОБЕДА!</b>\n\n"
                f"🏆 Пройдено этажей: {game['level']}/{len(TOWER_MULTIPLIERS)}\n"
                f"📈 Множитель: {mult}x\n"
                f"💎 Выигрыш: {fmt_money(payout)}",
                parse_mode="HTML"
            )
            TOWER_GAMES.pop(user_id, None)
            await call.answer("🎉 ПОБЕДА!")
            return
        
        mult = TOWER_MULTIPLIERS[game["level"] - 1]
        potential = int(game["bet"] * mult)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", callback_data="tower_pick:1"),
             InlineKeyboardButton(text="2️⃣", callback_data="tower_pick:2"),
             InlineKeyboardButton(text="3️⃣", callback_data="tower_pick:3")],
            [InlineKeyboardButton(text=f"💰 Забрать {fmt_money(potential)}", callback_data="tower_cashout")]
        ])
        
        await call.message.edit_text(
            f"🗼 <b>БАШНЯ</b>\n\n"
            f"💰 Ставка: {fmt_money(game['bet'])}\n"
            f"🏆 Этаж: {game['level']}/{len(TOWER_MULTIPLIERS)}\n"
            f"📈 Текущий множитель: {mult}x\n"
            f"💎 Потенциал: {fmt_money(potential)}",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await call.answer("✅ Успех!")
    
    elif action == "cashout":
        if game["level"] == 0:
            await call.answer("❌ Нет выигрыша!")
            return
        
        mult = TOWER_MULTIPLIERS[game["level"] - 1]
        payout = int(game["bet"] * mult)
        update_balance(user_id, payout)
        add_bet_record(user_id, game["bet"], payout, "tower", "cashout", True)
        
        await call.message.edit_text(
            f"✅ <b>ВЫИГРЫШ ЗАБРАН!</b>\n\n"
            f"🏆 Пройдено этажей: {game['level']}\n"
            f"📈 Множитель: {mult}x\n"
            f"💎 Получено: {fmt_money(payout)}",
            parse_mode="HTML"
        )
        TOWER_GAMES.pop(user_id, None)
        await call.answer("💰 Выигрыш забран!")

# ==================== ИГРЫ: КУБИК, КОСТИ, ФУТБОЛ, БАСКЕТ ====================

@router.message(F.text.lower().startswith("кубик"))
async def cube_game(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Формат: кубик 100")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    dice_msg = await message.answer_dice(emoji="🎲")
    rolled = dice_msg.dice.value
    
    # Угадывание числа
    win = rolled == 6  # Шанс 1/6
    payout = int(bet * 3.5) if win else 0
    
    new_balance = update_balance(message.from_user.id, payout - bet)
    add_bet_record(message.from_user.id, bet, payout, "cube", f"rolled={rolled}", win)
    
    await message.answer(
        f"🎲 <b>КУБИК</b>\n\n"
        f"🎯 Выпало: <b>{rolled}</b>\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"📊 Исход: {'✅ ПОБЕДА' if win else '❌ ПОРАЖЕНИЕ'}\n"
        f"💎 Выплата: {fmt_money(payout)}\n"
        f"💵 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

@router.message(F.text.lower().startswith("кости"))
async def dice_game(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("📝 Формат: кости 100 м (м/б/семь)")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    choice = parts[2].lower()
    if choice not in ["м", "б", "семь", "7"]:
        await message.reply("❌ Выбор: м (меньше), б (больше), семь")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    d1 = await message.answer_dice(emoji="🎲")
    d2 = await message.answer_dice(emoji="🎲")
    total = d1.dice.value + d2.dice.value
    
    win = False
    multiplier = 2.0
    
    if choice in ["м", "меньше"] and total < 7:
        win = True
    elif choice in ["б", "больше"] and total > 7:
        win = True
    elif choice in ["семь", "7"] and total == 7:
        win = True
        multiplier = 5.0
    
    payout = int(bet * multiplier) if win else 0
    new_balance = update_balance(message.from_user.id, payout - bet)
    add_bet_record(message.from_user.id, bet, payout, f"dice:{choice}", f"sum={total}", win)
    
    await message.answer(
        f"🎯 <b>КОСТИ</b>\n\n"
        f"🎲 Выпало: {d1.dice.value} + {d2.dice.value} = <b>{total}</b>\n"
        f"🎯 Ваш выбор: {choice}\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"📊 Исход: {'✅ ПОБЕДА' if win else '❌ ПОРАЖЕНИЕ'}\n"
        f"💎 Выплата: {fmt_money(payout)}\n"
        f"💵 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

@router.message(F.text.lower().startswith("футбол"))
async def football_game(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Формат: футбол 100")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    shoot = await message.answer_dice(emoji="⚽")
    gol = shoot.dice.value >= 4
    
    payout = int(bet * 1.85) if gol else 0
    new_balance = update_balance(message.from_user.id, payout - bet)
    add_bet_record(message.from_user.id, bet, payout, "football", f"value={shoot.dice.value}", gol)
    
    await message.answer(
        f"⚽ <b>ФУТБОЛ</b>\n\n"
        f"🎯 Результат: {'✅ ГОЛ' if gol else '❌ МИМО'}\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"🎁 Выплата: {fmt_money(payout)}\n"
        f"💎 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

@router.message(F.text.lower().startswith("баскет"))
async def basketball_game(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("📝 Формат: баскет 100")
        return
    
    try:
        bet = parse_amount_with_suffix(parts[1])
    except:
        await message.reply("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_balance = get_user(message.from_user.id)["coins"]
    if user_balance < bet:
        await message.reply(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    shot = await message.answer_dice(emoji="🏀")
    scored = shot.dice.value in [4, 5]
    
    payout = int(bet * 1.85) if scored else 0
    new_balance = update_balance(message.from_user.id, payout - bet)
    add_bet_record(message.from_user.id, bet, payout, "basketball", f"value={shot.dice.value}", scored)
    
    await message.answer(
        f"🏀 <b>БАСКЕТБОЛ</b>\n\n"
        f"🎯 Результат: {'✅ ЗАБРОС' if scored else '❌ ПРОМАХ'}\n"
        f"💰 Ставка: {fmt_money(bet)}\n"
        f"🎁 Выплата: {fmt_money(payout)}\n"
        f"💎 Баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

# ==================== АДМИН-ПАНЕЛЬ ====================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать монеты", callback_data="admin_give")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Админы", callback_data="admin_list")],
        [InlineKeyboardButton(text="🎮 Управление играми", callback_data="admin_games")],
        [InlineKeyboardButton(text="🎟 Создать промо", callback_data="admin_promo")],
        [InlineKeyboardButton(text="💎 Установить баланс", callback_data="admin_set_balance")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])
    
    await message.answer(
        f"🛡️ <b>Админ-панель</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Статус: {'👑 Владелец' if is_owner(message.from_user.id) else '🛡️ Админ'}",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("admin_"))
async def admin_callbacks(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа!", show_alert=True)
        return
    
    action = call.data.split("_")[1]
    
    if action == "give":
        await call.message.edit_text(
            "💰 <b>Выдача монет</b>\n\n"
            "Отправьте сумму в чат.\n"
            "Поддерживаются суффиксы: 1k, 1kk, 1kkk\n\n"
            "<i>Или используйте /give @user 1000</i>",
            parse_mode="HTML"
        )
        await state.set_state("admin_give_amount")
    
    elif action == "stats":
        conn = get_db()
        try:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_coins = conn.execute("SELECT SUM(coins) FROM users").fetchone()[0] or 0
            bets = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            wins = conn.execute("SELECT COUNT(*) FROM bets WHERE win=1").fetchone()[0]
        finally:
            conn.close()
        
        win_rate = (wins / bets * 100) if bets > 0 else 0
        
        await call.message.edit_text(
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Пользователей: {users:,}\n"
            f"💰 Всего монет: {fmt_money(total_coins)}\n"
            f"🎲 Ставок: {bets:,}\n"
            f"🏆 Побед: {wins:,} ({win_rate:.1f}%)\n"
            f"💵 Профит казино: {fmt_money(total_coins - START_BALANCE * users)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]])
        )
    
    elif action == "list":
        admins = "\n".join([f"🛡️ <code>{aid}</code>" for aid in ADMIN_IDS])
        owners = "\n".join([f"👑 <code>{oid}</code>" for oid in OWNER_IDS])
        
        await call.message.edit_text(
            f"👥 <b>Администраторы</b>\n\n"
            f"<b>Владельцы:</b>\n{owners}\n\n"
            f"<b>Админы:</b>\n{admins}\n\n"
            f"<i>Добавление: /add_admin (ответить на сообщение)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]])
        )
    
    elif action == "games":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎡 Рулетка", callback_data="admin_toggle_roulette")],
            [InlineKeyboardButton(text="📈 Краш", callback_data="admin_toggle_crash")],
            [InlineKeyboardButton(text="💣 Мины", callback_data="admin_toggle_mines")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
        
        await call.message.edit_text("🎮 <b>Управление играми</b>\n\nНажмите на игру, чтобы включить/выключить", parse_mode="HTML", reply_markup=keyboard)
    
    elif action == "promo":
        await call.message.edit_text(
            "🎟 <b>Создание промокода</b>\n\n"
            "Формат: /create_promo КОД СУММА АКТИВАЦИИ\n\n"
            "Пример: <code>/create_promo HELLO 1000 50</code>",
            parse_mode="HTML"
        )
    
    elif action == "set_balance":
        await call.message.edit_text(
            "💎 <b>Установка баланса</b>\n\n"
            "Формат: /setbalance @user 1000\n"
            "<i>Ответьте на сообщение пользователя</i>",
            parse_mode="HTML"
        )
    
    elif action == "close":
        await call.message.delete()
    
    elif action == "back":
        await admin_panel(call.message)
    
    await call.answer()

@router.message(Command("add_admin"))
async def add_admin_cmd(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Только владелец!")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя!")
        return
    
    new_admin = message.reply_to_message.from_user.id
    
    if new_admin in ADMIN_IDS:
        await message.answer("❌ Уже админ!")
        return
    
    ADMIN_IDS.append(new_admin)
    await message.answer(f"✅ <code>{new_admin}</code> добавлен в админы!", parse_mode="HTML")

@router.message(Command("remove_admin"))
async def remove_admin_cmd(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ Только владелец!")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя!")
        return
    
    admin = message.reply_to_message.from_user.id
    
    if admin not in ADMIN_IDS:
        await message.answer("❌ Не админ!")
        return
    
    if admin in OWNER_IDS:
        await message.answer("❌ Нельзя удалить владельца!")
        return
    
    ADMIN_IDS.remove(admin)
    await message.answer(f"✅ <code>{admin}</code> удалён из админов!", parse_mode="HTML")

@router.message(lambda m: m.text and m.text.lower().startswith(("выдать", "/give", "добавить")))
async def give_coins(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return
    
    target_user = None
    amount_str = None
    
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        parts = message.text.split()
        if len(parts) >= 2:
            amount_str = parts[1]
    else:
        parts = message.text.split()
        if len(parts) >= 3:
            target_username = parts[1].replace("@", "")
            amount_str = parts[2]
            await message.answer("❌ Используйте ответ на сообщение!")
            return
        elif len(parts) >= 2:
            amount_str = parts[1]
            target_user = message.from_user
    
    if not target_user or not amount_str:
        await message.answer("❌ Формат: ответьте на сообщение и напишите сумму\nПример: выдать 1000")
        return
    
    try:
        amount = parse_amount_with_suffix(amount_str)
    except:
        await message.answer("❌ Неверная сумма! Примеры: 1000, 1k, 1kk")
        return
    
    new_balance = update_balance(target_user.id, amount)
    
    await message.answer(
        f"✅ <b>Выдача выполнена!</b>\n\n"
        f"👤 Пользователь: {mention_user(target_user.id, target_user.first_name)}\n"
        f"💰 Сумма: {fmt_money(amount)}\n"
        f"💎 Новый баланс: {fmt_money(new_balance)}",
        parse_mode="HTML"
    )

@router.message(Command("setbalance"))
async def set_balance_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет прав!")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите сумму! Пример: /setbalance 1000")
        return
    
    try:
        amount = parse_amount_with_suffix(parts[1])
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    target = message.reply_to_message.from_user
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (amount, str(target.id)))
        conn.commit()
        
        await message.answer(
            f"✅ <b>Баланс установлен!</b>\n\n"
            f"👤 {mention_user(target.id, target.first_name)}\n"
            f"💰 Новый баланс: {fmt_money(amount)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        conn.close()

# ==================== ЗАПУСК ====================

async def main():
    init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    print(f"👑 Владельцы: {OWNER_IDS}")
    print(f"🛡️ Админы: {ADMIN_IDS}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
