"""Faz 2.5 — Outcome Link testleri.

KAPSAM: Formation History ile MEVCUT Karne/outcome sistemi arasındaki bağlantı.

BU TURDA DEĞİŞTİRİLMEYENLER (testler mevcut haliyle kullanır):
  * `sinyal_sonucu()` ve tüm outcome matematiği (MFE/MAE, ATR hedef/stop, horizon,
    HEDEF/STOP/NÖTR/BEKLIYOR karar mantığı) — yalnızca ÇAĞRILIR.
  * Karne kayıt biçimi, dedup anahtarları, `formasyon_kaydet` TTL'si.
  * `karne_hesapla` sonuçları.
  * Eski (stable_id'siz) kayıtlar: silinmez, migrate edilmez, görmezden gelinir.

Doğrulanan davranışlar:
  1. stable_id -> outcome doğru bağlanıyor
  2. iki formation -> iki ayrı outcome (multi-formation izolasyonu)
  3. outcome'ı olmayan formation -> yanlış sonuç üretmiyor
  4. terminal formation -> sonucu sonradan okunabiliyor
  5. restart -> linkage korunuyor
  6. eski stable_id'siz Karne kayıtları -> bozulmuyor
  7. mevcut sinyal_sonucu() sonuçları değişmiyor

Çalıştırma:  python3 -m pytest test_outcome_link.py -q
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

import config as config_mod
import karne as K
from karne import KarneDefteri
from state import formation_history as fh
from state import outcome_link as ol

IST = K.ISTANBUL_TZ


def t(yil, ay, gun, saat=0, dakika=0):
    return IST.localize(datetime(yil, ay, gun, saat, dakika))


def _seri(baslangic: datetime, kapanislar, bar_dk=60):
    idx = pd.DatetimeIndex([baslangic + timedelta(minutes=bar_dk * i)
                            for i in range(len(kapanislar))])
    return pd.DataFrame({
        "open": kapanislar,
        "high": [c * 1.002 for c in kapanislar],
        "low": [c * 0.998 for c in kapanislar],
        "close": kapanislar,
        "volume": [1000] * len(kapanislar),
    }, index=idx)


# --- iki kırılımı aynı (stock,tf) serisinde bar-indeksi ile ayıran seri ------
# A: 5. barda giriş 100 -> ileri barlar 104'e çıkar  -> HEDEF
# B: 20. barda giriş 100 -> ileri barlar 97'ye düşer  -> STOP
def _iki_kirilim_serisi():
    basla = t(2026, 10, 1, 10, 30)
    kapanislar = (
        [100.0] * 6                                    # 0..5 (A giriş barı = 5)
        + [100.5, 101.0, 101.5, 102.0, 102.5, 103.0,   # 6..11
           103.5, 104.0, 104.0, 104.0]                 # 12..15
        + [100.0] * 4                                  # 16..19
        + [100.0]                                      # 20 (B giriş barı)
        + [99.5, 99.0, 98.5, 98.0, 97.5, 97.0,         # 21..26
           97.0, 97.0, 97.0, 97.0]                     # 27..30
    )
    return _seri(basla, kapanislar), basla


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """Karne ve history AYNI dizine yazsın (bağlantı ikisini de okur)."""
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config_mod, "DATA_DIR", str(tmp_path))
    return tmp_path


def _history_kaydi_ekle(stock, tf, stable_id, durum=fh.DURUM_ACIK,
                        bar_time="2026-10-01 10:30:00+03:00", bar_index=5):
    defter = fh.yukle(stock, tf)
    defter["kayitlar"][stable_id] = {
        "stable_id": stable_id, "durum": durum,
        "ilk_gorulme": "2026-10-01T10:30:00",
        "dogum": {"bar_time": bar_time, "bar_index": bar_index,
                  "alanlar": {"family": "Flama", "classic_dir": 1,
                              "pattern_type": "Boğa Flaması"}},
        "olaylar": [], "snapshotlar": [],
    }
    fh.kaydet(defter)
    return defter


def _saglayici(df):
    return lambda stock, tf: df


# =====================================================================
# 1) stable_id -> outcome doğru bağlanıyor
# =====================================================================

def test_stable_id_outcome_dogru_baglaniyor(ortam):
    stock, tf, sid = "THYAO", "1h", "sid-1"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    assert defter.kirilim_kaydet(
        stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1, 100.0, 2.0, 80.0,
        bar, stable_id=sid) is True

    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)

    ozet = ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df))
    assert ozet is not None, "Bağlantı kurulamadı"
    assert ozet["durum"] == K.DURUM_HEDEF

    # History kaydına yazıldı mı?
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF
    assert rec["sonuc"]["outcome"]["durum"] == K.DURUM_HEDEF

    # Okuma fonksiyonu birleşik görünümü veriyor mu?
    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum["stable_id"] == sid
    assert gorunum["history"] is not None
    assert len(gorunum["karne"]["kirilim"]) == 1
    assert gorunum["outcome"]["durum"] == K.DURUM_HEDEF


def test_tam_zincir_formation_kirilim_outcome(ortam):
    """stable_id -> formation kaydı -> kirilim kaydı -> outcome zinciri."""
    stock, tf, sid = "ASELS", "4h", "zincir-1"
    defter = KarneDefteri()
    bar = t(2026, 10, 2, 13, 30)
    defter.formasyon_kaydet(stock, tf, "Simetrik Üçgen", "SIKISMA_GUCLENIYOR",
                            84.0, bar, stable_id=sid)
    defter.kirilim_kaydet(stock, tf, "Simetrik Üçgen", "KIRILIM_TEYITLI", 1,
                          292.25, 3.4, 84.0, bar, stable_id=sid)
    defter.olay_kaydet(stock, tf, "FORMASYON_TAMAMLANDI", bar, stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    df = _seri(bar, [292.25, 293, 294, 296, 297, 298, 297, 296, 295, 294, 293])
    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    # Üç kayıt türü de aynı stable_id'ye bağlı
    assert len(gorunum["karne"]["formasyon"]) == 1
    assert len(gorunum["karne"]["kirilim"]) == 1
    assert len(gorunum["karne"]["olay"]) == 1
    assert gorunum["durum"] == K.DURUM_HEDEF
    # History kaydına bağlandı mı? (bagla yazma tarafı)
    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is not None
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF
    assert rec["sonuc"]["outcome"]["durum"] == K.DURUM_HEDEF


# =====================================================================
# 2) Multi-formation izolasyonu
# =====================================================================

def test_iki_formation_iki_ayri_outcome(ortam):
    """Aynı (stock,tf) içinde iki formation -> iki AYRI outcome."""
    stock, tf = "ASELS", "1h"
    sid_a, sid_b = "sid-A", "sid-B"
    df, basla = _iki_kirilim_serisi()
    bar_a = df.index[5]
    bar_b = df.index[20]

    defter = KarneDefteri()
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar_a, stable_id=sid_a)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 75.0, bar_b, stable_id=sid_b)
    _history_kaydi_ekle(stock, tf, sid_a, bar_index=5)
    _history_kaydi_ekle(stock, tf, sid_b, bar_index=20)

    oz_a = ol.bagla(defter, stock, tf, sid_a, saglayici=_saglayici(df))
    oz_b = ol.bagla(defter, stock, tf, sid_b, saglayici=_saglayici(df))

    assert oz_a["durum"] == K.DURUM_HEDEF, "A'nın outcome'ı yanlış"
    assert oz_b["durum"] == K.DURUM_STOP, "B'nin outcome'ı yanlış"

    rec_a = fh.kayit_getir(fh.yukle(stock, tf), sid_a)
    rec_b = fh.kayit_getir(fh.yukle(stock, tf), sid_b)
    assert rec_a["sonuc"]["durum"] == K.DURUM_HEDEF
    assert rec_b["sonuc"]["durum"] == K.DURUM_STOP
    # A'nın outcome'u B'ye (ve tersi) SIZMADI
    assert rec_a["sonuc"]["durum"] != rec_b["sonuc"]["durum"]
    assert rec_a["sonuc"]["kaynak"] == bar_a.isoformat()
    assert rec_b["sonuc"]["kaynak"] == bar_b.isoformat()


def test_a_outcome_b_ye_baglanmaz(ortam):
    """Sadece A için bağlantı kurulunca B'ye hiçbir şey yazılmaz."""
    stock, tf = "GARAN", "1h"
    sid_a, sid_b = "A", "B"
    df, _ = _iki_kirilim_serisi()
    defter = KarneDefteri()
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, df.index[5], stable_id=sid_a)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, df.index[20], stable_id=sid_b)
    _history_kaydi_ekle(stock, tf, sid_a, bar_index=5)
    _history_kaydi_ekle(stock, tf, sid_b, bar_index=20)

    ol.bagla(defter, stock, tf, sid_a, saglayici=_saglayici(df))

    rec_b = fh.kayit_getir(fh.yukle(stock, tf), sid_b)
    assert "sonuc" not in rec_b, "B'nin kaydına sızıntı oldu"


