"""Phase 1 — Kalıcı Formation Identity (stable_id) testleri.

KAPSAM: yalnız identity kalıcılığı. Formation matematiği, geometri, kalite,
pivot seçimi, continuity_score/lifecycle eşikleri ve breakout mantığı burada
DOKUNULMAZ; testler bunları mevcut haliyle kullanır.

Senaryolar:
  A — Formation doğumu        : stable_id boş değil, benzersiz, UUID formatında
  B — Aynı formation devamı   : bar ilerledikçe stable_id değişmez
  C — Restart / re-attach     : yeni motor aynı formation'a eski stable_id'yi bağlar
  D — Yeni formation          : terminal sonrası yeni formation YENİ stable_id alır
  E — Farklı timeframe        : stable_id'ler bağımsız
  F — Farklı stock            : stable_id'ler bağımsız
  G — Eski state uyumluluğu   : stable_id'siz kayıtlar crash ettmeden okunur
  H — Karne uyumluluğu        : eski karne kayıtlarında outcome hesabı çalışır

Çalıştırma:  python3 -m pytest test_stable_identity.py -q
"""

import json
import os
import uuid
from datetime import datetime, timedelta

import pandas as pd
import pytest

import karne as karne_mod
from karne import (DURUM_BEKLIYOR, DURUM_HEDEF, DURUM_NOTR, DURUM_STOP,
                   KarneDefteri, karne_hesapla, sinyal_sonucu)
from live_state import LiveState
from patterns.candidate import PatternCandidate
from patterns.lifecycle import (PatternLifecycleManager, _match_persisted_anchor,
                                _new_stable_id, _parse_stock_tf)
from state import formation_identity as fid


# --- sentetik veri üreticileri (test_pennant.py ile aynı kanal yapısı) ------

def _df_yap(close, start="2026-01-05 09:30", freq="h"):
    return pd.DataFrame(
        {"open": [c - 0.02 for c in close], "high": [c + 0.15 for c in close],
         "low": [c - 0.15 for c in close], "close": close,
         "volume": [3_000_000] * len(close)},
        index=pd.date_range(start=start, periods=len(close), freq=freq,
                            tz="Europe/Istanbul"))


def _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, pole_bars=12,
                     asagi=False, seed=21):
    """Direk + daralan kanal: standart simetrik flama/üçgen geometrisi."""
    import numpy as np
    np.random.seed(seed)
    close = []
    for i in range(n_bars):
        if i <= 4:
            c = 92.0
        elif i == 5:
            c = 90.5 if not asagi else 108.0
        elif i == 6:
            c = 89.2 if not asagi else 118.0
        elif i == 7:
            c = 88.4 if not asagi else 124.0
        elif i == 8:
            c = 88.0 if not asagi else 128.0
        elif i <= 8 + pole_bars:
            adim = (38.0 if not asagi else -40.0) / pole_bars
            c = (88.0 if not asagi else 128.0) + (i - 8) * adim
        else:
            p = i - 8 - pole_bars
            if asagi:
                ul, ll = 95.0 + p * upper_k, 89.0 + p * lower_k
            else:
                ul, ll = 126.0 + p * upper_k, 122.0 + p * lower_k
            pos = p % 8
            c = ul - 0.05 if pos == 6 else (ll + 0.05 if pos == 2 else (ul + ll) * 0.5)
        close.append(c + np.random.randn() * 0.02)
    return _df_yap(close)


def _iki_formasyon(seed1=21, seed2=77):
    """Terminal olan 1. formation + farklı geometrili 2. formation (üst üste)."""
    d1 = _kanalli_pennant(n_bars=48, upper_k=-0.06, lower_k=0.06, seed=seed1)
    d2 = _kanalli_pennant(n_bars=48, upper_k=-0.001, lower_k=0.15, seed=seed2)
    d2 = d2.copy()
    d2.index = d2.index + pd.Timedelta(hours=len(d1))
    return pd.concat([d1, d2])


def _besle(mgr, key, df, baslangic=30):
    """Seriyi bara bara besle (canlı akışın aynısı); son snapshot döner."""
    son = None
    for i in range(baslangic, len(df) + 1):
        son = mgr.scan(key, df.iloc[:i])
    return son


