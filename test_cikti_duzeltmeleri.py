"""Faz 0 çıktı düzeltmeleri: yanıltıcı satırlar + kalıcı gün işaretleri."""

import pytest

import main as main_mod
import notifier as notifier_mod
import state.persistence as persistence


@pytest.fixture
def notifier(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.delenv("TELEGRAM_GROUP_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)
    return notifier_mod.TelegramNotifier()


def _formasyon(state="FORMASYON_TAMAMLANDI", stock="ISMEN", tf="4h", q=87):
    return {"stock_name": stock, "timeframe": tf, "pattern_name": "Alçalan Üçgen",
            "state": state, "confidence_score": q, "contraction": 0.8}


# --- "432 hisse tarandı" yanılgısı -----------------------------------------

def test_gun_satiri_tarama_turunu_yazar(notifier):
    metin = notifier.format_daily_summary([_formasyon()], {"tarama_sayisi": 9, "alerts_sent": 28})
    assert "📈 Gün: 9 tarama" in metin
    assert "48 hisse × 4 zaman dilimi" in metin
    assert "28 bildirim" in metin
    assert "432" not in metin


def test_gun_satiri_sabah_yoksa_henuz_der(notifier):
    metin = notifier.format_daily_summary([_formasyon()], {"tarama_sayisi": 0, "alerts_sent": 0})
    assert "henüz tarama yapılmadı" in metin
    assert "0 hisse tarandı" not in metin


# --- "TAMAMLANAN (6)" ama 3 satır -------------------------------------------

def test_ozet_basligi_kac_satir_listelendigini_soyler(notifier):
    aktif = [_formasyon(stock=f"SYM{i}") for i in range(6)]
    metin = notifier.format_daily_summary(aktif)
    assert "TAMAMLANAN (6 · ilk 3)" in metin
    assert len([s for s in metin.splitlines() if s.startswith("•")]) == 3


def test_ozet_basligi_az_sayida_ek_vermez(notifier):
    metin = notifier.format_daily_summary([_formasyon(), _formasyon(stock="GARAN")])
    assert "TAMAMLANAN (2)" in metin


# --- Başarısız kırılım günde bir sayılır ------------------------------------

def test_basarisiz_kirilim_gunde_bir_sayilir():
    main_mod._daily_basarisiz_keys.clear()
    main_mod.daily_stats['basarisiz_kirilim'] = 0
    main_mod._note_basarisiz_kirilim("TSKB", "4h", "2026-10-02 11:30")
    main_mod._note_basarisiz_kirilim("TSKB", "4h", "2026-10-02 11:30")   # aynı olay
    assert main_mod.daily_stats['basarisiz_kirilim'] == 1
    main_mod._note_basarisiz_kirilim("TCELL", "4h", "2026-10-02 11:30")
    assert main_mod.daily_stats['basarisiz_kirilim'] == 2


# --- Kalıcı gönderim işaretleri --------------------------------------------

def test_gonderim_durumu_kalicidir(tmp_path):
    assert persistence.gonderim_durumu_yukle(data_dir=str(tmp_path)) == {}
    assert persistence.gonderim_durumu_kaydet(
        {"post_close_analizi_gun": "2026-10-02"}, data_dir=str(tmp_path)) is True
    assert persistence.gonderim_durumu_yukle(
        data_dir=str(tmp_path))["post_close_analizi_gun"] == "2026-10-02"
    # Birleştirir: ikinci anahtar ilkini silmez
    persistence.gonderim_durumu_kaydet({"baska": 1}, data_dir=str(tmp_path))
    veri = persistence.gonderim_durumu_yukle(data_dir=str(tmp_path))
    assert veri["post_close_analizi_gun"] == "2026-10-02" and veri["baska"] == 1


def test_gonderim_durumu_bozuk_dosyada_bos_doner(tmp_path):
    (tmp_path / "gonderim_durumu.json").write_text("{bozuk json", encoding="utf-8")
    assert persistence.gonderim_durumu_yukle(data_dir=str(tmp_path)) == {}


# --- /durum public sayaçları ----------------------------------------------

def test_gonderim_durumu_public_alanlarini_tasir(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    n = notifier_mod.TelegramNotifier()
    durum = n.gonderim_durumu()
    assert durum["public_enabled"] is True
    assert durum["public_chat_id"] == "-1001234567890"
    for anahtar in ("public_gonderilen", "public_hatasi", "public_engel",
                    "public_kuyruk", "public_kuyruk_tasmasi"):
        assert anahtar in durum
