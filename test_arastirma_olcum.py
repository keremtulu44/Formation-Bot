"""Araştırma ölçüm hattının testleri (Faz 6).

Odak üç risktir:

1. **Lookahead.** Ölçüm çapadan sonraki barları kullanmak zorundadır; ufuk
   dışındaki bir barın değeri ölçümü değiştirmemelidir. Bu, backtest'in
   geçerliliğini belirleyen tek şeydir ve sentetik veriyle kesin olarak
   test edilir.
2. **Determinizm ve idempotens.** Aynı girdi aynı satırları üretmeli ve koşu
   yarıda kesilip yeniden çalıştırıldığında işler çift sayılmamalıdır.
3. **Survivorship.** Hem OB zone'ları hem MS rolleri zamanla silinen/mutate
   olan durumlardır. Final snapshot'a dayanan bir ölçüm sistematik olarak
   yanlı olur; testler geçmişin yeniden kurulduğunu doğrular.

Testler arşiv verisine bağımlı değildir (sentetik çerçeve kullanılır),
dolayısıyla ``backfill_data/`` olmadan da koşar.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_KOKU = Path(__file__).resolve().parent
if str(REPO_KOKU) not in sys.path:
    sys.path.insert(0, str(REPO_KOKU))

from research import olcum  # noqa: E402


def _sentetik_frame(fiyatlar: list[tuple[float, float, float, float]], hacim: float = 1000.0) -> pd.DataFrame:
    """(open, high, low, close) listesinden DatetimeIndex'li çerçeve üretir."""
    indeks = pd.date_range("2025-01-02 09:30", periods=len(fiyatlar), freq="1h", tz="Europe/Istanbul")
    return pd.DataFrame(
        {
            "open": [p[0] for p in fiyatlar],
            "high": [p[1] for p in fiyatlar],
            "low": [p[2] for p in fiyatlar],
            "close": [p[3] for p in fiyatlar],
            "volume": [hacim] * len(fiyatlar),
        },
        index=indeks,
    )


# ---------------------------------------------------------------------------
# Eşik etiketi: 2.0 -> "200" (0.20 gibi okunmamalı)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("esik", "beklenen"),
    [(0.15, "015"), (0.25, "025"), (0.5, "050"), (1.0, "100"), (1.5, "150"), (2.0, "200")],
)
def test_esik_etiketi_belirsiz_degil(esik: float, beklenen: str) -> None:
    assert olcum._esik_etiketi(esik) == beklenen


def test_esik_etiketleri_cakismaz() -> None:
    etiketler = [olcum._esik_etiketi(e) for e in olcum.ESIK_IZGARA]
    assert len(etiketler) == len(set(etiketler)), f"çakışan eşik etiketi: {etiketler}"
    assert olcum._esik_etiketi(2.0) != olcum._esik_etiketi(0.2)


# ---------------------------------------------------------------------------
# Kenar tespiti: direnç/destek mantığı
# ---------------------------------------------------------------------------
def test_ust_kenar_asagi_olculur() -> None:
    bar = {"high": 105.0, "low": 101.0}
    assert olcum.dokunulan_kenar(bar, 90.0, 100.0) == "UST_KENAR"
    assert olcum.kenar_yonu("UST_KENAR") == "DOWN"


def test_alt_kenar_yukari_olculur() -> None:
    bar = {"high": 99.0, "low": 89.0}
    assert olcum.dokunulan_kenar(bar, 90.0, 100.0) == "ALT_KENAR"
    assert olcum.kenar_yonu("ALT_KENAR") == "UP"


def test_tum_zone_yon_belirlenemez() -> None:
    """Bar zone'u baştan sona kat ediyorsa yön belirlenemez; tahmin edilmez."""
    bar = {"high": 105.0, "low": 85.0}
    assert olcum.dokunulan_kenar(bar, 90.0, 100.0) == "TUM_ZONE"
    assert olcum.kenar_yonu("TUM_ZONE") is None


def test_zone_ici_yon_belirlenemez() -> None:
    bar = {"high": 97.0, "low": 93.0}
    assert olcum.dokunulan_kenar(bar, 90.0, 100.0) == "ZONE_ICI"
    assert olcum.kenar_yonu("ZONE_ICI") is None


def test_gecersiz_zone_yuksekligi() -> None:
    """Sıfır/ters zone yüksekliği ölçülmemelidir (bölme patlamasın)."""
    assert olcum.dokunulan_kenar({"high": 105.0, "low": 95.0}, 100.0, 100.0) == "GECERSIZ"
    assert olcum.dokunulan_kenar({"high": 105.0, "low": 95.0}, 110.0, 100.0) == "GECERSIZ"


def test_belirsiz_kenar_olcum_yapmaz_ama_isaretler() -> None:
    """Yön belirlenemeyen temas ``olculmedi`` ile işaretlenir, sessizce 0 olmaz."""
    ozet = olcum.kenar_ancored_olcum("TUM_ZONE", 90.0, 100.0, [{"high": 120.0, "low": 80.0}], 1.0)
    assert ozet["olculmedi"] == "TUM_ZONE"
    assert ozet["tepe_atr"] is None


