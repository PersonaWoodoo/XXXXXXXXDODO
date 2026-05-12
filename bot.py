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
import hashlib
import hmac
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum
import re

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
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    InputFile,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== КОНФИГУРАЦИЯ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = "8365761672:AAELKM3NAQppEos41sTXJ9v-54CI8LhfQiU"
    logger.warning("Using hardcoded token!")

ADMIN_IDS = {8478884644}
BOT_USERNAME = "DodoCoin_bot"

# ==================== ЭМОДЗИ ====================

class Emoji:
    CROWN = "👑"
    DIAMOND = "💎"
    VIP = "✨"
    PLAYER = "👤"
    ID = "🆔"
    STATUS = "⚡"
    GAMES = "🎮"
    TOP = "🏆"
    TURNOVER = "🔄"
    LOST = "📉"
    DATE = "📅"
    COIN = "💰"
    BONUS = "🎁"
    REF = "🔗"
    INVITED = "🧲"
    WIN = "🎉"
    LOSE = "💔"
    BANK = "🏦"
    CHECK = "🧾"
    PROMO = "🎟️"
    CRASH = "📈"
    ROULETTE = "🎡"
    DICE = "🎲"
    CUBE = "🎯"
    FOOTBALL = "⚽"
    BASKET = "🏀"
    TOWER = "🗼"
    GOLD = "🥇"
    MINES = "💣"
    CARDS = "🃏"
    SETTINGS = "⚙️"
    STATS = "📊"
    INFO = "ℹ️"
    WARNING = "⚠️"
    ERROR = "❌"
    SUCCESS = "✅"
    CLOCK = "⏰"
    GIFT = "🎁"
    SHOP = "🛒"
    TRADE = "🔄"
    DUEL = "⚔️"
    TOURNAMENT = "🏆"
    JACKPOT = "🎰"
    LOTTERY = "🍀"
    WHEEL = "🎡"
    FISHING = "🎣"
    FARM = "🌾"
    PET = "🐕"
    CASINO = "🎲"
    SLOTS = "🎰"
    POKER = "♠️"
    BINGO = "🔴"
    LOTTO = "🎫"
    SCRATCH = "🎯"
    COINFLIP = "🪙"

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
MONTHLY_BONUS = 10000.0

CHANNEL_ID = "@dodoCoin_news"
CHAT_ID = "@dodocoin_chat"

BANK_TERMS = {
    7: 0.03,
    14: 0.07,
    30: 0.18,
    60: 0.40,
    90: 0.65,
    180: 1.50,
    365: 3.50
}

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

TOWER_MULTIPLIERS = [1.20, 1.48, 1.86, 2.35, 2.95, 3.75, 4.85, 6.15, 7.80, 10.0, 12.5, 15.0]
GOLD_MULTIPLIERS = [1.15, 1.35, 1.62, 2.0, 2.55, 3.25, 4.2, 5.5, 7.2, 9.0, 11.0]
DIAMOND_MULTIPLIERS = [1.12, 1.28, 1.48, 1.72, 2.02, 2.4, 2.92, 3.6, 4.5, 5.6, 7.0, 8.5]
FOOTBALL_MULTIPLIERS = {"gol": 1.6, "mimo": 2.2, "penalty": 3.0}
BASKET_MULTIPLIERS = {2: 1.5, 3: 1.8, 4: 2.2, 5: 3.0}
SLOTS_PAYOUTS = {
    "🍒🍒🍒": 10,
    "🍋🍋🍋": 20,
    "🍊🍊🍊": 30,
    "🍉🍉🍉": 50,
    "🔔🔔🔔": 100,
    "⭐️⭐️⭐️": 200,
    "💎💎💎": 500,
    "7️⃣7️⃣7️⃣": 1000,
    "🎰🎰🎰": 5000,
}

MAX_DAILY_WIN = 1000000.0
MAX_BET_PER_GAME = 50000.0

# ==================== ДАТА КЛАССЫ ====================

@dataclass
class UserStats:
    user_id: int
    coins: float
    games_played: int
    games_won: int
    winrate: float
    total_bet: float
    total_win: float
    net_profit: float
    vip_level: int
    ref_count: int
    ref_earned: float
    
@dataclass
class GameResult:
    win: bool
    payout: float
    multiplier: float
    message: str
    details: Dict[str, Any]

@dataclass
class Tournament:
    id: int
    name: str
    prize_pool: float
    min_bet: float
    start_time: int
    end_time: int
    participants: List[int]
    winners: List[Tuple[int, float]]
    
@dataclass
class Achievement:
    id: str
    name: str
    description: str
    reward: float
    required_progress: int

# ==================== ДОСТИЖЕНИЯ ====================

ACHIEVEMENTS = {
    "first_win": Achievement("first_win", "Первая победа", "Выиграй первую игру", 500, 1),
    "high_roller": Achievement("high_roller", "Высокий ставщик", "Сделай ставку 10000", 5000, 1),
    "millionaire": Achievement("millionaire", "Миллионер", "Накопи 1,000,000", 100000, 1),
    "serial_winner": Achievement("serial_winner", "Серийный победитель", "Выиграй 10 игр подряд", 10000, 10),
    "jackpot_hunter": Achievement("jackpot_hunter", "Охотник за джекпотом", "Сорви джекпот", 50000, 1),
    "tournament_champion": Achievement("tournament_champion", "Чемпион турнира", "Победи в турнире", 25000, 1),
    "ref_master": Achievement("ref_master", "Мастер рефералов", "Пригласи 100 друзей", 50000, 100),
    "vip_player": Achievement("vip_player", "VIP игрок", "Достигни VIP уровня 5", 100000, 5),
    "marathon": Achievement("marathon", "Марафонец", "Сыграй 1000 игр", 25000, 1000),
    "lucky_one": Achievement("lucky_one", "Везунчик", "Выиграй с множителем x100", 50000, 1),
}

# ==================== FSM СОСТОЯНИЯ (РАСШИРЕННЫЕ) ====================

