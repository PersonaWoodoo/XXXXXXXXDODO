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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Bot, Dispatcher, types, F
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
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    ChatMember,
)

# ==================== КОНФИГУРАЦИЯ ====================

BOT_TOKEN = "8365761672:AAFNA79Or2QnBVmHdOL465Rp0Ta89nF7DPA"
ADMIN_IDS = {8478884644}
BOT_USERNAME = "DodoCoin_bot"

# КАНАЛЫ И ЧАТЫ ДЛЯ ПОДПИСКИ
CHANNELS = [
    {"id": "@dodoCoin_news", "name": "📢 Новости казино", "url": "https://t.me/dodoCoin_news"},
    {"id": "@dodocoin_chat", "name": "💬 Общий чат", "url": "https://t.me/dodocoin_chat"},
]

# Константы
START_BALANCE = 10000.0
MIN_BET = 10.0
CURRENCY_NAME = "DodoCoin"
CURRENCY_SHORT = "DC"
REF_REWARD = 5000.0
REF_PERCENT = 0.03
BONUS_AMOUNT = 500

# Эмодзи
EMOJI = {
    "crown": "👑",
    "diamond": "💎",
    "vip": "✨",
    "player": "👤",
    "coin": "💰",
    "bonus": "🎁",
    "ref": "🔗",
    "win": "🎉",
    "lose": "💔",
    "bank": "🏦",
    "games": "🎮",
    "top": "🏆",
    "star": "⭐",
    "heart": "❤️",
    "rocket": "🚀",
    "roulette": "🎡",
    "crash": "📈",
    "tower": "🗼",
    "mines": "💣",
    "cube": "🎲",
    "dice": "🎯",
    "check": "✅",
    "error": "❌",
    "clock": "⏰",
    "gift": "🎁",
    "warning": "⚠️",
    "info": "ℹ️",
}

# Игровые множители
TOWER_MULTIPLIERS = [1.20, 1.48, 1.86, 2.35, 2.95, 3.75, 4.85, 6.15, 7.80, 10.0]

# Рулетка
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# ==================== ПРОВЕРКА ПОДПИСКИ ====================

