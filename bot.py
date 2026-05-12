import asyncio
import html
import json
import logging
import os
import random
import sqlite3
import string
import time
import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter, BaseFilter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    BotCommand,
    BotCommandScopeDefault,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
)

# ==================== КОНФИГУРАЦИЯ ====================

BOT_TOKEN = "8365761672:AAFNA79Or2QnBVmHdOL465Rp0Ta89nF7DPA"
ADMIN_IDS = {8478884644}
BOT_USERNAME = "DodoCoin_bot"

# Курс: 1 Telegram Star = 10,000 DodoCoin
STAR_TO_COIN_RATE = 10000
PAYMENT_PROVIDER_TOKEN = ""  # Для реальных платежей нужен токен от @BotFather

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ ====================

DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "dodocoin.db")
os.makedirs(DB_DIR, exist_ok=True)

START_BALANCE = 1000.0
MIN_BET = 10.0
MAX_BET = 1000000.0
CURRENCY_NAME = "DodoCoin"
CURRENCY_SHORT = "DC"
BONUS_COOLDOWN_SECONDS = 8 * 60 * 60
BONUS_REWARD_MIN = 200
BONUS_REWARD_MAX = 800
REF_REWARD = 5000.0
REF_PERCENT = 0.03
DAILY_BONUS = 300.0
WEEKLY_BONUS = 2500.0

CHANNEL_ID = "@dodoCoin_news"
CHAT_ID = "@dodocoin_chat"

TOWER_MULTIPLIERS = [1.20, 1.48, 1.86, 2.35, 2.95, 3.75, 4.85, 6.15, 7.80, 10.0]
GOLD_MULTIPLIERS = [1.15, 1.35, 1.62, 2.0, 2.55, 3.25, 4.2, 5.5, 7.2]
DIAMOND_MULTIPLIERS = [1.12, 1.28, 1.48, 1.72, 2.02, 2.4, 2.92, 3.6, 4.5, 5.6]

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# ==================== ЭМОДЗИ ====================

class Emoji:
    CROWN = "👑"
    DIAMOND = "💎"
    VIP = "✨"
    PLAYER = "👤"
    COIN = "💰"
    BONUS = "🎁"
    REF = "🔗"
    WIN = "🎉"
    LOSE = "💔"
    BANK = "🏦"
    GAMES = "🎮"
    TOP = "🏆"
    STAR = "⭐"
    ROCKET = "🚀"
    HEART = "❤️"
    THANK = "🙏"
    SUPPORT = "🤝"
    DONATE = "💝"

# ==================== FSM СОСТОЯНИЯ ====================

class DonateStates(StatesGroup):
    waiting_amount = State()

class CheckCreateStates(StatesGroup):
    waiting_amount = State()
    waiting_count = State()

class PromoStates(StatesGroup):
    waiting_code = State()

class NewPromoStates(StatesGroup):
    waiting_code = State()
    waiting_reward = State()
    waiting_activations = State()

class BankStates(StatesGroup):
    waiting_amount = State()

class RouletteStates(StatesGroup):
    waiting_amount = State()
    waiting_choice = State()

class CrashStates(StatesGroup):
    waiting_amount = State()
    waiting_target = State()

class CubeStates(StatesGroup):
    waiting_amount = State()
    waiting_guess = State()

class DiceStates(StatesGroup):
    waiting_amount = State()
    waiting_guess = State()

class TowerStates(StatesGroup):
    waiting_amount = State()

class GoldStates(StatesGroup):
    waiting_amount = State()

class DiamondStates(StatesGroup):
    waiting_amount = State()

class MinesStates(StatesGroup):
    waiting_amount = State()
    waiting_mines = State()

class OchkoStates(StatesGroup):
    waiting_amount = State()
    waiting_confirm = State()

class AdminBroadcastStates(StatesGroup):
    waiting_message = State()

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            coins REAL DEFAULT 1000.0,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            lost_coins REAL DEFAULT 0.0,
            won_coins REAL DEFAULT 0.0,
            status INTEGER DEFAULT 0,
            registered_at INTEGER DEFAULT 0,
            last_active INTEGER DEFAULT 0,
            ref_id TEXT DEFAULT NULL,
            ref_earned REAL DEFAULT 0.0,
            ref_count INTEGER DEFAULT 0,
            first_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            vip_level INTEGER DEFAULT 0,
            total_donated REAL DEFAULT 0.0,
            banned INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            bet_amount REAL,
            choice TEXT,
            outcome TEXT,
            win INTEGER DEFAULT 0,
            payout REAL DEFAULT 0.0,
            ts INTEGER DEFAULT 0,
            game_type TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward REAL,
            claimed TEXT DEFAULT '[]',
            remaining_activations INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            principal REAL,
            rate REAL,
            term_days INTEGER,
            opened_at INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            closed_at INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS json_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            stars INTEGER,
            coins REAL,
            donated_at INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts():
    return int(time.time())

def fmt_money(value: float) -> str:
    value = round(float(value), 2)
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"{value/1_000_000:.1f}M {CURRENCY_SHORT}"
    elif abs_value >= 1000:
        return f"{value/1000:.1f}K {CURRENCY_SHORT}"
    elif abs(value - int(value)) < 1e-9:
        return f"{int(value)} {CURRENCY_SHORT}"
    else:
        return f"{value:.2f} {CURRENCY_SHORT}"

def fmt_dt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M") if ts > 0 else "Неизвестно"