def _dogumlar(mgr, key, df, baslangic=30):
    """Her yeni stable_id'nin doğduğu anları topla: [(bar, stable_id, state)]."""
    gorulen, once = [], None
    for i in range(baslangic, len(df) + 1):
        snap = mgr.scan(key, df.iloc[:i])
        a = snap.active
        if a is not None and a.valid and a.stable_id:
            imza = (a.stable_id, snap.state)
            if imza != once:
                gorulen.append((i, a.stable_id, snap.state))
                once = imza
    return gorulen


def _uuid_mu(deger):
    try:
        return str(uuid.UUID(str(deger))) == str(deger)
    except (ValueError, AttributeError, TypeError):
        return False


# --- yardımcı: doğrulanabilir anchor --------------------------------------

def _anchor_kaydet(stock, tf, stable_id, family="Simetrik Üçgen", classic_dir=1,
                   start_bar=10, **ek):
    veri = {"stable_id": stable_id, "stock": stock, "timeframe": tf,
            "family": family, "classic_dir": classic_dir,
            "pattern_type": "Simetrik Üçgen", "start_bar": start_bar,
            "apex_bar": start_bar + 8,
            "hb1": 2, "hb2": 6, "lb1": 3, "lb2": 7,
            "hp1": 120.0, "hp2": 121.0, "lp1": 110.0, "lp2": 111.0}
    veri.update(ek)
    return fid.save_anchor(veri)


# ===========================================================================
# TEST A — Formation doğumu
# ===========================================================================

def test_a_dogumda_stable_id_atanir_ve_benzersiz():
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    snap = _besle(mgr, "GARAN_1h", df)

    assert snap.active is not None and snap.active.valid, "formasyon oluşmadı"
    assert snap.active.stable_id, "stable_id boş"
    assert _uuid_mu(snap.active.stable_id), "stable_id UUID değil"
    # Motor-içi identity ayrı kavram olarak yaşıyor
    assert snap.active.identity >= 1
    assert snap.active.stable_id != str(snap.active.identity)


def test_a_iki_ayri_formasyon_farkli_stable_id_alir():
    """Farklı (stock,tf): doğan her formation kendi UUID'sini alır."""
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    s1 = _besle(mgr, "GARAN_1h", df)
    s2 = _besle(mgr, "THYAO_4h", df)
    assert s1.active.valid and s2.active.valid
    assert s1.active.stable_id != s2.active.stable_id


def test_a_motor_ici_identity_anlami_degismedi():
    """stable_id eklenince `identity` davranışı bozulmamalı (regresyon)."""
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    snap = _besle(mgr, "GARAN_1h", df)
    eng = mgr.get_engine("GARAN_1h")
    assert eng.next_pattern_identity >= 1
    assert snap.active.identity == eng.next_pattern_identity
    assert snap.active.stable_id


# ===========================================================================
# TEST B — Aynı formation devamı
# ===========================================================================

def test_b_ayni_formation_ilerledikce_stable_id_degismez():
    df = _kanalli_pennant(n_bars=60)
    mgr = PatternLifecycleManager("Dengeli", 0.01)

    ilk = None
    gorulen = set()
    for i in range(30, len(df) + 1):
        snap = mgr.scan("GARAN_1h", df.iloc[:i])
        a = snap.active
        if a is not None and a.valid and a.stable_id:
            if ilk is None:
                ilk = (a.start_bar, a.stable_id)
            gorulen.add(a.stable_id)
            # Aynı start_bar (aynı yapı) -> aynı stable_id
            if (a.start_bar, a.stable_id) == ilk:
                assert a.stable_id == ilk[1]
    assert ilk is not None, "formasyon hiç doğmadı"
    # Tek bir yapı beslendi: tek stable_id
    assert len(gorulen) == 1, f"beklenmeyen ek kimlik: {gorulen}"


def test_b_identity_compatible_guncellemede_stable_id_korunur():
    """Aynı formation'ın identity-compatible güncellemesi kimliği korur."""
    df = _kanalli_pennant(n_bars=56)
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    once = None
    for i in range(30, len(df) + 1):
        snap = mgr.scan("GARAN_1h", df.iloc[:i])
        a = snap.active
        if a is not None and a.valid and a.stable_id:
            if once is None:
                once = a.stable_id
            assert a.stable_id == once
    assert once


# ===========================================================================
# TEST C — Restart / re-attach
# ===========================================================================

