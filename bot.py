import asyncio
import html
import json
import os
import random
import sqlite3
import string
import time
from datetime import datetime
from typing import Any, Dict, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ==================== КОНФИГ ====================

BOT_TOKEN = "8365761672:AAELKM3NAQppEos41sTXJ9v-54CI8LhfQiU"
ADMIN_IDS = {8478884644}
BOT_USERNAME = "DodoCoin_bot"

# ==================== PREMIUM ЭМОДЗИ ====================

EMOJI_CROWN = '<emoji id="5805553606635559688">👑</emoji>'
EMOJI_DIAMOND = '<emoji id="6037083366438737901">💎</emoji>'
EMOJI_VIP = '<emoji id="5213012509660850622">✨</emoji>'
EMOJI_PLAYER = '<emoji id="6032994772321309200">👤</emoji>'
EMOJI_ID = '<emoji id="5884366771913233289">🆔</emoji>'
EMOJI_STATUS = '<emoji id="5368767059108837104">⚡</emoji>'
EMOJI_GAMES = '<emoji id="5938413566624272793">🎮</emoji>'
EMOJI_TOP = '<emoji id="5415655814079723871">🏆</emoji>'
EMOJI_TURNOVER = '<emoji id="5402186569006210455">🔄</emoji>'
EMOJI_LOST = '<emoji id="5244837092042750681">📉</emoji>'
EMOJI_DATE = '<emoji id="5413879192267805083">📅</emoji>'
EMOJI_COIN = '<emoji id="5409048419211682843">💰</emoji>'
EMOJI_BONUS = '<emoji id="5235511932064129087">🎁</emoji>'
EMOJI_REF = '<emoji id="5271604874419647061">🔗</emoji>'
EMOJI_INVITED = '<emoji id="5397916757333654639">🧲</emoji>'
EMOJI_WIN = '<emoji id="5415655814079723871">🏆</emoji>'
EMOJI_LOSE = '<emoji id="5244837092042750681">📉</emoji>'

# ==================== КОНСТАНТЫ ====================

DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "dodocoin.db")
os.makedirs(DB_DIR, exist_ok=True)

START_BALANCE = 100.0
MIN_BET = 10.0
CURRENCY_NAME = "DodoCoin"
CURRENCY_SHORT = "dC"
BONUS_COOLDOWN_SECONDS = 12 * 60 * 60
BONUS_REWARD_MIN = 150
BONUS_REWARD_MAX = 350
REF_REWARD = 5000.0
REF_PERCENT = 0.02

CHANNEL_ID = "@dodoCoin_news"
CHAT_ID = "@dodocoin_chat"

BANK_TERMS = {7: 0.03, 14: 0.07, 30: 0.18}

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

ROULETTE_STICKERS = [
    "CAACAgIAAxkBAAEK1V9nQZ5..." ,  # Замени на реальные file_id стикеров из пака
]

TOWER_MULTIPLIERS = [1.20, 1.48, 1.86, 2.35, 2.95, 3.75, 4.85, 6.15]
GOLD_MULTIPLIERS = [1.15, 1.35, 1.62, 2.0, 2.55, 3.25, 4.2]
DIAMOND_MULTIPLIERS = [1.12, 1.28, 1.48, 1.72, 2.02, 2.4, 2.92, 3.6]
FOOTBALL_MULTIPLIERS = {"gol": 1.6, "mimo": 2.2}

# ==================== FSM СОСТОЯНИЯ ====================

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

class AdminBroadcastStates(StatesGroup):
    waiting_message = State()

# ==================== ИГРОВЫЕ ХРАНИЛИЩА ====================

TOWER_GAMES: Dict[int, Dict[str, Any]] = {}
GOLD_GAMES: Dict[int, Dict[str, Any]] = {}
DIAMOND_GAMES: Dict[int, Dict[str, Any]] = {}
MINES_GAMES: Dict[int, Dict[str, Any]] = {}
OCHKO_GAMES: Dict[int, Dict[str, Any]] = {}
NFOOTBALL_GAMES: Dict[int, Dict[str, Any]] = {}
user_game_locks: Dict[str, asyncio.Lock] = {}

# ==================== БАЗА ДАННЫХ ====================

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            coins REAL DEFAULT 100.0,
            GGs INTEGER DEFAULT 0,
            lost_coins REAL DEFAULT 0.0,
            won_coins REAL DEFAULT 0.0,
            status INTEGER DEFAULT 0,
            registered_at INTEGER DEFAULT 0,
            ref_id TEXT DEFAULT NULL,
            ref_earned REAL DEFAULT 0.0,
            ref_count INTEGER DEFAULT 0,
            first_name TEXT DEFAULT ''
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
            ts INTEGER DEFAULT 0
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

    conn.commit()
    conn.close()

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts() -> int:
    return int(time.time())

def fmt_money(value: float) -> str:
    value = round(float(value), 2)
    abs_value = abs(value)
    if abs_value >= 1000000:
        compact = value / 1000000
        text = f"{compact:.2f}".rstrip("0").rstrip(".")
        amount = f"{text}M"
    elif abs_value >= 1000:
        compact = value / 1000
        text = f"{compact:.2f}".rstrip("0").rstrip(".")
        amount = f"{text}к"
    elif abs(value - int(value)) < 1e-9:
        amount = str(int(value))
    else:
        amount = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{amount} {CURRENCY_SHORT}"

def fmt_dt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M") if ts > 0 else "Неизвестно"

def fmt_left(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, m = seconds // 3600, (seconds % 3600) // 60
    s = seconds % 60
    if h > 0: return f"{h}ч {m}м"
    if m > 0: return f"{m}м {s}с"
    return f"{s}с"

def parse_amount(text: str) -> float:
    raw = str(text or "").strip().lower().replace(" ", "").replace(",", ".")
    multiplier = 1.0
    if raw.endswith(("к", "k")): raw, multiplier = raw[:-1], 1000.0
    if raw.endswith(("м", "m")): raw, multiplier = raw[:-1], 1000000.0
    value = float(raw) * multiplier
    if value <= 0: raise ValueError("amount must be positive")
    return round(value, 2)

def parse_int(text: str) -> int:
    return int(str(text or "").strip())

def parse_bet_legacy(raw: str, balance: float) -> int:
    arg = str(raw or "").strip().lower().replace(" ", "")
    if arg in {"все", "всё"}: return int(balance)
    return int(parse_amount(arg))

def normalize_text(text: Optional[str]) -> str:
    return " ".join(str(text or "").lower().split())

def escape_html(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=False)

def mention_user(user_id: int, name: Optional[str] = None) -> str:
    label = escape_html(name or f"ID {user_id}")
    return f'<a href="tg://user?id={int(user_id)}">{label}</a>'

def normalize_promo_code(text: str) -> str:
    code = str(text or "").strip().upper()
    allowed = set(string.ascii_uppercase + string.digits + "_-")
    if not (3 <= len(code) <= 24): raise ValueError("length")
    if any(ch not in allowed for ch in code): raise ValueError("symbols")
    return code

def is_admin_user(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

def ensure_user_in_conn(conn: sqlite3.Connection, user_id: int, ref_id: Optional[str] = None, first_name: str = "") -> None:
    now = now_ts()
    row = conn.execute("SELECT id, registered_at, ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users (id, coins, GGs, lost_coins, won_coins, status, registered_at, ref_id, ref_earned, ref_count, first_name) VALUES (?, ?, 0, 0, 0, 0, ?, ?, 0, 0, ?)",
            (str(user_id), START_BALANCE, now, ref_id, first_name),
        )
        if ref_id and ref_id != str(user_id):
            conn.execute("UPDATE users SET ref_count = ref_count + 1 WHERE id = ?", (ref_id,))
    else:
        if not row["registered_at"]:
            conn.execute("UPDATE users SET registered_at = ?, ref_id = COALESCE(ref_id, ?) WHERE id = ?", (now, ref_id, str(user_id)))
        if first_name:
            conn.execute("UPDATE users SET first_name = ? WHERE id = ? AND (first_name = '' OR first_name IS NULL)", (first_name, str(user_id)))

def ensure_user(user_id: int, ref_id: Optional[str] = None, first_name: str = "") -> None:
    conn = get_db()
    try:
        ensure_user_in_conn(conn, user_id, ref_id, first_name)
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
        conn.execute("INSERT INTO json_data (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()

def get_json_value(key: str, default: Any = None) -> Any:
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM json_data WHERE key = ?", (key,)).fetchone()
        if not row: return default
        try: return json.loads(row["value"])
        except Exception: return default
    finally:
        conn.close()

def reserve_bet(user_id: int, bet: float) -> tuple[bool, float]:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        coins = float(row["coins"] or 0)
        if coins < bet: conn.rollback(); return False, coins
        new_balance = round(coins - bet, 2)
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, str(user_id)))
        conn.commit()
        return True, new_balance
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def finalize_reserved_bet(user_id: int, bet: float, payout: float, choice: str, outcome: str) -> float:
    payout = round(max(0.0, payout), 2)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        if payout > 0:
            conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (payout, str(user_id)))
        conn.execute(
            "INSERT INTO bets (user_id, bet_amount, choice, outcome, win, payout, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(user_id), round(bet, 2), choice, outcome, 1 if payout > 0 else 0, payout, now_ts()),
        )
        if payout <= 0:
            conn.execute("UPDATE users SET lost_coins = lost_coins + ? WHERE id = ?", (bet, str(user_id)))
            user_row = conn.execute("SELECT ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if user_row and user_row["ref_id"]:
                ref_bonus = round(bet * REF_PERCENT, 2)
                conn.execute("UPDATE users SET ref_earned = ref_earned + ?, coins = coins + ? WHERE id = ?", (ref_bonus, ref_bonus, user_row["ref_id"]))
        else:
            conn.execute("UPDATE users SET won_coins = won_coins + ? WHERE id = ?", (payout - bet, str(user_id)))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"] or 0)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def settle_instant_bet(user_id: int, bet: float, payout: float, choice: str, outcome: str) -> tuple[bool, float]:
    payout = round(max(0.0, payout), 2)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        coins = float(row["coins"] or 0)
        if coins < bet: conn.rollback(); return False, coins
        new_balance = round(coins - bet + payout, 2)
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (new_balance, str(user_id)))
        conn.execute(
            "INSERT INTO bets (user_id, bet_amount, choice, outcome, win, payout, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(user_id), round(bet, 2), choice, outcome, 1 if payout > 0 else 0, payout, now_ts()),
        )
        if payout <= 0:
            conn.execute("UPDATE users SET lost_coins = lost_coins + ? WHERE id = ?", (bet, str(user_id)))
            user_row = conn.execute("SELECT ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if user_row and user_row["ref_id"]:
                ref_bonus = round(bet * REF_PERCENT, 2)
                conn.execute("UPDATE users SET ref_earned = ref_earned + ?, coins = coins + ? WHERE id = ?", (ref_bonus, ref_bonus, user_row["ref_id"]))
        else:
            conn.execute("UPDATE users SET won_coins = won_coins + ? WHERE id = ?", (payout - bet, str(user_id)))
        conn.commit()
        return True, new_balance
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def add_balance(user_id: int, delta: float) -> float:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (round(delta, 2), str(user_id)))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"] or 0)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def transfer_coins(from_id: int, to_id: int, amount: float) -> tuple[bool, str]:
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, from_id)
        ensure_user_in_conn(conn, to_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(from_id),)).fetchone()
        if float(row["coins"] or 0) < amount: conn.rollback(); return False, "Недостаточно средств."
        conn.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (amount, str(from_id)))
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (amount, str(to_id)))
        conn.commit()
        return True, "Перевод выполнен."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_profile_stats(user_id: int) -> Dict[str, Any]:
    conn = get_db()
    try:
        ensure_user_in_conn(conn, user_id)
        user = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        row = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN win = 1 THEN 1 ELSE 0 END), 0) AS wins, COALESCE(SUM(payout - bet_amount), 0) AS net, COALESCE(SUM(bet_amount), 0) AS total_bet FROM bets WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        dep = conn.execute(
            "SELECT COUNT(*) AS active_count, COALESCE(SUM(principal), 0) AS active_sum FROM bank_deposits WHERE user_id = ? AND status = 'active'",
            (str(user_id),),
        ).fetchone()
        conn.commit()
        return {
            "coins": float(user["coins"] or 0),
            "status": int(user["status"] or 0),
            "total": int(row["total"] or 0),
            "wins": int(row["wins"] or 0),
            "net": float(row["net"] or 0),
            "total_bet": float(row["total_bet"] or 0),
            "active_deposits": int(dep["active_count"] or 0),
            "active_deposit_sum": float(dep["active_sum"] or 0),
            "ref_earned": float(user["ref_earned"] or 0),
            "ref_count": int(user["ref_count"] or 0),
            "first_name": user["first_name"] or "",
        }
    finally:
        conn.close()