# ---------------------------------------------------------------------------
# Şekil metrikleri: anlık mı yavaş-kalıcı mı
# ---------------------------------------------------------------------------
def test_yol_ozeti_anlik_tepki() -> None:
    """İlk barda tepe yapıp sonra soluyan yol: pay_5 ~ 1, decay yüksek."""
    yol = [3.0, 2.0, 1.0, 0.5, 0.25, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ozet = olcum.yol_ozeti(yol)
    assert ozet["tepe_atr"] == pytest.approx(3.0)
    assert ozet["tepe_bar"] == 1
    assert ozet["pay_5"] == pytest.approx(1.0)
    assert ozet["h12"] == pytest.approx(3.0)
    assert ozet["h12_decay"] == pytest.approx(1.0)


def test_yol_ozeti_yavas_ve_kalici() -> None:
    """Geç tepe yapıp koruyan yol: pay_5 düşük, decay düşük."""
    yol = [0.1, 0.2, 0.3, 0.4, 0.5, 0.8, 1.2, 1.8, 2.5, 3.0, 3.0, 3.0]
    ozet = olcum.yol_ozeti(yol)
    assert ozet["tepe_bar"] == 10
    assert ozet["pay_5"] == pytest.approx(0.5 / 3.0)
    assert ozet["h12_decay"] == pytest.approx(0.0)


def test_tepe_metrikleri_sinirlidir() -> None:
    """Sınırsız gelecek tepeye sızmamalı: 12 bardan sonraki dev değer yok sayılır.

    Bu test gerçek bir hatayı kilitler. Önceki sürüm tüm gözlenen barlarda
    ``max`` alıyordu; 12 barda hiç tepki vermeyen bir zone 800 bar sonraki
    fiyat aralığı sayesinde dev tepe alıyor ve ``pay_5`` negatif çıkıyordu.
    """
    yol = [0.0] * 12 + [50.0] * 30
    ozet = olcum.yol_ozeti(yol)
    assert ozet["tepe_atr"] == pytest.approx(0.0), "ana tepe 12 barla sınırlı olmalı"
    assert ozet["tepe_bar"] == 1
    assert ozet["uzun_tepe_atr"] == pytest.approx(50.0), "uzun pencere 40 barı görür"
    assert ozet["pay_5"] is None or ozet["pay_5"] >= 0, "pay asla negatif olmamalı"


def test_asim_esik_izgarasi_ve_ilk_asim_bari() -> None:
    yol = [0.1, 0.3, 0.6, 1.2, 1.6] + [0.0] * 7
    ozet = olcum.yol_ozeti(yol)
    assert ozet["asim_025"] is True and ozet["asim_025_bar"] == 2
    assert ozet["asim_050"] is True and ozet["asim_050_bar"] == 3
    assert ozet["asim_100"] is True and ozet["asim_100_bar"] == 4
    assert ozet["asim_150"] is True and ozet["asim_150_bar"] == 5
    assert ozet["asim_200"] is False and ozet["asim_200_bar"] is None


def test_negatif_tepe_ters_tepki_sinifi_verir() -> None:
    """Fiyat ölçüm yönüne hiç gitmediyse bu 'tepki yok' değil 'TERS'tir."""
    yol = [-0.5, -1.0, -0.2] + [None] * 9
    ozet = olcum.yol_ozeti(yol)
    assert ozet["tepe_atr"] < 0
    assert olcum.tepki_sinifi(ozet["h12"]) == "TERS"


def test_bos_yol_olculemedi() -> None:
    ozet = olcum.yol_ozeti([])
    assert ozet["tepe_atr"] is None
    assert olcum.tepki_sinifi(ozet["h12"]) == "OLCULEMEDI"
    assert ozet["h12_sansur"] is True


def test_atr_gecersizse_yol_none_dolar() -> None:
    """ATR yoksa uzanım uydurulmaz; None kalır ve OLCULEMEDI sınıfına düşer."""
    yol = olcum.tek_yonlu_yol("UP", 100.0, [{"high": 110.0, "low": 105.0}], 0.0)
    assert yol == [None]
    assert olcum.tek_yonlu_yol("UP", 100.0, [{"high": 110.0, "low": 105.0}], None) == [None]


def test_tek_yonlu_yol_negatifi_korur() -> None:
    """Negatif uzanım kırpılmamalı: fiyatın ters tarafa geçtiği bilgisidir."""
    yol = olcum.tek_yonlu_yol("UP", 100.0, [{"high": 98.0, "low": 95.0}], 2.0)
    assert yol == [pytest.approx(-1.0)]


# ---------------------------------------------------------------------------
# Deneme / engelleme (PH/PL, WL/WH)
# ---------------------------------------------------------------------------
def test_deneme_engelledi_kirilim_yok() -> None:
    """Seviye hiç aşılmadı ve pencere tam -> engelledi True."""
    barlar = [{"high": 99.0, "low": 95.0, "close": 97.0}] * olcum.SWING_PENCERESI
    ozet = olcum.deneme_ozeti(100.0, "HIGH", barlar, 1.0)
    assert ozet["sansur"] is False
    assert ozet["kirilim_bar"] is None
    assert ozet["engelledi_025"] is True
    assert ozet["gecildi"] is False


def test_deneme_sansurlu_iken_karar_verilmez() -> None:
    """Pencere veri sonuna takıldıysa 'engelledi' True OLMAZ; None kalır.

    'Henüz kırılmadı' ile 'başarılı direnç' ayrımı budur.
    """
    barlar = [{"high": 99.0, "low": 95.0, "close": 97.0}] * 5
    ozet = olcum.deneme_ozeti(100.0, "HIGH", barlar, 1.0)
    assert ozet["sansur"] is True
    assert ozet["engelledi_025"] is None


def test_deneme_kirilim_varsa_engellemedi() -> None:
    barlar = [{"high": 99.0, "low": 95.0, "close": 97.0}] * 3 + [
        {"high": 105.0, "low": 100.0, "close": 104.0}
    ] + [{"high": 104.0, "low": 100.0, "close": 102.0}] * (olcum.SWING_PENCERESI - 4)
    ozet = olcum.deneme_ozeti(100.0, "HIGH", barlar, 1.0)
    assert ozet["kirilim_bar"] == 4
    assert ozet["engelledi_025"] is False
    assert ozet["gecildi"] is True
    assert ozet["red_magnitude_atr"] == pytest.approx(4.0)


def test_deneme_epizot_sayisi_ardisik_barlari_tek_sayar() -> None:
    """3 ardışık yaklaşma barı = 1 epizot, 3 deneme değil."""
    barlar = [{"high": 100.0, "low": 95.0, "close": 97.0}] * 3
    barlar += [{"high": 90.0, "low": 85.0, "close": 88.0}] * 5
    barlar += [{"high": 100.0, "low": 96.0, "close": 98.0}] * 2
    barlar += [{"high": 90.0, "low": 85.0, "close": 88.0}] * (olcum.SWING_PENCERESI - 10)
    ozet = olcum.deneme_ozeti(100.0, "HIGH", barlar, 1.0)
    assert ozet["deneme_epizot_025"] == 2
    assert ozet["deneme_bar_025"] == 5


def test_low_rolu_simetrik() -> None:
    barlar = [{"high": 105.0, "low": 101.0, "close": 103.0}] * olcum.SWING_PENCERESI
    ozet = olcum.deneme_ozeti(100.0, "LOW", barlar, 1.0)
    assert ozet["engelledi_025"] is True
    assert ozet["gecildi"] is False


def test_deneme_rol_gecersizse_hata() -> None:
    with pytest.raises(ValueError):
        olcum.deneme_ozeti(100.0, "MIDDLE", [{"high": 1.0, "low": 0.0, "close": 0.5}], 1.0)


# ---------------------------------------------------------------------------
# Yükseklik kovası
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("deger", "beklenen"),
    [(0.1, "0-0.5"), (0.49, "0-0.5"), (0.5, "0.5-1"), (0.99, "0.5-1"), (1.0, "1-2"), (1.9, "1-2"), (2.0, ">=2"), (9.0, ">=2")],
)
def test_yukseklik_kovasi(deger: float, beklenen: str) -> None:
    assert olcum.yukseklik_kovasi(deger) == beklenen


