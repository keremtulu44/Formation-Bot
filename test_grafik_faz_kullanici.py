# -*- coding: utf-8 -*-
"""FAZ 1-4 görsel plan testleri (kullanıcı planı, 2026-10-15).

Plan dört fazda uygulandı; bu dosya planın her maddesini ölçülebilir bir
sözleşmeye bağlar:

  FAZ 1 — Temizlik ve alan kazanımı
    * kırmızı/gri geliştirici metinleri ve lejant kareden ÇIKTI (kart dipnotuna
      taşındı, `notifier._grafik_dipnotu`),
    * alt hacim paneli kaldırıldı; `meta["serit"]["panel"] is False`,
    * sıra dışı hacim mum altına YÖNLÜ rozetle bağlanır: `⚡↑ x2,5` patlama
      (RVOL > 2,0), `⚡↓ x0,5` kuruma (RVOL ≤ 0,5; 2026-10-16 kullanıcı isteği).

  FAZ 2 — Akıllı kadraj
    * TF matrisi (`1G 62 · 4S 68 · 2S 74 · 1S 80`) formasyon yokken geçerli,
    * formasyon varsa kadraj formasyona odaklanır: +10 mum sol tampon, 35-85 arası,
    * sağda her zaman eksen genişliğinin %10-20'si kadar boş alan
      (`sag_bosluk_orani`; 2026-10-16 kullanıcı kararı).

  FAZ 3 — SMC motoru ve çizim revizyonu
    * OB kaydında `mitigated_percentage` (motorun `fill_boundary`si),
    * dolan alan mat gri + kalan alan canlı renk; kırılan kutu boşalır,
    * OB yeşil/kırmızı, FVG turkuaz/mor (ayrı renk grupları + kontur stili),
    * BOS/CHoCH çizgisi pivot → kırılım mumu (Line Truncation); yalnız aktif
      hedef sağ boşluğa uzar.

  FAZ 4 — Cila
    * sağ eksen etiketleri için çakışma önleyici kaydırma + LİDER çizgisi,
    * üst başlık yarı saydam yuvarlatılmış rozetler (Pills),
    * HH/HL/LH/LL etiketleri fitilden 10-15 px uzakta,
    * teyitli alarmda sağ boşlukta kesikli ok + 🎯 hedef kutusu.

Kareler sentetik veriyle üretilir (`bot_data/` önbelleğine yazılmaz).
"""

from __future__ import annotations

import unittest.mock as mock

import pytest
from matplotlib.patches import Rectangle

import grafik
from test_grafik_gorsel4 import _bolge, _eksen, _olay_goruntusu
from test_grafik_iskelet import _cerceve, _cift, _goruntu, _png_olcu


def _kare_ciz(g, tf, tmp_path, **secenek):
    """Kareyi GERÇEKTEN çizer ve figürü döner: `(fig, meta, yol)`."""
    yakalanan: list = []
    orijinal = grafik._metin_ciz

    def sarmal(fig, *a, **k):
        yakalanan.append(fig)
        return orijinal(fig, *a, **k)

    with mock.patch.object(grafik, "_metin_ciz", sarmal):
        yol, meta = grafik.ciz(g, tf, {"cikti": str(tmp_path / "kare.png"), **secenek})
    assert yol and yakalanan, meta
    return yakalanan[-1], meta, yol


def _ob(index, alt, ust, bullish=True, dolan=0.0):
    """Sentetik `OrderBlockRecord` (motorun `fill_boundary` kuralıyla)."""
    from types import SimpleNamespace

    yuk = float(ust) - float(alt)
    sinir = (float(ust) - yuk * float(dolan)) if bullish else (float(alt) + yuk * float(dolan))
    return SimpleNamespace(source_index=index, source_time=None, top=ust, bottom=alt,
                           bullish=bullish, base_score=2, anchor_high=ust, anchor_low=alt,
                           imbalance_end_index=None, fill_boundary=sinir)


def _fvg(index, alt, ust, direction=1):
    from types import SimpleNamespace

    return SimpleNamespace(formation_index=index, formation_time=None,
                           lower_boundary=alt, upper_boundary=ust,
                           direction=SimpleNamespace(value=direction),
                           state=SimpleNamespace(name="ACTIVE"), gap_size=0.8,
                           gap_atr=0.5, formation_atr=1.5, quality=88.0,
                           maximum_fill_ratio=0.0, close_fill_ratio=0.0)


# --------------------------------------------------- FAZ 1: temizlik, alan, rozet