def get_top_balances(limit: int = 10) -> list[Dict[str, Any]]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, coins, first_name FROM users ORDER BY coins DESC, id ASC LIMIT ?", (int(limit),)).fetchall()
        conn.commit()
        return [{"id": row["id"], "coins": row["coins"], "name": row["first_name"] or f"ID {row['id']}"} for row in rows]
    finally:
        conn.close()

def generate_check_code() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=32))

def create_check(user_id: int, per_user: float, count: int) -> str:
    total = round(per_user * count, 2)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        if float(row["coins"] or 0) < total: conn.rollback(); return ""
        code = generate_check_code()
        conn.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (total, str(user_id)))
        set_json_value(f"check:{code}", {"creator": user_id, "per_user": per_user, "remaining": count, "claimed": []})
        conn.commit()
        return code
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def claim_check(user_id: int, code: str) -> tuple[bool, str, float]:
    data = get_json_value(f"check:{code}")
    if not data: return False, "Чек не найден.", 0.0
    if data["remaining"] <= 0: return False, "Этот чек уже закончился.", 0.0
    if str(user_id) in data["claimed"]: return False, "Ты уже активировал этот чек.", 0.0
    if data["creator"] == user_id: return False, "Нельзя активировать свой чек.", 0.0
    data["claimed"].append(str(user_id))
    data["remaining"] -= 1
    reward = data["per_user"]
    add_balance(user_id, reward)
    set_json_value(f"check:{code}", data)
    return True, "Чек успешно активирован.", reward

def redeem_promo(user_id: int, code: str) -> tuple[bool, str, float]:
    promo_name = code.upper().strip()
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        row = conn.execute("SELECT * FROM promos WHERE name = ?", (promo_name,)).fetchone()
        if not row: conn.rollback(); return False, "Промокод не найден.", 0.0
        if int(row["remaining_activations"] or 0) <= 0: conn.rollback(); return False, "Промокод уже закончился.", 0.0
        claimed = json.loads(row["claimed"] or "[]")
        if str(user_id) in {str(x) for x in claimed}: conn.rollback(); return False, "Ты уже активировал этот промокод.", 0.0
        reward = round(float(row["reward"] or 0), 2)
        claimed.append(str(user_id))
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (reward, str(user_id)))
        conn.execute("UPDATE promos SET claimed = ?, remaining_activations = remaining_activations - 1 WHERE name = ?", (json.dumps(claimed, ensure_ascii=False), promo_name))
        conn.commit()
        return True, "Промокод активирован.", reward
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def create_promo(code: str, reward: float, activations: int) -> None:
    conn = get_db()
    try:
        conn.execute("INSERT INTO promos (name, reward, claimed, remaining_activations) VALUES (?, ?, '[]', ?) ON CONFLICT(name) DO UPDATE SET reward = excluded.reward, remaining_activations = excluded.remaining_activations, claimed = '[]'", (code.upper().strip(), round(reward, 2), int(activations)))
        conn.commit()
    finally:
        conn.close()

def add_deposit(user_id: int, amount: float, term_days: int) -> tuple[bool, str]:
    if term_days not in BANK_TERMS: return False, "Неверный срок депозита."
    ok, _ = reserve_bet(user_id, amount)
    if not ok: return False, "Недостаточно средств."
    conn = get_db()
    try:
        conn.execute("INSERT INTO bank_deposits (user_id, principal, rate, term_days, opened_at, status, closed_at) VALUES (?, ?, ?, ?, ?, 'active', NULL)", (str(user_id), round(amount, 2), float(BANK_TERMS[term_days]), int(term_days), now_ts()))
        conn.commit()
        return True, "Депозит открыт."
    finally:
        conn.close()

def list_user_deposits(user_id: int) -> list[sqlite3.Row]:
    conn = get_db()
    try:
        return list(conn.execute("SELECT * FROM bank_deposits WHERE user_id = ? ORDER BY id DESC LIMIT 15", (str(user_id),)).fetchall())
    finally:
        conn.close()

def withdraw_matured_deposits(user_id: int) -> tuple[int, float]:
    now = now_ts()
    conn = get_db()
    total_payout, closed_count = 0.0, 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user_in_conn(conn, user_id)
        rows = conn.execute("SELECT * FROM bank_deposits WHERE user_id = ? AND status = 'active'", (str(user_id),)).fetchall()
        for row in rows:
            if now < int(row["opened_at"] or 0) + int(row["term_days"] or 0) * 86400: continue
            payout = round(float(row["principal"] or 0) * (1.0 + float(row["rate"] or 0)), 2)
            total_payout += payout; closed_count += 1
            conn.execute("UPDATE bank_deposits SET status = 'closed', closed_at = ? WHERE id = ?", (now, int(row["id"])))
        if total_payout > 0: conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (round(total_payout, 2), str(user_id)))
        conn.commit()
        return closed_count, round(total_payout, 2)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_bank_summary(user_id: int) -> Dict[str, Any]:
    conn = get_db()
    try:
        ensure_user_in_conn(conn, user_id)
        user = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        deps = conn.execute("SELECT COUNT(*) AS count_active, COALESCE(SUM(principal), 0) AS active_sum FROM bank_deposits WHERE user_id = ? AND status = 'active'", (str(user_id),)).fetchone()
        conn.commit()
        return {"coins": float(user["coins"] or 0), "count_active": int(deps["count_active"] or 0), "active_sum": float(deps["active_sum"] or 0)}
    finally:
        conn.close()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def clear_active_sessions(user_id: int) -> None:
    for d in (TOWER_GAMES, GOLD_GAMES, DIAMOND_GAMES, MINES_GAMES, OCHKO_GAMES):
        d.pop(user_id, None)

def roulette_roll(choice: str) -> tuple[bool, float, str, int, str]:
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in RED_NUMBERS else "black")
    parity = "zero" if number == 0 else ("even" if number % 2 == 0 else "odd")
    win, multiplier = False, 0.0
    if choice == "red" and color == "red": win, multiplier = True, 2.0
    elif choice == "black" and color == "black": win, multiplier = True, 2.0
    elif choice == "even" and parity == "even": win, multiplier = True, 2.0
    elif choice == "odd" and parity == "odd": win, multiplier = True, 2.0
    elif choice == "zero" and number == 0: win, multiplier = True, 36.0
    elif choice.isdigit() and 0 <= int(choice) <= 36 and int(choice) == number: win, multiplier = True, 35.0
    pretty_color = {"red": "🔴 Красное", "black": "⚫ Чёрное", "green": "🟢 Зеро"}[color]
    return win, multiplier, f"🎡 Выпало {number} ({pretty_color})", number, color

def football_value_text(value: int) -> str: return "⚽ Гол" if value >= 3 else "💨 Мимо"
def basketball_value_text(value: int) -> str: return "🏀 Точный бросок" if value in {4, 5} else "💨 Промах"

def mines_multiplier(opened_count: int, mines_count: int, total_cells: int = 25) -> float:
    if opened_count <= 0: return 1.0
    safe_cells = total_cells - mines_count
    base = total_cells / max(1.0, safe_cells)
    mult = (base ** opened_count) * 0.95
    return round(mult, 2)

def make_deck() -> list[tuple[str, str]]:
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    suits = ["♠", "♥", "♦", "♣"]
    deck = [(r, s) for r in ranks for s in suits]
    random.shuffle(deck)
    return deck

def card_points(rank: str) -> int:
    if rank in {"J", "Q", "K"}: return 10
    if rank == "A": return 11
    return int(rank)

def hand_value(cards: list[tuple[str, str]]) -> int:
    total = sum(card_points(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces > 0: total -= 10; aces -= 1
    return total

def format_hand(cards: list[tuple[str, str]]) -> str:
    return " ".join(f"{r}{s}" for r, s in cards)

def _game_lock(user_id: int | str) -> asyncio.Lock:
    key = str(user_id)
    if key not in user_game_locks: user_game_locks[key] = asyncio.Lock()
    return user_game_locks[key]

async def check_subscription(bot: Bot, user_id: int) -> tuple[bool, str]:
    not_subscribed = []
    try:
        cm = await bot.get_chat_member(CHANNEL_ID, user_id)
        if cm.status in ("left", "kicked", "restricted"): not_subscribed.append(f"📢 Канал: {CHANNEL_ID}")
    except Exception: not_subscribed.append(f"📢 Канал: {CHANNEL_ID}")
    try:
        cm = await bot.get_chat_member(CHAT_ID, user_id)
        if cm.status in ("left", "kicked", "restricted"): not_subscribed.append(f"💬 Чат: {CHAT_ID}")
    except Exception: not_subscribed.append(f"💬 Чат: {CHAT_ID}")
    if not_subscribed:
        lines = ["❌ <b>Для игры нужна подписка:</b>", ""] + not_subscribed + ["", "<i>Подпишись и попробуй снова.</i>"]
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

# ==================== UI КЛАВИАТУРЫ ====================

def games_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗼 Башня", callback_data="games:pick:tower"), InlineKeyboardButton(text="🥇 Золото", callback_data="games:pick:gold")],
        [InlineKeyboardButton(text="💍 Алмазы", callback_data="games:pick:diamonds"), InlineKeyboardButton(text="💣 Мины", callback_data="games:pick:mines")],
        [InlineKeyboardButton(text="🎴 Очко", callback_data="games:pick:ochko"), InlineKeyboardButton(text="🎡 Рулетка", callback_data="games:pick:roulette")],
        [InlineKeyboardButton(text="📈 Краш", callback_data="games:pick:crash"), InlineKeyboardButton(text="🎲 Кубик", callback_data="games:pick:cube")],
        [InlineKeyboardButton(text="🎯 Кости", callback_data="games:pick:dice"), InlineKeyboardButton(text="⚽ Футбол", callback_data="games:pick:football")],
        [InlineKeyboardButton(text="🏀 Баскет", callback_data="games:pick:basket")],
    ])

def checks_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать чек", callback_data="checks:create")],
        [InlineKeyboardButton(text="📄 Мои чеки", callback_data="checks:my")],
    ])

def bank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Открыть депозит", callback_data="bank:open")],
        [InlineKeyboardButton(text="📜 Мои депозиты", callback_data="bank:list")],
        [InlineKeyboardButton(text="💰 Снять зрелые", callback_data="bank:withdraw")],
    ])

def bank_terms_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{d} дн. (+{int(r*100)}%)", callback_data=f"bank:term:{d}")] for d, r in BANK_TERMS.items()]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bank:term:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def roulette_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное", callback_data="roulette:choice:red"), InlineKeyboardButton(text="⚫ Чёрное", callback_data="roulette:choice:black")],
        [InlineKeyboardButton(text="2️⃣ Чет", callback_data="roulette:choice:even"), InlineKeyboardButton(text="1️⃣ Нечет", callback_data="roulette:choice:odd")],
        [InlineKeyboardButton(text="0️⃣ Зеро (x36)", callback_data="roulette:choice:zero")],
        [InlineKeyboardButton(text="🔢 Число (x35)", callback_data="roulette:choice:number")],
    ])

def tower_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="tower:pick:1"), InlineKeyboardButton(text="2", callback_data="tower:pick:2"), InlineKeyboardButton(text="3", callback_data="tower:pick:3")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="tower:cash"), InlineKeyboardButton(text="❌ Сдаться", callback_data="tower:cancel")],
    ])

def gold_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 1", callback_data="gold:pick:1"), InlineKeyboardButton(text="🧱 2", callback_data="gold:pick:2"), InlineKeyboardButton(text="🧱 3", callback_data="gold:pick:3"), InlineKeyboardButton(text="🧱 4", callback_data="gold:pick:4")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="gold:cash"), InlineKeyboardButton(text="❌ Сдаться", callback_data="gold:cancel")],
    ])

def diamond_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔹 1", callback_data="diamond:pick:1"), InlineKeyboardButton(text="🔹 2", callback_data="diamond:pick:2"), InlineKeyboardButton(text="🔹 3", callback_data="diamond:pick:3"), InlineKeyboardButton(text="🔹 4", callback_data="diamond:pick:4"), InlineKeyboardButton(text="🔹 5", callback_data="diamond:pick:5")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="diamond:cash"), InlineKeyboardButton(text="❌ Сдаться", callback_data="diamond:cancel")],
    ])

def mines_kb_5x5(game: Dict[str, Any], reveal_all: bool = False) -> InlineKeyboardMarkup:
    opened = set(game["opened"])
    mines_set = set(game["mines"])
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c + 1
            if idx in opened: text, cb = "✅", "mines:noop"
            elif reveal_all and idx in mines_set: text, cb = "💣", "mines:noop"
            else: text, cb = str(idx), f"mines:cell:{idx}"
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="💰 Забрать", callback_data="mines:cash"), InlineKeyboardButton(text="❌ Сдаться", callback_data="mines:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def ochko_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Взять", callback_data="ochko:hit"), InlineKeyboardButton(text="✋ Стоп", callback_data="ochko:stand")]])

