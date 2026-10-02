"""Haftalık doğruluk karnesi testleri (karne.py + main entegrasyonu).

Kapsam:
  * Sinyal defteri: kayıt / tekilleştirme / atomik yerel dosya (Supabase YOK),
  * İleri performans: MFE/MAE + ilk dokunuş yarışı (hedef/stop/nötr), yön aynası,
  * Rapor metni: sayılar, TF kırılımı, hisse listesi, huni, uyarılar,
  * Cuma kapısı + haftada bir gönderim işareti,
  * main entegrasyonu: tarama sırasında defter kaydı, /karne komutu.
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

import karne as K

IST = K.ISTANBUL_TZ


def t(yil, ay, gun, saat=0, dakika=0):
    return IST.localize(datetime(yil, ay, gun, saat, dakika))


def _seri(baslangic: datetime, kapanislar, bar_dk=60):
    idx = pd.DatetimeIndex([baslangic + timedelta(minutes=bar_dk * i)
                            for i in range(len(kapanislar))])
    df = pd.DataFrame({
        "open": kapanislar,
        "high": [c * 1.002 for c in kapanislar],
        "low": [c * 0.998 for c in kapanislar],
        "close": kapanislar,
        "volume": [1000] * len(kapanislar),
    }, index=idx)
    return df


@pytest.fixture
def defter(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    return K.KarneDefteri()


# === 1) DEFTER ============================================================

def test_kayit_yukle_dongusu_yerel_dosya(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    d = K.KarneDefteri()
    assert d.formasyon_kaydet("THYAO", "4h", "Simetrik Üçgen", "SIKISMA_GUCLENIYOR", 84.0,
                              t(2026, 10, 2, 13, 30)) is True
    assert d.kirilim_kaydet("THYAO", "4h", "Simetrik Üçgen", "KIRILIM_TEYITLI", 1,
                            292.25, 3.4, 84.0, t(2026, 10, 2, 13, 30)) is True
    dosya = tmp_path / K.KARNE_DOSYA
    assert dosya.exists(), "defter yerel dosyaya yazılmadı (Supabase'siz çalışmalı)"
    # Yeni nesne diskten okur (restart dayanıklılığı)
    d2 = K.KarneDefteri()
    assert d2.boyut() == 2
    assert any(k["tip"] == "kirilim" for k in d2.kayitlar())


def test_kirilim_ayni_bar_iki_kez_sayilmaz(defter):
    kw = dict(stock="GARAN", tf="1h", pattern="Yükselen Üçgen", state="KIRILIM_TEYITLI",
              dir=1, entry=120.0, atr=1.2, quality=82.0, bar_zamani=t(2026, 10, 2, 14, 30))
    assert defter.kirilim_kaydet(**kw) is True
    assert defter.kirilim_kaydet(**kw) is False
    assert defter.boyut() == 1


def test_formasyon_ttl_ile_tekillesir(defter):
    z = t(2026, 10, 2, 11, 30)
    assert defter.formasyon_kaydet("ASELS", "1h", "Üçgen", "FORMASYON_TANIMLANDI", 80, z) is True
    # Aynı hisse/TF/formasyon 48 saat içinde yeniden sayılmaz (motor her taramada üretir)
    assert defter.formasyon_kaydet("ASELS", "1h", "Üçgen", "OLGUNLASIYOR", 85,
                                   z + timedelta(hours=5)) is False
    # Farklı formasyon adı yeni kayıt
    assert defter.formasyon_kaydet("ASELS", "1h", "Boğa Bayrağı", "SIKISMA_GUCLENIYOR", 80,
                                   z + timedelta(hours=6)) is True


def test_gecersiz_kirilim_kaydedilmez(defter):
    assert defter.kirilim_kaydet("X", "1h", "Üçgen", "KIRILIM_TEYITLI", 0, 10.0, 1.0, 80,
                                 t(2026, 10, 2)) is False
    assert defter.kirilim_kaydet("X", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, None, 1.0, 80,
                                 t(2026, 10, 2)) is False


def test_buda_eski_kayitlari_siler(defter):
    eski = datetime.now(IST) - timedelta(days=200)
    defter.kirilim_kaydet("ESKI", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, 10.0, 0.5, 70,
                          t(2026, 3, 2, 10, 30), now=eski)
    defter.kirilim_kaydet("YENI", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, 10.0, 0.5, 70,
                          t(2026, 10, 1, 10, 30))
    assert defter.boyut() == 2
    assert defter.buda() == 1
    assert defter.boyut() == 1


# === 2) PERFORMANS ÖLÇÜMÜ =================================================

def _kirilim_kaydi(yon=1, entry=100.0, atr=2.0, saat=10, gun=1):
    return {"tip": "kirilim", "stock": "TEST", "tf": "1h", "dir": yon, "entry": entry,
            "atr": atr, "quality": 80.0, "bar_time": t(2026, 10, gun, saat, 30).isoformat(),
            "kayit_zaman": t(2026, 10, gun, saat, 30).isoformat()}


def test_yukari_kirilim_hedefe_ulasir():
    # Giriş 100; sonraki barlarda 104'e çıkıyor (hedef 1.5 ATR = 103)
    df = _seri(t(2026, 10, 1, 10, 30), [100, 101, 102, 104, 103])
    sonuc = K.sinyal_sonucu(_kirilim_kaydi(), df)
    assert sonuc["durum"] == K.DURUM_HEDEF
    assert sonuc["hedef_bar"] == 3   # 3. barda 103+ (1.5 ATR) görüldü
    assert sonuc["mfe_atr"] >= 1.5


def test_yukari_kirilim_stop_olur():
    # Giriş 100; 97'ye düşüyor (stop 1.0 ATR = 98) -> stop daha önce
    df = _seri(t(2026, 10, 1, 10, 30), [100, 99.5, 97.5, 101, 104])
    sonuc = K.sinyal_sonucu(_kirilim_kaydi(), df)
    assert sonuc["durum"] == K.DURUM_STOP
    assert sonuc["stop_bar"] == 2   # 2. barda 98 (1.0 ATR) altı görüldü


def test_asagi_kirilim_aynasi():
    # Aşağı yönlü sinyalde düşüş "lehte" sayılır
    df = _seri(t(2026, 10, 1, 10, 30), [100, 98, 96, 95, 96])
    sonuc = K.sinyal_sonucu(_kirilim_kaydi(yon=-1), df)
    assert sonuc["durum"] == K.DURUM_HEDEF
    assert sonuc["son_pct"] > 0
    # Aynı seri yukarı yönlü sinyalde stop olur
    assert K.sinyal_sonucu(_kirilim_kaydi(yon=1), df)["durum"] == K.DURUM_STOP


def test_notr_ve_bekleyen():
    yatay = _seri(t(2026, 10, 1, 10, 30), [100, 100.2, 99.9, 100.1])
    assert K.sinyal_sonucu(_kirilim_kaydi(), yatay)["durum"] == K.DURUM_NOTR
    # Sinyal son bar: ileri bar yok -> bekliyor
    df = _seri(t(2026, 10, 1, 10, 30), [100, 101])
    kayit = _kirilim_kaydi()
    kayit["bar_time"] = df.index[-1].isoformat()
    assert K.sinyal_sonucu(kayit, df)["durum"] == K.DURUM_BEKLIYOR


def test_seri_yoksa_none():
    assert K.sinyal_sonucu(_kirilim_kaydi(), None) is None
    assert K.sinyal_sonucu(_kirilim_kaydi(), pd.DataFrame()) is None


def test_atr_hesabi():
    df = _seri(t(2026, 10, 1, 10, 30), [100, 101, 102])
    deger = K.atr_hesapla(df)
    assert deger is not None and deger > 0


# === 3) RAPOR METNİ =======================================================

def _dolu_defter(defter):
    z = K.hafta_baslangici(t(2026, 10, 2, 18, 0))  # pazartesi
    # Formasyonlar: TF ve hisse kırılımı
    for hisse, tf in [("THYAO", "1h"), ("THYAO", "4h"), ("ASELS", "1h"),
                      ("GARAN", "1d"), ("EREGL", "2h")]:
        defter.formasyon_kaydet(hisse, tf, "Simetrik Üçgen", "SIKISMA_GUCLENIYOR", 82,
                                z + timedelta(hours=10), now=z + timedelta(hours=10))
    # Kırılımlar: biri hedef (yükseliyor), biri stop (düşüyor)
    defter.kirilim_kaydet("THYAO", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, 100.0, 2.0, 84,
                          t(2026, 10, 1, 10, 30), now=t(2026, 10, 1, 15, 30))
    defter.kirilim_kaydet("ASELS", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, 100.0, 2.0, 74,
                          t(2026, 10, 1, 10, 30), now=t(2026, 10, 1, 15, 30))
    defter.olay_kaydet("THYAO", "1h", "FORMASYON_TAMAMLANDI", t(2026, 10, 1, 15, 30),
                       now=t(2026, 10, 1, 15, 30))
    return defter


def _saglayici(stock, tf):
    if stock == "THYAO":
        return _seri(t(2026, 10, 1, 10, 30), [100, 101, 102, 104, 103])   # hedef
    return _seri(t(2026, 10, 1, 10, 30), [100, 99, 97, 96, 96])           # stop


def test_karne_metni_istenen_ciktilar(defter):
    d = _dolu_defter(defter)
    metin = K.karne_uret(d, _saglayici, now=t(2026, 10, 2, 18, 45))
    assert "HAFTALIK DOĞRULUK KARNESİ" in metin
    assert "Formasyon tespiti: 5" in metin
    assert "1 saatlik 2" in metin and "4 saatlik 1" in metin and "günlük 1" in metin
    assert "Hisse: (4 hisse)" in metin
    assert "THYAO 2" in metin and "ASELS 1" in metin
    assert "Kırılım sinyali: 2" in metin
    assert "hedef 1" in metin and "stop 1" in metin
    assert "Kırılım yönünde kapatan: 1/2" in metin
    assert "Kalite: q≥80 1/1 · q70–79 0/1" in metin
    assert "Huni: kırılım 2 → tamamlanan 1" in metin
    assert "Supabase gerekmez" in metin


def test_karne_gun_sayisi_penceresi(defter):
    d = _dolu_defter(defter)
    hafta = K.karne_uret(d, _saglayici, now=t(2026, 10, 2, 18, 45))
    otuz = K.karne_uret(d, _saglayici, now=t(2026, 10, 2, 18, 45), gun_sayisi=30)
    assert "HAFTALIK DOĞRULUK KARNESİ" in hafta
    assert "SON 30 GÜN DOĞRULUK KARNESİ" in otuz
    assert "Formasyon tespiti: 5" in otuz


def test_bos_defter_metni(defter):
    metin = K.karne_uret(defter, _saglayici, now=t(2026, 10, 2, 18, 45))
    assert "Formasyon tespiti: 0" in metin
    assert "Kırılım sinyali: 0" in metin


# === 4) CUMA KAPISI + GÖNDERİM TEKİLLİĞİ =================================

def test_karne_gunu_cuma():
    assert K.karne_gunu_mu(t(2026, 10, 2, 18, 45)) is True    # Cuma
    assert K.karne_gunu_mu(t(2026, 10, 1, 18, 45)) is False   # Perşembe


def test_hafta_damgasi_iso():
    assert K.hafta_damgasi(t(2026, 10, 2, 18, 45)) == "2026-W40"
    assert K.hafta_damgasi(t(2026, 10, 9, 18, 45)) == "2026-W41"


def test_gonderim_isareti_kalici(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    d = K.KarneDefteri()
    assert d.karne_gonderildi_mi("2026-W40") is False
    d.karne_gonderildi_isaretle("2026-W40")
    assert K.KarneDefteri().karne_gonderildi_mi("2026-W40") is True


def test_karne_hafta_baslangici_pazartesi():
    bas = K.hafta_baslangici(t(2026, 10, 2, 18, 45))
    assert bas.weekday() == 0 and bas.day == 28 and bas.hour == 0


# === 5) MAIN ENTEGRASYONU =================================================

def test_main_karne_ekleme_kapisi(monkeypatch, tmp_path):
    import main as M
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    d = M._karne_al()
    d.formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82, t(2026, 10, 2, 10, 30))
    # Cuma -> eklenir ve metin döner
    metin = M._haftalik_karne_ekle(t(2026, 10, 2, 18, 45), None)
    assert "HAFTALIK DOĞRULUK KARNESİ" in metin
    # İşaretlenince aynı hafta tekrar eklenmez
    M._karne_gonderildi_isaretle(t(2026, 10, 2, 18, 45))
    assert M._haftalik_karne_ekle(t(2026, 10, 2, 18, 50), None) == ""
    # Perşembe hiç eklenmez
    assert M._haftalik_karne_ekle(t(2026, 10, 8, 18, 45), None) == ""


def test_main_komut_karne(monkeypatch, tmp_path):
    import main as M
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    cevap_bos = M._komut_karne("")
    assert "boş" in cevap_bos.lower()
    M._karne_al().formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82,
                                   t(2026, 10, 2, 10, 30))
    cevap = M._komut_karne("")
    assert "DOĞRULUK KARNESİ" in cevap and "Formasyon tespiti: 1" in cevap
    assert "karne_defteri.json" in cevap
    assert "Kullanım: /karne" in M._komut_karne("abc")


def test_main_komut_tablosunda_karne_var():
    import main as M
    assert M.TELEGRAM_KOMUTLARI["karne"] is M._komut_karne
    assert M.TELEGRAM_KOMUTLARI["karnem"] is M._komut_karne
    assert "/karne" in M.KOMUT_YARDIM


def test_tarama_sirasinda_defter_kaydi(monkeypatch, tmp_path):
    """scan_all_stocks, kırılım teyidinde deftere performans kaydı düşer."""
    import main as M
    from data import StockDequeManager
    from patterns import PatternLifecycleManager
    from types import SimpleNamespace

    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    monkeypatch.setattr(M, "fetch_1h_stocks_paced", lambda *a, **k: ({}, {}, 0, 0))

    class Aday:
        pattern_type, upper_now, lower_now, contraction = "Simetrik Üçgen", 100.0, 95.0, 0.7
        upper_touches, lower_touches, break_strength, start_bar = 2, 2, 80.0, 10

    snap = SimpleNamespace(state="KIRILIM_TEYITLI", break_dir=1, log="sahte", active=Aday(),
                           effective_quality=85.0, bar_index=30, retest_seen=True,
                           invalid_reason="Yok")
    lm = PatternLifecycleManager()
    monkeypatch.setattr(lm, "scan", lambda *a, **k: snap)
    notifier = M.TelegramNotifier()
    monkeypatch.setattr(notifier, "send", lambda data, kuyrukla=True: True)

    yedek = dict(M.daily_stats)
    try:
        M.scan_all_stocks(StockDequeManager(), lm, notifier, stocks=["THYAO"], send_alerts=True)
    finally:
        M.daily_stats.clear()
        M.daily_stats.update(yedek)
        M._live_state.begin_scan(datetime.now(IST), manuel=True, beklenen_hisse=0,
                                 scope=[], replace_all=True)
        M._live_state.finish_scan()

    kayitlar = M._karne_al().kayitlar()
    kirilimlar = [k for k in kayitlar if k["tip"] == "kirilim"]
    assert kirilimlar, "kırılım deftere yazılmadı"
    assert kirilimlar[0]["stock"] == "THYAO" and kirilimlar[0]["dir"] == 1
    assert kirilimlar[0]["entry"] > 0


# === 6) MESAJ SINIRI GÜVENLİĞİ ===========================================

def test_karne_sigarsa_altina_eklenir():
    import main as M

    class N:
        def __init__(self):
            self.gonderilenler = []

        def send_text(self, metin):
            self.gonderilenler.append(metin)
            return True, ""

    n = N()
    ok, _ = M._karneyle_gonder(n, "📋 Günlük Özet\nkısa", "📊 KARNE\nsatır")
    assert ok and len(n.gonderilenler) == 1
    assert n.gonderilenler[0].endswith("📊 KARNE\nsatır"), "karne ana mesajın ALTINDA olmalı"


def test_karne_sigmazsa_ayri_mesaj_ve_kesilmez():
    import main as M

    class N:
        def __init__(self):
            self.gonderilenler = []

        def send_text(self, metin):
            self.gonderilenler.append(metin)
            return True, ""

    n = N()
    ana = "x" * 4000          # kirp() ile kesilecek uzunluk
    karne = "📊 KARNE\n" + "y" * 300
    ok, _ = M._karneyle_gonder(n, ana, karne)
    assert ok and len(n.gonderilenler) == 2
    assert n.gonderilenler[0] == ana                    # ana mesaj kırpılmadı
    assert n.gonderilenler[1] == karne                  # karne tam gitti (kesilmedi)


def test_karne_gonderilemezse_isaretlenmez(monkeypatch, tmp_path):
    """Gönderim başarısızsa haftalık işaret konmaz -> sonraki gün sonu tekrar denenir."""
    import main as M
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    M._karne_al().formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82,
                                   t(2026, 10, 2, 10, 30))

    class N:
        def send_text(self, metin):
            return False, "ağ hatası"

    ok, hata = M._karneyle_gonder(N(), "özet", "karne")
    assert ok is False and "ağ" in hata
    assert M._karne_al().karne_gonderildi_mi("2026-W40") is False


# === 7) OPSİYONEL UZAK YEDEK (Supabase KURULU DEĞİLSE DEĞİŞMEZ) ===========

class _SahteStore:
    """SupabaseStore yerine geçen basit sahte (yalnız test)."""

    def __init__(self, veri=None):
        self.veri = dict(veri or {})
        self.yazma = 0
        self.hata = False

    def get_many(self, keys):
        if self.hata:
            raise RuntimeError("uzak yok")
        return {k: self.veri.get(k) for k in keys}

    def upsert(self, key, payload):
        if self.hata:
            raise RuntimeError("uzak yok")
        self.veri[key] = payload
        self.yazma += 1
        return True


def test_store_yoksa_defter_sadece_yerel(defter, tmp_path):
    """Supabase YOK: defter yerel dosyayla tam çalışır (kullanıcı şartı)."""
    import state.persistence as SP
    assert SP.karne_defteri_yukle(defter, None) == 0
    assert SP.karne_defteri_kaydet(defter, None) is False
    defter.formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82, t(2026, 10, 2, 10))
    assert (tmp_path / K.KARNE_DOSYA).exists()
    assert K.KarneDefteri().boyut() == 1


def test_uzak_yedek_birlestirir(tmp_path, monkeypatch):
    """Supabase VARSA: yerel (restart sonrası) + uzak defter birleşir, veri kaybolmaz."""
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    import state.persistence as SP

    # Uzakta geçen haftanın kayıtları var; yerelde sadece bu restart'ta yazılan var
    uzak = K.KarneDefteri(dosya=str(tmp_path / "uzak.json"))
    uzak.formasyon_kaydet("ASELS", "4h", "Üçgen", "SIKISMA_GUCLENIYOR", 80, t(2026, 9, 30, 10))
    store = _SahteStore({"state:karne_defteri": uzak.snapshot()})

    yerel = K.KarneDefteri()
    yerel.formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82, t(2026, 10, 2, 10))
    assert yerel.boyut() == 1
    eklenen = SP.karne_defteri_yukle(yerel, store)
    assert eklenen == 1 and yerel.boyut() == 2
    # Yerel kopya kazanır: tekrar birleştirme çift kayıt üretmez
    assert SP.karne_defteri_yukle(yerel, store) == 0


def test_uzak_yedek_yazilir_ve_tasir(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    import state.persistence as SP
    store = _SahteStore()
    d = K.KarneDefteri()
    d.kirilim_kaydet("THYAO", "1h", "Üçgen", "KIRILIM_TEYITLI", 1, 100.0, 2.0, 84,
                     t(2026, 10, 2, 10, 30))
    assert SP.karne_defteri_kaydet(d, store) is True
    assert store.yazma == 1
    # /tmp silindikten sonra (yeni ortam) yalnız uzaktan geri yüklenebilmeli
    (tmp_path / K.KARNE_DOSYA).unlink()
    yeni = K.KarneDefteri()
    assert yeni.boyut() == 0
    assert SP.karne_defteri_yukle(yeni, store) == 1
    assert yeni.kayitlar()[0]["stock"] == "THYAO"


def test_uzak_hata_karneyi_durdurmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    import state.persistence as SP
    store = _SahteStore()
    store.hata = True
    d = K.KarneDefteri()
    d.formasyon_kaydet("THYAO", "1h", "Üçgen", "SIKISMA_GUCLENIYOR", 82, t(2026, 10, 2, 10))
    assert SP.karne_defteri_yukle(d, store) == 0        # sessizce 0
    assert SP.karne_defteri_kaydet(d, store) is False   # sessizce False
    assert d.boyut() == 1 and (tmp_path / K.KARNE_DOSYA).exists()


def test_main_karne_al_uzak_yedekle_birlesir(monkeypatch, tmp_path):
    """main._karne_al: yerel boşken uzak yedekten doldurur (Render restart senaryosu)."""
    import main as M
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    uzak = K.KarneDefteri(dosya=str(tmp_path / "uzak.json"))
    uzak.formasyon_kaydet("GARAN", "1d", "Üçgen", "SIKISMA_GUCLENIYOR", 78, t(2026, 10, 1, 10))
    monkeypatch.setattr(M, "_supabase_store_ref", _SahteStore({"state:karne_defteri": uzak.snapshot()}))
    try:
        d = M._karne_al()
        assert d.boyut() == 1 and d.kayitlar()[0]["stock"] == "GARAN"
    finally:
        monkeypatch.setattr(M, "_supabase_store_ref", None)
        monkeypatch.setattr(M, "_karne_defteri", None)