def fmt_left(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    if minutes > 0:
        return f"{minutes}м {secs}с"
    return f"{secs}с"

def parse_amount(text: str) -> float:
    raw = str(text or "").strip().lower().replace(" ", "").replace(",", ".")
    multiplier = 1.0
    if raw.endswith(("k", "к")):
        raw = raw[:-1]
        multiplier = 1000.0
    elif raw.endswith(("m", "м")):
        raw = raw[:-1]
        multiplier = 1000000.0
    value = float(raw) * multiplier
    if value <= 0:
        raise ValueError("amount must be positive")
    return round(value, 2)

def escape_html(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=False)

def mention_user(user_id: int, name: Optional[str] = None) -> str:
    label = escape_html(name or f"ID {user_id}")
    return f'<a href="tg://user?id={int(user_id)}">{label}</a>'

def is_admin_user(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

def ensure_user(user_id: int, ref_id: Optional[str] = None, first_name: str = "", username: str = "") -> None:
    conn = get_db()
    try:
        now = now_ts()
        row = conn.execute("SELECT id FROM users WHERE id = ?", (str(user_id),)).fetchone()
        if not row:
            conn.execute("""
                INSERT INTO users (id, coins, registered_at, last_active, ref_id, first_name, username)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(user_id), START_BALANCE, now, now, ref_id, first_name, username))
            if ref_id and ref_id != str(user_id):
                conn.execute("UPDATE users SET ref_count = ref_count + 1, coins = coins + ? WHERE id = ?", (REF_REWARD, ref_id))
        else:
            conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()

def get_user(user_id: int):
    conn = get_db()
    try:
        ensure_user(user_id)
        return conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
    finally:
        conn.close()

def add_balance(user_id: int, amount: float, reason: str = "") -> float:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user(user_id)
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (round(amount, 2), str(user_id)))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def reserve_bet(user_id: int, bet: float) -> Tuple[bool, float]:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user(user_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        coins = float(row["coins"] or 0)
        if coins < bet:
            conn.rollback()
            return False, coins
        new_balance = round(coins - bet, 2)
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, str(user_id)))
        conn.commit()
        return True, new_balance
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def finalize_reserved_bet(user_id: int, bet: float, payout: float, choice: str, outcome: str, game_type: str = "") -> float:
    payout = round(max(0.0, payout), 2)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user(user_id)
        if payout > 0:
            conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (payout, str(user_id)))
            conn.execute("UPDATE users SET games_won = games_won + 1, won_coins = won_coins + ? WHERE id = ?", (payout - bet, str(user_id)))
        else:
            conn.execute("UPDATE users SET lost_coins = lost_coins + ? WHERE id = ?", (bet, str(user_id)))
            user_row = conn.execute("SELECT ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if user_row and user_row["ref_id"]:
                ref_bonus = round(bet * REF_PERCENT, 2)
                conn.execute("UPDATE users SET ref_earned = ref_earned + ?, coins = coins + ? WHERE id = ?", (ref_bonus, ref_bonus, user_row["ref_id"]))
        conn.execute("UPDATE users SET games_played = games_played + 1 WHERE id = ?", (str(user_id),))
        conn.execute("""
            INSERT INTO bets (user_id, bet_amount, choice, outcome, win, payout, ts, game_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(user_id), round(bet, 2), choice, outcome, 1 if payout > 0 else 0, payout, now_ts(), game_type))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_top_balances(limit: int = 10):
    conn = get_db()
    try:
        return conn.execute("SELECT id, coins, first_name FROM users WHERE banned = 0 ORDER BY coins DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()

# ==================== ДОНАТ СИСТЕМА ====================

def create_donation_invoice(amount_stars: int) -> Tuple[str, List[LabeledPrice]]:
    """Создание счета для доната через Telegram Stars"""
    coins = amount_stars * STAR_TO_COIN_RATE
    title = f"Пополнение баланса DodoCoin"
    description = f"💰 {coins:,} {CURRENCY_SHORT}\n⭐ {amount_stars} Telegram Stars"
    payload = f"donate_{amount_stars}_{coins}"
    prices = [LabeledPrice(label=f"{coins} {CURRENCY_SHORT}", amount=amount_stars * 100)]
    return payload, prices

# Клавиатура выбора суммы доната
def get_donate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 10 Stars = 100,000 DC", callback_data="donate:10")],
        [InlineKeyboardButton(text="⭐ 25 Stars = 250,000 DC", callback_data="donate:25")],
        [InlineKeyboardButton(text="⭐ 50 Stars = 500,000 DC", callback_data="donate:50")],
        [InlineKeyboardButton(text="⭐ 100 Stars = 1,000,000 DC", callback_data="donate:100")],
        [InlineKeyboardButton(text="⭐ 250 Stars = 2,500,000 DC", callback_data="donate:250")],
        [InlineKeyboardButton(text="⭐ 500 Stars = 5,000,000 DC", callback_data="donate:500")],
        [InlineKeyboardButton(text="⭐ 1000 Stars = 10,000,000 DC", callback_data="donate:1000")],
        [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="donate:custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="donate:cancel")]
    ])

# ==================== ИГРЫ ====================

def roulette_roll(choice: str) -> Tuple[bool, float, str, int, str]:
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in RED_NUMBERS else "black")
    win, multiplier = False, 0.0
    if choice == "red" and color == "red":
        win, multiplier = True, 2.0
    elif choice == "black" and color == "black":
        win, multiplier = True, 2.0
    elif choice == "even" and number % 2 == 0 and number != 0:
        win, multiplier = True, 2.0
    elif choice == "odd" and number % 2 == 1:
        win, multiplier = True, 2.0
    elif choice == "zero" and number == 0:
        win, multiplier = True, 36.0
    elif choice.isdigit() and 0 <= int(choice) <= 36 and int(choice) == number:
        win, multiplier = True, 35.0
    pretty_color = {"red": "🔴 Красное", "black": "⚫ Чёрное", "green": "🟢 Зеро"}[color]
    return win, multiplier, f"🎡 Выпало {number} ({pretty_color})", number, color

def crash_roll() -> float:
    r = random.random()
    if r < 0.60:
        return round(random.uniform(1.0, 4.0), 2)
    elif r < 0.85:
        return round(random.uniform(4.01, 15.0), 2)
    else:
        return round(random.uniform(15.01, 100.0), 2)

def mines_multiplier(opened_count: int, mines_count: int, total_cells: int = 25) -> float:
    if opened_count <= 0:
        return 1.0
    safe_cells = total_cells - mines_count
    base = total_cells / max(1.0, safe_cells)
    return round((base ** opened_count) * 0.95, 2)

def make_deck():
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suits = ["♠", "♥", "♦", "♣"]
    deck = [(r, s) for r in ranks for s in suits]
    random.shuffle(deck)
    return deck

def card_points(rank: str) -> int:
    if rank in {"J", "Q", "K"}:
        return 10
    if rank == "A":
        return 11
    return int(rank)

def hand_value(cards):
    total = sum(card_points(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

# ==================== ИГРОВЫЕ ХРАНИЛИЩА ====================

TOWER_GAMES = {}
GOLD_GAMES = {}
DIAMOND_GAMES = {}
MINES_GAMES = {}
OCHKO_GAMES = {}
user_game_locks = {}

def _game_lock(user_id):
    key = str(user_id)
    if key not in user_game_locks:
        user_game_locks[key] = asyncio.Lock()
    return user_game_locks[key]

def clear_active_sessions(user_id):
    for d in (TOWER_GAMES, GOLD_GAMES, DIAMOND_GAMES, MINES_GAMES, OCHKO_GAMES):
        d.pop(user_id, None)

# ==================== КЛАВИАТУРЫ ====================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игры", callback_data="menu:games"),
         InlineKeyboardButton(text="🏦 Банк", callback_data="menu:bank")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data="menu:top"),
         InlineKeyboardButton(text="🔗 Рефералы", callback_data="menu:ref")],
        [InlineKeyboardButton(text="💝 Донат", callback_data="menu:donate"),
         InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile")],
        [InlineKeyboardButton(text="⭐ Пополнить", callback_data="menu:donate")]
    ])

def games_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Рулетка", callback_data="games:roulette"),
         InlineKeyboardButton(text="📈 Краш", callback_data="games:crash")],
        [InlineKeyboardButton(text="🗼 Башня", callback_data="games:tower"),
         InlineKeyboardButton(text="🥇 Золото", callback_data="games:gold")],
        [InlineKeyboardButton(text="💍 Алмазы", callback_data="games:diamonds"),
         InlineKeyboardButton(text="💣 Мины", callback_data="games:mines")],
        [InlineKeyboardButton(text="🎴 Очко", callback_data="games:ochko"),
         InlineKeyboardButton(text="🎲 Кубик", callback_data="games:cube")],
        [InlineKeyboardButton(text="🎯 Кости", callback_data="games:dice")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
    ])

def bank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Открыть депозит", callback_data="bank:open")],
        [InlineKeyboardButton(text="📜 Мои депозиты", callback_data="bank:list")],
        [InlineKeyboardButton(text="💰 Снять зрелые", callback_data="bank:withdraw")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
    ])

