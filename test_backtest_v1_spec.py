"""FAZ 3 — Backtest V1 DAVRANIŞ SPESİFİKASYONU (regression kilidi).

Bu testler `analytics/backtest.py` (henüz yok) üzerinde FAZ 3 V1 kapsamını
kilitler. Modül import edilemediği sürece dosyanın tamamı ATLANIR
(importorskip); implementasyon turunda otomatik devreye girer ve sözleşmeyi
zorlar. Sözleşme kaynağı: FAZ3_BACKTEST_VERI_ANALIZI.md §5.

Kilitlenen kurallar (kullanıcı onayı, 2026-10-04):
  * Salt-okunur: history/karne/Supabase-aynasına TEK BAYT yazılmaz (#12/#13/#14).
  * history.sonuc (native-TF outcome) BİRİNCİL outcome kaynağıdır; Karne satırları
    yalnız `kirilim_var_mi` çapraz kontrolüdür.
  * /backtest, /backtest <gün>, /backtest <gün> detay — tek kapı `komut()`.
  * Bozuk dosya/kayıt raporu düşürmez (#16).
  * Her anlamlı istatistik n ile gelir; n-gate altı "betimleyici" etiketlidir
    (#17/#18); YETERLI_N=30, KISMI_N=15.
  * Scoring/threshold değişikliği yok — statik AST bekçisiyle de kilitli (#19).
  * Deterministik tekrar (#15).

ML / otomatik optimizasyon / scoring değişikliği / MTF / XU100 / breadth /
grafik / gerçek replay-backfill KASITLI olarak test edilmez — V1 kapsamı dışıdır.

API SÖZLEŞMESİ (implementasyon buna uyar):
  topla(data_dir=None, gun=None, simdi=None, store=None) -> corpus dict
      corpus = {"kayitlar": [rec...], "uyarilar": [str...], "bozuk_dosya": int,
                "slot": int, "dosya": int, "tarih_araligi": (min,max)|None,
                "kaynak": "local", "pencere": "son N gün"|None}
      rec = {"stable_id","stock","tf","pattern_type","family","classic_dir",
             "dogum_quality","kirilim_quality","durum","terminal_state",
             "sonuc","kirilim_var_mi","components","breakout","events",
             "dogum_bar_time"}   # sonuc = history kaydedilmiş sözlük | None
      Sıralama: (stock, tf, stable_id) artan — determinizm.
  metrikler(corpus) -> {"genel","tip","aile","tf","kalite","bilesim","huni",
                        "vaka","kapsayici"}
  rapor_metni(metrik, detay=False) -> str ; komut(arguman, *, data_dir, simdi,
                        store=None) -> str
  Sabitler: BLOKLAR_TEMEL, BLOKLAR_DETAY, KALITE_BANTLARI, NEAR_MISS_MFE_ATR,
            YETERLI_N, KISMI_N
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from state import formation_history as fh

bt = pytest.importorskip(
    "analytics.backtest",
    reason="FAZ 3 V1 implementasyonu bekleniyor (analytics/backtest.py)",
)

IST = ZoneInfo("Europe/Istanbul")
SIMDI = datetime(2026, 10, 4, 12, 0, tzinfo=IST)

# --- Sözleşme anahtarları (yukarıdaki docstring ile birebir) ---------------
REC_KEYS = {"stable_id", "stock", "tf", "pattern_type", "family", "classic_dir",
            "dogum_quality", "kirilim_quality", "durum", "terminal_state",
            "sonuc", "kirilim_var_mi", "components", "breakout", "events",
            "dogum_bar_time"}
CORPUS_KEYS = {"kayitlar", "uyarilar", "bozuk_dosya", "slot", "dosya",
               "tarih_araligi", "kaynak", "pencere"}
METRIK_KEYS = {"genel", "tip", "aile", "tf", "kalite", "bilesim", "huni",
               "vaka", "kapsayici"}
BILESIM_SKORLARI = {"geometry_score", "slope_shape_score", "touch_score",
                    "contraction_score", "maturity_score"}
TEMEL_TOKENS = ("KAPSAYICILIK", "GENEL", "TİP", "TIMEFRAME", "KALİTE",
                "HUNİ", "NOTLAR")
DETAY_TOKENS = ("BİLEŞEN", "GEOMETRİ", "VAKA")
# NOTLAR bir okuma/uyarı bloğudur; ölçüm üreten blokların HEPSİ n taşımak zorunda:
N_ILE_GELMELI = ("KAPSAYICILIK", "GENEL", "TİP", "TIMEFRAME", "KALİTE", "HUNİ")
OUTCOME_ALANLARI = {"mfe_pct", "mae_pct", "mfe_atr", "mae_atr", "son_pct",
                    "hedef_bar", "stop_bar"}


# ---------------------------------------------------------------------------
# Fixture yardımcıları
# ---------------------------------------------------------------------------

def _yaz(path, veri):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False)
    return str(path)


def _geo_snap(bz, sid, *, state="KIRILIM_TEYITLI", **alanlar):
    taban = {"upper_now": 101.0, "lower_now": 100.0, "current_width": 1.0,
             "contraction": 0.45, "progress": 0.8, "upper_touches": 3,
             "lower_touches": 3, "violation": 0.1, "raw_quality": 80.0,
             "geometry_score": 70.0, "slope_shape_score": 65.0,
             "touch_score": 60.0, "contraction_score": 55.0,
             "maturity_score": 50.0, "correction_depth": None,
             "duration_ratio": None, "consolidation_efficiency": None,
             "consolidation_height_ratio": None}
    taban.update(alanlar)
    return {"tur": "geometri", "bar_time": bz, "state": state,
            "stable_id": sid, "alanlar": taban}


def _kir_snap(bz, sid, *, frozen_q=84.0, direction=1, **alanlar):
    taban = {"quality_frozen": True, "frozen_raw_quality": frozen_q,
             "frozen_atr_at_break": 1.2, "frozen_break_buffer": 0.3,
             "frozen_retest_tolerance": 0.5, "frozen_classic_dir": 0,
             "frozen_pattern_type": "Simetrik Üçgen",
             "break_snapshot_bar": 12, "break_snapshot_price": 101.0,
             "break_snapshot_direction": direction,
             "break_snapshot_quality": frozen_q, "break_strength": 61.0,
             "break_body_score": 70.0, "break_close_score": 66.0,
             "break_penetration_score": 58.0, "break_expansion_score": 60.0,
             "break_volume_score": None, "break_confirmation_strength": 70.0}
    taban.update(alanlar)
    return {"tur": "kirilim", "bar_time": bz, "state": "KIRILIM_TEYITLI",
            "stable_id": sid, "alanlar": taban}


def _olay(tip, bz, sid, direction=0, quality=None, state="KIRILIM_TEYITLI"):
    return {"type": tip, "name": tip, "direction": direction,
            "quality": quality, "price": 100.5, "bar": 12, "time": bz,
            "state": state, "stable_id": sid}


def _ham_kayit(sid, *, durum="terminal", terminal_state="FORMASYON_TAMAMLANDI",
               pattern="Simetrik Üçgen", family="Üçgen", classic_dir=0,
               dogum_q=78.0, dogum_bt="2026-09-20 10:00:00+03:00",
               sonuc=None, olaylar=None, snapshotlar=None):
    return {
        "stable_id": sid, "durum": durum, "terminal_state": terminal_state,
        "ilk_gorulme": "2026-09-20T09:00:00+03:00",
        "son_gorulme": "2026-09-20T18:00:00+03:00",
        "dogum": {"bar_time": dogum_bt, "bar_index": 5, "alanlar": {
            "stable_id": sid, "pattern_type": pattern, "family": family,
            "classic_dir": classic_dir, "raw_quality": dogum_q,
            "geometry_atr": 2.0, "has_pole": False, "pole_quality": 0.0}},
        "olaylar": list(olaylar or []),
        "snapshotlar": list(snapshotlar or []),
        "sonuc": sonuc,
    }


def _tarih_dosyasi(tmp_path, stock, tf, kayitlar):
    return _yaz(fh.yol(stock, tf, str(tmp_path)),
                {"surum": 1, "stock": stock, "timeframe": tf,
                 "guncellendi": None, "kayitlar": kayitlar})


def _karne_yaz(tmp_path, satirlar):
    kayitlar = {f"{s['stock']}|{s['tf']}|K|{i}": s for i, s in enumerate(satirlar)}
    return _yaz(tmp_path / "karne_defteri.json",
                {"surum": 1, "kayitlar": kayitlar,
                 "formasyon_zamanlari": {}, "son_karne_gonderim": None})


def _sonuc(durum="hedef", *, mfe_pct=1.5, mae_pct=0.5, mfe_atr=1.5,
           mae_atr=0.5, son_pct=1.0, hedef_bar=2, stop_bar=None, deneme=1,
           kaynak="2026-09-20 12:00:00+03:00"):
    return {"durum": durum,
            "outcome": {"durum": durum, "mfe_pct": mfe_pct, "mae_pct": mae_pct,
                        "mfe_atr": mfe_atr, "mae_atr": mae_atr,
                        "son_pct": son_pct, "bar_sayisi": 10,
                        "hedef_bar": hedef_bar, "stop_bar": stop_bar},
            "deneme": deneme, "kaynak": kaynak}


_KIRILIM_IZI = {"BREAK_CANDIDATE", "COUNTER_BREAK", "BREAK_CONFIRMED",
                "TIMEOUT", "BREAK_FAILED", "RETEST_OK"}


def _rec(sid="s1", durum="hedef", **kw):
    """metrikler birim testleri için backtest-kayıt sözlüğü (topla çıktısı biçimi).

    `durum`= kaydedilmiş sonuc.un durum'u; durum=None → sonuc yok.
    Olay/kırılım izi türetimi: kirilim_var_mi yoksa events/sonuc'tan hesaplanır.
    """
    okw = {k: kw.pop(k) for k in list(kw) if k in OUTCOME_ALANLARI}
    deneme = kw.pop("deneme", 1)
    kirilim_var_mi = kw.pop("kirilim_var_mi", None)
    events = kw.pop("events", None)
    sonuc = _sonuc(durum, deneme=deneme, **okw) if durum else None
    if kirilim_var_mi is None:
        kirilim_var_mi = bool(set(events or []) & _KIRILIM_IZI) or (sonuc is not None)
    if events is None:
        events = ["BREAK_CONFIRMED"] if kirilim_var_mi else []
    r = {"stable_id": sid,
         "stock": kw.pop("stock", "AKBNK"),
         "tf": kw.pop("tf", "1h"),
         "pattern_type": kw.pop("pattern_type", "Simetrik Üçgen"),
         "family": kw.pop("family", "Üçgen"),
         "classic_dir": kw.pop("classic_dir", 0),
         "dogum_quality": kw.pop("dogum_q", 78.0),
         "kirilim_quality": kw.pop("kirilim_q", None),
         "durum": kw.pop("kayit_durum", "terminal"),
         "terminal_state": kw.pop("terminal_state", "FORMASYON_TAMAMLANDI"),
         "sonuc": sonuc, "kirilim_var_mi": bool(kirilim_var_mi),
         "components": kw.pop("components", {}),
         "breakout": kw.pop("breakout", {}),
         "events": list(events),
         "dogum_bar_time": kw.pop("dogum_bt", "2026-09-20 10:00:00+03:00")}
    assert not kw, f"beklenmeyen anahtarlar: {sorted(kw)}"
    return r


def _korpus(kayitlar, **ek):
    corpus = {"kayitlar": list(kayitlar), "uyarilar": [], "bozuk_dosya": 0,
              "slot": 1, "dosya": 1, "tarih_araligi": None, "kaynak": "local",
              "pencere": None}
    corpus.update(ek)
    return corpus


def _metrik(kayitlar, **ek):
    return bt.metrikler(_korpus(kayitlar, **ek))


# ---------------------------------------------------------------------------
# topla(): dosya → corpus eşlemesi ve toleranslar
# ---------------------------------------------------------------------------

def test_topla_korpus_anahtarlari(tmp_path):
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {"s1": _ham_kayit("s1", sonuc=_sonuc())})
    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    assert CORPUS_KEYS <= set(korpus)
    assert korpus["kaynak"] == "local"
    assert isinstance(korpus["uyarilar"], list)


def test_bos_klasor_crash_yok(tmp_path):
    """#1: boş history corpus → açıklayıcı boş sonuç, çökme yok."""
    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    assert korpus["kayitlar"] == []
    assert korpus["bozuk_dosya"] == 0
    metrik = bt.metrikler(korpus)
    assert metrik["genel"]["n"] == 0
    rapor = bt.rapor_metni(metrik)
    assert "veri yok" in rapor


