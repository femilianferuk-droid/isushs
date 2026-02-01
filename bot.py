import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from database import Database
from games import GameEngine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверяем настройки
Config.validate()

# Инициализация
bot = Bot(token=Config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Состояния для FSM
class GameStates(StatesGroup):
    choosing_bet = State()
    playing_dice = State()

class WithdrawState(StatesGroup):
    choosing_amount = State()

class AdminStates(StatesGroup):
    adding_sponsor = State()
    broadcasting = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def format_balance(balance: float) -> str:
    return f"{balance:.2f}"

def format_time(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes} мин {secs} сек"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"

def create_main_menu(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🐵 Заработать звезды", callback_data="earn")],
        [InlineKeyboardButton(text="🎮 Играть в игры", callback_data="play_games")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
    ]
    
    # Админ панель
    if user_id == Config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def check_subscriptions(user_id: int) -> bool:
    """Проверить подписки"""
    sponsors_status = db.get_user_sponsors_status(user_id)
    if not sponsors_status:  # Если нет спонсоров
        return True
    
    for sponsor in sponsors_status:
        if not sponsor.get('is_subscribed', False):
            return False
    return True

async def show_sponsors_message(message: Message, user_id: int):
    """Показать спонсоров"""
    sponsors = db.get_sponsors()
    
    if not sponsors:
        await show_main_menu(message)
        return
    
    keyboard = []
    for sponsor in sponsors:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📢 {sponsor.get('channel_username', 'Канал')}",
                url=sponsor.get('channel_url', 'https://t.me')
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscriptions")
    ])
    
    await message.answer(
        "📢 *Чтобы начать, подпишитесь на наших спонсоров!*\n\n"
        "После подписки нажмите кнопку ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

async def show_main_menu(message: Message, text: str = None):
    """Показать главное меню"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    balance = user['balance'] if user else 0.0
    
    welcome_text = text or (
        "🐵 *Monkey Stars*\n\n"
        f"💰 Баланс: *{format_balance(balance)} STAR*\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=create_main_menu(user_id),
        parse_mode="Markdown"
    )

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    logger.info(f"User {user_id} ({username}) started bot")
    
    # Обработка реферальной ссылки
    referrer_id = None
    if len(message.text.split()) > 1:
        try:
            referrer_id = int(message.text.split()[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass
    
    # Создаем пользователя
    db.create_user(user_id, username, referrer_id)
    
    # Проверяем подписки
    if not await check_subscriptions(user_id):
        await show_sponsors_message(message, user_id)
        return
    
    await show_main_menu(message)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Справка"""
    help_text = (
        "🎮 *Monkey Stars Bot*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать работу\n"
        "/balance - Проверить баланс\n"
        "/games - Список игр\n"
        "/profile - Ваш профиль\n"
        "/referral - Реферальная система\n"
        "/help - Эта справка\n\n"
        "🎯 *Игры в меню:*\n"
        "• 🎯 Monkey Flip (орел/решка x2.0)\n"
        "• 🚀 Banana Crash (краш-игра)\n"
        "• 🎰 Банановый слот (джекпот x50)\n"
        "• 🎲 Банановые кости (угадай число x3.0)\n"
        "• 💰 Джекпот (шанс x100)\n\n"
        "💰 *Заработок:*\n"
        "• Кликер (каждый час)\n"
        "• Приглашайте друзей\n"
        "• Получайте 10% от их кликов"
    )
    
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    """Проверка баланса"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if user:
        balance = user['balance']
        await message.answer(f"💰 Ваш баланс: *{format_balance(balance)} STAR*", parse_mode="Markdown")
    else:
        await message.answer("❌ Пользователь не найден. Используйте /start")

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data == "check_subscriptions")
async def handle_check_subscriptions(callback: CallbackQuery):
    """Проверка подписок"""
    user_id = callback.from_user.id
    
    # Имитация успешной подписки
    sponsors = db.get_sponsors()
    for sponsor in sponsors:
        db.update_user_sponsor_status(user_id, sponsor['id'], True)
    
    await callback.answer("✅ Отлично! Доступ открыт!")
    await callback.message.delete()
    await show_main_menu(callback.message)

@dp.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery):
    """Главное меню"""
    await callback.message.delete()
    await show_main_menu(callback.message)

@dp.callback_query(F.data == "earn")
async def handle_earn(callback: CallbackQuery):
    """Заработок"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        await show_sponsors_message(callback.message, user_id)
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🎯 Кликнуть (+0.2 STAR)", callback_data="click")],
        [InlineKeyboardButton(text="💸 Вывод средств", callback_data="withdraw_menu")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    await callback.message.edit_text(
        "🐵 *Заработать звезды*\n\n"
        "Выберите способ заработка:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "click")
async def handle_click(callback: CallbackQuery):
    """Кликер"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    current_time = int(datetime.now().timestamp())
    last_click = user.get('last_click')
    
    # Проверка кулдауна
    if last_click and (current_time - last_click) < Config.CLICK_COOLDOWN:
        remaining = Config.CLICK_COOLDOWN - (current_time - last_click)
        await callback.answer(f"⏳ Подождите {format_time(remaining)}")
        return
    
    # Начисление
    reward = Config.CLICK_REWARD
    db.update_balance(user_id, reward)
    db.update_last_click(user_id)
    db.add_transaction(user_id, reward, "click", "Кликер")
    
    # Реферальный бонус
    referrer_id = user.get('referrer_id')
    if referrer_id:
        referral_bonus = reward * (Config.CLICK_REFERRAL_PERCENT / 100)
        db.update_balance(referrer_id, referral_bonus)
        db.add_transaction(
            referrer_id,
            referral_bonus,
            "referral_income",
            f"10% от клика пользователя {callback.from_user.username or user_id}"
        )
    
    # Обновляем сообщение
    user = db.get_user(user_id)
    await callback.message.edit_text(
        f"✅ *Вы получили {reward} STAR!*\n\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n\n"
        f"⏰ Следующий клик через 1 час",
        parse_mode="Markdown",
        reply_markup=callback.message.reply_markup
    )
    
    await callback.answer(f"+{reward} STAR")

@dp.callback_query(F.data == "withdraw_menu")
async def handle_withdraw_menu(callback: CallbackQuery):
    """Вывод средств"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    keyboard = []
    for amount in Config.WITHDRAWAL_AMOUNTS:
        keyboard.append([InlineKeyboardButton(text=f"{amount} STAR", callback_data=f"withdraw_{amount}")])
    
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="earn")])
    
    await callback.message.edit_text(
        "💸 *Вывод средств*\n\n"
        "📋 Требования:\n"
        "• Баланс ≥ выбранной суммы\n"
        "• 3 активных реферала\n\n"
        "Выберите сумму:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("withdraw_"))
async def handle_withdraw(callback: CallbackQuery):
    """Обработка вывода"""
    user_id = callback.from_user.id
    
    try:
        amount = float(callback.data.split("_")[1])
    except:
        await callback.answer("❌ Ошибка")
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    # Проверка баланса
    if user['balance'] < amount:
        await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
        return
    
    # Проверка рефералов
    total_ref, active_ref = db.get_user_referrals(user_id)
    if active_ref < 3:
        await callback.answer(f"❌ Нужно 3 активных реферала. У вас: {active_ref}")
        return
    
    # Создаем заявку
    withdrawal = db.create_withdrawal(user_id, amount)
    if not withdrawal:
        await callback.answer("❌ Ошибка")
        return
    
    # Списание
    db.update_balance(user_id, -amount)
    db.add_transaction(user_id, -amount, "withdrawal", f"Вывод #{withdrawal['id']}")
    
    await callback.message.edit_text(
        f"✅ *Заявка на вывод одобрена!*\n\n"
        f"💰 Сумма: *{amount} STAR*\n"
        f"📝 ID заявки: *#{withdrawal['id']}*\n\n"
        f"Для получения средств свяжитесь с @MonkeyStarsov\n"
        f"Укажите ID: `{user_id}` и сумму: `{amount} STAR`",
        parse_mode="Markdown"
    )

# ========== ИГРЫ ==========

@dp.callback_query(F.data == "play_games")
async def handle_play_games(callback: CallbackQuery):
    """Выбор игры"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton(text=Config.GAMES['flip']['name'], callback_data="game_flip")],
        [InlineKeyboardButton(text=Config.GAMES['crash']['name'], callback_data="game_crash")],
        [InlineKeyboardButton(text=Config.GAMES['slot']['name'], callback_data="game_slot")],
        [InlineKeyboardButton(text=Config.GAMES['dice']['name'], callback_data="game_dice")],
        [InlineKeyboardButton(text=Config.GAMES['jackpot']['name'], callback_data="game_jackpot")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    user = db.get_user(user_id)
    balance = user['balance'] if user else 0.0
    
    await callback.message.edit_text(
        f"🎮 *Выберите игру:*\n\n"
        f"💰 Ваш баланс: *{format_balance(balance)} STAR*\n\n"
        f"🎯 *Monkey Flip* - Подбрось банан (x2.0)\n"
        f"🚀 *Banana Crash* - Краш-игра\n"
        f"🎰 *Банановый слот* - 3 барабана\n"
        f"🎲 *Банановые кости* - Угадай число (x3.0)\n"
        f"💰 *Джекпот* - Шанс x100",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "game_flip")
async def handle_game_flip(callback: CallbackQuery):
    """Monkey Flip"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🍌 Banana", callback_data="flip_heads")],
        [InlineKeyboardButton(text="🐵 Monkey", callback_data="flip_tails")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🎯 *Monkey Flip*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"📈 Шанс выигрыша: *49%*\n"
        f"🎲 Множитель: *x2.0*\n"
        f"💰 Мин. ставка: *{Config.GAMES['flip']['min_bet']} STAR*\n\n"
        f"Выберите сторону:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("flip_"))
async def handle_flip_choice(callback: CallbackQuery, state: FSMContext):
    """Выбор в Flip"""
    user_id = callback.from_user.id
    choice = callback.data.split("_")[1]
    
    await state.update_data(game_type="flip", flip_choice=choice)
    await state.set_state(GameStates.choosing_bet)
    
    await callback.message.edit_text(
        f"🎯 Вы выбрали: {'🍌 Banana' if choice == 'heads' else '🐵 Monkey'}\n\n"
        f"💰 Введите сумму ставки (мин. {Config.GAMES['flip']['min_bet']} STAR):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Отмена", callback_data="game_flip")]
        ])
    )