async def check_subscriptions(bot: Bot, user_id: int) -> Tuple[bool, List[str]]:
    """Проверяет подписку пользователя на все каналы"""
    not_subscribed = []
    
    for channel in CHANNELS:
        try:
            chat_member = await bot.get_chat_member(channel["id"], user_id)
            if chat_member.status in ["left", "kicked", "restricted"]:
                not_subscribed.append(channel["name"])
        except Exception:
            not_subscribed.append(channel["name"])
    
    return len(not_subscribed) == 0, not_subscribed

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подписки"""
    buttons = []
    for channel in CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 {channel['name']}", url=channel["url"])])
    buttons.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

class SubscriptionFilter(BaseFilter):
    """Фильтр для проверки подписки"""
    async def __call__(self, message: Message, bot: Bot) -> bool:
        user_id = message.from_user.id
        is_subscribed, not_subscribed = await check_subscriptions(bot, user_id)
        
        if not is_subscribed:
            channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
            await message.answer(
                f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
                f"Для игры в казино необходимо подписаться на следующие каналы:\n\n"
                f"{channels_text}\n\n"
                f"<i>После подписки нажми кнопку «Проверить подписку»</i>",
                reply_markup=get_subscription_keyboard()
            )
            return False
        return True

# ==================== БАЗА ДАННЫХ ====================

DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "dodocoin.db")
os.makedirs(DB_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            coins REAL DEFAULT 1000.0,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            lost_coins REAL DEFAULT 0.0,
            won_coins REAL DEFAULT 0.0,
            registered_at INTEGER DEFAULT 0,
            last_active INTEGER DEFAULT 0,
            ref_id TEXT DEFAULT NULL,
            ref_earned REAL DEFAULT 0.0,
            ref_count INTEGER DEFAULT 0,
            first_name TEXT DEFAULT '',
            last_bonus INTEGER DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            bet_amount REAL,
            game_type TEXT,
            outcome TEXT,
            win INTEGER DEFAULT 0,
            payout REAL DEFAULT 0.0,
            ts INTEGER DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS bank_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            principal REAL,
            rate REAL,
            term_days INTEGER,
            opened_at INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS json_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts():
    return int(time.time())

def fmt_money(value):
    value = round(float(value), 2)
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M {CURRENCY_SHORT}"
    elif value >= 1000:
        return f"{value/1000:.1f}K {CURRENCY_SHORT}"
    elif value == int(value):
        return f"{int(value)} {CURRENCY_SHORT}"
    else:
        return f"{value:.2f} {CURRENCY_SHORT}"

def escape_html(text):
    return html.escape(str(text or ""), quote=False)

def mention_user(user_id, name=None):
    label = escape_html(name or f"ID {user_id}")
    return f'<a href="tg://user?id={user_id}">{label}</a>'

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

def ensure_user(user_id, ref_id=None, first_name=""):
    conn = get_db()
    try:
        now = now_ts()
        row = conn.execute("SELECT id FROM users WHERE id = ?", (str(user_id),)).fetchone()
        if not row:
            conn.execute("""
                INSERT INTO users (id, coins, registered_at, last_active, ref_id, first_name, last_bonus)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(user_id), START_BALANCE, now, now, ref_id, first_name[:50], now - 86400))
            if ref_id and ref_id != str(user_id):
                conn.execute("UPDATE users SET ref_count = ref_count + 1, coins = coins + ? WHERE id = ?", (REF_REWARD, ref_id))
        else:
            conn.execute("UPDATE users SET last_active = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()

def get_user(user_id):
    conn = get_db()
    try:
        ensure_user(user_id)
        return conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
    finally:
        conn.close()

def add_balance(user_id, amount, reason=""):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_user(user_id)
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (round(amount, 2), str(user_id)))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"])
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def reserve_bet(user_id, bet):
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
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def finalize_bet(user_id, bet, payout, game_type, outcome):
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
            row = conn.execute("SELECT ref_id FROM users WHERE id = ?", (str(user_id),)).fetchone()
            if row and row["ref_id"]:
                ref_bonus = round(bet * REF_PERCENT, 2)
                conn.execute("UPDATE users SET ref_earned = ref_earned + ?, coins = coins + ? WHERE id = ?", (ref_bonus, ref_bonus, row["ref_id"]))
        conn.execute("UPDATE users SET games_played = games_played + 1 WHERE id = ?", (str(user_id),))
        conn.execute("INSERT INTO bets (user_id, bet_amount, game_type, outcome, win, payout, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(user_id), round(bet, 2), game_type, outcome, 1 if payout > 0 else 0, payout, now_ts()))
        row = conn.execute("SELECT coins FROM users WHERE id = ?", (str(user_id),)).fetchone()
        conn.commit()
        return float(row["coins"])
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_top_users(limit=10):
    conn = get_db()
    try:
        return conn.execute("SELECT id, coins, first_name FROM users ORDER BY coins DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()

def set_json(key, value):
    conn = get_db()
    try:
        conn.execute("INSERT INTO json_data (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, json.dumps(value)))
        conn.commit()
    finally:
        conn.close()

def get_json(key, default=None):
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM json_data WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row["value"])
        return default
    finally:
        conn.close()

# ==================== ИГРЫ ====================

def roulette_spin(choice):
    number = random.randint(0, 36)
    color = "green" if number == 0 else ("red" if number in RED_NUMBERS else "black")
    
    win = False
    multiplier = 0
    
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
    elif choice.isdigit() and int(choice) == number:
        win, multiplier = True, 35.0
    
    color_text = {"red": "🔴 Красное", "black": "⚫ Чёрное", "green": "🟢 Зеро"}[color]
    return win, multiplier, f"{number} ({color_text})"

def crash_game():
    r = random.random()
    if r < 0.60:
        return round(random.uniform(1.0, 4.0), 2)
    elif r < 0.85:
        return round(random.uniform(4.01, 15.0), 2)
    else:
        return round(random.uniform(15.01, 100.0), 2)

def mines_multiplier(opened, mines, total=25):
    if opened <= 0:
        return 1.0
    safe = total - mines
    base = total / max(1.0, safe)
    return round((base ** opened) * 0.95, 2)

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Игры"), KeyboardButton(text="🏦 Банк")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="🔗 Рефералы")],
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="⭐ Пополнить")],
        ],
        resize_keyboard=True
    )
    return keyboard

def get_games_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="📈 Краш")],
            [KeyboardButton(text="🗼 Башня"), KeyboardButton(text="💣 Мины")],
            [KeyboardButton(text="🎲 Кубик"), KeyboardButton(text="🎯 Кости")],
            [KeyboardButton(text="◀️ Главное меню")],
        ],
        resize_keyboard=True
    )
    return keyboard

# ==================== ОБРАБОТЧИКИ ====================

dp = Dispatcher(storage=MemoryStorage())

# Хранилища игр
tower_games = {}
mines_games = {}