def bank_terms_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 дн. (+3%)", callback_data="bank:term:7")],
        [InlineKeyboardButton(text="14 дн. (+7%)", callback_data="bank:term:14")],
        [InlineKeyboardButton(text="30 дн. (+18%)", callback_data="bank:term:30")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bank:term:cancel")]
    ])

def roulette_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="roulette:red"),
         InlineKeyboardButton(text="⚫ Чёрное", callback_data="roulette:black")],
        [InlineKeyboardButton(text="2️⃣ Чет", callback_data="roulette:even"),
         InlineKeyboardButton(text="1️⃣ Нечет", callback_data="roulette:odd")],
        [InlineKeyboardButton(text="0️⃣ Зеро (x36)", callback_data="roulette:zero")],
        [InlineKeyboardButton(text="🔢 Число (x35)", callback_data="roulette:number")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="game:cancel")]
    ])

def tower_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="tower:1"),
         InlineKeyboardButton(text="2", callback_data="tower:2"),
         InlineKeyboardButton(text="3", callback_data="tower:3")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="tower:cash"),
         InlineKeyboardButton(text="❌ Сдаться", callback_data="tower:cancel")]
    ])

def gold_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="gold:1"),
         InlineKeyboardButton(text="2", callback_data="gold:2"),
         InlineKeyboardButton(text="3", callback_data="gold:3"),
         InlineKeyboardButton(text="4", callback_data="gold:4")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="gold:cash"),
         InlineKeyboardButton(text="❌ Сдаться", callback_data="gold:cancel")]
    ])

def diamond_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="diamond:1"),
         InlineKeyboardButton(text="2", callback_data="diamond:2"),
         InlineKeyboardButton(text="3", callback_data="diamond:3"),
         InlineKeyboardButton(text="4", callback_data="diamond:4"),
         InlineKeyboardButton(text="5", callback_data="diamond:5")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="diamond:cash"),
         InlineKeyboardButton(text="❌ Сдаться", callback_data="diamond:cancel")]
    ])

def mines_kb_5x5(game, reveal_all=False):
    opened = set(game.get("opened", []))
    mines_set = set(game.get("mines", []))
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c + 1
            if idx in opened:
                text, cb = "✅", "mines:noop"
            elif reveal_all and idx in mines_set:
                text, cb = "💣", "mines:noop"
            else:
                text, cb = str(idx), f"mines:cell:{idx}"
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data="mines:cash"),
                 InlineKeyboardButton(text="❌ Сдаться", callback_data="mines:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ochko_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Взять", callback_data="ochko:hit"),
         InlineKeyboardButton(text="✋ Стоп", callback_data="ochko:stand")]
    ])

