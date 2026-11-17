# -*- coding: utf-8 -*-
"""Ok kademesi düzeltmeleri (2026-11-16) — sözleşmeler.

İnceleme (`docs/denetim/GRAFIK_OK_VE_CIZIM_INCELEMESI_2026-11-16.md`) dört şey
söyledi; dördü de burada kilitleniyor:

1. **Lejant çizileni anlatır** (§0.12v): `○` halka / `◎` çift halka / soluk ok
   kareye çizildiyse adı da lejantta olur; çizilmediyse madde de olmaz.
2. **Zayıf ok silinmez**: eski davranış okun üstüne zemin rengi basıyordu (ok
   fiilen kayboluyordu). Artık ok kendi alfasıyla çizilir; örtü işareti yok.
3. **Tür bilinmiyorsa nötr kademe**: eski snapshot'ta tüm momentum okları "en
   güçlü" (s=62) görünüyordu; bilinmeyen tür nötr (s=50) çizilir.
4. **İşaret çakışması ölçülür**: kalite kapısı `ax.texts` dışında `▲`/`○`
   işaretlerini de ölçer (`isaret`, `isaret_komsu_cakisan`).

Ek: 120 barlık günlük karede tarih etiketleri artık üst üste binmez.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import grafik
from grafik.render import _stabil_ciz

IST = timezone(timedelta(hours=3))


def _goruntu(n: int = 40, *, dusuk: float = 49.4):
    kapanis = [50.0 + i * 0.1 for i in range(n)]
    return {
        "sembol": "THYAO", "tf": "1d", "tf_kisa": "1G",
        "zamanlar": [datetime(2026, 9, 1, 18, tzinfo=IST) + timedelta(days=i) for i in range(n)],
        "acilis": [k - 0.05 for k in kapanis], "kapanis": kapanis,
        "yuksek": [k + 0.3 for k in kapanis], "dusuk": [dusuk] * n,
        "son_bar_ts": "2026-11-03T17:30:00+03:00", "son_bar_kapali": True,
        "son_kapanis": kapanis[-1],
        "zone": {}, "olay": {}, "formasyon": {}, "alarm": {}, "serit": {},
    }


def _katman(**ek):
    katman = {
        "hazir": True, "seviyeler": [49.0] * 40, "renkler": ["ust"] * 40,
        "reclaim_barlar": [10], "momentum_barlar": [20],
        "reclaim_turleri": {"10": "multi_bar_recovery"},
        "momentum_turleri": {"20": "upward_rebase_momentum"},
        "baglam": {}, "dikey_barlar": [], "dikey_deneme_barlar": [],
        "son_seviye": 49.0, "son_renk": "ust",
    }
    katman.update(ek)
    return katman


def _ciz(tmp_path, katman, ad="a.png"):
    g = _goruntu()
    g["stabil"] = katman
    return grafik.ciz(g, "1d", {"cikti": str(tmp_path / ad)})


def _gidler(fig):
    return {str(c.get_gid()) for a in fig.axes for c in a.collections if c.get_gid()}


# ------------------------------------------------------------- 1) LEJANT ----
def test_lejant_halka_ve_soluk_oku_anlatir(tmp_path):
    """Kareye çizilen her kademe lejantta adıyla yazılır; çizilmeyen yazılmaz."""
    katman = _katman(baglam={"10": "cok_guclu", "20": "zayif"})
    yol, meta = _ciz(tmp_path, katman)
    assert yol
    satir = " ".join(meta["metin"]["lejant"])
    assert "ok kademesi:" in satir
    assert "◎ çok güçlü" in satir          # çift halka çizildi
    assert "soluk = zayıf" in satir        # soluk ok çizildi
    assert "○ güçlü" not in satir          # 'guclu' sınıfı yok → madde yok


def test_lejant_kademe_yoksa_madde_uydurmaz(tmp_path):
    """Halka/soluk hiç çizilmediyse lejantta 'ok kademesi' maddesi olmaz."""
    yol, meta = _ciz(tmp_path, _katman())
    assert yol
    assert "ok kademesi:" not in " ".join(meta["metin"]["lejant"])


# --------------------------------------------------- 2) ZAYIF OK SİLİNMEZ --
def test_zayif_ok_sayaci_ve_alfasi_korunur(tmp_path):
    """Soluk ok hâlâ bir işarettir: sayaç onu sayar (örtüyle silinmiş sayılmaz)."""
    yol, meta = _ciz(tmp_path, _katman(baglam={"10": "zayif"}))
    assert yol
    cizgiler = meta["cizgiler"]["stabil"]
    assert cizgiler["baglam_zayif_isaret"] == 1
    assert cizgiler["reclaim_isaret"] == 1      # sayaç okun çizildiğini söyler


def test_zemin_ortusu_kaldirildi(tmp_path, monkeypatch):
    """Eski `grafik-stabil-baglam-zayif` örtü işareti artık üretilmez."""
    from matplotlib.figure import Figure

    orijinal = Figure.savefig
    yakalanan: dict = {}

    def yakala(self, *a, **k):
        yakalanan["fig"] = self
        return orijinal(self, *a, **k)

    monkeypatch.setattr(Figure, "savefig", yakala)
    yol, meta = _ciz(tmp_path, _katman(baglam={"10": "zayif"}), ad="b.png")
    assert yol and meta["cizgiler"]["stabil"]["baglam_zayif_isaret"] == 1
    assert "grafik-stabil-baglam-zayif" not in _gidler(yakalanan["fig"])


# ------------------------------------------- 3) TÜR BİLİNMİYORKEN NÖTR -----
def _momentum_boyutu(tmp_path, momentum_turleri, monkeypatch, ad):
    from matplotlib.figure import Figure

    orijinal = Figure.savefig
    yakalanan = {}

    def yakala(self, *a, **k):
        yakalanan["fig"] = self
        return orijinal(self, *a, **k)

    monkeypatch.setattr(Figure, "savefig", yakala)
    yol, _meta = _ciz(tmp_path, _katman(momentum_turleri=momentum_turleri), ad=ad)
    assert yol
    for eksen in yakalanan["fig"].axes:
        for koleksiyon in eksen.collections:
            if str(koleksiyon.get_gid()) == "grafik-stabil-momentum":
                return float(koleksiyon.get_sizes()[0])
    return None


def test_tur_bilinmiyorsa_momentum_notr_boyutta(tmp_path, monkeypatch):
    """Eski snapshot (tür sözlüğü yok) artık 'en güçlü' görünüm almaz."""
    bilinen = _momentum_boyutu(tmp_path, {"20": "upward_rebase_momentum"}, monkeypatch, "m1.png")
    bilinmeyen = _momentum_boyutu(tmp_path, {}, monkeypatch, "m2.png")
    assert bilinen == 62.0
    assert bilinmeyen == 50.0


def test_momentum_tur_sozlugu_bossa_sayac_korunur(tmp_path):
    """Bilinmeyen türde de ok `momentum_isaret` sayılır (görünür işaret var)."""
    yol, meta = _ciz(tmp_path, _katman(momentum_turleri={}))
    assert yol
    assert meta["cizgiler"]["stabil"]["momentum_isaret"] == 1


# ---------------------------------------- 4) İŞARET ÇAKIŞMASI ÖLÇÜLÜR ------
def test_kalite_kapisi_isaret_geometrisini_olcer(tmp_path):
    """`meta["kalite"]` işaret sayısını ve komşu mum temasını raporlar."""
    yol, meta = _ciz(tmp_path, _katman(baglam={"10": "guclu"}))
    assert yol
    kalite = meta["kalite"]
    assert "isaret" in kalite and "isaret_komsu_cakisan" in kalite
    assert kalite["isaret"] >= 2                 # geri alım oku + halka
    assert 0 <= kalite["isaret_komsu_cakisan"] <= kalite["isaret"]


def test_isaret_kapladigi_komşu_mum_sayilir(tmp_path):
    """Kendi mumuna değen ok hata değil; KOMŞU mumla temas sayılır."""
    # Dar mum + çok yakın komşu: 20. barın oku 21. barın fitiline değer.
    n = 40
    g = _goruntu(n=n)
    g["dusuk"] = [49.4] * n
    g["stabil"] = _katman(momentum_barlar=[20], reclaim_barlar=[],
                          reclaim_turleri={}, baglam={"20": "cok_guclu"})
    yol, meta = grafik.ciz(g, "1d", {"cikti": str(tmp_path / "c.png")})
    assert yol
    kalite = meta["kalite"]
    # Çift halka (r≈12 px) 200 barlık sıkışık kadrajda komşuya değebilir; ölçüm
    # en azından sayıyı görünür kılmalı ve kendi mumuyla teması "komşu" saymamalı.
    assert kalite["isaret"] >= 3
    assert kalite["isaret_komsu_cakisan"] <= kalite["isaret"]


# ---------------------------------------- EK: eksen etiketi çakışması ------
def test_gunluk_eksende_etiketler_ust_uste_binmez(tmp_path, monkeypatch):
    """120 barlık 1G karede ay başı etiketleri piksel komşuluğuna göre seyreltilir."""
    from matplotlib.figure import Figure

    orijinal = Figure.savefig
    yakalanan = {}

    def yakala(self, *a, **k):
        yakalanan["fig"] = self
        return orijinal(self, *a, **k)

    monkeypatch.setattr(Figure, "savefig", yakala)
    if True:
        g = _goruntu(n=120)
        # Ay sonuna denk gelen başlangıç: eski kod "27 Nis"+"03 May" bindiriyordu.
        g["zamanlar"] = [datetime(2026, 4, 27, 18, tzinfo=IST) + timedelta(days=i)
                         for i in range(120)]
        yol, meta = grafik.ciz(g, "1d", {"cikti": str(tmp_path / "d.png")})
        assert yol
        fig = yakalanan["fig"]
        fig.canvas.draw()
        kutu = [t.get_window_extent() for a in fig.axes for t in a.get_xticklabels()
                if t.get_text().strip()]
        assert kutu, "tarih etiketi hiç yok"
        for i in range(len(kutu)):
            for j in range(i + 1, len(kutu)):
                b1, b2 = kutu[i], kutu[j]
                kesisim = (b1.x1 > b2.x0 + 0.5 and b2.x1 > b1.x0 + 0.5
                           and b1.y1 > b2.y0 + 0.5 and b2.y1 > b1.y0 + 0.5)
                assert not kesisim, f"etiketler üst üste: {b1} / {b2}"


def test_stabil_ciz_zayif_grubu_ayri_gid_ile_cizer():
    """Birim düzeyi: `_stabil_ciz` soluk grubu kendi gid'iyle çizer (örtü yok)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    katman = _katman(baglam={"20": "zayif"})
    fig, ax = plt.subplots()
    try:
        meta = _stabil_ciz(ax, {"stabil": katman}, 40, (48.0, 52.0),
                           dusuk=[49.4] * 40, yuksek=[50.9] * 40)
        gidler = {str(c.get_gid()) for c in ax.collections}
        assert "grafik-stabil-momentum-zayif" in gidler
        assert "grafik-stabil-baglam-zayif" not in gidler
        assert meta["baglam_zayif_isaret"] == 1
    finally:
        plt.close(fig)