def test_topla_tek_formation_alan_eslemesi(tmp_path):
    """#2: tek formation — tüm alanlar doğru kaynaktan eşlenir."""
    bk = "2026-09-20 12:00:00+03:00"
    rec = _ham_kayit("sid-1", dogum_q=78.0, sonuc=_sonuc("hedef"),
                     snapshotlar=[_geo_snap(bk, "sid-1", geometry_score=95.0,
                                            touch_score=60.0),
                                  _kir_snap(bk, "sid-1", frozen_q=84.0)],
                     olaylar=[_olay("NEW_PATTERN", "2026-09-20 10:00:00+03:00", "sid-1"),
                              _olay("BREAK_CONFIRMED", bk, "sid-1", direction=1),
                              _olay("RETEST_OK", bk, "sid-1", direction=1)])
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {"sid-1": rec})

    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    assert len(korpus["kayitlar"]) == 1
    r = korpus["kayitlar"][0]
    assert REC_KEYS <= set(r)
    assert r["stable_id"] == "sid-1" and r["stock"] == "AKBNK" and r["tf"] == "1h"
    assert r["pattern_type"] == "Simetrik Üçgen" and r["family"] == "Üçgen"
    assert r["dogum_quality"] == 78.0
    assert r["kirilim_quality"] == 84.0          # frozen_raw_quality
    assert r["durum"] == "terminal" and r["terminal_state"] == "FORMASYON_TAMAMLANDI"
    assert r["sonuc"]["durum"] == "hedef"        # history.sonuc BİRİNCİL kaynak
    assert r["sonuc"]["outcome"]["mfe_pct"] == 1.5
    assert r["kirilim_var_mi"] is True
    assert r["events"] == ["NEW_PATTERN", "BREAK_CONFIRMED", "RETEST_OK"]
    # geometri+kirilim AYNI bar_time → bileşen vektörü kırılım barından:
    assert r["components"]["geometry_score"] == 95.0
    assert r["components"]["touch_score"] == 60.0
    assert r["breakout"]["break_strength"] == 61.0


