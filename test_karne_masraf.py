# -*- coding: utf-8 -*-
"""Karne masraf katmanı — sözleşmeler (2026-11-16).

Neden bu dosya: karne "10 sinyalde 4 hedef" diyordu ama işlem masrafını
(komisyon + kayma) hiç saymıyordu; kâğıt üstünde artı görünen hafta gerçekte
eksi olabiliyordu. Buradaki testler üç şeyi kilitler:

1. **Formül**: masraf = komisyon (gidiş-dönüş, bps) + kayma (tek yön ATR × 2).
   Net = brüt − masraf. Elle hesapla birebir eşleşmeli.
2. **Metin**: karne "Para (sinyal başına ortalama)" bölümünü yazar, masraf
   parametresini gizlemez, ve eski dağınık satırlar (`⚡ Kırılım:`, `🎯`,
   "ort. lehte") artık üretilmez.
3. **Okunabilirlik**: her satır Telegram bütçesine (283 px) sığar.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import karne as K

IST = timezone(timedelta(hours=3))


def _zaman(*args):
    return datetime(*args, tzinfo=IST)


def _seri(baslangic: datetime, kapanislar):
    """Kapanış listesinden OHLCV serisi; yüksek/düşük kapanışın ±%1'i."""
    idx = [baslangic + timedelta(hours=i) for i in range(len(kapanislar))]
    return pd.DataFrame(
        {
            "open": kapanislar,
            "high": [k * 1.01 for k in kapanislar],
            "low": [k * 0.99 for k in kapanislar],
            "close": kapanislar,
            "volume": [1000] * len(kapanislar),
        },
        index=pd.DatetimeIndex(idx, name="time"),
    )


def _kayit(bar_time, entry=100.0, atr=2.0, yon=1, stock="THYAO", tf="4h"):
    return {
        "tip": "kirilim", "stock": stock, "tf": tf, "pattern": "Üçgen",
        "state": "KIRILIM_TEYITLI", "dir": yon, "entry": entry, "atr": atr,
        "quality": 85.0, "bar_time": bar_time.isoformat(),
    }


# ------------------------------------------------------------ 1) FORMÜL ----
def test_masraf_formulu_elle_hesapla_esit():
    """entry 100, ATR 2, komisyon binde 2,1, kayma 0,05 ATR → masraf %0,41."""
    baslangic = _zaman(2026, 9, 28, 10)
    # Hedef: 1,5 ATR = 3 TL → +%3,0 brüt
    seri = _seri(baslangic, [100, 101, 102, 104])
    sonuc = K.sinyal_sonucu(_kayit(baslangic), seri,
                            komisyon_bps=21.0, kayma_atr=0.05)
    assert sonuc["durum"] == K.DURUM_HEDEF
    assert sonuc["masraf_pct"] == pytest.approx(0.41, abs=1e-6)   # 0,21 + 0,20
    assert sonuc["brut_pct"] == pytest.approx(3.0, abs=1e-6)
    assert sonuc["net_pct"] == pytest.approx(2.59, abs=1e-6)


def test_masraf_stopta_da_dusulur():
    """Stop −1,0 ATR = −%2,0 brüt; net −%2,41 (masraf kaybı büyütür)."""
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100, 99, 97, 96])
    sonuc = K.sinyal_sonucu(_kayit(baslangic), seri,
                            komisyon_bps=21.0, kayma_atr=0.05)
    assert sonuc["durum"] == K.DURUM_STOP
    assert sonuc["brut_pct"] == pytest.approx(-2.0, abs=1e-6)
    assert sonuc["net_pct"] == pytest.approx(-2.41, abs=1e-6)


def test_masraf_sifirsa_net_brute_esit():
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100, 101, 102, 104])
    sonuc = K.sinyal_sonucu(_kayit(baslangic), seri, komisyon_bps=0.0, kayma_atr=0.0)
    assert sonuc["masraf_pct"] == 0.0
    assert sonuc["net_pct"] == sonuc["brut_pct"]


def test_notr_sinyalde_isaret_korunur():
    """Nötr sinyalin brütü ufuk sonu yönlü getiri; net masraf kadar azalır."""
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100, 100.4, 100.6, 100.8])   # ne hedef ne stop
    sonuc = K.sinyal_sonucu(_kayit(baslangic), seri,
                            komisyon_bps=21.0, kayma_atr=0.05)
    assert sonuc["durum"] == K.DURUM_NOTR
    assert sonuc["brut_pct"] == pytest.approx(0.8, abs=1e-6)      # +%0,8
    assert sonuc["net_pct"] == pytest.approx(0.39, abs=1e-6)


def test_bekleyen_sinyalde_masraf_alanlari_bos():
    """Henüz bar dolmadıysa brüt/net `None` (uydurma sayı yok)."""
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100])                      # ileri bar yok
    sonuc = K.sinyal_sonucu(_kayit(baslangic), seri)
    assert sonuc["durum"] == K.DURUM_BEKLIYOR
    assert sonuc["brut_pct"] is None and sonuc["net_pct"] is None


def test_komisyon_modul_sabiti_uzerinden_okunur(monkeypatch):
    """Varsayılan `config.KARNE_KOMISYON_BPS`; env/monkeypatch ile değişebilir."""
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100, 101, 102, 104])
    varsayilan = K.sinyal_sonucu(_kayit(baslangic), seri)
    monkeypatch.setattr(K, "KARNE_KOMISYON_BPS", 0.0)
    monkeypatch.setattr(K, "KARNE_KAYMA_ATR", 0.0)
    sifir = K.sinyal_sonucu(_kayit(baslangic), seri)
    assert varsayilan["masraf_pct"] > 0
    assert sifir["masraf_pct"] == 0.0