class RegisterStates(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_country = State()

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
    waiting_term = State()

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

class FootballStates(StatesGroup):
    waiting_amount = State()

class BasketStates(StatesGroup):
    waiting_amount = State()

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

class SlotsStates(StatesGroup):
    waiting_amount = State()

class PokerStates(StatesGroup):
    waiting_amount = State()
    waiting_action = State()

class BingoStates(StatesGroup):
    waiting_amount = State()
    waiting_number = State()

class LottoStates(StatesGroup):
    waiting_amount = State()
    waiting_numbers = State()

class ScratchStates(StatesGroup):
    waiting_amount = State()

class CoinFlipStates(StatesGroup):
    waiting_amount = State()
    waiting_choice = State()

class FishingStates(StatesGroup):
    waiting_bait = State()

class FarmStates(StatesGroup):
    waiting_crop = State()

class PetStates(StatesGroup):
    waiting_action = State()

class AdminBroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()

class AdminGiveStates(StatesGroup):
    waiting_user = State()
    waiting_amount = State()
    waiting_reason = State()

class JackpotStates(StatesGroup):
    waiting_amount = State()

class DuelStates(StatesGroup):
    waiting_amount = State()
    waiting_opponent = State()
    waiting_choice = State()

class TournamentStates(StatesGroup):
    waiting_bet = State()
    waiting_register = State()

class TradeStates(StatesGroup):
    waiting_user = State()
    waiting_amount = State()
    waiting_item = State()
    waiting_confirm = State()

class SupportStates(StatesGroup):
    waiting_message = State()
    waiting_response = State()

class ShopStates(StatesGroup):
    waiting_item = State()
    waiting_quantity = State()

class WheelStates(StatesGroup):
    waiting_spin = State()

class LotteryStates(StatesGroup):
    waiting_ticket = State()

# ==================== ИГРОВЫЕ ХРАНИЛИЩА ====================

TOWER_GAMES: Dict[int, Dict[str, Any]] = {}
GOLD_GAMES: Dict[int, Dict[str, Any]] = {}
DIAMOND_GAMES: Dict[int, Dict[str, Any]] = {}
MINES_GAMES: Dict[int, Dict[str, Any]] = {}
OCHKO_GAMES: Dict[int, Dict[str, Any]] = {}
FOOTBALL_GAMES: Dict[int, Dict[str, Any]] = {}
CRASH_GAMES: Dict[int, Dict[str, Any]] = {}
DUEL_GAMES: Dict[int, Dict[str, Any]] = {}
JACKPOT_GAMES: Dict[int, Dict[str, Any]] = {}
SLOTS_GAMES: Dict[int, Dict[str, Any]] = {}
POKER_GAMES: Dict[int, Dict[str, Any]] = {}
BINGO_GAMES: Dict[int, Dict[str, Any]] = {}
LOTTO_GAMES: Dict[int, Dict[str, Any]] = {}
SCRATCH_GAMES: Dict[int, Dict[str, Any]] = {}
COINFLIP_GAMES: Dict[int, Dict[str, Any]] = {}
FISHING_GAMES: Dict[int, Dict[str, Any]] = {}
FARM_GAMES: Dict[int, Dict[str, Any]] = {}
PET_GAMES: Dict[int, Dict[str, Any]] = {}
WHEEL_GAMES: Dict[int, Dict[str, Any]] = {}
LOTTERY_GAMES: Dict[int, Dict[str, Any]] = {}

user_game_locks: Dict[str, asyncio.Lock] = {}
active_duels: Dict[int, Dict[str, Any]] = {}
active_tournaments: Dict[int, Tournament] = {}
jackpot_pool: float = 0
jackpot_contributors: Dict[int, float] = {}

# ==================== БАЗА ДАННЫХ (РАСШИРЕННАЯ) ====================

def init_db():
    """Инициализация базы данных со всеми таблицами"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица пользователей
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
            last_name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            daily_bonus_taken INTEGER DEFAULT 0,
            weekly_bonus_taken INTEGER DEFAULT 0,
            monthly_bonus_taken INTEGER DEFAULT 0,
            total_deposit REAL DEFAULT 0.0,
            total_withdraw REAL DEFAULT 0.0,
            vip_level INTEGER DEFAULT 0,
            vip_exp REAL DEFAULT 0.0,
            banned INTEGER DEFAULT 0,
            ban_reason TEXT DEFAULT '',
            language TEXT DEFAULT 'ru',
            referal_code TEXT DEFAULT '',
            two_factor_enabled INTEGER DEFAULT 0,
            withdraw_limit REAL DEFAULT 100000.0,
            daily_withdrawn REAL DEFAULT 0.0,
            last_withdraw_reset INTEGER DEFAULT 0,
            avatar TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            country TEXT DEFAULT '',
            age INTEGER DEFAULT 0
        )
    """)

    # Таблица ставок
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
            game_type TEXT DEFAULT '',
            multiplier REAL DEFAULT 1.0,
            profit REAL DEFAULT 0.0
        )
    """)

    # Таблица промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward REAL,
            claimed TEXT DEFAULT '[]',
            remaining_activations INTEGER DEFAULT 0,
            created_by TEXT DEFAULT '',
            created_at INTEGER DEFAULT 0,
            expires_at INTEGER DEFAULT 0,
            max_activations INTEGER DEFAULT 0,
            min_level INTEGER DEFAULT 0
        )
    """)

    # Таблица депозитов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            principal REAL,
            rate REAL,
            term_days INTEGER,
            opened_at INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            closed_at INTEGER,
            interest_earned REAL DEFAULT 0.0,
            auto_renew INTEGER DEFAULT 0
        )
    """)

    # Таблица для JSON данных
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS json_data (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER DEFAULT 0
        )
    """)

    # Таблица турниров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            prize_pool REAL,
            min_bet REAL,
            start_time INTEGER,
            end_time INTEGER,
            status TEXT DEFAULT 'active',
            participants TEXT DEFAULT '[]',
            winners TEXT DEFAULT '[]',
            creator TEXT DEFAULT '',
            game_type TEXT DEFAULT '',
            max_participants INTEGER DEFAULT 0
        )
    """)

    # Таблица предметов инвентаря
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            item_id TEXT,
            item_name TEXT,
            item_type TEXT DEFAULT 'common',
            quantity INTEGER DEFAULT 1,
            acquired_at INTEGER DEFAULT 0,
            equipped INTEGER DEFAULT 0,
            durability INTEGER DEFAULT 100,
            stats TEXT DEFAULT '{}'
        )
    """)

    # Таблица достижений
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            achievement_id TEXT,
            unlocked_at INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0
        )
    """)

    # Таблица логов администраторов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id TEXT,
            action TEXT,
            target_id TEXT,
            amount REAL,
            reason TEXT,
            ts INTEGER DEFAULT 0,
            ip_address TEXT DEFAULT ''
        )
    """)

    # Таблица поддержки
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at INTEGER DEFAULT 0,
            resolved_at INTEGER,
            admin_response TEXT,
            category TEXT DEFAULT 'general',
            priority INTEGER DEFAULT 1
        )
    """)

    # Таблица транзакций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            type TEXT,
            amount REAL,
            balance_after REAL,
            description TEXT,
            ts INTEGER DEFAULT 0,
            reference_id TEXT DEFAULT ''
        )
    """)

    # Таблица реферальной сети
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals_network (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referer_id TEXT,
            referred_id TEXT,
            level INTEGER DEFAULT 1,
            joined_at INTEGER DEFAULT 0,
            earnings REAL DEFAULT 0.0
        )
    """)

    # Таблица ежедневных заданий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            quest_id TEXT,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            date TEXT DEFAULT ''
        )
    """)

    # Таблица торгов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT,
            item_id TEXT,
            item_name TEXT,
            price REAL,
            quantity INTEGER,
            listed_at INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    """)

    # Таблица голосований
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            vote_for TEXT,
            vote_date INTEGER DEFAULT 0,
            reward_claimed INTEGER DEFAULT 0
        )
    """)

    # Таблица предсказаний
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            event TEXT,
            prediction TEXT,
            bet_amount REAL,
            potential_win REAL,
            created_at INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0,
            result TEXT DEFAULT ''
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts() -> int:
    return int(time.time())

def fmt_money(value: float) -> str:
    value = round(float(value), 2)
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value/1_000_000_000:.1f}B {CURRENCY_SHORT}"
    elif abs_value >= 1_000_000:
        return f"{value/1_000_000:.1f}M {CURRENCY_SHORT}"
    elif abs_value >= 1000:
        return f"{value/1000:.1f}K {CURRENCY_SHORT}"
    elif abs(value - int(value)) < 1e-9:
        return f"{int(value)} {CURRENCY_SHORT}"
    else:
        return f"{value:.2f} {CURRENCY_SHORT}"

def fmt_dt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S") if ts > 0 else "Неизвестно"

def fmt_left(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if days > 0:
        return f"{days}д {hours}ч"
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
    elif raw.endswith(("b", "б")):
        raw = raw[:-1]
        multiplier = 1000000000.0
    
    value = float(raw) * multiplier
    if value <= 0:
        raise ValueError("amount must be positive")
    if value > 100_000_000:
        raise ValueError("amount too large")
    return round(value, 2)

def escape_html(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=False)

def mention_user(user_id: int, name: Optional[str] = None) -> str:
    label = escape_html(name or f"ID {user_id}")
    return f'<a href="tg://user?id={int(user_id)}">{label}</a>'

def is_admin_user(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

def ensure_user_in_conn(conn: sqlite3.Connection, user_id: int, ref_id: Optional[str] = None, 
                        first_name: str = "", last_name: str = "", username: str = "") -> None:
    now = now_ts()
    row = conn.execute("SELECT id, registered_at, ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
    
    if not row:
        referal_code = generate_referal_code()
        conn.execute("""
            INSERT INTO users (id, coins, games_played, games_won, lost_coins, won_coins, 
            status, registered_at, last_active, ref_id, ref_earned, ref_count, 
            first_name, last_name, username, referal_code)
            VALUES (?, ?, 0, 0, 0, 0, 0, ?, ?, ?, 0, 0, ?, ?, ?, ?)
        """, (str(user_id), START_BALANCE, now, now, ref_id, first_name, last_name, username, referal_code))
        
        if ref_id and ref_id != str(user_id):
            conn.execute("UPDATE users SET ref_count = ref_count + 1, coins = coins + ? WHERE id = ?", 
                        (REF_REWARD, ref_id))
            conn.execute("""
                INSERT INTO referrals_network (referer_id, referred_id, level, joined_at, earnings)
                VALUES (?, ?, 1, ?, 0)
            """, (ref_id, str(user_id), now))
    else:
        if not row["registered_at"]:
            conn.execute("UPDATE users SET registered_at = ?, ref_id = COALESCE(ref_id, ?) WHERE id = ?", 
                        (now, ref_id, str(user_id)))
        conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (now, str(user_id)))

def generate_referal_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def ensure_user(user_id: int, ref_id: Optional[str] = None, first_name: str = "", 
                last_name: str = "", username: str = "") -> None:
    conn = get_db()
    try:
        ensure_user_in_conn(conn, user_id, ref_id, first_name, last_name, username)
        conn.commit()
    finally:
        conn.close()

def get_user(user_id: int) -> sqlite3.Row:
    conn = get_db()
    try:
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return row
    finally:
        conn.close()

def set_json_value(key: str, value: Any) -> None:
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO json_data (key, value, updated_at) 
            VALUES (?, ?, ?) 
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, json.dumps(value, ensure_ascii=False), now_ts()))
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