def test_yukseklik_kovasi_bilinmeyen() -> None:
    assert olcum.yukseklik_kovasi(None) == "BILINMEYEN"
    assert olcum.yukseklik_kovasi(float("nan")) == "BILINMEYEN"


# ---------------------------------------------------------------------------
# VP örnekleme
# ---------------------------------------------------------------------------
def test_vp_ornek_sinir_disi_indeks() -> None:
    ornek = olcum.vp_ornek([], 5)
    assert all(v is None for v in ornek.values())
    assert ornek["vp_rvol"] is None


def test_vp_ornek_none_history() -> None:
    ornek = olcum.vp_ornek(None, 0)
    assert ornek["vp_data_ready"] is None


def test_vp_ornek_bool_degeri_korur() -> None:
    """``data_ready`` bool'dur; float'a çevrilirse True/1 ayırt edilemez."""

    class _M:
        rvol = 1.5
        data_ready = True
        volume_usable = False

    ornek = olcum.vp_ornek([_M()], 0)
    assert ornek["vp_rvol"] == pytest.approx(1.5)
    assert ornek["vp_data_ready"] is True
    assert ornek["vp_volume_usable"] is False


# ---------------------------------------------------------------------------
# LOOKAHEAD GUARD: en kritik test
# ---------------------------------------------------------------------------
def test_lookahead_guard_ufuk_disi_bar_olcumu_degistirmez() -> None:
    """Ufuk dışındaki barlar ölçümü değiştirmemelidir.

    Aynı çapa, iki farklı gelecek uzunluğu: 12 barlık uzanım birebir aynı
    kalmalıdır. Değişirse ölçüm geleceği okuyordur ve backtest geçersizdir.
    Uzun pencere (40) alanları *bilerek* farklıdır; bu, sınırlı ufuk
    tanımının çalıştığını ayrıca kanıtlar.
    """
    taban = [(100.0, 101.0, 99.0, 100.0)] * 30
    kisa = _sentetik_frame(taban)
    uzun_fiyatlar = taban + [(100.0, 300.0, 99.0, 290.0)] * 60  # ufuk dışında dev hareket
    uzun = _sentetik_frame(uzun_fiyatlar)

    anchor = 10
    atr = 2.0
    referans = 100.0

    kisa_yol = olcum.tek_yonlu_yol("UP", referans, kisa.iloc[anchor + 1:].to_dict("records"), atr)
    uzun_yol = olcum.tek_yonlu_yol("UP", referans, uzun.iloc[anchor + 1:].to_dict("records"), atr)

    kisa_ozet = olcum.yol_ozeti(kisa_yol)
    uzun_ozet = olcum.yol_ozeti(uzun_yol)

    for h in olcum.HORIZONLAR:
        assert kisa_ozet[f"h{h}"] == pytest.approx(uzun_ozet[f"h{h}"]), f"h{h} ufuk dışı bardan etkilendi"
        assert kisa_ozet[f"h{h}_decay"] == pytest.approx(uzun_ozet[f"h{h}_decay"] or 0.0, abs=1e-9) or uzun_ozet[f"h{h}_decay"] is None
    for p in olcum.PAY_PENCERELERI:
        if kisa_ozet[f"pay_{p}"] is not None:
            assert kisa_ozet[f"pay_{p}"] == pytest.approx(uzun_ozet[f"pay_{p}"])

    # Uzun pencere dev hareketi GÖRMELİ — yani iki pencere gerçekten farklı.
    assert uzun_ozet["uzun_tepe_atr"] > kisa_ozet["uzun_tepe_atr"]


