import os
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
import pytz
from flask import Flask

# ======== Настройки ========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Неверный токен! Установите BOT_TOKEN в переменных окружения.")
bot = telebot.TeleBot(BOT_TOKEN)

# Московское время
tz = pytz.timezone("Europe/Moscow")

# ======== Мини-сервер для Render ========
app = Flask("")

@app.route("/")
def home():
    return "Бот живой!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_server, daemon=True).start()

# ======== Хранилище ивентов ========
events = {}

# ======== Проверка и уведомления ========
def check_events():
    while True:
        now = datetime.now(tz)
        for name, data in list(events.items()):
            event_time = data["time"]
            chat_id = data["chat_id"]
            notified = data["notified"]
            alerts = data["alerts"]
            members = data.get("members", [])

            # Умные уведомления
            for minutes_before in alerts:
                key = f"{minutes_before}m"
                if key not in notified:
                    delta = (event_time - now).total_seconds() / 60
                    if delta <= minutes_before:
                        if delta > 1440:
                            days = round(delta / 1440)
                            msg = f"⚔️ Событие '{name}' стартует через {days} дн в {event_time.strftime('%H:%M')} МСК! Готовьтесь!"
                        elif delta >= 60:
                            hours = round(delta / 60)
                            msg = f"⚔️ До '{name}' осталось {hours} час(а/ов)!"
                        else:
                            msg = f"⚔️ До '{name}' осталось {int(delta)} минут!"
                        member_str = " ".join(members) if members else ""
                        bot.send_message(chat_id, f"{msg} {member_str}")
                        notified.add(key)

            # Финальное уведомление при старте
            if event_time <= now < event_time + timedelta(minutes=1) and "start" not in notified:
                member_str = " ".join(members) if members else ""
                bot.send_message(chat_id, f"🔥 '{name}' НАЧАЛСЯ! {member_str} Аминь! (Время: {event_time.strftime('%H:%M')} МСК)")
                notified.add("start")

            # Удаление старых ивентов через 2 часа после старта
            if now > event_time + timedelta(hours=2):
                del events[name]
        time.sleep(30)

threading.Thread(target=check_events, daemon=True).start()

# ======== Стартовое меню ========
@bot.message_handler(commands=['start'])
def start_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Все ивенты", callback_data="show_events"))
    markup.add(types.InlineKeyboardButton("Создать ивент", callback_data="create_event"))
    markup.add(types.InlineKeyboardButton("Общий сбор", callback_data="general_call"))

    bot.send_message(message.chat.id, 
                     "🤖 Этот бот создан для удобного создания ивентов в вашем чате!\nС ним вы можете создавать ивенты, добавлять участников и делать общий сбор.\nВыберите действие:", 
                     reply_markup=markup)

# ======== Обработка кнопок ========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "show_events":
        if not events:
            bot.send_message(call.message.chat.id, "📭 Нет активных ивентов.")
            return
        markup = types.InlineKeyboardMarkup()
        for name in events.keys():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"event_{name}"))
        bot.send_message(call.message.chat.id, "Выберите ивент:", reply_markup=markup)

    elif call.data == "create_event":
        msg = bot.send_message(call.message.chat.id, "Введите название нового ивента:")
        bot.register_next_step_handler(msg, step_event_name)

    elif call.data == "general_call":
        try:
            members = []
            for member in bot.get_chat_administrators(call.message.chat.id):
                if hasattr(member, "user") and member.user.username and "bot" not in member.user.username.lower():
                    members.append(f"@{member.user.username}")
            member_str = " ".join(members)
            if member_str:
                bot.send_message(call.message.chat.id, f"⚔️ Общий сбор! {member_str}, все на старт! ⏳")
            else:
                bot.send_message(call.message.chat.id, "⚠️ Не удалось найти участников для общего сбора.")
        except:
            bot.send_message(call.message.chat.id, "⚠️ Ошибка при получении участников чата.")

# ======== Шаги создания ивента ========
def step_event_name(message):
    event_name = message.text.lower()
    message.chat.event_name = event_name
    msg = bot.send_message(message.chat.id, "Введите дату и время (например, 09.10.2025 18:00):")
    bot.register_next_step_handler(msg, step_event_datetime)

def step_event_datetime(message):
    try:
        dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        dt = tz.localize(dt)
        message.chat.event_time = dt
        msg = bot.send_message(message.chat.id, "Введите участников (через @username), через пробел, или оставьте пустым для всех:")
        bot.register_next_step_handler(msg, step_event_members)
    except:
        msg = bot.send_message(message.chat.id, "⚠️ Неверный формат даты. Попробуйте снова:")
        bot.register_next_step_handler(msg, step_event_datetime)

def step_event_members(message):
    members = message.text.split() if message.text.strip() else []
    event_name = message.chat.event_name
    event_time = message.chat.event_time
    events[event_name] = {
        "time": event_time,
        "chat_id": message.chat.id,
        "members": members,
        "notified": set(),
        "alerts": [10, 60, 300, 720, 1440, 2880]  # 10мин,1ч,5ч,12ч,1д,2д
    }
    bot.send_message(message.chat.id, f"✅ Ивент '{event_name}' создан на {event_time.strftime('%d.%m.%Y %H:%M')} МСК. Участники: {' '.join(members) if members else 'Все'}")

# ======== Запуск бота ========
bot.infinity_polling()
