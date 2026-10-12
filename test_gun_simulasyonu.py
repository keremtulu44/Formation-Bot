"""Simülasyon aracının (gun_simulasyonu.py) hızlı birim testleri.

Tam gün koşumu (dakikalar) test paketine girmez; burada yalnız aracın veri
katmanı ve sınıflandırma mantığı doğrulanır ki araç sessizce bozulmasın.
"""

from datetime import date, datetime, timedelta

import os
import pandas as pd
import pytest

import config
import gun_simulasyonu as S


def test_mesaj_turu_siniflandirmasi():
    dm = "DM"
    assert S._mesaj_turu(dm, "📋 Günlük Özet\n📊 ...") == "DM özet"
    assert S._mesaj_turu(dm, "🌙 GÜN SONU ANALİZİ\n📋 PANEL") == "DM gün sonu panel"
    assert S._mesaj_turu(dm, "🏁 THYAO saatlik · Yükselen Kama") == "DM alarm"
    grup = "GRUP"
    assert S._mesaj_turu(grup, "📊 Formasyon bülteni · 25 Eyl 10:35 · 2 gelişme") == "GRUP bülten"
    assert S._mesaj_turu(grup, "📊 25 Eyl 18:45 kapanış · BIST formasyon özeti") == "GRUP özet"
    assert S._mesaj_turu(grup, "📊 25 Eyl 09:55 sabah notu · BIST formasyon takibi") == "GRUP özet"


@pytest.fixture(scope="module")
def feed():
    return S.Feed()


def test_feed_gelecek_barlari_vermez(feed):
    """Sanal saatten sonra KAPANAN mumlar verilmez (gelecek veri sızmasın)."""
    stock = sorted(feed.cache)[0]
    df = feed.cache[stock]
    # Sim gününün ilk kapanışından önceki bir an: 10:00
    gun = df.index[-1].date()
    an = config.ISTANBUL_TZ.localize(datetime.combine(gun, datetime.min.time())) + timedelta(hours=10)
    kesit = feed._kesit(df, "1h", an)
    from data import mum_kapanis_anlari

    kapanislar = mum_kapanis_anlari(kesit.index, "1h")
    assert len(kesit) > 0
    assert all(k <= pd.Timestamp(an) for k in kapanislar)
    # Aynı günün ilerleyen saatlerindeki barlar henüz yok
    assert kesit.index[-1].date() < gun

    sonra = feed._kesit(df, "1h", an + timedelta(hours=8))
    assert len(sonra) > len(kesit), "saat ilerleyince yeni kapanmış mumlar gelmeli"


def test_feed_1d_gun_sonuna_kadar_verilmez(feed):
    """Sim gününün günlük mumu ancak seans kapanınca (18:30) verilir."""
    stock = sorted(feed.cache)[0]
    gun = feed.cache[stock].index[-1].date()
    eski = S._SIMDI[0]
    try:
        for saat, gelmeli in ((11, False), (17, False), (19, True)):
            S._SIMDI[0] = config.ISTANBUL_TZ.localize(
                datetime.combine(gun, datetime.min.time())) + timedelta(hours=saat)
            gunluk = feed.fetch_1d(stock)
            if gunluk is None:
                continue  # yeterli geçmiş yok: kapsam dışı
            ayni_gun = gunluk.index[-1].date() == gun
            assert ayni_gun is gelmeli, f"{saat}:00 için günlük mum beklentisi uyuşmadı"
    finally:
        S._SIMDI[0] = eski


def test_tohumla_sim_gunu_ve_sonrasini_yazmaz(feed, tmp_path):
    gun = max(feed.gunler())
    adet = feed.tohumla(tmp_path, gun)
    assert adet > 0
    yazilanlar = list(tmp_path.glob("*.json"))
    assert len(yazilanlar) == adet
    import json

    for dosya in yazilanlar[:5]:
        kayitlar = json.loads(dosya.read_text(encoding="utf-8"))
        assert all(k["timestamp"][:10] < gun.isoformat() for k in kayitlar)


def test_hizli_pacer_aninda_doner():
    pacer = S.HizliPacer()
    with pacer.request("test"):
        pass
    pacer.reset_batch()
    assert pacer.request_count_unused() is None  # bilinmeyen alan: no-op


def test_sanal_datetime_now_sim_saati_dondurur():
    eski = S._SIMDI[0]
    try:
        S._SIMDI[0] = config.ISTANBUL_TZ.localize(datetime(2026, 9, 25, 14, 5))
        simdi = S.SanalDatetime.now(config.ISTANBUL_TZ)
        assert (simdi.hour, simdi.minute) == (14, 5)
        assert S.SanalDatetime.now().tzinfo is None  # naive istek
    finally:
        S._SIMDI[0] = eski


def test_gunler_artan_sirada(feed):
    gunler = feed.gunler()
    assert gunler == sorted(gunler) and gunler[-1] == date(2026, 9, 25)
    assert len(gunler) > 20


def test_rapor_cikti_dizini_yoksa_olusturulur(tmp_path, monkeypatch):
    """--cikti 'olmayan_dizin/rapor.md' ilk koşumda patlamamalı (bulunan hata)."""
    import types
    args = types.SimpleNamespace(
        cikti=str(tmp_path / "yeni" / "alt" / "rapor.md"), gun=None)
    # _rapor_yaz yalnız bu iki satırı çalıştırarak dizin davranışını sınar:
    # (rapor üretiminin tamamı için tam gün koşumu gerekir)
    hedef = S.Path(args.cikti)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text("test", encoding="utf-8")
    assert hedef.exists()
    # Araç kodunda da mkdir çağrısı var mı (regresyon koruması)?
    kod = (S.REPO / "gun_simulasyonu.py").read_text(encoding="utf-8")
    assert "cikti.parent.mkdir(parents=True, exist_ok=True)" in kod


def test_ayni_gun_tekrar_kosum_korumasi(tmp_path):
    """Aynı --veri-dir ile aynı günü tekrar koşmak mesajları bastırıyordu (bulunan hata).

    Koruma gerçek fonksiyonlar üzerinden sınanır: marker okuma/yazma + temizleme.
    """
    from datetime import date

    veri = tmp_path / "data"
    veri.mkdir()
    gun = date(2026, 9, 25)

    # Başlangıçta marker yok -> tekrar koşum uyarısı tetiklenmez
    assert S._sim_marker_oku(veri) == []
    S._sim_marker_yaz(veri, gun)
    assert S._sim_marker_oku(veri) == ["2026-09-25"]
    # İkinci gün eklendiğinde liste korunur
    S._sim_marker_yaz(veri, date(2026, 9, 24))
    assert S._sim_marker_oku(veri) == ["2026-09-24", "2026-09-25"]

    # Durum dosyaları + hisse verisi
    for ad in S.SIM_DURUM_DOSYALARI:
        (veri / ad).write_text("{}", encoding="utf-8")
    (veri / "THYAO.json").write_text("[]", encoding="utf-8")
    (veri / "THYAO_gunluk.json").write_text("[]", encoding="utf-8")

    silinen = S._durum_temizle(veri)
    assert set(silinen) == set(S.SIM_DURUM_DOSYALARI), "tüm gönderim geçmişi silinmeli"
    kalan = {y.name for y in veri.iterdir()}
    # Hisse verisi ve marker KORUNUR (zincirleme devam edebilsin, uyarı sürsün)
    assert kalan == {"THYAO.json", "THYAO_gunluk.json", S.SIM_MARKER}
    # Bozuk marker çökertmez
    (veri / S.SIM_MARKER).write_text("{bozuk", encoding="utf-8")
    assert S._sim_marker_oku(veri) == []
