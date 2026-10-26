# --- MAIN LOOP ---
# BIST Bot Ana Döngü - İskelet
# Henüz tam değil, adım adım doldurulacak
# Türkçe yorumlar: Neden uyuyor, neden tarıyor?
#
# 2026-10-26 modülerleştirme: sistem bot/ paketinde; bu dosya İNCE
# başlatıcıdır. `from bot import *` dış API + yama yüzeyini (test_patch_yuzeyi)
# main namespace'ine bağlar — testlerin monkeypatch.setattr(main, X) yamaları
# aynen çalışır (plan §3).

# ruff: noqa: F405  (bilinçli facade: adlar bot.__all__'dan gelir)

import os
import re
import sys
import time
import json
import signal
import logging
import math
import random
import socket
import threading
from datetime import datetime, timedelta, time as dt_time

import pandas as pd

import config
from health_server import start_render_health_server

from bot import *  # noqa: F403,F401  (dış API + yama yüzeyi)

logger = logging.getLogger(__name__)

signal.signal(signal.SIGTERM, signal_handler)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    setup_logging()
    # HTTP sunucusu main_loop'tan ÖNCE başlar: Render'ın health check'i ilk veri
    # yüklemesi sürerken de yanıt verir. Webhook modunda güncellemeler bu sunucudan
    # gelir; bot komutları kurana kadar /webhook 503 döner (Telegram tekrar dener).
    _health_server_ref = start_render_health_server(
        test_sender=_render_test_sender,
        webhook_handler=_telegram_webhook_isle,
        webhook_secret=TELEGRAM_WEBHOOK_SECRET,
        # Denetim B-4: /health botun canlılığını da raporlasın (heartbeat yaşı).
        health_provider=_saglik_ozeti,
    )
    if os.getenv("BOT_HEALTH_SMOKE_ONLY") == "1":
        # CI liveness dumanı (Render parity): yalnız HTTP sunucusu ayakta kalsın.
        # Notifier kurulmaz, Telegram/Supabase'e istek gitmez, Yahoo fetch ve ana
        # tarama döngüsü BAŞLAMAZ — CI'nın dışa bağımlı olmadan gerçek entrypoint'ı
        # denemesi için tek güvenlik kapısı budur.
        logger.info("Health smoke mode: provider and command loops disabled")
        while not _shutdown_requested:
            time.sleep(0.25)
    else:
        main_loop()
