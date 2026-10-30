"""Gerçek giriş noktası (`python main.py`) script-modu başlatma regresyonu.

NEDEN (2026-10-27 Render deploy hatası):
    Render'ın Start Command'i ve CI "Render duman testi" adımı dosyayı MODÜL
    olarak değil SCRIPT olarak çalıştırır (`python main.py`). `bot/*` alt
    modülleri ise `import main as _pkg` ile yamalı adlara geç bağlanır
    (MODULERLESTIRME_PLANI §3). Script modunda `main` adı sys.modules'te
    `__main__`'den AYRI bir modül olarak yeniden üretilirse dosya İKİNCİ kez
    koşar; o sırada `bot` yarım yüklenmiş olduğundan `from bot import *`
    `signal_handler`'ı getirmez ve modül seviyesindeki sinyal kaydı
    ``NameError: name 'signal_handler' is not defined`` fırlatır. Unit testler
    `import main` (modül modu) kullandığı için bu yolu hiç görmüyordu.

BU TEST NE YAPAR:
    * Gerçek entrypoint'ı İZOLE bir alt süreçte, dış ağa çıkmadan
      (BOT_HEALTH_SMOKE_ONLY=1, PORT yok, token/Supabase env'leri boş)
      çalıştırır. Eski kod import anında Traceback ile ölüyordu; düzeltilmiş
      kod health-smoke döngüsüne girip ayakta kalır.
    * Modül modunda tüm `bot/*._pkg` referanslarının TEK `main` modülüne
      baktığını doğrular (geç bağlamanın bölünmediği).

KULLANIM:  python -m pytest test_entrypoint_boot.py -q
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_KOK = Path(__file__).resolve().parent

# Dış servislere çıkılmasın: alt süreç yalnızca import + health-smoke döngüsü.
_TEMIZLENEN_ENV = (
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_GROUP_ID", "TELEGRAM_TEST_KEY", "TELEGRAM_WEBHOOK_SECRET",
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
)

# `from bot import *` BAŞARILI olursa __main__ bloğunda bu loglardan biri düşer.
_BASLANGIC_ISARETLERI = (b"Logging kuruldu", b"PORT env yok", b"Health smoke mode")


def _smoke_ortami(tmp_path) -> dict:
    """İzole, ağsız ortam. PORT bilinçli YOK: HTTP sunucusu açılmaz."""
    env = os.environ.copy()
    env.pop("PORT", None)
    env["BOT_HEALTH_SMOKE_ONLY"] = "1"
    env["DATA_DIR"] = str(tmp_path / "data")
    env["LOG_DIR"] = str(tmp_path / "logs")
    env["LOCAL_LOG_DIR"] = str(tmp_path / "logs-fallback")
    for anahtar in _TEMIZLENEN_ENV:
        env[anahtar] = ""
    return env


def test_python_main_py_script_modunda_cokmez(tmp_path):
    """`python main.py` script modunda döngüsel import/NameError vermemeli."""
    env = _smoke_ortami(tmp_path)
    log_yolu = tmp_path / "entrypoint.log"
    kendiliginden_cikti = False

    with log_yolu.open("wb") as log:
        proc = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=str(_KOK),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
        try:
            bitis = time.monotonic() + 20
            while time.monotonic() < bitis:
                if proc.poll() is not None:
                    # Eski (bozuk) kod burada import hatasıyla ölür.
                    kendiliginden_cikti = True
                    break
                try:
                    kayit = log_yolu.read_bytes()
                except OSError:
                    kayit = b""
                if any(isaret in kayit for isaret in _BASLANGIC_ISARETLERI):
                    # Düzeltilmiş kod: import zinciri tamamlandı, __main__ bloğu
                    # çalıştı (health-smoke döngüsü ayakta).
                    break
                time.sleep(0.2)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

    try:
        cikti = log_yolu.read_bytes().decode("utf-8", "replace")
    except OSError:
        cikti = ""

    assert "Traceback" not in cikti, (
        "python main.py script modunda import zinciri çöktü (döngüsel import / "
        "NameError). Log:\n" + cikti[-2500:]
    )
    assert not kendiliginden_cikti, (
        "python main.py health-smoke modunda KENDİLİĞİNDEN çıktı — import "
        "zamanı hata (örn. signal_handler NameError) olabilir. Log:\n" + cikti[-2500:]
    )


def test_bot_alt_modulleri_tek_main_modulune_bakar():
    """Modül modunda tüm `bot/*._pkg` aynı `main` nesnesine işaret etmeli.

    İki ayrı modül olursa monkeypatch/_shutdown_requested/_logging_kuruldu
    gibi yamalı adlar ikiye bölünür; bu, script modu hatasının çalışma anındaki
    sessiz karşılığıdır.
    """
    import main
    from bot import (app, commands, counters, heartbeat, lifecycle_events,
                     scan, security, statestore, summary)

    moduller = (app, commands, counters, heartbeat, lifecycle_events,
                scan, security, statestore, summary)
    for mod in moduller:
        assert mod._pkg is main, (
            f"{mod.__name__}._pkg, `main` modülünden FARKLI bir nesneye bakıyor; "
            "geç bağlama bölünmüş (yamalı adlar görünmez olur)."
        )


def test_shutdown_closes_readiness_and_interrupts_retry_wait(monkeypatch):
    import threading
    import main
    from bot.app import _shutdown_bekle

    monkeypatch.setattr(main, "_startup_ready", True)
    monkeypatch.setattr(main, "_shutdown_requested", False)
    monkeypatch.setattr(main, "_scan_istegi", threading.Event())
    waiter = threading.Thread(target=_shutdown_bekle, args=(30,), daemon=True)
    waiter.start()
    try:
        main.signal_handler(signal.SIGTERM, None)
        waiter.join(timeout=2)
        assert not waiter.is_alive()
        assert main._shutdown_requested is True
        assert main._startup_ready is False
        assert main._saglik_ozeti()["startup_complete"] is False
    finally:
        main._scan_istegi.set()
        waiter.join(timeout=2)
