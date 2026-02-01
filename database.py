import sqlite3
import time
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "monkey_stars.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить подключение к базе"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для работы с колонками по имени
        return conn
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            # Таблица пользователей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0.0,
                    referrer_id INTEGER DEFAULT NULL,
                    last_click INTEGER DEFAULT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    total_wagered REAL DEFAULT 0.0,
                    games_played INTEGER DEFAULT 0,
                    games_won INTEGER DEFAULT 0,
                    FOREIGN KEY (referrer_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица спонсоров
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sponsors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_username TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_url TEXT NOT NULL
                )
            ''')
            
            # Таблица подписок пользователей
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_sponsors (
                    user_id INTEGER,
                    sponsor_id INTEGER,
                    is_subscribed BOOLEAN DEFAULT 0,
                    last_check INTEGER DEFAULT (strftime('%s', 'now')),
                    PRIMARY KEY (user_id, sponsor_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (sponsor_id) REFERENCES sponsors(id)
                )
            ''')
            
            # Таблица транзакций
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT,
                    description TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица выводов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            conn.commit()
            logger.info("✅ База данных инициализирована")
    
    # === ПОЛЬЗОВАТЕЛИ ===
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str, referrer_id: int = None) -> bool:
        """Создать нового пользователя"""
        try:
            with self.get_connection() as conn:
                # Проверяем, есть ли уже пользователь
                existing = self.get_user(user_id)
                if existing:
                    return True
                
                # Создаем пользователя
                conn.execute('''
                    INSERT INTO users (user_id, username, referrer_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, username or f"user_{user_id}", referrer_id, int(time.time())))
                
                conn.commit()
                
                # Если есть реферер, начисляем бонусы
                if referrer_id:
                    from config import Config
                    
                    # Бонус рефереру (3 STAR)
                    self.update_balance(referrer_id, Config.REFERRAL_REWARD_REFERRER)
                    self.add_transaction(
                        referrer_id,
                        Config.REFERRAL_REWARD_REFERRER,
                        "referral_bonus",
                        f"За приглашение {username}"
                    )
                    
                    # Бонус рефералу (2 STAR)
                    self.update_balance(user_id, Config.REFERRAL_REWARD_REFEREE)
                    self.add_transaction(
                        user_id,
                        Config.REFERRAL_REWARD_REFEREE,
                        "referral_bonus",
                        "За регистрацию по реферальной ссылке"
                    )
                
                logger.info(f"✅ Пользователь {user_id} создан")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {user_id}: {e}")
            return False
    
    def update_balance(self, user_id: int, amount: float) -> bool:
        """Обновить баланс пользователя"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления баланса {user_id}: {e}")
            return False
    
    def update_last_click(self, user_id: int) -> bool:
        """Обновить время последнего клика"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE users SET last_click = ? WHERE user_id = ?",
                    (int(time.time()), user_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления last_click {user_id}: {e}")
            return False
    
    def update_game_stats(self, user_id: int, wagered: float, won: bool) -> bool:
        """Обновить статистику игр"""
        try:
            with self.get_connection() as conn:
                # Обновляем общую сумму ставок и количество игр
                conn.execute(
                    "UPDATE users SET total_wagered = total_wagered + ?, games_played = games_played + 1 WHERE user_id = ?",
                    (wagered, user_id)
                )
                
                # Если выиграл - увеличиваем счетчик побед
                if won:
                    conn.execute(
                        "UPDATE users SET games_won = games_won + 1 WHERE user_id = ?",
                        (user_id,)
                    )
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статистики {user_id}: {e}")
            return False
    
    # === СПОНСОРЫ ===
    def get_sponsors(self) -> List[Dict]:
        """Получить всех спонсоров"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sponsors ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_sponsors_status(self, user_id: int) -> List[Dict]:
        """Получить статус подписок пользователя"""
        sponsors = self.get_sponsors()
        if not sponsors:
            return []
        
        result = []
        with self.get_connection() as conn:
            for sponsor in sponsors:
                # Проверяем подписку пользователя
                cursor = conn.execute(
                    "SELECT is_subscribed FROM user_sponsors WHERE user_id = ? AND sponsor_id = ?",
                    (user_id, sponsor['id'])
                )
                row = cursor.fetchone()
                
                result.append({
                    **sponsor,
                    'is_subscribed': bool(row[0]) if row else False
                })
        
        return result
    
    def update_user_sponsor_status(self, user_id: int, sponsor_id: int, is_subscribed: bool) -> bool:
        """Обновить статус подписки"""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO user_sponsors (user_id, sponsor_id, is_subscribed, last_check)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, sponsor_id, int(is_subscribed), int(time.time())))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса подписки: {e}")
            return False
    
    def add_sponsor(self, channel_username: str, channel_id: str, channel_url: str) -> bool:
        """Добавить спонсора (админ)"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT INTO sponsors (channel_username, channel_id, channel_url) VALUES (?, ?, ?)",
                    (channel_username, channel_id, channel_url)
                )
                conn.commit()
                logger.info(f"✅ Спонсор {channel_username} добавлен")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления спонсора: {e}")
            return False
    
    def delete_sponsor(self, sponsor_id: int) -> bool:
        """Удалить спонсора (админ)"""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM sponsors WHERE id = ?", (sponsor_id,))
                conn.execute("DELETE FROM user_sponsors WHERE sponsor_id = ?", (sponsor_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка удаления спонсора: {e}")
            return False
    
    # === РЕФЕРАЛЫ ===
    def get_user_referrals(self, user_id: int) -> Tuple[int, int]:
        """Получить статистику рефералов"""
        with self.get_connection() as conn:
            # Все рефералы
            cursor = conn.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = ?",
                (user_id,)
            )
            total = cursor.fetchone()[0]
            
            # Активные рефералы (подписанные на спонсоров)
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT u.user_id)
                FROM users u
                JOIN user_sponsors us ON u.user_id = us.user_id
                WHERE u.referrer_id = ? AND us.is_subscribed = 1
            ''', (user_id,))
            active = cursor.fetchone()[0]
            
            return total, active
    
    # === ТРАНЗАКЦИИ ===
    def add_transaction(self, user_id: int, amount: float, type: str, description: str = "") -> bool:
        """Добавить транзакцию"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "INSERT INTO transactions (user_id, amount, type, description, created_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, amount, type, description, int(time.time()))
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления транзакции: {e}")
            return False
    
    def get_user_transactions(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить транзакции пользователя"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # === ВЫВОД СРЕДСТВ ===
    def create_withdrawal(self, user_id: int, amount: float) -> Optional[Dict]:
        """Создать заявку на вывод"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO withdrawals (user_id, amount, created_at) VALUES (?, ?, ?) RETURNING id",
                    (user_id, amount, int(time.time()))
                )
                withdrawal_id = cursor.fetchone()[0]
                conn.commit()
                
                return {
                    'id': withdrawal_id,
                    'user_id': user_id,
                    'amount': amount,
                    'status': 'pending',
                    'created_at': int(time.time())
                }
        except Exception as e:
            logger.error(f"Ошибка создания вывода: {e}")
            return None
    
    def get_withdrawals(self, status: str = None) -> List[Dict]:
        """Получить заявки на вывод"""
        with self.get_connection() as conn:
            if status:
                cursor = conn.execute('''
                    SELECT w.*, u.username 
                    FROM withdrawals w
                    LEFT JOIN users u ON w.user_id = u.user_id
                    WHERE w.status = ?
                    ORDER BY w.created_at DESC
                ''', (status,))
            else:
                cursor = conn.execute('''
                    SELECT w.*, u.username 
                    FROM withdrawals w
                    LEFT JOIN users u ON w.user_id = u.user_id
                    ORDER BY w.created_at DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def update_withdrawal_status(self, withdrawal_id: int, status: str) -> bool:
        """Обновить статус вывода"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE withdrawals SET status = ? WHERE id = ?",
                    (status, withdrawal_id)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса вывода: {e}")
            return False
    
    # === АДМИН ФУНКЦИИ ===
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        with self.get_connection() as conn:
            # Количество пользователей
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Общий баланс
            cursor = conn.execute("SELECT SUM(balance) FROM users")
            total_balance = cursor.fetchone()[0] or 0.0
            
            # Общая сумма ставок
            cursor = conn.execute("SELECT SUM(total_wagered) FROM users")
            total_wagered = cursor.fetchone()[0] or 0.0
            
            # Заявки на вывод
            cursor = conn.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
            pending_withdrawals = cursor.fetchone()[0]
            
            # Общий доход (сумма всех проигрышей)
            cursor = conn.execute("SELECT SUM(amount) FROM transactions WHERE amount < 0")
            total_income = abs(cursor.fetchone()[0] or 0.0)
            
            return {
                "total_users": total_users,
                "total_balance": total_balance,
                "total_wagered": total_wagered,
                "pending_withdrawals": pending_withdrawals,
                "total_income": total_income
            }
    
    def broadcast_message(self, message: str) -> List[int]:
        """Отправить сообщение всем пользователям"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT user_id FROM users")
            user_ids = [row[0] for row in cursor.fetchall()]
            return user_ids
