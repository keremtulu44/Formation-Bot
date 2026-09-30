"""Batch 2 regresyonları: görünürlük (digest şeffaflığı, özet kaynağı) ve ölü kod sözleşmeleri.

Bu dosya ağa çıkmaz; main/notifier modülleri doğrudan çağrılır.
"""

import logging
from datetime import datetime

import pytest

import config
import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ
from telegram_alert_flow import DeferredAlertBuffer


# --- B2: digest şeffaflığı -------------------------------------------------

def _kayit(stock, tf, q=90, state="SIKISMA_GUCLENIYOR", contraction=0.8):
    return dict(stock=stock, timeframe=tf, pattern_name="Simetrik Üçgen",
                quality=float(q), state=state, contraction=contraction,
                upper_touches=2, lower_touches=2, break_type=1)


def test_digest_basligi_kac_aday_gosterildigini_soyler():
    kayitlar = [_kayit(f"SYM{i:02d}", "1h") for i in range(12)]
    metin = main_mod._format_deferred_alert_summary(kayitlar, toplam=21)
    assert "12/21 gösteriliyor" in metin
    assert "… 9 aday daha (tam liste: /formasyonlar)" in metin
    assert len([s for s in metin.splitlines() if s.startswith("•")]) == 12


def test_digest_toplam_verilmezse_eski_baslik_korunur():
    kayitlar = [_kayit("THYAO", "1h"), _kayit("GARAN", "4h")]
    metin = main_mod._format_deferred_alert_summary(kayitlar)
    assert metin.startswith("📡 Gün içi izleme adayları (en yüksek puanlılar)")
    assert "aday daha" not in metin


def test_digest_toplam_gosterilenden_kucukse_tutarsizlik_yazilmaz():
    """Savunma: toplam yanlış/silik gelirse '12/11' gibi saçma başlık çıkmaz."""
    kayitlar = [_kayit(f"SYM{i}", "1h") for i in range(5)]
    metin = main_mod._format_deferred_alert_summary(kayitlar, toplam=3)
    assert "5/5 gösteriliyor" not in metin
    assert "aday daha" not in metin


def test_digest_limiti_env_ile_ayarlanabilir():
    assert isinstance(config.DEFERRED_ALERT_DIGEST_LIMIT, int)
    assert config.DEFERRED_ALERT_DIGEST_LIMIT >= 1
    kaynak = open(main_mod.__file__, encoding="utf-8").read()
    # İki meşru çağrı yeri var: 18:45 digesti ve kaçırılan kapanış telafisi
    # (Batch 5). İkisi de env kaynaklı sabiti kullanır; gömülü sayı olmamalı.
    assert kaynak.count("limit=DEFERRED_ALERT_DIGEST_LIMIT") == 2, (
        "digest limiti env kaynaklı olmalı (sabit 12 kalmamalı)")
    assert "limit=12" not in kaynak and "limit = 12" not in kaynak


def test_tampon_bossa_digest_metni_cikmaz():
    assert main_mod._format_deferred_alert_summary([], toplam=5) == ""


# --- A3: özet ile panel aynı kaynaktan ------------------------------------

class _SahteLifecycle:
    """last_snapshots CASI: eski hatalı kod her zaman buraya düşüyordu."""

    def __init__(self):
        self.last_snapshots = {}


def test_ozet_live_state_formations_kaynagini_kullanir(monkeypatch):
    kayit = dict(stock="THYAO", timeframe="1h", pattern_name="Yükselen Üçgen",
                 quality=91.0, state="SIKISMA_GUCLENIYOR", contraction=0.83,
                 break_dir=1)

    class _LS:
        def formations(self):
            return [kayit]

    monkeypatch.setattr(main_mod, "_live_state", _LS())
    aktif = main_mod._build_active_formations_for_summary(_SahteLifecycle())
    assert len(aktif) == 1
    assert aktif[0]["stock_name"] == "THYAO"
    assert aktif[0]["confidence_score"] == 91.0