def test_eslesmeyen_vektor_components_bos(tmp_path):
    """kirilim snapshot'ı var ama aynı bar_time'da geometri YOK → components {}."""
    rec = _ham_kayit("sid-1",
                     snapshotlar=[_kir_snap("2026-09-20 12:00:00+03:00", "sid-1")],
                     olaylar=[_olay("BREAK_CONFIRMED", "2026-09-20 12:00:00+03:00",
                                    "sid-1")])
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {"sid-1": rec})
    r = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)["kayitlar"][0]
    assert r["components"] == {}
    assert r["kirilim_quality"] == 84.0


def test_karne_kirilim_satiri_kirilim_var_mi_yapilir(tmp_path):
    """Karne `kirilim` satırı çapraz kontrol: history'de iz yoksa kirilim_var_mi
    True olur; outcome yine history'den gelir (yoksa ölçülememiş sayılır)."""
    rec = _ham_kayit("sid-k", olaylar=[_olay("NEW_PATTERN", "2026-09-20 10:00:00+03:00",
                                             "sid-k")], sonuc=None)
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {"sid-k": rec})
    _karne_yaz(tmp_path, [{"tip": "kirilim", "stock": "AKBNK", "tf": "1h",
                           "quality": 82.0, "dir": 1, "entry": 100.0, "atr": 1.0,
                           "bar_time": "2026-09-20 15:00:00+03:00",
                           "kayit_zaman": "2026-09-20T16:00:00+03:00",
                           "stable_id": "sid-k"}])
    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    r = korpus["kayitlar"][0]
    assert r["kirilim_var_mi"] is True
    assert r["sonuc"] is None
    m = bt.metrikler(korpus)
    assert m["genel"]["olcumemis"] == 1
    assert m["genel"]["degerlendirilen"] == 0