# =====================================================================
# 3) Outcome'ı olmayan formation
# =====================================================================

def test_outcome_olmayan_formation_yanlis_sonuc_uretmez(ortam):
    """Kırılım olmayan formation: outcome None, durum KIRILIM_YOK."""
    stock, tf, sid = "PETKM", "1h", "kirilimsiz"
    defter = KarneDefteri()
    defter.formasyon_kaydet(stock, tf, "Simetrik Üçgen", "SIKISMA_GUCLENIYOR",
                            70.0, t(2026, 10, 1, 10, 30), stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf)
    assert gorunum is not None
    assert gorunum["outcome"] is None
    assert gorunum["durum"] == ol.DURUM_KIRILIM_YOK
    # Karne'nin `bekliyor` semantiği KULLANILMAMIŞ olmalı (ikisi farklı şey)
    assert gorunum["durum"] != K.DURUM_BEKLIYOR
    # History'ye yanlış sonuç yazılmamalı
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert "sonuc" not in rec


def test_bekliyor_semantigi_korunuyor(ortam):
    """Kırılım var ama ufuk dolmadı -> Karne'nin KENDİ `bekliyor` durumu."""
    stock, tf, sid = "EREGL", "1h", "bekleyen"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    # İleri bar YOK -> sinyal_sonucu bekliyor döner
    df = _seri(bar, [100.0])
    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum["durum"] == K.DURUM_BEKLIYOR
    assert gorunum["outcome"]["durum"] == K.DURUM_BEKLIYOR