def test_c_restart_sonrasi_eski_stable_id_yeniden_baglanir():
    df = _kanalli_pennant()

    mgr1 = PatternLifecycleManager("Dengeli", 0.01)
    s1 = _besle(mgr1, "GARAN_1h", df)
    assert s1.active.valid and s1.active.stable_id
    eski = s1.active.stable_id

    # Anchor gerçekten diske yazıldı mı?
    anchor = fid.load_anchor("GARAN", "1h")
    assert anchor is not None and anchor["stable_id"] == eski

    # --- RESTART: yeni manager + yeni engine (bellek tamamen sıfır) ---
    mgr2 = PatternLifecycleManager("Dengeli", 0.01)
    s2 = _besle(mgr2, "GARAN_1h", df)
    assert s2.active.valid, "restart sonrası formasyon doğmadı"
    assert s2.active.stable_id == eski, (
        f"re-attach başarısız: {s2.active.stable_id} != {eski}")


def test_c_restart_sonrasi_motor_identity_sifirlanir_stable_id_korunur():
    """`identity` restart'ta sıfırlanır (mevcut davranış); stable_id korunur."""
    df = _kanalli_pennant()
    s1 = _besle(PatternLifecycleManager("Dengeli", 0.01), "GARAN_1h", df)
    s2 = _besle(PatternLifecycleManager("Dengeli", 0.01), "GARAN_1h", df)
    assert s1.active.identity == s2.active.identity      # motor identity sıfırlandı
    assert s1.active.stable_id == s2.active.stable_id    # stable_id korundu


def test_c_eslesme_yoksa_yeni_stable_id_uretir():
    """Anchor farklı family -> eşleşme yok -> yeni UUID."""
    df = _kanalli_pennant()
    _anchor_kaydet("GARAN", "1h", "eski-kimlik", family="Bayrak", classic_dir=-1)

    mgr = PatternLifecycleManager("Dengeli", 0.01)
    snap = _besle(mgr, "GARAN_1h", df)
    assert snap.active.valid and snap.active.stable_id
    assert snap.active.stable_id != "eski-kimlik"


def test_c_bilinmeyen_stock_tf_icin_anchor_yok():
    """Anchor'u olmayan (stock,tf): eşleşme denenemez, yeni UUID üretilir."""
    df = _kanalli_pennant()
    _anchor_kaydet("BASKABIRSE", "1d", "baska-kimlik")

    mgr = PatternLifecycleManager("Dengeli", 0.01)
    snap = _besle(mgr, "GARAN_1h", df)
    assert snap.active.valid and snap.active.stable_id != "baska-kimlik"


def test_c_match_persisted_anchor_dogrudan():
    """Yardımcı fonksiyon: uyumlu anchor -> eski kimlik, uyumsuz -> None."""
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    snap = _besle(mgr, "GARAN_1h", df)
    cand = snap.active
    assert cand.valid

    _anchor_kaydet("GARAN", "1h", "anchor-kimlik",
                   family=cand.family, classic_dir=cand.classic_dir,
                   start_bar=cand.start_bar,
                   hb1=cand.hb1, hb2=cand.hb2, lb1=cand.lb1, lb2=cand.lb2,
                   hp1=cand.hp1, hp2=cand.hp2, lp1=cand.lp1, lp2=cand.lp2)
    eng = mgr.get_engine("GARAN_1h")
    assert _match_persisted_anchor(eng, cand) == "anchor-kimlik"

    # Farklı family -> None
    _anchor_kaydet("GARAN", "1h", "diger", family="Bayrak")
    assert _match_persisted_anchor(eng, cand) is None


# ===========================================================================
# TEST D — Yeni formation (terminal sonrası)
# ===========================================================================

def test_d_terminal_sonrasi_yeni_formation_yeni_stable_id_alir():
    """Terminal olan eski formation'ın stable_id'si yeniye TAŞINMAZ."""
    df = _iki_formasyon()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    gorulen = _dogumlar(mgr, "GARAN_1h", df)

    # En az iki ayrı kimlik doğmuş olmalı
    kimlikler = [g[1] for g in gorulen]
    assert len(set(kimlikler)) >= 2, f"yeni formation yeni kimlik almadı: {kimlikler}"

    # İlk doğum terminale ulaşmış olmalı (yoksa senaryo geçersiz)
    durumlar = [g[2] for g in gorulen]
    assert any("GECERSIZ" in d or "TAMAMLANDI" in d or "BASARISIZ" in d
               for d in durumlar), f"terminal durumu görülmedi: {durumlar}"

    # İki doğumun stable_id'leri farklı
    assert gorulen[0][1] != gorulen[-1][1]