def test_topla_bozuk_dosya_ve_bozuk_kayit_tolere(tmp_path):
    """#16: bir bozuk dosya/kayıt tüm raporu düşürmez; sağlam kayıtlar gelir."""
    _tarih_dosyasi(tmp_path, "AKBNK", "1h",
                   {"s1": _ham_kayit("s1", sonuc=_sonuc("hedef"))})
    bozuk_yol = fh.yol("BOZUK", "1h", str(tmp_path))
    os.makedirs(os.path.dirname(bozuk_yol), exist_ok=True)
    with open(bozuk_yol, "w", encoding="utf-8") as f:
        f.write("{{{ bozuk json")
    _tarih_dosyasi(tmp_path, "GARAN", "1h",
                   {"s2": _ham_kayit("s2", sonuc=_sonuc("stop", son_pct=-1.2,
                                                         mfe_pct=0.2, mae_pct=1.1)),
                    "gecersiz-kayit": 12345})   # dict olmayan kayıt (defter filtresi)

    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    assert korpus["bozuk_dosya"] == 1
    assert {r["stable_id"] for r in korpus["kayitlar"]} == {"s1", "s2"}
    m = bt.metrikler(korpus)
    assert m["genel"]["hedef"] == 1 and m["genel"]["stop"] == 1


def test_gun_filtresi(tmp_path):
    """#10: /backtest 90 — simdi-90g sınırı DÂHİL, öncesi hariç; bar_time'sız korunur."""
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {
        "eski": _ham_kayit("eski", dogum_bt="2026-07-05 10:00:00+03:00"),
        "sinir": _ham_kayit("sinir", dogum_bt="2026-07-06 12:00:00+03:00"),
        "yeni": _ham_kayit("yeni", dogum_bt="2026-09-20 10:00:00+03:00"),
    })
    _tarih_dosyasi(tmp_path, "GARAN", "1h", {"zamani-yok": _ham_kayit("zamani-yok",
                                                                       dogum_bt=None)})
    k90 = bt.topla(data_dir=str(tmp_path), gun=90, simdi=SIMDI)
    sids = {r["stable_id"] for r in k90["kayitlar"]}
    assert sids == {"sinir", "yeni", "zamani-yok"}
    ktum = bt.topla(data_dir=str(tmp_path), gun=None, simdi=SIMDI)
    assert {r["stable_id"] for r in ktum["kayitlar"]} == sids | {"eski"}
    assert k90["pencere"] and "90" in str(k90["pencere"])


# ---------------------------------------------------------------------------
# metrikler(): hesaplama sözleşmesi
# ---------------------------------------------------------------------------

def test_metrikler_bos_korpus():
    m = _metrik([])
    assert METRIK_KEYS <= set(m)
    assert m["genel"]["n"] == 0 and m["genel"]["degerlendirilen"] == 0
    assert m["genel"]["hedef_orani"] is None
    assert m["genel"]["med_son_pct"] is None
    assert m["genel"]["yorum"] == "betimleyici"


def test_metrikler_tek_formation_hedef():
    """#2 (metrik seviyesi): tek formation → doğru outcome sayaçları."""
    m = _metrik([_rec("only-1", durum="hedef")])
    g = m["genel"]
    assert g["n"] == 1 and g["degerlendirilen"] == 1
    assert g["hedef"] == 1 and g["stop"] == 0 and g["notr"] == 0
    assert g["hedef_orani"] == 1.0
    assert g["med_son_pct"] == 1.0
    assert g["med_mfe_pct"] == 1.5 and g["med_mae_pct"] == 0.5
    assert g["med_mfe_atr"] == 1.5 and g["med_mae_atr"] == 0.5
    assert g["med_hedef_bar"] == 2 and g["med_stop_bar"] is None
    assert m["vaka"]["en_iyi"][0]["stable_id"] == "only-1"
    assert m["kapsayici"]["kayit"] == 1


