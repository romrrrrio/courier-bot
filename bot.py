import os
import telebot
from telebot import types

# Токен вашого бота вже вставлено
TOKEN = "9082226158:AAGIRe-wteR51j1vI8USvIdVuuC5pkWGmec"
bot = telebot.TeleBot(TOKEN)

# Проста структура даних для обліку
user_data = {
    "probig": 0,
    "tochky": 0,
    "zapravka": 0,
    "bak": 50.0,  # Початковий залишок палива
}


@bot.message_handler(commands=["start"])
def send_welcome(markup_message):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.add(
      types.KeyboardButton("📊 Додати заїзд"),
      types.KeyboardButton("⛽ Заправка"),
  )
  markup.add(
      types.KeyboardButton("📈 Звіт за місяць"),
      types.KeyboardButton("🔄 Новий місяць"),
  )

  bot.send_message(
      markup_message.chat.id,
      "Привіт! Я твій бот-помічник для обліку заробітку кур'єра.\nОбери"
      " необхідну дію на клавіатурі нижче:",
      reply_markup=markup,
  )


@bot.message_handler(
    func=lambda message: message.text in [
        "📊 Додати заїзд",
        "⛽ Заправка",
        "📈 Звіт за місяць",
        "🔄 Новий місяць",
    ]
)
def handle_menu(message):
  if message.text == "📊 Додати заїзд":
    sent_msg = bot.send_message(
        message.chat.id,
        "Введи дані через пробіл:\n👉 **Кілометри Точки**\n(наприклад: `120"
        " 8`)",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(sent_msg, process_trip)

  elif message.text == "⛽ Заправка":
    sent_msg = bot.send_message(
        message.chat.id, "Скільки літрів заправив? (наприклад: `15`)"
    )
    bot.register_next_step_handler(sent_msg, process_refuel)

  elif message.text == "📈 Звіт за місяць":
    zarobitok_km = user_data["probig"] * 3
    zarobitok_tochky = user_data["tochky"] * 15
    vsego = zarobitok_km + zarobitok_tochky

    report = (
        f"📊 **Звіт за поточний місяць:**\n\n🛣 Пробіг: {user_data['probig']}"
        f" км\n📍 Точки: {user_data['tochky']}\n\n💰 За кілометри: {zarobitok_km}"
        f" грн\n💰 За точки: {zarobitok_tochky} грн\n🏆 **Всього зароблено:"
        f" {vsego} грн**\n\n⛽ Заправлено палива: {user_data['zapravka']}"
        f" л\n🚗 Залишок в баку: {user_data['bak']:.1f} л"
    )
    bot.send_message(message.chat.id, report, parse_mode="Markdown")

  elif message.text == "🔄 Новий місяць":
    user_data["probig"] = 0
    user_data["tochky"] = 0
    user_data["zapravka"] = 0
    bot.send_message(
        message.chat.id,
        "🔄 Дані місяця очищено! Залишок палива в баку збережено.",
    )


def process_trip(message):
  try:
    parts = message.text.split()
    km = float(parts[0])
    tochky = int(parts[1])

    user_data["probig"] += km
    user_data["tochky"] += tochky

    # Витрата палива: 8л на 100 км (0.08 л на 1 км)
    palyno_vytrata = km * 0.08
    user_data["bak"] -= palyno_vytrata

    zar_d(message, km, tochky, palyno_vytrata)
  except Exception:
    bot.send_message(
        message.chat.id, "❌ Помилка! Введи два числа через пробіл, наприклад: 120 8"
    )


def process_refuel(message):
  try:
    litriv = float(message.text)
    user_data["zapravka"] += litriv
    user_data["bak"] += litriv
    bot.send_message(
        message.chat.id,
        f"✅ Успішно заправлено {litriv} л.\n🚗 Залишок в баку:"
        f" {user_data['bak']:.1f} л",
    )
  except Exception:
    bot.send_message(
        message.chat.id, "❌ Помилка! Введи число, наприклад: 15"
    )


def zar_d(message, km, tochky, palyno_vytrata):
  z_km = km * 3
  z_toch = tochky * 15
  vsego_d = z_km + z_toch
  bot.send_message(
      message.chat.id,
      f"✅ Запис додано!\n• За км: {z_km} грн\n• За точки: {z_toch}"
      f" грн\n• За день: **{vsego_d} грн**\n• Витрачено палива:"
      f" {palyno_vytrata:.1f} л\n• Залишок в баку: {user_data['bak']:.1f} л",
      parse_mode="Markdown",
  )


if __name__ == "__main__":
  bot.infinity_polling()
