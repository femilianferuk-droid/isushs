import os

class Config:
    # Токен бота (установите в системе или прямо здесь)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ")
    
    # ID администратора
    ADMIN_ID = 7973988177
    
    # Настройки игры
    CLICK_REWARD = 0.2
    CLICK_COOLDOWN = 3600  # 1 час в секундах
    REFERRAL_REWARD_REFERRER = 3.0
    REFERRAL_REWARD_REFEREE = 2.0
    CLICK_REFERRAL_PERCENT = 10
    
    # Суммы для вывода
    WITHDRAWAL_AMOUNTS = [15, 25, 50, 100]
    
    # Настройки игр
    GAMES = {
        'flip': {
            'name': '🎯 Monkey Flip',
            'win_chance': 0.49,
            'multiplier': 2.0,
            'special_event_chance': 0.015,
            'min_bet': 1.0
        },
        'crash': {
            'name': '🚀 Banana Crash',
            'instant_crash_chance': 0.6,
            'low_multiplier_range': (1.0, 1.1),
            'high_multiplier_chance': 0.02,
            'min_high_multiplier': 1.5,
            'min_bet': 1.0
        },
        'slot': {
            'name': '🎰 Банановый слот',
            'winning_combinations': 1,
            'total_combinations': 27,
            'win_multiplier': 20,
            'jackpot_multiplier': 50,
            'min_bet': 1.0
        },
        'dice': {
            'name': '🎲 Банановые кости',
            'win_chance': 0.1667,  # 1/6
            'multiplier': 3.0,
            'min_bet': 1.0
        },
        'jackpot': {
            'name': '💰 Джекпот',
            'ticket_price': 1.0,
            'win_chance': 0.01,
            'multiplier': 100.0,
            'min_bet': 1.0
        }
    }
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN or cls.BOT_TOKEN == "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ":
            raise ValueError(
                "❌ Установите токен бота!\n\n"
                "1. Получите токен у @BotFather\n"
                "2. Измените в config.py строку:\n"
                "   BOT_TOKEN = 'ваш_токен'\n"
                "3. Или установите в системе:\n"
                "   export BOT_TOKEN='ваш_токен'"
            )
        return True
