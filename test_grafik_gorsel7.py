# -*- coding: utf-8 -*-
"""GÖRSEL-7 paketi: geçersizleşme kâresinin işaretleri + lejant taşması.

Kullanıcı kararları (2026-10-15, onaylı tur):
  * Geçersizleşme kâresinde ÜÇ yeni işaret: `✕ geçersizleştiren mum`, `┈ teyit
    sınırı` (+ sağ çipte `× 38,79 üstü kapanış`) ve soluk `✕ eski seviye`.
  * Kırmızı `lejant: N madde sığmadı` dipnotu kaldırıldı; sayı `meta`da kalıyor.
  * Lejant taşarsa önce UZUN ve düşük öncelikli maddeler düşer; geçersizleşme
    işaretleri (✕/┈) hiçbir koşulda düşmez — yoksa kare açıklamasız işaret bırakır.

Ölçüler gerçek kareden alındı (AKBNK 4h: kırılan 70,75 · teyit sınırı 70,84; bu
fark 1,4 px olduğu için soluk seviye çizgisi ÇİZİLMEZ, yalnız çip kalır).
"""

from __future__ import annotations

import grafik


def _eksen(n=60, alt=60.0, ust=80.0):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(alt, ust)
    return fig, ax


def _yatay(ax):
    """Eksendeki YATAY çizgiler (düşey alarm mumu çizgisi hariç)."""
    return [c for c in ax.lines if len(c.get_ydata()) and c.get_ydata()[0] == c.get_ydata()[-1]]


def _goruntu(formasyon=None, alarm=None):
    return {"formasyon": dict(formasyon or {}), "alarm": dict(alarm or {}),
            "yuksek": [70.0, 71.0, 72.0] * 20, "dusuk": [69.0, 68.5, 69.5] * 20,
            "zamanlar": list(range(60)), "tf": "4h"}


# ---------------------------------------------------------------- alarm tanımı


def test_alarm_gecersizde_teyit_siniri_ve_yonu_tasir():
    """Kural: eşik GÜNCEL bant sınırıdır (notifier `× geçersiz` satırıyla aynı)."""
    goruntu = _goruntu({"upper_now": 76.9, "lower_now": 70.8})
    for yon, beklenen in ((-1, 70.8), (1, 76.9)):
        cift = {"state": "KIRILIM_GECERSIZLESTI", "break_dir": yon, "break_price": 70.75}
        alarm = grafik._alarm_kopyala(cift, "gecersiz", 41, 0, 60, goruntu)
        assert alarm["tur"] == "gecersiz" and alarm["yon"] == yon
        assert alarm["teyit_siniri"] == beklenen
        assert alarm["deger"] == 70.75          # kırılan (dondurulmuş) seviye ayrı kalır


def test_alarm_yonu_durum_adindan_cikarilir():
    """Motor `break_dir` vermezse durum adından okunur; okunamazsa 0 (uydurma yok)."""
    goruntu = _goruntu({"upper_now": 76.9, "lower_now": 70.8})
    alarm = grafik._alarm_kopyala({"state": "KIRILIM_GECERSIZ"}, "gecersiz", 5, 0, 60, goruntu)
    assert alarm["yon"] == 0 and alarm["teyit_siniri"] is None


# ------------------------------------------------------------------ ✕/┈ katmanı


def test_gecersiz_katmani_klavuz_ve_cip_ekler():
    fig, ax = _eksen()
    sag: list = []
    uyari = _goruntu({"upper_now": 76.9, "lower_now": 70.84},
                    {"tur": "gecersiz", "yon": -1, "teyit_siniri": 70.84, "deger": 70.75,
                     "bar": 41})
    grafik._gecersiz_katmani(ax, uyari, uyari["alarm"], sag, 60)
    cip = [c for c in sag if str(c.get("kaynak")) == "gecersiz"]
    assert len(cip) == 1
    assert cip[0]["metin"] == "× 70,84 üstü kapanış"
    assert cip[0]["renk"] == grafik.PALET["olay"]
    # Noktalı kılavuz çizgisi + ✕ işareti eksende: yatay çizgi 1, yazı 1 arttı.
    assert any(abs(float(c.get_ydata()[0]) - 70.84) < 1e-6 for c in _yatay(ax))
    assert any(t.get_text() == "✕" for t in ax.texts)


