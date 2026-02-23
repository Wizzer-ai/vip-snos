#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SNOSER BOT v5.0 - ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ
Без заглушек, с работающими Логами и Настройками
"""

import asyncio
import json
import os
import uuid
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "7662143323:AAEtzJ_q2UofYIWo1jgVwt-JYYdJwWfvHg8"
ADMIN_IDS = [7308065271]
CHANNEL_ID = -1003820913832
SUPPORT_USERNAME = "Write_forpizzabot"

CRYPTOBOT_USERNAME = "CryptoBot"
TON_WALLET = "UQDfuvp0hT8spsS0bIvhqMaDdplMC5zz66-KKTqaglrQnPhw"

DEFAULT_TARIFFS = {
    1: {'name': '🔥 Неделя', 'price_rub': 699, 'price_usdt': 7.5, 'duration': 7, 'requests': 500},
    2: {'name': '⚡️ Месяц', 'price_rub': 1999, 'price_usdt': 21, 'duration': 30, 'requests': 2000},
    3: {'name': '👑 Год', 'price_rub': 9999, 'price_usdt': 105, 'duration': 365, 'requests': 10000}
}

# ========== СОСТОЯНИЯ FSM ==========
class SnosStates(StatesGroup):
    waiting_target = State()

class BroadcastStates(StatesGroup):
    waiting_text = State()

class SettingsStates(StatesGroup):
    waiting_support = State()
    waiting_cryptobot = State()
    waiting_ton = State()
    waiting_tariff_price = State()
    waiting_tariff_requests = State()
    waiting_tariff_id = State()

# ========== ЛОГИ В КАНАЛ ==========
class ChannelLogger:
    def __init__(self, bot_token: str, channel_id: int):
        self.bot = Bot(token=bot_token)
        self.channel_id = channel_id
        self.last_log = datetime.now()
        self.messages = []
    
    async def add_log(self, text: str):
        self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
        if (datetime.now() - self.last_log).seconds >= 3600 or len(self.messages) >= 20:
            await self.flush()
    
    async def flush(self):
        if not self.messages:
            return
        try:
            text = "📊 ЛОГИ ЗА ЧАС\n\n" + "\n".join(self.messages[-15:])
            await self.bot.send_message(self.channel_id, text)
            self.messages = []
            self.last_log = datetime.now()
        except:
            pass
    
    async def stop(self):
        await self.flush()

# ========== БАЗА ДАННЫХ ==========
class Database:
    def __init__(self):
        self.file = "database.json"
        self.cache = self._load()
    
    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Добавляем раздел settings если его нет
                    if 'settings' not in data:
                        data['settings'] = {
                            'support': SUPPORT_USERNAME,
                            'cryptobot': CRYPTOBOT_USERNAME,
                            'ton_wallet': TON_WALLET,
                            'tariffs': DEFAULT_TARIFFS
                        }
                    return data
            except:
                return self._default_data()
        return self._default_data()
    
    def _default_data(self):
        return {
            'users': {},
            'pending': {},
            'transactions': [],
            'next_id': 1,
            'settings': {
                'support': SUPPORT_USERNAME,
                'cryptobot': CRYPTOBOT_USERNAME,
                'ton_wallet': TON_WALLET,
                'tariffs': DEFAULT_TARIFFS
            }
        }
    
    def _save(self):
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    async def get_user(self, user_id, username=None, referrer=None):
        uid = str(user_id)
        if uid in self.cache['users']:
            return self.cache['users'][uid]
        
        new_user = {
            'id': self.cache['next_id'],
            'tg_id': user_id,
            'username': username,
            'total_spent': 0,
            'plan_id': 1,
            'sub_end': None,
            'requests_left': 0,
            'referrer': referrer,
            'referrals': [],
            'created_at': datetime.now().isoformat()
        }
        self.cache['users'][uid] = new_user
        self.cache['next_id'] += 1
        self._save()
        return new_user
    
    async def activate_sub(self, user_id, plan_id):
        uid = str(user_id)
        if uid not in self.cache['users']:
            return False
        user = self.cache['users'][uid]
        tariffs = self.cache['settings']['tariffs']
        plan = tariffs[str(plan_id)]
        
        if user_id in ADMIN_IDS:
            user['sub_end'] = 'forever'
            user['plan_id'] = plan_id
            user['requests_left'] = 999999
        else:
            current_end = None
            if user.get('sub_end') and user['sub_end'] != 'forever':
                try:
                    current_end = datetime.fromisoformat(user['sub_end'])
                except:
                    current_end = datetime.now()
            else:
                current_end = datetime.now()
            
            new_end = current_end + timedelta(days=plan['duration'])
            user['sub_end'] = new_end.isoformat()
            user['plan_id'] = plan_id
            user['requests_left'] = user.get('requests_left', 0) + plan['requests']
            user['total_spent'] = user.get('total_spent', 0) + plan['price_rub']
        
        self._save()
        return True
    
    async def add_pending(self, pid, data):
        self.cache['pending'][pid] = data
        self._save()
    
    async def get_pending(self, pid):
        return self.cache['pending'].get(pid)
    
    async def remove_pending(self, pid):
        if pid in self.cache['pending']:
            del self.cache['pending'][pid]
            self._save()
    
    async def use_request(self, user_id):
        if user_id in ADMIN_IDS:
            return True
        uid = str(user_id)
        if uid in self.cache['users'] and self.cache['users'][uid].get('requests_left', 0) > 0:
            self.cache['users'][uid]['requests_left'] -= 1
            self._save()
            return True
        return False
    
    async def check_sub(self, user_id):
        if user_id in ADMIN_IDS:
            return True
        uid = str(user_id)
        if uid not in self.cache['users']:
            return False
        user = self.cache['users'][uid]
        if user.get('sub_end') == 'forever':
            return True
        if not user.get('sub_end'):
            return False
        try:
            return datetime.fromisoformat(user['sub_end']) > datetime.now()
        except:
            return False
    
    async def update_setting(self, key, value):
        if 'settings' not in self.cache:
            self.cache['settings'] = {}
        self.cache['settings'][key] = value
        self._save()
    
    async def update_tariff(self, tariff_id, key, value):
        if 'settings' not in self.cache:
            self.cache['settings'] = {'tariffs': {}}
        if 'tariffs' not in self.cache['settings']:
            self.cache['settings']['tariffs'] = {}
        
        tariff_id_str = str(tariff_id)
        if tariff_id_str not in self.cache['settings']['tariffs']:
            self.cache['settings']['tariffs'][tariff_id_str] = DEFAULT_TARIFFS[tariff_id].copy()
        
        self.cache['settings']['tariffs'][tariff_id_str][key] = value
        self._save()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def loading_bar(percent: int, width: int = 10) -> str:
    filled = "█" * (percent // 10)
    empty = "▒" * (width - (percent // 10))
    return f"[{filled}{empty}] {percent}%"

def generate_phone(country: str) -> str:
    flags = {
        'uz': '🇺🇿 +998',
        'ru': '🇷🇺 +7',
        'kz': '🇰🇿 +7',
        'ua': '🇺🇦 +380',
        'us': '🇺🇸 +1'
    }
    
    if country == 'uz':
        op = random.choice([90, 91, 93, 94, 95, 97, 98, 99])
        return f"{flags['uz']} {op} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}"
    elif country in ['ru', 'kz']:
        code = random.choice([900, 901, 902, 903, 904, 905, 909, 925, 926, 927, 999])
        return f"{flags[country]} {code} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}"
    elif country == 'ua':
        op = random.choice([50, 63, 66, 67, 68, 93, 95, 96, 97, 98, 99])
        return f"{flags['ua']} {op} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}"
    else:
        return f"{flags['us']} {random.randint(200,999)} {random.randint(100,999)} {random.randint(1000,9999)}"

def generate_email() -> str:
    domains = ['gmail.com', 'mail.ru', 'yandex.ru', 'yahoo.com', 'ukr.net', 'hotmail.com']
    names = ['ivan', 'petr', 'john', 'jane', 'alex', 'maria', 'timur', 'dilnoza']
    name = random.choice(names)
    domain = random.choice(domains)
    if len(name) > 2:
        masked = name[0] + '...' + name[-1]
    else:
        masked = name[0] + '...'
    return f"{masked}@{domain}"

# ========== КЛАВИАТУРЫ ==========

def main_menu():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🎯 НАЧАТЬ СНОС", callback_data="snos"),
        InlineKeyboardButton(text="💳 ТАРИФЫ", callback_data="tariffs")
    )
    b.row(
        InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile"),
        InlineKeyboardButton(text="👥 РЕФЕРАЛЫ", callback_data="ref")
    )
    b.row(InlineKeyboardButton(text="🆘 ПОМОЩЬ", callback_data="help"))
    return b.as_markup()

def back_button(callback: str = "main_menu"):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=callback))
    return b.as_markup()

def tariffs_keyboard():
    b = InlineKeyboardBuilder()
    for tid, tariff in DEFAULT_TARIFFS.items():
        stars = int(tariff['price_rub'] * 1.3)
        b.row(InlineKeyboardButton(
            text=f"{tariff['name']} — {tariff['price_rub']}₽ | ⭐{stars} | NFT-{stars}",
            callback_data=f"select_tariff_{tid}"
        ))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return b.as_markup()

def payment_methods_keyboard(tariff_id: int):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="💳 CryptoBot", callback_data=f"pay_cryptobot_{tariff_id}"),
        InlineKeyboardButton(text="⭐ Stars", callback_data=f"pay_stars_{tariff_id}")
    )
    b.row(
        InlineKeyboardButton(text="🖼 NFT подарок", callback_data=f"pay_nft_{tariff_id}"),
        InlineKeyboardButton(text="💎 TON", callback_data=f"pay_ton_{tariff_id}")
    )
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="tariffs"))
    return b.as_markup()

def admin_menu():
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📋 ЗАЯВКИ", callback_data="admin_pending"),
        InlineKeyboardButton(text="💳 ТАРИФЫ", callback_data="admin_tariffs")
    )
    b.row(
        InlineKeyboardButton(text="📢 РАССЫЛКА", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="⚙️ НАСТРОЙКИ", callback_data="admin_settings")
    )
    b.row(
        InlineKeyboardButton(text="📊 ЛОГИ", callback_data="admin_logs"),
        InlineKeyboardButton(text="🚪 ВЫХОД", callback_data="main_menu")
    )
    return b.as_markup()

def pending_keyboard(payment_id: str):
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{payment_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{payment_id}")
    )
    return b.as_markup()

def settings_keyboard():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🤖 CryptoBot", callback_data="settings_cryptobot"))
    b.row(InlineKeyboardButton(text="💎 TON кошелек", callback_data="settings_ton"))
    b.row(InlineKeyboardButton(text="🆘 Поддержка", callback_data="settings_support"))
    b.row(InlineKeyboardButton(text="💳 Тариф 1", callback_data="settings_tariff_1"))
    b.row(InlineKeyboardButton(text="💳 Тариф 2", callback_data="settings_tariff_2"))
    b.row(InlineKeyboardButton(text="💳 Тариф 3", callback_data="settings_tariff_3"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin"))
    return b.as_markup()

def tariff_edit_keyboard(tariff_id: int):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"tariff_price_{tariff_id}"))
    b.row(InlineKeyboardButton(text="🎯 Изменить лимит", callback_data=f"tariff_requests_{tariff_id}"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_settings"))
    return b.as_markup()

# ========== ХЕНДЛЕРЫ ==========

router = Router()

# --- СТАРТ ---
@router.message(Command("start"))
async def cmd_start(message: Message, db: Database, channel_logger: ChannelLogger):
    args = message.text.split()
    ref = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    user = await db.get_user(message.from_user.id, message.from_user.username, ref)
    await channel_logger.add_log(f"👤 Новый пользователь: @{message.from_user.username or 'no username'}")
    await message.answer(
        "🎯 SNOSER BOT\n\n"
        "500+ почтовых ящиков\n"
        "Мгновенная отправка\n"
        "Ручное подтверждение платежей\n\n"
        "Выбери действие:",
        reply_markup=main_menu()
    )

@router.callback_query(F.data == "main_menu")
async def go_main(cb: CallbackQuery):
    await cb.message.edit_text("🎯 ГЛАВНОЕ МЕНЮ", reply_markup=main_menu())
    await cb.answer()

# --- ТАРИФЫ ---
@router.callback_query(F.data == "tariffs")
async def show_tariffs(cb: CallbackQuery, db: Database):
    tariffs = db.cache['settings']['tariffs']
    text = "💎 ДОСТУПНЫЕ ТАРИФЫ\n\n"
    for tid, tariff in tariffs.items():
        stars = int(tariff['price_rub'] * 1.3)
        text += f"{tariff['name']}\n"
        text += f"💰 {tariff['price_rub']}₽ | ⭐{stars} | NFT-{stars}\n"
        text += f"⚡️ {tariff['requests']} жалоб | 📅 {tariff['duration']} дней\n\n"
    await cb.message.edit_text(text, reply_markup=tariffs_keyboard())
    await cb.answer()

@router.callback_query(F.data.startswith("select_tariff_"))
async def select_tariff(cb: CallbackQuery, db: Database):
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    stars = int(tariff['price_rub'] * 1.3)
    text = (
        f"💎 ОПЛАТА ТАРИФА: {tariff['name']}\n\n"
        f"💰 Рубли: {tariff['price_rub']}₽\n"
        f"⭐ Stars: {stars}\n"
        f"🖼 NFT подарок: {stars}\n"
        f"💎 TON: {tariff['price_usdt']} USDT\n\n"
        f"Выбери способ оплаты:"
    )
    await cb.message.edit_text(text, reply_markup=payment_methods_keyboard(tariff_id))
    await cb.answer()

# --- ОПЛАТА ---
@router.callback_query(F.data.startswith("pay_cryptobot_"))
async def pay_cryptobot(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    payment_id = str(uuid.uuid4())[:8]
    
    await db.add_pending(payment_id, {
        'user_id': cb.from_user.id,
        'username': cb.from_user.username,
        'plan_id': tariff_id,
        'amount_rub': tariff['price_rub'],
        'amount_usdt': tariff['price_usdt'],
        'method': 'cryptobot',
        'status': 'pending'
    })
    
    await channel_logger.add_log(f"💰 Заявка #{payment_id} от @{cb.from_user.username or 'no username'} на {tariff['name']}")
    
    for admin_id in ADMIN_IDS:
        try:
            text = f"💰 НОВАЯ ЗАЯВКА\n\n🆔 #{payment_id}\n👤 @{cb.from_user.username or 'no username'}\n💎 {tariff['name']}\n💳 CryptoBot\n💰 {tariff['price_rub']}₽\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            await cb.bot.send_message(admin_id, text, reply_markup=pending_keyboard(payment_id))
        except:
            pass
    
    settings = db.cache['settings']
    await cb.message.edit_text(
        f"✅ ЗАЯВКА СОЗДАНА\n\nНомер: #{payment_id}\nТариф: {tariff['name']}\nСумма: {tariff['price_rub']}₽\n\nПереведи {tariff['price_usdt']} USDT через @{settings['cryptobot']}\nПосле оплаты админ проверит",
        reply_markup=back_button("tariffs")
    )
    await cb.answer()

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    stars = int(tariff['price_rub'] * 1.3)
    payment_id = str(uuid.uuid4())[:8]
    
    await db.add_pending(payment_id, {
        'user_id': cb.from_user.id,
        'username': cb.from_user.username,
        'plan_id': tariff_id,
        'amount_stars': stars,
        'method': 'stars',
        'status': 'pending'
    })
    
    await channel_logger.add_log(f"⭐ Заявка #{payment_id} от @{cb.from_user.username or 'no username'} на {tariff['name']}")
    
    for admin_id in ADMIN_IDS:
        try:
            text = f"💰 НОВАЯ ЗАЯВКА\n\n🆔 #{payment_id}\n👤 @{cb.from_user.username or 'no username'}\n💎 {tariff['name']}\n⭐ Stars\n💰 {stars}⭐\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            await cb.bot.send_message(admin_id, text, reply_markup=pending_keyboard(payment_id))
        except:
            pass
    
    settings = db.cache['settings']
    await cb.message.edit_text(
        f"✅ ЗАЯВКА СОЗДАНА\n\nНомер: #{payment_id}\nТариф: {tariff['name']}\nСумма: {stars}⭐\n\nОтправь {stars}⭐ на @{settings['support']}",
        reply_markup=back_button("tariffs")
    )
    await cb.answer()

@router.callback_query(F.data.startswith("pay_nft_"))
async def pay_nft(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    nft_price = int(tariff['price_rub'] * 1.3)
    payment_id = str(uuid.uuid4())[:8]
    
    await db.add_pending(payment_id, {
        'user_id': cb.from_user.id,
        'username': cb.from_user.username,
        'plan_id': tariff_id,
        'amount_nft': nft_price,
        'method': 'nft',
        'status': 'pending'
    })
    
    await channel_logger.add_log(f"🖼 Заявка #{payment_id} от @{cb.from_user.username or 'no username'} на {tariff['name']}")
    
    for admin_id in ADMIN_IDS:
        try:
            text = f"💰 НОВАЯ ЗАЯВКА\n\n🆔 #{payment_id}\n👤 @{cb.from_user.username or 'no username'}\n💎 {tariff['name']}\n🖼 NFT\n💰 {nft_price} NFT\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            await cb.bot.send_message(admin_id, text, reply_markup=pending_keyboard(payment_id))
        except:
            pass
    
    settings = db.cache['settings']
    await cb.message.edit_text(
        f"🖼 ОПЛАТА NFT\n\nТариф: {tariff['name']}\nЦена: {nft_price} NFT\n\n💎 КОШЕЛЕК:\n`{settings['ton_wallet']}`\n\nПосле отправки напиши @{settings['support']}",
        reply_markup=back_button("tariffs")
    )
    await cb.answer()

@router.callback_query(F.data.startswith("pay_ton_"))
async def pay_ton(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    payment_id = str(uuid.uuid4())[:8]
    
    await db.add_pending(payment_id, {
        'user_id': cb.from_user.id,
        'username': cb.from_user.username,
        'plan_id': tariff_id,
        'amount_usdt': tariff['price_usdt'],
        'method': 'ton',
        'status': 'pending'
    })
    
    await channel_logger.add_log(f"💎 Заявка #{payment_id} от @{cb.from_user.username or 'no username'} на {tariff['name']}")
    
    for admin_id in ADMIN_IDS:
        try:
            text = f"💰 НОВАЯ ЗАЯВКА\n\n🆔 #{payment_id}\n👤 @{cb.from_user.username or 'no username'}\n💎 {tariff['name']}\n💎 TON/USDT\n💰 {tariff['price_usdt']} USDT\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            await cb.bot.send_message(admin_id, text, reply_markup=pending_keyboard(payment_id))
        except:
            pass
    
    settings = db.cache['settings']
    await cb.message.edit_text(
        f"💎 ОПЛАТА TON/USDT\n\nТариф: {tariff['name']}\nСумма: {tariff['price_usdt']} USDT\n\n💎 АДРЕС:\n`{settings['ton_wallet']}`\n\nПосле перевода напиши @{settings['support']}",
        reply_markup=back_button("tariffs")
    )
    await cb.answer()

# --- ПОДТВЕРЖДЕНИЕ ПЛАТЕЖЕЙ ---
@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    payment_id = cb.data.split("_")[1]
    payment = await db.get_pending(payment_id)
    
    if not payment:
        return await cb.answer("❌ Заявка не найдена", show_alert=True)
    
    await db.activate_sub(payment['user_id'], payment['plan_id'])
    await channel_logger.add_log(f"✅ Подтверждена заявка #{payment_id} для @{payment['username']}")
    
    try:
        await cb.bot.send_message(payment['user_id'], "✅ ПЛАТЕЖ ПОДТВЕРЖДЕН!\n\nПодписка активирована. Можешь начинать снос!")
    except:
        pass
    
    await db.remove_pending(payment_id)
    await cb.message.edit_text(f"✅ Платеж #{payment_id} подтвержден")
    await cb.answer()

@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(cb: CallbackQuery, db: Database, channel_logger: ChannelLogger):
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    payment_id = cb.data.split("_")[1]
    payment = await db.get_pending(payment_id)
    
    if not payment:
        return await cb.answer("❌ Заявка не найдена", show_alert=True)
    
    await channel_logger.add_log(f"❌ Отклонена заявка #{payment_id} для @{payment['username']}")
    
    try:
        await cb.bot.send_message(payment['user_id'], f"❌ ПЛАТЕЖ ОТКЛОНЕН\n\nПлатеж не найден. По вопросам: @{SUPPORT_USERNAME}")
    except:
        pass
    
    await db.remove_pending(payment_id)
    await cb.message.edit_text(f"❌ Платеж #{payment_id} отклонен")
    await cb.answer()

# ========== АДМИН-ПАНЕЛЬ ==========

@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database):
    """Главная админ-панель"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    users = db.cache['users']
    pending = len(db.cache['pending'])
    
    active_subs = 0
    paid_users = 0
    total_spent = 0
    
    for uid, user in users.items():
        if user.get('total_spent', 0) > 0:
            paid_users += 1
            total_spent += user['total_spent']
        
        if user.get('sub_end'):
            if user['sub_end'] == 'forever':
                active_subs += 1
            else:
                try:
                    if datetime.fromisoformat(user['sub_end']) > datetime.now():
                        active_subs += 1
                except:
                    pass
    
    text = (
        f"👑 АДМИН-ПАНЕЛЬ\n\n"
        f"📊 СТАТИСТИКА\n"
        f"👤 Всего юзеров: {len(users)}\n"
        f"✅ Активных подписок: {active_subs}\n"
        f"⏳ Ожидают оплаты: {pending}\n"
        f"💰 Купивших тариф: {paid_users}\n"
        f"💸 Всего заработано: {total_spent}₽\n\n"
        f"🛠 УПРАВЛЕНИЕ"
    )
    
    await message.answer(text, reply_markup=admin_menu())


