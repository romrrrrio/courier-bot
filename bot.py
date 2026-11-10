import telebot
from datetime import datetime, timedelta

API_TOKEN = 9082226158:AAGIRe-wteR51j1vI8USvIdVuuC5pkWGmec
bot = telebot.TeleBot(API_TOKEN)

# Налаштування розцінок та витрати палива
RATE_PER_KM = 3.0       # Гривень за кілометр
RATE_PER_POINT = 15.0    # Гривень за точку
FUEL_CONSUMPTION = 8.0  # Літрів на 100 км
FUEL_PRICE = 50.0        # Ціна за літр палива

# Словники для збереження стану користувачів
user_fuel = {}
user_data_entry = {}

def get_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Додати заїзд', 'Заправка')
    markup.row('Редагувати залишок палива', 'Звіт за місяць')
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_fuel.setdefault(message.chat.id, 0.0) # Початкові літри за замовчуванням
    bot.reply_to(
        message,
        "Привіт! Я оновлений бот кур'єра. Оберіть дію:",
        reply_markup=get_markup()
    )

@bot.message_handler(commands=['set_fuel'])
@bot.message_handler(func=lambda message: message.text == 'Редагувати залишок палива')
def set_fuel_start(message):
    bot.send_message(message.chat.id, "Вкажіть поточний залишок палива в баку (в літрах):")
    user_data_entry[message.chat.id] = 'wait_fuel'

@bot.message_handler(func=lambda message: message.chat.id in user_data_entry and user_data_entry[message.chat.id] == 'wait_fuel')
def set_fuel_process(message):
    try:
        fuel = float(message.text.replace(',', '.'))
        if fuel < 0:
            raise ValueError
        user_fuel[message.chat.id] = fuel
        del user_data_entry[message.chat.id]
        bot.send_message(message.chat.id, f"Залишок палива оновлено: {fuel:.1f} л.", reply_markup=get_markup())
    except ValueError:
        bot.send_message(message.chat.id, "Некоректне значення. Вкажіть число:")

@bot.message_handler(func=lambda message: message.text in ['Додати заїзд', 'Заправка'])
def action_selection(message):
    if message.text == 'Додати заїзд':
        bot.send_message(
            message.chat.id,
            "Введіть дані у форматі: [дата] [км] [точки]\n"
            "Приклади:\n"
            "Сьогодні: 120 5\n"
            "Вчора: 09.11 100 3\n"
            "Конкретна дата: 05.11 80 2"
        )
        user_data_entry[message.chat.id] = 'wait_ride'
    elif message.text == 'Заправка':
        bot.send_message(message.chat.id, "Введіть кількість заправлених літрів:")
        user_data_entry[message.chat.id] = 'wait_refuel'

@bot.message_handler(func=lambda message: message.chat.id in user_data_entry and user_data_entry[message.chat.id] in ['wait_ride', 'wait_refuel'])
def process_custom_input(message):
    action = user_data_entry[message.chat.id]
    text = message.text.strip()
    
    if action == 'wait_refuel':
        try:
            liters = float(text.replace(',', '.'))
            if liters <= 0:
                raise ValueError
            current_fuel = user_fuel.get(message.chat.id, 0.0)
            new_fuel = current_fuel + liters
            user_fuel[message.chat.id] = new_fuel
            del user_data_entry[message.chat.id]
            bot.send_message(message.chat.id, f"Заправку додано! В баку тепер: {new_fuel:.1f} л.", reply_markup=get_markup())
        except ValueError:
            bot.send_message(message.chat.id, "Помилка! Введіть коректну додатну кількість літрів.")
            
    elif action == 'wait_ride':
        parts = text.split()
        current_year = datetime.now().year
        
        try:
            if len(parts) == 3:
                # Вказано дату, км та точки
                date_obj = datetime.strptime(parts[0], "%d.%m").replace(year=current_year)
                km = float(parts[1])
                points = int(parts[2])
            elif len(parts) == 2:
                # Дата сьогоднішня, вказано тільки км та точки
                date_obj = datetime.now()
                km = float(parts[0])
                points = int(parts[1])
            else:
                raise ValueError
                
            if km < 0 or points < 0:
                raise ValueError
                
        except ValueError:
            bot.send_message(
                message.chat.id,
                "Помилка формату. Перевірте, чи ви ввели додатні числа, та дотримуйтесь формату: [дата] [км] [точки]"
            )
            return

        del user_data_entry[message.chat.id]
        
        # Розрахунки
        earned_km = km * RATE_PER_KM
        earned_points = points * RATE_PER_POINT
        daily_total = earned_km + earned_points
        
        fuel_used = (km / 100) * FUEL_CONSUMPTION
        current_fuel = user_fuel.get(message.chat.id, 0.0)
        remaining_fuel = max(0.0, current_fuel - fuel_used)
        user_fuel[message.chat.id] = remaining_fuel
        
        response = (
            f"✅ Запис за {date_obj.strftime('%d.%m')} додано!\n"
            f"• За км: {earned_km:.1f} грн\n"
            f"• За точки: {earned_points:.1f} грн\n"
            f"• Всього за день: {daily_total:.1f} грн\n"
            f"• Витрачено палива: {fuel_used:.1f} л\n"
            f"• Залишок в баку: {remaining_fuel:.1f} л"
        )
        bot.send_message(message.chat.id, response, reply_markup=get_markup())

@bot.message_handler(func=lambda message: message.text == 'Звіт за місяць')
def send_report(message):
    current_fuel = user_fuel.get(message.chat.id, 0.0)
    bot.send_message(message.chat.id, f"📊 Статистика:\nПоточний залишок палива: {current_fuel:.1f} л.", reply_markup=get_markup())

bot.infinity_polling()