def test_lookahead_guard_capa_bari_uzanima_katilmaz() -> None:
    """Çapa barının kendisi uzanıma girerse tepki olduğundan büyük görünür."""
    fiyatlar = [(100.0, 100.5, 99.5, 100.0)] * 5
    fiyatlar.append((100.0, 250.0, 99.0, 240.0))  # çapa barı: dev yükseliş
    fiyatlar += [(240.0, 241.0, 239.0, 240.0)] * 12
    frame = _sentetik_frame(fiyatlar)
    anchor = 5
    yol = olcum.tek_yonlu_yol("UP", 100.0, frame.iloc[anchor + 1:].to_dict("records"), 1.0)
    ozet = olcum.yol_ozeti(yol)
    # Çapa barı dahil edilseydi tepe ~140 ATR olurdu; doğru değer ~141 değil,
    # çapa SONRASI barların uzanımıdır (240 - 100 = 140 değil, 241 - 100 = 141).
    assert ozet["tepe_atr"] == pytest.approx(141.0)
    assert len(yol) == 12, "yol uzunluğu çapa sonrası bar sayısı olmalı"


# ---------------------------------------------------------------------------
# Determinizm
# ---------------------------------------------------------------------------
def test_yol_ozeti_deterministik() -> None:
    yol = [0.5, 1.2, 0.8, 2.0, 1.5, 0.3, 0.1, 0.0, 0.4, 0.9, 1.1, 0.7]
    a = olcum.yol_ozeti(yol)
    b = olcum.yol_ozeti(list(yol))
    assert a == b


def test_deneme_ozeti_deterministik() -> None:
    barlar = [{"high": 100.5, "low": 96.0, "close": 99.0}] * 20
    a = olcum.deneme_ozeti(100.0, "HIGH", barlar, 1.5)
    b = olcum.deneme_ozeti(100.0, "HIGH", list(barlar), 1.5)
    assert a == b


# ---------------------------------------------------------------------------
# Arşiv yükleyici
# ---------------------------------------------------------------------------
def test_arsiv_eksik_dosya_file_not_found(tmp_path: Path) -> None:
    """Eksik arşiv dosyası sessiz boş çerçeve değil açık hata vermeli."""
    from research import arsiv

    with pytest.raises(FileNotFoundError):
        arsiv.tf_frame("YOKBOYLEBIRSEMBOL", "1h", kok=tmp_path)


def test_arsiv_bos_frame_sessiz_degil(tmp_path: Path) -> None:
    """Başlıklı ama satırsız CSV.gz: resample boş döner, gürültülü hata gerekir.

    Boş çerçeve 'ölçülecek zone yok' ile karışır ve raporda yanlışlıkla sıfır
    gözlem olarak görünür; bu yüzden sessizce boş dönmek kabul edilemez.
    """
    import gzip

    from research import arsiv

    frame = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    assert len(arsiv.temizle(frame)) == 0

    yol = tmp_path / "BOSSEMBOL_1h.csv.gz"
    with gzip.open(yol, "wt", encoding="utf-8") as dosya:
        dosya.write("bar_time,open,high,low,close,volume\n")
    with pytest.raises((ValueError, FileNotFoundError)):
        arsiv.tf_frame("BOSSEMBOL", "1h", kok=tmp_path)


def test_arsiv_kaynak_interval_eslemesi() -> None:
    """2h/4h 1h'den türetilir, 1d native günlük seriden okunur."""
    from research import arsiv

    assert arsiv.KAYNAK_INTERVAL == {"1h": "1h", "2h": "1h", "4h": "1h", "1d": "1d"}
    assert set(arsiv.ARASTIRMA_TIMEFRAMELERI) == {"1h", "2h", "4h", "1d"}


def test_arsiv_temizle_high_low_tutarsizligini_ayiklar() -> None:
    """high < low satırı uzanım ölçümünü ters çevirir; ayıklanmalıdır."""
    from research import arsiv

    frame = _sentetik_frame([(100.0, 101.0, 99.0, 100.0), (100.0, 98.0, 102.0, 100.0)])
    temiz = arsiv.temizle(frame)
    assert len(temiz) == 1
    assert float(temiz.iloc[0]["high"]) >= float(temiz.iloc[0]["low"])