def test_metrikler_siniflandirma():
    """bekliyor/ölçülememiş/kırılımsız/devam kutuları ayrı; paydaya girmez."""
    recs = [
        _rec("a", durum="bekliyor"),
        _rec("b", durum=None, kirilim_var_mi=True),                 # ölçülememiş
        _rec("c", durum=None, kirilim_var_mi=False),                # kırılımsız terminal
        _rec("d", durum=None, kirilim_var_mi=False, kayit_durum="acik",
             terminal_state=None),                                   # devam eden
    ]
    g = _metrik(recs)["genel"]
    assert g["n"] == 4
    assert g["bekliyor"] == 1 and g["olcumemis"] == 1
    assert g["kirilimsiz"] == 1 and g["devam"] == 1
    assert g["degerlendirilen"] == 0
    assert g["hedef_orani"] is None


def test_metrikler_near_miss_ve_medyan_barlar():
    """#6/#8: stop'ta hedefi kıl payı kaçırma + varış barı medyanları."""
    recs = [
        _rec("nm1", durum="stop", mfe_atr=1.3, stop_bar=4),      # near-miss (>=1.2)
        _rec("nm2", durum="stop", mfe_atr=0.4, stop_bar=2),      # değil
        _rec("nm3", durum="hedef", hedef_bar=3),
        _rec("nm4", durum="hedef", hedef_bar=5),
    ]
    g = _metrik(recs)["genel"]
    assert bt.NEAR_MISS_MFE_ATR == 1.2
    assert g["near_miss"] == 1
    assert g["near_miss_esik"] == 1.2
    assert g["med_stop_bar"] == 3 and g["med_hedef_bar"] == 4.0


def test_metrikler_tip_aile_tf_ayrismasi():
    """#3/#4/#5: karışmıyor; tip ve TF grup anahtarları doğru."""
    recs = [
        _rec("x1", durum="hedef", pattern_type="Boğa Bayrağı", family="Bayrak",
             tf="1h"),
        _rec("x2", durum="stop", pattern_type="Boğa Bayrağı", family="Bayrak",
             tf="4h"),
        _rec("x3", durum="hedef", pattern_type="Simetrik Üçgen", family="Üçgen",
             tf="1h"),
    ]
    m = _metrik(recs)
    assert set(m["tip"]) == {"Boğa Bayrağı", "Simetrik Üçgen"}
    assert m["tip"]["Boğa Bayrağı"]["n"] == 2
    assert m["tip"]["Boğa Bayrağı"]["hedef"] == 1
    assert m["tip"]["Boğa Bayrağı"]["stop"] == 1
    assert m["tip"]["Simetrik Üçgen"]["n"] == 1
    assert set(m["aile"]) == {"Bayrak", "Üçgen"}
    assert set(m["tf"]) == {"1h", "4h"}
    assert m["tf"]["4h"]["n"] == 1 and m["tf"]["4h"]["stop"] == 1
    assert m["tf"]["1h"]["n"] == 2 and m["tf"]["1h"]["hedef"] == 2


def test_metrikler_kalite_bantlari_karne_uyumlu():
    """#6: q≥80 / q70–79 / q<70 (Karne ile AYNI etiketler); kırılım kalitesi öncelikli."""
    recs = [
        _rec("k1", durum="hedef", dogum_q=60.0, kirilim_q=80.0),   # → q≥80
        _rec("k2", durum="stop", dogum_q=77.0),                      # → q70–79
        _rec("k3", durum="hedef", dogum_q=69.9),                      # → q<70
    ]
    k = _metrik(recs)["kalite"]
    assert k["karne"]["q≥80"]["n"] == 1 and k["karne"]["q≥80"]["hedef"] == 1
    assert k["karne"]["q70–79"]["n"] == 1 and k["karne"]["q70–79"]["stop"] == 1
    assert k["karne"]["q<70"]["n"] == 1 and k["karne"]["q<70"]["hedef"] == 1
    assert tuple(bt.KALITE_BANTLARI) == ("q≥80", "q70–79", "q<70")
    assert k["dagilim"]["n"] == 3 and k["dagilim"]["maks"] == 80.0


def test_metrikler_esik_goreli_bantlar():
    """TF alarm eşiğine göreli bantlar — config'ten OKUNUR, değiştirilmez."""
    recs = [
        _rec("e1", durum="hedef", dogum_q=74.0),   # eşikaltı (<80)
        _rec("e2", durum="hedef", dogum_q=80.0),   # eşik   (80 .. 84.99)
        _rec("e3", durum="stop", dogum_q=84.0),    # eşik   (85 değil)
        _rec("e4", durum="stop", dogum_q=92.0),    # eşik+10 (>=90)
    ]
    eg = _metrik(recs)["kalite"]["esik_goreli"]
    assert eg["1h"]["eşikaltı"] == 1
    assert eg["1h"]["eşik"] == 2
    assert eg["1h"]["eşik+5"] == 0
    assert eg["1h"]["eşik+10"] == 1