def test_faz1_hacim_paneli_kapali_ve_rozet_sayaci_var(tmp_path):
    """Plan FAZ 1: panel kaldırıldı, dikey alan ana panele; RVOL rozeti çizilir."""
    g = _goruntu(_cerceve(240, "1h", taban=50.0, yon=0.02), "1h", cift=None)
    fig, meta, yol = _kare_ciz(g, "1h", tmp_path)
    assert len(fig.axes) == 1                       # tek eksen: hacim kulvarı yok
    assert meta["serit"]["panel"] is False and meta["serit"]["acik"] is False
    assert meta["serit"]["rozet"] <= int(grafik.SABITLER["rvol_rozet_maks"])
    assert _png_olcu(yol) == (1080, 810)


def test_faz1_hacim_paneli_env_ile_geri_gelebilir(tmp_path, monkeypatch):
    """Kaçış kapısı: `GRAFIK_HACIM_PANELI=1` eski iki kulvarlı görünümü verir."""
    monkeypatch.setenv("GRAFIK_HACIM_PANELI", "1")
    g = _goruntu(_cerceve(240, "1h"), "1h", cift=None)
    fig, meta, _ = _kare_ciz(g, "1h", tmp_path)
    assert len(fig.axes) == 2 and meta["serit"]["panel"] is True
    assert meta["serit"]["acik"] is True


def test_faz1_gelistirici_metinleri_karede_yok(tmp_path):
    """Karede lejant/dipnot bloğu çizilmez; metin `meta`da durur (kart dipnotu)."""
    g = _goruntu(_cerceve(240, "1h", hacim_sifir=(200, 201, 202)))
    fig, meta, _ = _kare_ciz(g, "1h", tmp_path)
    metin = meta["metin"]
    assert "veri: 3 bar hacimsiz" in metin["dipnotlar"]      # bilgi korunur (kartta)
    assert metin["lejant"] and metin.get("_y") is None       # kareye yerleşim YOK
    yazilar = [str(t.get_text()) for t in fig.texts]
    assert any("Veri uyarısı:" in y and "hacimsiz" in y for y in yazilar)
    assert not any("bar hacimsiz" in y for y in yazilar)
    # lejant satırı da kareye basılmaz (uzun `·` listesi yalnız meta'da)
    assert not any("yeşil boş" in y for y in yazilar)


def _rozetler(ax):
    return [str(t.get_text()) for t in ax.texts if str(t.get_text()).startswith("⚡")]


def _yon_sayaci(sayac):
    """Yön sayaçları: dönüş sözleşmesi artık tazelik izlerini de taşır (2026-10-16)."""
    return {k: sayac[k] for k in ("artis", "dusus")}


def test_faz1_rvol_rozeti_esik_ustu_mumlara_baglanir():
    """⚡↑ rozeti yalnız RVOL > 2,0 mumlara ve mumun ALTINA (fitil altı) konur."""
    fig, ax = _eksen(60)
    goruntu = {"serit": {"degerler": [1.0] * 59 + [3.4]}, "acilis": [100.0] * 60,
               "kapanis": [100.0] * 60}
    dusuk = [99.0] * 59 + [98.0]
    sayac = grafik._rvol_rozetleri(ax, goruntu, 60, dusuk)
    assert _yon_sayaci(sayac) == {"artis": 1, "dusus": 0}
    rozet = [t for t in ax.texts if str(t.get_text()).startswith("⚡")]
    assert len(rozet) == 1 and str(rozet[0].get_text()) == "⚡↑ x3,4"
    assert rozet[0].xy[1] <= 98.0                   # mumun altında (düşük fitil)


def test_faz1_rozet_iki_yonlu_artis_ve_dusus(monkeypatch):
    """2026-10-16 kullanıcı: `⚡↑ x3,0` patlama, `⚡↓ x0,5` kuruma — YÖN okla yazılır.

    Eski davranış tek yönlüydü: yalnız eşik üstü işaretlenirdi, hacim kuruması
    (x0,5) karede hiç görünmüyordu. Renk tek kanal değil (§0.4.1): yön oktan,
    büyüklük sayıdan okunur; renk (yeşil/kırmızı) yalnız pekiştirir.
    """
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    degerler[10] = 3.0                              # patlama
    degerler[40] = 0.5                              # kuruma
    goruntu = {"serit": {"degerler": degerler}}
    sayac = grafik._rvol_rozetleri(ax, goruntu, 60, [99.0] * 60)
    assert _yon_sayaci(sayac) == {"artis": 1, "dusus": 1}
    assert sorted(_rozetler(ax)) == ["⚡↑ x3,0", "⚡↓ x0,5"]
    renkler = {str(t.get_text())[1]: t.get_color() for t in ax.texts
               if str(t.get_text()).startswith("⚡")}
    assert renkler["↑"] == grafik.PALET["mum_yukselen"]
    assert renkler["↓"] == grafik.PALET["mum_dusen"]


