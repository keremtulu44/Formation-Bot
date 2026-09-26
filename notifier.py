# --- TELEGRAM NOTIFIER ---
# Henüz aktif değil - iskelet
# Neden en son? Önce formasyon sistemi otursun, mesaj formatını insanlaştırma yapacağız dedin

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Telegram bildirim yöneticisi
    - Cooldown: aynı pattern için 4 saat spam önleme
    - Env'den token/chat_id
    - Mesaj formatı sonra insanlaştırılacak
    """
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}  # key: stock_pattern_timeframe -> timestamp
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram token/chat_id env'de yok - notifier pasif (test modu)")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram notifier aktif")
    
    def _cooldown_key(self, stock: str, pattern: str, timeframe: str) -> str:
        return f"{stock}_{pattern}_{timeframe}"
    
    def can_send(self, stock: str, pattern: str, timeframe: str) -> bool:
        """Cooldown kontrolü - 4 saat içinde aynı pattern gönderildi mi?"""
        key = self._cooldown_key(stock, pattern, timeframe)
        if key not in self.last_sent:
            return True
        
        last = self.last_sent[key]
        elapsed = datetime.now() - last
        return elapsed > timedelta(hours=self.cooldown_hours)
    
    def format_message(self, data: Dict) -> str:
        """
        Mesaj formatla - şimdilik ham, sonra insanlaştırma
        data: {stock, timeframe, pattern, state, quality, price, timestamp, ...}
        """
        # Eski prompt'taki format ALIM/SATIM içeriyordu, sen dedin olmayacak
        # Şimdilik state bazlı format
        stock = data.get('stock_name', 'Bilinmiyor')
        timeframe = data.get('timeframe', '1h')
        pattern = data.get('pattern_name', 'Formasyon')
        state = data.get('state', 'Tespit')
        quality = data.get('confidence_score', 0)
        price = data.get('critical_price_level', 0)
        timestamp = data.get('timestamp', datetime.now())
        
        # İnsanlaştırma sonra - şimdilik teknik
        message = f"""🤖 ARGENT Formasyon Radarı
📌 Hisse: {stock}
📊 Zaman: {timeframe}
📈 Formasyon: {pattern}
📍 Durum: {state}
💰 Seviye: {price:.2f}
⏰ Saat: {timestamp}
📝 Kalite: {quality:.0f}/100
"""
        return message
    
    def send(self, data: Dict) -> bool:
        """Gönder - şimdilik sadece log"""
        stock = data.get('stock_name', '')
        pattern = data.get('pattern_name', '')
        timeframe = data.get('timeframe', '')
        
        if not self.can_send(stock, pattern, timeframe):
            logger.info(f"{stock} {pattern} {timeframe} - cooldown aktif, gönderilmiyor")
            return False
        
        if not self.enabled:
            logger.info(f"[MOCK TELEGRAM] {self.format_message(data)}")
            # Cooldown kaydet
            key = self._cooldown_key(stock, pattern, timeframe)
            self.last_sent[key] = datetime.now()
            return True
        
        # Gerçek gönderim - requests ile
        try:
            import requests
            message = self.format_message(data)
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram gönderildi: {stock} {pattern}")
                key = self._cooldown_key(stock, pattern, timeframe)
                self.last_sent[key] = datetime.now()
                return True
            else:
                logger.error(f"Telegram hatası: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram gönderim hatası: {e}")
            return False

if __name__ == "__main__":
    # Test
    notifier = TelegramNotifier()
    test_data = {
        'stock_name': 'THYAO',
        'timeframe': '1h',
        'pattern_name': 'Simetrik Üçgen',
        'state': 'KIRILIM_ADAYI',
        'confidence_score': 72,
        'critical_price_level': 298.5,
        'timestamp': datetime.now()
    }
    notifier.send(test_data)