def test_metrikler_bilesim_ayni_toplam_farkli_vektor():
    """#7 ve §3 ana soru: toplam q=80 İKİ formasyon BİLEŞEN bazında ayrılır."""
    a = _rec("cmp-a", durum="hedef", dogum_q=80.0,
             components={c: 60.0 for c in BILESIM_SKORLARI}
                        | {"geometry_score": 95.0})
    b = _rec("cmp-b", durum="stop", dogum_q=80.0,
             components={c: 60.0 for c in BILESIM_SKORLARI}
                        | {"touch_score": 95.0})
    m = _metrik([a, b])
    sk = m["bilesim"]["skorlar"]
    assert BILESIM_SKORLARI <= set(sk)
    assert sk["geometry_score"]["med_hedef"] == 95.0
    assert sk["geometry_score"]["med_stop"] == 60.0
    assert sk["geometry_score"]["fark"] == 35.0
    assert sk["touch_score"]["med_hedef"] == 60.0
    assert sk["touch_score"]["med_stop"] == 95.0
    assert sk["touch_score"]["fark"] == -35.0
    assert m["bilesim"]["eslesmeyen"] == 0
    # eşleşmeyen vektörlü kayıt ayrı sayılır, skor istatistiğine girmez:
    c = _rec("cmp-c", durum="hedef", components={})
    m2 = _metrik([a, b, c])
    assert m2["bilesim"]["eslesmeyen"] == 1
    assert m2["bilesim"]["skorlar"]["geometry_score"]["n_hedef"] == 1


def test_metrikler_mfe_mae_birebir_oku():
    """#8: outcome alanları BİREBİR okunur — yeniden hesap YOK."""
    r = _rec("mm", durum="nötr", mfe_pct=2.75, mae_pct=1.25, mfe_atr=2.2,
             mae_atr=1.0, son_pct=-0.3, hedef_bar=None, stop_bar=None)
    g = _metrik([r])["genel"]
    assert g["notr"] == 1 and g["degerlendirilen"] == 1
    assert g["med_mfe_pct"] == 2.75 and g["med_mae_pct"] == 1.25
    assert g["med_mfe_atr"] == 2.2 and g["med_mae_atr"] == 1.0
    assert g["med_son_pct"] == -0.3
    assert g["med_hedef_bar"] is None and g["med_stop_bar"] is None


def test_metrikler_huni_lifecycle_breakout_retest():
    """#9: lifecycle/breakout/retest sayaçları events + sonuc + breakout'tan."""
    a = _rec("h1", durum="hedef",
             events=["NEW_PATTERN", "BREAK_CANDIDATE", "BREAK_CONFIRMED",
                     "RETEST_OK", "COMPLETED"],
             breakout={"break_strength": 61.0,
                       "break_confirmation_strength": 70.0,
                       "dir": 1, "karsi_yonlu": False},
             deneme=2)
    b = _rec("h2", durum=None,
             events=["BREAK_CANDIDATE", "TIMEOUT", "BREAK_FAILED"],
             breakout={"break_strength": 30.0,
                       "break_confirmation_strength": None,
                       "dir": -1, "karsi_yonlu": True})
    huni = _metrik([a, b])["huni"]
    assert huni["kirilimi_olan"] == 2
    assert huni["teyitli"] == 1            # BREAK_CONFIRMED yalnız a'da
    assert huni["retest_ok"] == 1
    assert huni["tamamlandi"] == 1         # terminal_state FORMASYON_TAMAMLANDI
    assert huni["basarisiz"] == 1          # BREAK_FAILED
    assert huni["timeout"] == 1           # TIMEOUT (Karne'de olayı YOK — #9 notu)
    assert huni["karsi_yonlu"] == 1
    assert huni["cok_denemeli"] == 1       # a.deneme=2
    assert huni["med_break_strength"] == 45.5


def test_metrikler_vaka_siralamasi():
    recs = [_rec("v1", durum="hedef", son_pct=2.5),
            _rec("v2", durum="stop", son_pct=-1.1),
            _rec("v3", durum="nötr", son_pct=0.4)]
    m = _metrik(recs)
    assert m["vaka"]["en_iyi"][0]["stable_id"] == "v1"
    assert m["vaka"]["en_kotu"][0]["stable_id"] == "v2"
    assert m["vaka"]["en_iyi"][0]["son_pct"] == 2.5
    assert len(m["vaka"]["en_iyi"]) <= 5 and len(m["vaka"]["en_kotu"]) <= 5


def test_metrikler_yorum_esikleri():
    """#17/#18: YETERLI_N=30, KISMI_N=15 — bayrak grup bazında ve karışmaz."""
    assert bt.YETERLI_N == 30 and bt.KISMI_N == 15
    assert _metrik([_rec(f"y{i}") for i in range(31)])["genel"]["yorum"] == "yeterli"
    assert _metrik([_rec(f"m{i}") for i in range(20)])["genel"]["yorum"] == "kısmi"
    buyuk = _metrik([_rec(f"y{i}") for i in range(31)])
    assert buyuk["tip"]["Simetrik Üçgen"]["yorum"] == "yeterli"
    kucuk = _metrik([_rec(f"k{i}") for i in range(10)])
    assert kucuk["genel"]["yorum"] == "betimleyici"


# ---------------------------------------------------------------------------
# rapor_metni() / komut(): metin düzeyi kilitler
# ---------------------------------------------------------------------------

