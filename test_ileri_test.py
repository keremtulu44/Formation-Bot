# -*- coding: utf-8 -*-
"""İleri test kaydı sözleşmesi.

SALT HESAP + geçici dosya: ağ yok, canlı veri yok. `gece()` fonksiyonuna veri
kaynağı enjekte edilir, yani testte hiçbir sembol indirilmez.

Korunan sözleşme:
  * yalnız gönderilen uyarı kaydedilir; zorunlu alan yoksa kayıt yok
  * aynı olay iki kez yazılmaz (anahtar bazlı)
  * sonuç 24 bar sonra; pencere dolmadıysa sonuç YOK (uydurulmaz)
  * ölçü yön lehine yüzde; en iyi/en kötü yalnız teşhis
  * karar kuralı önceden yazılı; grup başına 100 gözlem altında hüküm yok
  * defter I/O hatası çağıranı düşürmez
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

import ileri_test as it


def _veri(**ek):
    temel = {
        "stock_name": "THYAO", "timeframe": "1h", "pattern_name": "Yükselen Kama",
        "state": "KIRILIM_TEYITLI", "break_dir": 1, "break_price": 100.0,
        "critical_price_level": 100.0, "mtf_uyum": 4, "mtf_destek": True,
        "bant_mesafe_atr": 0.2,
        "bar_kapanis": "2026-10-20T17:00:00+03:00",
    }
    temel.update(ek)
    return temel


def _df(baslangic: str = "2026-10-20T18:00:00+03:00", adet: int = 30,
        yuksek: float = 102.0, dusuk: float = 98.0, kapanis=None) -> pd.DataFrame:
    bas = pd.Timestamp(baslangic)
    if bas.tzinfo is None:
        bas = bas.tz_localize("Europe/Istanbul")
    idx = pd.date_range(bas, periods=adet, freq="h")
    kapanis = kapanis if kapanis is not None else [101.0] * adet
    return pd.DataFrame({"open": kapanis, "high": [yuksek] * adet,
                         "low": [dusuk] * adet, "close": kapanis}, index=idx)


@pytest.fixture(autouse=True)
def _temiz():
    it.sifirla()
    yield
    it.sifirla()


# --- bayrak -----------------------------------------------------------------

def test_bayrak_tek_iddia():
    assert it.bayrak(_veri()) is True
    # üçgende üst TF uyumu ölçümde etkisiz → bayrak değil
    assert it.bayrak(_veri(pattern_name="Simetrik Üçgen")) is False
    # kama ama üst TF yön uyumu yok
    assert it.bayrak(_veri(mtf_uyum=0)) is False
    assert it.bayrak(_veri(mtf_uyum=None)) is False


# --- kayıt ------------------------------------------------------------------

def test_kayit_zorunlu_alanlar():
    kayit = it.kayit_olustur(_veri())
    assert kayit is not None
    assert kayit["anahtar"] == "THYAO|1h|2026-10-20T17:00:00+03:00"
    assert kayit["giris"] == 100.0 and kayit["yon"] == 1
    assert kayit["bayrak"] is True and kayit["sonuc"] is None
    # puan yalnız log: kayıtta var, kartta yok
    assert isinstance(kayit["puan"], int)

    # bar zamanı yoksa kayıt YOK (24 barlık pencere yanlış başlamasın)
    assert it.kayit_olustur(_veri(bar_kapanis="", bar_time="", timestamp="")) is None
    assert it.kayit_olustur(_veri(break_dir=0)) is None
    assert it.kayit_olustur(_veri(break_price=None, critical_price_level=None)) is None
    assert it.kayit_olustur(_veri(stock_name="")) is None


def test_ayni_olay_iki_kez_yazilmaz(tmp_path):
    assert it.kaydet(_veri(), data_dir=str(tmp_path)) is True
    assert it.kaydet(_veri(), data_dir=str(tmp_path)) is False
    defter = it.defter_yukle(data_dir=str(tmp_path))
    assert len(defter["kayitlar"]) == 1


# --- sonuç ------------------------------------------------------------------

def test_sonuc_yon_lehine_yuzde():
    kayit = it.kayit_olustur(_veri())
    sonuc = it.sonuc_hesapla(kayit, _df(kapanis=[101.0] * 30))
    assert sonuc is not None
    assert sonuc["yuzde"] == pytest.approx(1.0)
    assert sonuc["devam"] is True
    assert sonuc["en_iyi"] == pytest.approx(2.0)   # 102'ye kadar lehte
    assert sonuc["en_kotu"] == pytest.approx(2.0)  # 98'e kadar aleyhte
    assert sonuc["bar"] == it.BAR_SAYISI

    # aşağı yönlü kırılımda işaret döner
    asagi = it.kayit_olustur(_veri(break_dir=-1))
    sonuc2 = it.sonuc_hesapla(asagi, _df(kapanis=[99.0] * 30))
    assert sonuc2["yuzde"] == pytest.approx(1.0)
    assert sonuc2["devam"] is True


def test_sonuc_pencere_dolmadan_uretilmez():
    kayit = it.kayit_olustur(_veri())
    # 24 bardan az → sonuç yok (uydurma yok)
    assert it.sonuc_hesapla(kayit, _df(adet=it.BAR_SAYISI - 1)) is None
    assert it.sonuc_hesapla(kayit, None) is None
    assert it.sonuc_hesapla(kayit, pd.DataFrame()) is None


def test_olgunluk_bar_sayisina_gore():
    simdi = datetime.fromisoformat("2026-10-22T00:00:00+03:00")
    eski = it.kayit_olustur(_veri(bar_kapanis="2026-10-20T17:00:00+03:00"))
    yeni = it.kayit_olustur(_veri(bar_kapanis="2026-10-21T20:00:00+03:00"))
    assert it.olgun_mu(eski, simdi=simdi) is True     # 31 saat ≥ 24 bar
    assert it.olgun_mu(yeni, simdi=simdi) is False    # 4 saat < 24 bar
    # günlükte 24 bar = 24 gün
    gunluk = it.kayit_olustur(_veri(timeframe="1d", bar_kapanis="2026-10-01T18:00:00+03:00"))
    assert it.olgun_mu(gunluk, simdi=simdi) is False


# --- defter -----------------------------------------------------------------

def test_defter_birlestirme_dolu_sonucu_korur():
    a = {"anahtar": "X|1h|b", "sonuc": {"yuzde": 2.0}}
    b = {"anahtar": "X|1h|b", "sonuc": None, "durum": "yeni"}
    birlesik = it._birlestir([a], [b])
    assert len(birlesik) == 1
    assert birlesik[0]["sonuc"] == {"yuzde": 2.0}
    assert birlesik[0]["durum"] == "yeni"


def test_defter_dosyaya_yazilir_ve_okunur(tmp_path):
    defter = {"kayitlar": [{"anahtar": "X|1h|b", "sonuc": None}], "son_gece": ""}
    assert it.defter_kaydet(defter, data_dir=str(tmp_path)) is True
    okunan = it.defter_yukle(data_dir=str(tmp_path))
    assert okunan["kayitlar"][0]["anahtar"] == "X|1h|b"
    # bozuk dosya botu düşürmez
    (tmp_path / it.DOSYA).write_text("{bozuk", encoding="utf-8")
    assert it.defter_yukle(data_dir=str(tmp_path))["kayitlar"] == []


def test_defter_tavani_asilmaz(monkeypatch):
    monkeypatch.setattr(it, "AZAMI_KAYIT", 3)
    kayitlar = [{"anahtar": f"k{i}", "sonuc": {"yuzde": 1.0},
                 "olusturma": f"2026-10-{i+1:02d}"} for i in range(5)]
    kalan = it._kirp(kayitlar)
    assert len(kalan) == 3
    # en eski SONUÇLU kayıtlar düşer
    assert [k["anahtar"] for k in kalan] == ["k2", "k3", "k4"]


# --- gece işi ---------------------------------------------------------------

def test_gece_sonuclari_hesaplar_ve_mesaj_atmaz(tmp_path):
    simdi = datetime.fromisoformat("2026-10-22T00:00:00+03:00")
    it.kaydet(_veri(), data_dir=str(tmp_path))
    it.kaydet(_veri(stock_name="ASELS", bar_kapanis="2026-10-21T23:00:00+03:00"),
              data_dir=str(tmp_path))

    cagrilar = []
    def fake_getir(sembol, tf):
        cagrilar.append((sembol, tf))
        return _df(kapanis=[101.0] * 30)

    rapor = tmp_path / "rapor.md"
    sonuc = it.gece(data_dir=str(tmp_path), simdi=simdi, getir=fake_getir,
                    rapor_yolu=str(rapor))
    assert sonuc["istatistik"]["hesaplanan"] == 1      # yalnız olgun kayıt
    assert sonuc["istatistik"]["veri_yok"] == 0
    # aynı sembol+tf için tek çağrı (önbellek)
    assert cagrilar == [("THYAO", "1h")]
    assert rapor.exists() and "İleri test" in rapor.read_text(encoding="utf-8")

    defter = it.defter_yukle(data_dir=str(tmp_path))
    olgun = [k for k in defter["kayitlar"] if k["sembol"] == "THYAO"][0]
    assert olgun["sonuc"]["yuzde"] == pytest.approx(1.0)
    assert defter["son_gece"] == "2026-10-22"

    # ikinci koşu aynı kaydı yeniden hesaplamaz
    sonuc2 = it.gece(data_dir=str(tmp_path), simdi=simdi, getir=fake_getir)
    assert sonuc2["istatistik"]["hesaplanan"] == 0


def test_gece_veri_yoksa_kaydi_bekletir(tmp_path):
    simdi = datetime.fromisoformat("2026-10-22T00:00:00+03:00")
    it.kaydet(_veri(), data_dir=str(tmp_path))
    sonuc = it.gece(data_dir=str(tmp_path), simdi=simdi, getir=lambda s, t: None)
    assert sonuc["istatistik"]["veri_yok"] == 1
    defter = it.defter_yukle(data_dir=str(tmp_path))
    assert defter["kayitlar"][0]["sonuc"] is None       # sonuç uydurulmadı


# --- özet / öneri -----------------------------------------------------------

def _sonuclu(n: int, yuzde: float, bayrak: bool):
    return [{"anahtar": f"{i}", "bayrak": bayrak, "sonuc": {"yuzde": yuzde}}
            for i in range(n)]


def test_ozet_az_gozlemde_hukum_yok():
    metin = it.ozet(_sonuclu(5, 5.0, True) + _sonuclu(5, 0.0, False))
    assert "Hüküm yok" in metin
    assert "Öneri" not in metin


def test_ozet_kural_esikte_karar_verir():
    # +5 puan fazla → kalsın
    metin = it.ozet(_sonuclu(it.MIN_GOZLEM, 5.0, True)
                    + _sonuclu(it.MIN_GOZLEM, 0.0, False))
    assert "kalsın" in metin and "+5.00" in metin
    # +1 puan fazla → kaldırılsın
    metin2 = it.ozet(_sonuclu(it.MIN_GOZLEM, 1.0, True)
                     + _sonuclu(it.MIN_GOZLEM, 0.0, False))
    assert "kaldırılsın" in metin2
    # tam eşik (3.0) → kalsın (>= kuralı)
    metin3 = it.ozet(_sonuclu(it.MIN_GOZLEM, 3.0, True)
                     + _sonuclu(it.MIN_GOZLEM, 0.0, False))
    assert "kalsın" in metin3


def test_ozet_karar_uygulanmaz():
    """Modül hiçbir eşiği/kartı değiştirmez; yalnız metin/öneri üretir."""
    metin = it.ozet(_sonuclu(it.MIN_GOZLEM, 1.0, True)
                    + _sonuclu(it.MIN_GOZLEM, 0.0, False))
    assert "kaldırılsın" in metin
    assert "kullanıcı onayıyla" in metin


# --- main.py bağlantısı ------------------------------------------------------

def test_main_kaydet_hatayi_yutar(monkeypatch):
    """Ölçüm kaydı botu düşürmez: bozuk veri sessizce atlanır."""
    import main

    main._ileri_test_kaydet({"stock_name": None, "timeframe": None})
    main._ileri_test_kaydet(object())          # hiç dict olmayan girdi


def test_main_gece_gunde_bir_kez_ve_saatten_sonra(monkeypatch, tmp_path):
    import main

    cagri = []

    def fake_gece(**kw):
        cagri.append(kw)
        return {"istatistik": {}, "ozet": "ok"}

    monkeypatch.setattr(it, "gece", fake_gece)
    monkeypatch.setattr(main, "_ileri_test_son_gece", "")
    monkeypatch.setattr(main.config, "DATA_DIR", str(tmp_path))

    # saatten önce: hiç koşmaz
    main._ileri_test_gece(datetime(2026, 10, 21, 12, 0))
    assert cagri == []
    # saatten sonra: bir kez
    main._ileri_test_gece(datetime(2026, 10, 21, 19, 30))
    assert len(cagri) == 1
    # aynı gün ikinci kez: koşmaz (maliyet)
    main._ileri_test_gece(datetime(2026, 10, 21, 22, 0))
    assert len(cagri) == 1
    # ertesi gün: yeniden
    main._ileri_test_gece(datetime(2026, 10, 22, 19, 5))
    assert len(cagri) == 2
