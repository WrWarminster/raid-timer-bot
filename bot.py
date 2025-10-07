import telebot
import threading
import time
from datetime import datetime, timedelta
import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# ======== Хранилище ========
events = {}
groups = {}  # {"название группы": ["@user1", "@user2"]}

GROUPS_FILE = "groups.json"

# Загрузка групп из файла
if os.path.exists(GROUPS_FILE):
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        groups = json.load(f)

def save_groups():
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

# ======== Настройки уведомлений ========
STANDARD_ALERTS = [10, 60, 300, 720, 1440]  # мин: 10мин,1ч,5ч,12ч,24ч

# ======== Проверка событий ========
def check_events():
    while True:
        now = datetime.utcnow()  # UTC
        for name, data in list(events.items()):
            event_time = data["time"]
            chat_id = data["chat_id"]
            notified = data["notified"]
            members = data.get("members", [])

            # Событие более суток вперед
            delta_total = (event_time - now).total_seconds() / 60
            if delta_total > 1440:
                if "days" not in notified:
                    days_left = int(delta_total // 1440)
                    bot.send_message(chat_id, f"📅 Событие '{name}' стартует через {days_left} дн. В {(event_time + timedelta(hours=3)).strftime('%H:%M')} МСК!")
                    notified.add("days")
                continue

            # Стандартные уведомления
            for minutes_before in STANDARD_ALERTS:
                key = f"{minutes_before}m"
                if minutes_before > delta_total:
                    continue
                if key not in notified:
                    if minutes_before >= 60:
                        hours = minutes_before // 60
                        msg = f"⏳ До '{name}' осталось {hours} час(а/ов)! Подготовьтесь!"
                    else:
                        msg = f"⚔️ До '{name}' осталось {minutes_before} минут!"
                    member_str = " ".join(members) if members else ""
                    bot.send_message(chat_id, f"{msg} {member_str}")
                    notified.add(key)

            # Сообщение о начале события
            if event_time <= now < event_time + timedelta(minutes=1) and "start" not in notified:
                member_str = " ".join(members) if members else ""
                bot.send_message(chat_id, f"🔥 '{name}' НАЧАЛСЯ! {member_str}")
                notified.add("start")

            # Удаление старых событий
            if now > event_time + timedelta(hours=2):
                del events[name]

        time.sleep(30)

threading.Thread(target=check_events, daemon=True).start()

# ======== Команды ========
# Создать группу
@bot.message_handler(commands=['создать_группу'])
def create_group(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Формат: /создать_группу <название> <@участник1 @участник2 ...>")
        return
    name = parts[1].lower()
    members = parts[2].split()
    groups[name] = members
    save_groups()
    bot.reply_to(message, f"✅ Группа '{name}' создана: {' '.join(members)}")

# Создать ивент с учетом МСК
@bot.message_handler(commands=['создать_ивент'])
def create_event(message):
    try:
        parts = message.text.split()
        if len(parts) < 5:
            bot.reply_to(message, "⚠️ Формат: /создать_ивент <название> <YYYY-MM-DD> <HH:MM> <участники/группы/слово 'все'>")
            return
        name = parts[1].lower()
        date_str, time_str = parts[2], parts[3]
        raw_members = parts[4:]

        # Вводим МСК, конвертируем в UTC для сервера
        msk_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        event_time = msk_time - timedelta(hours=3)  # МСК → UTC

        final_members = []
        for m in raw_members:
            if m.lower() == "все":
                final_members = []
                break
            elif m.lower() in groups:
                final_members.extend(groups[m.lower()])
            else:
                final_members.append(m)

        events[name] = {"time": event_time, "chat_id": message.chat.id, "notified": set(), "members": final_members}
        bot.reply_to(message, f"✅ Ивент '{name}' создан на {msk_time.strftime('%d.%m.%Y %H:%M')} МСК\nУчастники: {' '.join(final_members) if final_members else 'Все'}")
    except ValueError:
        bot.reply_to(message, "⚠️ Неверный формат даты или времени. Пример: /создать_ивент рейд 2025-10-10 20:00 @user1 @user2")

# Команда созыв для всех участников чата
@bot.message_handler(commands=['созыв'])
def general_call(message):
    chat_id = message.chat.id
    all_members = []
    for members in groups.values():
        all_members.extend(members)
    member_str = ' '.join(all_members)
    if member_str:
        bot.send_message(chat_id, f"⚔️ Общий сбор! {member_str}, все к старту! ⏳")
    else:
        bot.send_message(chat_id, "⚠️ Нет участников для общего сбора.")

# Список событий
@bot.message_handler(commands=['ивенты'])
def list_events(message):
    if not events:
        bot.reply_to(message, "📭 Нет активных ивентов.")
        return
    text = "📅 Активные ивенты:\n"
    for name, data in events.items():
        text += f"• {name} — {(data['time'] + timedelta(hours=3)).strftime('%d.%m.%Y %H:%M')} МСК\n"
    bot.reply_to(message, text)

# Отмена события
@bot.message_handler(commands=['отменить_ивент'])
def cancel_event(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /отменить_ивент <название>")
        return
    name = parts[1].lower()
    if name in events:
        del events[name]
        bot.reply_to(message, f"🛑 Ивент '{name}' отменён.")
    else:
        bot.reply_to(message, f"❌ Ивент '{name}' не найден.")

# Команда /до — сколько времени осталось
@bot.message_handler(commands=['до'])
def time_left(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Формат: /до <название>")
        return
    name = parts[1].lower()
    if name not in events:
        bot.reply_to(message, f"❌ Ивент '{name}' не найден.")
        return
    now = datetime.utcnow()
    event_time = events[name]["time"]
    delta = event_time - now
    if delta.total_seconds() > 0:
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        bot.reply_to(message, f"✨ До '{name}' осталось: {days}д {hours:02}:{minutes:02}:{seconds:02}")
    else:
        bot.reply_to(message, f"🔥 '{name}' уже начался!")

# Команда помощь — список всех команд
@bot.message_handler(commands=['помощь'])
def help_commands(message):
    text = (
        "🤖 Список команд бота:\n\n"
        "/создать_группу <название> <@участник1 @участник2 ...> — создать новую группу\n"
        "/создать_ивент <название> <YYYY-MM-DD> <HH:MM> <участники/группы/слово 'все'> — создать событие\n"
        "/ивенты — показать все активные события\n"
        "/до <название> — сколько времени осталось до события\n"
        "/отменить_ивент <название> — отменить событие\n"
        "/созыв — общий сбор участников всех групп\n"
        "/помощь — показать это сообщение"
    )
    bot.reply_to(message, text)

bot.polling()