def test_d_terminal_sonrasi_anchor_yeni_kimlige_guncellenir():
    """Yeni formation doğunca anchor da yeni stable_id'yi yazar."""
    df = _iki_formasyon()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    gorulen = _dogumlar(mgr, "GARAN_1h", df)
    if len({g[1] for g in gorulen}) < 2:
        pytest.skip("bu veride ikinci formation doğmadı")

    son_kimlik = gorulen[-1][1]
    anchor = fid.load_anchor("GARAN", "1h")
    assert anchor is not None
    assert anchor["stable_id"] == son_kimlik
    # Anchor hâlâ minimum yapıda (kalite/geometri persist edilmiyor)
    assert "quality" not in anchor and "raw_quality" not in anchor
    assert "geometry_score" not in anchor and "current_width" not in anchor
    assert "upper_now" not in anchor and "lower_now" not in anchor
    assert "end_bar" not in anchor and "known_bar" not in anchor


def test_d_terminal_sonrasi_yeni_motorda_tek_kimlik():
    """Restart + iki formation: her biri kendi kimliğini korur."""
    df = _iki_formasyon()
    gorulen = _dogumlar(PatternLifecycleManager("Dengeli", 0.01), "GARAN_1h", df)
    if len({g[1] for g in gorulen}) < 2:
        pytest.skip("bu veride ikinci formation doğmadı")
    # İkinci doğumun stable_id'i ilkinkinden farklı
    assert gorulen[0][1] != gorulen[-1][1]


# ===========================================================================
# TEST E — Farklı timeframe
# ===========================================================================

def test_e_ayni_stock_farkli_timeframe_bagimsiz():
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    s1 = _besle(mgr, "GARAN_1h", df)
    s2 = _besle(mgr, "GARAN_4h", df)
    assert s1.active.valid and s2.active.valid
    assert s1.active.stable_id != s2.active.stable_id

    a1 = fid.load_anchor("GARAN", "1h")
    a4 = fid.load_anchor("GARAN", "4h")
    assert a1["stable_id"] != a4["stable_id"]
    assert a1["timeframe"] == "1h" and a4["timeframe"] == "4h"


def test_e_timeframe_anahtari_ayristiriliyor():
    assert _parse_stock_tf("GARAN_1h") == ("GARAN", "1h")
    assert _parse_stock_tf("THYAO_4h") == ("THYAO", "4h")
    assert _parse_stock_tf("ASELS_1d") == ("ASELS", "1d")


def test_e_timeframe_restart_re_attach_karisiyor_mu():
    """1h anchor'u 4h motorunu etkilememeli."""
    df = _kanalli_pennant()
    mgr1 = PatternLifecycleManager("Dengeli", 0.01)
    s1 = _besle(mgr1, "GARAN_1h", df)
    mgr2 = PatternLifecycleManager("Dengeli", 0.01)
    s4 = _besle(mgr2, "GARAN_4h", df)
    assert s1.active.stable_id != s4.active.stable_id


# ===========================================================================
# TEST F — Farklı stock
# ===========================================================================

def test_f_farkli_stock_bagimsiz():
    df = _kanalli_pennant()
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    s1 = _besle(mgr, "GARAN_1h", df)
    s2 = _besle(mgr, "THYAO_1h", df)
    assert s1.active.valid and s2.active.valid
    assert s1.active.stable_id != s2.active.stable_id

    a1 = fid.load_anchor("GARAN", "1h")
    a2 = fid.load_anchor("THYAO", "1h")
    assert a1["stock"] == "GARAN" and a2["stock"] == "THYAO"
    assert a1["stable_id"] != a2["stable_id"]


def test_f_stock_restart_re_attach_karisiyor_mu():
    df = _kanalli_pennant()
    s1 = _besle(PatternLifecycleManager("Dengeli", 0.01), "GARAN_1h", df)
    s2 = _besle(PatternLifecycleManager("Dengeli", 0.01), "THYAO_1h", df)
    assert s1.active.stable_id != s2.active.stable_id


# ===========================================================================
# TEST G — Eski state compatibility
# ===========================================================================