def _dolu_korpus(tmp_path):
    bk = "2026-09-20 12:00:00+03:00"
    rec = _ham_kayit("sid-A", sonuc=_sonuc("hedef", son_pct=1.8),
                     snapshotlar=[_geo_snap(bk, "sid-A"), _kir_snap(bk, "sid-A")],
                     olaylar=[_olay("BREAK_CONFIRMED", bk, "sid-A")])
    _tarih_dosyasi(tmp_path, "AKBNK", "1h", {"sid-A": rec})
    return tmp_path


def test_rapor_blok_basliklari_ve_n():
    """#17: ölçüm üreten her blokta n; detay blokları normal çıktıda YOK."""
    assert tuple(bt.BLOKLAR_TEMEL) == TEMEL_TOKENS
    assert tuple(bt.BLOKLAR_DETAY) == DETAY_TOKENS
    metin = bt.rapor_metni(_metrik([_rec("r1"), _rec("r2", durum="stop")]))
    for token in TEMEL_TOKENS:
        assert token in metin, f"blok eksik: {token}"
    for token in N_ILE_GELMELI:
        assert re.search(r"n=\d+", metin.split(token, 1)[1]), f"{token}: n yok"
    for token in DETAY_TOKENS:
        assert token not in metin


def test_rapor_detay_farki():
    """#11: detay = temel + BİLEŞEN/GEOMETRİ/VAKA; uzunluğu artar, n korunur."""
    m = _metrik([_rec("d1")])
    temel = bt.rapor_metni(m, detay=False)
    detay = bt.rapor_metni(m, detay=True)
    for token in DETAY_TOKENS:
        assert token not in temel and token in detay
    assert re.search(r"n=\d+", detay.split("BİLEŞEN", 1)[1]), "BİLEŞEN: n yok"
    assert len(detay) > len(temel)


def test_rapor_kucuk_n_betimleyici():
    """#18: küçük örneklem 'kanıt' gibi sunulmaz — etiket metinde görünür."""
    metin = bt.rapor_metni(_metrik([_rec("s1"), _rec("s2", durum="stop")]))
    assert "betimleyici" in metin


def test_komut_akisi_pencere_ve_vaka(tmp_path):
    """#10/#11 uçtan uca: /backtest, /backtest 90, /backtest 90 detay."""
    _dolu_korpus(tmp_path)
    temel = bt.komut("", data_dir=str(tmp_path), simdi=SIMDI)
    assert isinstance(temel, str) and "KAPSAYICILIK" in temel
    assert "tüm zamanlar" in temel
    gunluk = bt.komut("90", data_dir=str(tmp_path), simdi=SIMDI)
    assert "son 90 gün" in gunluk
    detayli = bt.komut("90 detay", data_dir=str(tmp_path), simdi=SIMDI)
    assert "VAKA" in detayli and "sid-A" in detayli


def test_komut_arguman_hatalari():
    """Kötü argüman → Kullanım metni (çökme yok); tek başına 'detay' geçerli."""
    yok_dizin = os.path.join(os.sep, "backtest-v1-yok-dizin")
    for kotu in ("abc", "90 abc", "0", "999999x", "-5"):
        metin = bt.komut(kotu, data_dir=yok_dizin, simdi=SIMDI)
        assert metin.startswith("Kullanım:"), kotu
    metin = bt.komut("detay", data_dir=yok_dizin, simdi=SIMDI)
    assert not metin.startswith("Kullanım:")
    assert "veri yok" in metin


def test_komut_mesaji_telegram_sinirinda(tmp_path):
    """Tek mesaj bütçesi: 3900 krn altı (4096 Telegram sınırına pay bırak)."""
    _dolu_korpus(tmp_path)
    for arg in ("", "90 detay"):
        assert len(bt.komut(arg, data_dir=str(tmp_path), simdi=SIMDI)) < 3900


# ---------------------------------------------------------------------------
# Yan-etki kilitleri (#12/#13/#14), determinizm (#15), AST bekçisi (#19)
# ---------------------------------------------------------------------------