def test_faz1_rozet_dusus_esigi_ve_hacimsiz_bar(monkeypatch):
    """Kuruma rozeti `≤ 0,5×`; hacimsiz bar (0/None) rozetlenmez (dipnotta bildirilir)."""
    esik_dusuk = float(grafik.SABITLER["rvol_rozet_esik_dusuk"])
    assert esik_dusuk == pytest.approx(0.5)
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    degerler[5] = esik_dusuk + 0.01                 # eşiğin hemen üstü: rozet yok
    degerler[30] = esik_dusuk                       # eşitlik: rozet var
    degerler[50] = 0.0                              # hacimsiz bar: rozet YOK
    goruntu = {"serit": {"degerler": degerler}}
    sayac = grafik._rvol_rozetleri(ax, goruntu, 60, [99.0] * 60)
    assert _yon_sayaci(sayac) == {"artis": 0, "dusus": 1}
    assert _rozetler(ax) == ["⚡↓ x0,5"]
    fig2, ax2 = _eksen(60)
    assert _yon_sayaci(grafik._rvol_rozetleri(ax2, {"serit": {"degerler": [0.0, None] + [1.0] * 58}},
                                  60, [99.0] * 60)) == {"artis": 0, "dusus": 0}


def test_faz1_rozet_esikleri_ortamla_ayarlanabilir(monkeypatch):
    """`GRAFIK_RVOL_ROZET_ESIK` / `_ESIK_DUSUK` (varsayılan 2,0 / 0,5; bozuk → varsayılan)."""
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    degerler[10] = 1.5                               # varsayılanda rozet YOK
    goruntu = {"serit": {"degerler": degerler}}
    assert _yon_sayaci(grafik._rvol_rozetleri(ax, goruntu, 60, [99.0] * 60)) == {"artis": 0, "dusus": 0}
    monkeypatch.setenv("GRAFIK_RVOL_ROZET_ESIK", "1,2")      # Türkçe virgül de okunur
    fig2, ax2 = _eksen(60)
    assert _yon_sayaci(grafik._rvol_rozetleri(ax2, goruntu, 60, [99.0] * 60)) == {"artis": 1, "dusus": 0}
    monkeypatch.setenv("GRAFIK_RVOL_ROZET_ESIK_DUSUK", "abc")  # bozuk → varsayılan (0,5)
    fig3, ax3 = _eksen(60)
    assert _yon_sayaci(grafik._rvol_rozetleri(ax3, {"serit": {"degerler": [0.6] * 60}},
                                  60, [99.0] * 60)) == {"artis": 0, "dusus": 0}


def test_faz1_rozet_metni_yuvarlamada_yanlis_yon_gostermez():
    """`x0,96` tek basamakta `x1,0` olurdu (kuruma "normal" görünürdü) — 2 basamak."""
    assert grafik._rvol_katı(0.96) == "0,96"
    assert grafik._rvol_katı(0.5) == "0,5"
    assert grafik._rvol_katı(2.04) == "2,04"          # eşik üstü `x2,0` yazmaz
    assert grafik._rvol_katı(3.4) == "3,4"
    assert grafik._rvol_katı(12.0) == "12,0"


def test_faz1_rozet_butcesi_iki_yone_yer_ayirir():
    """Sakin penceredeki sert kurumalar hacim PATLAMASINI kareden atamaz.

    Neden: sertliğe göre tam sıralamada 8 kuruma (x0,1 ≈ sertlik 10) belirgin bir
    patlamayı (x2,2 = sertlik 2,2) tamamen dışarıda bırakıyordu — asıl sinyal
    (kırılımı hacmin teyit etmesi) kaybolurdu.
    """
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    for i in range(0, 56, 7):                        # 8 sert kuruma (x0,1)
        degerler[i] = 0.1
    degerler[57] = 2.2                               # tek ve zayıf patlama
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert sayac["artis"] == 1
    assert 1 <= sayac["dusus"] <= int(grafik.SABITLER["rvol_rozet_dusus_maks"])
    assert "⚡↑ x2,2" in _rozetler(ax)