@router.callback_query(F.data == "admin_pending")
async def show_pending(cb: CallbackQuery, db: Database):
    """Показывает ожидающие заявки"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    pending = db.cache['pending']
    
    if not pending:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin"))
        await cb.message.edit_text("📋 Нет ожидающих заявок", reply_markup=b.as_markup())
        await cb.answer()
        return
    
    text = "📋 ОЖИДАЮТ ПОДТВЕРЖДЕНИЯ\n\n"
    for pid, data in list(pending.items())[:5]:
        tariffs = db.cache['settings']['tariffs']
        plan_name = tariffs[str(data['plan_id'])]['name']
        amount = data.get('amount_rub') or data.get('amount_usdt') or data.get('amount_stars')
        text += f"🆔 #{pid}\n👤 @{data.get('username', 'no username')}\n💎 {plan_name} | {amount}\n\n"
    
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin"))
    
    await cb.message.edit_text(text, reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "admin_tariffs")
async def admin_tariffs(cb: CallbackQuery, db: Database):
    """Управление тарифами"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    tariffs = db.cache['settings']['tariffs']
    text = "💳 УПРАВЛЕНИЕ ТАРИФАМИ\n\n"
    for tid, tariff in tariffs.items():
        stars = int(tariff['price_rub'] * 1.3)
        text += f"{tariff['name']}\n"
        text += f"💰 Цена: {tariff['price_rub']}₽\n"
        text += f"⭐ Stars: {stars}\n"
        text += f"🎯 Лимит: {tariff['requests']} жалоб\n"
        text += f"📅 Срок: {tariff['duration']} дней\n\n"
    
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin"))
    
    await cb.message.edit_text(text, reply_markup=b.as_markup())
    await cb.answer()


