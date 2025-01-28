import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import requests
import sqlite3
import hashlib
import schedule
import time
from dotenv import load_dotenv

load_dotenv()

# Инициализация бота
TOKEN = os.getenv('TELEGRAM_TOKEN')
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Инициализация базы данных
conn = sqlite3.connect('vpn_subscriptions.db')
cursor = conn.cursor()

# Функции бота

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Купить VLESS и Shadowsocks (30р/месяц)", callback_data='buy_both')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Добро пожаловать! Выберите услугу:', reply_markup=reply_markup)

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'buy_both':
        query.edit_message_text(text='Вы выбрали подписку на VLESS и Shadowsocks. Перейдите по ссылке для оплаты:')
        send_payment_url(query.message.chat.id)

def send_payment_url(chat_id):
    payment_url = f"https://www.freekassa.ru/merchant/cash.php?m={os.getenv('MERCHANT_ID')}&oa=30&o={chat_id}&s=both"
    dispatcher.bot.send_message(chat_id=chat_id, text=payment_url)

def freekassa_callback(update: Update, context: CallbackContext) -> None:
    data = update.message.text.split('&')
    amount = next((d.split('=')[1] for d in data if d.startswith('AMOUNT')), None)
    user_id = next((d.split('=')[1] for d in data if d.startswith('MERCHANT_ORDER_ID')), None)
    sign = next((d.split('=')[1] for d in data if d.startswith('SIGN')), None)
    
    if amount == '30' and check_signature(data):
        update_subscription(user_id)
        update.message.reply_text('Ваша подписка успешно обновлена!')
    else:
        update.message.reply_text('Ошибка при проверке платежа.')

def check_signature(data):
    merchant_id = os.getenv('MERCHANT_ID')
    secret_key = os.getenv('FREEKASSA_SECRET_KEY')
    amount = next((d.split('=')[1] for d in data if d.startswith('AMOUNT')), None)
    user_id = next((d.split('=')[1] for d in data if d.startswith('MERCHANT_ORDER_ID')), None)
    
    signature_string = f"{merchant_id}:{amount}:{user_id}:{secret_key}"
    generated_signature = hashlib.md5(signature_string.encode()).hexdigest().upper()
    
    return generated_signature == sign

def update_subscription(user_id):
    vless_config = get_config('vless', user_id)
    shadowsocks_config = get_config('shadowsocks', user_id)
    
    if vless_config and shadowsocks_config:
        from datetime import datetime, timedelta
        expiration_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        cursor.execute('''
        INSERT OR REPLACE INTO subscriptions (user_id, vless_config, shadowsocks_config, expiration_date)
        VALUES (?, ?, ?, ?)
        ''', (user_id, vless_config, shadowsocks_config, expiration_date))
        
        conn.commit()
        dispatcher.bot.send_message(chat_id=user_id, text=f"VLESS конфигурация:\n{vless_config}\n\nShadowsocks конфигурация:\n{shadowsocks_config}")
    else:
        print("Ошибка при получении конфигураций от 3x-ui")

def get_config(protocol, user_id):
    response = requests.get(f"{os.getenv('XRAY_API_URL')}/api/config/{protocol}/{user_id}")
    if response.status_code == 200:
        return response.json()
    return None

def check_expirations():
    cursor.execute("SELECT user_id, expiration_date FROM subscriptions")
    for user_id, expiration_date in cursor.fetchall():
        if datetime.strptime(expiration_date, '%Y-%m-%d') < datetime.now():
            dispatcher.bot.send_message(chat_id=user_id, text="Ваша подписка истекла. Пожалуйста, оплатите продление.")
            # Здесь вы должны реализовать логику отключения пользователя в 3x-ui
            # Например, отправка запроса на отключение пользователя
            disable_user(user_id)

def disable_user(user_id):
    # Пример запроса для отключения пользователя в 3x-ui
    requests.post(f"{os.getenv('XRAY_API_URL')}/api/disable/{user_id}")

# Планировщик для проверки истечения срока действия подписок
schedule.every().day.at("00:00").do(check_expirations)

# Обработчики
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, freekassa_callback))

# Запуск бота
if __name__ == '__main__':
    updater.start_polling()
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверка каждую минуту