def ochko_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать", callback_data="ochko:start"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="ochko:cancel")]
    ])

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать DC", callback_data="admin:give")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Топ-20", callback_data="admin:top20")],
        [InlineKeyboardButton(text="🎟 Новый промо", callback_data="admin:newpromo")],
        [InlineKeyboardButton(text="🔄 Обновить БД", callback_data="admin:refreshdb")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
    ])

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def start_command(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    args = command.args or ""
    ref_id = None
    
    if args.startswith("ref_"):
        ref_id = args.replace("ref_", "")
        if ref_id == str(user_id):
            ref_id = None
    
    ensure_user(user_id, ref_id, message.from_user.first_name or "", message.from_user.username or "")
    await state.clear()
    clear_active_sessions(user_id)
    
    if ref_id:
        await message.bot.send_message(
            int(ref_id),
            f"{Emoji.BONUS} <b>Новый реферал!</b>\nПо твоей ссылке присоединился {mention_user(user_id, message.from_user.first_name)}\nНачислено: <b>{fmt_money(REF_REWARD)}</b>"
        )
    
    user = get_user(user_id)
    
    await message.answer(
        f"<b>🏆 ДОБРО ПОЖАЛОВАТЬ В DODOKEN CASINO! 🏆</b>\n\n"
        f"{Emoji.PLAYER} <b>Игрок:</b> {mention_user(user_id, message.from_user.first_name)}\n"
        f"{Emoji.COIN} <b>Баланс:</b> {fmt_money(user['coins'])}\n"
        f"{Emoji.VIP} <b>VIP уровень:</b> {user['vip_level']}\n\n"
        f"<b>🎮 ДОСТУПНЫЕ ИГРЫ:</b>\n"
        f"┌ 🎡 Рулетка - угадай цвет или число\n"
        f"├ 📈 Краш - забери множитель вовремя\n"
        f"├ 🗼 Башня - найди безопасный путь\n"
        f"├ 💣 Мины - открой все безопасные клетки\n"
        f"├ 🎴 Очко - обыграй дилера в Blackjack\n"
        f"└ 🎲 Кубик/Кости - угадай выпадение\n\n"
        f"<b>⭐ ПОПОЛНЕНИЕ БАЛАНСА:</b>\n"
        f"Используй команду /donate или кнопку «Пополнить»\n"
        f"<b>1 Telegram Star = 10,000 {CURRENCY_SHORT}</b>\n\n"
        f"<i>Если депозите 15+ звёзд - напишите модератору @debashev</i>\n\n"
        f"<b>👇 ИСПОЛЬЗУЙ КНОПКИ ДЛЯ НАВИГАЦИИ 👇</b>",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        f"<b>📚 ПОМОЩЬ ПО КОМАНДАМ</b>\n\n"
        f"<b>💰 БАЛАНС И БОНУСЫ:</b>\n"
        f"┌ /balance или /б - показать баланс\n"
        f"├ /bonus - получить бонус\n"
        f"├ /daily - ежедневный бонус\n"
        f"├ /weekly - еженедельный бонус\n"
        f"└ /profile - профиль игрока\n\n"
        f"<b>🎮 ИГРЫ:</b>\n"
        f"┌ /roulette [сумма] [ставка] - рулетка\n"
        f"├ /crash [сумма] [множитель] - краш\n"
        f"├ /tower [сумма] - башня\n"
        f"├ /gold [сумма] - золото\n"
        f"├ /diamonds [сумма] - алмазы\n"
        f"├ /mines [сумма] [мины] - мины\n"
        f"├ /ochko [сумма] - очко\n"
        f"├ /cube [сумма] [число] - кубик\n"
        f"└ /dice [сумма] [больше/меньше/7] - кости\n\n"
        f"<b>⭐ ПОПОЛНЕНИЕ:</b>\n"
        f"┌ /donate - пополнить баланс через Telegram Stars\n"
        f"└ 1 Star = 10,000 {CURRENCY_SHORT}\n\n"
        f"<b>🏦 ФИНАНСЫ:</b>\n"
        f"┌ /bank - банковские депозиты\n"
        f"├ /transfer [ID] [сумма] - перевод\n"
        f"├ /promo [код] - активировать промокод\n"
        f"└ /top - топ игроков\n\n"
        f"<b>🔗 РЕФЕРАЛЫ:</b>\n"
        f"┌ /referral - реферальная система\n"
        f"└ Приглашай друзей и получай 5,000 DC\n\n"
        f"<i>Отмена действия: /cancel</i>"
    )

@dp.message(Command("balance"))
@dp.message(Command("б"))
async def balance_command(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"{Emoji.COIN} <b>ТВОЙ БАЛАНС</b>\n"
        f"<code>{fmt_money(float(user['coins'] or 0))}</code>\n\n"
        f"<i>VIP уровень: {user['vip_level']} | Игр: {user['games_played']} | Побед: {user['games_won']}</i>"
    )

@dp.message(Command("profile"))
async def profile_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    status_text = "👑 Админ" if is_admin_user(user_id) else (f"{Emoji.VIP} VIP {user['vip_level']}" if user['vip_level'] > 0 else f"{Emoji.PLAYER} Игрок")
    reg_date = fmt_dt(int(user["registered_at"] or 0))
    
    winrate = round((user['games_won'] / user['games_played'] * 100), 1) if user['games_played'] > 0 else 0
    
    await message.answer(
        f"<b>👤 ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"┌ {Emoji.PLAYER} <b>Имя:</b> {mention_user(user_id, user['first_name'] or 'Игрок')}\n"
        f"├ {Emoji.STATUS} <b>Статус:</b> {status_text}\n"
        f"├ {Emoji.COIN} <b>Баланс:</b> {fmt_money(user['coins'])}\n"
        f"├ {Emoji.GAMES} <b>Сыграно игр:</b> {user['games_played']}\n"
        f"├ {Emoji.TOP} <b>Побед:</b> {user['games_won']} ({winrate}%)\n"
        f"├ {Emoji.WIN} <b>Выиграно:</b> {fmt_money(user['won_coins'])}\n"
        f"├ {Emoji.LOSE} <b>Проиграно:</b> {fmt_money(user['lost_coins'])}\n"
        f"├ {Emoji.REF} <b>Рефералов:</b> {user['ref_count']}\n"
        f"├ {Emoji.REF} <b>Заработано с реф:</b> {fmt_money(user['ref_earned'])}\n"
        f"├ {Emoji.DATE} <b>Регистрация:</b> {reg_date}\n"
        f"└ {Emoji.DONATE} <b>Пополнено:</b> {fmt_money(user['total_donated'] or 0)}\n\n"
        f"<i>Используй /donate для пополнения баланса!</i>"
    )

@dp.message(Command("bonus"))
async def bonus_command(message: Message):
    user_id = message.from_user.id
    key = f"bonus_ts:{user_id}"
    last = int(get_json_value(key, 0) or 0)
    now = now_ts()
    
    if now - last < BONUS_COOLDOWN_SECONDS:
        left = BONUS_COOLDOWN_SECONDS - (now - last)
        await message.answer(f"{Emoji.BONUS} <b>Бонус уже получен!</b>\nСледующий через: <code>{fmt_left(left)}</code>")
        return
    
    reward = round(random.uniform(BONUS_REWARD_MIN, BONUS_REWARD_MAX), 2)
    add_balance(user_id, reward, "Бонус за активность")
    set_json_value(key, now)
    
    await message.answer(
        f"{Emoji.BONUS} <b>БОНУС ПОЛУЧЕН!</b>\n\n"
        f"💰 Начислено: <code>{fmt_money(reward)}</code>\n\n"
        f"<i>Заходи за бонусом каждые 8 часов!</i>"
    )

@dp.message(Command("daily"))
async def daily_bonus_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_taken = int(user["daily_bonus_taken"] or 0)
    now = now_ts()
    day_start = now - (now % 86400)
    
    if last_taken >= day_start:
        next_bonus = last_taken + 86400
        left = next_bonus - now
        await message.answer(f"{Emoji.CLOCK} <b>Ежедневный бонус уже получен!</b>\nСледующий через: <code>{fmt_left(left)}</code>")
        return
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET daily_bonus_taken = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()
    
    reward = DAILY_BONUS
    add_balance(user_id, reward, "Ежедневный бонус")
    
    await message.answer(
        f"{Emoji.GIFT} <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n"
        f"💰 Начислено: <code>{fmt_money(reward)}</code>\n\n"
        f"<i>Заходи каждый день за бонусом!</i>"
    )

@dp.message(Command("weekly"))
async def weekly_bonus_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_taken = int(user["weekly_bonus_taken"] or 0)
    now = now_ts()
    week_start = now - (now % 604800)
    
    if last_taken >= week_start:
        next_bonus = last_taken + 604800
        left = next_bonus - now
        await message.answer(f"{Emoji.CLOCK} <b>Еженедельный бонус уже получен!</b>\nСледующий через: <code>{fmt_left(left)}</code>")
        return
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET weekly_bonus_taken = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()
    
    reward = WEEKLY_BONUS
    add_balance(user_id, reward, "Еженедельный бонус")
    
    await message.answer(
        f"{Emoji.GIFT} <b>ЕЖЕНЕДЕЛЬНЫЙ БОНУС!</b>\n\n"
        f"💰 Начислено: <code>{fmt_money(reward)}</code>\n\n"
        f"<i>Заходи каждую неделю за бонусом!</i>"
    )

@dp.message(Command("top"))
async def top_command(message: Message):
    rows = get_top_balances(15)
    if not rows:
        await message.answer(f"{Emoji.TOP} <b>ТОП ИГРОКОВ</b>\n<blockquote><i>Пока пусто...</i></blockquote>")
        return
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"}
    lines = [f"{Emoji.TOP} <b>ТОП ИГРОКОВ ПО БОГАТСТВУ</b>", "<blockquote>"]
    
    for idx, row in enumerate(rows, start=1):
        icon = medals.get(idx, f"{idx}.")
        name = escape_html(row["first_name"] or f"ID {row['id']}")
        lines.append(f"{icon} {name} — <b>{fmt_money(float(row['coins']))}</b>")
    
    lines.append("</blockquote>")
    lines.append(f"\n<i>Всего игроков: {len(rows)}+</i>")
    await message.answer("\n".join(lines))

@dp.message(Command("referral"))
@dp.message(Command("реф"))
async def referral_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    await message.answer(
        f"{Emoji.REF} <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"┌ {Emoji.COIN} <b>За приглашённого друга:</b> {fmt_money(REF_REWARD)}\n"
        f"├ {Emoji.PERCENT} <b>{int(REF_PERCENT * 100)}% от проигрышей друга</b>\n"
        f"├ {Emoji.INVITED} <b>Приглашено друзей:</b> {user['ref_count']}\n"
        f"├ {Emoji.COIN} <b>Заработано с рефералов:</b> {fmt_money(user['ref_earned'])}\n"
        f"└ {Emoji.REF} <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<i>Отправь ссылку друзьям и получай бонусы!</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"ref:copy:{user_id}")]
        ])
    )

# ==================== ДОНАТ КОМАНДЫ ====================

@dp.message(Command("donate"))
@dp.message(Command("дон"))
@dp.message(Command("пополнить"))
async def donate_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"<b>⭐ ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
        f"<b>Курс обмена:</b>\n"
        f"┌ 1 Telegram Star = 10,000 {CURRENCY_SHORT}\n"
        f"└ Минимальное пополнение: 10 Stars\n\n"
        f"<b>💰 ВЫБЕРИ СУММУ ПОПОЛНЕНИЯ:</b>\n\n"
        f"<i>💰 После оплаты монеты поступят автоматически!</i>\n"
        f"<i>⭐ Если депозите 15+ звёзд - напишите модератору @debashev</i>",
        reply_markup=get_donate_keyboard()
    )