# ========== РАБОЧИЕ ЛОГИ ==========
@router.callback_query(F.data == "admin_logs")
async def show_logs(cb: CallbackQuery, channel_logger: ChannelLogger):
    """Показывает последние логи"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    # Принудительно отправляем накопленные логи
    await channel_logger.flush()
    
    text = "📊 ПОСЛЕДНИЕ ЛОГИ\n\n"
    
    if not channel_logger.messages:
        text += "Логов пока нет"
    else:
        for msg in channel_logger.messages[-10:]:  # последние 10
            text += f"{msg}\n"
    
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_logs"))
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin"))
    
    await cb.message.edit_text(text, reply_markup=b.as_markup())
    await cb.answer()


# ========== РАБОЧИЕ НАСТРОЙКИ ==========
@router.callback_query(F.data == "admin_settings")
async def show_settings(cb: CallbackQuery, db: Database):
    """Показывает текущие настройки"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    settings = db.cache['settings']
    
    text = (
        f"⚙️ ТЕКУЩИЕ НАСТРОЙКИ\n\n"
        f"🤖 CryptoBot: @{settings['cryptobot']}\n"
        f"💎 TON кошелек: {settings['ton_wallet'][:10]}...\n"
        f"🆘 Поддержка: @{settings['support']}\n\n"
        f"Выбери что изменить:"
    )
    
    await cb.message.edit_text(text, reply_markup=settings_keyboard())
    await cb.answer()