# ------------------------------------------------- 2) HAFTALIK KOVALAR -----
def test_haftalik_net_kovalari_ve_ortanca():
    """Farklı haftalardaki sinyaller ayrı kovaya düşer; ortanca doğru hesaplanır."""
    haftalar = [_zaman(2026, 9, 21, 10), _zaman(2026, 9, 28, 10),
                _zaman(2026, 10, 5, 10)]
    # net sırasıyla: +%2,59 (hedef), +%2,59 (hedef), −%2,41 (stop)
    kapanislar = [[100, 101, 102, 104], [100, 101, 102, 104], [100, 99, 97, 96]]
    kayitlar = [_kayit(h, stock=f"S{i}") for i, h in enumerate(haftalar)]
    seriler = {f"S{i}": _seri(h, k) for i, (h, k) in enumerate(zip(haftalar, kapanislar))}
    metrik = K.karne_hesapla(kayitlar, lambda s, tf: seriler.get(s),
                             now=_zaman(2026, 10, 9, 18))
    assert len(metrik["haftalik_net"]) == 3
    degerler = [v for _, v in metrik["haftalik_net"]]
    assert degerler == pytest.approx([2.59, 2.59, -2.41], abs=1e-2)
    assert metrik["haftalik_net_ortanca"] == pytest.approx(2.59, abs=1e-2)


def test_tek_hafta_varsa_ortanca_uretilmez():
    """2'den az kova varsa "son N hafta" bölümü yazılmaz (uydurma yok)."""
    baslangic = _zaman(2026, 9, 28, 10)
    kayitlar = [_kayit(baslangic)]
    seri = _seri(baslangic, [100, 101, 102, 104])
    metrik = K.karne_hesapla(kayitlar, lambda s, tf: seri, now=_zaman(2026, 10, 2, 18))
    assert len(metrik["haftalik_net"]) == 1
    assert metrik["haftalik_net_ortanca"] is None


# ------------------------------------------------------------- 3) METİN ----
def _metin(metrik, baslik="HAFTALIK DOĞRULUK KARNESİ"):
    return K.karne_metni(metrik, baslik=baslik, pencere_metni="28.09–02.10.2026",
                         gun_sayisi=5)


def test_metin_masraf_bolumunu_yazar():
    baslangic = _zaman(2026, 9, 28, 10)
    kayitlar = [_kayit(baslangic)]
    seri = _seri(baslangic, [100, 101, 102, 104])
    metrik = K.karne_hesapla(kayitlar, lambda s, tf: seri, now=_zaman(2026, 10, 2, 18))
    metin = _metin(metrik)
    assert "Sonuç" in metin
    assert "1 sinyal · yukarı 1 · aşağı 0" in metin
    assert "Para (sinyal başına ortalama)" in metin
    assert "Masraf dahil: +%2,59" in metin
    assert "Masrafsız: +%3,00" in metin
    assert "Masraf: binde 2,1 + kayma" in metin


def test_metin_eski_daginik_satirlari_uretmez():
    """Sadeleştirme sonrası eski biçim tamamen kalkmalı (iki biçim bir arada olmaz)."""
    baslangic = _zaman(2026, 9, 28, 10)
    kayitlar = [_kayit(baslangic)]
    seri = _seri(baslangic, [100, 101, 102, 104])
    metrik = K.karne_hesapla(kayitlar, lambda s, tf: seri, now=_zaman(2026, 10, 2, 18))
    metin = _metin(metrik)
    for eski in ("⚡ Kırılım:", "🎯", "ort. lehte", "✅ Yönünde", "ters "):
        assert eski not in metin, f"eski satır kaldı: {eski}"


def test_metin_guven_esikleri():
    """n<30 / 30-100 / 100+ için farklı güven cümlesi; sayı her zaman görünür."""
    baslangic = _zaman(2026, 9, 28, 10)
    seri = _seri(baslangic, [100, 101, 102, 104])
    metrik = K.karne_hesapla([_kayit(baslangic)], lambda s, tf: seri,
                             now=_zaman(2026, 10, 2, 18))
    metin = _metin(metrik)
    assert "Güven: az veri (1 sinyal)" in metin
    assert "30+ sinyalden sonra yorum yapılır" in metin

    metrik2 = dict(metrik)
    metrik2["degerlendirilen"] = 45
    assert "Güven: kısmi (45 sinyal)" in _metin(metrik2)
    metrik3 = dict(metrik)
    metrik3["degerlendirilen"] = 120
    assert "Güven: yeterli (120 sinyal)" in _metin(metrik3)


def test_metin_satirlari_telegram_butcesine_sigar():
    """Hiçbir satır 283 px'i aşmaz (telefonda ortadan bölünme yok)."""
    from telegram_measure import SATIR_BUTCE, genislik

    baslangic = _zaman(2026, 9, 28, 10)
    kayitlar = [_kayit(baslangic, stock="THYAO"),
                _kayit(_zaman(2026, 9, 29, 10), yon=-1, stock="GARAN")]
    seriler = {
        "THYAO": _seri(baslangic, [100, 101, 102, 104]),
        "GARAN": _seri(_zaman(2026, 9, 29, 10), [100, 99, 97, 96]),
    }
    metrik = K.karne_hesapla(kayitlar, lambda s, tf: seriler.get(s),
                             now=_zaman(2026, 10, 2, 18))
    for satir in _metin(metrik).split("\n"):
        assert genislik(satir) <= SATIR_BUTCE, f"bütçe aşıldı: {satir!r}"