def test_g_live_state_stable_idsiz_kayit_okunur(tmp_path, monkeypatch):
    """stable_id içermeyen eski son_tarama kaydı: crash yok, anahtar dolar."""
    eski = {
        "surum": 1,
        "kayit_zamani": datetime.now().isoformat(),
        "status": {"son_tarama_durumu": "tamamlandi"},
        "formations": [
            {"stock": "GARAN", "timeframe": "1h", "pattern_name": "Simetrik Üçgen",
             "quality": 87.0, "state": "KIRILIM_TEYITLI"},
            {"stock": "THYAO", "timeframe": "4h", "pattern_name": "Bayrak",
             "quality": 71.0, "state": "SIKISMA_GUCLENIYOR"},
        ],
    }
    durum = LiveState()
    assert durum.hydrate(eski) == 2          # eski kayıt okunabildi

    kayitlar = durum.formations()
    assert len(kayitlar) == 2
    for k in kayitlar:
        # Eski kayıtta anahtar hiç yok; okuyan taraf .get() ile None alır
        assert k.get("stable_id") is None
        assert "stable_id" not in k          # hydrate alan EKLEMEZ (sözleşme)
    # Sıralama/snapshot da çalışmaya devam eder
    assert len(durum.snapshot()["formations"]) == 2
    assert durum.status()["son_tarama_durumu"] == "tamamlandi"
    # Kayıt birebir geri yüklenir (alan kümesi değişmez)
    assert set(kayitlar[0]) == set(eski["formations"][0])


def test_g_live_state_karisik_kayit(tmp_path):
    """stable_id'li yeni kayıt + stable_id'siz eski kayıt birlikte okunur."""
    veri = {
        "surum": 1,
        "kayit_zamani": datetime.now().isoformat(),
        "status": {},
        "formations": [
            {"stock": "GARAN", "timeframe": "1h", "quality": 90.0,
             "stable_id": "yeni-kimlik"},
            {"stock": "THYAO", "timeframe": "1h", "quality": 80.0},
        ],
    }
    durum = LiveState()
    assert durum.hydrate(veri) == 2
    eslesen = {k["stock"]: k.get("stable_id") for k in durum.formations()}
    assert eslesen["GARAN"] == "yeni-kimlik"
    assert eslesen["THYAO"] is None


def test_g_formation_identity_dosya_yok():
    """Anchor dosyası hiç yoksa eşleşme denenemez (None)."""
    assert fid.load_anchor("GARAN", "1h") is None


def test_g_formation_identity_bozuk_dosya(tmp_path, monkeypatch):
    """Bozuk/okunamaz anchor dosyası botu durdurmaz."""
    hedef = tmp_path / "formation_identity.json"
    hedef.write_text("{bozuk json", encoding="utf-8")
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path), raising=False)

    assert fid.load_anchor("GARAN", "1h") is None      # çökmez, None döner
    assert fid.save_anchor({"stock": "GARAN", "timeframe": "1h",
                            "stable_id": "x"}) is True  # üzerine yazabilir
    assert fid.load_anchor("GARAN", "1h")["stable_id"] == "x"


def test_g_eksik_alanli_anchor_reddedilir():
    """Zorunlu alanları eksik anchor yazılmaz (kimlik taşınmaz)."""
    assert fid.save_anchor({"stable_id": "x", "stock": "GARAN"}) is False
    assert fid.save_anchor({"stock": "GARAN", "timeframe": "1h"}) is False
    assert fid.save_anchor({"stable_id": "x", "timeframe": "1h"}) is False
    assert fid.save_anchor({}) is False


def test_g_match_persisted_anchor_bozuk_anchor(tmp_path, monkeypatch):
    """start_bar/family'siz anchor -> eşleşme denenemez (None), crash yok."""
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path), raising=False)
    fid.save_anchor({"stable_id": "eksik", "stock": "GARAN", "timeframe": "1h",
                     "family": None, "start_bar": None})

    mgr = PatternLifecycleManager("Dengeli", 0.01)
    eng = mgr.get_engine("GARAN_1h")
    cand = PatternCandidate()
    cand.valid = True
    cand.family = "Simetrik Üçgen"
    cand.classic_dir = 1
    cand.start_bar = 10
    assert _match_persisted_anchor(eng, cand) is None


def test_g_yeni_stable_id_urunultusu():
    assert _uuid_mu(_new_stable_id())
    assert _new_stable_id() != _new_stable_id()


def test_g_motor_keyi_yoksa_eslesme_yok():
    """Anahtarsız motor (manager dışı kullanım) güvenle None döner."""
    from patterns.lifecycle import ArgentEngine
    eng = ArgentEngine("Dengeli", 0.01)
    assert eng._key is None
    cand = PatternCandidate()
    cand.valid = True
    assert _match_persisted_anchor(eng, cand) is None