# ==================== ПРОВЕРКА ПОДПИСКИ (Callback) ====================

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(query: CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    is_subscribed, not_subscribed = await check_subscriptions(bot, user_id)
    
    if is_subscribed:
        await query.message.edit_text(
            f"{EMOJI['check']} <b>ПОДПИСКА ПОДТВЕРЖДЕНА!</b>\n\n"
            f"Добро пожаловать в DodoCoin Casino!\n"
            f"Используй кнопки для навигации.",
            reply_markup=get_main_keyboard()
        )
        await query.answer("✅ Подписка подтверждена!")
    else:
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        await query.answer(f"❌ Вы не подписаны на: {', '.join(not_subscribed)}", show_alert=True)

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

@dp.message(CommandStart())
async def start_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    args = message.text.split()
    ref_id = None
    
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_id = args[1].replace("ref_", "")
        if ref_id == str(user_id):
            ref_id = None
    
    ensure_user(user_id, ref_id, message.from_user.first_name or "")
    
    # Проверяем подписку
    is_subscribed, not_subscribed = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        channels_text = "\n".join([f"• {ch}" for ch in not_subscribed])
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Для игры в казино необходимо подписаться на следующие каналы:\n\n"
            f"{channels_text}\n\n"
            f"<i>После подписки нажми кнопку «Проверить подписку»</i>",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    await message.answer(
        f"{EMOJI['crown']} <b>ДОБРО ПОЖАЛОВАТЬ В DODOKEN CASINO!</b> {EMOJI['crown']}\n\n"
        f"{EMOJI['player']} <b>Игрок:</b> {mention_user(user_id, message.from_user.first_name)}\n"
        f"{EMOJI['coin']} <b>Баланс:</b> {fmt_money(user['coins'])}\n\n"
        f"<b>🎮 ДОСТУПНЫЕ КОМАНДЫ:</b>\n"
        f"┌ баланс - показать баланс\n"
        f"├ бонус - получить бонус\n"
        f"├ профиль - ваш профиль\n"
        f"├ топ - топ игроков\n"
        f"├ реф - реферальная ссылка\n"
        f"├ рул [сумма] [ставка] - рулетка\n"
        f"├ краш [сумма] [множитель] - краш\n"
        f"├ башня [сумма] - башня\n"
        f"├ мины [сумма] - мины\n"
        f"├ кубик [сумма] [число] - кубик\n"
        f"└ кости [сумма] [больше/меньше/7] - кости\n\n"
        f"<b>👇 ИСПОЛЬЗУЙ КНОПКИ 👇</b>",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda m: m.text and m.text.lower() in ["главное меню", "◀️ главное меню", "меню"])
async def main_menu_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    await message.answer(
        f"{EMOJI['crown']} <b>ГЛАВНОЕ МЕНЮ</b> {EMOJI['crown']}\n\n"
        f"{EMOJI['player']} <b>Игрок:</b> {mention_user(user_id, message.from_user.first_name)}\n"
        f"{EMOJI['coin']} <b>Баланс:</b> {fmt_money(user['coins'])}\n\n"
        f"<b>👇 ВЫБЕРИ РАЗДЕЛ 👇</b>",
        reply_markup=get_main_keyboard()
    )

@dp.message(lambda m: m.text and m.text.lower() in ["🎮 игры", "игры"])
async def games_menu_handler(message: Message):
    await message.answer(
        f"{EMOJI['games']} <b>ВЫБЕРИ ИГРУ</b> {EMOJI['games']}\n\n"
        f"┌ 🎡 <b>Рулетка</b> - угадай цвет или число\n"
        f"├ 📈 <b>Краш</b> - забери множитель вовремя\n"
        f"├ 🗼 <b>Башня</b> - найди безопасный путь\n"
        f"├ 💣 <b>Мины</b> - открой все безопасные клетки\n"
        f"├ 🎲 <b>Кубик</b> - угадай выпадение\n"
        f"└ 🎯 <b>Кости</b> - угадай сумму\n\n"
        f"<i>Используй кнопки или команды:</i>\n"
        f"рул 100 красное\nкраш 100 2.5\nбашня 100\nмины 100\nкубик 100 4\nкости 100 больше",
        reply_markup=get_games_keyboard()
    )

@dp.message(lambda m: m.text and m.text.lower() in ["💰 баланс", "баланс", "/balance", "б"])
async def balance_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    await message.answer(
        f"{EMOJI['coin']} <b>ТВОЙ БАЛАНС</b>\n\n"
        f"<code>{fmt_money(user['coins'])}</code>\n\n"
        f"<i>Игр сыграно: {user['games_played']} | Побед: {user['games_won']}</i>"
    )

@dp.message(lambda m: m.text and m.text.lower() in ["👤 профиль", "профиль"])
async def profile_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    
    name = user['first_name'] if user['first_name'] else f"ID {user_id}"
    reg_date = datetime.fromtimestamp(user['registered_at'] or 0).strftime("%d.%m.%Y")
    winrate = round((user['games_won'] / user['games_played'] * 100), 1) if user['games_played'] > 0 else 0
    
    await message.answer(
        f"{EMOJI['player']} <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        f"┌ {EMOJI['player']} <b>Имя:</b> {mention_user(user_id, name)}\n"
        f"├ {EMOJI['coin']} <b>Баланс:</b> {fmt_money(user['coins'])}\n"
        f"├ {EMOJI['games']} <b>Сыграно:</b> {user['games_played']}\n"
        f"├ {EMOJI['top']} <b>Побед:</b> {user['games_won']} ({winrate}%)\n"
        f"├ {EMOJI['win']} <b>Выиграно:</b> {fmt_money(user['won_coins'])}\n"
        f"├ {EMOJI['lose']} <b>Проиграно:</b> {fmt_money(user['lost_coins'])}\n"
        f"├ {EMOJI['ref']} <b>Рефералов:</b> {user['ref_count']}\n"
        f"├ {EMOJI['ref']} <b>Заработано:</b> {fmt_money(user['ref_earned'])}\n"
        f"└ {EMOJI['clock']} <b>Регистрация:</b> {reg_date}"
    )

@dp.message(lambda m: m.text and m.text.lower() in ["🏆 топ", "топ"])
async def top_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    users = get_top_users(10)
    if not users:
        await message.answer(f"{EMOJI['top']} <b>ТОП ИГРОКОВ</b>\n\nПока пусто...")
        return
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [f"{EMOJI['top']} <b>ТОП ИГРОКОВ</b>\n"]
    for idx, user in enumerate(users, 1):
        medal = medals.get(idx, f"{idx}.")
        name = user['first_name'] if user['first_name'] else f"ID {user['id']}"
        lines.append(f"{medal} {escape_html(name)} — {fmt_money(user['coins'])}")
    
    await message.answer("\n".join(lines))

@dp.message(lambda m: m.text and m.text.lower() in ["🎁 бонус", "бонус"])
async def bonus_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    now = now_ts()
    last_bonus = user['last_bonus'] or 0
    
    if now - last_bonus < 86400:
        left = 86400 - (now - last_bonus)
        hours = left // 3600
        minutes = (left % 3600) // 60
        await message.answer(f"{EMOJI['clock']} <b>Бонус уже получен!</b>\nСледующий через: {hours}ч {minutes}м")
        return
    
    reward = BONUS_AMOUNT
    new_balance = add_balance(user_id, reward, "Ежедневный бонус")
    
    conn = get_db()
    try:
        conn.execute("UPDATE users SET last_bonus = ? WHERE id = ?", (now, str(user_id)))
        conn.commit()
    finally:
        conn.close()
    
    await message.answer(
        f"{EMOJI['gift']} <b>БОНУС ПОЛУЧЕН!</b>\n\n"
        f"💰 Начислено: {fmt_money(reward)}\n"
        f"💎 Новый баланс: {fmt_money(new_balance)}\n\n"
        f"<i>Следующий бонус через 24 часа</i>"
    )

@dp.message(lambda m: m.text and m.text.lower() in ["🔗 рефералы", "рефералы", "реф"])
async def ref_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = get_user(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    await message.answer(
        f"{EMOJI['ref']} <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n\n"
        f"┌ {EMOJI['coin']} <b>За друга:</b> {fmt_money(REF_REWARD)}\n"
        f"├ {EMOJI['ref']} <b>Приглашено:</b> {user['ref_count']}\n"
        f"├ {EMOJI['coin']} <b>Заработано:</b> {fmt_money(user['ref_earned'])}\n"
        f"└ {EMOJI['ref']} <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>"
    )

@dp.message(lambda m: m.text and m.text.lower() in ["🏦 банк", "банк"])
async def bank_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    await message.answer(
        f"{EMOJI['bank']} <b>БАНКОВСКАЯ СИСТЕМА</b>\n\n"
        f"┌ 7 дней — +3%\n"
        f"├ 14 дней — +7%\n"
        f"└ 30 дней — +18%\n\n"
        f"<i>Используй команду: депозит [сумма] [дни]</i>\n"
        f"<i>Пример: депозит 1000 7</i>\n\n"
        f"<i>Или сними депозит: снятьдепозит</i>"
    )

@dp.message(lambda m: m.text and m.text.lower().startswith("депозит"))
async def deposit_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: депозит [сумма] [дни]\nДни: 7, 14, 30")
        return
    
    try:
        amount = float(parts[1])
        days = int(parts[2])
    except:
        await message.answer("❌ Неверный формат!")
        return
    
    rates = {7: 0.03, 14: 0.07, 30: 0.18}
    if days not in rates:
        await message.answer("❌ Доступные дни: 7, 14, 30")
        return
    
    if amount < 100:
        await message.answer(f"❌ Минимальная сумма: {fmt_money(100)}")
        return
    
    ok, _ = reserve_bet(message.from_user.id, amount)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!")
        return
    
    rate = rates[days]
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO bank_deposits (user_id, principal, rate, term_days, opened_at, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (str(message.from_user.id), amount, rate, days, now_ts()))
        conn.commit()
    finally:
        conn.close()
    
    profit = amount * rate
    await message.answer(
        f"{EMOJI['check']} <b>ДЕПОЗИТ ОТКРЫТ!</b>\n\n"
        f"┌ 💰 Сумма: {fmt_money(amount)}\n"
        f"├ 📅 Срок: {days} дней\n"
        f"├ 📈 Ставка: +{int(rate*100)}%\n"
        f"└ 💎 Доход: {fmt_money(profit)}"
    )

@dp.message(lambda m: m.text and m.text.lower() in ["снятьдепозит", "снять депозит"])
async def withdraw_deposit_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    now = now_ts()
    conn = get_db()
    try:
        deposits = conn.execute("""
            SELECT * FROM bank_deposits 
            WHERE user_id = ? AND status = 'active' AND opened_at + term_days * 86400 <= ?
        """, (str(message.from_user.id), now)).fetchall()
        
        total = 0
        count = 0
        for dep in deposits:
            payout = dep["principal"] * (1 + dep["rate"])
            total += payout
            count += 1
            conn.execute("UPDATE bank_deposits SET status = 'closed' WHERE id = ?", (dep["id"],))
        
        if total > 0:
            add_balance(message.from_user.id, total, "Вывод депозита")
            await message.answer(
                f"{EMOJI['check']} <b>ДЕПОЗИТЫ ВЫВЕДЕНЫ</b>\n\n"
                f"┌ 📊 Выведено: {count} депозитов\n"
                f"└ 💰 Сумма: {fmt_money(total)}"
            )
        else:
            await message.answer("❌ Нет депозитов готовых к выводу.")
    finally:
        conn.close()

@dp.message(lambda m: m.text and m.text.lower() in ["⭐ пополнить", "пополнить"])
async def donate_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    await message.answer(
        f"{EMOJI['star']} <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
        f"Для пополнения свяжитесь с администратором:\n"
        f"{mention_user(list(ADMIN_IDS)[0])}\n\n"
        f"<i>Минимальная сумма пополнения: 100 {CURRENCY_SHORT}</i>"
    )

# ==================== ИГРА: РУЛЕТКА ====================

@dp.message(lambda m: m.text and m.text.lower().startswith("рул"))
async def roulette_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            f"{EMOJI['roulette']} <b>РУЛЕТКА</b>\n\n"
            f"Использование: рул [сумма] [ставка]\n\n"
            f"<b>Ставки:</b>\n"
            f"┌ красное / черное - x2\n"
            f"├ чет / нечет - x2\n"
            f"├ зеро - x36\n"
            f"└ [число] 0-36 - x35\n\n"
            f"<i>Пример: рул 100 красное</i>"
        )
        return
    
    try:
        bet = float(parts[1])
        choice = parts[2]
    except:
        await message.answer("❌ Неверный формат!\nПример: рул 100 красное")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    win, multiplier, outcome = roulette_spin(choice)
    payout = round(bet * multiplier, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!\nНужно: {fmt_money(bet)}")
        return
    
    new_balance = finalize_bet(message.from_user.id, bet, payout, "roulette", f"{choice}:{outcome}")
    
    result_icon = EMOJI['win'] if win else EMOJI['lose']
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>РУЛЕТКА - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Выбор:</b> {choice}\n"
        f"├ <b>Выпало:</b> {outcome}\n"
        f"├ <b>Множитель:</b> x{multiplier}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРА: КРАШ ====================

@dp.message(lambda m: m.text and m.text.lower().startswith("краш"))
async def crash_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            f"{EMOJI['crash']} <b>КРАШ</b>\n\n"
            f"Использование: краш [сумма] [множитель]\n"
            f"<i>Пример: краш 100 2.5</i>\n\n"
            f"Множитель от 1.01 до 100"
        )
        return
    
    try:
        bet = float(parts[1])
        target = float(parts[2])
    except:
        await message.answer("❌ Неверный формат!\nПример: краш 100 2.5")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    if target < 1.01 or target > 100:
        await message.answer("❌ Множитель от 1.01 до 100")
        return
    
    crash_value = crash_game()
    win = target <= crash_value
    payout = round(bet * target, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!\nНужно: {fmt_money(bet)}")
        return
    
    new_balance = finalize_bet(message.from_user.id, bet, payout, "crash", f"target:{target}:crash:{crash_value}")
    
    result_icon = EMOJI['win'] if win else EMOJI['lose']
    result_text = "УСПЕХ!" if win else "КРАШ!"
    
    await message.answer(
        f"{result_icon} <b>КРАШ - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Твой множитель:</b> x{target}\n"
        f"├ <b>Выпало:</b> x{crash_value}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРА: КУБИК ====================

@dp.message(lambda m: m.text and m.text.lower().startswith("кубик"))
async def cube_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            f"{EMOJI['cube']} <b>КУБИК</b>\n\n"
            f"Использование: кубик [сумма] [число 1-6]\n"
            f"<i>Пример: кубик 100 4</i>"
        )
        return
    
    try:
        bet = float(parts[1])
        guess = int(parts[2])
    except:
        await message.answer("❌ Неверный формат!\nПример: кубик 100 4")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    if guess not in range(1, 7):
        await message.answer("❌ Число от 1 до 6")
        return
    
    rolled = random.randint(1, 6)
    win = guess == rolled
    payout = round(bet * 5.8, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!\nНужно: {fmt_money(bet)}")
        return
    
    new_balance = finalize_bet(message.from_user.id, bet, payout, "cube", f"guess:{guess}:rolled:{rolled}")
    
    result_icon = EMOJI['win'] if win else EMOJI['lose']
    result_text = "ПОБЕДА!" if win else "ПОРАЖЕНИЕ"
    
    await message.answer(
        f"{result_icon} <b>КУБИК - {result_text}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Твой выбор:</b> {guess}\n"
        f"├ <b>Выпало:</b> {rolled}\n"
        f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
        f"└ <b>Баланс:</b> {fmt_money(new_balance)}"
    )

# ==================== ИГРА: КОСТИ ====================

@dp.message(lambda m: m.text and m.text.lower().startswith("кости"))
async def dice_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.lower().split()
    if len(parts) < 3:
        await message.answer(
            f"{EMOJI['dice']} <b>КОСТИ</b>\n\n"
            f"Использование: кости [сумма] [больше/меньше/7]\n"
            f"<i>Пример: кости 100 больше</i>"
        )
        return
    
    try:
        bet = float(parts[1])
        choice = parts[2]
    except:
        await message.answer("❌ Неверный формат!\nПример: кости 100 больше")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2
    
    win = False
    multiplier = 0
    
    if choice == "больше" and total > 7:
        win, multiplier = True, 2.25
    elif choice == "меньше" and total < 7:
        win, multiplier = True, 2.25
    elif choice == "7" and total == 7:
        win, multiplier = True, 5.0
    
    payout = round(bet * multiplier, 2) if win else 0
    
    ok, _ = reserve_bet(message.from_user.id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!\nНужно: {fmt_money(bet)}")
        return
    
    new_balance = finalize_bet(message.from_user.id, bet, payout, "dice", f"choice:{choice}:{d1}+{d2}={total}")
    
    result_icon = EMOJI['win'] if win else EMOJI['lose']
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

# ==================== ИГРА: БАШНЯ ====================

def get_tower_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="tower:1"),
         InlineKeyboardButton(text="2", callback_data="tower:2"),
         InlineKeyboardButton(text="3", callback_data="tower:3")],
        [InlineKeyboardButton(text="💰 Забрать", callback_data="tower:cash"),
         InlineKeyboardButton(text="❌ Сдаться", callback_data="tower:cancel")]
    ])