def test_bekliyor_cozumlenmise_gecer(ortam):
    """Ufuk dolduğunda bekliyor -> çözümlenmiş geçişi bağlantıya yansır."""
    stock, tf, sid = "EREGL", "1h", "gecis"
    bar = t(2026, 10, 1, 10, 30)
    defter = KarneDefteri()
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    kisitli = _seri(bar, [100.0])                       # ufuk yok
    ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(kisitli))
    assert fh.kayit_getir(fh.yukle(stock, tf), sid)["sonuc"]["durum"] == K.DURUM_BEKLIYOR

    tam = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(tam))
    assert fh.kayit_getir(fh.yukle(stock, tf), sid)["sonuc"]["durum"] == K.DURUM_HEDEF


# =====================================================================
# 4) Terminal formation
# =====================================================================

def test_terminal_formation_sonucu_sonradan_okunabilir(ortam):
    """Terminal işaretlenen kaydın sonucu diskten okunabilir."""
    stock, tf, sid = "SISE", "1h", "terminal-1"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)

    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is not None
    # Terminal işaretle
    defter_h = fh.yukle(stock, tf)
    assert fh.terminal_ekle(defter_h, sid, "FORMASYON_TAMAMLANDI") is True
    fh.kaydet(defter_h)

    # Sonradan oku (yeni defter nesnesi + yeni Karne defteri)
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert rec["durum"] == fh.DURUM_TERMINAL
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF
    gorunum = ol.formasyon_sonucu(sid, defter=KarneDefteri(), stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum["durum"] == K.DURUM_HEDEF
    assert gorunum["history"]["durum"] == fh.DURUM_TERMINAL
    # Seri saglanmasa bile bagli sonuc gecmisten okunur
    serisiz = ol.formasyon_sonucu(sid, defter=KarneDefteri(), stock=stock, tf=tf)
    assert serisiz["durum"] == K.DURUM_HEDEF
    assert serisiz["outcome"] == rec["sonuc"]["outcome"]


# =====================================================================
# 5) Restart
# =====================================================================

def test_restart_sonrasi_linkage_kurunuyor(ortam):
    """Process restart'i taklit: yeni Karne defteri + history diskten okunur."""
    stock, tf, sid = "KCHOL", "1h", "restart-1"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)
    ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df))

    # --- restart ---
    defter2 = KarneDefteri()          # diskten yeniden okur
    gorunum = ol.formasyon_sonucu(sid, defter=defter2, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum is not None
    assert gorunum["durum"] == K.DURUM_HEDEF
    assert gorunum["stable_id"] == sid
    assert gorunum["history"]["sonuc"]["durum"] == K.DURUM_HEDEF


# =====================================================================
# 6) Eski (stable_id'siz) kayıtlar
# =====================================================================

def test_eski_kayitlar_bozulmuyor(ortam):
    """stable_id'siz Karne kayıtları mevcut davranışlarıyla çalışmaya devam eder."""
    stock, tf = "TUPRS", "1h"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    # stable_id verilmeden kayıt (eski format)
    assert defter.formasyon_kaydet(stock, tf, "Simetrik Üçgen",
                                   "SIKISMA_GUCLENIYOR", 80.0, bar) is True
    assert defter.kirilim_kaydet(stock, tf, "Simetrik Üçgen", "KIRILIM_TEYITLI",
                                 1, 100.0, 2.0, 80.0, bar) is True
    assert defter.olay_kaydet(stock, tf, "FORMASYON_TAMAMLANDI", bar) is True

    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    saglayici = _saglayici(df)

    # Linkage stable_id'siz kayıtları GÖRMEZDEN gelir
    assert ol.formasyon_sonucu(None, defter=defter, stock=stock, tf=tf,
                               saglayici=saglayici) is None
    assert ol.stable_id_ozetleri(defter=defter, saglayici=saglayici) == {}

    # karne_hesapla sonuçları DEĞİŞMEMELİ (mevcut davranış)
    metrik = K.karne_hesapla(defter.kayitlar(), saglayici)
    assert metrik["kirilim_toplam"] == 1
    assert metrik["formasyon_toplam"] == 1


def test_bagla_stable_id_yoksa_hicbir_sey_yapmaz(ortam):
    stock, tf = "TUPRS", "1h"
    defter = KarneDefteri()
    assert ol.bagla(defter, stock, tf, None, saglayici=_saglayici(None)) is None
    assert ol.bagla(defter, stock, tf, "", saglayici=_saglayici(None)) is None
    # Hiç dosya oluşmamalı
    assert fh.yukle(stock, tf)["kayitlar"] == {}


# =====================================================================
# 7) sinyal_sonucu sonuçları değişmiyor
# =====================================================================

def test_sinyal_sonucu_sonuclari_degismiyor(ortam):
    """`outcome_hesapla` birebir `sinyal_sonucu` çağrısıdır — matematik aynı."""
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    kayit = {"tip": "kirilim", "stock": "X", "tf": "1h", "dir": 1, "entry": 100.0,
             "atr": 2.0, "quality": 80.0, "bar_time": bar.isoformat(),
             "kayit_zaman": bar.isoformat(), "stable_id": "s"}
    dogrudan = K.sinyal_sonucu(kayit, df)
    sarmalanmis = ol.outcome_hesapla(kayit, _saglayici(df))
    assert dogrudan == sarmalanmis, "Sarmalayıcı outcome'ı değiştirdi"

    # Seri sağlayıcı None ise ikisi de None döner (ölçülemedi semantiği)
    assert K.sinyal_sonucu(kayit, None) is None
    assert ol.outcome_hesapla(kayit, None) is None
    assert ol.outcome_hesapla(kayit, _saglayici(None)) is None


def test_kirilim_olmayan_kayit_outcome_hesaplanamaz():
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102])
    formasyon = {"tip": "formasyon", "stock": "X", "tf": "1h",
                 "bar_time": bar.isoformat()}
    assert ol.outcome_hesapla(formasyon, _saglayici(df)) is None
    # birincil_outcome: kırılım listesi boş -> KIRILIM_YOK
    assert ol.birincil_outcome([], _saglayici(df))["durum"] == ol.DURUM_KIRILIM_YOK