@dp.callback_query(F.data.startswith("donate:"))
async def donate_callback(query: CallbackQuery, state: FSMContext):
    action = query.data.split(":")[1]
    
    if action == "cancel":
        await query.message.edit_text("❌ Пополнение отменено")
        await query.answer()
        return
    
    if action == "custom":
        await state.set_state(DonateStates.waiting_amount)
        await query.message.edit_text(
            f"<b>⭐ ВВЕДИ СВОЮ СУММУ</b>\n\n"
            f"Введи количество Telegram Stars для пополнения:\n"
            f"<b>Минимум: 10 Stars</b>\n"
            f"<b>Курс: 1 Star = 10,000 {CURRENCY_SHORT}</b>\n\n"
            f"<i>Пример: 50</i>"
        )
        await query.answer()
        return
    
    try:
        stars = int(action)
        if stars < 10:
            await query.answer("Минимальная сумма: 10 Stars!", show_alert=True)
            return
        
        coins = stars * STAR_TO_COIN_RATE
        
        # Показываем красивый текст с большим шрифтом
        await query.message.edit_text(
            f"<b>⭐ ПОДТВЕРЖДЕНИЕ ПОПОЛНЕНИЯ</b>\n\n"
            f"┌ <b>Telegram Stars:</b> {stars} ⭐\n"
            f"├ <b>Получите:</b> {fmt_money(coins)}\n"
            f"└ <b>Сумма к оплате:</b> {stars} ⭐\n\n"
            f"<i>Нажмите кнопку ниже для оплаты через Telegram Stars</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ Оплатить {stars} Stars", callback_data=f"donate:pay:{stars}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="donate:cancel")]
            ])
        )
    except ValueError:
        await query.answer("Ошибка!")
    await query.answer()

@dp.callback_query(F.data.startswith("donate:pay:"))
async def donate_pay_callback(query: CallbackQuery):
    stars = int(query.data.split(":")[2])
    coins = stars * STAR_TO_COIN_RATE
    
    # Создаем инвойс для оплаты
    payload, prices = create_donation_invoice(stars)
    
    try:
        await query.bot.send_invoice(
            chat_id=query.from_user.id,
            title=f"Пополнение DodoCoin",
            description=f"💰 {coins:,} {CURRENCY_SHORT}\n⭐ {stars} Telegram Stars",
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="XTR",
            prices=prices,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            is_flexible=False,
        )
    except Exception as e:
        logger.error(f"Invoice error: {e}")
        await query.message.edit_text(
            f"<b>❌ ОШИБКА СОЗДАНИЯ ПЛАТЕЖА</b>\n\n"
            f"Попробуйте позже или обратитесь к администратору.\n"
            f"Ошибка: {str(e)[:100]}"
        )
    
    await query.answer()