def ochko_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Начать", callback_data="ochko:start"), InlineKeyboardButton(text="❌ Отмена", callback_data="ochko:cancel")]])

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать dC", callback_data="admin:give")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Топ-20", callback_data="admin:top20")],
        [InlineKeyboardButton(text="🎟 Новый промо", callback_data="admin:newpromo")],
        [InlineKeyboardButton(text="🔄 Обновить БД", callback_data="admin:refreshdb")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
    ])

# ==================== BOT ====================

dp = Dispatcher(storage=MemoryStorage())

def get_bot_token() -> str:
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE": raise RuntimeError("Заполни BOT_TOKEN")
    return BOT_TOKEN# ==================== КОМАНДЫ ====================

@dp.message(CommandStart(deep_link=True))
async def start_deep(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    args = command.args or ""
    ref_id = None
    check_code = None

    if args.startswith("ref_"):
        ref_id = args.replace("ref_", "")
        if ref_id == str(user_id): ref_id = None
    elif args.startswith("check_"):
        check_code = args.replace("check_", "")

    ensure_user(user_id, ref_id, message.from_user.first_name or "")
    await state.clear()
    clear_active_sessions(user_id)

    if ref_id:
        add_balance(int(ref_id), REF_REWARD)
        try:
            await message.bot.send_message(int(ref_id), f"{EMOJI_BONUS} <b>Новый реферал!</b>\nПо твоей ссылке присоединился {mention_user(user_id, message.from_user.first_name)}\nНачислено: <b>{fmt_money(REF_REWARD)}</b>")
        except Exception: pass

    if check_code:
        ok, msg, reward = claim_check(user_id, check_code)
        if ok:
            await message.answer(f"✅ <b>Чек активирован!</b>\nНачислено: <b>{fmt_money(reward)}</b>")
        else:
            await message.answer(f"❌ {msg}")

    bot = message.bot
    subscribed, sub_msg = await check_subscription(bot, user_id)
    if not subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/dodoCoin_news")],
            [InlineKeyboardButton(text="💬 Войти в чат", url="https://t.me/dodocoin_chat")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
        ])
        await message.answer(sub_msg, reply_markup=kb)
        return

    await message.answer(
        f"🎮 <b>DodoCoin Casino Bot</b>\n"
        "<blockquote>Основные команды:\n"
        "• <code>б</code> — баланс\n"
        "• <code>бонус</code> — ежедневный бонус\n"
        "• <code>игры</code> — список игр\n"
        "• <code>топ</code> — топ игроков\n"
        "• <code>банк</code> — депозиты\n"
        "• <code>чеки</code> — создать/активировать чек\n"
        "• <code>промо CODE</code> — активировать промокод\n"
        "• <code>реф</code> — реферальная система\n"
        "• <code>П сумма</code> — перевести игроку</blockquote>"
    )

@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    ensure_user(user_id, first_name=message.from_user.first_name or "")
    await state.clear()
    clear_active_sessions(user_id)

    bot = message.bot
    subscribed, sub_msg = await check_subscription(bot, user_id)
    if not subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/dodoCoin_news")],
            [InlineKeyboardButton(text="💬 Войти в чат", url="https://t.me/dodocoin_chat")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
        ])
        await message.answer(sub_msg, reply_markup=kb)
        return

    await message.answer(
        f"🎮 <b>DodoCoin Casino Bot</b>\n"
        "<blockquote>Основные команды:\n"
        "• <code>б</code> — баланс\n"
        "• <code>бонус</code> — ежедневный бонус\n"
        "• <code>игры</code> — список игр\n"
        "• <code>топ</code> — топ игроков\n"
        "• <code>банк</code> — депозиты\n"
        "• <code>чеки</code> — создать/активировать чек\n"
        "• <code>промо CODE</code> — активировать промокод\n"
        "• <code>реф</code> — реферальная система\n"
        "• <code>П сумма</code> — перевести игроку</blockquote>"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(query: CallbackQuery):
    bot = query.bot
    subscribed, sub_msg = await check_subscription(bot, query.from_user.id)
    if not subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/dodoCoin_news")],
            [InlineKeyboardButton(text="💬 Войти в чат", url="https://t.me/dodocoin_chat")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")],
        ])
        await query.message.edit_text(sub_msg, reply_markup=kb)
        await query.answer("Подпишись на канал и чат!", show_alert=True)
        return
    await query.message.edit_text(
        "✅ <b>Подписка подтверждена!</b>\n\n"
        "🎮 <b>DodoCoin Casino Bot</b>\n"
        "<blockquote>Основные команды:\n"
        "• <code>б</code> — баланс\n• <code>бонус</code> — бонус\n• <code>игры</code>\n• <code>топ</code>\n"
        "• <code>банк</code>\n• <code>чеки</code>\n• <code>промо CODE</code>\n• <code>реф</code>\n• <code>П сумма</code></blockquote>"
    )
    await query.answer("Добро пожаловать!")

@dp.message(lambda m: normalize_text(m.text) in {"отмена", "/cancel", "cancel"})
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    clear_active_sessions(message.from_user.id)
    await message.answer("🛑 Отменено.")

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"б", "баланс", "/balance", "balance", "b"})
async def balance_command(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"{EMOJI_COIN} {mention_user(message.from_user.id, message.from_user.first_name)}, твой баланс:\n"
        f"<blockquote>Доступно: <b>{fmt_money(float(user['coins'] or 0))}</b></blockquote>"
    )

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"профиль", "/profile", "profile"})
async def profile_command(message: Message):
    user_id = message.from_user.id
    stats = get_profile_stats(user_id)
    user = get_user(user_id)
    reg_date = fmt_dt(int(user["registered_at"] or 0))
    top_rows = get_top_balances(1000)
    place = "—"
    for idx, row in enumerate(top_rows, start=1):
        if str(row["id"]) == str(user_id): place = str(idx); break
    status_code = int(user["status"] or 0)
    status_map = {0: f"{EMOJI_PLAYER} Игрок", 1: f"{EMOJI_VIP} VIP", 2: f"{EMOJI_DIAMOND} Премиум", 3: f"{EMOJI_CROWN} Админ"}
    status_text = status_map.get(status_code, f"{EMOJI_PLAYER} Игрок")
    if is_admin_user(user_id): status_text = f"{EMOJI_CROWN} Админ"
    lines = [
        f"{EMOJI_ID} <b>Профиль</b>",
        "·····················",
        f"├ {EMOJI_PLAYER} <b>{escape_html(message.from_user.full_name)}</b>",
        f"├ {EMOJI_STATUS} Статус: <b>{status_text}</b>",
        f"├ {EMOJI_GAMES} Сыграно игр: <b>{stats['total']}</b>",
        f"├ {EMOJI_TOP} Место в топе: <b>#{place}</b>",
        f"├ {EMOJI_TURNOVER} Оборот: <b>{fmt_money(stats['total_bet'])}</b>",
        f"├ {EMOJI_LOST} Проиграно: <b>{fmt_money(float(user['lost_coins'] or 0))}</b>",
        f"├ {EMOJI_DATE} Дата регистрации: <b>{reg_date}</b>",
        "·····················",
        f"{EMOJI_COIN} Баланс: <b>{fmt_money(stats['coins'])}</b>",
        "·····················",
        f"{EMOJI_ID} ID: <code>{user_id}</code>",
    ]
    await message.answer("\n".join(lines))

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"бонус", "/bonus", "bonus"})
async def bonus_command(message: Message):
    user_id = message.from_user.id
    ensure_user(user_id)
    key = f"bonus_ts:{user_id}"
    last = int(get_json_value(key, 0) or 0)
    now = now_ts()
    if now - last < BONUS_COOLDOWN_SECONDS:
        left = BONUS_COOLDOWN_SECONDS - (now - last)
        await message.answer(f"{EMOJI_BONUS} Ты уже забрал бонус.\nОсталось: <b>{fmt_left(left)}</b>")
        return
    reward = round(float(random.randint(BONUS_REWARD_MIN, BONUS_REWARD_MAX)), 2)
    ok, balance = settle_instant_bet(user_id=user_id, bet=0.0, payout=reward, choice="bonus", outcome="bonus_claim")
    if not ok:
        await message.answer("Ошибка.")
        return
    set_json_value(key, now)
    await message.answer(f"{EMOJI_BONUS} Бонус получен!\nНачислено: <b>{fmt_money(reward)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"помощь", "/help", "help"})
async def help_command(message: Message):
    admin_hint = ""
    if is_admin_user(message.from_user.id):
        admin_hint = "\n\n🛠️ <b>Админ:</b>\n<code>админ</code> — панель\n<code>выдать 1000</code> (reply) — выдать dC\n<code>/new_promo</code> — промо\n<code>/addpromo CODE REWARD ACTS</code>"
    await message.answer(
        "❓ <b>Помощь</b>\n"
        "<blockquote>💰 <code>б</code> — баланс\n🎁 <code>бонус</code> — бонус\n🎮 <code>игры</code> — игры\n"
        "🏆 <code>топ</code> — топ\n🏦 <code>банк</code> — депозиты\n🧾 <code>чеки</code> — чеки\n"
        "🎟 <code>промо CODE</code>\n🔗 <code>реф</code> — рефералы\n💸 <code>П сумма</code> (reply) — перевод</blockquote>\n\n"
        "<b>Игры:</b>\n🗼 башня, 🥇 золото, 💍 алмазы, 🎡 рулетка, 📈 краш,\n💣 мины (5×5), 🎲 кубик, 🎯 кости, 🎴 очко, ⚽ футбол, 🏀 баскет\n\n"
        "Отмена: <code>отмена</code>" + admin_hint
    )

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"топ", "/top", "top"})
async def top_command(message: Message):
    rows = get_top_balances(10)
    if not rows:
        await message.answer("🏆 <b>Топ игроков</b>\n<blockquote><i>Пока пусто.</i></blockquote>")
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Топ игроков</b>", "<blockquote>"]
    for idx, row in enumerate(rows, start=1):
        icon = medals.get(idx, f"{idx}.")
        name = escape_html(row["name"])
        lines.append(f"{icon} {name} — <b>{fmt_money(float(row['coins']))}</b>")
    lines.append("</blockquote>")
    await message.answer("\n".join(lines))

# ==================== РЕФЕРАЛЫ ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"реф", "рефка", "/ref", "ref"})
async def ref_command(message: Message):
    user_id = message.from_user.id
    stats = get_profile_stats(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    lines = [
        f"{EMOJI_REF} <b>ПРИГЛАСИТЬ ДРУЗЕЙ</b>",
        "·····················",
        f"{EMOJI_BONUS} Приглашайте друзей и получайте бонусы:",
        f"• <b>{fmt_money(REF_REWARD)}</b> за каждого друга",
        f"• <b>{int(REF_PERCENT * 100)}%</b> от проигрыша друзей",
        "",
        f"{EMOJI_REF} <b>Твоя ссылка:</b>",
        f"⤷ <code>{ref_link}</code>",
        "",
        f"{EMOJI_COIN} Уже заработано: <b>{fmt_money(stats['ref_earned'])}</b>",
        f"{EMOJI_INVITED} Приглашено: <b>{stats['ref_count']} чел.</b>",
        "",
        "ℹ️ Друг должен сыграть хотя бы 1 игру или собрать бонус.",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"ref:copy:{user_id}")],
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=f"Реферальная ссылка: {ref_link}")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)

@dp.callback_query(F.data.startswith("ref:copy:"))
async def ref_copy_cb(query: CallbackQuery):
    uid = query.data.split(":")[-1]
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    await query.message.answer(f"🔗 Твоя ссылка:\n<code>{ref_link}</code>")
    await query.answer("Ссылка в чате!")

# ==================== ПЕРЕВОДЫ ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text).startswith("п ") or normalize_text(m.text).startswith("дать "))
async def transfer_start(message: Message):
    parts = str(message.text or "").strip().split()
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        try:
            amount = parse_amount(parts[1])
        except Exception:
            await message.answer("Формат: <code>П 1000</code>")
            return
        if amount < 10: await message.answer("Минимум: 10 dC"); return
        ok, msg = transfer_coins(message.from_user.id, target.id, amount)
        if not ok: await message.answer(f"❌ {msg}"); return
        await message.answer(f"✅ Переведено <b>{fmt_money(amount)}</b> для {mention_user(target.id, target.full_name)}")
        try:
            await message.bot.send_message(target.id, f"{EMOJI_COIN} Получен перевод <b>{fmt_money(amount)}</b> от {mention_user(message.from_user.id, message.from_user.first_name)}")
        except Exception: pass
    elif len(parts) >= 3:
        try:
            target_raw = parts[1].replace("@", "")
            target_id = int(target_raw)
            amount = parse_amount(parts[2])
        except Exception:
            await message.answer("Формат: <code>П ID сумма</code>")
            return
        if amount < 10: await message.answer("Минимум: 10 dC"); return
        ok, msg = transfer_coins(message.from_user.id, target_id, amount)
        if not ok: await message.answer(f"❌ {msg}"); return
        await message.answer(f"✅ Переведено <b>{fmt_money(amount)}</b> для {mention_user(target_id)}")
        try:
            await message.bot.send_message(target_id, f"{EMOJI_COIN} Получен перевод <b>{fmt_money(amount)}</b> от {mention_user(message.from_user.id, message.from_user.first_name)}")
        except Exception: pass
    else:
        await message.answer("Ответь на сообщение: <code>П сумма</code>\nИли: <code>П ID сумма</code>")# ==================== АДМИНКА ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"админ", "/admin", "admin", "админка"})