@dp.message(GameStates.choosing_bet)
async def handle_bet_input(message: Message, state: FSMContext):
    """Ввод ставки"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    
    try:
        bet = float(message.text)
        data = await state.get_data()
        game_type = data.get('game_type')
        
        # Проверка минимальной ставки
        min_bet = Config.GAMES[game_type]['min_bet']
        if bet < min_bet:
            await message.answer(f"❌ Минимальная ставка: {min_bet} STAR")
            return
        
        # Проверка баланса
        if user['balance'] < bet:
            await message.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Играем
        if game_type == "flip":
            choice = data.get('flip_choice')
            win, amount, emoji, result_text = GameEngine.play_flip(bet, choice)
            
            # Обновляем баланс
            if win:
                db.update_balance(user_id, amount - bet)
                db.add_transaction(user_id, amount - bet, "game_win", "Monkey Flip выигрыш")
                db.update_game_stats(user_id, bet, True)
            else:
                db.update_balance(user_id, -bet)
                db.add_transaction(user_id, -bet, "game_lose", "Monkey Flip проигрыш")
                db.update_game_stats(user_id, bet, False)
            
            # Получаем новый баланс
            user = db.get_user(user_id)
            
            await message.answer(
                f"🎯 *Monkey Flip*\n\n"
                f"💰 Ставка: *{bet} STAR*\n"
                f"{emoji} {result_text}\n\n"
                f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
                f"🎮 Сыграть ещё?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Играть снова", callback_data="game_flip")],
                    [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                    [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="Markdown"
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Ошибка")
        await state.clear()

@dp.callback_query(F.data == "game_crash")
async def handle_game_crash(callback: CallbackQuery):
    """Banana Crash"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🚀 Играть (1 STAR)", callback_data="crash_play_1")],
        [InlineKeyboardButton(text="🚀 Играть (5 STAR)", callback_data="crash_play_5")],
        [InlineKeyboardButton(text="🚀 Играть (10 STAR)", callback_data="crash_play_10")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🚀 *Banana Crash*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"📈 Множитель растет от x1.00\n"
        f"💥 60% шанс мгновенного краша\n"
        f"🎰 2% шанс на высокий множитель\n\n"
        f"Выберите ставку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("crash_play_"))
async def handle_crash_play(callback: CallbackQuery):
    """Игра в Crash"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    try:
        bet = float(callback.data.split("_")[2])
        
        # Проверка баланса
        if user['balance'] < bet:
            await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Играем
        win, amount, emoji, result_text = GameEngine.play_crash(bet)
        
        # Обновляем баланс
        if win:
            db.update_balance(user_id, amount - bet)
            db.add_transaction(user_id, amount - bet, "game_win", f"Banana Crash выигрыш x{amount/bet:.2f}")
            db.update_game_stats(user_id, bet, True)
        else:
            db.update_balance(user_id, -bet)
            db.add_transaction(user_id, -bet, "game_lose", "Banana Crash проигрыш")
            db.update_game_stats(user_id, bet, False)
        
        # Новый баланс
        user = db.get_user(user_id)
        
        await callback.message.edit_text(
            f"🚀 *Banana Crash*\n\n"
            f"💰 Ставка: *{bet} STAR*\n"
            f"{emoji} {result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Сыграть ещё?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Играть снова", callback_data="game_crash")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ Ошибка")

@dp.callback_query(F.data == "game_slot")
async def handle_game_slot(callback: CallbackQuery):
    """Слоты"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    keyboard = [
        [InlineKeyboardButton(text="🎰 Крутить (1 STAR)", callback_data="slot_play_1")],
        [InlineKeyboardButton(text="🎰 Крутить (5 STAR)", callback_data="slot_play_5")],
        [InlineKeyboardButton(text="🎰 Крутить (10 STAR)", callback_data="slot_play_10")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="play_games")]
    ]
    
    await callback.message.edit_text(
        f"🎰 *Банановый слот*\n\n"
        f"💰 Ваш баланс: *{format_balance(user['balance'])} STAR*\n"
        f"🎯 3 одинаковых = x20\n"
        f"🍌 3 банана = ДЖЕКПОТ x50!\n"
        f"🎲 2 одинаковых = x1.5\n\n"
        f"Выберите ставку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("slot_play_"))
async def handle_slot_play(callback: CallbackQuery):
    """Игра в слоты"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    try:
        bet = float(callback.data.split("_")[2])
        
        # Проверка баланса
        if user['balance'] < bet:
            await callback.answer(f"❌ Недостаточно STAR. Баланс: {format_balance(user['balance'])}")
            return
        
        # Играем
        win, amount, result_text, reels = GameEngine.play_slot(bet)
        
        # Обновляем баланс
        if win:
            db.update_balance(user_id, amount - bet)
            db.add_transaction(user_id, amount - bet, "game_win", f"Слоты выигрыш x{amount/bet:.2f}")
            db.update_game_stats(user_id, bet, True)
        else:
            db.update_balance(user_id, -bet)
            db.add_transaction(user_id, -bet, "game_lose", "Слоты проигрыш")
            db.update_game_stats(user_id, bet, False)
        
        # Новый баланс
        user = db.get_user(user_id)
        
        await callback.message.edit_text(
            f"🎰 *Банановый слот*\n\n"
            f"💰 Ставка: *{bet} STAR*\n"
            f"🎰 Результат: {' '.join(reels)}\n"
            f"{result_text}\n\n"
            f"💰 Новый баланс: *{format_balance(user['balance'])} STAR*\n\n"
            f"🎮 Сыграть ещё?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎰 Крутить снова", callback_data="game_slot")],
                [InlineKeyboardButton(text="🎮 Все игры", callback_data="play_games")],
                [InlineKeyboardButton(text="🐵 Главное меню", callback_data="main_menu")]
            ]),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await callback.answer("❌ Ошибка")

# ПРОФИЛЬ И РЕФЕРАЛКА

@dp.callback_query(F.data == "profile")
async def handle_profile(callback: CallbackQuery):
    """Профиль"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    user = db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка")
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    # Статистика игр
    games_played = user.get('games_played', 0)
    games_won = user.get('games_won', 0)
    total_wagered = user.get('total_wagered', 0.0)
    
    win_rate = (games_won / games_played * 100) if games_played > 0 else 0
    
    # Время до клика
    last_click = user.get('last_click')
    current_time = int(datetime.now().timestamp())
    
    if last_click:
        time_passed = current_time - last_click
        if time_passed < Config.CLICK_COOLDOWN:
            remaining = Config.CLICK_COOLDOWN - time_passed
            next_click = f"через {format_time(remaining)}"
        else:
            next_click = "сейчас"
    else:
        next_click = "сейчас"
    
    text = (
        f"📊 *Профиль*\n\n"
        f"👤 ID: `{user_id}`\n"
        f"👤 Имя: {callback.from_user.full_name}\n"
        f"💰 Баланс: *{format_balance(user['balance'])} STAR*\n"
        f"👥 Рефералов: *{active_ref}* / {total_ref}\n\n"
        f"🎮 *Статистика:*\n"
        f"• Сыграно: {games_played}\n"
        f"• Побед: {games_won}\n"
        f"• Процент: {win_rate:.1f}%\n"
        f"• Поставлено: {format_balance(total_wagered)} STAR\n\n"
        f"⏰ Кликер: {next_click}"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "referral")