# Обработка успешного платежа
@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    
    # Парсим payload
    payload = payment.invoice_payload
    parts = payload.split("_")
    if len(parts) >= 3:
        stars = int(parts[1])
        coins = int(parts[2])
    else:
        stars = int(payment.total_amount / 100)
        coins = stars * STAR_TO_COIN_RATE
    
    # Начисляем монеты
    new_balance = add_balance(user_id, coins, f"Пополнение через Telegram Stars: {stars} ⭐")
    
    # Записываем в историю донатов
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO donations (user_id, stars, coins, donated_at)
            VALUES (?, ?, ?, ?)
        """, (str(user_id), stars, coins, now_ts()))
        conn.execute("UPDATE users SET total_donated = total_donated + ? WHERE id = ?", (coins, str(user_id)))
        conn.commit()
    except Exception as e:
        logger.error(f"Donation record error: {e}")
    finally:
        conn.close()
    
    # Проверка на VIP статус
    user = get_user(user_id)
    if coins >= 1500000:  # 150+ звезд
        new_vip = 3
    elif coins >= 500000:  # 50+ звезд
        new_vip = 2
    elif coins >= 100000:  # 10+ звезд
        new_vip = 1
    else:
        new_vip = 0
    
    if new_vip > user["vip_level"]:
        conn = get_db()
        try:
            conn.execute("UPDATE users SET vip_level = ? WHERE id = ?", (new_vip, str(user_id)))
            conn.commit()
        finally:
            conn.close()
        await message.answer(
            f"{Emoji.VIP} <b>ПОЗДРАВЛЯЕМ! VIP УРОВЕНЬ ПОВЫШЕН!</b>\n\n"
            f"Ваш новый VIP уровень: {new_vip}\n"
            f"Вам доступны эксклюзивные бонусы и привилегии!"
        )
    
    # Отправляем благодарственное сообщение
    thank_text = (
        f"<b>{Emoji.HEART} {Emoji.THANK} {Emoji.SUPPORT} БЛАГОДАРИМ ЗА ПОДДЕРЖКУ! {Emoji.SUPPORT} {Emoji.THANK} {Emoji.HEART}</b>\n\n"
        f"<b>⭐ {Emoji.ROCKET} {Emoji.STAR} {Emoji.ROCKET} {Emoji.STAR} {Emoji.ROCKET}</b>\n\n"
        f"┌ <b>🪙 Пополнение:</b> {fmt_money(coins)}\n"
        f"├ <b>⭐ Звёзд:</b> {stars} ⭐\n"
        f"└ <b>💰 Новый баланс:</b> {fmt_money(new_balance)}\n\n"
        f"<b>{Emoji.HEART} СПАСИБО ЗА РАЗВИТИЕ И ПОМОЩЬ НАШЕМУ ПРОЕКТУ! {Emoji.HEART}</b>\n\n"
        f"<i>Ваша поддержка помогает нам становиться лучше!\n"
        f"Спасибо, что вы с нами! 🙏✨</i>\n\n"
        f"<b>🎉 ЖЕЛАЕМ УДАЧИ В ИГРАХ! 🎉</b>"
    )
    
    # Если депозит 15+ звезд
    if stars >= 15:
        thank_text += f"\n\n<b>⭐ ДЕПОЗИТ 15+ ЗВЁЗД!</b>\n<i>Напишите модератору @debashev для получения дополнительных бонусов!</i>"
    
    await message.answer(thank_text)
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"{Emoji.DONATE} <b>НОВЫЙ ДОНАТ!</b>\n"
                f"┌ 👤 Игрок: {mention_user(user_id, message.from_user.first_name)}\n"
                f"├ ⭐ Stars: {stars}\n"
                f"├ 💰 Получено: {fmt_money(coins)}\n"
                f"└ 📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        except Exception:
            pass

@dp.message(DonateStates.waiting_amount)
async def donate_custom_amount(message: Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        if stars < 10:
            await message.answer("<b>❌ МИНИМАЛЬНАЯ СУММА: 10 STARS!</b>\n\nВведите сумму больше 10:")
            return
        if stars > 10000:
            await message.answer("<b>❌ МАКСИМАЛЬНАЯ СУММА: 10,000 STARS!</b>\n\nВведите сумму меньше:")
            return
        
        coins = stars * STAR_TO_COIN_RATE
        
        await state.clear()
        await message.answer(
            f"<b>⭐ ПОДТВЕРЖДЕНИЕ ПОПОЛНЕНИЯ</b>\n\n"
            f"┌ <b>Telegram Stars:</b> {stars} ⭐\n"
            f"├ <b>Получите:</b> {fmt_money(coins)}\n"
            f"└ <b>Сумма к оплате:</b> {stars} ⭐\n\n"
            f"<i>Нажмите кнопку ниже для оплаты через Telegram Stars</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ Оплатить {stars} Stars", callback_data=f"donate:pay:{stars}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="donate:cancel")]
            ])
        )
    except ValueError:
        await message.answer("<b>❌ ВВЕДИТЕ ЦЕЛОЕ ЧИСЛО!</b>\n\nПример: 50")

# ==================== ИГРЫ: РУЛЕТКА ====================

@dp.message(Command("roulette"))
@dp.message(Command("рул"))
async def roulette_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(RouletteStates.waiting_amount)
        await message.answer(
            f"{Emoji.ROULETTE} <b>РУЛЕТКА</b>\n\n"
            f"<b>Введи сумму ставки:</b>\n"
            f"Минимальная ставка: {fmt_money(MIN_BET)}"
        )
        return
    
    try:
        bet = parse_amount(args[1])
        choice = args[2].lower()
    except:
        await message.answer("❌ Неверный формат!\nПример: /рул 100 красное")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    choice_map = {
        "красное": "red", "крас": "red", "red": "red",
        "черное": "black", "чёрное": "black", "чер": "black", "black": "black",
        "чет": "even", "четное": "even", "even": "even",
        "нечет": "odd", "нечетное": "odd", "odd": "odd",
        "зеро": "zero", "zero": "zero", "0": "zero",
    }
    choice = choice_map.get(choice, choice)
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств! Нужно: {fmt_money(bet)}")
        return
    
    win, multiplier, outcome_text, number, color = roulette_roll(choice)
    payout = round(bet * multiplier, 2) if win else 0
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"roulette:{choice}", f"num={number}", "roulette")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>РУЛЕТКА - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Выбор:</b> {choice}\n"
        f"├ <b>Выпало:</b> {outcome_text}\n"
        f"├ <b>Множитель:</b> x{multiplier}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Новый баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРЫ: КРАШ ====================

@dp.message(Command("crash"))
@dp.message(Command("краш"))
async def crash_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(CrashStates.waiting_amount)
        await message.answer(
            f"{Emoji.CRASH} <b>КРАШ</b>\n\n"
            f"<b>Введи сумму ставки и множитель:</b>\n"
            f"Пример: /краш 100 2.5\n"
            f"Минимальная ставка: {fmt_money(MIN_BET)}"
        )
        return
    
    try:
        bet = parse_amount(args[1])
        target = float(args[2])
    except:
        await message.answer("❌ Неверный формат!\nПример: /краш 100 2.5")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    if target < 1.01 or target > 100:
        await message.answer("❌ Множитель должен быть от 1.01 до 100")
        return
    
    crash_value = crash_roll()
    win = target <= crash_value
    payout = round(bet * target, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!")
        return
    
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"crash:{target}", f"crash={crash_value}", "crash")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "УСПЕХ!" if win else "КРАШ!"
    
    await message.answer(
        f"{result_icon} <b>КРАШ - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Твой множитель:</b> x{target}\n"
        f"├ <b>Выпало:</b> x{crash_value}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРЫ: КУБИК ====================

@dp.message(Command("cube"))
@dp.message(Command("кубик"))
async def cube_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(CubeStates.waiting_amount)
        await message.answer(
            f"{Emoji.CUBE} <b>КУБИК</b>\n\n"
            f"<b>Введи сумму ставки и число (1-6):</b>\n"
            f"Пример: /кубик 100 4"
        )
        return
    
    try:
        bet = parse_amount(args[1])
        guess = int(args[2])
    except:
        await message.answer("❌ Неверный формат!\nПример: /кубик 100 4")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    if guess not in range(1, 7):
        await message.answer("❌ Число должно быть от 1 до 6")
        return
    
    rolled = random.randint(1, 6)
    win = guess == rolled
    payout = round(bet * 5.8, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!")
        return
    
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"cube:{guess}", f"rolled={rolled}", "cube")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>КУБИК - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Твой выбор:</b> {guess}\n"
        f"├ <b>Выпало:</b> {rolled}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРЫ: КОСТИ ====================

@dp.message(Command("dice"))
@dp.message(Command("кости"))
async def dice_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(DiceStates.waiting_amount)
        await message.answer(
            f"{Emoji.DICE} <b>КОСТИ</b>\n\n"
            f"<b>Введи сумму ставки и исход (больше/меньше/7):</b>\n"
            f"Пример: /кости 100 больше"
        )
        return
    
    try:
        bet = parse_amount(args[1])
        choice = args[2].lower()
    except:
        await message.answer("❌ Неверный формат!\nПример: /кости 100 больше")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    choice_map = {"б": "больше", "м": "меньше", "7": "семь", "семь": "семь"}
    choice = choice_map.get(choice, choice)
    if choice not in {"больше", "меньше", "семь"}:
        await message.answer("❌ Выбери: больше, меньше или семь")
        return
    
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2
    
    win, multiplier = False, 0
    if choice == "больше" and total > 7:
        win, multiplier = True, 2.25
    elif choice == "меньше" and total < 7:
        win, multiplier = True, 2.25
    elif choice == "семь" and total == 7:
        win, multiplier = True, 5.0
    
    payout = round(bet * multiplier, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!")
        return
    
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"dice:{choice}", f"{d1}+{d2}={total}", "dice")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>КОСТИ - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Твой выбор:</b> {choice}\n"
        f"├ <b>Выпало:</b> {d1} + {d2} = {total}\n"
        f"├ <b>Множитель:</b> x{multiplier}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРЫ: БАШНЯ ====================

@dp.message(Command("tower"))
@dp.message(Command("башня"))
async def tower_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 2:
        await state.set_state(TowerStates.waiting_amount)
        await message.answer(
            f"{Emoji.TOWER} <b>БАШНЯ</b>\n\n"
            f"<b>Введи сумму ставки:</b>\n"
            f"Пример: /башня 100"
        )
        return
    
    try:
        bet = parse_amount(args[1])
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in TOWER_GAMES:
            await message.answer("❌ У тебя уже есть активная игра!")
            return
        
        ok, _ = reserve_bet(user_id, bet)
        if not ok:
            await message.answer(f"❌ Недостаточно средств!")
            return
        
        TOWER_GAMES[user_id] = {"bet": bet, "level": 0}
        
        await message.answer(
            f"{Emoji.TOWER} <b>БАШНЯ</b>\n\n"
            f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
            f"├ <b>Этаж:</b> 0\n"
            f"└ <b>Множитель:</b> x1.00\n\n"
            f"<b>Выбери безопасную секцию (1-3):</b>",
            reply_markup=tower_kb()
        )

@dp.callback_query(F.data.startswith("tower:"))
async def tower_callback(query: CallbackQuery):
    user_id = query.from_user.id
    game = TOWER_GAMES.get(user_id)
    if not game:
        await query.answer("❌ Нет активной игры!", show_alert=True)
        return
    
    action = query.data.split(":")[1]
    
    if action == "cash":
        level = game["level"]
        if level == 0:
            await query.answer("❌ Сделай хотя бы один ход!", show_alert=True)
            return
        mult = TOWER_MULTIPLIERS[level - 1]
        payout = round(game["bet"] * mult, 2)
        balance = finalize_reserved_bet(user_id, game["bet"], payout, "tower", f"cashout_level{level}", "tower")
        TOWER_GAMES.pop(user_id, None)
        await query.message.edit_text(
            f"{Emoji.WIN} <b>БАШНЯ - ВЫВОД СРЕДСТВ</b>\n\n"
            f"┌ <b>Этаж:</b> {level}\n"
            f"├ <b>Множитель:</b> x{mult}\n"
            f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
            f"└ <b>Баланс:</b> {fmt_money(balance)}"
        )
        await query.answer()
        return
    
    if action == "cancel":
        level = game["level"]
        if level == 0:
            payout = game["bet"]
            balance = finalize_reserved_bet(user_id, game["bet"], payout, "tower", "cancel_refund", "tower")
            await query.message.edit_text(f"🛑 Игра отменена. Возврат: {fmt_money(payout)}\nБаланс: {fmt_money(balance)}")
        else:
            balance = finalize_reserved_bet(user_id, game["bet"], 0, "tower", "cancel_lose", "tower")
            await query.message.edit_text(f"❌ Игра завершена. Потеряно: {fmt_money(game['bet'])}\nБаланс: {fmt_money(balance)}")
        TOWER_GAMES.pop(user_id, None)
        await query.answer()
        return
    
    # Ход
    chosen = int(action)
    safe = random.randint(1, 3)
    
    if chosen != safe:
        balance = finalize_reserved_bet(user_id, game["bet"], 0, "tower", f"lose_chosen{chosen}_safe{safe}", "tower")
        TOWER_GAMES.pop(user_id, None)
        await query.message.edit_text(
            f"{Emoji.LOSE} <b>БАШНЯ - ПРОИГРЫШ</b>\n\n"
            f"┌ <b>Твой выбор:</b> {chosen}\n"
            f"├ <b>Было опасно:</b> {safe}\n"
            f"└ <b>Потеряно:</b> {fmt_money(game['bet'])}\n\n"
            f"<b>Новый баланс:</b> {fmt_money(balance)}"
        )
        await query.answer()
        return
    
    game["level"] += 1
    level = game["level"]
    
    if level >= len(TOWER_MULTIPLIERS):
        mult = TOWER_MULTIPLIERS[-1]
        payout = round(game["bet"] * mult, 2)
        balance = finalize_reserved_bet(user_id, game["bet"], payout, "tower", "max_level", "tower")
        TOWER_GAMES.pop(user_id, None)
        await query.message.edit_text(
            f"{Emoji.WIN} <b>БАШНЯ - ПОБЕДА!</b>\n\n"
            f"┌ <b>Максимальный этаж!</b>\n"
            f"├ <b>Множитель:</b> x{mult}\n"
            f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
            f"└ <b>Баланс:</b> {fmt_money(balance)}"
        )
        await query.answer()
        return
    
    current_mult = TOWER_MULTIPLIERS[level - 1]
    current_win = round(game["bet"] * current_mult, 2)
    next_mult = TOWER_MULTIPLIERS[level] if level < len(TOWER_MULTIPLIERS) else TOWER_MULTIPLIERS[-1]
    
    await query.message.edit_text(
        f"{Emoji.TOWER} <b>БАШНЯ - ЭТАЖ {level}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(game['bet'])}\n"
        f"├ <b>Этаж:</b> {level}\n"
        f"├ <b>Текущий множитель:</b> x{current_mult}\n"
        f"├ <b>Можно забрать:</b> {fmt_money(current_win)}\n"
        f"└ <b>Следующий множитель:</b> x{next_mult}\n\n"
        f"<b>Выбери безопасную секцию (1-3):</b>",
        reply_markup=tower_kb()
    )
    await query.answer(f"✅ Безопасно! Этаж {level}")

# ==================== АДМИН КОМАНДЫ ====================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Только для администраторов!")
        return
    
    await message.answer(
        f"{Emoji.CROWN} <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"Выбери действие:",
        reply_markup=admin_panel_kb()
    )

@dp.callback_query(F.data == "admin:stats")
async def admin_stats(query: CallbackQuery):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа!", show_alert=True)
        return
    
    conn = get_db()
    try:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bets_count = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
        total_bet = conn.execute("SELECT COALESCE(SUM(bet_amount), 0) FROM bets").fetchone()[0]
        total_payout = conn.execute("SELECT COALESCE(SUM(payout), 0) FROM bets").fetchone()[0]
        donations_sum = conn.execute("SELECT COALESCE(SUM(coins), 0) FROM donations").fetchone()[0]
        donations_stars = conn.execute("SELECT COALESCE(SUM(stars), 0) FROM donations").fetchone()[0]
    finally:
        conn.close()
    
    profit = total_bet - total_payout
    
    await query.message.edit_text(
        f"{Emoji.STATS} <b>СТАТИСТИКА БОТА</b>\n\n"
        f"┌ 👥 <b>Пользователей:</b> {users_count}\n"
        f"├ 🎮 <b>Ставок:</b> {bets_count}\n"
        f"├ 💰 <b>Общий оборот:</b> {fmt_money(total_bet)}\n"
        f"├ 💸 <b>Выплат:</b> {fmt_money(total_payout)}\n"
        f"├ 📈 <b>Профит казино:</b> {fmt_money(profit)}\n"
        f"├ ⭐ <b>Всего донатов Stars:</b> {donations_stars}\n"
        f"└ 💎 <b>Всего донатов DC:</b> {fmt_money(donations_sum)}\n\n"
        f"<i>Данные обновлены: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "admin:top20")
async def admin_top20(query: CallbackQuery):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа!", show_alert=True)
        return
    
    rows = get_top_balances(20)
    lines = [f"{Emoji.TOP} <b>ТОП-20 ИГРОКОВ</b>", "<blockquote>"]
    for idx, row in enumerate(rows, start=1):
        lines.append(f"{idx}. {escape_html(row['first_name'] or f'ID {row['id']}')} — {fmt_money(float(row['coins']))}")
    lines.append("</blockquote>")
    
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "admin:refreshdb")
async def admin_refresh_db(query: CallbackQuery):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа!", show_alert=True)
        return
    
    init_db()
    await query.message.edit_text("✅ База данных успешно обновлена!")
    await query.answer()

# ==================== МЕНЮ НАВИГАЦИЯ ====================

@dp.callback_query(F.data == "menu:main")
async def menu_main_cb(query: CallbackQuery):
    user = get_user(query.from_user.id)
    await query.message.edit_text(
        f"<b>🏆 ГЛАВНОЕ МЕНЮ 🏆</b>\n\n"
        f"{Emoji.PLAYER} <b>Игрок:</b> {mention_user(query.from_user.id)}\n"
        f"{Emoji.COIN} <b>Баланс:</b> {fmt_money(user['coins'])}\n\n"
        f"<b>👇 ВЫБЕРИ РАЗДЕЛ 👇</b>",
        reply_markup=main_menu_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:games")
async def menu_games_cb(query: CallbackQuery):
    await query.message.edit_text(
        f"{Emoji.GAMES} <b>ВСЕ ИГРЫ</b>\n\n"
        f"<b>Выбери игру:</b>",
        reply_markup=games_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:bank")
async def menu_bank_cb(query: CallbackQuery):
    user = get_user(query.from_user.id)
    
    conn = get_db()
    try:
        active = conn.execute("SELECT COUNT(*) as count, COALESCE(SUM(principal), 0) as total FROM bank_deposits WHERE user_id = ? AND status = 'active'", (str(query.from_user.id),)).fetchone()
    finally:
        conn.close()
    
    await query.message.edit_text(
        f"{Emoji.BANK} <b>БАНКОВСКАЯ СИСТЕМА</b>\n\n"
        f"┌ 💰 <b>Баланс:</b> {fmt_money(user['coins'])}\n"
        f"├ 📊 <b>Активных депозитов:</b> {active['count']}\n"
        f"└ 💎 <b>Сумма в депозитах:</b> {fmt_money(active['total'])}\n\n"
        f"<b>💰 ПРОЦЕНТНЫЕ СТАВКИ:</b>\n"
        f"┌ 7 дней — +3%\n"
        f"├ 14 дней — +7%\n"
        f"└ 30 дней — +18%\n\n"
        f"<i>Выбери действие:</i>",
        reply_markup=bank_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:top")
async def menu_top_cb(query: CallbackQuery):
    rows = get_top_balances(15)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"{Emoji.TOP} <b>ТОП ИГРОКОВ</b>", "<blockquote>"]
    for idx, row in enumerate(rows, start=1):
        icon = medals.get(idx, f"{idx}.")
        lines.append(f"{icon} {escape_html(row['first_name'] or f'ID {row['id']}')} — <b>{fmt_money(float(row['coins']))}</b>")
    lines.append("</blockquote>")
    lines.append("\n<i>Используй /profile для просмотра статистики</i>")
    
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "menu:ref")
async def menu_ref_cb(query: CallbackQuery):
    user_id = query.from_user.id
    user = get_user(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    await query.message.edit_text(
        f"{Emoji.REF} <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"┌ {Emoji.COIN} <b>За друга:</b> {fmt_money(REF_REWARD)}\n"
        f"├ {Emoji.PERCENT} <b>{int(REF_PERCENT * 100)}% от проигрышей</b>\n"
        f"├ {Emoji.INVITED} <b>Приглашено:</b> {user['ref_count']}\n"
        f"├ {Emoji.COIN} <b>Заработано:</b> {fmt_money(user['ref_earned'])}\n"
        f"└ {Emoji.REF} <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data=f"ref:copy:{user_id}"),
             InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "menu:donate")
async def menu_donate_cb(query: CallbackQuery):
    await query.message.edit_text(
        f"<b>⭐ ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
        f"<b>Курс обмена:</b>\n"
        f"┌ 1 Telegram Star = 10,000 {CURRENCY_SHORT}\n"
        f"└ Минимальное пополнение: 10 Stars\n\n"
        f"<b>💰 ВЫБЕРИ СУММУ ПОПОЛНЕНИЯ:</b>\n\n"
        f"<i>💎 После оплаты монеты поступят автоматически!</i>\n"
        f"<i>⭐ Если депозите 15+ звёзд - напишите модератору @debashev</i>",
        reply_markup=get_donate_keyboard()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:profile")
async def menu_profile_cb(query: CallbackQuery):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    status_text = "👑 Админ" if is_admin_user(user_id) else (f"{Emoji.VIP} VIP {user['vip_level']}" if user['vip_level'] > 0 else f"{Emoji.PLAYER} Игрок")
    reg_date = fmt_dt(int(user["registered_at"] or 0))
    winrate = round((user['games_won'] / user['games_played'] * 100), 1) if user['games_played'] > 0 else 0
    
    await query.message.edit_text(
        f"<b>👤 ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"┌ {Emoji.PLAYER} <b>Имя:</b> {mention_user(user_id, user['first_name'] or 'Игрок')}\n"
        f"├ {Emoji.STATUS} <b>Статус:</b> {status_text}\n"
        f"├ {Emoji.COIN} <b>Баланс:</b> {fmt_money(user['coins'])}\n"
        f"├ {Emoji.GAMES} <b>Сыграно игр:</b> {user['games_played']}\n"
        f"├ {Emoji.TOP} <b>Побед:</b> {user['games_won']} ({winrate}%)\n"
        f"├ {Emoji.WIN} <b>Выиграно:</b> {fmt_money(user['won_coins'])}\n"
        f"├ {Emoji.LOSE} <b>Проиграно:</b> {fmt_money(user['lost_coins'])}\n"
        f"├ {Emoji.REF} <b>Рефералов:</b> {user['ref_count']}\n"
        f"├ {Emoji.REF} <b>Заработано с реф:</b> {fmt_money(user['ref_earned'])}\n"
        f"├ {Emoji.DATE} <b>Регистрация:</b> {reg_date}\n"
        f"└ {Emoji.DONATE} <b>Пополнено:</b> {fmt_money(user['total_donated'] or 0)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(query: CallbackQuery):
    await query.message.edit_text(
        f"✅ <b>ПОДПИСКА ПОДТВЕРЖДЕНА!</b>\n\n"
        f"Добро пожаловать в DodoCoin Casino!\n"
        f"Используй меню для навигации:",
        reply_markup=main_menu_kb()
    )
    await query.answer("Добро пожаловать!")

@dp.callback_query(F.data.startswith("ref:copy:"))
async def ref_copy_cb(query: CallbackQuery):
    user_id = query.data.split(":")[-1]
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await query.message.answer(f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>")
    await query.answer("Ссылка отправлена в чат!")

# ==================== JSON ФУНКЦИИ ====================

def set_json_value(key: str, value: Any) -> None:
    conn = get_db()
    try:
        conn.execute("INSERT INTO json_data (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()

def get_json_value(key: str, default: Any = None) -> Any:
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM json_data WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return default
    finally:
        conn.close()

# ==================== ОТМЕНА ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"отмена", "/cancel", "cancel"})
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    clear_active_sessions(message.from_user.id)
    await message.answer("🛑 Действие отменено.")

def normalize_text(text: Optional[str]) -> str:
    return " ".join(str(text or "").lower().split())

# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска бота"""
    init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Устанавливаем команды     # Устанавливаем команды бота
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="📚 Помощь"),
        BotCommand(command="balance", description="💰 Баланс"),
        BotCommand(command="profile", description="👤 Профиль"),
        BotCommand(command="bonus", description="🎁 Бонус"),
        BotCommand(command="daily", description="📅 Ежедневный бонус"),
        BotCommand(command="weekly", description="📆 Еженедельный бонус"),
        BotCommand(command="top", description="🏆 Топ игроков"),
        BotCommand(command="referral", description="🔗 Реферальная система"),
        BotCommand(command="donate", description="⭐ Пополнить баланс"),
        BotCommand(command="roulette", description="🎡 Рулетка"),
        BotCommand(command="crash", description="📈 Краш"),
        BotCommand(command="tower", description="🗼 Башня"),
        BotCommand(command="mines", description="💣 Мины"),
        BotCommand(command="ochko", description="🎴 Очко"),
        BotCommand(command="cube", description="🎲 Кубик"),
        BotCommand(command="dice", description="🎯 Кости"),
        BotCommand(command="bank", description="🏦 Банк"),
        BotCommand(command="transfer", description="💸 Перевод"),
        BotCommand(command="promo", description="🎟 Промокод"),
    ]
    
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    
    # Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("✅ Бот успешно запущен!")
    print(f"📊 Бот: @{BOT_USERNAME}")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💎 Курс: 1 Star = {STAR_TO_COIN_RATE:,} {CURRENCY_SHORT}")
    
    await dp.start_polling(bot)

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    asyncio.run(main())