def test_arsiv_sifir_hacim_satiri_dusurmez() -> None:
    """BIST açılış müzayede barı sistemli olarak sıfır hacimlidir; çıkarılamaz."""
    from research import arsiv

    frame = _sentetik_frame([(100.0, 101.0, 99.0, 100.0)] * 3, hacim=0.0)
    assert len(arsiv.temizle(frame)) == 3


def test_arsiv_manifest_bozuk_json_toleransi(tmp_path: Path) -> None:
    from research import arsiv

    (tmp_path / "manifest.json").write_text("{bozuk json", encoding="utf-8")
    assert arsiv.manifest_oku(tmp_path) == {}
    assert arsiv.arsiv_sembolleri(tmp_path) == []


# ---------------------------------------------------------------------------
# Kayıt katmanı: kimlik ve sürüm alanları
# ---------------------------------------------------------------------------
def test_config_hash_esiklere_duyarli() -> None:
    """Eşikler değişirse config_hash değişmeli; eski satırlar ayrışabilsin."""
    from research import kayit

    birinci = kayit.config_hash()
    assert isinstance(birinci, str) and len(birinci) == 12
    orijinal = olcum.SWING_PENCERESI
    try:
        olcum.SWING_PENCERESI = orijinal + 1
        assert kayit.config_hash() != birinci
    finally:
        olcum.SWING_PENCERESI = orijinal
    assert kayit.config_hash() == birinci


@pytest.mark.parametrize(
    ("direction", "beklenen"),
    [("UP", "UP"), ("DOWN", "DOWN"), ("NEUTRAL", "BELIRSIZ"), (None, "BELIRSIZ"), ("garip", "BELIRSIZ")],
)
def test_yon_metni_normalizasyonu(direction: object, beklenen: str) -> None:
    from research import kayit

    assert kayit.yon_metni(direction) == beklenen


def test_yon_metni_intenum_direction() -> None:
    """MS ``Direction`` bir IntEnum'dur (UP=1, DOWN=-1, NEUTRAL=0)."""
    from domain_engines.market_structure.models import Direction
    from research import kayit

    assert kayit.yon_metni(Direction.UP) == "UP"
    assert kayit.yon_metni(Direction.DOWN) == "DOWN"
    assert kayit.yon_metni(Direction.NEUTRAL) == "BELIRSIZ"


@pytest.mark.parametrize(
    ("tepe", "beklenen"),
    [(None, "OLCULEMEDI"), (float("nan"), "OLCULEMEDI"), (-0.5, "TERS"), (0.0, "YOK"), (0.24, "YOK"), (0.25, "AZ"), (0.99, "AZ"), (1.0, "CALISTI"), (5.0, "CALISTI")],
)
def test_tepki_sinifi_esikleri(tepe: float | None, beklenen: str) -> None:
    assert olcum.tepki_sinifi(tepe) == beklenen


def test_bar_time_pencere_indeksi_degil() -> None:
    """Kimlik ``bar_time`` olmalı; pencere içi indeks yeniden koşuda kayar."""
    from research import kayit

    frame = _sentetik_frame([(100.0, 101.0, 99.0, 100.0)] * 5)
    frame = frame.reset_index().rename(columns={"index": "timestamp"})
    assert kayit._bar_time(frame, 2) is not None
    assert "2025-01" in str(kayit._bar_time(frame, 2))
    assert kayit._bar_time(frame, None) is None
    assert kayit._bar_time(frame, -1) is None
    assert kayit._bar_time(frame, 999) is None


def test_ozet_duzlestir_string_degeri_korur() -> None:
    """``olcum_yonu`` gibi string alanlar ``None``'a dönüşmemeli.

    Önceki sürüm her değeri ``float()`` içinden geçiriyordu ve string alanlar
    sessizce ``None`` oluyordu: ölçüm yapıldığı halde "yön belirlenemedi"
    gibi görünüyordu.
    """
    from research import kayit

    duz = kayit._ozet_duzlestir({"olcum_yonu": "DOWN", "tepe_atr": 1.234567891, "bayrak": True, "bos": None}, "kenar_")
    assert duz["kenar_olcum_yonu"] == "DOWN"
    assert duz["kenar_tepe_atr"] == pytest.approx(1.234568)
    assert duz["kenar_bayrak"] is True
    assert duz["kenar_bos"] is None