def add_transaction(user_id: int, trans_type: str, amount: float, description: str, reference_id: str = ""):
    conn = get_db()
    try:
        user = get_user(user_id)
        balance = user["coins"] if user else 0
        conn.execute("""
            INSERT INTO transactions (user_id, type, amount, balance_after, description, ts, reference_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(user_id), trans_type, amount, float(balance), description, now_ts(), reference_id))
        conn.commit()
    finally:
        conn.close()

def add_balance(user_id: int, delta: float, reason: str = "") -> float:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (round(delta, 2), str(user_id)))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        new_balance = float(row["coins"] or 0)
        if reason:
            add_transaction(user_id, "bonus" if delta > 0 else "withdraw", delta, reason)
        conn.commit()
        return new_balance
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def reserve_bet(user_id: int, bet: float) -> Tuple[bool, float]:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        coins = float(row["coins"] or 0)
        
        if coins < bet:
            conn.rollback()
            return False, coins
        
        new_balance = round(coins - bet, 2)
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, str(user_id)))
        conn.commit()
        return True, new_balance
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in reserve_bet: {e}")
        raise
    finally:
        conn.close()

def finalize_reserved_bet(user_id: int, bet: float, payout: float, choice: str, 
                         outcome: str, game_type: str = "") -> float:
    payout = round(max(0.0, payout), 2)
    conn = get_db()
    
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        
        if payout > 0:
            conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (payout, str(user_id)))
            conn.execute("UPDATE users SET games_won = games_won + 1 WHERE id = ?", (str(user_id),))
            conn.execute("UPDATE users SET won_coins = won_coins + ? WHERE id = ?", (payout - bet, str(user_id)))
            add_transaction(user_id, "win", payout - bet, f"Выигрыш в {game_type}")
        else:
            conn.execute("UPDATE users SET lost_coins = lost_coins + ? WHERE id = ?", (bet, str(user_id)))
            add_transaction(user_id, "loss", -bet, f"Проигрыш в {game_type}")
            
            user_row = conn.execute("SELECT ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if user_row and user_row["ref_id"]:
                ref_bonus = round(bet * REF_PERCENT, 2)
                conn.execute("""
                    UPDATE users SET ref_earned = ref_earned + ?, coins = coins + ? 
                    WHERE id = ?
                """, (ref_bonus, ref_bonus, user_row["ref_id"]))
                add_transaction(user_row["ref_id"], "ref_bonus", ref_bonus, f"Реферальный бонус от {user_id}")
        
        conn.execute("UPDATE users SET games_played = games_played + 1 WHERE id = ?", (str(user_id),))
        
        conn.execute("""
            INSERT INTO bets (user_id, bet_amount, choice, outcome, win, payout, ts, game_type) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(user_id), round(bet, 2), choice, outcome, 1 if payout > 0 else 0, payout, now_ts(), game_type))
        
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        
        check_achievements(user_id)
        update_vip_level(user_id)
        
        return float(row["coins"] or 0)
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in finalize_reserved_bet: {e}")
        raise
    finally:
        conn.close()

def check_achievements(user_id: int):
    user = get_user(user_id)
    if not user:
        return
    
    # Проверка различных достижений
    stats = get_user_stats(user_id)
    
    for ach_id, achievement in ACHIEVEMENTS.items():
        progress = 0
        if ach_id == "first_win" and stats.games_won >= 1:
            progress = 1
        elif ach_id == "high_roller" and any_bet_above(user_id, 10000):
            progress = 1
        elif ach_id == "millionaire" and stats.coins >= 1000000:
            progress = 1
        elif ach_id == "ref_master" and stats.ref_count >= 100:
            progress = stats.ref_count
        elif ach_id == "vip_player" and stats.vip_level >= 5:
            progress = stats.vip_level
        elif ach_id == "marathon" and stats.games_played >= 1000:
            progress = stats.games_played
        
        if progress >= achievement.required_progress:
            unlock_achievement(user_id, ach_id, achievement.reward)

def unlock_achievement(user_id: int, achievement_id: str, reward: float):
    conn = get_db()
    try:
        existing = conn.execute("""
            SELECT * FROM achievements WHERE user_id = ? AND achievement_id = ? AND claimed = 0
        """, (str(user_id), achievement_id)).fetchone()
        
        if not existing:
            conn.execute("""
                INSERT INTO achievements (user_id, achievement_id, unlocked_at, progress, claimed)
                VALUES (?, ?, ?, ?, 0)
            """, (str(user_id), achievement_id, now_ts(), 1))
            add_balance(user_id, reward, f"Достижение: {ACHIEVEMENTS[achievement_id].name}")
            conn.commit()
            return True
    finally:
        conn.close()
    return False

def any_bet_above(user_id: int, threshold: float) -> bool:
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT 1 FROM bets WHERE user_id = ? AND bet_amount >= ? LIMIT 1
        """, (str(user_id), threshold)).fetchone()
        return row is not None
    finally:
        conn.close()

def update_vip_level(user_id: int):
    conn = get_db()
    try:
        user = conn.execute("SELECT coins, total_deposit FROM users WHERE id = ?", (str(user_id),)).fetchone()
        if not user:
            return
        
        total_value = float(user["coins"] or 0) + float(user["total_deposit"] or 0)
        
        if total_value >= 1000000:
            vip_level = 5
        elif total_value >= 500000:
            vip_level = 4
        elif total_value >= 100000:
            vip_level = 3
        elif total_value >= 25000:
            vip_level = 2
        elif total_value >= 5000:
            vip_level = 1
        else:
            vip_level = 0
        
        conn.execute("UPDATE users SET vip_level = ? WHERE id = ?", (vip_level, str(user_id)))
        conn.commit()
    finally:
        conn.close()

def get_user_stats(user_id: int) -> UserStats:
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        if not user:
            return UserStats(user_id, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN win = 1 THEN 1 ELSE 0 END) as wins,
                SUM(bet_amount) as total_bet,
                SUM(payout - bet_amount) as net
            FROM bets WHERE user_id = ?
        """, (str(user_id),)).fetchone()
        
        winrate = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
        
        return UserStats(
            user_id=user_id,
            coins=float(user["coins"] or 0),
            games_played=stats["total"] or 0,
            games_won=stats["wins"] or 0,
            winrate=round(winrate, 2),
            total_bet=stats["total_bet"] or 0,
            total_win=stats["total_bet"] + (stats["net"] or 0),
            net_profit=stats["net"] or 0,
            vip_level=int(user["vip_level"] or 0),
            ref_count=int(user["ref_count"] or 0),
            ref_earned=float(user["ref_earned"] or 0)
        )
    finally:
        conn.close()