async def handle_referral(callback: CallbackQuery):
    """Рефералка"""
    user_id = callback.from_user.id
    
    if not await check_subscriptions(user_id):
        await callback.answer("❌ Сначала подпишитесь на спонсоров!", show_alert=True)
        return
    
    total_ref, active_ref = db.get_user_referrals(user_id)
    
    text = (
        f"👥 *Реферальная система*\n\n"
        f"🔗 Ваша ссылка:\n"
        f"`https://t.me/MonkeyStarsBot?start={user_id}`\n\n"
        f"📊 Статистика:\n"
        f"• Приглашено: *{total_ref}*\n"
        f"• Активных: *{active_ref}*\n\n"
        f"🎁 *Правила:*\n"
        f"• Вы получаете *3 STAR*, друг *2 STAR*\n"
        f"• Вы получаете *10%* от кликов реферала\n"
        f"• Для вывода нужно *3 активных реферала*"
    )
    
    keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

# ========== АДМИН ПАНЕЛЬ ==========

@dp.callback_query(F.data == "admin_panel")
async def handle_admin_panel(callback: CallbackQuery):
    """Админ панель"""
    if callback.from_user.id != Config.ADMIN_ID:
        await callback.answer("❌ Доступ запрещен")
        return
    
    stats = db.get_stats()
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Добавить спонсора", callback_data="admin_add_sponsor")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ]
    
    text = (
        f"👑 *Админ панель*\n\n"
        f"📊 Статистика:\n"
        f"• Пользователей: {stats['total_users']}\n"
        f"• Общий баланс: {format_balance(stats['total_balance'])} STAR\n"
        f"• Всего поставлено: {format_balance(stats['total_wagered'])} STAR\n"
        f"• Заявок на вывод: {stats['pending_withdrawals']}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )

# ========== ЗАПУСК ==========

async def main():
    """Запуск бота"""
    logger.info("🚀 Запуск Monkey Stars Bot...")
    
    try:
        # Проверка базы
        stats = db.get_stats()
        logger.info(f"✅ База данных: {stats['total_users']} пользователей")
        
        # Запуск
        logger.info("✅ Бот запущен")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