@dp.message(lambda m: m.text and m.text.lower().startswith("башня"))
async def tower_start_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    
    if not is_subscribed:
        await message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    parts = message.text.lower().split()
    if len(parts) < 2:
        await message.answer(
            f"{EMOJI['tower']} <b>БАШНЯ</b>\n\n"
            f"Использование: башня [сумма]\n"
            f"<i>Пример: башня 100</i>"
        )
        return
    
    try:
        bet = float(parts[1])
    except:
        await message.answer("❌ Неверная сумма!\nПример: башня 100")
        return
    
    if bet < MIN_BET:
        await message.answer(f"❌ Минимальная ставка: {fmt_money(MIN_BET)}")
        return
    
    if user_id in tower_games:
        await message.answer("❌ У тебя уже есть активная игра!")
        return
    
    ok, _ = reserve_bet(user_id, bet)
    if not ok:
        await message.answer(f"❌ Недостаточно средств!\nНужно: {fmt_money(bet)}")
        return
    
    tower_games[user_id] = {"bet": bet, "level": 0}
    
    await message.answer(
        f"{EMOJI['tower']} <b>БАШНЯ</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(bet)}\n"
        f"├ <b>Этаж:</b> 0\n"
        f"└ <b>Множитель:</b> x1.00\n\n"
        f"<b>Выбери безопасную секцию (1-3):</b>",
        reply_markup=get_tower_kb()
    )