# =====================================================================
# EK: birçok kırılım denemesi / idempotan yazma / eski history biçimi
# =====================================================================

def test_coklu_kirilim_denemesi_birincil_secimi(ortam):
    """Aynı formation iki kırılım denemesi: EN YENİ çözümlenmiş outcome birincil."""
    stock, tf, sid = "BIMAS", "1h", "coklu-denet"
    df, _ = _iki_kirilim_serisi()
    defter = KarneDefteri()
    # İlk deneme (eski bar): HEDEF olur
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, df.index[5], stable_id=sid)
    # İkinci deneme (yeni bar): STOP olur
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, df.index[20], stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum["deneme"] == 2, "İki deneme sayılmalı"
    # En yeni (bar 20) STOP -> birincil STOP
    assert gorunum["durum"] == K.DURUM_STOP
    assert gorunum["kaynak"] == df.index[20].isoformat()
    # İki deneme de ayrıca görünür (hiçbir şey gizlenmiyor)
    assert len(gorunum["karne"]["kirilim"]) == 2


def test_bagla_degisiklik_yoksa_yazmaz(ortam):
    """Aynı outcome tekrar bağlanınca gereksiz disk yazımı olmaz."""
    stock, tf, sid = "ARCLK", "1h", "idempotan"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)

    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is not None
    dosya = fh.yol(stock, tf)
    ilk_zaman = dosya and __import__("os").path.getmtime(dosya)
    # İkinci çağrı: sonuç aynı -> None (yazma yok)
    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is None
    assert __import__("os").path.getmtime(dosya) == ilk_zaman, "Gereksiz yazma yapıldı"


