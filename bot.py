import os
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
from flask import Flask
import json

# ======== Настройки ========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Неверный токен! Установите BOT_TOKEN в переменных окружения.")
bot = telebot.TeleBot(BOT_TOKEN)

MOSCOW_OFFSET = 3  # Московское время
ADMIN_USERNAME = "mrwarminster"  # Админ для создания ивентов/групп
GROUPS_FILE = "groups.json"

# ======== Мини-сервер для Render ========
app = Flask("")

@app.route("/")
def home():
    return "Бот живой!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_server, daemon=True).start()

# ======== Хранилище ========
events = {}
groups = {}

# Загрузка групп
if os.path.exists(GROUPS_FILE):
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        groups = json.load(f)

def save_groups():
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

# ======== Вспомогательные функции ========
def back_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Назад", callback_data="back_to_menu"))
    markup.add(types.InlineKeyboardButton("Закрыть", callback_data="close_message"))
    return markup

# ======== Проверка событий ========
def check_events():
    while True:
        now_utc = datetime.utcnow()
        for name, data in list(events.items()):
            event_time_utc = data["time_utc"]
            chat_id = data["chat_id"]
            notified = data["notified"]
            alerts = data["alerts"]
            members = data.get("members", [])

            for minutes_before in alerts:
                key = f"{minutes_before}m"
                if key not in notified:
                    delta = (event_time_utc - now_utc).total_seconds() / 60
                    if delta <= minutes_before:
                        if delta > 1440:
                            days = round(delta / 1440)
                            msg = f"⚔️ Событие '{name}' стартует через {days} дн в {(event_time_utc + timedelta(hours=MOSCOW_OFFSET)).strftime('%H:%M')} МСК!"
                        elif delta >= 60:
                            hours = round(delta / 60)
                            msg = f"⚔️ До '{name}' осталось {hours} час(а/ов)!"
                        else:
                            msg = f"⚔️ До '{name}' осталось {int(delta)} минут!"
                        member_str = " ".join(members) if members else ""
                        bot.send_message(chat_id, f"{msg} {member_str}")
                        notified.add(key)

            if event_time_utc <= now_utc < event_time_utc + timedelta(minutes=1) and "start" not in notified:
                member_str = " ".join(members) if members else ""
                bot.send_message(chat_id, f"🔥 '{name}' НАЧАЛСЯ! {member_str} Аминь! (Время: {(event_time_utc + timedelta(hours=MOSCOW_OFFSET)).strftime('%H:%M')} МСК)")
                notified.add("start")

            if now_utc > event_time_utc + timedelta(hours=2):
                del events[name]
        time.sleep(30)

threading.Thread(target=check_events, daemon=True).start()

# ======== Стартовое меню ========
@bot.message_handler(commands=['start'])
def start_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Все ивенты", callback_data="show_events"))
    markup.add(types.InlineKeyboardButton("Создать ивент", callback_data="create_event"))
    markup.add(types.InlineKeyboardButton("Создать группу", callback_data="create_group"))
    markup.add(types.InlineKeyboardButton("Все группы", callback_data="show_groups"))
    markup.add(types.InlineKeyboardButton("Общий сбор", callback_data="general_call"))
    bot.send_message(message.chat.id, "🤖 Бот для управления ивентами и группами.\nВыберите действие:", reply_markup=markup)

# ======== Команда /clear ========
@bot.message_handler(commands=['clear'])
def clear_events(message):
    username = message.from_user.username or ""
    if username.lower() != ADMIN_USERNAME.lower():
        bot.send_message(message.chat.id, f"⚠️ Для очистки ивентов обратитесь к @{ADMIN_USERNAME}")
        return
    events.clear()
    bot.send_message(message.chat.id, "✅ Все активные ивенты удалены.")

# ======== Обработка кнопок ========
@bot.callback_query_handler(func=lambda call: True)
def universal_callback(call):
    username = call.from_user.username or ""

    if call.data == "back_to_menu":
        start_menu(call.message)
    elif call.data == "close_message":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
    else:
        handle_buttons(call)

def handle_buttons(call):
    username = call.from_user.username or ""

    if call.data == "show_events":
        if not events:
            bot.send_message(call.message.chat.id, "📭 Нет активных ивентов.")
            return
        markup = types.InlineKeyboardMarkup()
        for name in events.keys():
            markup.add(types.InlineKeyboardButton(name, callback_data=f"event_{name}"))
        bot.send_message(call.message.chat.id, "Выберите ивент:", reply_markup=markup)

    elif call.data == "create_event":
        if username.lower() != ADMIN_USERNAME.lower():
            bot.send_message(call.message.chat.id, f"⚠️ Для создания или изменения ивентов обратитесь к @{ADMIN_USERNAME}")
            return
        msg = bot.send_message(call.message.chat.id, "Введите название нового ивента:")
        bot.register_next_step_handler(msg, step_event_name)

    elif call.data == "create_group":
        if username.lower() != ADMIN_USERNAME.lower():
            bot.send_message(call.message.chat.id, f"⚠️ Для создания или изменения групп обратитесь к @{ADMIN_USERNAME}")
            return
        msg = bot.send_message(call.message.chat.id, "Введите название группы:")
        bot.register_next_step_handler(msg, step_create_group)

    elif call.data == "show_groups":
        if not groups:
            bot.send_message(call.message.chat.id, "📭 Нет созданных групп.")
            return
        text = "Список групп:\n"
        for gname, members in groups.items():
            text += f"- {gname}: {' '.join(members) if members else 'Нет участников'}\n"
        bot.send_message(call.message.chat.id, text)

    elif call.data == "general_call":
        all_members = []
        for members in groups.values():
            all_members.extend(members)
        member_str = ' '.join(all_members)
        if member_str:
            bot.send_message(call.message.chat.id, f"⚔️ Общий сбор! {member_str}, все на старт! ⏳")
        else:
            bot.send_message(call.message.chat.id, "⚠️ Нет участников для общего сбора.")

# ======== Запуск бота ========
bot.infinity_polling()