def get_top_balances(limit: int = 10) -> list[Dict[str, Any]]:
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, coins, first_name, username, vip_level 
            FROM users 
            WHERE banned = 0
            ORDER BY coins DESC, id ASC 
            LIMIT ?
        """, (int(limit),)).fetchall()
        conn.commit()
        return [{
            "id": row["id"], 
            "coins": row["coins"], 
            "name": row["first_name"] or row["username"] or f"ID {row['id']}",
            "vip_level": row["vip_level"]
        } for row in rows]
    finally:
        conn.close()

def clear_active_sessions(user_id: int) -> None:
    for d in (TOWER_GAMES, GOLD_GAMES, DIAMOND_GAMES, MINES_GAMES, OCHKO_GAMES, 
              FOOTBALL_GAMES, CRASH_GAMES, SLOTS_GAMES, POKER_GAMES, BINGO_GAMES,
              LOTTO_GAMES, SCRATCH_GAMES, COINFLIP_GAMES):
        d.pop(user_id, None)

def _game_lock(user_id: int | str) -> asyncio.Lock:
    key = str(user_id)
    if key not in user_game_locks:
        user_game_locks[key] = asyncio.Lock()
    return user_game_locks[key]

# ==================== ФИЛЬТР ПОДПИСКИ ====================

async def check_subscription(bot: Bot, user_id: int) -> Tuple[bool, str]:
    not_subscribed = []
    try:
        cm = await bot.get_chat_member(CHANNEL_ID, user_id)
        if cm.status in ("left", "kicked", "restricted"):
            not_subscribed.append(f"📢 Канал: {CHANNEL_ID}")
    except Exception:
        not_subscribed.append(f"📢 Канал: {CHANNEL_ID}")
    
    try:
        cm = await bot.get_chat_member(CHAT_ID, user_id)
        if cm.status in ("left", "kicked", "restricted"):
            not_subscribed.append(f"💬 Чат: {CHAT_ID}")
    except Exception:
        not_subscribed.append(f"💬 Чат: {CHAT_ID}")
    
    if not_subscribed:
        lines = [f"{Emoji.WARNING} <b>Для игры нужна подписка:</b>", ""] + not_subscribed + ["", "<i>Подпишись и попробуй снова.</i>"]
        return False, "\n".join(lines)
    return True, ""

class SubscriptionFilter(BaseFilter):
    async def __call__(self, message: Message, bot: Bot) -> bool:
        subscribed, sub_msg = await check_subscription(bot, message.from_user.id)
        if not subscribed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/dodoCoin_news")],
                [InlineKeyboardButton(text="💬 Войти в чат", url="https://t.me/dodocoin_chat")],
                [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
            ])
            await message.answer(sub_msg, reply_markup=kb)
            return False
        return True

# ==================== ИГРЫ (РАСШИРЕННЫЕ) ====================

def roulette_roll(choice: str) -> Tuple[bool, float, str, int, str]:
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in RED_NUMBERS else "black")
    parity = "zero" if number == 0 else ("even" if number % 2 == 0 else "odd")
    win, multiplier = False, 0.0
    
    if choice == "red" and color == "red":
        win, multiplier = True, 2.0
    elif choice == "black" and color == "black":
        win, multiplier = True, 2.0
    elif choice == "even" and parity == "even":
        win, multiplier = True, 2.0
    elif choice == "odd" and parity == "odd":
        win, multiplier = True, 2.0
    elif choice == "zero" and number == 0:
        win, multiplier = True, 36.0
    elif choice == "1-12" and 1 <= number <= 12:
        win, multiplier = True, 3.0
    elif choice == "13-24" and 13 <= number <= 24:
        win, multiplier = True, 3.0
    elif choice == "25-36" and 25 <= number <= 36:
        win, multiplier = True, 3.0
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
    elif r < 0.95:
        return round(random.uniform(15.01, 50.0), 2)
    else:
        return round(random.uniform(50.01, 200.0), 2)

def slots_spin() -> Tuple[List[str], float]:
    symbols = ["🍒", "🍋", "🍊", "🍉", "🔔", "⭐️", "💎", "7️⃣", "🎰"]
    weights = [30, 25, 20, 15, 10, 8, 5, 3, 1]
    
    reels = []
    for _ in range(3):
        reels.append(random.choices(symbols, weights=weights)[0])
    
    combination = "".join(reels)
    multiplier = SLOTS_PAYOUTS.get(combination, 0)
    
    return reels, multiplier

def blackjack_hand_value(cards: List[Tuple[str, str]]) -> int:
    value = 0
    aces = 0
    
    for rank, _ in cards:
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            aces += 1
            value += 11
        else:
            value += int(rank)
    
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    
    return value

def mines_multiplier(opened_count: int, mines_count: int, total_cells: int = 25) -> float:
    if opened_count <= 0:
        return 1.0
    safe_cells = total_cells - mines_count
    base = total_cells / max(1.0, safe_cells)
    mult = (base ** opened_count) * 0.95
    return round(mult, 2)

def coinflip_result() -> Tuple[str, float]:
    result = random.choice(["heads", "tails"])
    return result, 1.95

def fishing_catch() -> Tuple[str, float]:
    catches = [
        ("🐟 Маленькая рыбка", 10, 50),
        ("🐠 Средняя рыбка", 25, 40),
        ("🐡 Большая рыбка", 50, 20),
        ("🦀 Краб", 30, 30),
        ("🐙 Осьминог", 75, 15),
        ("🦑 Кальмар", 100, 10),
        ("🐋 Кит", 500, 5),
        ("👢 Старый ботинок", 0, 10),
        ("⚓️ Якорь", 0, 5),
    ]
    fish, reward, chance = random.choices(catches, weights=[c[2] for c in catches])[0]
    return fish, reward

def wheel_of_fortune_spin() -> Tuple[str, float]:
    sectors = [
        ("💎 Джекпот!", 100, 1),
        ("💰 1000 монет", 1000, 5),
        ("💰 500 монет", 500, 10),
        ("💰 250 монет", 250, 15),
        ("💰 100 монет", 100, 20),
        ("💰 50 монет", 50, 20),
        ("🎁 Бонус x2", 0, 10),
        ("😢 Попробуй ещё", 0, 19),
    ]
    sector, reward, weight = random.choices(sectors, weights=[s[2] for s in sectors])[0]
    return sector, reward

def lottery_draw(tickets: int) -> Tuple[int, float]:
    total_tickets = tickets + random.randint(1, 1000)
    winning_ticket = random.randint(1, total_tickets)
    if winning_ticket <= tickets:
        prize = total_tickets * random.uniform(0.8, 1.2)
        return 1, prize
    return 0, 0

# ==================== UI КЛАВИАТУРЫ ====================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.GAMES} Игры", callback_data="menu:games"),
         InlineKeyboardButton(text=f"{Emoji.BANK} Банк", callback_data="menu:bank")],
        [InlineKeyboardButton(text=f"{Emoji.TOP} Топ", callback_data="menu:top"),
         InlineKeyboardButton(text=f"{Emoji.REF} Рефералы", callback_data="menu:ref")],
        [InlineKeyboardButton(text=f"{Emoji.SHOP} Магазин", callback_data="menu:shop"),
         InlineKeyboardButton(text=f"{Emoji.PROFILE} Профиль", callback_data="menu:profile")],
        [InlineKeyboardButton(text=f"{Emoji.SUPPORT} Поддержка", callback_data="menu:support"),
         InlineKeyboardButton(text=f"{Emoji.SETTINGS} Настройки", callback_data="menu:settings")],
    ])

def games_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.CASINO} Рулетка", callback_data="games:roulette"),
         InlineKeyboardButton(text=f"{Emoji.SLOTS} Слоты", callback_data="games:slots")],
        [InlineKeyboardButton(text=f"{Emoji.TOWER} Башня", callback_data="games:tower"),
         InlineKeyboardButton(text=f"{Emoji.GOLD} Золото", callback_data="games:gold")],
        [InlineKeyboardButton(text=f"{Emoji.DIAMOND} Алмазы", callback_data="games:diamonds"),
         InlineKeyboardButton(text=f"{Emoji.MINES} Мины", callback_data="games:mines")],
        [InlineKeyboardButton(text=f"{Emoji.CARDS} Очко", callback_data="games:ochko"),
         InlineKeyboardButton(text=f"{Emoji.CRASH} Краш", callback_data="games:crash")],
        [InlineKeyboardButton(text=f"{Emoji.CUBE} Кубик", callback_data="games:cube"),
         InlineKeyboardButton(text=f"{Emoji.DICE} Кости", callback_data="games:dice")],
        [InlineKeyboardButton(text=f"{Emoji.FOOTBALL} Футбол", callback_data="games:football"),
         InlineKeyboardButton(text=f"{Emoji.BASKET} Баскет", callback_data="games:basket")],
        [InlineKeyboardButton(text=f"{Emoji.POKER} Покер", callback_data="games:poker"),
         InlineKeyboardButton(text=f"{Emoji.COINFLIP} Орёл/Решка", callback_data="games:coinflip")],
        [InlineKeyboardButton(text=f"{Emoji.WHEEL} Колесо фортуны", callback_data="games:wheel"),
         InlineKeyboardButton(text=f"{Emoji.FISHING} Рыбалка", callback_data="games:fishing")],
        [InlineKeyboardButton(text=f"{Emoji.LOTTERY} Лотерея", callback_data="games:lottery"),
         InlineKeyboardButton(text=f"{Emoji.SCRATCH} Лотерейка", callback_data="games:scratch")],
        [InlineKeyboardButton(text=f"{Emoji.DUEL} Дуэль", callback_data="games:duel"),
         InlineKeyboardButton(text=f"{Emoji.TOURNAMENT} Турнир", callback_data="games:tournament")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")],
    ])

def roulette_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="roulette:red"),
         InlineKeyboardButton(text="⚫ Чёрное", callback_data="roulette:black")],
        [InlineKeyboardButton(text="📊 1-12", callback_data="roulette:1-12"),
         InlineKeyboardButton(text="📊 13-24", callback_data="roulette:13-24"),
         InlineKeyboardButton(text="📊 25-36", callback_data="roulette:25-36")],
        [InlineKeyboardButton(text="2️⃣ Чет", callback_data="roulette:even"),
         InlineKeyboardButton(text="1️⃣ Нечет", callback_data="roulette:odd")],
        [InlineKeyboardButton(text="0️⃣ Зеро (x36)", callback_data="roulette:zero")],
        [InlineKeyboardButton(text="🔢 Число (x35)", callback_data="roulette:number")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="game:cancel")],
    ])

def tower_kb(level: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i in range(1, 4):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"tower:pick:{i}"))
    buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="💰 Забрать", callback_data="tower:cash"),
        InlineKeyboardButton(text="❌ Сдаться", callback_data="tower:cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def mines_kb_5x5(game: Dict[str, Any], reveal_all: bool = False) -> InlineKeyboardMarkup:
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
    
    rows.append([
        InlineKeyboardButton(text="💰 Забрать", callback_data="mines:cash"),
        InlineKeyboardButton(text="❌ Сдаться", callback_data="mines:cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ochko_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Взять", callback_data="ochko:hit"),
         InlineKeyboardButton(text="✋ Стоп", callback_data="ochko:stand")]
    ])

def slots_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить", callback_data="slots:spin"),
         InlineKeyboardButton(text="💰 Забрать", callback_data="slots:cash")],
        [InlineKeyboardButton(text="❌ Выход", callback_data="slots:exit")]
    ])

def poker_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Взять", callback_data="poker:hit"),
         InlineKeyboardButton(text="✋ Оставить", callback_data="poker:stand")],
        [InlineKeyboardButton(text="💰 Удвоить", callback_data="poker:double")]
    ])

def bank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Открыть депозит", callback_data="bank:open")],
        [InlineKeyboardButton(text="📜 Мои депозиты", callback_data="bank:list")],
        [InlineKeyboardButton(text="💰 Снять зрелые", callback_data="bank:withdraw")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="bank:stats")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")],
    ])

def bank_terms_kb() -> InlineKeyboardMarkup:
    rows = []
    for days, rate in BANK_TERMS.items():
        rows.append([InlineKeyboardButton(
            text=f"{days} дн. (+{int(rate*100)}%)", 
            callback_data=f"bank:term:{days}"
        )])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bank:term:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.COIN} Выдать монеты", callback_data="admin:give")],
        [InlineKeyboardButton(text=f"{Emoji.STATS} Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text=f"{Emoji.TOP} Топ-20", callback_data="admin:top20")],
        [InlineKeyboardButton(text=f"{Emoji.PROMO} Создать промо", callback_data="admin:newpromo")],
        [InlineKeyboardButton(text=f"{Emoji.WARNING} Забанить", callback_data="admin:ban")],
        [InlineKeyboardButton(text=f"{Emoji.SUCCESS} Разбанить", callback_data="admin:unban")],
        [InlineKeyboardButton(text="🔄 Обновить БД", callback_data="admin:refreshdb")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="🎯 Задать джекпот", callback_data="admin:setjackpot")],
        [InlineKeyboardButton(text="👥 Список админов", callback_data="admin:admins")],
        [InlineKeyboardButton(text="📜 Логи", callback_data="admin:logs")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")],
    ])

def profile_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.STATS} Статистика", callback_data="profile:stats")],
        [InlineKeyboardButton(text=f"{Emoji.ACHIEVEMENTS} Достижения", callback_data="profile:achievements")],
        [InlineKeyboardButton(text=f"{Emoji.INVENTORY} Инвентарь", callback_data="profile:inventory")],
        [InlineKeyboardButton(text=f"{Emoji.REF} Рефералы", callback_data="profile:referrals")],
        [InlineKeyboardButton(text=f"{Emoji.SETTINGS} Настройки", callback_data="profile:settings")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")],
    ])

def shop_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Бустеры", callback_data="shop:boosters"),
         InlineKeyboardButton(text="🎨 Скины", callback_data="shop:skins")],
        [InlineKeyboardButton(text="🐕 Питомцы", callback_data="shop:pets"),
         InlineKeyboardButton(text="✨ VIP", callback_data="shop:vip")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")],
    ])

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

@dp.message(CommandStart())
async def start_command(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    args = command.args or ""
    ref_id = None
    
    if args.startswith("ref_"):
        ref_id = args.replace("ref_", "")
        if ref_id == str(user_id):
            ref_id = None
    
    ensure_user(user_id, ref_id, message.from_user.first_name or "", 
                message.from_user.last_name or "", message.from_user.username or "")
    await state.clear()
    clear_active_sessions(user_id)
    
    if ref_id:
        await message.bot.send_message(
            int(ref_id), 
            f"{Emoji.BONUS} <b>Новый реферал!</b>\n"
            f"По твоей ссылке присоединился {mention_user(user_id, message.from_user.first_name)}\n"
            f"Начислено: <b>{fmt_money(REF_REWARD)}</b>"
        )
    
    subscribed, sub_msg = await check_subscription(message.bot, user_id)
    if not subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/dodoCoin_news")],
            [InlineKeyboardButton(text="💬 Войти в чат", url="https://t.me/dodocoin_chat")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
        ])
        await message.answer(sub_msg, reply_markup=kb)
        return
    
    user = get_user(user_id)
    await message.answer(
        f"{Emoji.CROWN} <b>Добро пожаловать в DodoCoin Casino!</b>\n\n"
        f"{Emoji.PLAYER} Игрок: {mention_user(user_id, message.from_user.first_name)}\n"
        f"{Emoji.COIN} Баланс: {fmt_money(user['coins'])}\n"
        f"{Emoji.VIP} VIP уровень: {user['vip_level']}\n\n"
        f"<i>Используй кнопки ниже для навигации</i>",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        f"{Emoji.INFO} <b>Помощь по командам</b>\n\n"
        f"<b>Основные:</b>\n"
        f"• /start - Запуск бота\n"
        f"• /balance, /б - Баланс\n"
        f"• /bonus - Бонус\n"
        f"• /daily - Ежедневный бонус\n"
        f"• /weekly - Еженедельный бонус\n"
        f"• /profile - Профиль\n"
        f"• /top - Топ игроков\n"
        f"• /referral, /реф - Реферальная система\n\n"
        f"<b>Игры:</b>\n"
        f"• /roulette, /рул [сумма] [ставка] - Рулетка\n"
        f"• /slots, /слоты [сумма] - Слоты\n"
        f"• /tower, /башня [сумма] - Башня\n"
        f"• /mines, /мины [сумма] [мины] - Мины\n"
        f"• /crash, /краш [сумма] [множитель] - Краш\n"
        f"• /coinflip, /орёл [сумма] [орёл/решка] - Орёл/Решка\n"
        f"• /blackjack, /очко [сумма] - Очко\n\n"
        f"<b>Финансы:</b>\n"
        f"• /bank, /банк - Депозиты\n"
        f"• /transfer, /перевод [id] [сумма] - Перевод\n"
        f"• /promo [код] - Активировать промокод\n"
        f"• /check, /чек - Система чеков\n\n"
        f"<i>Отмена действия: /cancel</i>"
    )

@dp.message(Command("balance"))
@dp.message(Command("б"))
async def balance_command(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"{Emoji.COIN} <b>Твой баланс</b>\n"
        f"<blockquote>{fmt_money(float(user['coins'] or 0))}</blockquote>\n"
        f"<i>VIP {user['vip_level']} | Игр: {user['games_played']} | Побед: {user['games_won']}</i>"
    )

@dp.message(Command("profile"))
async def profile_command(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    stats = get_user_stats(user_id)
    
    status_map = {
        0: f"{Emoji.PLAYER} Игрок",
        1: f"{Emoji.VIP} VIP",
        2: f"{Emoji.DIAMOND} Премиум",
        3: f"{Emoji.CROWN} Админ"
    }
    status_text = status_map.get(int(user["status"] or 0), f"{Emoji.PLAYER} Игрок")
    if is_admin_user(user_id):
        status_text = f"{Emoji.CROWN} Админ"
    
    reg_date = fmt_dt(int(user["registered_at"] or 0))
    last_active = fmt_dt(int(user["last_active"] or 0))
    
    await message.answer(
        f"{Emoji.ID} <b>Профиль игрока</b>\n"
        f"┌ {Emoji.PLAYER} {mention_user(user_id, user['first_name'] or 'Unknown')}\n"
        f"├ {Emoji.STATUS} Статус: {status_text}\n"
        f"├ {Emoji.VIP} VIP уровень: {user['vip_level']}\n"
        f"├ {Emoji.GAMES} Сыграно: {stats.games_played}\n"
        f"├ {Emoji.TOP} Побед: {stats.games_won}\n"
        f"├ {Emoji.WIN} Винрейт: {stats.winrate}%\n"
        f"├ {Emoji.TURNOVER} Оборот: {fmt_money(stats.total_bet)}\n"
        f"├ {Emoji.COIN} Профит: {fmt_money(stats.net_profit)}\n"
        f"├ {Emoji.REF} Рефералов: {stats.ref_count}\n"
        f"├ {Emoji.DATE} Регистрация: {reg_date}\n"
        f"└ {Emoji.CLOCK} Последний визит: {last_active}\n\n"
        f"{Emoji.COIN} Баланс: {fmt_money(stats.coins)}",
        reply_markup=profile_kb(user_id)
    )

@dp.message(Command("bonus"))
async def bonus_command(message: Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    key = f"bonus_ts:{user_id}"
    last = int(get_json_value(key, 0) or 0)
    now = now_ts()
    
    if now - last < BONUS_COOLDOWN_SECONDS:
        left = BONUS_COOLDOWN_SECONDS - (now - last)
        await message.answer(f"{Emoji.BONUS} Ты уже забрал бонус.\nОсталось: <b>{fmt_left(left)}</b>")
        return
    
    reward = round(random.uniform(BONUS_REWARD_MIN, BONUS_REWARD_MAX), 2)
    add_balance(user_id, reward, "Бонус за активность")
    set_json_value(key, now)
    
    await message.answer(
        f"{Emoji.BONUS} <b>Бонус получен!</b>\n"
        f"Начислено: <b>{fmt_money(reward)}</b>"
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
        await message.answer(f"{Emoji.CLOCK} Ежедневный бонус уже получен.\nСледующий через: {fmt_left(left)}")
        return
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET daily_bonus_taken = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()
    
    reward = DAILY_BONUS * (1 + int(user["vip_level"] or 0) * 0.1)
    add_balance(user_id, reward, "Ежедневный бонус")
    
    await message.answer(
        f"{Emoji.GIFT} <b>Ежедневный бонус!</b>\n"
        f"Начислено: <b>{fmt_money(reward)}</b>\n"
        f"VIP бонус: +{int(user['vip_level'] or 0) * 10}%"
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
        await message.answer(f"{Emoji.CLOCK} Еженедельный бонус уже получен.\nСледующий через: {fmt_left(left)}")
        return
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET weekly_bonus_taken = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()
    
    reward = WEEKLY_BONUS * (1 + int(user["vip_level"] or 0) * 0.2)
    add_balance(user_id, reward, "Еженедельный бонус")
    
    await message.answer(
        f"{Emoji.GIFT} <b>Еженедельный бонус!</b>\n"
        f"Начислено: <b>{fmt_money(reward)}</b>\n"
        f"VIP бонус: +{int(user['vip_level'] or 0) * 20}%"
    )

@dp.message(Command("top"))
async def top_command(message: Message):
    rows = get_top_balances(15)
    if not rows:
        await message.answer(f"{Emoji.TOP} <b>Топ игроков</b>\n<blockquote><i>Пока пусто.</i></blockquote>")
        return
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    lines = [f"{Emoji.TOP} <b>Топ игроков по богатству</b>", "<blockquote>"]
    
    for idx, row in enumerate(rows, start=1):
        icon = medals.get(idx, f"{idx}.")
        vip_icon = "👑" if row["vip_level"] >= 3 else ("⭐️" if row["vip_level"] >= 1 else "")
        lines.append(f"{icon} {escape_html(row['name'])} {vip_icon} — <b>{fmt_money(float(row['coins']))}</b>")
    
    lines.append("</blockquote>")
    await message.answer("\n".join(lines))

@dp.message(Command("referral"))
@dp.message(Command("реф"))
async def referral_command(message: Message):
    user_id = message.from_user.id
    stats = get_user_stats(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    # Получаем рефералов 2-го уровня
    conn = get_db()
    try:
        level2 = conn.execute("""
            SELECT COUNT(*) as count FROM referrals_network 
            WHERE referer_id IN (SELECT referred_id FROM referrals_network WHERE referer_id = ?)
        """, (str(user_id),)).fetchone()
        level2_count = level2["count"] if level2 else 0
    finally:
        conn.close()
    
    await message.answer(
        f"{Emoji.REF} <b>Реферальная система</b>\n"
        f"┌ Приглашай друзей и зарабатывай!\n"
        f"├ {Emoji.COIN} За друга: {fmt_money(REF_REWARD)}\n"
        f"├ {Emoji.PERCENT} {int(REF_PERCENT * 100)}% от проигрышей\n"
        f"├ {Emoji.INVITED} Приглашено: {stats.ref_count} (2 ур.: {level2_count})\n"
        f"├ {Emoji.COIN} Заработано: {fmt_money(stats.ref_earned)}\n"
        f"└ {Emoji.REF} Твоя ссылка:\n"
        f"<code>{ref_link}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data=f"ref:copy:{user_id}"),
             InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=f"Присоединяйся! {ref_link}")]
        ])
    )

@dp.message(Command("transfer"))
@dp.message(Command("перевод"))
async def transfer_command(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Использование: /transfer [ID] [сумма]\nИли ответь на сообщение пользователя: /transfer [сумма]")
        return
    
    try:
        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            amount = parse_amount(args[1])
        else:
            target_id = int(args[1])
            amount = parse_amount(args[2])
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /transfer 123456789 1000")
        return
    
    if target_id == message.from_user.id:
        await message.answer("❌ Нельзя перевести самому себе")
        return
    
    if amount < MIN_BET:
        await message.answer(f"❌ Минимальная сумма перевода: {fmt_money(MIN_BET)}")
        return
    
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        sender = conn.execute("SELECT coins FROM users WHERE id = ?", (str(message.from_user.id),)).fetchone()
        if not sender or float(sender["coins"] or 0) < amount:
            conn.rollback()
            await message.answer(f"❌ Недостаточно средств. Нужно: {fmt_money(amount)}")
            return
        
        conn.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (amount, str(message.from_user.id)))
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (amount, str(target_id)))
        add_transaction(message.from_user.id, "transfer_out", -amount, f"Перевод пользователю {target_id}")
        add_transaction(target_id, "transfer_in", amount, f"Перевод от {message.from_user.id}")
        conn.commit()
        
        target_user = conn.execute("SELECT first_name FROM users WHERE id = ?", (str(target_id),)).fetchone()
        target_name = target_user["first_name"] if target_user else f"ID {target_id}"
        
        await message.answer(f"✅ Перевод {fmt_money(amount)} отправлен {mention_user(target_id, target_name)}")
        
        try:
            await message.bot.send_message(
                target_id,
                f"{Emoji.COIN} Вам переведено {fmt_money(amount)} от {mention_user(message.from_user.id, message.from_user.first_name)}"
            )
        except Exception:
            pass
    except Exception as e:
        conn.rollback()
        logger.error(f"Transfer error: {e}")
        await message.answer("❌ Ошибка при переводе")
    finally:
        conn.close()

# ==================== КОМАНДЫ ИГР ====================

@dp.message(Command("roulette"))
@dp.message(Command("рул"))
async def roulette_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(RouletteStates.waiting_amount)
        await message.answer(f"{Emoji.ROULETTE} <b>Рулетка</b>\nВведи сумму ставки:")
        return
    
    user_id = message.from_user.id
    try:
        bet = parse_amount(args[1])
        choice = args[2].lower()
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /рул 100 красное")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    # Маппинг выбора
    choice_map = {
        "красное": "red", "крас": "red", "red": "red",
        "черное": "black", "чёрное": "black", "чер": "black", "black": "black",
        "чет": "even", "четное": "even", "even": "even",
        "нечет": "odd", "нечетное": "odd", "odd": "odd",
        "зеро": "zero", "zero": "zero", "0": "zero",
        "1-12": "1-12", "13-24": "13-24", "25-36": "25-36"
    }
    choice = choice_map.get(choice, choice)
    
    ok, balance = reserve_bet(user_id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств. Нужно: {fmt_money(bet)}")
        return
    
    win, multiplier, outcome_text, number, color = roulette_roll(choice)
    payout = round(bet * multiplier, 2) if win else 0
    new_balance = finalize_reserved_bet(user_id, bet, payout, f"roulette:{choice}", f"num={number}", "roulette")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>Рулетка - {result_text}</b>\n"
        f"┌ Ставка: {fmt_money(bet)}\n"
        f"├ Выбор: {choice}\n"
        f"├ Выпало: {outcome_text}\n"
        f"├ Множитель: x{multiplier}\n"
        f"├ Выплата: {fmt_money(payout)}\n"
        f"└ Новый баланс: {fmt_money(new_balance)}"
    )

@dp.message(Command("crash"))
@dp.message(Command("краш"))
async def crash_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(CrashStates.waiting_amount)
        await message.answer(f"{Emoji.CRASH} <b>Краш</b>\nВведи сумму ставки:")
        return
    
    try:
        bet = parse_amount(args[1])
        target = float(args[2])
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /краш 100 2.5")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    if target < 1.01 or target > 100:
        await message.answer("❌ Множитель должен быть от 1.01 до 100")
        return
    
    crash_mult = crash_roll()
    win = target <= crash_mult
    payout = round(bet * target, 2) if win else 0
    
    ok, balance = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств")
        return
    
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"crash:{target}", f"crash={crash_mult}", "crash")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "УСПЕХ!" if win else "КРАШ!"
    
    await message.answer(
        f"{result_icon} <b>Краш - {result_text}</b>\n"
        f"┌ Ставка: {fmt_money(bet)}\n"
        f"├ Твой множитель: x{target}\n"
        f"├ Выпало: x{crash_mult}\n"
        f"├ Выплата: {fmt_money(payout)}\n"
        f"└ Баланс: {fmt_money(new_balance)}"
    )

@dp.message(Command("coinflip"))
@dp.message(Command("орёл"))
async def coinflip_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 3:
        await state.set_state(CoinFlipStates.waiting_amount)
        await message.answer(f"{Emoji.COINFLIP} <b>Орёл/Решка</b>\nВведи сумму ставки:")
        return
    
    try:
        bet = parse_amount(args[1])
        choice = args[2].lower()
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /орёл 100 орёл")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    if choice not in ["орёл", "орел", "решка"]:
        await message.answer("❌ Выбери: орёл или решка")
        return
    
    result, multiplier = coinflip_result()
    win = (choice == "орёл" and result == "heads") or (choice == "решка" and result == "tails")
    payout = round(bet * multiplier, 2) if win else 0
    
    ok, balance = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств")
        return
    
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, f"coinflip:{choice}", f"result={result}", "coinflip")
    
    result_icon = Emoji.WIN if win else Emoji.LOSE
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    result_emoji = "🪙 Орёл" if result == "heads" else "🪙 Решка"
    
    await message.answer(
        f"{result_icon} <b>Орёл/Решка - {result_text}</b>\n"
        f"┌ Ставка: {fmt_money(bet)}\n"
        f"├ Твой выбор: {choice}\n"
        f"├ Выпало: {result_emoji}\n"
        f"├ Множитель: x{multiplier}\n"
        f"├ Выплата: {fmt_money(payout)}\n"
        f"└ Баланс: {fmt_money(new_balance)}"
    )

@dp.message(Command("slots"))
@dp.message(Command("слоты"))
async def slots_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 2:
        await state.set_state(SlotsStates.waiting_amount)
        await message.answer(f"{Emoji.SLOTS} <b>Слоты</b>\nВведи сумму ставки:")
        return
    
    try:
        bet = parse_amount(args[1])
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /слоты 100")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    ok, balance = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств")
        return
    
    reels, multiplier = slots_spin()
    payout = round(bet * multiplier, 2) if multiplier > 0 else 0
    new_balance = finalize_reserved_bet(message.from_user.id, bet, payout, "slots", f"reels={' '.join(reels)}", "slots")
    
    result_icon = Emoji.WIN if multiplier > 0 else Emoji.LOSE
    result_text = "ДЖЕКПОТ!" if multiplier >= 100 else ("ВЫИГРЫШ!" if multiplier > 0 else "ПРОИГРЫШ")
    
    # Красивое отображение слотов
    slot_display = f"""