def test_history_kaydi_yoksa_baglantı_kayit_uydurmaz(ortam):
    """Karne'de kayıt var ama history'de yok -> yanlış birleşme riskine düşülmez."""
    stock, tf, sid = "FROTO", "1h", "history-yok"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])

    # History'de kayıt YOK
    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is None
    assert fh.yukle(stock, tf)["kayitlar"] == {}, "Uydurma kayıt oluşturuldu"
    # Okuma tarafı yine çalışır (history None)
    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum["history"] is None
    assert gorunum["durum"] == K.DURUM_HEDEF


def test_eski_faz1_history_bicimi_crash_etmez(ortam):
    """Faz 1 anchor biçimindeki (düz alanlar) history kaydı bağlantıyı kırmaz."""
    stock, tf, sid = "TTKOM", "1h", "eski-bicim"
    defter = KarneDefteri()
    bar = t(2026, 10, 1, 10, 30)
    defter.kirilim_kaydet(stock, tf, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])

    defter_h = fh.bos_defter(stock, tf)
    defter_h["kayitlar"][sid] = {           # `dogum` yok: Faz 1 düz biçimi
        "stable_id": sid, "durum": fh.DURUM_ACIK,
        "family": "Flama", "classic_dir": 1,
    }
    fh.kaydet(defter_h)

    gorunum = ol.formasyon_sonucu(sid, defter=defter, stock=stock, tf=tf,
                                  saglayici=_saglayici(df))
    assert gorunum is not None
    assert gorunum["durum"] == K.DURUM_HEDEF
    assert ol.bagla(defter, stock, tf, sid, saglayici=_saglayici(df)) is not None


# =====================================================================
# main.py entegrasyonu (tarama yazim noktasi)
# =====================================================================

def _main_ortam(monkeypatch, tmp_path):
    """main modulunu gercek DATA_DIR ile yukler (karne + history ayni dizin)."""
    import main as M
    monkeypatch.setattr(K, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(M, "_karne_defteri", None)
    return M


def test_tarama_yazim_noktasi_outcome_baglaniyor(monkeypatch, tmp_path):
    """`_karne_olay_kaydet` hem karne kaydini duser hem outcome'i baglar."""
    M = _main_ortam(monkeypatch, tmp_path)
    stock, tf, sid = "THYAO", "1h", "main-1"
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)

    M._karne_olay_kaydet(stock, tf, "KIRILIM_TEYITLI", "Boğa Flaması", 85.0,
                         bar, kirilim=True, dir=1, entry=100.0, df_tf=df,
                         stable_id=sid)

    defter = M._karne_al()
    assert len(ol.kirilim_kayitlari(defter, sid)) == 1, "Karne kaydi dusmedi"
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF, "Outcome baglanmadi"