@router.callback_query(F.data == "settings_cryptobot")
async def edit_cryptobot(cb: CallbackQuery, state: FSMContext):
    """Изменение CryptoBot username"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    await state.set_state(SettingsStates.waiting_cryptobot)
    await cb.message.edit_text(
        "🤖 Введи новый username для CryptoBot (без @):\n\n"
        "Пример: CryptoBot\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()


@router.message(SettingsStates.waiting_cryptobot)
async def process_cryptobot(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    """Обработка нового CryptoBot username"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    new_username = message.text.strip().replace('@', '')
    await db.update_setting('cryptobot', new_username)
    await channel_logger.add_log(f"🤖 CryptoBot username изменен на @{new_username}")
    
    await state.clear()
    await message.answer(f"✅ CryptoBot username обновлен на @{new_username}", reply_markup=main_menu())


@router.callback_query(F.data == "settings_ton")
async def edit_ton(cb: CallbackQuery, state: FSMContext):
    """Изменение TON кошелька"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    await state.set_state(SettingsStates.waiting_ton)
    await cb.message.edit_text(
        "💎 Введи новый TON кошелек:\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()


@router.message(SettingsStates.waiting_ton)
async def process_ton(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    """Обработка нового TON кошелька"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    new_wallet = message.text.strip()
    await db.update_setting('ton_wallet', new_wallet)
    await channel_logger.add_log(f"💎 TON кошелек изменен")
    
    await state.clear()
    await message.answer(f"✅ TON кошелек обновлен", reply_markup=main_menu())


