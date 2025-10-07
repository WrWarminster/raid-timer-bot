import telebot
import threading
import time
from datetime import datetime, timedelta
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

events = {}

def check_events():
    while True:
        now = datetime.now()
        for name, data in list(events.items()):
            event_time = data["time"]
            chat_id = data["chat_id"]
            notified = data["notified"]
            alerts = data["alerts"]

            for minutes_before in alerts:
                key = f"{minutes_before}m"
                if event_time - timedelta(minutes=minutes_before) <= now < event_time - timedelta(minutes=minutes_before-1) and key not in notified:
                    if minutes_before >= 60:
                        hours = minutes_before // 60
                        msg = f"⏳ До '{name}' осталось {hours} час(а/ов)! Подготовьтесь, братья!"
                    else:
                        msg = f"⚔️ До '{name}' осталось {minutes_before} минут! Все к святилищу!"
                    bot.send_message(chat_id, msg)
                    notified.add(key)

            if event_time <= now < event_time + timedelta(minutes=1) and "start" not in notified:
                bot.send_message(chat_id, f"🔥 '{name}' НАЧАЛСЯ! Аминь!")
                notified.add("start")

            if now > event_time + timedelta(hours=2):
                del events[name]
        time.sleep(30)

threading.Thread(target=check_events, daemon=True).start()

@bot.message_handler(commands=['создать_ивент'])
def create_event(message):
    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.reply_to(message, "⚠️ Формат:\n/создать_ивент <название> <YYYY-MM-DD> <HH:MM> [оповещения_в_минутах]\nПример:\n/создать_ивент рейд 2025-10-10 20:00 60 15 5")
            return
        name = parts[1].lower()
        date_str, time_str = parts[2], parts[3]
        event_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        alerts = [int(x) for x in parts[4:]] if len(parts) > 4 else [60, 15, 5]
        events[name] = {"time": event_time, "chat_id": message.chat.id, "notified": set(), "alerts": alerts}
        alert_str = ", ".join(str(a) for a in alerts)
        bot.reply_to(message, f"✅ Ивент '{name}' создан на {event_time.strftime('%d.%m.%Y %H:%M')}\n🔔 Оповещения за: {alert_str} мин.")
    except ValueError:
        bot.reply_to(message, "⚠️ Неверный формат даты или времени. Пример: /создать_ивент рейд 2025-10-10 20:00 60 15 5")

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
    now = datetime.now()
    event_time = events[name]["time"]
    delta = event_time - now
    if delta.total_seconds() > 0:
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        bot.reply_to(message, f"✨ Аминь! До '{name}' осталось: {days}д {hours:02}:{minutes:02}:{seconds:02}")
    else:
        bot.reply_to(message, f"🔥 '{name}' уже начался!")

@bot.message_handler(commands=['ивенты'])
def list_events(message):
    if not events:
        bot.reply_to(message, "📭 Нет активных ивентов.")
        return
    text = "📅 Активные ивенты:\n"
    for name, data in events.items():
        text += f"• {name} — {data['time'].strftime('%d.%m.%Y %H:%M')}\n"
    bot.reply_to(message, text)

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

bot.polling()