def test_ozet_daralmayi_korur_sikisanlar_bolumu_bosalmaz(monkeypatch):
    """A3c: contraction sabit None yazılırsa özetin ⚡ SIKIŞANLAR bölümü sessizce boşalır."""
    kayit = dict(stock="ASELS", timeframe="2h", pattern_name="Simetrik Üçgen",
                 quality=88.0, state="SIKISMA_GUCLENIYOR", contraction=0.9,
                 break_dir=0)

    class _LS:
        def formations(self):
            return [kayit]

    monkeypatch.setattr(main_mod, "_live_state", _LS())
    aktif = main_mod._build_active_formations_for_summary(_SahteLifecycle())
    assert aktif[0]["contraction"] == 0.9, "daralma gerçek kayıttan gelmeli"

    n = notifier_mod.TelegramNotifier()
    ozet = n.format_daily_summary(aktif, {"stocks_scanned": 48, "alerts_sent": 0})
    assert "SIKIŞANLAR" in ozet and "ASELS" in ozet


def test_live_state_bosken_lifecycle_snapshots_yedegi_calisir(monkeypatch):
    """İlk tarama öncesi (LiveState boş) davranış korunur."""
    class _BosLS:
        def formations(self):
            return []
    monkeypatch.setattr(main_mod, "_live_state", _BosLS())

    class _Snap:
        active = type("A", (), {"pattern_type": "Alçalan Kama", "contraction": 0.7})()
        state = "KIRILIM_ADI"  # içerik önemli değil
        effective_quality = 84.0
        break_dir = -1

    lc = _SahteLifecycle()
    lc.last_snapshots = {"GARAN_4h": _Snap()}
    aktif = main_mod._build_active_formations_for_summary(lc)
    assert aktif and aktif[0]["stock_name"] == "GARAN"
    assert aktif[0]["timeframe"] == "4h"


# --- A3a: public kanal filtresi (ölü dal kaldırıldı) ----------------------

def test_kanal_filtresi_public_states_disi_statelari_gondermez():
    n = notifier_mod.TelegramNotifier()
    n.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI"}
    n.public_min_quality = 80
    # SIKISMA varsayılan PUBLIC_STATES'te yok -> kanala gitmez (ölü dal kaldırıldı;
    # davranış aynı, karar artık env ile veriliyor).
    assert n.should_send_to_public({"state": "SIKISMA_GUCLENIYOR", "confidence_score": 95,
                                    "contraction": 0.95}) is False
    assert n.should_send_to_public({"state": "RETEST_BASARILI", "confidence_score": 85}) is True
    assert n.should_send_to_public({"state": "RETEST_BASARILI", "confidence_score": 79}) is False


def test_kanal_filtresi_sikisma_env_ile_acilabilir():
    n = notifier_mod.TelegramNotifier()
    n.public_states = {"SIKISMA_GUCLENIYOR"}
    n.public_min_quality = 80
    assert n.should_send_to_public({"state": "SIKISMA_GUCLENIYOR", "confidence_score": 88}) is True


# --- A3d: ölü [:10] kalıntısı geri gelmesin ------------------------------

def test_daily_summary_olu_onluk_liste_icermez():
    kaynak = open(notifier_mod.__file__, encoding="utf-8").read()
    assert "reverse=True)[:10]" not in kaynak, "kullanılmayan [:10] ölü kodu geri gelmiş"
    assert "reverse=True)[:3]" in kaynak or "for f in tamamlanan[:3]" in kaynak


# --- A9: günlük benzersiz formasyon sayacı --------------------------------

def test_gunluk_formasyon_sayaci_benzersiz_slot_sayar():
    main_mod._daily_pattern_keys.clear()
    main_mod.daily_stats['patterns_found'] = 0
    main_mod._note_pattern_found("THYAO", "1h")
    main_mod._note_pattern_found("THYAO", "1h")   # aynı slot: tekrar sayılmaz
    main_mod._note_pattern_found("thyao", "1H")   # büyük/küçük harf farkı da aynı slot
    assert main_mod.daily_stats['patterns_found'] == 1
    main_mod._note_pattern_found("GARAN", "4h")
    assert main_mod.daily_stats['patterns_found'] == 2


def test_gun_degisimi_formasyon_sayacini_sifirlar():
    from datetime import timedelta
    main_mod._daily_pattern_keys.clear()
    main_mod._note_pattern_found("THYAO", "1h")
    main_mod.daily_stats['last_reset'] = main_mod.daily_stats['last_reset'] - timedelta(days=1)
    main_mod.reset_daily_if_needed()
    assert main_mod.daily_stats['patterns_found'] == 0
    assert not main_mod._daily_pattern_keys
    # Diğer testleri etkilememek için bugünün tarihine geri dön.
    main_mod.daily_stats['last_reset'] = datetime.now(ISTANBUL_TZ).date()