# ===========================================================================
# TEST H — Karne compatibility
# ===========================================================================

def _kirilim_kaydi(stable_id="kimlik-1", **ek):
    taban = {
        "tip": "kirilim", "stock": "GARAN", "tf": "1h",
        "pattern": "Simetrik Üçgen", "state": "KIRILIM_TEYITLI",
        "dir": 1, "entry": 100.0, "atr": 2.0, "quality": 85.0,
        "mtf_destek": True, "bar_time": "2026-01-10T10:00:00+03:00",
        "kayit_zaman": "2026-01-10T10:30:00+03:00", "hafta": "2026-W02",
    }
    taban.update(ek)
    return taban


def _seri(bar_sayisi=20, yon=1):
    """Kırılım sonrası seri: lehte/alehte hareket üretsin."""
    idx = pd.date_range("2026-01-10 09:00", periods=bar_sayisi, freq="h",
                        tz="Europe/Istanbul")
    fiyat = [100.0]
    for i in range(1, bar_sayisi):
        fiyat.append(fiyat[-1] + yon * (0.9 if i % 3 else -0.4))
    return pd.DataFrame(
        {"open": [p - 0.1 for p in fiyat], "high": [p + 0.6 for p in fiyat],
         "low": [p - 0.6 for p in fiyat], "close": fiyat,
         "volume": [1_000_000] * bar_sayisi}, index=idx)


def test_h_eski_karne_kaydi_outcome_hesabi_calisiyor():
    """stable_id İÇERMEYEN eski kırılım kaydı: outcome hesabı çalışır."""
    kayit = _kirilim_kaydi()           # stable_id alanı hiç yok
    assert "stable_id" not in kayit

    df = _seri(yon=1)
    sonuc = sinyal_sonucu(kayit, df)
    assert sonuc is not None
    assert sonuc["durum"] in (DURUM_HEDEF, DURUM_STOP, DURUM_NOTR, DURUM_BEKLIYOR)
    assert sonuc["bar_sayisi"] > 0
    # MFE/MAE ve ATR normalize değerleri üretiliyor
    assert sonuc["mfe_pct"] is not None and sonuc["mae_pct"] is not None
    assert sonuc["mfe_atr"] is not None and sonuc["mae_atr"] is not None


def test_h_eski_karne_kaydi_karne_hesapla_calisiyor():
    """Eski kayıtlarla karne_hesapla (haftalık accuracy) çalışır."""
    kayitlar = [_kirilim_kaydi(), _kirilim_kaydi(stock="THYAO", dir=-1)]
    for k in kayitlar:
        k.pop("stable_id", None)

    def saglayici(stock, tf):
        return _seri(yon=1)

    metrik = karne_hesapla(kayitlar, saglayici)
    assert isinstance(metrik, dict)
    # Eski kayıtlar kırılım olarak değerlendirildi (outcome üretildi)
    assert metrik["kirilim_toplam"] == 2
    assert metrik["degerlendirilen"] + metrik["bekleyen"] >= 1
    # MFE/MAE ve ATR normalize ortalamalar üretiliyor
    assert metrik["ort_mfe_atr"] is not None
    assert metrik["kayit_sayisi"] == 2


def test_h_karne_kayit_stable_id_tasir(tmp_path, monkeypatch):
    """Yeni kayıtlarda stable_id yazılır ve geri okunur."""
    monkeypatch.setattr("config.DATA_DIR", str(tmp_path), raising=False)
    defter = KarneDefteri(data_dir=str(tmp_path))
    bar = datetime(2026, 1, 10, 10, 0)

    assert defter.kirilim_kaydet("GARAN", "1h", "Simetrik Üçgen",
                                 "KIRILIM_TEYITLI", 1, 100.0, 2.0, 85.0, bar,
                                 stable_id="kimlik-kirilim")
    assert defter.formasyon_kaydet("GARAN", "1h", "Simetrik Üçgen",
                                   "FORMASYON_TANIMLANDI", 85.0, bar,
                                   stable_id="kimlik-formasyon")
    assert defter.olay_kaydet("GARAN", "1h", "RETEST_BASARILI", bar,
                              stable_id="kimlik-olay")

    kayitlar = {k["tip"]: k for k in defter.kayitlar()}
    assert kayitlar["kirilim"]["stable_id"] == "kimlik-kirilim"
    assert kayitlar["formasyon"]["stable_id"] == "kimlik-formasyon"
    assert kayitlar["olay"]["stable_id"] == "kimlik-olay"