def _agac_sha(tmp_path):
    dosyalar = sorted(p for p in tmp_path.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for p in dosyalar:
        h.update(str(p.relative_to(tmp_path)).encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest(), [str(p.relative_to(tmp_path)) for p in dosyalar]


def _tam_korpus(tmp_path):
    """history + karne + f2 mirror kuyruğu içeren tmp data_dir."""
    _dolu_korpus(tmp_path)
    _karne_yaz(tmp_path, [{"tip": "kirilim", "stock": "AKBNK", "tf": "1h",
                           "quality": 84.0, "dir": 1, "entry": 101.0, "atr": 1.2,
                           "bar_time": "2026-09-20 12:00:00+03:00",
                           "kayit_zaman": "2026-09-20T13:00:00+03:00",
                           "stable_id": "sid-A"}])
    _yaz(tmp_path / "f2_kuyruk.json",
         {"f2_formations": [], "f2_snapshots": [], "f2_events": [],
          "f2_outcome_links": []})
    return tmp_path


def test_backtest_dosyalara_dokunmaz(tmp_path):
    """#12/#13/#14: komut ÖNCESİ/SONRASI dosya içerikleri + dosya listesi aynı."""
    _tam_korpus(tmp_path)
    sha_once, liste_once = _agac_sha(tmp_path)
    bt.komut("", data_dir=str(tmp_path), simdi=SIMDI)
    bt.komut("90 detay", data_dir=str(tmp_path), simdi=SIMDI)
    sha_son, liste_son = _agac_sha(tmp_path)
    assert sha_once == sha_son
    assert liste_once == liste_son          # .tmp / rapor dosyası da üretilmez


def test_backtest_yazma_apisini_hic_cagirmaz(tmp_path, monkeypatch):
    """#12/#13/#14 davranışsal mayın: YAZMA fonksiyonları çağrılırsa patlar."""
    from karne import KarneDefteri
    from state import formation_mirror, outcome_link

    def patlama(*a, **k):
        raise AssertionError("backtest YAZMA API'si çağırdı!")

    monkeypatch.setattr(fh, "kaydet", patlama)
    monkeypatch.setattr(fh, "sonuc_bagla", patlama)
    monkeypatch.setattr(fh, "dogum_ekle", patlama)
    monkeypatch.setattr(fh, "olay_ekle", patlama)
    monkeypatch.setattr(fh, "snapshot_ekle", patlama)
    monkeypatch.setattr(fh, "terminal_ekle", patlama)
    monkeypatch.setattr(fh, "durum_guncelle", patlama)
    monkeypatch.setattr(outcome_link, "bagla", patlama)
    for ad in ("kaydet", "buda", "formasyon_kaydet", "kirilim_kaydet",
               "olay_kaydet"):
        monkeypatch.setattr(KarneDefteri, ad, patlama)
    monkeypatch.setattr(formation_mirror, "mirror_kaydet", patlama)
    monkeypatch.setattr(formation_mirror, "get_mirror_queue", patlama)

    _tam_korpus(tmp_path)
    metin = bt.komut("detay", data_dir=str(tmp_path), simdi=SIMDI)
    assert "KAPSAYICILIK" in metin          # patlama olmadı → sözleşme temiz


def test_determinizm_iki_kos_ayni(tmp_path):
    """#15: aynı veri → bayt bayt aynı corpus/rapor; deterministik sıralama."""
    _tam_korpus(tmp_path)
    assert (bt.komut("90 detay", data_dir=str(tmp_path), simdi=SIMDI) ==
            bt.komut("90 detay", data_dir=str(tmp_path), simdi=SIMDI))
    c1 = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    c2 = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    assert c1 == c2
    _tarih_dosyasi(tmp_path, "GARAN", "4h", {"sid-B": _ham_kayit("sid-B",
                                                                  sonuc=_sonuc("stop"))})
    c3 = bt.topla(data_dir=str(tmp_path), simdi=SIMDI)
    ana = [(x["stock"], x["tf"], x["stable_id"]) for x in c3["kayitlar"]]
    assert ana == sorted(ana)


def test_ast_modul_yazma_ag_ve_saat_cagrisi_icermez():
    """#19 + salt-okunur mimari: kaynak taraması (yorum satırları hariç).

    V1 tek dosyalık salt-okunur bir katmandır (`analytics/backtest.py`).
    Yazma API'leri, ağ erişimi, backfill/fetch ve koşu-anı saati (determinizm)
    statik olarak yasaktır — config eşikleri yalnız OKUNUR, atanamaz.
    """
    src = inspect.getsource(bt)
    kod = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
    yasak = [
        r"open\(",                                   # ham dosya erişimi yok
        r"\.kaydet\(",
        r"json\.dump",
        r"os\.replace|makedirs|unlink|remove\(|rename\(",
        r"mirror_kaydet|get_mirror_queue|sonuc_bagla|snapshot_ekle|olay_ekle",
        r"\bbagla\(",                                # outcome_link.bagla (yazan varyant)
        r"upsert|requests\.|urlopen|http",
        r"yfinance|fetch_",                          # backfill/replay V1 dışı
        r"datetime\.now|utcnow\(|time\.time",        # #15: koşu-anı saat yok
        r"config\.[A-Z_]+\s*=(?!=)",                 # config'e yazmak yasak
    ]
    for desen in yasak:
        assert not re.search(desen, kod), f"yasak desen: {desen}"


def test_store_param_guvenli_olmali(tmp_path):
    """Supabase opsiyonel: store verilse de çökmez; salt-okunur kalır."""
    _tam_korpus(tmp_path)
    sha_once, _ = _agac_sha(tmp_path)
    korpus = bt.topla(data_dir=str(tmp_path), simdi=SIMDI, store=object())
    assert korpus["kayitlar"]
    assert _agac_sha(tmp_path)[0] == sha_once


def test_metrikler_tum_anlamli_bloklarda_n_var():
    """#17: metrikler sözlüğündeki her grup satırının n'ı vardır."""
    m = _metrik([_rec("n1"), _rec("n2", durum="stop", tf="4h",
                                  pattern_type="Boğa Bayrağı")])
    assert m["genel"]["n"] == 2
    for grup in ("tip", "aile", "tf"):
        for etiket, v in m[grup].items():
            assert v["n"] >= 1, etiket
            assert "degerlendirilen" in v and "yorum" in v
    assert m["bilesim"]["eslesmeyen"] + m["bilesim"]["n_vektorlu"] == 2