┌─────┬─────┬─────┐
│  {reels[0]}  │  {reels[1]}  │  {reels[2]}  │
└─────┴─────┴─────┘
"""
    
    await message.answer(
        f"{result_icon} <b>Слоты - {result_text}</b>\n"
        f"<code>{slot_display}</code>\n"
        f"┌ Ставка: {fmt_money(bet)}\n"
        f"├ Комбинация: {''.join(reels)}\n"
        f"├ Множитель: x{multiplier}\n"
        f"├ Выплата: {fmt_money(payout)}\n"
        f"└ Баланс: {fmt_money(new_balance)}"
    )

@dp.message(Command("blackjack"))
@dp.message(Command("очко"))
async def blackjack_command(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) < 2:
        await state.set_state(OchkoStates.waiting_amount)
        await message.answer(f"{Emoji.CARDS} <b>Очко (Blackjack)</b>\nВведи сумму ставки:")
        return
    
    try:
        bet = parse_amount(args[1])
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пример: /очко 100")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    ok, balance = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств")
        return
    
    # Создаем колоду
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [(r, s) for r in ranks for s in suits]
    random.shuffle(deck)
    
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    
    OCHKO_GAMES[message.from_user.id] = {
        "bet": bet,
        "deck": deck,
        "player": player_hand,
        "dealer": dealer_hand
    }
    
    player_value = blackjack_hand_value(player_hand)
    dealer_card = f"{dealer_hand[0][0]}{dealer_hand[0][1]}"
    
    await message.answer(
        f"{Emoji.CARDS} <b>Очко</b>\n"
        f"Ставка: {fmt_money(bet)}\n\n"
        f"🃏 Дилер: {dealer_card} ?\n"
        f"🃏 Ты: {' '.join([f'{r}{s}' for r, s in player_hand])} = {player_value}\n\n"
        f"<i>Выбери действие:</i>",
        reply_markup=ochko_kb()
    )

# ==================== ДЖЕКПОТ ====================

@dp.message(Command("jackpot"))
async def jackpot_command(message: Message):
    global jackpot_pool
    
    # Обновляем джекпот
    jackpot_pool = get_json_value("jackpot_pool", 100000.0)
    
    await message.answer(
        f"{Emoji.JACKPOT} <b>ДЖЕКПОТ</b>\n"
        f"┌ Текущий джекпот: {fmt_money(jackpot_pool)}\n"
        f"├ Участников: {len(jackpot_contributors)}\n"
        f"├ Сделай ставку от {fmt_money(MIN_BET)} для участия\n"
        f"└ Шанс выигрыша: 1% от суммы ставки\n\n"
        f"<i>Используй /jackpotbet [сумма] чтобы сделать ставку</i>"
    )

@dp.message(Command("jackpotbet"))
async def jackpot_bet_command(message: Message):
    global jackpot_pool
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /jackpotbet [сумма]")
        return
    
    try:
        bet = parse_amount(args[1])
    except ValueError:
        await message.answer("❌ Неверная сумма")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    user_id = message.from_user.id
    ok, balance = reserve_bet(user_id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств")
        return
    
    # Добавляем в джекпот
    jackpot_contributors[user_id] = jackpot_contributors.get(user_id, 0) + bet
    jackpot_pool += bet * 0.9  # 10% уходит в фонд
    set_json_value("jackpot_pool", jackpot_pool)
    
    # Шанс выигрыша
    win_chance = min(0.05, bet / 10000)  # Максимум 5% шанс
    if random.random() < win_chance:
        # ВЫИГРЫШ!
        winner_bonus = jackpot_pool * 0.7
        add_balance(user_id, winner_bonus, "Джекпот!")
        jackpot_pool = jackpot_pool * 0.3
        set_json_value("jackpot_pool", jackpot_pool)
        jackpot_contributors.clear()
        
        await message.answer(
            f"{Emoji.JACKPOT} 🎉 <b>ВЫ ВЫИГРАЛИ ДЖЕКПОТ!</b> 🎉\n"
            f"Выигрыш: {fmt_money(winner_bonus)}\n"
            f"Остаток джекпота: {fmt_money(jackpot_pool)}"
        )
    else:
        await message.answer(
            f"{Emoji.JACKPOT} Ставка {fmt_money(bet)} добавлена в джекпот!\n"
            f"Твой шанс выиграть: {win_chance*100:.2f}%\n"
            f"Текущий джекпот: {fmt_money(jackpot_pool)}"
        )

# ==================== ДУЭЛИ ====================

@dp.message(Command("duel"))
async def duel_command(message: Message, state: FSMContext):
    await state.set_state(DuelStates.waiting_amount)
    await message.answer(
        f"{Emoji.DUEL} <b>Дуэль</b>\n"
        f"Введи сумму ставки (от {fmt_money(MIN_BET)} до {fmt_money(MAX_BET)}):"
    )

@dp.message(DuelStates.waiting_amount)
async def duel_amount(message: Message, state: FSMContext):
    try:
        bet = parse_amount(message.text)
    except ValueError:
        await message.answer("❌ Неверная сумма")
        return
    
    if bet < MIN_BET or bet > MAX_BET:
        await message.answer(f"❌ Ставка должна быть от {fmt_money(MIN_BET)} до {fmt_money(MAX_BET)}")
        return
    
    await state.update_data(duel_bet=bet)
    await state.set_state(DuelStates.waiting_opponent)
    await message.answer("👥 Кого вызываешь на дуэль? (Отправь ID пользователя или ответь на его сообщение)")

@dp.message(DuelStates.waiting_opponent)
async def duel_opponent(message: Message, state: FSMContext):
    if message.reply_to_message:
        opponent_id = message.reply_to_message.from_user.id
    else:
        try:
            opponent_id = int(message.text)
        except ValueError:
            await message.answer("❌ Укажи ID пользователя или ответь на его сообщение")
            return
    
    if opponent_id == message.from_user.id:
        await message.answer("❌ Нельзя вызвать себя")
        return
    
    data = await state.get_data()
    bet = data.get("duel_bet", 0)
    
    # Проверяем баланс противника
    conn = get_db()
    try:
        opponent = conn.execute("SELECT coins FROM users WHERE id = ?", (str(opponent_id),)).fetchone()
        if not opponent or float(opponent["coins"] or 0) < bet:
            await message.answer(f"❌ У противника недостаточно средств для дуэли ({fmt_money(bet)})")
            return
    finally:
        conn.close()
    
    # Резервируем средства
    ok1, _ = reserve_bet(message.from_user.id, bet)
    ok2, _ = reserve_bet(opponent_id, bet)
    
    if not ok1 or not ok2:
        if ok1:
            add_balance(message.from_user.id, bet, "Возврат ставки")
        await message.answer("❌ Ошибка резервирования средств")
        return
    
    # Сохраняем дуэль
    duel_id = now_ts()
    active_duels[duel_id] = {
        "player1": message.from_user.id,
        "player2": opponent_id,
        "bet": bet,
        "status": "waiting"
    }
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять дуэль", callback_data=f"duel:accept:{duel_id}"),
         InlineKeyboardButton(text="❌ Отказаться", callback_data=f"duel:decline:{duel_id}")]
    ])
    
    await message.bot.send_message(
        opponent_id,
        f"{Emoji.DUEL} <b>Вызов на дуэль!</b>\n"
        f"{mention_user(message.from_user.id)} вызывает тебя!\n"
        f"Ставка: {fmt_money(bet)}\n\n"
        f"Принимаешь вызов?",
        reply_markup=kb
    )
    
    await message.answer(f"✅ Вызов отправлен {mention_user(opponent_id)}!\nОжидай ответа...")
    await state.clear()

@dp.callback_query(F.data.startswith("duel:accept:"))
async def duel_accept(query: CallbackQuery):
    duel_id = int(query.data.split(":")[2])
    duel = active_duels.get(duel_id)
    
    if not duel:
        await query.answer("❌ Дуэль уже завершена", show_alert=True)
        return
    
    if query.from_user.id != duel["player2"]:
        await query.answer("❌ Это не тебя вызывали", show_alert=True)
        return
    
    # Проводим дуэль (рандом)
    winner = random.choice([duel["player1"], duel["player2"]])
    loser = duel["player1"] if winner == duel["player2"] else duel["player2"]
    bet = duel["bet"]
    
    payout = bet * 2
    new_balance_winner = add_balance(winner, payout, f"Выигрыш в дуэли против {loser}")
    new_balance_loser = finalize_reserved_bet(loser, bet, 0, "duel", f"lost to {winner}", "duel")
    
    await query.message.edit_text(
        f"{Emoji.DUEL} <b>Результат дуэли!</b>\n"
        f"┌ Участники: {mention_user(duel['player1'])} vs {mention_user(duel['player2'])}\n"
        f"├ Ставка: {fmt_money(bet)}\n"
        f"├ Победитель: {mention_user(winner)} 🏆\n"
        f"├ Выигрыш: {fmt_money(payout)}\n"
        f"└ Проигравший: {mention_user(loser)} 😢"
    )
    
    await query.answer("Дуэль завершена!")
    active_duels.pop(duel_id, None)

# ==================== ТУРНИРЫ ====================

@dp.message(Command("tournament"))
async def tournament_command(message: Message):
    tournaments = get_json_value("tournaments", [])
    
    if not tournaments:
        await message.answer(
            f"{Emoji.TOURNAMENT} <b>Турниры</b>\n"
            f"<i>Активных турниров нет.</i>\n\n"
            f"Используй /create_tournament для создания нового турнира (только для админов)"
        )
        return
    
    text = f"{Emoji.TOURNAMENT} <b>Активные турниры</b>\n\n"
    for tour in tournaments[:5]:
        text += f"┌ <b>{tour['name']}</b>\n"
        text += f"├ Призовой фонд: {fmt_money(tour['prize_pool'])}\n"
        text += f"├ Мин. ставка: {fmt_money(tour['min_bet'])}\n"
        text += f"├ Участников: {len(tour['participants'])}\n"
        text += f"└ Статус: {tour['status']}\n\n"
    
    await message.answer(text)

# ==================== МАГАЗИН ====================

@dp.message(Command("shop"))
async def shop_command(message: Message):
    await message.answer(
        f"{Emoji.SHOP} <b>Магазин</b>\n\n"
        f"Выбери категорию:",
        reply_markup=shop_kb()
    )

# ==================== АДМИН КОМАНДЫ ====================

@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Только для администраторов")
        return
    
    await message.answer(
        f"{Emoji.CROWN} <b>Админ-панель</b>\n"
        f"Выбери действие:",
        reply_markup=admin_panel_kb()
    )

@dp.callback_query(F.data == "admin:stats")
async def admin_stats(query: CallbackQuery):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True)
        return
    
    conn = get_db()
    try:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bets_count = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
        total_bet = conn.execute("SELECT COALESCE(SUM(bet_amount), 0) FROM bets").fetchone()[0]
        total_payout = conn.execute("SELECT COALESCE(SUM(payout), 0) FROM bets").fetchone()[0]
        total_deposits = conn.execute("SELECT COALESCE(SUM(principal), 0) FROM bank_deposits WHERE status = 'active'").fetchone()[0]
        active_tickets = conn.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'").fetchone()[0]
    finally:
        conn.close()
    
    profit = total_bet - total_payout
    
    await query.message.edit_text(
        f"{Emoji.STATS} <b>Статистика бота</b>\n"
        f"┌ 👥 Пользователей: {users_count}\n"
        f"├ 🎮 Ставок: {bets_count}\n"
        f"├ 💰 Общий оборот: {fmt_money(total_bet)}\n"
        f"├ 💸 Выплат: {fmt_money(total_payout)}\n"
        f"├ 📈 Профит казино: {fmt_money(profit)}\n"
        f"├ 🏦 Активных депозитов: {fmt_money(total_deposits)}\n"
        f"└ 🎫 Открытых тикетов: {active_tickets}"
    )
    await query.answer()

@dp.callback_query(F.data == "admin:refreshdb")
async def admin_refresh_db(query: CallbackQuery):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True)
        return
    
    init_db()
    await query.message.edit_text("✅ База данных успешно обновлена")
    await query.answer()

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(query: CallbackQuery, state: FSMContext):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminBroadcastStates.waiting_message)
    await query.message.edit_text("📢 Введи сообщение для рассылки (можно с HTML-разметкой):")
    await query.answer()

@dp.message(AdminBroadcastStates.waiting_message)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user.id):
        await message.answer("Нет доступа")
        return
    
    text = message.html_text
    
    conn = get_db()
    try:
        users = conn.execute("SELECT id FROM users").fetchall()
    finally:
        conn.close()
    
    success = 0
    failed = 0
    
    progress_msg = await message.answer(f"📢 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        try:
            await message.bot.send_message(int(user["id"]), text)
            success += 1
            await asyncio.sleep(0.05)  # Защита от флуда
        except Exception:
            failed += 1
        
        if (success + failed) % 50 == 0:
            await progress_msg.edit_text(f"📢 Рассылка: {success + failed}/{len(users)} | ✅ {success} | ❌ {failed}")
    
    await progress_msg.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n"
        f"✅ Доставлено: {success}\n"
        f"❌ Ошибок: {failed}"
    )
    
    await state.clear()

# ==================== КОЛБЭКИ МЕНЮ ====================

@dp.callback_query(F.data == "menu:main")
async def menu_main_cb(query: CallbackQuery):
    await query.message.edit_text(
        f"{Emoji.CROWN} <b>DodoCoin Casino</b>\n"
        f"Выбери раздел:",
        reply_markup=main_menu_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:games")
async def menu_games_cb(query: CallbackQuery):
    await query.message.edit_text(
        f"{Emoji.GAMES} <b>Все игры</b>\n"
        f"<i>Выбери игру:</i>",
        reply_markup=games_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:bank")
async def menu_bank_cb(query: CallbackQuery):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    conn = get_db()
    try:
        active_deposits = conn.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(principal), 0) as total 
            FROM bank_deposits WHERE user_id = ? AND status = 'active'
        """, (str(user_id),)).fetchone()
    finally:
        conn.close()
    
    await query.message.edit_text(
        f"{Emoji.BANK} <b>Банк</b>\n"
        f"┌ Баланс: {fmt_money(user['coins'])}\n"
        f"├ Активных депозитов: {active_deposits['count']}\n"
        f"├ Сумма в депозитах: {fmt_money(active_deposits['total'])}\n"
        f"└ Процентная ставка: от 3% до 350%\n\n"
        f"<i>Выбери действие:</i>",
        reply_markup=bank_kb()
    )
    await query.answer()