@dp.callback_query(F.data.startswith("tower:"))
async def tower_callback(query: CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    game = tower_games.get(user_id)
    
    if not game:
        await query.answer("❌ Нет активной игры!", show_alert=True)
        return
    
    is_subscribed, _ = await check_subscriptions(bot, user_id)
    if not is_subscribed:
        await query.message.answer(
            f"{EMOJI['warning']} <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            f"Подпишись на каналы чтобы продолжить.",
            reply_markup=get_subscription_keyboard()
        )
        await query.answer()
        return
    
    action = query.data.split(":")[1]
    
    if action == "cash":
        level = game["level"]
        if level == 0:
            await query.answer("❌ Сделай хотя бы один ход!", show_alert=True)
            return
        mult = TOWER_MULTIPLIERS[level - 1]
        payout = round(game["bet"] * mult, 2)
        balance = finalize_bet(user_id, game["bet"], payout, "tower", f"cashout_level{level}")
        tower_games.pop(user_id, None)
        await query.message.edit_text(
            f"{EMOJI['win']} <b>ВЫВОД СРЕДСТВ</b>\n\n"
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
            balance = finalize_bet(user_id, game["bet"], game["bet"], "tower", "cancel_refund")
            await query.message.edit_text(f"🛑 Игра отменена. Возврат: {fmt_money(game['bet'])}\nБаланс: {fmt_money(balance)}")
        else:
            balance = finalize_bet(user_id, game["bet"], 0, "tower", "cancel_lose")
            await query.message.edit_text(f"❌ Игра завершена. Потеряно: {fmt_money(game['bet'])}\nБаланс: {fmt_money(balance)}")
        tower_games.pop(user_id, None)
        await query.answer()
        return
    
    chosen = int(action)
    safe = random.randint(1, 3)
    
    if chosen != safe:
        balance = finalize_bet(user_id, game["bet"], 0, "tower", f"lose_chosen{chosen}_safe{safe}")
        tower_games.pop(user_id, None)
        await query.message.edit_text(
            f"{EMOJI['lose']} <b>ПРОИГРЫШ</b>\n\n"
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
        balance = finalize_bet(user_id, game["bet"], payout, "tower", "max_level")
        tower_games.pop(user_id, None)
        await query.message.edit_text(
            f"{EMOJI['win']} <b>ПОБЕДА!</b>\n\n"
            f"┌ <b>Максимальный этаж!</b>\n"
            f"├ <b>Множитель:</b> x{mult}\n"
            f"├ <b>Выплата:</b> {fmt_money(payout)}\n"
            f"└ <b>Баланс:</b> {fmt_money(balance)}"
        )
        await query.answer()
        return
    
    current_mult = TOWER_MULTIPLIERS[level - 1]
    current_win = round(game["bet"] * current_mult, 2)
    
    await query.message.edit_text(
        f"{EMOJI['tower']} <b>БАШНЯ - ЭТАЖ {level}</b>\n\n"
        f"┌ <b>Ставка:</b> {fmt_money(game['bet'])}\n"
        f"├ <b>Этаж:</b> {level}\n"
        f"├ <b>Можно забрать:</b> {fmt_money(current_win)}\n"
        f"└ <b>Множитель:</b> x{current_mult}\n\n"
        f"<b>Выбери безопасную секцию (1-3):</b>",
        reply_markup=get_tower_kb()
    )
    await query.answer(f"✅ Безопасно! Этаж {level}")

# ==================== АДМИН КОМАНДЫ ====================

@dp.message(lambda m: m.text and m.text.lower() == "админ" and is_admin(m.from_user.id))
async def admin_panel(message: Message):
    await message.answer(
        f"{EMOJI['crown']} <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"Доступные команды:\n"
        f"┌ выдать [id] [сумма] - выдать монеты\n"
        f"├ массбонус [сумма] - массовый бонус\n"
        f"├ рассылка [текст] - рассылка\n"
        f"├ статистика - статистика бота\n"
        f"└ топ20 - топ 20 игроков"
    )

@dp.message(lambda m: m.text and m.text.lower().startswith("выдать") and is_admin(m.from_user.id))
async def admin_give(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Использование: выдать [id] [сумма]")
        return
    
    try:
        target_id = int(parts[1])
        amount = float(parts[2])
    except:
        await message.answer("❌ Неверный формат!")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    ensure_user(target_id)
    new_balance = add_balance(target_id, amount, f"Выдано администратором {message.from_user.id}")
    
    await message.answer(
        f"{EMOJI['check']} <b>МОНЕТЫ ВЫДАНЫ</b>\n\n"
        f"┌ 👤 Пользователь: {mention_user(target_id)}\n"
        f"├ 💰 Сумма: {fmt_money(amount)}\n"
        f"└ 💎 Новый баланс: {fmt_money(new_balance)}"
    )

@dp.message(lambda m: m.text and m.text.lower().startswith("массбонус") and is_admin(m.from_user.id))
async def admin_mass_bonus(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Использование: массбонус [сумма]")
        return
    
    try:
        amount = float(parts[1])
    except:
        await message.answer("❌ Неверная сумма!")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть положительной")
        return
    
    conn = get_db()
    try:
        users = conn.execute("SELECT id FROM users").fetchall()
    finally:
        conn.close()
    
    success = 0
    for user in users:
        try:
            add_balance(int(user["id"]), amount, "Массовый бонус от администратора")
            success += 1
            await asyncio.sleep(0.01)
        except:
            pass
    
    await message.answer(
        f"{EMOJI['check']} <b>МАССОВЫЙ БОНУС</b>\n\n"
        f"┌ 💰 Сумма: {fmt_money(amount)}\n"
        f"└ 👥 Получили: {success} игроков"
    )

@dp.message(lambda m: m.text and m.text.lower().startswith("рассылка") and is_admin(m.from_user.id))
async def admin_broadcast(message: Message):
    text = message.text[9:].strip()
    if not text:
        await message.answer("❌ Введи текст рассылки после команды")
        return
    
    conn = get_db()
    try:
        users = conn.execute("SELECT id FROM users").fetchall()
    finally:
        conn.close()
    
    success = 0
    failed = 0
    
    progress = await message.answer(f"📢 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        try:
            await message.bot.send_message(int(user["id"]), text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
        
        if (success + failed) % 50 == 0:
            await progress.edit_text(f"📢 Рассылка: {success + failed}/{len(users)} | ✅ {success} | ❌ {failed}")
    
    await progress.edit_text(
        f"📢 <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
        f"✅ Доставлено: {success}\n"
        f"❌ Ошибок: {failed}"
    )

@dp.message(lambda m: m.text and m.text.lower() == "статистика" and is_admin(m.from_user.id))
async def admin_stats(message: Message):
    conn = get_db()
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bets = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
        total_bet = conn.execute("SELECT COALESCE(SUM(bet_amount), 0) FROM bets").fetchone()[0]
        total_payout = conn.execute("SELECT COALESCE(SUM(payout), 0) FROM bets").fetchone()[0]
        deposits = conn.execute("SELECT COALESCE(SUM(principal), 0) FROM bank_deposits WHERE status = 'active'").fetchone()[0]
    finally:
        conn.close()
    
    profit = total_bet - total_payout
    
    await message.answer(
        f"{EMOJI['stats']} <b>СТАТИСТИКА БОТА</b>\n\n"
        f"┌ 👥 Пользователей: {users}\n"
        f"├ 🎮 Ставок: {bets}\n"
        f"├ 💰 Общий оборот: {fmt_money(total_bet)}\n"
        f"├ 💸 Выплат: {fmt_money(total_payout)}\n"
        f"├ 📈 Профит: {fmt_money(profit)}\n"
        f"└ 🏦 Депозитов: {fmt_money(deposits)}"
    )

@dp.message(lambda m: m.text and m.text.lower() == "топ20" and is_admin(m.from_user.id))
async def admin_top20(message: Message):
    users = get_top_users(20)
    lines = [f"{EMOJI['top']} <b>ТОП-20 ИГРОКОВ</b>\n"]
    for idx, user in enumerate(users, 1):
        name = user['first_name'] if user['first_name'] else f"ID {user['id']}"
        lines.append(f"{idx}. {escape_html(name)} — {fmt_money(user['coins'])}")
    
    await message.answer("\n".join(lines))

# ==================== ЗАПУСК БОТА ====================

async def main():
    init_db()
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Устанавливаем команды
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="📚 Помощь"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("=" * 50)
    print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
    print(f"📊 Имя бота: @{BOT_USERNAME}")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"📢 Каналы для подписки: {len(CHANNELS)}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