async def admin_command(message: Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Команда только для админов.")
        return
    await message.answer(f"{EMOJI_CROWN} <b>Админ-панель</b>\nВыбери действие:", reply_markup=admin_panel_kb())

@dp.message(StateFilter(None), lambda m: normalize_text(m.text).startswith("выдать "))
async def admin_give_coins(message: Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Команда только для админов.")
        return
    parts = str(message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: <code>выдать 1000</code> (reply на сообщение игрока)")
        return
    try:
        amount = parse_amount(parts[1])
    except Exception:
        await message.answer("Введи корректную сумму.")
        return
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    balance = add_balance(target.id, amount)
    await message.answer(f"✅ Выдано <b>{fmt_money(amount)}</b>\nКому: {mention_user(target.id, target.full_name)}\nБаланс: <b>{fmt_money(balance)}</b>")

@dp.callback_query(F.data.startswith("admin:"))
async def admin_cb(query: CallbackQuery, state: FSMContext):
    if not is_admin_user(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True)
        return
    action = query.data.split(":")[1]
    if action == "give":
        await state.clear()
        await state.set_state(AdminBroadcastStates.waiting_message)
        await state.update_data(admin_action="give")
        await query.message.answer("💰 Введи сумму dC (reply на сообщение игрока):")
        await query.answer()
    elif action == "stats":
        conn = get_db()
        try:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            bets_count = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            total_bet = conn.execute("SELECT COALESCE(SUM(bet_amount), 0) FROM bets").fetchone()[0]
            total_payout = conn.execute("SELECT COALESCE(SUM(payout), 0) FROM bets").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        await query.message.answer(
            "📊 <b>Статистика</b>\n"
            f"<blockquote>👥 Пользователей: <b>{users_count}</b>\n🎮 Ставок: <b>{bets_count}</b>\n"
            f"💰 Сумма ставок: <b>{fmt_money(float(total_bet))}</b>\n💸 Выплат: <b>{fmt_money(float(total_payout))}</b></blockquote>"
        )
        await query.answer()
    elif action == "top20":
        rows = get_top_balances(20)
        if not rows:
            await query.message.answer("Список пуст.")
        else:
            lines = ["👥 <b>Топ-20</b>", "<blockquote>"]
            for idx, row in enumerate(rows, start=1):
                lines.append(f"{idx}. {escape_html(row['name'])} — <b>{fmt_money(float(row['coins']))}</b>")
            lines.append("</blockquote>")
            await query.message.answer("\n".join(lines))
        await query.answer()
    elif action == "newpromo":
        await state.clear()
        await state.set_state(NewPromoStates.waiting_code)
        await query.message.answer("🎟 <b>Создание промо</b>\nШаг 1/3: Введи код (A-Z, 0-9, _, -)")
        await query.answer()
    elif action == "refreshdb":
        init_db()
        await query.message.answer("✅ База обновлена.")
        await query.answer()
    elif action == "broadcast":
        await state.clear()
        await state.set_state(AdminBroadcastStates.waiting_message)
        await state.update_data(admin_action="broadcast")
        await query.message.answer("📢 Введи сообщение для рассылки:")
        await query.answer()

@dp.message(AdminBroadcastStates.waiting_message)
async def admin_broadcast_or_give(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("admin_action", "")
    if action == "broadcast":
        await state.clear()
        conn = get_db()
        try:
            users = conn.execute("SELECT id FROM users").fetchall()
            conn.commit()
        finally:
            conn.close()
        success, failed = 0, 0
        for user in users:
            try:
                await message.bot.send_message(int(user["id"]), f"📢 <b>Рассылка:</b>\n\n{message.text}")
                success += 1
            except Exception:
                failed += 1
        await message.answer(f"📢 Рассылка завершена\n✅ {success} | ❌ {failed}")
    elif action == "give":
        try:
            amount = parse_amount(message.text)
        except Exception:
            await message.answer("Введи число.")
            return
        await state.clear()
        target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
        balance = add_balance(target.id, amount)
        await message.answer(f"✅ Выдано <b>{fmt_money(amount)}</b>\nКому: {mention_user(target.id, target.full_name)}\nБаланс: <b>{fmt_money(balance)}</b>")

# ==================== ЧЕКИ ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"чеки", "/check", "check"})
async def checks_command(message: Message):
    await message.answer("🧾 <b>Чеки</b>\n<i>Выбери действие:</i>", reply_markup=checks_kb())

@dp.callback_query(F.data == "checks:create")
async def checks_create_cb(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(CheckCreateStates.waiting_amount)
    await query.message.answer("💰 Введи сумму на 1 активацию чека (dC):")
    await query.answer()

@dp.message(CheckCreateStates.waiting_amount)
async def checks_create_amount(message: Message, state: FSMContext):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer("Нужно положительное число. Например: 100")
        return
    if amount < 10:
        await message.answer("Минимум: 10 dC")
        return
    await state.update_data(amount=amount)
    await state.set_state(CheckCreateStates.waiting_count)
    await message.answer("🔢 Сколько активаций (1-100)?")

@dp.message(CheckCreateStates.waiting_count)
async def checks_create_count(message: Message, state: FSMContext):
    try:
        count = parse_int(message.text)
    except Exception:
        await message.answer("Введи целое число 1-100.")
        return
    if not 1 <= count <= 100:
        await message.answer("Количество: 1-100.")
        return
    data = await state.get_data()
    amount = float(data.get("amount", 0))
    code = create_check(message.from_user.id, amount, count)
    await state.clear()
    if not code:
        await message.answer("❌ Недостаточно средств.")
        return
    total = round(amount * count, 2)
    check_link = f"https://t.me/{BOT_USERNAME}?start=check_{code}"
    await message.answer(
        f"✅ <b>ЧЕК СОЗДАН!</b>\n\n"
        f"🔗 Ссылка:\n<code>{check_link}</code>\n\n"
        f"💰 На 1 чел: <b>{fmt_money(amount)}</b>\n"
        f"👥 Активаций: <b>{count}</b>\n"
        f"💸 Заморожено: <b>{fmt_money(total)}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"check:copy:{code}")],
            [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=f"Чек на {fmt_money(amount)}: {check_link}")],
        ])
    )

@dp.callback_query(F.data.startswith("check:copy:"))
async def check_copy_cb(query: CallbackQuery):
    code = query.data.split(":")[-1]
    link = f"https://t.me/{BOT_USERNAME}?start=check_{code}"
    await query.message.answer(f"🔗 Ссылка на чек:\n<code>{link}</code>")
    await query.answer("Ссылка в чате!")

@dp.callback_query(F.data == "checks:my")
async def checks_my_cb(query: CallbackQuery):
    user_id = query.from_user.id
    conn = get_db()
    try:
        keys = conn.execute("SELECT key FROM json_data WHERE key LIKE 'check:%'").fetchall()
        conn.commit()
    finally:
        conn.close()
    my_checks = []
    for k in keys:
        data = get_json_value(k["key"])
        if data and data.get("creator") == user_id:
            code = k["key"].replace("check:", "")
            my_checks.append({"code": code, "per_user": data["per_user"], "remaining": data["remaining"]})
    if not my_checks:
        await query.message.answer("У тебя нет созданных чеков.")
    else:
        lines = ["🧾 <b>Твои чеки</b>", "<blockquote>"]
        for ch in my_checks[:10]:
            link = f"https://t.me/{BOT_USERNAME}?start=check_{ch['code']}"
            lines.append(f"<code>{link}</code>\n└ {fmt_money(ch['per_user'])} | Ост: {ch['remaining']}")
        lines.append("</blockquote>")
        await query.message.answer("\n".join(lines))
    await query.answer()

# ==================== ПРОМОКОДЫ ====================

@dp.message(Command("addpromo"))
async def addpromo_command(message: Message):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Только для админов.")
        return
    parts = str(message.text or "").split()
    if len(parts) != 4:
        await message.answer("Формат: /addpromo CODE REWARD ACTIVATIONS")
        return
    try:
        code = normalize_promo_code(parts[1])
    except Exception:
        await message.answer("Код: 3-24 символа, A-Z, 0-9, _, -")
        return
    try:
        reward = parse_amount(parts[2])
        activations = int(parts[3])
    except Exception:
        await message.answer("Неверные данные.")
        return
    if activations <= 0:
        await message.answer("Активаций > 0.")
        return
    create_promo(code, reward, activations)
    await message.answer(f"✅ Промо <code>{code}</code> создан!\n💰 {fmt_money(reward)} | ♾️ {activations}")

@dp.message(Command("new_promo"))
async def new_promo_start(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user.id):
        await message.answer("⛔ Только для админов.")
        return
    await state.clear()
    await state.set_state(NewPromoStates.waiting_code)
    await message.answer("🎟 Шаг 1/3: Введи код промо (A-Z, 0-9, _, -)")

@dp.message(StateFilter(NewPromoStates.waiting_code, NewPromoStates.waiting_reward, NewPromoStates.waiting_activations), lambda m: normalize_text(m.text) in {"отмена", "/cancel", "cancel"})
async def new_promo_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Отменено.")

@dp.message(NewPromoStates.waiting_code)
async def new_promo_code(message: Message, state: FSMContext):
    try:
        code = normalize_promo_code(message.text or "")
    except Exception:
        await message.answer("Некорректный код.")
        return
    await state.update_data(code=code)
    await state.set_state(NewPromoStates.waiting_reward)
    await message.answer("💰 Шаг 2/3: Введи награду (число)")

@dp.message(NewPromoStates.waiting_reward)
async def new_promo_reward(message: Message, state: FSMContext):
    try:
        reward = parse_amount(message.text or "")
    except Exception:
        await message.answer("Нужно число.")
        return
    await state.update_data(reward=reward)
    await state.set_state(NewPromoStates.waiting_activations)
    await message.answer("🔢 Шаг 3/3: Введи количество активаций")

@dp.message(NewPromoStates.waiting_activations)
async def new_promo_activations(message: Message, state: FSMContext):
    try:
        activations = parse_int(message.text or "")
    except Exception:
        await message.answer("Нужно целое число.")
        return
    if activations <= 0: await message.answer("> 0."); return
    data = await state.get_data()
    code, reward = str(data.get("code", "")), float(data.get("reward", 0))
    if not code or reward <= 0: await message.answer("Ошибка."); await state.clear(); return
    create_promo(code, reward, activations)
    await state.clear()
    await message.answer(f"✅ Промо <code>{code}</code> создан!\n💰 {fmt_money(reward)} | ♾️ {activations}")

@dp.message(StateFilter(None), lambda m: normalize_text(m.text).startswith("промо"))
async def promo_use(message: Message):
    parts = str(message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer("Формат: <code>промо КОД</code>")
        return
    code = parts[1].strip()
    ok, msg, reward = redeem_promo(message.from_user.id, code)
    if not ok: await message.answer(f"❌ {msg}"); return
    await message.answer(f"✅ Промо активирован!\n💰 Начислено: <b>{fmt_money(reward)}</b>")

# ==================== БАНК ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"банк", "/bank", "bank"})
async def bank_command(message: Message):
    s = get_bank_summary(message.from_user.id)
    await message.answer(
        "🏦 <b>Банк</b>\n"
        f"<blockquote>💰 Баланс: <b>{fmt_money(s['coins'])}</b>\n"
        f"📊 Активных депозитов: <b>{s['count_active']}</b>\n"
        f"💸 В работе: <b>{fmt_money(s['active_sum'])}</b></blockquote>\n"
        "<i>Ставки: 7д +3% | 14д +7% | 30д +18%</i>",
        reply_markup=bank_kb()
    )

@dp.callback_query(F.data == "bank:open")
async def bank_open_cb(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(BankStates.waiting_amount)
    await query.message.answer("💰 Введи сумму депозита (мин. 100 dC):")
    await query.answer()

@dp.message(BankStates.waiting_amount)
async def bank_amount(message: Message, state: FSMContext):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer("Нужно число.")
        return
    if amount < 100: await message.answer("Минимум 100 dC."); return
    await state.update_data(amount=amount)
    await message.answer("📅 Выбери срок:", reply_markup=bank_terms_kb())

@dp.callback_query(F.data.startswith("bank:term:"))
async def bank_term_cb(query: CallbackQuery, state: FSMContext):
    raw = query.data.split(":")[-1]
    if raw == "cancel": await state.clear(); await query.message.answer("Отменено."); await query.answer(); return
    data = await state.get_data()
    amount = float(data.get("amount", 0))
    if amount <= 0: await query.message.answer("Сначала введи сумму."); await query.answer(); return
    try: term_days = int(raw)
    except Exception: await query.answer("Ошибка.", show_alert=True); return
    ok, msg = add_deposit(query.from_user.id, amount, term_days)
    await state.clear()
    if not ok: await query.message.answer(f"❌ {msg}")
    else:
        rate = BANK_TERMS[term_days]
        await query.message.answer(f"✅ Депозит открыт!\n💰 {fmt_money(amount)} | 📅 {term_days}д | +{int(rate*100)}%")
    await query.answer()

@dp.callback_query(F.data == "bank:list")
async def bank_list_cb(query: CallbackQuery):
    rows = list_user_deposits(query.from_user.id)
    if not rows: await query.message.answer("Нет депозитов."); await query.answer(); return
    now = now_ts()
    lines = ["📜 <b>Депозиты</b>"]
    for r in rows[:10]:
        left = int(r["opened_at"] or 0) + int(r["term_days"] or 0) * 86400 - now
        st = "✅ готов" if r["status"] == "active" and left <= 0 else ("⏳ активен" if r["status"] == "active" else "✅ закрыт")
        lines.append(f"#{r['id']} | {fmt_money(float(r['principal']))} | {r['term_days']}д | {st}")
    await query.message.answer("\n".join(lines))
    await query.answer()

@dp.callback_query(F.data == "bank:withdraw")
async def bank_withdraw_cb(query: CallbackQuery):
    closed, payout = withdraw_matured_deposits(query.from_user.id)
    if closed == 0: await query.message.answer("Нет зрелых депозитов.")
    else: await query.message.answer(f"✅ Закрыто: {closed}\n💰 Начислено: <b>{fmt_money(payout)}</b>")
    await query.answer()

# ==================== GAMES MENU ====================

@dp.message(StateFilter(None), lambda m: normalize_text(m.text) in {"игры", "/games", "games"})
async def games_command(message: Message):
    await message.answer("🎮 <b>Игры</b>\nВыбери игру кнопкой или введи команду.\nПример: <code>рул 300 красное</code>", reply_markup=games_kb())

@dp.callback_query(F.data.startswith("games:pick:"))
async def games_pick_cb(query: CallbackQuery, state: FSMContext):
    await state.clear()
    game = query.data.split(":")[-1]
    usage = {"tower": "башня 300 2", "gold": "золото 300", "diamonds": "алмазы 300 2", "roulette": "рул 300 красное", "crash": "краш 300 2.5", "mines": "мины 300 3", "cube": "кубик 300 5", "dice": "кости 300 м", "ochko": "очко 300", "football": "футбол 300 гол", "basket": "баскет 300"}
    ex = usage.get(game)
    if ex: await query.message.answer(f"<i>Пример:</i> <code>{ex}</code>")
    await query.answer()

# ==================== РУЛЕТКА СО СТИКЕРАМИ ====================

ROULETTE_STICKER_SET = "IrisAdvanceRoulette"

def get_random_roulette_sticker() -> str:
    """Возвращает рандомный file_id стикера из сета (заполни после получения)."""
    stickers = [
        "CAACAgIAAxkBAAEK...",  # ЗАМЕНИ НА РЕАЛЬНЫЕ FILE_ID
    ]
    return random.choice(stickers) if stickers else ""

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("рул"))
async def roulette_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 3:
        await state.clear()
        await state.set_state(RouletteStates.waiting_amount)
        await message.answer("🎡 <b>Рулетка</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try:
        bet = parse_bet_legacy(parts[1], balance)
    except Exception:
        await state.clear()
        await state.set_state(RouletteStates.waiting_amount)
        await message.answer("Неверная ставка. Введи сумму:")
        return
    if bet < MIN_BET:
        await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        return

    choice_raw = parts[2]
    mapping = {
        "красное": "red", "кра": "red", "red": "red",
        "черное": "black", "чёрное": "black", "чер": "black", "black": "black",
        "чет": "even", "четное": "even", "чёт": "even", "even": "even",
        "нечет": "odd", "нечетное": "odd", "нечёт": "odd", "odd": "odd",
        "зеро": "zero", "zero": "zero", "зел": "zero", "0": "zero",
    }
    choice = mapping.get(choice_raw)
    if not choice and choice_raw.isdigit() and 0 <= int(choice_raw) <= 36:
        choice = choice_raw

    if not choice:
        await state.update_data(bet=float(bet))
        await state.set_state(RouletteStates.waiting_choice)
        await message.answer("Выбери сектор:", reply_markup=roulette_choice_kb())
        return

    # Отправляем стикер
    sticker_id = get_random_roulette_sticker()
    if sticker_id:
        try:
            await message.answer_sticker(sticker_id)
        except Exception:
            pass

    await asyncio.sleep(1.5)

    win, multiplier, outcome_text, number, color = roulette_roll(choice)
    payout = round(bet * multiplier, 2) if win else 0.0
    ok, new_balance = settle_instant_bet(user_id=user_id, bet=float(bet), payout=payout, choice=f"roulette:{choice}", outcome=f"num={number}")

    if not ok:
        await message.answer("❌ Недостаточно средств.")
        return

    result_emoji = EMOJI_WIN if win else EMOJI_LOSE
    result_word = "Победа" if win else "Поражение"

    await message.answer(
        f"{result_emoji} <b>Рулетка</b>\n"
        f"<blockquote>"
        f"🎡 Итог: <b>{outcome_text}</b>\n"
        f"🎯 Твой выбор: <b>{choice}</b>\n"
        f"▶️ Результат: <b>{result_word}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(new_balance)}</b>"
        f"</blockquote>"
    )

@dp.message(RouletteStates.waiting_amount)
async def roulette_amount(message: Message, state: FSMContext):
    try:
        bet = parse_amount(message.text)
    except Exception:
        await message.answer("Введи корректную сумму.")
        return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    await state.update_data(bet=bet)
    await state.set_state(RouletteStates.waiting_choice)
    await message.answer("🎡 Выбери сектор или введи число (0-36):", reply_markup=roulette_choice_kb())

@dp.message(RouletteStates.waiting_choice)
async def roulette_choice_text(message: Message, state: FSMContext):
    raw = normalize_text(message.text)
    mapping = {
        "красное": "red", "red": "red", "черное": "black", "чёрное": "black", "black": "black",
        "чет": "even", "четное": "even", "even": "even",
        "нечет": "odd", "нечетное": "odd", "odd": "odd",
        "зеро": "zero", "zero": "zero", "0": "zero",
    }
    choice = mapping.get(raw)
    if not choice and raw.isdigit() and 0 <= int(raw) <= 36:
        choice = raw
    if not choice:
        await message.answer("Неверный выбор.")
        return

    data = await state.get_data()
    bet = float(data.get("bet", 0))
    if bet <= 0: await message.answer("Ставка не найдена."); await state.clear(); return

    sticker_id = get_random_roulette_sticker()
    if sticker_id:
        try: await message.answer_sticker(sticker_id)
        except Exception: pass

    await asyncio.sleep(1.5)

    win, multiplier, outcome_text, number, color = roulette_roll(choice)
    payout = round(bet * multiplier, 2) if win else 0.0
    ok, balance = settle_instant_bet(message.from_user.id, bet, payout, f"roulette:{choice}", f"num={number}")
    await state.clear()

    if not ok: await message.answer("❌ Недостаточно средств."); return

    result_emoji = EMOJI_WIN if win else EMOJI_LOSE
    result_word = "Победа" if win else "Поражение"

    await message.answer(
        f"{result_emoji} <b>Рулетка</b>\n"
        f"<blockquote>"
        f"🎡 Итог: <b>{outcome_text}</b>\n"
        f"🎯 Твой выбор: <b>{choice}</b>\n"
        f"▶️ Результат: <b>{result_word}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(balance)}</b>"
        f"</blockquote>"
    )

@dp.callback_query(RouletteStates.waiting_choice, F.data.startswith("roulette:choice:"))
async def roulette_cb(query: CallbackQuery, state: FSMContext):
    choice = query.data.split(":")[-1]
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    if bet <= 0: await query.answer("Ставка не найдена.", show_alert=True); await state.clear(); return

    if choice == "number":
        await query.answer("Введи число от 0 до 36 текстом!")
        return

    sticker_id = get_random_roulette_sticker()
    if sticker_id:
        try: await query.message.answer_sticker(sticker_id)
        except Exception: pass

    await asyncio.sleep(1.5)

    win, multiplier, outcome_text, number, color = roulette_roll(choice)
    payout = round(bet * multiplier, 2) if win else 0.0
    ok, balance = settle_instant_bet(query.from_user.id, bet, payout, f"roulette:{choice}", f"num={number}")
    await state.clear()

    if not ok:
        await query.message.edit_text("❌ Недостаточно средств.")
        await query.answer()
        return

    result_emoji = EMOJI_WIN if win else EMOJI_LOSE
    result_word = "Победа" if win else "Поражение"

    await query.message.edit_text(
        f"{result_emoji} <b>Рулетка</b>\n"
        f"<blockquote>"
        f"🎡 Итог: <b>{outcome_text}</b>\n"
        f"🎯 Твой выбор: <b>{choice}</b>\n"
        f"▶️ Результат: <b>{result_word}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(balance)}</b>"
        f"</blockquote>"
    )
    await query.answer()# ==================== CRASH ====================

def crash_roll() -> float:
    """Краш с распределением: 1-4x (60%), 4-15x (30%), 15-100x (10%)"""
    r = random.random()
    if r < 0.60:
        return round(random.uniform(1.0, 4.0), 2)
    elif r < 0.90:
        return round(random.uniform(4.01, 15.0), 2)
    else:
        return round(random.uniform(15.01, 100.0), 2)

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("краш"))
async def crash_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().split()
    if len(parts) < 3:
        await state.clear()
        await state.set_state(CrashStates.waiting_amount)
        await message.answer("📈 <b>Краш</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try:
        bet = parse_bet_legacy(parts[1], balance)
        target = float(parts[2].replace(",", "."))
    except Exception:
        await state.clear()
        await state.set_state(CrashStates.waiting_amount)
        await message.answer("Неверный формат. Введи сумму:")
        return

    if bet < MIN_BET:
        await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        return
    if target < 1.01 or target > 100:
        await message.answer("Множитель: 1.01 – 100")
        return

    crash = crash_roll()
    win = crash >= target
    payout = round(bet * target, 2) if win else 0.0
    ok, new_balance = settle_instant_bet(user_id, float(bet), payout, f"crash:{target}", f"x={crash}")
    if not ok:
        await message.answer("❌ Недостаточно средств.")
        return

    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Краш</b>\n"
        f"<blockquote>📈 Множитель: <b>x{crash:.2f}</b>\n"
        f"🎯 Цель: <b>x{target:.2f}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(new_balance)}</b></blockquote>"
    )

@dp.message(CrashStates.waiting_amount)
async def crash_amount(message: Message, state: FSMContext):
    try:
        bet = parse_amount(message.text)
    except Exception:
        await message.answer("Введи корректную ставку.")
        return
    if bet < MIN_BET:
        await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        return
    await state.update_data(bet=bet)
    await state.set_state(CrashStates.waiting_target)
    await message.answer("🎯 Введи множитель (1.01 – 100):")

@dp.message(CrashStates.waiting_target)
async def crash_target(message: Message, state: FSMContext):
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    try:
        target = parse_amount(message.text)
    except Exception:
        await message.answer("Введи число, например 2.5")
        return
    if target < 1.01 or target > 100:
        await message.answer("Множитель: 1.01 – 100")
        return

    crash = crash_roll()
    win = target <= crash
    payout = round(bet * target, 2) if win else 0.0
    ok, balance = settle_instant_bet(message.from_user.id, bet, payout, f"crash:{target}", f"x={crash}")
    await state.clear()
    if not ok:
        await message.answer("❌ Недостаточно средств.")
        return

    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Краш</b>\n"
        f"<blockquote>📈 Множитель: <b>x{crash:.2f}</b>\n"
        f"🎯 Цель: <b>x{target:.2f}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )

# ==================== CUBE ====================

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("кубик"))
async def cube_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 3:
        await state.clear()
        await state.set_state(CubeStates.waiting_amount)
        await message.answer("🎲 <b>Кубик</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try:
        bet = parse_bet_legacy(parts[1], balance)
    except Exception:
        await state.clear()
        await state.set_state(CubeStates.waiting_amount)
        await message.answer("Неверная ставка. Введи сумму:")
        return
    if bet < MIN_BET:
        await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        return

    bet_type = parts[2]
    valid = {"1", "2", "3", "4", "5", "6", "чет", "нечет", "б", "м"}
    if bet_type not in valid:
        await state.update_data(bet=float(bet))
        await state.set_state(CubeStates.waiting_guess)
        await message.answer("Угадай: 1-6 / чет / нечет / б / м")
        return

    dice_msg = await message.answer_dice(emoji="🎲")
    number = int(dice_msg.dice.value)
    win, mult = False, 0.0
    if bet_type == str(number): win, mult = True, 3.5
    elif bet_type == "чет" and number % 2 == 0: win, mult = True, 1.9
    elif bet_type == "нечет" and number % 2 == 1: win, mult = True, 1.9
    elif bet_type == "б" and number >= 4: win, mult = True, 1.9
    elif bet_type == "м" and number <= 3: win, mult = True, 1.9

    payout = round(bet * mult, 2) if win else 0.0
    ok, new_balance = settle_instant_bet(user_id, float(bet), payout, f"cube:{bet_type}", f"num={number}")
    if not ok: await message.answer("❌ Недостаточно средств."); return

    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    ml = "меньше" if number <= 3 else "больше"
    pr = "чет" if number % 2 == 0 else "нечет"
    await message.answer(
        f"{em} <b>Кубик</b>\n"
        f"<blockquote>🎲 Выпало: <b>{number}</b> ({ml}, {pr})\n"
        f"🎯 Выбор: <b>{bet_type}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(new_balance)}</b></blockquote>"
    )

@dp.message(CubeStates.waiting_amount)
async def cube_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    await state.update_data(bet=bet)
    await state.set_state(CubeStates.waiting_guess)
    await message.answer("🎯 Угадай: 1-6, чет, нечет, б, м")

@dp.message(CubeStates.waiting_guess)
async def cube_guess(message: Message, state: FSMContext):
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    guess = normalize_text(message.text)
    try:
        g = int(guess)
        if 1 <= g <= 6:
            dice_msg = await message.answer_dice(emoji="🎲")
            rolled = int(dice_msg.dice.value)
            win = g == rolled
            payout = round(bet * 5.8, 2) if win else 0.0
            ok, balance = settle_instant_bet(message.from_user.id, bet, payout, f"cube:{g}", f"rolled={rolled}")
            await state.clear()
            if not ok: await message.answer("❌ Недостаточно средств."); return
            em = EMOJI_WIN if win else EMOJI_LOSE
            rw = "Победа" if win else "Поражение"
            await message.answer(
                f"{em} <b>Кубик</b>\n"
                f"<blockquote>🎲 Выпало: <b>{rolled}</b>\n🎯 Выбор: <b>{g}</b>\n"
                f"▶️ Результат: <b>{rw}</b>\n🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
            )
            return
    except Exception: pass

    bet_type = guess
    mapping = {"even": "чет", "odd": "нечет", "больше": "б", "меньше": "м"}
    bet_type = mapping.get(bet_type, bet_type)
    if bet_type not in {"чет", "нечет", "б", "м"}: await message.answer("Неверно."); return

    dice_msg = await message.answer_dice(emoji="🎲")
    rolled = int(dice_msg.dice.value)
    win, mult = False, 0.0
    if bet_type == "чет" and rolled % 2 == 0: win, mult = True, 1.9
    elif bet_type == "нечет" and rolled % 2 == 1: win, mult = True, 1.9
    elif bet_type == "б" and rolled >= 4: win, mult = True, 1.9
    elif bet_type == "м" and rolled <= 3: win, mult = True, 1.9

    payout = round(bet * mult, 2) if win else 0.0
    ok, balance = settle_instant_bet(message.from_user.id, bet, payout, f"cube:{bet_type}", f"rolled={rolled}")
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Кубик</b>\n"
        f"<blockquote>🎲 Выпало: <b>{rolled}</b>\n🎯 Выбор: <b>{bet_type}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )

# ==================== DICE ====================

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("кости"))
async def dice_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 3:
        await state.clear()
        await state.set_state(DiceStates.waiting_amount)
        await message.answer("🎯 <b>Кости</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try: bet = parse_bet_legacy(parts[1], balance)
    except Exception: await state.clear(); await state.set_state(DiceStates.waiting_amount); await message.answer("Неверная ставка."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return

    choice = parts[2]
    mapping = {"м": "меньше", "б": "больше", "7": "семь", "семь": "семь", "равно": "семь"}
    choice = mapping.get(choice, choice)
    if choice not in {"больше", "меньше", "семь"}:
        await state.update_data(bet=float(bet))
        await state.set_state(DiceStates.waiting_guess)
        await message.answer("Выбери: больше / меньше / семь")
        return

    d1_msg = await message.answer_dice(emoji="🎲")
    d2_msg = await message.answer_dice(emoji="🎲")
    d1, d2 = int(d1_msg.dice.value), int(d2_msg.dice.value)
    total = d1 + d2
    win, mult = False, 0.0
    if choice == "больше" and total > 7: win, mult = True, 2.25
    elif choice == "меньше" and total < 7: win, mult = True, 2.25
    elif choice == "семь" and total == 7: win, mult = True, 5.0

    payout = round(bet * mult, 2) if win else 0.0
    ok, new_balance = settle_instant_bet(user_id, float(bet), payout, f"dice:{choice}", f"{d1}+{d2}={total}")
    if not ok: await message.answer("❌ Недостаточно средств."); return

    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    rel = "меньше 7" if total < 7 else ("больше 7" if total > 7 else "равно 7")
    await message.answer(
        f"{em} <b>Кости</b>\n"
        f"<blockquote>🎯 Итог: <b>{d1}</b> + <b>{d2}</b> = <b>{total}</b> ({rel})\n"
        f"🎯 Выбор: <b>{choice}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(new_balance)}</b></blockquote>"
    )

@dp.message(DiceStates.waiting_amount)
async def dice_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    await state.update_data(bet=bet)
    await state.set_state(DiceStates.waiting_guess)
    await message.answer("🎯 Исход: больше / меньше / семь")

@dp.message(DiceStates.waiting_guess)
async def dice_guess(message: Message, state: FSMContext):
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    guess = normalize_text(message.text)
    mapping = {"м": "меньше", "б": "больше", "7": "семь", "семь": "семь", "равно": "семь"}
    guess = mapping.get(guess, guess)
    if guess not in {"больше", "меньше", "семь"}: await message.answer("Неверно."); return

    d1_msg = await message.answer_dice(emoji="🎲")
    d2_msg = await message.answer_dice(emoji="🎲")
    d1, d2 = int(d1_msg.dice.value), int(d2_msg.dice.value)
    total = d1 + d2
    win, mult = False, 0.0
    if guess == "больше" and total > 7: win, mult = True, 1.9
    elif guess == "меньше" and total < 7: win, mult = True, 1.9
    elif guess in {"семь", "7"} and total == 7: win, mult = True, 5.0

    payout = round(bet * mult, 2) if win else 0.0
    ok, balance = settle_instant_bet(message.from_user.id, bet, payout, f"dice:{guess}", f"{d1}+{d2}={total}")
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    rel = "меньше 7" if total < 7 else ("больше 7" if total > 7 else "равно 7")
    await message.answer(
        f"{em} <b>Кости</b>\n"
        f"<blockquote>🎯 Итог: <b>{d1}</b> + <b>{d2}</b> = <b>{total}</b> ({rel})\n"
        f"🎯 Выбор: <b>{guess}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n"
        f"⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )

# ==================== FOOTBALL ====================

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("футбол"))
async def football_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear()
        await state.set_state(FootballStates.waiting_amount)
        await message.answer("⚽ <b>Футбол</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try: bet = parse_bet_legacy(parts[1], balance)
    except Exception: await state.clear(); await state.set_state(FootballStates.waiting_amount); await message.answer("Неверная ставка."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return

    choice = None
    if len(parts) >= 3:
        c = parts[2]
        if c in {"гол", "gol", "goal"}: choice = "gol"
        elif c in {"мимо", "mimo", "miss"}: choice = "mimo"

    if choice:
        dice_msg = await message.answer_dice(emoji="⚽")
        await asyncio.sleep(3)
        outcome = "mimo" if int(dice_msg.dice.value) <= 2 else "gol"
        win = outcome == choice
        payout = round(bet * FOOTBALL_MULTIPLIERS[choice], 2) if win else 0.0
        ok, new_balance = settle_instant_bet(user_id, float(bet), payout, f"football:{choice}", f"{outcome}")
        if not ok: await message.answer("❌ Недостаточно средств."); return
        em = EMOJI_WIN if win else EMOJI_LOSE
        rw = "Победа" if win else "Поражение"
        await message.answer(
            f"{em} <b>Футбол</b>\n"
            f"<blockquote>⚽ Итог: <b>{'Гол' if outcome == 'gol' else 'Мимо'}</b>\n"
            f"🎯 Выбор: <b>{'Гол' if choice == 'gol' else 'Мимо'}</b>\n"
            f"▶️ Результат: <b>{rw}</b>\n"
            f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(new_balance)}</b></blockquote>"
        )
        return

    ok, _ = reserve_bet(user_id, float(bet))
    if not ok: await message.answer("❌ Недостаточно средств."); return
    NFOOTBALL_GAMES[user_id] = {"bet": int(bet)}
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⚽ Гол x{FOOTBALL_MULTIPLIERS['gol']}", callback_data="nfoot:play:gol")],
        [InlineKeyboardButton(text=f"💨 Мимо x{FOOTBALL_MULTIPLIERS['mimo']}", callback_data="nfoot:play:mimo")],
        [InlineKeyboardButton(text="Отмена", callback_data="nfoot:cancel")],
    ])
    await message.answer(f"⚽ <b>Футбол</b>\nСтавка: <b>{fmt_money(bet)}</b>\nВыбери исход:", reply_markup=kb)

@dp.message(FootballStates.waiting_amount)
async def football_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    dice_msg = await message.answer_dice(emoji="⚽")
    value = int(dice_msg.dice.value)
    win = value >= 4
    payout = round(bet * 1.85, 2) if win else 0.0
    balance = finalize_reserved_bet(message.from_user.id, bet, payout, "football", f"val={value}")
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Футбол</b>\n"
        f"<blockquote>⚽ Итог: <b>{football_value_text(value)}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )

@dp.callback_query(F.data == "nfoot:cancel")
async def football_cancel(query: CallbackQuery):
    user_id = query.from_user.id
    s = NFOOTBALL_GAMES.pop(user_id, None)
    if not s: return await query.answer("Нет игры.", show_alert=True)
    balance = add_balance(user_id, s["bet"])
    await query.message.edit_text(f"🛑 Отменено. Возврат: <b>{fmt_money(s['bet'])}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

@dp.callback_query(F.data.startswith("nfoot:play:"))
async def football_play(query: CallbackQuery):
    user_id = query.from_user.id
    s = NFOOTBALL_GAMES.get(user_id)
    if not s: return await query.answer("Нет игры.", show_alert=True)
    choice = query.data.split(":")[-1]
    if choice not in {"gol", "mimo"}: return await query.answer("Ошибка.", show_alert=True)
    try: await query.message.edit_reply_markup(None)
    except Exception: pass
    dice_msg = await query.message.answer_dice(emoji="⚽")
    await asyncio.sleep(3)
    outcome = "mimo" if int(dice_msg.dice.value) <= 2 else "gol"
    win = outcome == choice
    payout = round(s["bet"] * FOOTBALL_MULTIPLIERS[choice], 2) if win else 0.0
    balance = finalize_reserved_bet(user_id, float(s["bet"]), payout, f"football:{choice}", f"{outcome}")
    NFOOTBALL_GAMES.pop(user_id, None)
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await query.message.answer(
        f"{em} <b>Футбол</b>\n"
        f"<blockquote>⚽ Итог: <b>{'Гол' if outcome == 'gol' else 'Мимо'}</b>\n"
        f"🎯 Выбор: <b>{'Гол' if choice == 'gol' else 'Мимо'}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )
    await query.answer()

# ==================== BASKET ====================

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith(("баскет", "баскетбол")))
async def basket_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await state.clear()
        await state.set_state(BasketStates.waiting_amount)
        await message.answer("🏀 <b>Баскетбол</b>\nВведи сумму ставки:")
        return

    user_id = message.from_user.id
    balance = float(get_user(user_id)["coins"] or 0)
    try: bet = parse_bet_legacy(parts[1], balance)
    except Exception: await state.clear(); await state.set_state(BasketStates.waiting_amount); await message.answer("Неверная ставка."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return

    roll = await message.answer_dice(emoji="🏀")
    value = int(roll.dice.value)
    win = value in {4, 5}
    payout = round(bet * 2.2, 2) if win else 0.0
    ok, new_balance = settle_instant_bet(user_id, float(bet), payout, "basketball", f"val={value}")
    if not ok: await message.answer("❌ Недостаточно средств."); return
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Баскетбол</b>\n"
        f"<blockquote>🏀 Итог: <b>{basketball_value_text(value)}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(new_balance)}</b></blockquote>"
    )

@dp.message(BasketStates.waiting_amount)
async def basket_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    dice_msg = await message.answer_dice(emoji="🏀")
    value = int(dice_msg.dice.value)
    win = value >= 4
    payout = round(bet * 1.85, 2) if win else 0.0
    balance = finalize_reserved_bet(message.from_user.id, bet, payout, "basket", f"val={value}")
    em = EMOJI_WIN if win else EMOJI_LOSE
    rw = "Победа" if win else "Поражение"
    await message.answer(
        f"{em} <b>Баскетбол</b>\n"
        f"<blockquote>🏀 Итог: <b>{basketball_value_text(value)}</b>\n"
        f"▶️ Результат: <b>{rw}</b>\n"
        f"🔄 Выплата: <b>{fmt_money(payout)}</b>\n⭐️ Баланс: <b>{fmt_money(balance)}</b></blockquote>"
    )

# ==================== TOWER ====================

def tower_text(game: Dict[str, Any]) -> str:
    level, bet = int(game["level"]), float(game["bet"])
    cm = TOWER_MULTIPLIERS[level - 1] if level > 0 else 0
    cw = bet * cm if level > 0 else 0
    nm = TOWER_MULTIPLIERS[level] if level < len(TOWER_MULTIPLIERS) else TOWER_MULTIPLIERS[-1]
    return f"🗼 <b>Башня</b>\nСтавка: <b>{fmt_money(bet)}</b>\nЭтаж: <b>{level}</b>\nМножитель: <b>x{cm:.2f}</b>\nСейчас: <b>{fmt_money(cw)}</b>\nСледующий: <b>x{nm:.2f}</b>\n\nВыбери секцию 1-3."

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("башня"))
async def tower_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear(); await state.set_state(TowerStates.waiting_amount)
        await message.answer("🗼 <b>Башня</b>\nВведи сумму ставки:"); return
    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in TOWER_GAMES: return await message.answer("Уже есть активная башня.")
        balance = float(get_user(user_id)["coins"] or 0)
        try: bet = parse_bet_legacy(parts[1], balance)
        except Exception: return await message.answer("Неверная ставка.")
        if bet < MIN_BET: return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        ok, _ = reserve_bet(user_id, float(bet))
        if not ok: return await message.answer("❌ Недостаточно средств.")
        TOWER_GAMES[user_id] = {"bet": bet, "level": 0}
        await message.answer(tower_text(TOWER_GAMES[user_id]), reply_markup=tower_kb())

@dp.message(TowerStates.waiting_amount)
async def tower_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    TOWER_GAMES[message.from_user.id] = {"bet": bet, "level": 0}
    await message.answer(tower_text(TOWER_GAMES[message.from_user.id]), reply_markup=tower_kb())

@dp.callback_query(F.data.startswith("tower:pick:"))
async def tower_pick(query: CallbackQuery):
    user_id = query.from_user.id
    game = TOWER_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    chosen = int(query.data.split(":")[-1])
    safe = random.randint(1, 3)
    if chosen != safe:
        bet = float(game["bet"])
        balance = finalize_reserved_bet(user_id, bet, 0.0, "tower", "lose")
        TOWER_GAMES.pop(user_id, None)
        await query.message.edit_text(f"💥 Ловушка в <b>{safe}</b>, ты выбрал <b>{chosen}</b>.\nПотеряно: <b>{fmt_money(bet)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    game["level"] += 1
    level = int(game["level"])
    if level >= len(TOWER_MULTIPLIERS):
        bet = float(game["bet"]); payout = round(bet * TOWER_MULTIPLIERS[-1], 2)
        balance = finalize_reserved_bet(user_id, bet, payout, "tower", "max")
        TOWER_GAMES.pop(user_id, None)
        await query.message.edit_text(f"🏁 Вершина!\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    await query.message.edit_text(tower_text(game), reply_markup=tower_kb())
    await query.answer("Успех!")

@dp.callback_query(F.data == "tower:cash")
async def tower_cash(query: CallbackQuery):
    user_id = query.from_user.id
    game = TOWER_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    level, bet = int(game["level"]), float(game["bet"])
    if level <= 0: return await query.answer("Сделай ход.", show_alert=True)
    mult = TOWER_MULTIPLIERS[level - 1]; payout = round(bet * mult, 2)
    balance = finalize_reserved_bet(user_id, bet, payout, "tower", f"cashout_{level}")
    TOWER_GAMES.pop(user_id, None)
    await query.message.edit_text(f"✅ Забрано!\nЭтаж: <b>{level}</b>\nМножитель: <b>x{mult:.2f}</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

@dp.callback_query(F.data == "tower:cancel")
async def tower_cancel(query: CallbackQuery):
    user_id = query.from_user.id
    game = TOWER_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    level, bet = int(game["level"]), float(game["bet"])
    payout = bet if level == 0 else 0.0; outcome = "cancel_refund" if level == 0 else "cancel_lose"
    balance = finalize_reserved_bet(user_id, bet, payout, "tower", outcome)
    TOWER_GAMES.pop(user_id, None)
    await query.message.edit_text(f"❌ Завершено.\nВозврат: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

# ==================== GOLD ====================

def gold_text(game: Dict[str, Any]) -> str:
    step, bet = int(game["step"]), float(game["bet"])
    cm = GOLD_MULTIPLIERS[step - 1] if step > 0 else 0
    cw = bet * cm if step > 0 else 0
    nm = GOLD_MULTIPLIERS[step] if step < len(GOLD_MULTIPLIERS) else GOLD_MULTIPLIERS[-1]
    return f"🥇 <b>Золото</b>\nСтавка: <b>{fmt_money(bet)}</b>\nРаунд: <b>{step}</b>\nМножитель: <b>x{cm:.2f}</b>\nСейчас: <b>{fmt_money(cw)}</b>\nСледующий: <b>x{nm:.2f}</b>\n\nВыбери плитку (1-4)."

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("золото"))
async def gold_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear(); await state.set_state(GoldStates.waiting_amount)
        await message.answer("🥇 <b>Золото</b>\nВведи сумму ставки:"); return
    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in GOLD_GAMES: return await message.answer("Уже есть активное золото.")
        balance = float(get_user(user_id)["coins"] or 0)
        try: bet = parse_bet_legacy(parts[1], balance)
        except Exception: return await message.answer("Неверная ставка.")
        if bet < MIN_BET: return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        ok, _ = reserve_bet(user_id, float(bet))
        if not ok: return await message.answer("❌ Недостаточно средств.")
        GOLD_GAMES[user_id] = {"bet": bet, "step": 0}
        await message.answer(gold_text(GOLD_GAMES[user_id]), reply_markup=gold_kb())

@dp.message(GoldStates.waiting_amount)
async def gold_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    GOLD_GAMES[message.from_user.id] = {"bet": bet, "step": 0}
    await message.answer(gold_text(GOLD_GAMES[message.from_user.id]), reply_markup=gold_kb())

@dp.callback_query(F.data.startswith("gold:pick:"))
async def gold_pick(query: CallbackQuery):
    user_id = query.from_user.id
    game = GOLD_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    chosen, trap = int(query.data.split(":")[-1]), random.randint(1, 4)
    if chosen == trap:
        bet = float(game["bet"]); balance = finalize_reserved_bet(user_id, bet, 0.0, "gold", "lose")
        GOLD_GAMES.pop(user_id, None)
        await query.message.edit_text(f"💥 Ловушка в <b>{trap}</b>.\nПотеряно: <b>{fmt_money(bet)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    game["step"] += 1
    step = int(game["step"])
    if step >= len(GOLD_MULTIPLIERS):
        bet = float(game["bet"]); payout = round(bet * GOLD_MULTIPLIERS[-1], 2)
        balance = finalize_reserved_bet(user_id, bet, payout, "gold", "max")
        GOLD_GAMES.pop(user_id, None)
        await query.message.edit_text(f"🏁 Всё пройдено!\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    await query.message.edit_text(gold_text(game), reply_markup=gold_kb())
    await query.answer("Успех!")

@dp.callback_query(F.data == "gold:cash")
async def gold_cash(query: CallbackQuery):
    user_id = query.from_user.id
    game = GOLD_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    step, bet = int(game["step"]), float(game["bet"])
    if step <= 0: return await query.answer("Сделай ход.", show_alert=True)
    mult = GOLD_MULTIPLIERS[step - 1]; payout = round(bet * mult, 2)
    balance = finalize_reserved_bet(user_id, bet, payout, "gold", f"cashout_{step}")
    GOLD_GAMES.pop(user_id, None)
    await query.message.edit_text(f"✅ Забрано!\nРаунд: <b>{step}</b>\nМножитель: <b>x{mult:.2f}</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

@dp.callback_query(F.data == "gold:cancel")
async def gold_cancel(query: CallbackQuery):
    user_id = query.from_user.id
    game = GOLD_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    step, bet = int(game["step"]), float(game["bet"])
    payout = bet if step == 0 else 0.0; outcome = "cancel_refund" if step == 0 else "cancel_lose"
    balance = finalize_reserved_bet(user_id, bet, payout, "gold", outcome)
    GOLD_GAMES.pop(user_id, None)
    await query.message.edit_text(f"❌ Завершено.\nВозврат: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()# ==================== DIAMONDS ====================

def diamond_text(game: Dict[str, Any]) -> str:
    step, bet = int(game["step"]), float(game["bet"])
    cm = DIAMOND_MULTIPLIERS[step - 1] if step > 0 else 0
    cw = bet * cm if step > 0 else 0
    nm = DIAMOND_MULTIPLIERS[step] if step < len(DIAMOND_MULTIPLIERS) else DIAMOND_MULTIPLIERS[-1]
    return f"💍 <b>Алмазы</b>\nСтавка: <b>{fmt_money(bet)}</b>\nШаг: <b>{step}</b>\nМножитель: <b>x{cm:.2f}</b>\nСейчас: <b>{fmt_money(cw)}</b>\nСледующий: <b>x{nm:.2f}</b>\n\nВыбери кристалл (1-5)."

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("алмазы"))
async def diamonds_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear(); await state.set_state(DiamondStates.waiting_amount)
        await message.answer("💍 <b>Алмазы</b>\nВведи сумму ставки:"); return
    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in DIAMOND_GAMES: return await message.answer("Уже есть активные алмазы.")
        balance = float(get_user(user_id)["coins"] or 0)
        try: bet = parse_bet_legacy(parts[1], balance)
        except Exception: return await message.answer("Неверная ставка.")
        if bet < MIN_BET: return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        ok, _ = reserve_bet(user_id, float(bet))
        if not ok: return await message.answer("❌ Недостаточно средств.")
        DIAMOND_GAMES[user_id] = {"bet": bet, "step": 0}
        await message.answer(diamond_text(DIAMOND_GAMES[user_id]), reply_markup=diamond_kb())

@dp.message(DiamondStates.waiting_amount)
async def diamond_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return
    DIAMOND_GAMES[message.from_user.id] = {"bet": bet, "step": 0}
    await message.answer(diamond_text(DIAMOND_GAMES[message.from_user.id]), reply_markup=diamond_kb())

@dp.callback_query(F.data.startswith("diamond:pick:"))
async def diamond_pick(query: CallbackQuery):
    user_id = query.from_user.id
    game = DIAMOND_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    chosen, trap = int(query.data.split(":")[-1]), random.randint(1, 5)
    if chosen == trap:
        bet = float(game["bet"]); balance = finalize_reserved_bet(user_id, bet, 0.0, "diamonds", "lose")
        DIAMOND_GAMES.pop(user_id, None)
        await query.message.edit_text(f"💥 Бракованный кристалл <b>{trap}</b>.\nПотеряно: <b>{fmt_money(bet)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    game["step"] += 1
    step = int(game["step"])
    if step >= len(DIAMOND_MULTIPLIERS):
        bet = float(game["bet"]); payout = round(bet * DIAMOND_MULTIPLIERS[-1], 2)
        balance = finalize_reserved_bet(user_id, bet, payout, "diamonds", "max")
        DIAMOND_GAMES.pop(user_id, None)
        await query.message.edit_text(f"🏁 Максимум шагов!\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    await query.message.edit_text(diamond_text(game), reply_markup=diamond_kb())
    await query.answer("Успех!")

@dp.callback_query(F.data == "diamond:cash")
async def diamond_cash(query: CallbackQuery):
    user_id = query.from_user.id
    game = DIAMOND_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    step, bet = int(game["step"]), float(game["bet"])
    if step <= 0: return await query.answer("Сделай шаг.", show_alert=True)
    mult = DIAMOND_MULTIPLIERS[step - 1]; payout = round(bet * mult, 2)
    balance = finalize_reserved_bet(user_id, bet, payout, "diamonds", f"cashout_{step}")
    DIAMOND_GAMES.pop(user_id, None)
    await query.message.edit_text(f"✅ Забрано!\nШаг: <b>{step}</b>\nМножитель: <b>x{mult:.2f}</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

@dp.callback_query(F.data == "diamond:cancel")
async def diamond_cancel(query: CallbackQuery):
    user_id = query.from_user.id
    game = DIAMOND_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    step, bet = int(game["step"]), float(game["bet"])
    payout = bet if step == 0 else 0.0; outcome = "cancel_refund" if step == 0 else "cancel_lose"
    balance = finalize_reserved_bet(user_id, bet, payout, "diamonds", outcome)
    DIAMOND_GAMES.pop(user_id, None)
    await query.message.edit_text(f"❌ Завершено.\nВозврат: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

# ==================== MINES 5×5 (до 24 мин) ====================

def mines_text_5x5(game: Dict[str, Any]) -> str:
    bet = float(game["bet"])
    opened_count = len(game["opened"])
    mines_count = int(game["mines_count"])
    mult = mines_multiplier(opened_count, mines_count, 25)
    potential = round(bet * mult, 2)
    return (
        f"💣 <b>Мины 5×5</b>\n"
        f"<blockquote>📊 Ставка: <b>{fmt_money(bet)}</b>\n"
        f"💣 Мин: <b>{mines_count}</b>\n"
        f"✅ Открыто: <b>{opened_count}</b>\n"
        f"📈 Множитель: <b>x{mult:.2f}</b>\n"
        f"💰 Потенциал: <b>{fmt_money(potential)}</b></blockquote>\n\n"
        f"<i>Открывай клетки или забирай выигрыш.</i>"
    )

def mines_kb_5x5(game: Dict[str, Any], reveal_all: bool = False) -> InlineKeyboardMarkup:
    opened = set(game["opened"])
    mines_set = set(game["mines"])
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            idx = r * 5 + c + 1
            if idx in opened: text, cb = "✅", "mines:noop"
            elif reveal_all and idx in mines_set: text, cb = "💣", "mines:noop"
            else: text, cb = str(idx), f"mines:cell:{idx}"
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="💰 Забрать", callback_data="mines:cash"),
        InlineKeyboardButton(text="❌ Сдаться", callback_data="mines:cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("мины"))
async def mines_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear(); await state.set_state(MinesStates.waiting_amount)
        await message.answer("💣 <b>Мины 5×5</b>\nВведи сумму ставки:"); return

    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in MINES_GAMES: return await message.answer("Уже есть активные мины.")
        balance = float(get_user(user_id)["coins"] or 0)
        try: bet = parse_bet_legacy(parts[1], balance)
        except Exception: return await message.answer("Неверная ставка.")
        mines_count = 3
        if len(parts) >= 3:
            try: mines_count = int(parts[2])
            except Exception: mines_count = 3
        if not (1 <= mines_count <= 24): return await message.answer("Мин: 1-24.")
        if bet < MIN_BET: return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        ok, _ = reserve_bet(user_id, float(bet))
        if not ok: return await message.answer("❌ Недостаточно средств.")

        cells = list(range(1, 26))
        mines_positions = set(random.sample(cells, mines_count))
        MINES_GAMES[user_id] = {"bet": bet, "mines_count": mines_count, "mines": mines_positions, "opened": set()}
        game = MINES_GAMES[user_id]
        await message.answer(mines_text_5x5(game), reply_markup=mines_kb_5x5(game))

@dp.message(MinesStates.waiting_amount)
async def mines_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    await state.update_data(bet=bet)
    await state.set_state(MinesStates.waiting_mines)
    await message.answer("💣 Сколько мин? (1-24):")

@dp.message(MinesStates.waiting_mines)
async def mines_count_input(message: Message, state: FSMContext):
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    try: mines_count = parse_int(message.text)
    except Exception: await message.answer("Введи число 1-24."); return
    if not (1 <= mines_count <= 24): await message.answer("Мин: 1-24."); return
    ok, _ = reserve_bet(message.from_user.id, bet)
    await state.clear()
    if not ok: await message.answer("❌ Недостаточно средств."); return

    cells = list(range(1, 26))
    mines_positions = set(random.sample(cells, mines_count))
    MINES_GAMES[message.from_user.id] = {"bet": bet, "mines_count": mines_count, "mines": mines_positions, "opened": set()}
    game = MINES_GAMES[message.from_user.id]
    await message.answer(mines_text_5x5(game), reply_markup=mines_kb_5x5(game))

@dp.callback_query(F.data == "mines:noop")
async def mines_noop(query: CallbackQuery):
    await query.answer()

@dp.callback_query(F.data.startswith("mines:cell:"))
async def mines_cell(query: CallbackQuery):
    user_id = query.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    idx = int(query.data.split(":")[-1])
    if idx in game["opened"]: return await query.answer("Уже открыта.", show_alert=True)

    if idx in game["mines"]:
        bet = float(game["bet"])
        balance = finalize_reserved_bet(user_id, bet, 0.0, "mines", "explode")
        await query.message.edit_text(
            f"💥 <b>Мины</b>\n<blockquote>Мина в клетке <b>{idx}</b>.\nПотеряно: <b>{fmt_money(bet)}</b>\nБаланс: <b>{fmt_money(balance)}</b></blockquote>",
            reply_markup=mines_kb_5x5(game, reveal_all=True)
        )
        MINES_GAMES.pop(user_id, None)
        await query.answer(); return

    game["opened"].add(idx)
    safe_opened = len(game["opened"])
    safe_total = 25 - int(game["mines_count"])

    if safe_opened >= safe_total:
        bet = float(game["bet"])
        mult = mines_multiplier(safe_opened, int(game["mines_count"]), 25)
        payout = round(bet * mult, 2)
        balance = finalize_reserved_bet(user_id, bet, payout, "mines", "cleared_all")
        await query.message.edit_text(
            f"🏁 <b>Мины</b>\n<blockquote>Все безопасные открыты!\nМножитель: <b>x{mult:.2f}</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b></blockquote>",
            reply_markup=mines_kb_5x5(game, reveal_all=True)
        )
        MINES_GAMES.pop(user_id, None)
        await query.answer(); return

    await query.message.edit_text(mines_text_5x5(game), reply_markup=mines_kb_5x5(game))
    await query.answer("✅ Безопасно!")

@dp.callback_query(F.data == "mines:cash")
async def mines_cash(query: CallbackQuery):
    user_id = query.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    bet = float(game["bet"])
    safe_opened = len(game["opened"])
    mines_count = int(game["mines_count"])
    if safe_opened <= 0: return await query.answer("Открой хотя бы 1 клетку.", show_alert=True)

    mult = mines_multiplier(safe_opened, mines_count, 25)
    payout = round(bet * mult, 2)
    balance = finalize_reserved_bet(user_id, bet, payout, "mines", f"cashout_{safe_opened}")
    await query.message.edit_text(
        f"✅ <b>Мины</b>\n<blockquote>Открыто: <b>{safe_opened}</b>\nМножитель: <b>x{mult:.2f}</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b></blockquote>",
        reply_markup=mines_kb_5x5(game, reveal_all=True)
    )
    MINES_GAMES.pop(user_id, None)
    await query.answer()

@dp.callback_query(F.data == "mines:cancel")
async def mines_cancel(query: CallbackQuery):
    user_id = query.from_user.id
    game = MINES_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    bet = float(game["bet"])
    safe_opened = len(game["opened"])
    mines_count = int(game["mines_count"])

    if safe_opened <= 0:
        payout, outcome = bet, "cancel_refund"
    else:
        payout = round(bet * mines_multiplier(safe_opened, mines_count, 25), 2)
        outcome = f"cancel_cashout_{safe_opened}"

    balance = finalize_reserved_bet(user_id, bet, payout, "mines", outcome)
    await query.message.edit_text(
        f"❌ <b>Мины завершены</b>\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>",
        reply_markup=mines_kb_5x5(game, reveal_all=True)
    )
    MINES_GAMES.pop(user_id, None)
    await query.answer()

# ==================== OCHKO (BLACKJACK) ====================

def render_ochko(game: Dict[str, Any], reveal_dealer: bool) -> str:
    pc, dc = game["player"], game["dealer"]
    if reveal_dealer: dl = f"{format_hand(dc)} ({hand_value(dc)})"
    else: dl = f"{dc[0][0]}{dc[0][1]} ??"
    return f"🎴 <b>Очко</b>\n💰 Ставка: <b>{fmt_money(game['bet'])}</b>\n\n🃏 Дилер: {dl}\n🃏 Ты: {format_hand(pc)} ({hand_value(pc)})"

@dp.message(StateFilter(None), lambda m: (m.text or "").lower().startswith("очко"))
async def ochko_start(message: Message, state: FSMContext):
    parts = (message.text or "").strip().lower().split()
    if len(parts) < 2:
        await state.clear(); await state.set_state(OchkoStates.waiting_amount)
        await message.answer("🎴 <b>Очко</b>\nВведи сумму ставки:"); return
    user_id = message.from_user.id
    async with _game_lock(user_id):
        if user_id in OCHKO_GAMES: return await message.answer("Уже есть активное очко.")
        balance = float(get_user(user_id)["coins"] or 0)
        try: bet = parse_bet_legacy(parts[1], balance)
        except Exception: return await message.answer("Неверная ставка.")
        if bet < MIN_BET: return await message.answer(f"Минимум: {fmt_money(MIN_BET)}")
        await state.clear(); await state.update_data(bet=float(bet))
        await state.set_state(OchkoStates.waiting_confirm)
        await message.answer(
            f"🎴 <b>Очко</b>\nСтавка: <b>{fmt_money(float(bet))}</b>\n\nНачать игру?",
            reply_markup=ochko_confirm_kb()
        )

@dp.message(OchkoStates.waiting_amount)
async def ochko_amount(message: Message, state: FSMContext):
    try: bet = parse_amount(message.text)
    except Exception: await message.answer("Введи ставку."); return
    if bet < MIN_BET: await message.answer(f"Минимум: {fmt_money(MIN_BET)}"); return
    await state.update_data(bet=bet)
    await state.set_state(OchkoStates.waiting_confirm)
    await message.answer(f"🎴 <b>Очко</b>\nСтавка: <b>{fmt_money(bet)}</b>\n\nНачать игру?", reply_markup=ochko_confirm_kb())

@dp.callback_query(OchkoStates.waiting_confirm, F.data == "ochko:cancel")
async def ochko_cancel_before(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("🛑 Игра отменена. Ставка не списана.")
    await query.answer()

@dp.callback_query(OchkoStates.waiting_confirm, F.data == "ochko:start")
async def ochko_start_confirm(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bet = float(data.get("bet", 0))
    if bet < MIN_BET: await state.clear(); await query.answer("Ошибка.", show_alert=True); return
    ok, _ = reserve_bet(query.from_user.id, bet)
    await state.clear()
    if not ok: await query.message.edit_text("❌ Недостаточно средств."); await query.answer(); return

    deck = make_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    OCHKO_GAMES[query.from_user.id] = {"bet": bet, "deck": deck, "player": player, "dealer": dealer}
    game = OCHKO_GAMES[query.from_user.id]

    if hand_value(player) == 21:
        if hand_value(dealer) == 21:
            payout = bet; outcome = "bj_push"; txt = "Ничья по Blackjack."
        else:
            payout = round(bet * 2.5, 2); outcome = "bj_win"; txt = "Blackjack! Победа!"
        balance = finalize_reserved_bet(query.from_user.id, bet, payout, "ochko", outcome)
        OCHKO_GAMES.pop(query.from_user.id, None)
        await query.message.edit_text(f"🎴 <b>Очко</b>\n\n{render_ochko(game, True)}\n\n{txt}\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return

    await query.message.edit_text(render_ochko(game, False), reply_markup=ochko_kb())
    await query.answer()

@dp.callback_query(F.data == "ochko:hit")
async def ochko_hit(query: CallbackQuery):
    user_id = query.from_user.id
    game = OCHKO_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    game["player"].append(game["deck"].pop())
    if hand_value(game["player"]) > 21:
        bet = float(game["bet"]); balance = finalize_reserved_bet(user_id, bet, 0.0, "ochko", "bust")
        OCHKO_GAMES.pop(user_id, None)
        await query.message.edit_text(f"🎴 <b>Очко</b>\n\n{render_ochko(game, True)}\n\n💥 Перебор! Поражение.\nБаланс: <b>{fmt_money(balance)}</b>")
        await query.answer(); return
    await query.message.edit_text(render_ochko(game, False), reply_markup=ochko_kb())
    await query.answer()

@dp.callback_query(F.data == "ochko:stand")
async def ochko_stand(query: CallbackQuery):
    user_id = query.from_user.id
    game = OCHKO_GAMES.get(user_id)
    if not game: return await query.answer("Нет игры.", show_alert=True)
    while hand_value(game["dealer"]) < 17: game["dealer"].append(game["deck"].pop())
    dv, pv = hand_value(game["dealer"]), hand_value(game["player"])
    bet = float(game["bet"])
    if dv > 21 or pv > dv: payout, txt, outcome = round(bet * 2.0, 2), "Победа!", "win"
    elif dv == pv: payout, txt, outcome = round(bet, 2), "Ничья.", "push"
    else: payout, txt, outcome = 0.0, "Поражение.", "lose"
    balance = finalize_reserved_bet(user_id, bet, payout, "ochko", outcome)
    OCHKO_GAMES.pop(user_id, None)
    await query.message.edit_text(f"🎴 <b>Очко</b>\n\n{render_ochko(game, True)}\n\n{txt}\nВыплата: <b>{fmt_money(payout)}</b>\nБаланс: <b>{fmt_money(balance)}</b>")
    await query.answer()

# ==================== ЗАПУСК ====================

async def main() -> None:
    init_db()
    bot = Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
