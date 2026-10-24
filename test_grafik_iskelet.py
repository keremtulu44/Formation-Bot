# -*- coding: utf-8 -*-
"""G1 grafik iskeleti testleri — §6.1 (kadraj/drift/eksik katman), §6.2 (hizalama),
§6.4 (kapsam), §6.5 (boyut/format), §6.6 (matris).

Piksel hash'ine bağlanmıyoruz (§12.19): determinizm `meta` ve `girdi_ozeti`
üzerinden doğrulanır. Testler `bot_data/` önbelleğine YAZMAZ — derin günlük
çerçeve gereken yerlerde sentetik üretilir (canlı bot aynı dizini okuyor, §22 kaydı).
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path
import unittest.mock as mock
from datetime import datetime, timedelta, timezone

import pytest

import grafik

IST = timezone(timedelta(hours=3))
ZAMAN = datetime(2026, 12, 1, 9, 0, tzinfo=IST)       # çizim testlerinde "şimdi"
VOLATIL = {"sure_ms", "png_kb", "yol", "girdi_ozeti", "kaynak"}


def _seans_zamanlari(n: int, tf: str, ilk: datetime) -> list[datetime]:
    """BIST seans etiketleri: 1s günde 9 mum (09:30…17:30, önbellekle aynı);
    2s/4s aynı günün kovaları, 1g iş günü başına bir bar.

    Neden böyle: `data.bar_kapandi_mi` seans sonuna göre karar veriyor (17:30
    etiketli 1s mumu 18:00'de kapanır). Düz 24 saatlik dizme testi yanıltırdı.
    """
    if tf == "1d":
        gun, cikti = ilk, []
        while len(cikti) < n:
            if gun.weekday() < 5:
                cikti.append(gun.replace(hour=9, minute=30))
            gun += timedelta(days=1)
        return cikti
    saatler = {"1h": [9, 10, 11, 12, 13, 14, 15, 16, 17],
               "2h": [9, 11, 13, 15, 17], "4h": [9, 13]}[tf]
    gun, cikti = ilk, []
    while len(cikti) < n:
        if gun.weekday() < 5:
            for s in saatler:
                if len(cikti) >= n:
                    break
                cikti.append(gun.replace(hour=s, minute=30))
        gun += timedelta(days=1)
    return cikti


def _cerceve(n: int = 240, tf: str = "1h", ilk=None, taban: float = 50.0,
             hacim_sifir=(), yon: float = 0.05):
    """Deterministik çerçeve (kolon sözlüğü): testler pandas/önbellek istemez."""
    ilk = ilk or datetime(2026, 10, 5, 9, 30, tzinfo=IST)
    zamanlar = _seans_zamanlari(n, tf, ilk)
    kapanis, acilis, yuksek, dusuk, hacim = [], [], [], [], []
    fiyat = taban
    for i in range(n):
        fiyat = round(max(1.0, fiyat + yon * math.sin(i / 9.0) + 0.01 * (i % 3)), 2)
        acilis.append(round(fiyat - 0.05, 2))
        kapanis.append(fiyat)
        yuksek.append(round(fiyat + 0.35, 2))
        dusuk.append(round(fiyat - 0.35, 2))
        hacim.append(0.0 if i in set(hacim_sifir) else float(1_000_000 + 7_000 * i))
    return {"zaman": zamanlar, "acilis": acilis, "yuksek": yuksek, "dusuk": dusuk,
            "kapanis": kapanis, "hacim": hacim}


def _cift(**uzerine):
    kayit = {"pattern_name": "Simetrik Üçgen", "state": "KIRILIM_TEYITLI",
             "quality": 88.0, "contraction": 0.42, "start_bar": 200, "end_bar": 239,
             "apex_bar": 230, "upper_now": 52.5, "lower_now": 49.5,
             "upper_touches": 3, "lower_touches": 4, "break_price": 52.5,
             "candle_close_price": 51.9, "evidence_text": ""}
    kayit.update({k: v for k, v in uzerine.items() if v is not ...})
    return kayit


def _goruntu(cerceve=None, tf="1h", cift=..., **secenek):
    cerceve = _cerceve(240, tf) if cerceve is None else cerceve
    cift = _cift() if cift is ... else cift
    secenek.setdefault("simdi", ZAMAN)
    secenek.setdefault("alarm_bar", min(len(cerceve["kapanis"]) - 1, 239))
    return grafik.anlik_goruntu(cift, tf, cerceve, **secenek)


def _png_olcu(yol: str) -> tuple[int, int]:
    with open(yol, "rb") as akis:
        baslik = akis.read(24)
    assert baslik[:8] == b"\x89PNG\r\n\x1a\n", "PNG imzası yok"
    return struct.unpack(">II", baslik[16:24])


# ---------------------------------------------------------------- kadraj (§2)


def test_kadraj_formasyon_penceresine_sabitlenir():
    """FAZ 2 Kural A: formasyon + 10 mum sol tampon, 35-85 mum aralığına kırpılır."""
    g = _goruntu()
    # start_bar 200, n 240 → istenen 10+10=20 → alt sınır 35 → sol = 200-10 = 190
    assert (g["sol"], g["sag"]) == (190, 240)
    assert len(g["zamanlar"]) == 50 and g["kare_mum"] == 80
    assert g["tavan_kalkti"] is False
    assert not any("kadraj:" in b for b in g["budama"])


def test_formasyon_yoksa_tf_matrisi_kullanilir():
    """FAZ 2 Kural B: formasyon yokken TF matrisi (1g 62 · 4s 68 · 2s 74 · 1s 80)."""
    for tf, beklenen in (("1h", 80), ("2h", 74), ("4h", 68), ("1d", 62)):
        g = _goruntu(_cerceve(240, tf), tf=tf, cift=None)
        assert g["kare_mum"] == beklenen, tf
        assert len(g["zamanlar"]) == beklenen
        assert (g["sol"], g["sag"]) == (g["bar_sayisi"] - beklenen, g["bar_sayisi"])
    assert grafik.kare_mum_tavani("1d") == 62


def test_formasyon_tavandan_uzunsa_pencere_kirpilir():
    """Kural A üst sınırı 180 (2026-10-23): daha uzun formasyonda sağ taraf gösterilir."""
    g = _goruntu(_cerceve(400), cift=_cift(start_bar=10, end_bar=399))
    assert g["tavan_kalkti"] is True
    # son bar açık olabilir (§0.6) → pencere `sag` üzerinden okunur
    assert g["sag"] - g["sol"] == 180 and g["sag"] == g["bar_sayisi"]
    assert "180 mumluk pencereye" in g["budama"][0]


def test_formasyon_yokken_tf_matrisi_kirpilmaz():
    """Kural B pencere boyu kadraj tavanından gelir; formasyon yoksa budama yazılmaz."""
    g = _goruntu(_cerceve(300), cift=None)
    assert (g["sol"], g["sag"]) == (300 - 80, 300)
    assert g["tavan_kalkti"] is False and g["budama"] == []


def test_formasyon_kisa_ise_alt_sinir_35_mum(monkeypatch):
    """Kural A alt sınırı 35: 3 mumluk formasyon 35 mumluk pencereye oturur."""
    monkeypatch.setenv("GRAFIK_MUM_MAKS", "100")
    g = _goruntu(_cerceve(240), cift=_cift(start_bar=237))
    assert g["kare_mum"] == 100 and (g["sol"], g["sag"]) == (205, 240)
    assert len(g["zamanlar"]) == 35


def test_kare_mum_tavani_env_anahtarindan_okunur(monkeypatch):
    monkeypatch.setenv("GRAFIK_MUM_MAKS", "100")
    assert grafik.kare_mum_tavani("1h") == 100
    g = _goruntu(cift=None)                          # formasyon yok → Kural B
    assert g["kare_mum"] == 100 and (g["sol"], g["sag"]) == (140, 240)
    monkeypatch.setenv("GRAFIK_MUM_MAKS", "bozuk")     # yutulur, varsayılana düşer
    assert grafik.kare_mum_tavani("1h") == int(grafik.SABITLER["kadraj_cerceve"]["1h"])


def test_genislik_bar_sayisiyla_buyur_ve_tavana_dayanir():
    kare = grafik._kare_olcu({"zamanlar": list(range(180))})
    assert (kare["genislik"], kare["yukseklik"]) == (1080, 810)     # §0.12q 4:3
    assert kare["px_bar"] == 6.0 and kare["cekme"] is False
    assert grafik._kare_olcu({"zamanlar": list(range(120))})["genislik"] == 1080  # taban
    genis = grafik._kare_olcu({"zamanlar": list(range(300))})
    assert genis["genislik"] == 1440 and genis["cekme"] is True      # §17.2 tavan
    assert genis["px_bar"] < float(grafik.SABITLER["mum_min_px"])


def test_yalniz_kapanmis_mumlar_cizilir():
    cerceve = _cerceve(117)                                          # 13 gün × 9 mum
    assert (cerceve["zaman"][-1].hour, cerceve["zaman"][-1].minute) == (17, 30)
    acik = grafik.anlik_goruntu(_cift(end_bar=116), "1h", cerceve,
                                simdi=cerceve["zaman"][-1] + timedelta(minutes=5))
    assert acik["son_bar_kapali"] is False and acik["bar_sayisi"] == 116
    assert any("açık" in x for x in acik["notlar"])
    # dipnot DEĞİL: açık bar çizilmemesi normaldir (§0.12w yalnız veri sorunu)
    assert not any("açık" in x for x in acik["uyarilar"])
    kapali = grafik.anlik_goruntu(_cift(end_bar=116), "1h", cerceve,
                                  simdi=cerceve["zaman"][-1] + timedelta(minutes=35))
    assert kapali["son_bar_kapali"] is True and kapali["notlar"] == []
    assert kapali["bar_sayisi"] == 117


# ------------------------------------------------------ temas + hizalama (§6.2)


def test_temas_kurali_zone_scoring_kuraliyla_ayni():
    import pandas as pd
    from zone_scoring import _touch_episodes

    cerceve = _cerceve(120, yon=0.9)
    frame = pd.DataFrame({"low": cerceve["dusuk"], "high": cerceve["yuksek"],
                          "close": cerceve["kapanis"], "timestamp": cerceve["zaman"]})
    alt, ust = 50.0, 51.0
    bulunan = set(grafik._bant_temaslari(cerceve["yuksek"], cerceve["dusuk"], alt, ust,
                                         0, 120))
    episode_barlari = set()
    for bolum in _touch_episodes(frame, alt, ust, first_index=0, last_index=119):
        episode_barlari.update(range(bolum.start_index, bolum.end_index + 1))
    assert bulunan == episode_barlari                        # aynı satır içi kural
    assert bulunan                                             # boş küme test olmasın


def test_temas_adedi_korunur_daire_isaretleri_cizimden_kaldirildi():
    cerceve = _cerceve(240, yon=1.2)
    g = grafik.anlik_goruntu(_cift(start_bar=200, upper_now=54.0, lower_now=47.0), "1h",
                             cerceve, simdi=ZAMAN)
    assert g["temas"]                                  # adet kaynağı korunur
    assert g["temas_isaret"] == []                    # mum üstü daireler kaldırıldı
    assert not any("temas işareti" in b for b in g["budama"])


def test_kadraj_disindaki_alarm_mumu_yazilir():
    g = _goruntu(cift=_cift(start_bar=200), alarm_bar=3)   # kadraj 60'tan başlar
    assert g["alarm"]["bar"] is None and g["alarm"]["bar_disarida"] is True
    assert any("kadraj dışında" in u for u in g["uyarilar"])


def test_isaretler_yalniz_kadraj_icindeki_mumlara_yazilir():
    g = _goruntu(cift=_cift(start_bar=200, end_bar=239, apex_bar=230))
    adlar = {x["ad"] for x in g["isaretler"]}
    assert "bant başlangıcı" in adlar and "apex" in adlar
    for kayit in g["isaretler"]:
        assert g["sol"] <= kayit["bar"] < g["sag"]
        assert kayit["y"] is not None


# ------------------------------------------------------------------- etiketler


def test_alarm_etiketi_motorun_durum_metninden():
    from notifier import PUBLIC_STATE_ETIKET

    g = _goruntu()
    assert g["alarm"]["etiket"] == PUBLIC_STATE_ETIKET["KIRILIM_TEYITLI"]
    # Tablo dışı duruma etiket UYDURULMAZ; iç izleme anahtarı kareye taşınmaz (§0.12z)
    retest = _goruntu(cift=_cift(state="RETEST_BASARILI"))
    assert retest["alarm"]["etiket"] == PUBLIC_STATE_ETIKET["RETEST_BASARILI"]
    yabanci = _goruntu(cift=_cift(state="IC_IZLEME_X"))
    assert not yabanci["alarm"]["etiket"]
    assert "IC_IZLEME_X" not in json.dumps(
        grafik._metinler(yabanci, {"mum_sayisi": 180, "hacimsiz_bar": 0}, 1080, [], False),
        ensure_ascii=False)
    duz = json.dumps(grafik._metinler(g, {"mum_sayisi": 180, "hacimsiz_bar": 0}, 1080,
                                     [], False), ensure_ascii=False)
    assert "KIRILIM_TEYITLI" not in duz                        # ham kod hiçbir yazıda yok


def test_yazi_virgullu_ve_baslarda_veri_yoksa_yazi_yok():
    g = _goruntu(cift=_cift(break_price=302.478, candle_close_price=299.999,
                            upper_now=302.478, lower_now=295.0))
    metin = grafik._metinler(g, {"mum_sayisi": 180, "hacimsiz_bar": 0}, 1080, [], False)
    duz = " ".join([metin["baslik"], metin["sag"]] + metin["satirlar"] + metin["lejant"])
    assert "302,48" in duz                                     # G0 standardı (§15)
    assert not re.search(r"\d+\.\d+", duz), duz                 # nokta ondalık yok
    assert "· 1s ·" in metin["baslik"]                       # TF kısaltması mevcut (§14.5)
    assert metin["baslik"].startswith("—") or metin["baslik"].split(" · ")[0]  # sembol yoksa —
    bos = grafik._metinler(grafik.anlik_goruntu(None, "1h", _cerceve(30), simdi=ZAMAN),
                           {"mum_sayisi": 30, "hacimsiz_bar": 0}, 1080, [], False)
    assert bos["satirlar"] == [] and bos["dipnotlar"] == []    # veri yok → uydurma yazı yok


def test_lejant_her_karede_var_dipnot_yalniz_veri_bozuksa():
    temiz = _goruntu()
    metin = grafik._metinler(temiz, {"mum_sayisi": 180, "hacimsiz_bar": 0}, 1080, [], False)
    assert metin["lejant"] and metin["dipnotlar"] == []         # §0.12v / §0.12w
    kirli = _goruntu(_cerceve(240, hacim_sifir=(200, 201, 202)))
    metin_kirli = grafik._metinler(kirli, {"mum_sayisi": 180, "hacimsiz_bar": 3}, 1080,
                                   ["ob"], False)
    assert "veri: 3 bar hacimsiz" in metin_kirli["dipnotlar"]
    assert metin_kirli["dipnotlar"][0] == "eksik: ob"


def test_lejant_sigmiyorsa_bolunur_veya_madde_dusurulur():
    oge = [f"madde {i} aciklamasi" for i in range(40)]
    satirlar, punto, atlanan = grafik._lejant_satirlar(oge, 1080)
    assert len(satirlar) <= 2 and punto <= float(grafik.SABITLER["lejant_pt"])
    # GÖRSEL-7: düşürülen madde sayısı kareye YAZILMAZ ("+N madde sığmadı" notu
    # okunurluğu bozan bir geliştirici notuydu); sayaç `meta["lejant_atlanan"]`da
    # ve `atlanan` dönüşünde durur — sessiz kayıp yok. Kareye yazılan metin ise
    # her zaman sığan maddelerden oluşur.
    assert not any("sığmadı" in s for s in satirlar)
    assert atlanan == 0 or len("".join(satirlar)) < len(" · ".join(oge))
    # Düşürme en uzun maddeden başlar: kısa/önemli maddeler ayakta kalır.
    if atlanan:
        kalan = [x for x in oge if any(x[:9] in s for s in satirlar)]
        atilan = [x for x in oge if x not in kalan]
        assert min(len(x) for x in atilan) >= max(len(x) for x in kalan) - 2
    # kısa içerik tek satır ve tam punto kalır
    tek, punto2, _ = grafik._lejant_satirlar(["mum: yalnız kapalı"], 1080)
    assert tek == ["mum: yalnız kapalı"] and punto2 == float(grafik.SABITLER["lejant_pt"])


# ---------------------------------------------------------------------- çizim


def test_bos_veride_istisna_yok_png_uretilmez(tmp_path):
    g = grafik.anlik_goruntu(None, "1h", None)
    assert g["uyarilar"] and g["bar_sayisi"] == 0
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "x.png")})
    assert yol is None and meta["red"] is True
    assert not (tmp_path / "x.png").exists()


def test_meta_sozlesmesi_ve_png_olcusu(tmp_path):
    g = _goruntu(sembol="AKBNK")
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "meta.png")})
    for alan in ("sem", "tf", "mum_sayisi", "bar_basina_px", "temas", "cizgiler", "zone",
                 "olay", "serit", "budama", "eksik_katmanlar", "hacimsiz_bar", "son_bar_ts",
                 "sure_ms", "png_kb", "uyarilar"):
        assert alan in meta, alan
    assert meta["sem"] == "AKBNK" and meta["tf"] == "1s"
    assert meta["kare"]["yukseklik"] == 810 and meta["mum_sayisi"] == 50
    assert meta["cizgiler"]["alarm"]["deger"] == pytest.approx(52.5)
    # G2: `zone` alanı biçimini sabit tuttu (boşken de aynı anahtarlar; §13)
    assert meta["zone"]["cizilen"] == 0 and meta["zone"]["elenen"] == 0
    assert meta["zone"]["sirala"] == "zone verisi yok"
    assert set(meta["zone"]) >= {"cizilen", "elenen", "tip", "kaynak_disi", "kapak",
                                 "sirala", "atr", "hata", "kayitlar"}
    # G3: `olay`/`serit` de sabit biçimde döner (§13 okuyucusu dalgalanmasın)
    assert meta["olay"]["cizilen"] == 0 and meta["olay"]["bos_choc"] == 0
    assert set(meta["olay"]) >= {"cizilen", "elenen", "swing", "bos_choc", "kritik",
                                 "kapak", "etiket_atlandi", "hata"}
    assert set(meta["serit"]) >= {"acik", "esik", "spike", "kaynak", "yerel", "hacimsiz"}
    # FAZ 1: hacim PANELİ varsayılan olarak çizilmez (dikey alan mumlara kalır);
    # RVOL verisi `spike` listesinde ve mum altı ⚡ rozetinde yaşar (`rozet` sayacı).
    # `GRAFIK_HACIM_PANELI=1` eski kulvarı geri getirir (ayrı test).
    assert meta["serit"]["acik"] is False and meta["serit"]["panel"] is False
    assert isinstance(meta["serit"]["spike"], list) and "rozet" in meta["serit"]
    assert meta["serit"]["kaynak"] in ("motor", "yerel hesap", "yok")
    assert _png_olcu(meta["yol"]) == (1080, 810) and meta["png_kb"] <= 500     # §6.5


def test_meta_belirleyici_ayni_girdi_ayni_kare(tmp_path):
    sonuclar = []
    for i in range(2):
        g = _goruntu(sembol="AKBNK")
        _, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / f"d{i}.png")})
        sonuclar.append({k: v for k, v in meta.items() if k not in VOLATIL})
        assert grafik.girdi_ozeti(g) == grafik.girdi_ozeti(_goruntu(sembol="AKBNK"))
    assert sonuclar[0] == sonuclar[1]


def test_drift_cizimi_reddeder(tmp_path):
    g = _goruntu()
    bir_sonraki = (datetime.fromisoformat(g["son_bar_ts"]) + timedelta(hours=1)).isoformat()
    cikti = str(tmp_path / "drift.png")
    yol, meta = grafik.ciz(g, "1h", {"cikti": cikti, "beklenen_son_bar_ts": bir_sonraki})
    assert yol is None and meta["red"] is True
    assert any("kaydi" in u for u in meta["uyarilar"])             # §6.1 drift reddi
    assert not (tmp_path / "drift.png").exists()                   # yarım dosya bırakılmaz
    yol2, meta2 = grafik.ciz(g, "1h", {"cikti": cikti, "beklenen_son_bar_ts": g["son_bar_ts"]})
    assert yol2 and meta2["red"] is False


def test_katman_hatasi_eksik_yazisiyla_gecer(tmp_path):
    def patlar(*args, **kwargs):
        raise ValueError("bant verisi yok")

    with mock.patch.object(grafik, "_formasyon_ciz", patlar):
        g = _goruntu()
        yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "eksik.png")})
    assert yol and meta["red"] is False
    assert "cizim" in meta["eksik_katmanlar"] or "formasyon" in meta["eksik_katmanlar"]
    assert any(d.startswith("eksik:") for d in meta["metin"]["dipnotlar"])    # §2.9
    assert meta["png_kb"] > 20


def test_butun_cizim_cokerse_yalnizca_mumlar_denendigi_yazilir(tmp_path):
    gercek = grafik._kare_ciz

    def yari_sahte(goruntu, tf, olcu, meta, secenekler, *, yalnizca_mumlar):
        if not yalnizca_mumlar:
            raise RuntimeError("test hatası")
        return gercek(goruntu, tf, olcu, meta, secenekler, yalnizca_mumlar=True)

    with mock.patch.object(grafik, "_kare_ciz", yari_sahte):
        g = _goruntu()
        yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "cekme.png")})
    assert yol and meta["cekme"] is True
    assert any("çökme modu" in u for u in meta["uyarilar"])
    assert "yalnızca mumlar" in meta["metin"]["lejant"][0]         # §2.9 etiket dürüst


def test_cizgi_ve_alan_modu_kullanilirken_budamaya_yazilir(tmp_path, monkeypatch):
    """Çekme modu: FAZ 2'de pencere 85 mumu geçemez → ayrıntı için penceresi
    büyütülmüş kare (Kural B + `GRAFIK_MUM_MAKS`) kullanılır (§17.14)."""
    monkeypatch.setenv("GRAFIK_MUM_MAKS", "700")
    g = _goruntu(_cerceve(600), tf="1h", cift=None, alarm_bar=599)
    yol, meta = grafik.ciz(g, "1h", {"cikti": str(tmp_path / "cizgi.png")})
    assert meta["kare"]["genislik"] == 1440 and meta["kare"]["cekme"] is True
    assert any("çizgi + alan" in b for b in meta["budama"])
    assert _png_olcu(meta["yol"]) == (1440, 810) and meta["png_kb"] <= 500


def test_killswitch_ve_kare_adedi(monkeypatch):
    monkeypatch.delenv("TELEGRAM_GRAFIK", raising=False)
    assert grafik.grafik_aktif_mi() is False                       # §5 varsayılanı `yok`
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    assert grafik.grafik_aktif_mi() is True
    assert grafik.grafik_kare_adedi() == 4
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "99")
    assert grafik.grafik_kare_adedi() == 4                          # §5 tavan 4
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "bozuk")
    assert grafik.grafik_kare_adedi() == 4


def test_matris_cercevesi_gercel_veriden_uretilir():
    """§6.6 matrisi: gerçek önbellek varsa 2 hisse × 4 TF çizilir (yoksa skip)."""
    from data import StockDequeManager, resample_ohlcv

    yonetici = StockDequeManager(data_dir="bot_data")
    denenmis = 0
    for hisse in ("AKBNK", "THYAO"):
        df_1s = yonetici.to_dataframe(hisse)
        if df_1s is None or len(df_1s) < 60:
            continue
        for tf in ("1h", "2h", "4h", "1d"):
            cerceve = df_1s if tf == "1h" else resample_ohlcv(df_1s, tf)
            if cerceve is None or len(cerceve) < 40:
                continue
            son = int(len(cerceve) - 1)
            g = grafik.anlik_goruntu(_cift(start_bar=max(0, son - 39), end_bar=son,
                                           upper_now=float(cerceve["close"].iloc[-1]) * 1.01,
                                           lower_now=float(cerceve["close"].iloc[-1]) * 0.98),
                                    tf, cerceve, sembol=hisse, alarm_bar=son, simdi=ZAMAN)
            yol, meta = grafik.ciz(g, tf, {"cikti": f"/tmp/fb_g1_matris_{hisse}_{tf}.png"})
            assert yol, meta["uyarilar"]
            assert meta["mum_sayisi"] == meta["kare"]["sag"] - meta["kare"]["sol"]
            gen, yuk = _png_olcu(meta["yol"])
            assert yuk == 810 and 1080 <= gen <= 1440               # §2 ölçek
            assert meta["png_kb"] <= 500 and meta["eksik_katmanlar"] == []
            assert meta["hacimsiz_bar"] == sum(1 for v in g["hacim"] if v is None or v <= 0)
            denenmis += 1
    if denenmis == 0:
        pytest.skip("bot_data önbelleği yok: matris çizimi yerelde denendi")

def test_aday_nesnesi_ile_sozone_sozluğu_ayni_cizilir():
    """§18.2: motor `PatternCandidate` nesnesi verir, köprü sözlük — ikisi de okunmalı.

    Neden: `_alan()` sözlük/nesne ayrımını tek yerde tutuyor; bu test olmasa
    köprü sözlüğe göre yazılıp nesne yolunda sessizce boş kare üretebilirdi.
    """
    from types import SimpleNamespace

    cerceve = _cerceve(240)
    kayit = _cift()
    g_soze = _goruntu(cerceve, cift=kayit)
    nesne = SimpleNamespace(**kayit)
    g_nesne = grafik.anlik_goruntu(nesne, "1h", cerceve, alarm_bar=239, simdi=ZAMAN)
    assert g_nesne["formasyon"] == g_soze["formasyon"]
    assert g_nesne["alarm"] == g_soze["alarm"]
    assert (g_nesne["sol"], g_nesne["sag"], g_nesne["temas"]) == (
        g_soze["sol"], g_soze["sag"], g_soze["temas"])
    assert g_nesne["budama"] == g_soze["budama"]


# ------------------------------------------------------------------- CLI


def test_cli_veri_dizin_bayragi_okunur(tmp_path, capsys):
    """`--veri-dizin` bayrağı yolu kullanır (regresyon: yanlış değişken adı NameError
    veriyordu — yalnız bayrak verildiğinde görünen bir yoldu)."""
    import shutil

    import grafik_uret

    kopya = tmp_path / "veri"
    kopya.mkdir()
    kaynak = Path(__file__).resolve().parent / "bot_data" / "AKBNK.json"
    if not kaynak.exists():
        pytest.skip("bot_data önbelleği yok")
    shutil.copy(kaynak, kopya / "AKBNK.json")
    hedef = tmp_path / "vd.png"
    kod = grafik_uret.main(["--hisse", "AKBNK", "--tf", "1h", "--veri-dizin", str(kopya),
                            "--mum", "60", "--cikti", str(hedef)])
    assert kod == 0 and hedef.exists()
    assert str(kopya / "AKBNK.json") in capsys.readouterr().out


def test_cli_cache_veya_demo_ile_kare_uretir(tmp_path):
    """`grafik_uret.py` uçtan uca: önbellek varsa ondan, yoksa `--demo`dan çizer."""
    import json as _json

    import grafik_uret

    hedef = tmp_path / "cli.png"
    kod = grafik_uret.main(["--hisse", "AKBNK", "--tf", "1h", "--demo",
                            "--mum", "60", "--cikti", str(hedef), "--json"])
    assert kod == 0 and hedef.exists()
    gorsel = _png_olcu(str(hedef))
    assert gorsel[1] == 810 and 1080 <= gorsel[0] <= 1440


def test_cli_formasyon_dosyasi_banti_cizdirir(tmp_path):
    import json

    import grafik_uret

    kayit = _cift(start_bar=..., end_bar=..., upper_now=..., lower_now=...)
    dosya = tmp_path / "formasyon.json"
    kayit.update({"start_bar": 12, "end_bar": 30, "apex_bar": 25,
                  "upper_now": 52.5, "lower_now": 49.5, "break_price": 52.5})
    dosya.write_text(json.dumps(kayit), encoding="utf-8")
    yol = tmp_path / "cli2.png"
    kod = grafik_uret.main(["--hisse", "AKBNK", "--tf", "1h", "--demo", "--mum", "40",
                            "--formasyon", str(dosya), "--cikti", str(yol)])
    assert kod == 0 and yol.exists()