def test_faz1_kuruma_rozeti_en_fazla_iki(monkeypatch):
    """Kullanıcı (2026-10-16): "çok fazla etiket olmamalı, en fazla 2 tane".

    Kuruma rozeti kare başına 2 TAVAN; en sert iki kuruma seçilir (sakin 4s
    karesinde ↓7'ye çıkıyordu). Patlamalar kalan bütçeyi doldurur.
    """
    tavan = int(grafik.SABITLER["rvol_rozet_dusus_maks"])
    maks = int(grafik.SABITLER["rvol_rozet_maks"])
    assert tavan == 2
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    for i in range(0, 56, 7):                        # 8 kuruma, farklı sertlikte
        degerler[i] = 0.1 + 0.01 * (i // 7)
    degerler[55] = 0.05                              # en sert kuruma (sertlik 20)
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert _yon_sayaci(sayac) == {"artis": 0, "dusus": tavan}
    metinler = _rozetler(ax)
    assert len(metinler) == tavan
    assert "⚡↓ x0,05" in metinler                    # EN SERT kuruma her zaman girer
    # Tavan ortamla değiştirilebilir; 0 → kuruma rozeti kapanır, patlama kalır.
    monkeypatch.setenv("GRAFIK_RVOL_ROZET_DUSUS_MAKS", "0")
    fig2, ax2 = _eksen(60)
    karisik = [3.0] * 60
    karisik[10] = 0.2
    assert _yon_sayaci(grafik._rvol_rozetleri(ax2, {"serit": {"degerler": karisik}},
                                  60, [99.0] * 60)) == {"artis": maks, "dusus": 0}


def test_faz1_rozet_kapak_ve_esik_alti_cizilmez():
    fig, ax = _eksen(60)
    goruntu = {"serit": {"degerler": [1.9] * 60}}    # eşik altı: hiç rozet yok
    assert _yon_sayaci(grafik._rvol_rozetleri(ax, goruntu, 60, [99.0] * 60)) == {"artis": 0, "dusus": 0}
    fig2, ax2 = _eksen(60)
    cok = {"serit": {"degerler": [5.0] * 60}}
    maks = int(grafik.SABITLER["rvol_rozet_maks"])
    assert _yon_sayaci(grafik._rvol_rozetleri(ax2, cok, 60, [99.0] * 60)) == {"artis": maks, "dusus": 0}


def test_faz1_rozet_kapak_iki_yonu_birlikte_sayar():
    """Tek bütçe + sertlik sırası: `|log(RVOL)|` büyük olan önce yazılır.

    Patlama sertliği `v`, kuruma sertliği `1/v` (x0,25 → 4,0 = x4,0 patlama kadar
    sert). İkisi de eşiği aşarsa aynı bütçeyi paylaşırlar; toplam `rvol_rozet_maks`.
    """
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    for i in (0, 7, 14, 21):                         # 4 patlama (sertlik 9,0)
        degerler[i] = 9.0
    degerler[40] = 0.25                              # kuruma (sertlik 4,0)
    goruntu = {"serit": {"degerler": degerler}}
    maks = int(grafik.SABITLER["rvol_rozet_maks"])
    sayac = grafik._rvol_rozetleri(ax, goruntu, 60, [99.0] * 60)
    assert _yon_sayaci(sayac) == {"artis": 4, "dusus": 1}
    assert sayac["artis"] + sayac["dusus"] <= maks          # bütçe iki yönün TOPLAMI
    assert "⚡↓ x0,25" in _rozetler(ax)                     # eşiği aşan kuruma da girdi


# ------------------------------------------------------------- FAZ 2: akıllı kadraj


@pytest.mark.parametrize("tf, beklenen", [("1d", 62), ("4h", 68), ("2h", 74), ("1h", 80)])
def test_faz2_tf_matrisi_formasyon_yokken(tf, beklenen):
    g = _goruntu(_cerceve(240, tf), tf=tf, cift=None)
    assert g["kare_mum"] == beklenen and len(g["zamanlar"]) == beklenen


@pytest.mark.parametrize("genislik, beklenen", [(1, 35), (20, 35), (60, 69), (400, 85)])
def test_faz2_formasyon_kadraji_tampon_ve_sinirlar(genislik, beklenen):
    """Formasyon + 10 mum tampon; alt 35, üst 85 (plan Kural A).

    Beklenen pencere `n - start_bar + 10`un 35-85 aralığına kırpılmışıdır;
    pencere SONUNDA açık mum düşebildiği için n kareden okunur (açık bar çizilmez).
    """
    n = 500
    g = _goruntu(_cerceve(n, "1h"), "1h",
                 cift=_cift(start_bar=n - genislik, end_bar=n - 1))
    gercek_n = g["bar_sayisi"]
    assert len(g["zamanlar"]) == max(35, min(85, gercek_n - (n - genislik) + 10))
    assert len(g["zamanlar"]) == beklenen


def test_faz2_sag_bosluk_eksenin_yuzde_10_20():
    """Kullanıcı (2026-10-16): sağ boşluk eksen genişliğinin %10-20'si (hedef %15).

    Eski "sabit 12-15 mum" kuralı kareye göre kayıyordu (80 mumda %16, 35 mumluk
    formasyon karesinde %30); yüzde kuralı her karede aynı oranı verir.
    """
    assert float(grafik.SABITLER["sag_bosluk_orani"]) == pytest.approx(0.15)
    for n in (35, 62, 68, 74, 80, 85):
        g = grafik.sag_bosluk_mum(n)
        oran = 100.0 * g / (n + 0.2 + g)
        assert 10.0 <= oran <= 20.0, (n, g, oran)


# --------------------------------------------------- FAZ 3: SMC motoru ve çizim


def test_faz3_taze_ob_canli_dolmus_ob_gri():
    """Taze OB %25 canlı düz kontur; kısmen dolmuşta kalan %12 + dolan mat gri."""
    d = grafik.SABITLER["doldurma"]
    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="ob", yon=1, alt=100.0, ust=102.0,
                                             x0=10, x1=40, doluluk=0.0)]},
                     60, (90.0, 120.0), [])
    taze = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    assert len(taze) == 1
    assert float(taze[0].get_alpha()) == pytest.approx(float(d["ob_taze"]))
    assert taze[0].get_linestyle() == "solid"        # düz dış çizgi

    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="ob", yon=1, alt=100.0, ust=102.0,
                                             x0=10, x1=40, doluluk=0.41)]},
                     60, (90.0, 120.0), [])
    dolu = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    assert len(dolu) == 2                            # kalan + dolan (gri) = iki bant
    alfa = sorted(float(p.get_alpha()) for p in dolu)
    assert alfa[0] == pytest.approx(float(d["ob_dolan"]), abs=0.03)
    assert alfa[1] == pytest.approx(float(d["ob_kalan"]))
    from matplotlib.colors import to_rgb

    gri = to_rgb(grafik.PALET["dolan"])
    assert any(tuple(round(float(c), 2) for c in p.get_facecolor()[:3])
               == tuple(round(c, 2) for c in gri) for p in dolu)
    kenar = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] == 0]
    assert any(p.get_linestyle() not in ("-", "solid") for p in kenar)   # kısmen: kesikli


def test_faz3_kirilan_ob_bosalir_iz_kalir():
    """Geçersizleşen/kırılan OB: içi BOŞALIR, yalnız çok silik bir iz kalır."""
    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="ob", yon=1, alt=100.0, ust=102.0,
                                             x0=10, x1=40, durum="INVALID",
                                             tamamlandi=True)]}, 60, (90.0, 120.0), [])
    dolgular = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    assert len(dolgular) == 1
    assert float(dolgular[0].get_alpha()) <= float(grafik.SABITLER["doldurma"]["kapanan"])


def test_faz3_fvg_doluluk_hesabi_yapmaz_ve_turkuaz_mor():
    """FVG: tek ton (turkuaz boğa / mor ayı), kesikli ince kontur, yüzde yok."""
    from matplotlib.colors import to_rgb

    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="fvg", yon=1, alt=100.0, ust=102.0,
                                             x0=10, x1=40, doluluk=0.62)]},
                     60, (90.0, 120.0), [])
    dolgular = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0]
    assert len(dolgular) == 1                        # doluluk bölmesi YOK
    beklenen = tuple(round(c, 2) for c in to_rgb(grafik.PALET["fvg_bull"]))
    assert tuple(round(float(c), 2) for c in dolgular[0].get_facecolor()[:3]) == beklenen
    kenar = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] == 0]
    assert kenar and all(p.get_linestyle() not in ("-", "solid") for p in kenar)
    assert grafik._zone_metni({"tip": "fvg", "yon": 1, "doluluk": 0.62}) == "FVG↑ · durum bilinmiyor"

    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [_bolge(tip="fvg", yon=-1, alt=100.0, ust=102.0,
                                             x0=10, x1=40)]}, 60, (90.0, 120.0), [])
    ayi = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_facecolor()[3] > 0][0]
    assert tuple(round(float(c), 2) for c in ayi.get_facecolor()[:3]) == tuple(
        round(c, 2) for c in to_rgb(grafik.PALET["fvg_bear"]))


def test_faz3_ob_boga_ayi_renk_gruplari_ayri():
    """OB yeşil/kırmızı, FVG turkuaz/mor: iki grup tek bakışta karışmaz."""
    fig, ax = _eksen(60)
    grafik._zone_ciz(ax, {"cizilen": [
        _bolge(tip="ob", yon=1, alt=100.0, ust=110.0, x0=10, x1=20),
        _bolge(tip="ob", yon=-1, alt=112.0, ust=118.0, x0=10, x1=20, vurgu="ust"),
    ]}, 60, (90.0, 120.0), [])
    renkler = {ln.get_color() for ln in ax.lines if len(ln.get_xdata()) == 2}
    assert grafik.PALET["ob_bull"] in renkler and grafik.PALET["ob_bear"] in renkler
    assert grafik._zone_renk({"tip": "fvg", "yon": -1}) == grafik.PALET["fvg_bear"]


def test_faz3_kirilim_cizgisi_pivot_baslar_kirilim_mumunda_biter():
    """Line Truncation: BOS ekranı boydan boya katetmez; aktif hedef sağa uzar."""
    n = 60
    fig, ax = _eksen(n)
    goruntu = _olay_goruntusu()
    for b in goruntu["olay"]["olaylar"]:
        b["pivot_bar"] = 8
    goruntu["olay"]["kritik"] = {"seviye": 98.0, "bar": 50, "pivot_bar": 8,
                                 "tur": "CHoCH", "yon": "alt"}
    grafik._olay_ciz(ax, goruntu, n, [], sag_bosluk=15)
    cizgiler = {float(ln.get_ydata()[0]): [float(v) for v in ln.get_xdata()]
                for ln in ax.lines if len(ln.get_ydata()) == 2
                and ln.get_ydata()[0] == ln.get_ydata()[1]}
    assert cizgiler[102.0] == [8.0, 40.0]                 # pivot → kırılım mumu
    assert cizgiler[98.0] == [8.0, n - 1 + 15]            # aktif hedef sağ boşluğa


def test_faz3_pivot_yoksa_kirilim_mumundan_baslar():
    """Motorun `origin_source_bar`ı yoksa uydurulmaz: çizgi kırılım mumundan başlar."""
    n = 60
    fig, ax = _eksen(n)
    grafik._olay_ciz(ax, _olay_goruntusu(), n, [], sag_bosluk=0)
    cizgiler = {float(ln.get_ydata()[0]): [float(v) for v in ln.get_xdata()]
                for ln in ax.lines if len(ln.get_ydata()) == 2
                and ln.get_ydata()[0] == ln.get_ydata()[1]}
    assert cizgiler[102.0] == [40.0, 40.0] and cizgiler[98.0] == [50.0, 50.0]


def test_faz3_mitigated_yuzdesi_kutu_metnine_girer():
    assert grafik._zone_metni({"tip": "ob", "yon": 1, "doluluk": 0.41}) == "OB↑ · durum bilinmiyor · dolum %41"
    assert grafik._zone_metni({"tip": "ob", "yon": 1, "doluluk": 0.0}) == "OB↑ · durum bilinmiyor · dolum %0"


# ----------------------------------------------------------- FAZ 4: fintech cila


def test_faz4_baslik_rozetleri_yarisaydam_pills():
    """Üst sol: `[ ◆ SEMBOL · TF ]` `[ ◈ Formasyon (%q) ]` rozetleri."""
    metin = grafik._metinler(_goruntu(), {"mum_sayisi": 50, "hacimsiz_bar": 0}, 1080,
                             [], False)
    rozetler = metin["pill_listesi"]
    assert rozetler and rozetler[0]["metin"].endswith("· 1S")
    assert "Simetrik Üçgen" in rozetler[1]["metin"] and "kalite 88/100" in rozetler[1]["metin"]
    assert all(r.get("dolgu") and r.get("kenar") for r in rozetler)


def test_faz4_rozetler_ust_seritte_ve_yarı_saydam(tmp_path):
    fig, meta, _ = _kare_ciz(_goruntu(), "1h", tmp_path)
    # Başlık bloğu artık düz metin değil: `fig.texts` içinde en az 3 kutu (rozet)
    cipler = [t for t in fig.texts if t.get_bbox_patch() is not None]
    assert len(cipler) >= 3
    for cip in cipler:
        assert float(cip.get_bbox_patch().get_alpha()) <= 0.8    # yarı saydam


def test_faz4_sag_etiketler_kaydirilir_ve_lider_cizgisi_alir():
    """Sağ ray: çakışan etiket Y-Offset ile ayrışır, gerçek seviyeye lider ile bağlanır."""
    fig, ax = _eksen(60)
    # Kaynaklar FARKLI: aynı seviyedeki `zone` çipleri tek satırda birleşiyor
    # (GÖRSEL-5 okunurluk kuralı), o yüzden çakışma denetimi çok kaynakla ölçülür.
    adaylar = [{"kaynak": kn, "x": 59.6, "y": 100.0 + i * 0.6, "metin": f"{kn} {i}",
                "renk": grafik.PALET["ob_bull"], "sabit": False, "oncelik": 2,
                "bg": None, "yeni": 50.0 - i}
               for i, kn in enumerate(("olay", "alarm", "swing", "son"))]
    for a in adaylar[1:]:
        a["oncelik"] = 5
    ozet = grafik._sag_ciz(ax, fig, adaylar, 60, (90.0, 120.0), x_kenar=59.6 + 15)
    assert ozet["yerlesen"] == 4
    assert ozet["kaydirilan"] >= 1 and ozet["lider"] >= 1
    assert ozet["yerlesen"] - ozet["atlanan"] == 4
    # Kaydırılan etiketlerde lider çizgisi kesikli
    oklar = [t for t in ax.texts if t.arrowprops]
    assert oklar and all("linestyle" in t.arrowprops for t in oklar)