@dp.callback_query(F.data == "menu:top")
async def menu_top_cb(query: CallbackQuery):
    rows = get_top_balances(15)
    if not rows:
        await query.message.edit_text(f"{Emoji.TOP} <b>Топ игроков</b>\n<blockquote><i>Пока пусто.</i></blockquote>")
        return
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    lines = [f"{Emoji.TOP} <b>Топ игроков</b>", "<blockquote>"]
    
    for idx, row in enumerate(rows, start=1):
        icon = medals.get(idx, f"{idx}.")
        vip_icon = "👑" if row["vip_level"] >= 3 else ("⭐️" if row["vip_level"] >= 1 else "")
        lines.append(f"{icon} {escape_html(row['name'])} {vip_icon} — <b>{fmt_money(float(row['coins']))}</b>")
    
    lines.append("</blockquote>")
    lines.append("\n<i>Используй /profile для просмотра статистики</i>")
    
    await query.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")]
    ]))
    await query.answer()

@dp.callback_query(F.data == "menu:ref")
async def menu_ref_cb(query: CallbackQuery):
    user_id = query.from_user.id
    stats = get_user_stats(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    await query.message.edit_text(
        f"{Emoji.REF} <b>Реферальная система</b>\n"
        f"┌ {Emoji.COIN} За друга: {fmt_money(REF_REWARD)}\n"
        f"├ {Emoji.PERCENT} {int(REF_PERCENT * 100)}% от проигрышей\n"
        f"├ {Emoji.INVITED} Приглашено: {stats.ref_count}\n"
        f"├ {Emoji.COIN} Заработано: {fmt_money(stats.ref_earned)}\n"
        f"└ {Emoji.REF} Твоя ссылка:\n"
        f"<code>{ref_link}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать", callback_data=f"ref:copy:{user_id}"),
             InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data="menu:main")]
        ])
    )
    await query.answer()

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(query: CallbackQuery):
    subscribed, sub_msg = await check_subscription(query.bot, query.from_user.id)
    if not subscribed:
        await query.answer("Подпишись на канал и чат!", show_alert=True)
        return
    
    await query.message.edit_text(
        f"✅ <b>Подписка подтверждена!</b>\n\n"
        f"Добро пожаловать в DodoCoin Casino!\n"
        f"Используй меню для навигации:",
        reply_markup=main_menu_kb()
    )
    await query.answer("Добро пожаловать!")

