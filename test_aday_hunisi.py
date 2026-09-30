"""Batch 3: "kaç aday üretildi, kaçı nereye gitti" görünürlüğü.

Kapsam: günlük aday hunisi sayaçları (/durum), engel sayaçları (notifier),
/panel'de eşik altı satırı. Ağ yok; sahte notifier kullanılır.
"""

import logging
from datetime import datetime, timedelta

import pytest

import main as main_mod
import notifier as notifier_mod
from config import ISTANBUL_TZ


@pytest.fixture(autouse=True)
def _live_state_temiz():
    """Panel testleri global LiveState'e yazar; sonraki testleri kirletmesin."""
    yield
    now = datetime.now(ISTANBUL_TZ)
    main_mod._live_state.begin_scan(now, replace_all=True)
    main_mod._live_state.finish_scan(now, son_tarama_durumu="tamamlandi")


class _SahteNotifier:
    def __init__(self):
        self.veri = {"gonderilen_alarm": 4, "hatalar": 1,
                     "engeller": {"cooldown": 3, "gunluk_kap": 0, "saatlik_kap": 1}}

    def gonderim_durumu(self):
        return dict(self.veri)


def _huni_satiri():
    metin = main_mod._komut_durum("")
    return next((s for s in metin.splitlines() if "Aday hunisi" in s), "")


def _engel_satiri():
    metin = main_mod._komut_durum("")
    return next((s for s in metin.splitlines() if "Gönderim engeli" in s), "")


def test_durum_aday_hunisini_yazar():
    main_mod.daily_stats.update(
        patterns_found=21, alerts_sent=4, alerts_deferred=11,
        alerts_state_disabled=6, alerts_below_threshold=3, alerts_digest_overflow=0,
    )
    satir = _huni_satiri()
    assert "21 üretildi" in satir
    assert "4 push" in satir and "11 digest" in satir
    assert "6 state dışı" in satir and "3 eşik altı" in satir


def test_digest_tasmasi_varsa_hunide_gorunur():
    main_mod.daily_stats.update(patterns_found=21, alerts_sent=4, alerts_deferred=11,
                                alerts_state_disabled=6, alerts_below_threshold=3,
                                alerts_digest_overflow=2)
    assert "2 digest taşması" in _huni_satiri()


def test_engel_sayaclari_durumda_gorunur(monkeypatch):
    monkeypatch.setattr(main_mod, "_notifier_ref", _SahteNotifier())
    satir = _engel_satiri()
    assert "3 cooldown" in satir and "0 günlük kap" in satir
    assert "1 saatlik kap" in satir and "1 hata" in satir


def test_notifier_yoksa_durum_cokmez():
    eski = main_mod._notifier_ref
    try:
        main_mod._notifier_ref = None
        assert "Gönderim engeli" not in main_mod._komut_durum("")
    finally:
        main_mod._notifier_ref = eski


# --- notifier engel sayaçları ve sebep ayrımı -----------------------------

def _notifier():
    n = notifier_mod.TelegramNotifier()
    n.max_gunluk = 1000
    n.max_saatlik = 1000
    return n


def test_cooldown_engeli_sayilir_ve_sebep_yazilir():
    n = _notifier()
    key = n._cooldown_key("THYAO", "Simetrik Üçgen", "1h", "KIRILIM_TEYITLI")
    n.last_sent[key] = datetime.now(ISTANBUL_TZ)
    assert n.can_send("THYAO", "Simetrik Üçgen", "1h", "KIRILIM_TEYITLI") is False
    assert n.engeller["cooldown"] == 1
    assert n._son_engel == "cooldown"


def test_gunluk_kap_engeli_sayilir():
    n = _notifier()
    n.max_gunluk = 5
    n._gunluk_sayac = 5
    assert n.can_send("THYAO", "X", "1h", "KIRILIM_TEYITLI") is False
    assert n.engeller["gunluk_kap"] == 1 and n._son_engel == "gunluk_kap"