def test_faz4_pivot_etiketleri_fitilden_10_15_px_uzak():
    """HH/HL/LH/LL metni mum fitiline değmez: taban ofset 10-15 px (piksel ölçümü)."""
    g = _goruntu()
    g["olay"] = {"swinglar": [{"bar": 30, "fiyat": 52.0, "yon": "ust", "sinif": "HH",
                               "durum": "teyitli"}],
                 "seviyeler": [], "olaylar": [], "kritik": {}, "cizilen": 1,
                 "elenen": 0, "kapak": {}, "hata": []}
    fig, ax = _eksen(60)
    ax.set_ylim(45.0, 55.0)
    grafik._olay_ciz(ax, g, 60, [])
    assert not [t for t in ax.texts if t.get_text() in ("HH", "HL", "LH", "LL")]
    assert not [ln for ln in ax.lines if ln.get_marker() in ("^", "v")]


def test_faz4_hedef_kutusu_teyitli_alarmda_cizilir():
    """🎯 hedef = kırılan seviye + yön × formasyon yüksekliği (ölçülü hareket)."""
    fig, ax = _eksen(60)
    ax.set_ylim(45.0, 55.0)
    alarm = {"tur": "teyit", "deger": 52.0, "yon": 1, "bar": 50, "hedef": 54.0,
             "durum": "KIRILIM_TEYITLI"}
    sag: list = []
    grafik._alarm_ciz(ax, alarm, 60, 300.0, sag)
    kutular = [p for p in ax.patches if isinstance(p, Rectangle)
               and p.get_linestyle() not in ("-", "solid")]
    assert kutular and any(abs(float(p.get_y()) - 54.0) < 2.0 for p in kutular)
    etiket = [t for t in ax.texts if "Hedef" in str(t.get_text())]
    assert etiket and "54" in str(etiket[0].get_text())
    # Ok, kırılım seviyesinden hedefe uzanır (kesikli)
    assert any(abs(float(t.xy[1]) - 54.0) < 1e-6 for t in ax.texts if "Hedef" in str(t.get_text()))


def test_faz4_hedef_yonu_ve_genisligi_yoksa_cizilmez():
    """Yön ya da formasyon genişliği yoksa hedef ÜRETİLMEZ (uydurma seviye yok)."""
    goruntu = {"formasyon": {"upper_now": 52.5, "lower_now": 49.5}, "son_kapanis": 52.0}
    kopya = grafik._alarm_kopyala({"state": "KIRILIM_TEYITLI", "break_price": 52.5}, None,
                                  None, 0, 60, goruntu)
    assert kopya["hedef"] is None
    goruntu2 = {"formasyon": {"upper_now": 52.5, "lower_now": 49.5, "current_width": 3.0},
                "son_kapanis": 52.0}
    kopya2 = grafik._alarm_kopyala({"state": "KIRILIM_TEYITLI", "break_price": 52.5,
                                    "break_dir": 1}, None, None, 0, 60, goruntu2)
    assert kopya2["hedef"] == pytest.approx(55.5)
    # Aday/geçersiz alarmlarda projeksiyon yok
    goruntu3 = {"formasyon": {"upper_now": 52.5, "current_width": 3.0}, "son_kapanis": 52.0}
    aday = grafik._alarm_kopyala({"state": "KIRILIM_ADAYI", "break_price": 52.5,
                                  "break_dir": 1}, None, None, 0, 60, goruntu3)
    assert aday["hedef"] is None


def test_faz4_ikon_tofu_cizmez():
    """Kare içi ikonlar font kapsamasına göre seçilir: asla 'tofu' kutusu olmaz."""
    sembol = grafik._ikon("sembol")
    formasyon = grafik._ikon("formasyon")
    assert sembol in ("📈", "◆") and formasyon in ("📐", "◈")
    # Seçilen işaret AKTİF fontta bulunmalı (yoksa çizimde kutu/tofu olurdu).
    assert grafik._font_emoji_var(sembol) and grafik._font_emoji_var(formasyon)
    assert grafik._font_emoji_var(grafik._ikon("hedef"))

