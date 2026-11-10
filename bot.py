import os
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
import telebot
from telebot import types

# Вбудований токен Telegram-бота
API_TOKEN = "9082226158:AAGIRe-wteR51j1vI8USvIdVuuC5pkWGmec"

bot = telebot.TeleBot(API_TOKEN)

# Налаштування оплати та палива
RATE_PER_KM = 3.0
RATE_PER_POINT = 15.0
FUEL_CONSUMPTION = 8.0  # л / 100 км
FUEL_PRICE = 87.0        # грн / л

DB_NAME = "courier_bot.sqlite3"

# Тимчасові стани діалогу. Основні дані зберігаються в SQLite.
user_states = {}


@contextmanager
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                fuel REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                ride_date TEXT NOT NULL,
                km REAL NOT NULL,
                points INTEGER NOT NULL,
                earned_km REAL NOT NULL,
                earned_points REAL NOT NULL,
                fuel_used REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refuels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                refuel_date TEXT NOT NULL,
                liters REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def ensure_user(chat_id):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(chat_id, fuel) VALUES (?, 0)",
            (chat_id,)
        )


def get_fuel(chat_id):
    ensure_user(chat_id)
    with db() as conn:
        row = conn.execute(
            "SELECT fuel FROM users WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return float(row["fuel"])


def set_fuel(chat_id, liters):
    ensure_user(chat_id)
    with db() as conn:
        conn.execute(
            "UPDATE users SET fuel = ? WHERE chat_id = ?",
            (liters, chat_id)
        )


def get_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Додати заїзд", "⛽ Заправка")
    markup.row("📈 Звіт за місяць", "🔄 Новий місяць")
    return markup


def parse_positive_number(value, allow_zero=False):
    number = float(value.replace(",", "."))
    if not math.isfinite(number):
        raise ValueError
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError
    return number


def parse_ride(text):
    """
    Формати:
      120 5          — сьогодні, 120 км, 5 точок
      09.11 100 3    — 9 листопада поточного року, 100 км, 3 точки
      09.11.2026 100 3 — повна дата
    """
    parts = text.split()
    today = date.today()

    if len(parts) == 2:
        ride_date = today
        km_text, points_text = parts
    elif len(parts) == 3:
        date_text, km_text, points_text = parts
        try:
            ride_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        except ValueError:
            ride_date = datetime.strptime(date_text, "%d.%m").date().replace(
                year=today.year
            )
    else:
        raise ValueError("Неправильна кількість значень.")

    km = parse_positive_number(km_text, allow_zero=True)
    points_float = parse_positive_number(points_text, allow_zero=True)
    if not points_float.is_integer():
        raise ValueError("Кількість точок має бути цілим числом.")
    points = int(points_float)

    if ride_date > today:
        raise ValueError("Дата заїзду не може бути в майбутньому.")

    return ride_date, km, points


@bot.message_handler(commands=["start"])
def send_welcome(message):
    ensure_user(message.chat.id)
    bot.send_message(
        message.chat.id,
        "Привіт! Я бот-помічник для обліку заробітку кур'єра.\n"
        "Обери дію на клавіатурі нижче.",
        reply_markup=get_markup()
    )


@bot.message_handler(commands=["cancel"])
def cancel_action(message):
    user_states.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id, "Дію скасовано.",
        reply_markup=get_markup()
    )


@bot.message_handler(commands=["set_fuel"])
def set_fuel_command(message):
    user_states[message.chat.id] = "wait_fuel"
    bot.send_message(
        message.chat.id,
        "Введи фактичний залишок палива в літрах. Для скасування — /cancel."
    )


@bot.message_handler(func=lambda m: m.text == "🔄 Новий місяць" or m.text == "Новий місяць")
def new_month(message):
    bot.send_message(
        message.chat.id,
        "Новий місяць обліковується автоматично з 1-го числа.\n"
        "Історію попередніх місяців збережено — нічого не видаляється.",
        reply_markup=get_markup()
    )


@bot.message_handler(func=lambda m: m.text in ("📊 Додати заїзд", "Додати заїзд"))
def add_ride_start(message):
    user_states[message.chat.id] = "wait_ride"
    bot.send_message(
        message.chat.id,
        "Введи дані у форматі:\n"
        "120 5 — сьогодні, 120 км і 5 точок\n"
        "09.11 100 3 — дата, км і точки\n"
        "09.11.2026 100 3 — дата з роком\n\n"
        "Для скасування — /cancel."
    )


@bot.message_handler(func=lambda m: m.text in ("⛽ Заправка", "Заправка"))
def refuel_start(message):
    user_states[message.chat.id] = "wait_refuel"
    bot.send_message(
        message.chat.id,
        "Введи кількість заправлених літрів. Для скасування — /cancel."
    )