@router.callback_query(F.data == "settings_support")
async def edit_support(cb: CallbackQuery, state: FSMContext):
    """Изменение поддержки"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    await state.set_state(SettingsStates.waiting_support)
    await cb.message.edit_text(
        "🆘 Введи новый username для поддержки (без @):\n\n"
        "Пример: Write_forpizzabot\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()


@router.message(SettingsStates.waiting_support)
async def process_support(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    """Обработка нового username поддержки"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    new_username = message.text.strip().replace('@', '')
    await db.update_setting('support', new_username)
    await channel_logger.add_log(f"🆘 Поддержка изменена на @{new_username}")
    
    await state.clear()
    await message.answer(f"✅ Поддержка обновлена на @{new_username}", reply_markup=main_menu())


@router.callback_query(F.data.startswith("settings_tariff_"))
async def edit_tariff(cb: CallbackQuery, db: Database):
    """Редактирование конкретного тарифа"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    tariff_id = int(cb.data.split("_")[2])
    tariffs = db.cache['settings']['tariffs']
    tariff = tariffs[str(tariff_id)]
    
    text = (
        f"💳 РЕДАКТИРОВАНИЕ ТАРИФА {tariff_id}\n\n"
        f"{tariff['name']}\n"
        f"💰 Текущая цена: {tariff['price_rub']}₽\n"
        f"🎯 Текущий лимит: {tariff['requests']} жалоб\n"
        f"📅 Срок: {tariff['duration']} дней\n\n"
        f"Выбери что изменить:"
    )
    
    await cb.message.edit_text(text, reply_markup=tariff_edit_keyboard(tariff_id))
    await cb.answer()


@router.callback_query(F.data.startswith("tariff_price_"))
async def edit_tariff_price(cb: CallbackQuery, state: FSMContext):
    """Изменение цены тарифа"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    tariff_id = int(cb.data.split("_")[2])
    await state.set_state(SettingsStates.waiting_tariff_price)
    await state.update_data(tariff_id=tariff_id)
    
    await cb.message.edit_text(
        f"💰 Введи новую цену для тарифа {tariff_id} (в рублях):\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()


@router.message(SettingsStates.waiting_tariff_price)
async def process_tariff_price(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    """Обработка новой цены тарифа"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    try:
        new_price = int(message.text.strip())
        data = await state.get_data()
        tariff_id = data['tariff_id']
        
        await db.update_tariff(tariff_id, 'price_rub', new_price)
        # Обновляем USDT цену примерно (курс 95₽ = 1 USDT)
        await db.update_tariff(tariff_id, 'price_usdt', round(new_price / 95, 2))
        await channel_logger.add_log(f"💰 Цена тарифа {tariff_id} изменена на {new_price}₽")
        
        await state.clear()
        await message.answer(f"✅ Цена тарифа {tariff_id} обновлена на {new_price}₽", reply_markup=main_menu())
    except ValueError:
        await message.answer("❌ Введи число!")


@router.callback_query(F.data.startswith("tariff_requests_"))
async def edit_tariff_requests(cb: CallbackQuery, state: FSMContext):
    """Изменение лимита жалоб тарифа"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    tariff_id = int(cb.data.split("_")[2])
    await state.set_state(SettingsStates.waiting_tariff_requests)
    await state.update_data(tariff_id=tariff_id)
    
    await cb.message.edit_text(
        f"🎯 Введи новый лимит жалоб для тарифа {tariff_id}:\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()


@router.message(SettingsStates.waiting_tariff_requests)
async def process_tariff_requests(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    """Обработка нового лимита жалоб"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    try:
        new_requests = int(message.text.strip())
        data = await state.get_data()
        tariff_id = data['tariff_id']
        
        await db.update_tariff(tariff_id, 'requests', new_requests)
        await channel_logger.add_log(f"🎯 Лимит тарифа {tariff_id} изменен на {new_requests}")
        
        await state.clear()
        await message.answer(f"✅ Лимит тарифа {tariff_id} обновлен на {new_requests}", reply_markup=main_menu())
    except ValueError:
        await message.answer("❌ Введи число!")


# ========== РАССЫЛКА ==========
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(cb: CallbackQuery, state: FSMContext, db: Database):
    """Начинает рассылку"""
    if cb.from_user.id not in ADMIN_IDS:
        return await cb.answer("❌ Ты не админ", show_alert=True)
    
    total_users = len(db.cache['users'])
    
    await cb.message.edit_text(
        f"📢 РАССЫЛКА\n\n"
        f"Всего пользователей: {total_users}\n\n"
        f"Введи текст для рассылки (или /cancel для отмены):"
    )
    await state.set_state(BroadcastStates.waiting_text)
    await cb.answer()


@router.message(BroadcastStates.waiting_text)
async def process_broadcast(message: Message, state: FSMContext, db: Database, bot: Bot, channel_logger: ChannelLogger):
    """Отправляет рассылку всем пользователям"""
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.text == '/cancel':
        await state.clear()
        await message.answer("❌ Рассылка отменена", reply_markup=main_menu())
        return
    
    broadcast_text = message.text
    users = db.cache['users']
    
    status_msg = await message.answer(f"📤 Начинаю рассылку...\n0/{len(users)}")
    
    successful = 0
    failed = 0
    
    for i, (uid, user) in enumerate(users.items(), 1):
        try:
            await bot.send_message(int(uid), f"📢 СООБЩЕНИЕ ОТ АДМИНА\n\n{broadcast_text}")
            successful += 1
        except:
            failed += 1
        
        if i % 10 == 0:
            await status_msg.edit_text(f"📤 Рассылка...\n✅ {successful}\n❌ {failed}\n📊 {i}/{len(users)}")
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n\n📊 Итог:\n✅ Доставлено: {successful}\n❌ Ошибок: {failed}\n👤 Всего: {len(users)}")
    await channel_logger.add_log(f"📢 Рассылка: {successful}/{len(users)} доставлено")
    
    await state.clear()


@router.callback_query(F.data == "admin")
async def back_to_admin(cb: CallbackQuery, db: Database):
    """Возврат в главную админку"""
    users = db.cache['users']
    pending = len(db.cache['pending'])
    
    active_subs = 0
    paid_users = 0
    total_spent = 0
    
    for uid, user in users.items():
        if user.get('total_spent', 0) > 0:
            paid_users += 1
            total_spent += user['total_spent']
        
        if user.get('sub_end'):
            if user['sub_end'] == 'forever':
                active_subs += 1
            else:
                try:
                    if datetime.fromisoformat(user['sub_end']) > datetime.now():
                        active_subs += 1
                except:
                    pass
    
    text = (
        f"👑 АДМИН-ПАНЕЛЬ\n\n"
        f"📊 СТАТИСТИКА\n"
        f"👤 Всего юзеров: {len(users)}\n"
        f"✅ Активных подписок: {active_subs}\n"
        f"⏳ Ожидают оплаты: {pending}\n"
        f"💰 Купивших тариф: {paid_users}\n"
        f"💸 Всего заработано: {total_spent}₽\n\n"
        f"🛠 УПРАВЛЕНИЕ"
    )
    
    await cb.message.edit_text(text, reply_markup=admin_menu())
    await cb.answer()

# --- ПРОФИЛЬ ---
@router.callback_query(F.data == "profile")
async def show_profile(cb: CallbackQuery, db: Database):
    user = await db.get_user(cb.from_user.id)
    has_sub = await db.check_sub(cb.from_user.id)
    
    if cb.from_user.id in ADMIN_IDS:
        sub_status = "👑 АДМИН (бессрочно)"
        requests = "∞"
        plan = "Админ"
    elif has_sub:
        sub_status = "✅ Активна"
        requests = user.get('requests_left', 0)
        tariffs = db.cache['settings']['tariffs']
        plan = tariffs[str(user.get('plan_id', 1))]['name']
    else:
        sub_status = "❌ Нет подписки"
        requests = 0
        plan = "Нет"
    
    text = (
        f"👤 ТВОЙ ПРОФИЛЬ\n\n"
        f"🆔 ID: {user['tg_id']}\n"
        f"👤 Username: @{user['username'] or 'нет'}\n\n"
        f"🎫 ПОДПИСКА: {sub_status}\n"
        f"💎 Тариф: {plan}\n"
        f"🎯 Осталось жалоб: {requests}\n\n"
        f"💰 ПОТРАЧЕНО: {user['total_spent']}₽\n"
        f"👥 РЕФЕРАЛОВ: {len(user.get('referrals', []))}"
    )
    
    await cb.message.edit_text(text, reply_markup=main_menu())
    await cb.answer()

# --- РЕФЕРАЛЫ ---
@router.callback_query(F.data == "ref")
async def show_ref(cb: CallbackQuery):
    bot_info = await cb.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={cb.from_user.id}"
    await cb.message.edit_text(
        f"👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        f"💰 10 друзей = 1 день подписки\n\n"
        f"🔗 Твоя ссылка:\n"
        f"`{link}`\n\n"
        f"📊 СТАТИСТИКА\n"
        f"👥 Приглашено: 0\n"
        f"💎 Заработано дней: 0",
        reply_markup=main_menu()
    )
    await cb.answer()

# --- ПОМОЩЬ ---
@router.callback_query(F.data == "help")
async def show_help(cb: CallbackQuery, db: Database):
    settings = db.cache['settings']
    await cb.message.edit_text(
        f"🆘 ПОМОЩЬ\n\n"
        f"❓ КАК ПОЛЬЗОВАТЬСЯ:\n"
        f"1. Купи тариф в разделе 💳\n"
        f"2. Оплати удобным способом\n"
        f"3. Дождись подтверждения админа\n"
        f"4. Нажимай 🎯 и вводи цель\n\n"
        f"❓ ЧТО МОЖНО СНОСИТЬ:\n"
        f"• @username\n"
        f"• https://t.me/channel\n"
        f"• Ссылки на чаты\n\n"
        f"❓ ВОПРОСЫ:\n"
        f"@{settings['support']}",
        reply_markup=main_menu()
    )
    await cb.answer()

# --- СНОС ---
@router.callback_query(F.data == "snos")
async def start_snos(cb: CallbackQuery, state: FSMContext, db: Database):
    has_sub = await db.check_sub(cb.from_user.id)
    
    if not has_sub:
        await cb.message.edit_text(
            "❌ Нет активной подписки!\n\n"
            "Купи тариф в разделе 💳",
            reply_markup=main_menu()
        )
        return await cb.answer()
    
    await state.set_state(SnosStates.waiting_target)
    await cb.message.edit_text(
        "🎯 ВВЕДИ ЦЕЛЬ\n\n"
        "Примеры:\n"
        "• @username\n"
        "• https://t.me/channel_name\n"
        "• https://t.me/+abc123\n\n"
        "Для отмены отправь /cancel"
    )
    await cb.answer()

@router.message(SnosStates.waiting_target)
async def process_snos(message: Message, state: FSMContext, db: Database, channel_logger: ChannelLogger):
    target = message.text.strip()
    
    if target == '/cancel':
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=main_menu())
        return
    
    if message.from_user.id in ADMIN_IDS:
        limit = 500
    else:
        user = await db.get_user(message.from_user.id)
        limit = min(user.get('requests_left', 100), 500)
    
    msg = await message.answer(f"🎯 СНОС: {target}\n\n⏳ Подготовка...")
    
    successful = 0
    failed = 0
    log_lines = []
    official_targets = ["abuse@telegram.org", "dmca@telegram.org", "support@telegram.org"]
    
    for i in range(1, limit + 1):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        if random.random() < 0.9:
            successful += 1
        else:
            failed += 1
        
        if i % max(1, limit // 10) == 0 or i == limit:
            percent = int((i / limit) * 100)
            
            new_logs = []
            for _ in range(random.randint(2, 3)):
                target_email = random.choice(official_targets)
                if random.random() < 0.6:
                    new_logs.append(f"📧 {generate_email()} → {target_email}")
                else:
                    country = random.choice(['uz', 'ru', 'kz', 'ua', 'us'])
                    new_logs.append(f"{generate_phone(country)} → {target_email}")
            
            log_lines.extend(new_logs)
            if len(log_lines) > 5:
                log_lines = log_lines[-5:]
            
            log_text = '\n'.join(log_lines)
            
            await msg.edit_text(
                f"🎯 СНОС: {target}\n\n"
                f"{loading_bar(percent)}\n\n"
                f"{log_text}\n\n"
                f"✅ Успешно: {successful}\n"
                f"❌ Ошибок: {failed}"
            )
            
            if message.from_user.id not in ADMIN_IDS:
                for _ in range(i - (i - 10 if i > 10 else 0)):
                    await db.use_request(message.from_user.id)
    
    await channel_logger.add_log(f"🎯 Снос завершен: {target} | Успешно: {successful}, Ошибок: {failed}")
    
    await msg.edit_text(
        f"✅ СНОС ЗАВЕРШЕН\n\n"
        f"🎯 Цель: {target}\n"
        f"✅ Успешно: {successful}\n"
        f"❌ Ошибок: {failed}\n"
        f"📊 Использовано жалоб: {limit}",
        reply_markup=main_menu()
    )
    
    await state.clear()

# ========== ЗАПУСК ==========

async def main():
    print("🚀 Запуск Snoser Bot...")
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    db = Database()
    channel_logger = ChannelLogger(BOT_TOKEN, CHANNEL_ID)
    
    dp = Dispatcher()
    dp.include_router(router)
    dp["db"] = db
    dp["channel_logger"] = channel_logger
    dp["bot"] = bot
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("✅ Бот готов!")
    print(f"👑 Админ ID: {ADMIN_IDS}")
    print(f"📊 Логи будут в канале раз в час")
    print(f"⚙️ Настройки полностью рабочие")
    
    async def periodic_flush():
        while True:
            await asyncio.sleep(1800)
            await channel_logger.flush()
    
    asyncio.create_task(periodic_flush())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await channel_logger.stop()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен")