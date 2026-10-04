"""FAZ 3 — Backtest V1 SÖZLEŞME testleri (implementasyondan bağımsız, ŞİMDİ geçer).

Bu dosya backtest'in üzerine bineceği zeminin DONMUŞ olduğunu kanıtlar:
  * karne.py outcome matematiği ve config eşikleri değişmemiştir (golden sayımlar),
  * history / karne / outcome-link OKUMA yolları salt-okunurdur (yazma API'leri
    patlatılmışken bile çağrılmaz, dosya byte'ları aynı kalır),
  * bozuk history dosyası okuyucuyu düşürmez (backtest'in #16 güvencesinin zemini),
  * Telegram komut ayrıştırma `/backtest 90 detay` biçimini taşır,
  * son test: analytics/backtest.py modülünün varlığı — FAZ3 V1 implementasyonu
    gelene kadar bu tek test KIRMIZI kalması İÇİN yazılmıştır (kırmızı çapa).

Kural: bu turda production koduna dokunulmadı; testler spesifikasyondur.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os

import pandas as pd
import pytest

from config import (ALERT_MIN_QUALITY, KARNE_FORMASYON_TTL_SAAT, KARNE_HEDEF_ATR,
                    KARNE_HORIZON_BAR, KARNE_SAKLAMA_GUN, KARNE_STOP_ATR)
from karne import KarneDefteri, sinyal_sonucu
from state import formation_history as fh
from telegram_commands import komut_coz


def _dosya_sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ---------------------------------------------------------------------------
# 1) MATEMATİK / EŞİK DONMUMLUĞU (rule: backtest hiçbir katsayı eşiği değiştirmez)
# ---------------------------------------------------------------------------

def test_karne_outcome_esikleri_donmus():
    """Karne hedef/stop/ufuk sabitleri Faz 3'te de aynı kalmalı."""
    assert KARNE_HEDEF_ATR == 1.5
    assert KARNE_STOP_ATR == 1.0
    assert KARNE_HORIZON_BAR == 10
    assert KARNE_SAKLAMA_GUN == 120
    assert KARNE_FORMASYON_TTL_SAAT == 48


def test_alarm_kalite_esikleri_donmus():
    """TF bazlı alarm eşikleri backtest tarafından okunur, DEĞİŞTİRİLMEZ."""
    assert ALERT_MIN_QUALITY == {"1h": 80, "2h": 78, "4h": 75, "1d": 70}


def _seri_ve_kayit(bar_high, bar_low, bar_close):
    idx = pd.date_range("2026-09-01 10:00", periods=11, freq="1h",
                        tz="Europe/Istanbul")
    df = pd.DataFrame({"high": bar_high, "low": bar_low, "close": bar_close},
                      index=idx)
    kayit = {"tip": "kirilim", "stock": "AKBNK", "tf": "1h", "dir": 1,
             "entry": 100.0, "atr": 1.0,
             "bar_time": "2026-09-01 10:00:00+03:00"}
    return kayit, df


def test_sinyal_sonucu_golden_hedef():
    """GOLDEN: giriş 100, ATR 1, hedef 1.5 ATR — 3. barda dokunuş, stop yok."""
    high = [100.2] * 11
    high[3] = 101.6
    low = [99.9] * 11
    close = [100.1] * 11
    close[10] = 101.0
    kayit, df = _seri_ve_kayit(high, low, close)

    sonuc = sinyal_sonucu(kayit, df)
    assert sonuc is not None
    assert sonuc["durum"] == "hedef"
    assert sonuc["hedef_bar"] == 3
    assert sonuc["stop_bar"] is None
    assert sonuc["mfe_pct"] == 1.6        # lehte max: 101.6 vs 100
    assert sonuc["mae_pct"] == 0.1        # alehte max: 99.9 vs 100
    assert sonuc["mfe_atr"] == 1.6        # 1.6 puan hareket / 1.0 ATR
    assert sonuc["mae_atr"] == 0.1
    assert sonuc["son_pct"] == 1.0        # kapanış 101.0
    assert sonuc["bar_sayisi"] == 10


def test_sinyal_sonucu_golden_ayni_bar_koruyucu_stop():
    """GOLDEN: aynı barda hem hedef hem stop dokunuşu -> muhafazakâr STOP."""
    high = [100.2] * 11
    high[1] = 101.6
    low = [99.9] * 11
    low[1] = 98.9
    close = [100.1] * 11
    kayit, df = _seri_ve_kayit(high, low, close)

    sonuc = sinyal_sonucu(kayit, df)
    assert sonuc["durum"] == "stop"
    assert sonuc["hedef_bar"] == 1
    assert sonuc["stop_bar"] == 1


def test_sinyal_sonucu_golden_bekliyor_ufuk_yok():
    """GOLDEN: sinyalden sonra hiç bar yoksa durum bekliyor, sayaçlar 0."""
    idx = pd.date_range("2026-09-01 10:00", periods=1, freq="1h",
                        tz="Europe/Istanbul")
    df = pd.DataFrame({"high": [100.2], "low": [99.9], "close": [100.1]},
                      index=idx)
    kayit = {"tip": "kirilim", "stock": "AKBNK", "tf": "1h", "dir": 1,
             "entry": 100.0, "atr": 1.0, "bar_time": "2026-09-01 10:00:00+03:00"}
    sonuc = sinyal_sonucu(kayit, df)
    assert sonuc["durum"] == "bekliyor"
    assert sonuc["bar_sayisi"] == 0
    assert sonuc["mfe_pct"] is None


# ---------------------------------------------------------------------------
# 2) OKUMA YOLLARI SALT-OKUNUR (backtest'in kullanacağı fonksiyonlar)
# ---------------------------------------------------------------------------

def _tarih_yaz(tmp_path, stock="AKBNK", tf="1h", sid="sid-1", sonuc=None):
    """Geçerli bir history defteri yazıp yolunu döner (sadece test fixtures'ü)."""
    rec = {
        "stable_id": sid,
        "durum": "terminal",
        "terminal_state": "FORMASYON_TAMAMLANDI",
        "ilk_gorulme": "2026-09-20T09:00:00+03:00",
        "son_gorulme": "2026-09-20T18:00:00+03:00",
        "dogum": {"bar_time": "2026-09-20 10:00:00+03:00", "bar_index": 5,
                  "alanlar": {"stable_id": sid, "pattern_type": "Simetrik Üçgen",
                               "family": "Üçgen", "classic_dir": 0,
                               "raw_quality": 78.0}},
        "olaylar": [],
        "snapshotlar": [],
    }
    if sonuc is not None:
        rec["sonuc"] = sonuc
    yol = fh.yol(stock, tf, str(tmp_path))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({"surum": 1, "stock": stock, "timeframe": tf,
                   "guncellendi": None, "kayitlar": {sid: rec}}, f)
    return yol


def test_fh_yukle_salt_okunur_dosyaya_dokunmaz(tmp_path):
    yol = _tarih_yaz(tmp_path)
    once = _dosya_sha(yol)
    defter = fh.yukle("AKBNK", "1h", str(tmp_path))
    rec = fh.kayit_getir(defter, "sid-1")
    assert rec is not None and rec["durum"] == "terminal"
    assert fh.kayitlar(defter)
    assert _dosya_sha(yol) == once


def test_bozuk_history_dosyasi_yukleyiciyi_dusurmez(tmp_path):
    """#16 zemini: bozuk dosya -> boş defter; exception SIZMAZ."""
    yol = fh.yol("BOZUK", "1h", str(tmp_path))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write("{bozuk json,,,\"")
    defter = fh.yukle("BOZUK", "1h", str(tmp_path))
    assert defter["kayitlar"] == {}


def test_karne_defteri_yukle_kaydetmez(tmp_path):
    dosya = tmp_path / "karne_defteri.json"
    icerik = {
        "surum": 1,
        "kayitlar": {
            "K1": {"tip": "kirilim", "stock": "AKBNK", "tf": "1h",
                   "quality": 82.0, "dir": 1, "entry": 100.0, "atr": 1.0,
                   "bar_time": "2026-09-20 10:00:00+03:00",
                   "kayit_zaman": "2026-09-20T11:00:00+03:00",
                   "stable_id": "sid-1"},
        },
        "formasyon_zamanlari": {},
        "son_karne_gonderim": None,
    }
    dosya.write_text(json.dumps(icerik, ensure_ascii=False), encoding="utf-8")
    once = _dosya_sha(str(dosya))
    defter = KarneDefteri(data_dir=str(tmp_path))
    assert len(defter.kayitlar()) == 1
    assert _dosya_sha(str(dosya)) == once
    # kaydet() AÇIKÇA çağrılmadı -> dosyaya tek bayt bile dokunulmadı.


def test_outcome_link_formasyon_sonucu_readonly(tmp_path, monkeypatch):
    """V1'in outcome okuma yolu: outcome_link.formasyon_sonucu.

    Yazma API'leri patlatılmışken bile temiz dönerse bu fonksiyon salt-okunur
    kanıtlanır; backtest de aynı fonksiyonu çağıracağı için #12/#13/#14 zemini.
    """
    from state import formation_history as fh_mod
    from state import outcome_link

    def patlama(*a, **k):
        raise AssertionError("salt-okunur okuma sırasında YAZMA çağrıldı!")

    monkeypatch.setattr(fh_mod, "kaydet", patlama)
    monkeypatch.setattr(fh_mod, "sonuc_bagla", patlama)
    monkeypatch.setattr(outcome_link, "bagla", patlama)
    monkeypatch.setattr(KarneDefteri, "kaydet", patlama)
    try:
        from state import formation_mirror
        monkeypatch.setattr(formation_mirror, "mirror_kaydet", patlama)
    except Exception:
        pass

    sakli = {"durum": "hedef",
             "outcome": {"durum": "hedef", "mfe_pct": 1.6, "mae_pct": 0.1,
                         "mfe_atr": 1.6, "mae_atr": 0.1, "son_pct": 1.0,
                         "bar_sayisi": 10, "hedef_bar": 3, "stop_bar": None},
             "deneme": 1, "kaynak": "2026-09-20 10:00:00+03:00"}
    yol = _tarih_yaz(tmp_path, sonuc=sakli)
    sha_once = _dosya_sha(yol)
    karne_yol = tmp_path / "karne_defteri.json"
    # Karne'de kırılım satırı VAR ama seri sağlanamıyor -> taze ölçüm
    # 'ölçülemedi' olur ve KAYITLI history.sonuc devreye girer. Bu, V1'in
    # "history.sonuc birincil" kuralının dayandığı mevcut P2.5 semantiğidir.
    karne_yol.write_text(json.dumps({
        "surum": 1,
        "kayitlar": {"AKBNK|1h|K|1": {
            "tip": "kirilim", "stock": "AKBNK", "tf": "1h", "dir": 1,
            "entry": 100.0, "atr": 1.0, "quality": 84.0,
            "bar_time": "2026-09-20 10:00:00+03:00",
            "kayit_zaman": "2026-09-20T11:00:00+03:00",
            "stable_id": "sid-1"}},
        "formasyon_zamanlari": {}, "son_karne_gonderim": None},
        ensure_ascii=False), encoding="utf-8")
    sha_karne = _dosya_sha(str(karne_yol))

    ozet = outcome_link.formasyon_sonucu("sid-1", defter=KarneDefteri(str(tmp_path)),
                                         stock="AKBNK", tf="1h", saglayici=None,
                                         data_dir=str(tmp_path))
    assert ozet is not None
    # saglayici=None -> taze hesap 'ölçülemedi'; KAYITLI sonuç override edilir.
    assert ozet["durum"] == "hedef"
    assert ozet["deneme"] == 1
    assert ozet["outcome"]["mfe_pct"] == 1.6
    assert _dosya_sha(yol) == sha_once
    assert _dosya_sha(str(karne_yol)) == sha_karne


# ---------------------------------------------------------------------------
# 3) KOMUT YÜZEYİ ŞEKLİ (handler implementasyonu BU turda YOK)
# ---------------------------------------------------------------------------

def test_komut_ayirma_backtest_bicimi():
    """/backtest ve argüman biçimi mevcut parser'a oturmalı (owner-only chat zaten var)."""
    assert komut_coz("/backtest 90 detay") == ("backtest", "90 detay")
    assert komut_coz("/backtest") == ("backtest", "")
    assert komut_coz("/backtest@FormationBot 90") == ("backtest", "90")


# ---------------------------------------------------------------------------
# 4) KIRMIZI ÇAPA — implementasyon gelene kadar TEK beklenen kırmızı test
# ---------------------------------------------------------------------------

def test_faz3_v1_modulu_var_mi():
    """analytics/backtest.py (V1) var olmalı.

    Bu test, kapsamın testlerle KİLİTLENDİĞİNİN kanıtıdır: implementasyon
    yapılmadan bu test KASITLI olarak başarısızdır; implementation turunda
    analytics/backtest.py yazılınca yeşile döner.
    """
    try:
        var_mi = importlib.util.find_spec("analytics.backtest") is not None
    except ModuleNotFoundError:
        var_mi = False
    if not var_mi:
        pytest.fail("FAZ 3 V1 implementasyonu bekleniyor: analytics/backtest.py "
                    "henüz yok (test_backtest_v1_spec.py bu modülü bekliyor).")
    import analytics.backtest as bt  # noqa: F401
    for ad in ("topla", "metrikler", "rapor_metni", "komut", "BLOKLAR_TEMEL",
               "BLOKLAR_DETAY", "KALITE_BANTLARI", "NEAR_MISS_MFE_ATR",
               "YETERLI_N", "KISMI_N"):
        assert hasattr(bt, ad), f"analytics.backtest.{ad} eksik (sözleşme ihlali)"