def test_tarama_yazim_noktasi_legacy_stable_id_yok(monkeypatch, tmp_path):
    """stable_id yoksa: karne kaydi duser, outcome baglanmaz, hata olmaz."""
    M = _main_ortam(monkeypatch, tmp_path)
    stock, tf = "TUPRS", "1h"
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])

    M._karne_olay_kaydet(stock, tf, "KIRILIM_TEYITLI", "Boğa Flaması", 85.0,
                         bar, kirilim=True, dir=1, entry=100.0, df_tf=df)

    defter = M._karne_al()
    assert len(defter.kayitlar()) == 1
    assert fh.yukle(stock, tf)["kayitlar"] == {}, "stable_id'suz kayda outcome yazildi"


def test_tarama_yazim_noktasi_olay_outcome_baglar(monkeypatch, tmp_path):
    """Kirilim disindaki anlamli state'lerde de linkage calisir."""
    M = _main_ortam(monkeypatch, tmp_path)
    stock, tf, sid = "SASA", "1h", "main-olay"
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    # Once kirilim kaydi
    M._karne_olay_kaydet(stock, tf, "KIRILIM_TEYITLI", "Boğa Flaması", 85.0,
                         bar, kirilim=True, dir=1, entry=100.0, df_tf=df,
                         stable_id=sid)
    _history_kaydi_ekle(stock, tf, sid)

    # Sonra terminal olay: linkage tekrar hesaplar ve yazar
    M._karne_olay_kaydet(stock, tf, "FORMASYON_TAMAMLANDI", "Boğa Flaması", 85.0,
                         df.index[-1], df_tf=df, stable_id=sid)

    defter = M._karne_al()
    assert len(ol.olay_kayitlari(defter, sid)) == 1
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    assert rec["sonuc"]["durum"] == K.DURUM_HEDEF


def test_outcome_linkage_hatasi_taramayi_durdurmaz(monkeypatch, tmp_path):
    """Linkage patlarsa tarama akisi devam eder (karne kaydi duser)."""
    M = _main_ortam(monkeypatch, tmp_path)
    stock, tf, sid = "KCHOL", "1h", "main-hata"
    bar = t(2026, 10, 1, 10, 30)
    df = _seri(bar, [100, 101, 102, 104, 103, 103, 103, 103, 103, 103, 103])
    _history_kaydi_ekle(stock, tf, sid)

    def patla(*a, **k):
        raise RuntimeError("baglanti kirildi")

    monkeypatch.setattr(ol, "bagla", patla)
    # Hicbir sey firlatmamali
    M._karne_olay_kaydet(stock, tf, "KIRILIM_TEYITLI", "Boğa Flaması", 85.0,
                         bar, kirilim=True, dir=1, entry=100.0, df_tf=df,
                         stable_id=sid)

    defter = M._karne_al()
    assert len(ol.kirilim_kayitlari(defter, sid)) == 1, "Karne kaydi kayboldu"
    # Hata yutuldugu icin history'ye sonuc yazilmadi
    assert "sonuc" not in fh.kayit_getir(fh.yukle(stock, tf), sid)


def test_outcome_linkage_seri_yoksa_calisma_devam(monkeypatch, tmp_path):
    """df_tf verilmediginde de linkage cozumlenir ve tarama devam eder."""
    M = _main_ortam(monkeypatch, tmp_path)
    stock, tf, sid = "TTKOM", "1h", "main-seriyok"
    bar = t(2026, 10, 1, 10, 30)
    _history_kaydi_ekle(stock, tf, sid)

    M._karne_olay_kaydet(stock, tf, "KIRILIM_TEYITLI", "Boğa Flaması", 85.0,
                         bar, kirilim=True, dir=1, entry=100.0, stable_id=sid)

    defter = M._karne_al()
    assert len(ol.kirilim_kayitlari(defter, sid)) == 1
    rec = fh.kayit_getir(fh.yukle(stock, tf), sid)
    # Seri olmadan olculemez; Karne'nin KENDI olculemedi durumu korunur
    assert rec["sonuc"]["durum"] == K.DURUM_OLCULEMEDI
    assert rec["sonuc"]["outcome"] == {"durum": K.DURUM_OLCULEMEDI}
    # Olculemedi: Karne'nin kendi semantigi (hedef/stop/nötür/ölanmedî degil)
    assert rec["sonuc"]["durum"] not in (K.DURUM_HEDEF, K.DURUM_STOP, K.DURUM_NOTR)