@dp.callback_query(F.data.startswith("ref:copy:"))
async def ref_copy_cb(query: CallbackQuery):
    user_id = query.data.split(":")[-1]
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await query.message.answer(f"🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>")
    await query.answer("Ссылка отправлена в чат!")

# ==================== ЗАПУСК БОТА ====================

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # Устанавливаем команды бота
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="balance", description="Баланс"),
        BotCommand(command="profile", description="Профиль"),
        BotCommand(command="bonus", description="Бонус"),
        BotCommand(command="daily", description="Ежедневный бонус"),
        BotCommand(command="weekly", description="Еженедельный бонус"),
        BotCommand(command="top", description="Топ игроков"),
        BotCommand(command="referral", description="Реферальная система"),
        BotCommand(command="transfer", description="Перевод монет"),
        BotCommand(command="roulette", description="Рулетка"),
        BotCommand(command="crash", description="Краш"),
        BotCommand(command="coinflip", description="Орёл/Решка"),
        BotCommand(command="slots", description="Слоты"),
        BotCommand(command="blackjack", description="Очко"),
        BotCommand(command="jackpot", description="Джекпот"),
        BotCommand(command="duel", description="Дуэль"),
        BotCommand(command="tournament", description="Турниры"),
        BotCommand(command="shop", description="Магазин"),
        BotCommand(command="bank", description="Банк"),
        BotCommand(command="promo", description="Промокод"),
    ]
    
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot started successfully!")

