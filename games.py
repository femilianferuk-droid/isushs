import random
from typing import Tuple, List
from config import Config

class GameEngine:
    
    @staticmethod
    def play_flip(bet: float, choice: str) -> Tuple[bool, float, str, str]:
        """Игра Monkey Flip"""
        config = Config.GAMES['flip']
        
        # Специальное событие (1.5% шанс проигрыша)
        if random.random() < config['special_event_chance']:
            return False, 0.0, "🍌🌀", "Специальное событие! Банан улетел в космос!"
        
        # Основная логика
        win = random.random() < config['win_chance']
        
        if win:
            win_amount = bet * config['multiplier']
            result_emoji = "🍌" if choice == 'heads' else "🐵"
            result_text = f"{result_emoji} Вы выиграли {win_amount:.2f} STAR!"
            return True, win_amount, result_emoji, result_text
        else:
            lose_emoji = "🐵" if choice == 'heads' else "🍌"
            result_text = f"{lose_emoji} Вы проиграли {bet:.2f} STAR"
            return False, 0.0, lose_emoji, result_text
    
    @staticmethod
    def play_crash(bet: float) -> Tuple[bool, float, str, str]:
        """Игра Banana Crash"""
        config = Config.GAMES['crash']
        
        # 60% шанс мгновенного краша
        if random.random() < config['instant_crash_chance']:
            return False, 0.0, "💥", "Мгновенный краш! x1.00"
        
        # 2% шанс на высокий множитель
        if random.random() < config['high_multiplier_chance']:
            multiplier = random.uniform(config['min_high_multiplier'], 5.0)
            multiplier = round(multiplier, 2)
            win_amount = bet * multiplier
            return True, win_amount, "🚀", f"Улетный множитель! x{multiplier}"
        
        # Обычный низкий множитель
        multiplier = random.uniform(*config['low_multiplier_range'])
        multiplier = round(multiplier, 2)
        
        # Игрок забирает в 80% случаев, когда множитель > 1.0
        if multiplier > 1.0 and random.random() < 0.8:
            win_amount = bet * multiplier
            return True, win_amount, "✅", f"Вы забрали на x{multiplier}"
        else:
            return False, 0.0, "💥", f"Краш на x{multiplier}"
    
    @staticmethod
    def play_slot(bet: float) -> Tuple[bool, float, str, List[str]]:
        """Игра Слот-машина"""
        config = Config.GAMES['slot']
        
        # Генерируем 3 барабана
        symbols = ['🍌', '🐵', '⭐', '💎', '🎯', '💰', '🎰', '🍀']
        reels = [random.choice(symbols) for _ in range(3)]
        
        # Проверяем выигрышную комбинацию
        if reels[0] == reels[1] == reels[2]:
            if reels[0] == '🍌':  # Джекпот за 3 банана
                win_amount = bet * config['jackpot_multiplier']
                return True, win_amount, f"🎰 ДЖЕКПОТ! 3x🍌", reels
            
            win_amount = bet * config['win_multiplier']
            return True, win_amount, f"🎰 Выигрыш! 3x{reels[0]}", reels
        
        # Проверяем 2 одинаковых символа
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            win_amount = bet * 1.5  # Небольшой выигрыш за 2 одинаковых
            return True, win_amount, f"🎰 2 одинаковых символа!", reels
        
        else:
            return False, 0.0, f"🎰 {reels[0]} {reels[1]} {reels[2]}", reels
    
    @staticmethod
    def play_dice(bet: float, user_number: int) -> Tuple[bool, float, str, int]:
        """Игра Банановые кости"""
        config = Config.GAMES['dice']
        
        # Бросаем кубик (1-6)
        dice_roll = random.randint(1, 6)
        
        # Игрок выигрывает, если угадал число
        if user_number == dice_roll:
            win_amount = bet * config['multiplier']
            return True, win_amount, f"🎲 Выпало {dice_roll}! Вы угадали!", dice_roll
        else:
            return False, 0.0, f"🎲 Выпало {dice_roll}, а вы загадали {user_number}", dice_roll
    
    @staticmethod
    def play_jackpot(bet: float) -> Tuple[bool, float, str]:
        """Игра Джекпот"""
        config = Config.GAMES['jackpot']
        
        # Количество билетов
        tickets = int(bet / config['ticket_price'])
        
        # Проверяем каждый билет
        for _ in range(tickets):
            if random.random() < config['win_chance']:
                win_amount = config['ticket_price'] * config['multiplier']
                return True, win_amount, "💰 ДЖЕКПОТ!!!"
        
        return False, 0.0, f"💰 Куплено {tickets} билетов. Попробуйте еще!"
