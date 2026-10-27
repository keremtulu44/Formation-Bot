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

# ---------------------------------------------------------------------------
# GEÇ BAĞLAMA ALIASI — script modu (`python main.py`) düzeltmesi (2026-10-27)
# ---------------------------------------------------------------------------
# bot/* alt modülleri `import main as _pkg` ile bu dosyanın namespace'ine
# ÇAĞRI ANINDA erişir (bkz. MODULERLESTIRME_PLANI §3). `python main.py` ile
# script olarak çalışınca CPython bu dosyayı `__main__` adıyla sys.modules'e
# koyar; statestore/app/... içindeki `import main` ise AYRI bir modül nesnesi
# oluşturup dosyayı İKİNCİ kez çalıştırırdı. O ikinci çalıştırmada `bot` henüz
# yarım yüklenmiş olduğundan `from bot import *` `signal_handler`'ı getirmez ve
# aşağıdaki sinyal kaydı NameError verirdi — Render logundaki
# "NameError: name 'signal_handler' is not defined" hatasının kök nedeni budur.
# İki ayrı modül nesnesi ayrıca `_pkg.X` ile okunan yamalı adların
# (monkeypatch, _shutdown_requested, _logging_kuruldu) __main__'den sapmasına
# yol açardı. Alias ile script modunda `main` ve `__main__` AYNI nesne olur:
# ne ikinci çalıştırma olur ne de namespace bölünür. `import main` (testler /
# modül modu) yolunda __name__ == "main" olduğu için bu blok çalışmaz.
#
# NOT: `from bot import *` satırının (dolayısıyla bot içindeki `import main`'in)
# ÜSTÜNDE kalmalıdır.
if __name__ == "__main__" and sys.modules.get("main") is not sys.modules.get("__main__"):
    sys.modules["main"] = sys.modules["__main__"]

import pandas as pd  # noqa: E402  (alias bilinçli olarak en üstte)

import config  # noqa: E402
from health_server import start_render_health_server  # noqa: E402

from bot import *  # noqa: F403,F401,E402  (dış API + yama yüzeyi)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Sinyal kaydı yalnızca GERÇEK giriş noktasında (ana thread) yapılır. Modül
    # seviyesinde tutmak iki sorundu: (1) `import bot`/`import main` sırasındaki
    # yarım yüklenmiş döngüsel importta `signal_handler` henüz bağlı değildi;
    # (2) `signal.signal` yalnızca ana thread'de geçerlidir. Import zamanı
    # kayıt zaten bot/__init__.py içinde yapılıyor; burada giriş noktası için
    # açıkça (yeniden) bağlıyoruz. Aynı fonksiyon iki kez kaydedilmesi zararsız.
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
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