async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot is shutting down...")

async def main():
    """Главная функция запуска бота"""
    # Инициализация БД
    init_db()
    
    # Настройка бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Удаляем вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем планировщик для периодических задач
    scheduler = AsyncIOScheduler()
    
    # Ежедневный сброс лимитов
    scheduler.add_job(
        reset_daily_limits,
        CronTrigger(hour=0, minute=0),
        args=[bot]
    )
    
    # Еженедельный сброс
    scheduler.add_job(
        reset_weekly_limits,
        CronTrigger(day_of_week="mon", hour=0, minute=0),
        args=[bot]
    )
    
    scheduler.start()
    
    # Регистрируем обработчики нажатий кнопок
    register_handlers()
    
    # Запускаем бота
    await on_startup(bot)
    
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown(bot)

async def reset_daily_limits(bot: Bot):
    """Сброс ежедневных лимитов"""
    conn = get_db()
    try:
        conn.execute("UPDATE users SET daily_withdrawn = 0")
        conn.commit()
        logger.info("Daily limits reset")
    finally:
        conn.close()

async def reset_weekly_limits(bot: Bot):
    """Сброс еженедельных лимитов"""
    conn = get_db()
    try:
        conn.execute("UPDATE users SET weekly_bonus_taken = 0")
        conn.commit()
        logger.info("Weekly limits reset")
    finally:
        conn.close()

def register_handlers():
    """Регистрация всех обработчиков"""
    # Здесь будут регистрироваться все дополнительные обработчики
    # Базовые обработчики уже зарегистрированы через декораторы
    pass

if __name__ == "__main__":
    asyncio.run(main())