# ---------------------------------------------------------------------------
# Uçtan uca: sentetik veri üzerinde tam ölçüm
# ---------------------------------------------------------------------------
def test_sembol_timeframe_gozlem_sentetik_ucan_uca() -> None:
    """Sentetik seride tam hat koşar; kategoriler ve alanlar üretilir."""
    from research import kayit

    fiyatlar: list[tuple[float, float, float, float]] = []
    fiyat = 100.0
    for i in range(140):
        yon = 1.0 if (i // 10) % 2 == 0 else -1.0
        acilis = fiyat
        kapanis = fiyat + yon * 1.5
        yuksek = max(acilis, kapanis) + 0.8
        dusuk = min(acilis, kapanis) - 0.8
        fiyatlar.append((acilis, yuksek, dusuk, kapanis))
        fiyat = kapanis
    frame = _sentetik_frame(fiyatlar)

    gozlem = kayit.sembol_timeframe_gozlem("TEST", "4h", frame)
    assert set(gozlem) == {"zone", "dokunus", "swing", "event", "meta"}
    meta = gozlem["meta"][0]
    assert meta["symbol"] == "TEST" and meta["timeframe"] == "4h"
    assert meta["bar_sayisi"] == 140
    assert meta["engine_version"] == kayit.ENGINE_VERSION
    assert meta["config_hash"] == kayit.config_hash()

    for kategori in ("zone", "dokunus", "swing", "event"):
        for satir in gozlem[kategori]:
            assert satir["engine_version"] == kayit.ENGINE_VERSION
            assert satir["config_hash"] == kayit.config_hash()


def test_gozlem_deterministik_iki_kosu() -> None:
    """Aynı çerçeve iki kez ölçülünce aynı satırları üretmeli."""
    from research import kayit

    fiyatlar = [(100.0 + (i % 7), 103.0 + (i % 7), 97.0 + (i % 5), 101.0 + (i % 6)) for i in range(130)]
    frame = _sentetik_frame(fiyatlar)
    a = kayit.sembol_timeframe_gozlem("DET", "4h", frame)
    b = kayit.sembol_timeframe_gozlem("DET", "4h", frame)
    for kategori in ("zone", "dokunus", "swing", "event"):
        assert len(a[kategori]) == len(b[kategori]), kategori
        for x, y in zip(a[kategori], b[kategori]):
            assert x == y, f"{kategori} deterministik değil"


def test_bos_frame_bos_gozlem() -> None:
    from research import kayit

    gozlem = kayit.sembol_timeframe_gozlem("BOS", "4h", pd.DataFrame())
    assert gozlem == {"zone": [], "dokunus": [], "swing": [], "event": [], "meta": []}


# ---------------------------------------------------------------------------
# CLI sözleşmesi
# ---------------------------------------------------------------------------
def _cli_modulu():
    yol = REPO_KOKU / "scripts" / "backfill" / "arastirma_kosu.py"
    spec = importlib.util.spec_from_file_location("arastirma_kosu", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_cli_help_calisir() -> None:
    import subprocess

    sonuc = subprocess.run(
        [sys.executable, str(REPO_KOKU / "scripts" / "backfill" / "arastirma_kosu.py"), "--help"],
        capture_output=True, text=True, timeout=120,
    )
    assert sonuc.returncode == 0, sonuc.stderr
    assert "--limit" in sonuc.stdout and "--agrega" in sonuc.stdout


def test_cli_jsonl_idempotent_devam(tmp_path: Path) -> None:
    """Tamamlanmış (symbol, timeframe) çiftleri yeniden koşulmaz."""
    cli = _cli_modulu()
    meta_yolu = tmp_path / "meta.jsonl"
    cli._ekle(meta_yolu, [{"symbol": "AAA", "timeframe": "1h"}, {"symbol": "AAA", "timeframe": "2h"}])
    tamamlanan = cli._tamamlananlar(tmp_path)
    assert tamamlanan == {("AAA", "1h"), ("AAA", "2h")}

    # Aynı veriyi bir kez daha eklemek yeni iş üretmemeli
    before = len(cli._jsonl_oku(meta_yolu))
    plan = [(s, tf) for s in ("AAA",) for tf in ("1h", "2h", "4h") if (s, tf) not in tamamlanan]
    assert plan == [("AAA", "4h")]
    assert before == 2


def test_cli_jsonl_bozuk_satir_toleransi(tmp_path: Path) -> None:
    """Çökme anında yarım kalan son satır dosyanın geri kalanını bozmamalı."""
    cli = _cli_modulu()
    yol = tmp_path / "meta.jsonl"
    yol.write_text('{"symbol": "A", "timeframe": "1h"}\n{"symbol": "B"\n', encoding="utf-8")
    kayitlar = cli._jsonl_oku(yol)
    assert len(kayitlar) == 1
    assert kayitlar[0]["symbol"] == "A"


def test_cli_json_serializable_nan_ve_timestamp() -> None:
    cli = _cli_modulu()
    ts = pd.Timestamp("2025-01-02 09:30", tz="Europe/Istanbul")
    assert cli._json_serializable(float("nan")) is None
    assert cli._json_serializable(float("inf")) is None
    assert cli._json_serializable(ts) == str(ts)
    assert cli._json_serializable(True) is True
    assert cli._json_serializable(None) is None
    assert isinstance(cli._json_serializable(pd.Series([1, 2])), str)


def test_havuz_disi_semboller_isaretli() -> None:
    """BRENT havuz dışıdır: seans yapısı yok, havuzlanmış istatistiği bozar."""
    from research import arsiv

    assert "BRENT" in arsiv.HAVUZ_DISI_SEMBOLLER
    assert arsiv.HAVUZ_DISI_SEMBOLLER["BRENT"]


# ---------------------------------------------------------------------------
# Rol geçmişi izleme: survivorship düzeltmesinin regresyon testleri
# ---------------------------------------------------------------------------
class _SahteBaglam:
    """``StructureContext`` yerine geçen minimal nesne."""

    def __init__(self, **roller: int) -> None:
        for alan in (
            "protected_high_identity",
            "protected_low_identity",
            "strong_high_identity",
            "strong_low_identity",
            "weak_high_identity",
            "weak_low_identity",
        ):
            setattr(self, alan, int(roller.get(alan, 0)))


def _gecmis_kos(baglamlar: list[_SahteBaglam]) -> list[dict]:
    from research import kayit

    aktif: dict = {}
    gecmis: list[dict] = []
    for bar_index, ctx in enumerate(baglamlar):
        kayit.rol_gecmisi_guncelle(aktif, gecmis, "EXTERNAL", ctx, bar_index)
    # Açık aralıkları veri sonuna kadar kapat
    for (scope, rol), (kimlik, ilk) in aktif.items():
        son = len(baglamlar) - 1
        gecmis.append({
            "scope": scope, "rol": rol, "identity": kimlik,
            "rol_ilk_bar": ilk, "rol_son_bar": son,
            "rol_sure_bar": son - ilk + 1, "kapanis": "VERI_SONU_SANSURLU",
        })
    return gecmis


def test_rol_araligi_cok_bar_surabilir() -> None:
    """REGRESYON: rol sabitken başlangıç barı kaydırılmamalı.

    Önceki sürüm kimlik değişmediğinde bile başlangıcı güncelliyordu ve
    30.238 aralığın TAMAMI 1 bar görünüyordu. 10 bar boyunca aynı identity
    PH taşıyorsa tek aralık ve süre 10 olmalıdır.
    """
    baglamlar = [_SahteBaglam(protected_high_identity=7)] * 10
    gecmis = _gecmis_kos(baglamlar)
    ph = [g for g in gecmis if g["rol"] == "PH"]
    assert len(ph) == 1, f"tek aralık bekleniyordu, {len(ph)} bulundu"
    assert ph[0]["identity"] == 7
    assert ph[0]["rol_ilk_bar"] == 0
    assert ph[0]["rol_sure_bar"] == 10


def test_rol_devri_araligi_kapatir() -> None:
    """Rol başka bir swing'e geçince eski aralık DEVREDILDI ile kapanır."""
    baglamlar = [_SahteBaglam(protected_high_identity=7)] * 4
    baglamlar += [_SahteBaglam(protected_high_identity=9)] * 3
    gecmis = _gecmis_kos(baglamlar)
    ph = sorted((g for g in gecmis if g["rol"] == "PH"), key=lambda g: g["rol_ilk_bar"])
    assert [g["identity"] for g in ph] == [7, 9]
    assert ph[0]["rol_ilk_bar"] == 0 and ph[0]["rol_son_bar"] == 3 and ph[0]["rol_sure_bar"] == 4
    assert ph[0]["kapanis"] == "DEVREDILDI"
    assert ph[1]["rol_ilk_bar"] == 4 and ph[1]["rol_sure_bar"] == 3
    assert ph[1]["kapanis"] == "VERI_SONU_SANSURLU"


def test_rol_temizlenince_aralik_kapanir() -> None:
    """Rol 0'a düşünce TEMIZLENDI ile kapanır; açık kalmaz."""
    baglamlar = [_SahteBaglam(weak_low_identity=3)] * 5
    baglamlar += [_SahteBaglam(weak_low_identity=0)] * 5
    gecmis = _gecmis_kos(baglamlar)
    wl = [g for g in gecmis if g["rol"] == "WL"]
    assert len(wl) == 1
    assert wl[0]["kapanis"] == "TEMIZLENDI"
    assert wl[0]["rol_sure_bar"] == 5


def test_rol_yeniden_alinirsa_iki_aralik() -> None:
    """Aynı identity rolü bırakıp yeniden alırsa iki ayrı aralık oluşur."""
    baglamlar = [_SahteBaglam(protected_low_identity=5)] * 3
    baglamlar += [_SahteBaglam(protected_low_identity=0)] * 2
    baglamlar += [_SahteBaglam(protected_low_identity=5)] * 4
    gecmis = _gecmis_kos(baglamlar)
    pl = sorted((g for g in gecmis if g["rol"] == "PL"), key=lambda g: g["rol_ilk_bar"])
    assert len(pl) == 2
    assert [g["rol_sure_bar"] for g in pl] == [3, 4]
    assert [g["kapanis"] for g in pl] == ["TEMIZLENDI", "VERI_SONU_SANSURLU"]


def test_roller_birbirinden_bagimsiz_izlenir() -> None:
    """PH değişirken WL sabitse WL aralığı bölünmemelidir."""
    baglamlar = [
        _SahteBaglam(protected_high_identity=1, weak_low_identity=2),
        _SahteBaglam(protected_high_identity=3, weak_low_identity=2),
        _SahteBaglam(protected_high_identity=3, weak_low_identity=2),
    ]
    gecmis = _gecmis_kos(baglamlar)
    wl = [g for g in gecmis if g["rol"] == "WL"]
    ph = sorted((g for g in gecmis if g["rol"] == "PH"), key=lambda g: g["rol_ilk_bar"])
    assert len(wl) == 1 and wl[0]["rol_sure_bar"] == 3
    assert [g["identity"] for g in ph] == [1, 3]


def test_hic_rol_yoksa_gecmis_bos() -> None:
    assert _gecmis_kos([_SahteBaglam()] * 5) == []


@pytest.mark.skipif(
    not (REPO_KOKU / "backfill_data").exists(),
    reason="backfill_data/ arşivi yok; gerçek veri testi atlanır",
)
def test_gercek_veride_rol_araliklari_birden_uzun() -> None:
    """Gerçek arşivde tüm rol aralıklarının 1 bar olması imkânsızdır.

    Bu test 704 işlik koşuyu baştan sona yanlış üreten hatayı kilitler.
    """
    from research import arsiv, kayit

    frame = kayit._normalize_frame(arsiv.tf_frame("THYAO", "4h"))
    _, gecmis = kayit.ms_adimli_kosu(frame)
    assert gecmis, "rol geçmişi boş olmamalı"
    sureler = [g["rol_sure_bar"] for g in gecmis]
    assert max(sureler) > 1, f"tüm aralıklar 1 bar: {set(sureler)}"
    assert sum(1 for s in sureler if s > 1) / len(sureler) > 0.2, (
        "aralıkların en az %20'si birden uzun olmalı"
    )


# ---------------------------------------------------------------------------
# Eşzamanlı koşu kilidi ve çift kayıt bekçisi
# ---------------------------------------------------------------------------
def test_kilit_ikinci_ornek_engeller(tmp_path: Path) -> None:
    """Aynı çıktı dizinine ikinci bir koşu başlatılamamalı.

    Gerçek olay: `stop_process` bir koşuyu durdurmuş *göründü* ama süreç
    yaşadı; düzeltilmiş ikinci koşu başlatılınca ikisi aynı JSONL dosyalarına
    ekledi. 704 işin 501'i çift yazıldı ve çiftlerin yarısı hatalı kodun
    çıktısıydı. Agregasyon bunu yakalamadı çünkü her satır tek başına
    geçerliydi.
    """
    import os

    cli = _cli_modulu()
    cikti = tmp_path / "cikti"
    kilit_yolu = cli._kilit_yolu(cikti)

    with cli._Kilit(kilit_yolu):
        assert kilit_yolu.exists()
        assert int(kilit_yolu.read_text(encoding="utf-8")) == os.getpid()
        # Kendi pid'imiz kilitteyse ikinci giriş bayat sayılıp devralınır;
        # bu yüzden gerçek çakışmayı yaşayan başka bir pid ile taklit edilir.
        kilit_yolu.write_text("1", encoding="utf-8")  # pid 1 (init) daima yaşar
        with pytest.raises(SystemExit) as bilgi:
            with cli._Kilit(kilit_yolu):
                pass
        assert "BAŞKA BİR KOŞU" in str(bilgi.value)
    assert not kilit_yolu.exists(), "kilit çıkışta serbest bırakılmalı"


def test_kilit_bayat_kilidi_devralir(tmp_path: Path) -> None:
    """Sahibi ölmüş kilit devralınmalı, yoksa koşu bir daha hiç başlamaz."""
    cli = _cli_modulu()
    kilit_yolu = tmp_path / "cikti.kilit"
    kilit_yolu.write_text("999999", encoding="utf-8")  # var olmayan pid
    assert not cli._pid_yasamda(999999)
    with cli._Kilit(kilit_yolu) as k:
        assert k.alindi
    assert not kilit_yolu.exists()


def test_kilit_yolu_cikti_dizininin_kardesi(tmp_path: Path) -> None:
    """`--zorla` çıktı dizinini siler; kilit içinde olsaydı koruma kaybolurdu."""
    cli = _cli_modulu()
    cikti = tmp_path / "arastirma_cikti"
    assert cli._kilit_yolu(cikti) == tmp_path / ".arastirma_cikti.kilit"
    assert cli._kilit_yolu(cikti).parent != cikti


def test_agregasyon_cift_kayitta_durmali(tmp_path: Path) -> None:
    """Yinelenen (symbol, timeframe) raporu üretmek yerine koşuyu durdurmalı."""
    import pandas as pd

    cli = _cli_modulu()
    cikti = tmp_path / "cikti"
    cikti.mkdir()
    cli._ekle(cikti / "meta.jsonl", [
        {"symbol": "AAA", "timeframe": "1h", "bar_sayisi": 100},
        {"symbol": "AAA", "timeframe": "1h", "bar_sayisi": 100},
    ])
    args = argparse.Namespace(
        cikti=str(cikti), rapor=str(tmp_path / "r.md"), csv_atla=True, havuz_disi_dahil=False,
    )
    with pytest.raises(SystemExit) as bilgi:
        cli.agregasyon(args)
    assert "ÇİFT KAYIT" in str(bilgi.value)
    assert not (tmp_path / "r.md").exists(), "kirli veriden rapor üretilmemeli"


def test_agregasyon_tek_kayitta_calisir(tmp_path: Path) -> None:
    """Bekçi yanlış pozitif üretmemeli: temiz çıktı raporlanabilmeli."""
    cli = _cli_modulu()
    cikti = tmp_path / "cikti"
    cikti.mkdir()
    cli._ekle(cikti / "meta.jsonl", [
        {"symbol": "AAA", "timeframe": "1h", "bar_sayisi": 100, "zone_sayisi": 3},
        {"symbol": "AAA", "timeframe": "2h", "bar_sayisi": 50, "zone_sayisi": 2},
    ])
    args = argparse.Namespace(
        cikti=str(cikti), rapor=str(tmp_path / "r.md"), csv_atla=True, havuz_disi_dahil=False,
    )
    assert cli.agregasyon(args) == 0
    assert (tmp_path / "r.md").exists()