def test_h_karne_stable_id_parametresi_opsiyonel():
    """stable_id verilmezse kayıt yine oluşur (eski çağrı imzası bozulmaz)."""
    defter = KarneDefteri(data_dir="/tmp/fid-test-karne-opsiyonel")
    bar = datetime(2026, 1, 10, 10, 0)
    try:
        assert defter.olay_kaydet("GARAN", "1h", "FORMASYON_TAMAMLANDI", bar)
        assert defter.kirilim_kaydet("GARAN", "1h", "X", "KIRILIM_TEYITLI",
                                     1, 100.0, 2.0, 85.0, bar)
        for k in defter.kayitlar():
            assert k["stable_id"] is None
    finally:
        for p in (defter.dosya, defter.dosya + ".tmp"):
            try:
                os.remove(p)
            except OSError:
                pass


def test_h_karne_eski_dosya_yuklenir(tmp_path):
    """stable_id'siz eski karne defteri dosyası yüklenebilir."""
    eski = {
        "surum": 1,
        "kayitlar": {
            "GARAN|1h|K|2026-01-10T10:00:00+03:00": {
                "tip": "kirilim", "stock": "GARAN", "tf": "1h",
                "pattern": "Simetrik Üçgen", "dir": 1, "entry": 100.0,
                "atr": 2.0, "quality": 85.0,
                "bar_time": "2026-01-10T10:00:00+03:00",
                "kayit_zaman": "2026-01-10T10:30:00+03:00", "hafta": "2026-W02",
            },
        },
        "formasyon_zamanlari": {},
        "son_karne_gonderim": None,
    }
    yol = tmp_path / "karne_defteri.json"
    yol.write_text(json.dumps(eski), encoding="utf-8")

    defter = KarneDefteri(data_dir=str(tmp_path))
    assert defter.boyut() == 1
    kayit = defter.kayitlar()[0]
    assert kayit.get("stable_id") is None        # eski kayıtta anahtar yok

    # Eski kayıt outcome'a girebiliyor
    sonuc = sinyal_sonucu(kayit, _seri(yon=1))
    assert sonuc is not None and sonuc["durum"] in (
        DURUM_HEDEF, DURUM_STOP, DURUM_NOTR, DURUM_BEKLIYOR)


def test_h_karne_stable_id_outcome_hesabini_etkilemez():
    """Aynı kaydın stable_id'li/stable_id'siz hâli AYNI outcome üretir."""
    df = _seri(yon=1)
    eski = _kirilim_kaydi()
    yeni = _kirilim_kaydi(stable_id="kimlik-1")

    assert "stable_id" not in eski
    assert sinyal_sonucu(eski, df) == sinyal_sonucu(yeni, df)


# ===========================================================================
# Regresyon: mevcut davranış korunuyor
# ===========================================================================

def test_regresyon_identity_alanlari_ayri():
    """`identity` (int, motor içi) ve `stable_id` (str, kalıcı) ayrı alanlar."""
    c = PatternCandidate()
    assert c.identity == 0 and isinstance(c.identity, int)
    assert c.stable_id is None
    c.identity = 7
    c.stable_id = "abc"
    assert c.identity == 7 and c.stable_id == "abc"
    assert c.identity != c.stable_id


def test_regresyon_manager_key_tasiyor():
    mgr = PatternLifecycleManager("Dengeli", 0.01)
    eng = mgr.get_engine("GARAN_1h")
    assert eng._key == "GARAN_1h"
    assert mgr.get_engine("GARAN_1h") is eng        # aynı motor korunur


def test_regresyon_karne_surumu_degismedi():
    """Karne kayıt şeması/sürümü bilinçli olarak değiştirilmedi."""
    assert karne_mod.KARNE_SURUM == 1


def test_regresyon_outcome_sabitleri_degismedi():
    """Outcome eşikleri (hedef/stop/horizon) Phase 1'de değiştirilmedi."""
    assert karne_mod.KARNE_HEDEF_ATR == 1.5
    assert karne_mod.KARNE_STOP_ATR == 1.0
    assert karne_mod.KARNE_HORIZON_BAR == 10