@bot.message_handler(func=lambda m: m.text in ("📈 Звіт за місяць", "Звіт за місяць"))
def send_report(message):
    chat_id = message.chat.id
    now = date.today()
    month_start = now.replace(day=1).isoformat()
    next_month = date(now.year + (now.month == 12), 1 if now.month == 12 else now.month + 1, 1).isoformat()

    with db() as conn:
        stats = conn.execute("""
            SELECT
                COUNT(*) AS rides_count,
                COALESCE(SUM(km), 0) AS total_km,
                COALESCE(SUM(points), 0) AS total_points,
                COALESCE(SUM(earned_km), 0) AS earned_km,
                COALESCE(SUM(earned_points), 0) AS earned_points,
                COALESCE(SUM(fuel_used), 0) AS fuel_used
            FROM rides
            WHERE chat_id = ? AND ride_date >= ? AND ride_date < ?
        """, (chat_id, month_start, next_month)).fetchone()

        refuel = conn.execute("""
            SELECT COALESCE(SUM(liters), 0) AS liters
            FROM refuels
            WHERE chat_id = ? AND refuel_date >= ? AND refuel_date < ?
        """, (chat_id, month_start, next_month)).fetchone()

    total_earned = stats["earned_km"] + stats["earned_points"]
    fuel_cost = stats["fuel_used"] * FUEL_PRICE
    current_fuel = get_fuel(chat_id)

    report = (
        f"📊 Звіт за {now.strftime('%m.%Y')}:\n\n"
        f"🚘 Пробіг: {stats['total_km']:.1f} км\n"
        f"📍 Точки: {stats['total_points']}\n"
        f"🧾 Кількість заїздів: {stats['rides_count']}\n\n"
        f"💰 За кілометри: {stats['earned_km']:.2f} грн\n"
        f"💰 За точки: {stats['earned_points']:.2f} грн\n"
        f"🏆 Всього зароблено: {total_earned:.2f} грн\n\n"
        f"⛽ Заправлено за місяць: {refuel['liters']:.1f} л\n"
        f"🛢 Витрачено за розрахунком: {stats['fuel_used']:.1f} л\n"
        f"💸 Орієнтовна вартість витраченого палива: {fuel_cost:.2f} грн\n"
        f"🚗 Залишок у баку: {current_fuel:.1f} л"
    )
    bot.send_message(chat_id, report, reply_markup=get_markup())


@bot.message_handler(func=lambda m: m.chat.id in user_states)
def process_input(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = (message.text or "").strip()

    if text in ("/cancel", "Скасувати"):
        user_states.pop(chat_id, None)
        bot.send_message(chat_id, "Дію скасовано.", reply_markup=get_markup())
        return

    if state == "wait_fuel":
        try:
            liters = parse_positive_number(text, allow_zero=True)
            set_fuel(chat_id, liters)
            user_states.pop(chat_id, None)
            bot.send_message(
                chat_id, f"Залишок палива встановлено: {liters:.1f} л.",
                reply_markup=get_markup()
            )
        except (ValueError, TypeError):
            bot.send_message(chat_id, "Введи коректне число літрів, наприклад 3.1.")
        return

    if state == "wait_refuel":
        try:
            liters = parse_positive_number(text)
            current = get_fuel(chat_id)
            new_balance = current + liters
            set_fuel(chat_id, new_balance)
            with db() as conn:
                conn.execute("""
                    INSERT INTO refuels(chat_id, refuel_date, liters, created_at)
                    VALUES (?, ?, ?, ?)
                """, (chat_id, date.today().isoformat(), liters, datetime.now().isoformat()))
            user_states.pop(chat_id, None)
            bot.send_message(
                chat_id,
                f"✅ Заправку додано: {liters:.1f} л.\n"
                f"🚗 Тепер у баку: {new_balance:.1f} л.",
                reply_markup=get_markup()
            )
        except (ValueError, TypeError):
            bot.send_message(chat_id, "Введи додатну кількість літрів, наприклад 20 або 12,5.")
        return

    if state == "wait_ride":
        try:
            ride_date, km, points = parse_ride(text)
        except (ValueError, TypeError) as error:
            bot.send_message(
                chat_id,
                f"Не вдалося розпізнати заїзд: {error}\n"
                "Приклад: 120 5 або 09.11 100 3. Спробуй ще раз."
            )
            return

        earned_km = km * RATE_PER_KM
        earned_points = points * RATE_PER_POINT
        fuel_used = km / 100 * FUEL_CONSUMPTION
        current_fuel = get_fuel(chat_id)
        remaining_fuel = current_fuel - fuel_used

        if remaining_fuel < -0.000001:
            bot.send_message(
                chat_id,
                f"Увага: за нормою на цей заїзд потрібно {fuel_used:.1f} л, "
                f"але в обліку є лише {current_fuel:.1f} л.\n"
                "Заїзд не записано. Спочатку виправ залишок через /set_fuel "
                "або додай заправку."
            )
            return

        with db() as conn:
            conn.execute("""
                INSERT INTO rides(
                    chat_id, ride_date, km, points, earned_km,
                    earned_points, fuel_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id, ride_date.isoformat(), km, points, earned_km,
                earned_points, fuel_used, datetime.now().isoformat()
            ))
            conn.execute(
                "UPDATE users SET fuel = ? WHERE chat_id = ?",
                (max(0.0, remaining_fuel), chat_id)
            )

        user_states.pop(chat_id, None)
        bot.send_message(
            chat_id,
            f"✅ Заїзд за {ride_date.strftime('%d.%m.%Y')} збережено!\n"
            f"🚘 Пробіг: {km:.1f} км\n"
            f"📍 Точки: {points}\n"
            f"💰 За км: {earned_km:.2f} грн\n"
            f"💰 За точки: {earned_points:.2f} грн\n"
            f"🏆 Всього за заїзд: {earned_km + earned_points:.2f} грн\n"
            f"⛽ Витрачено за нормою: {fuel_used:.1f} л\n"
            f"🚗 Залишок у баку: {max(0.0, remaining_fuel):.1f} л",
            reply_markup=get_markup()
        )


if __name__ == "__main__":
    init_db()
    print("Бот запущено.")
    bot.infinity_polling(skip_pending=True)