def test_saatlik_kap_engeli_sayilir_ama_kritik_state_gecer():
    n = _notifier()
    n.max_saatlik = 1
    n._saatlik_zamanlar = [datetime.now(ISTANBUL_TZ), datetime.now(ISTANBUL_TZ)]
    assert n.can_send("THYAO", "X", "1h", "SIKISMA_GUCLENIYOR") is False
    assert n.engeller["saatlik_kap"] == 1 and n._son_engel == "saatlik_kap"
    # Kritik state kapıyı geçer ve sayaç ARTMAZ (yanlış engel raporlanmasın).
    onceki = dict(n.engeller)
    assert n.can_send("GARAN", "X", "1h", "KIRILIM_TEYITLI") is True
    assert n.engeller == onceki
    assert n._son_engel is None


def test_gun_degisiminde_engel_sayaclari_sifirlanir():
    n = _notifier()
    n.engeller["cooldown"] = 7
    n.gonderim_hatasi = 2
    n.gonderilen_alarm = 5
    n._gunluk_tarih = n._gunluk_tarih - timedelta(days=1)
    n._gunu_sifirla_gerekirse()
    assert n.engeller == {"cooldown": 0, "gunluk_kap": 0, "saatlik_kap": 0}
    assert n.gonderim_hatasi == 0 and n.gonderilen_alarm == 0


# --- /panel: eşik altı adaylar -------------------------------------------

def _tarama_yayinla(kayitlar):
    now = datetime.now(ISTANBUL_TZ)
    hisseler = [k["stock"] for k in kayitlar]
    # replace_all=True: testler birbirinden etkilenmesin (kısmi tarama davranışı
    # ayrı test ediliyor; burada liste tamamen bu kayıtlarla kurulur).
    main_mod._live_state.begin_scan(now, beklenen_hisse=len(hisseler),
                                    scope=hisseler, replace_all=True)
    for k in kayitlar:
        main_mod._live_state.record_formation(k)
    main_mod._live_state.finish_scan(now, son_tarama_durumu="tamamlandi",
                                     son_tarama_hissesi=len(hisseler),
                                     son_tarama_beklenen_hisse=len(hisseler))


def test_panel_esik_alti_adaylari_soyler():
    _tarama_yayinla([
        dict(stock="THYAO", timeframe="1h", pattern_name="Simetrik Üçgen", quality=90,
             state="SIKISMA_GUCLENIYOR", min_quality=80, contraction=0.85, critical_price=10),
        dict(stock="GARAN", timeframe="1h", pattern_name="Yükselen Üçgen", quality=62,
             state="SIKISMA_GUCLENIYOR", min_quality=80, contraction=0.5, critical_price=5),
    ])
    panel = main_mod._panel_raporu("")
    assert "1 aday alarm eşiğinin altında" in panel


def test_panel_esik_alti_yoksa_satir_basmaz():
    _tarama_yayinla([
        dict(stock="AKBNK", timeframe="2h", pattern_name="Alçalan Üçgen", quality=95,
             state="SIKISMA_GUCLENIYOR", min_quality=78, contraction=0.9, critical_price=10),
    ])
    panel = main_mod._panel_raporu("")
    assert "alarm eşiğinin altında" not in panel


def test_huni_sayaclari_gun_degisiminde_sifirlanir():
    main_mod.daily_stats.update(alerts_deferred=11, alerts_below_threshold=3,
                                alerts_state_disabled=6, alerts_attempted=5, alerts_failed=1)
    main_mod.daily_stats['last_reset'] = main_mod.daily_stats['last_reset'] - timedelta(days=1)
    main_mod.reset_daily_if_needed()
    for alan in ("alerts_deferred", "alerts_below_threshold", "alerts_state_disabled",
                 "alerts_attempted", "alerts_failed", "alerts_digest_overflow"):
        assert main_mod.daily_stats[alan] == 0, alan
    main_mod.daily_stats['last_reset'] = datetime.now(ISTANBUL_TZ).date()