def test_faz1_taze_rozet_gecikmez_dusus():
    """Kullanıcı (2026-10-16): "bu sistem sadece geçmişi filtreler, yeni geleni
    geciktirebilir".

    Ölçüm (kural öncesi, gerçek önbellek): son mumun rozeti DÖRT karede de
    düşüyordu — GARAN 4s son bar RVOL 0,16 · THYAO 4s 0,18 · AKBNK 4s 0,17 ·
    GARAN 1s 0,47 (hepsi kuruma eşiğinin altında). Yeni kural: her yönün en taze
    uygun mumu rozet alır; eskiler kalan yerleri doldurur.
    """
    fig, ax = _eksen(60)
    degerler = [0.10] * 40                            # eski, çok sert kurumalar
    degerler += [1.0] * 19
    degerler.append(0.45)                             # SON mum: hafif kuruma
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert sayac["taze_dusus"] == 59                  # taze rozet ÇİZİLDİ
    assert 59 in {int(round(float(t.xy[0]))) for t in ax.texts
                  if str(t.get_text()).startswith("⚡")}
    assert "⚡↓ x0,45" in _rozetler(ax)               # son mumun kendi değeri yazıldı
    assert _yon_sayaci(sayac) == {"artis": 0, "dusus": 2}   # taze + bir eski = tavan


def test_faz1_taze_rozet_gecikmez_artis():
    """Taze PATLAMA da garanti: 8 sert eski patlama bütçeyi doldursa bile son mum girer."""
    fig, ax = _eksen(60)
    degerler = [9.0] * 8 + [1.0] * 51
    degerler.append(2.05)                             # SON mum: hafif patlama
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert sayac["taze_artis"] == 59
    assert "⚡↑ x2,05" in _rozetler(ax)
    assert sayac["artis"] + sayac["dusus"] <= int(grafik.SABITLER["rvol_rozet_maks"])


def test_faz1_taze_rozet_aralik_cakismasinda_eski_duser():
    """Taze rozet ile eski aday arasında `min_ara`'dan az bar varsa DÜŞEN ESKİ olur."""
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    degerler[55] = 0.05                               # çok sert eski kuruma
    degerler[58] = 0.40                               # taze ile komşu kuruma
    degerler[59] = 0.45                               # taze kuruma
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    barlar = {int(round(float(t.xy[0]))) for t in ax.texts
              if str(t.get_text()).startswith("⚡")}
    assert 59 in barlar                               # taze (en yeni) yazıldı
    assert 55 not in barlar                           # aralık çakışmasında eski düştü
    assert sayac["taze_dusus"] == 59


def test_faz1_taze_uygun_mum_yoksa_izler_none():
    """Pencerede taze uygun mum yoksa davranış eskisi gibi (sertlik sırası), izler None."""
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    degerler[10] = 3.0
    degerler[30] = 0.4
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert _yon_sayaci(sayac) == {"artis": 1, "dusus": 1}
    assert sayac["taze_artis"] == 10 and sayac["taze_dusus"] == 30   # tek uygun onlar


def test_faz1_taze_kuruma_kapatilinca_patlama_korunur():
    """Kuruma tavanı 0'a çekilse bile TAZE PATLAMA yer bulur (garanti bütçeden bağımsız)."""
    fig, ax = _eksen(60)
    degerler = [1.0] * 60
    for i in range(8):
        degerler[i] = 9.0
    degerler[59] = 2.1
    sayac = grafik._rvol_rozetleri(ax, {"serit": {"degerler": degerler}},
                                   60, [99.0] * 60)
    assert sayac["taze_artis"] == 59 and sayac["dusus"] == 0


def test_faz1_gercek_karede_son_mumun_rozeti_cizilir():
    """Gerçek önbellek: 4s karelerinde son mum kuruma eşiğinin altındaysa rozeti ÇIKAR.

    Bu, "yeni gelen sinyal gecikmesin" kuralının canlı veriyle kapısıdır: kural
    öncesi GARAN/THYAO/AKBNK 4s karelerinde son mumun rozeti hiç çizilmiyordu.
    """
    import grafik_uret

    kare = 0
    for hisse in ("GARAN", "THYAO", "AKBNK"):
        sonuc = grafik_uret.kare_uret(hisse, "4h", veri_dizin="bot_data", zone=True,
                                      cikti=f"/tmp/kare/_taze_{hisse}.png")
        m = sonuc["meta"]["serit"]
        if m["kaynak"] == "yok":
            continue
        kare += 1
        esik_dusuk = float(grafik.SABITLER["rvol_rozet_esik_dusuk"])
        esik = float(grafik.SABITLER["rvol_rozet_esik"])
        mum = sonuc["meta"]["mum_sayisi"]
        son = m["rozet_taze_dusus"]
        if son is None and m["rozet_taze_artis"] is not None:
            continue                                  # son uygun mum patlamaydı
        assert son is not None, (f"{hisse}: taze rozet düşmüş "
                                 f"(artis={m['rozet_taze_artis']}, dusus={m['rozet_taze_dusus']})")
        assert 0 <= son < mum
        assert esik_dusuk < esik
    assert kare > 0, "hiç gerçek kare üretilemedi"