def test_gecersiz_katmani_teyitli_alarmda_hicbir_sey_eklemez():
    fig, ax = _eksen()
    sag: list = []
    uyari = _goruntu({"upper_now": 76.9, "lower_now": 70.84},
                     {"tur": "teyit", "yon": -1, "teyit_siniri": 70.84, "bar": 41})
    grafik._gecersiz_katmani(ax, uyari, uyari["alarm"], sag, 60)
    assert sag == [] and not ax.texts


def test_soluk_eski_seviye_cizgisi_cakisinca_cizilmez():
    """İki seviye 0,02×aralıktan yakınsa tek çizgi kalır (üst üste binen çizgi okunmaz)."""
    fig, ax = _eksen()                        # aralık 20 → sınır 0,4
    sag: list = []
    # 70,75 ile 70,84 arası 0,09 < 0,4 → soluk çizgi YOK, çip VAR
    grafik._alarm_ciz(ax, {"tur": "gecersiz", "deger": 70.75, "bar": 41,
                           "teyit_siniri": 70.84}, 60, 300.0, sag)
    assert _yatay(ax) == []
    assert sag and sag[0]["metin"] == "✕ eski seviye 70,75"
    # Uzak seviyede ise çizgi çizilir (aynı sözleşme, ölçü büyük)
    fig2, ax2 = _eksen()
    sag2: list = []
    grafik._alarm_ciz(ax2, {"tur": "gecersiz", "deger": 62.0, "bar": 41,
                            "teyit_siniri": 70.84}, 60, 300.0, sag2)
    assert len(_yatay(ax2)) == 1


# ---------------------------------------------------------------------- lejant


def test_lejant_gecersizlesmede_yeni_maddeleri_yazar():
    oge = grafik._lejant(_goruntu({"upper_now": 76.9, "lower_now": 70.8},
                                  {"tur": "gecersiz", "bar": 41, "deger": 70.75,
                                   "teyit_siniri": 70.84}), False)
    assert "✕ geçersizleştiren mum" in oge
    assert "✕ eski seviye (artık geçerli değil)" in oge
    assert "┈ teyit sınırı" in oge
    assert "│ alarm mumu" not in oge and "─ seviye" not in oge


def test_lejant_teyitli_alarmda_eski_dili_korur():
    oge = grafik._lejant(_goruntu({"upper_now": 76.9, "lower_now": 70.8},
                                  {"tur": "teyit", "bar": 41, "deger": 70.75,
                                   "teyit_siniri": 70.84}), False)
    assert "│ alarm mumu" in oge and "─ seviye" in oge
    assert not any("✕ geçersizleştiren" in x or "teyit sınırı" in x for x in oge)


def test_lejant_tasmada_gecersizlik_maddeleri_dusurulmez():
    """Kare 2 satır taşır; sıra önemli — ✕/┈ maddeleri her koşulda ayakta kalır."""
    oge = [f"uzun aciklama maddesi {i}" for i in range(20)]
    oge += ["✕ geçersizleştiren mum", "┈ teyit sınırı", "✕ eski seviye (artık geçerli değil)"]
    satirlar, punto, atlanan = grafik._lejant_satirlar(oge, 1080)
    metin = " ".join(satirlar)
    assert len(satirlar) <= 2 and atlanan > 0
    assert "✕ geçersizleştiren mum" in metin
    assert "┈ teyit sınırı" in metin
    assert "✕ eski seviye (artık geçerli değil)" in metin
    assert "uzun aciklama maddesi 19" not in metin      # en uzunlar düştü
    assert "sığmadı" not in metin


def test_lejant_tasmasi_kareye_yazilmaz_meta_da_sayilir(monkeypatch):
    """`lejant: N madde sığmadı` kırmızı dipnotu KALKTI (okunurluk)."""
    import grafik_uret

    d = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True, mum=140,
                              cikti="/tmp/kare/_p7_lejant.png")
    meta = d.get("meta") or {}
    if not meta.get("metin"):
        import pytest
        pytest.skip("çerçeve üretilemedi")
    assert not any("madde sığmadı" in s for s in meta["metin"]["dipnotlar"])
    assert int(meta["lejant_atlanan"]) >= 0
