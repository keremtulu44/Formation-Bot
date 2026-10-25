# -*- coding: utf-8 -*-
"""Gece ölçüm tazeleme sözleşmesi — yalnız ÖNERİ, hiçbir değişiklik yok.

SALT HESAP: Supabase taklidi enjekte edilir, ağa çıkılmaz.
"""

from __future__ import annotations

import olcum_tazele as O


class SahteCevap:
    def __init__(self, satirlar=None, sayi=None):
        self._satirlar = satirlar or []
        self.headers = {} if sayi is None else {"Content-Range": f"0-0/{sayi}"}

    def json(self):
        return self._satirlar


class SahteStore:
    """PostgREST taklidi: tablo → (satır sayısı ya da satırlar)."""

    def __init__(self, sayilar=None, ozet_satirlari=None):
        self.sayilar = sayilar or {}
        self.ozet_satirlari = ozet_satirlari or []
        self.cagrilar = []

    def request_table(self, tablo, method, *, params=None, json=None, headers=None):
        self.cagrilar.append(tablo)
        if tablo == "v_ileri_test_ozet":
            return SahteCevap(self.ozet_satirlari)
        return SahteCevap(sayi=self.sayilar.get(tablo))


def _kayit(yuzde, bayrak):
    return {"anahtar": f"{yuzde}-{bayrak}", "bayrak": bayrak, "sonuc": {"yuzde": yuzde}}


def test_yetersiz_veride_oneri_uretilmez():
    sonuc = O.tazele(store=None, kayitlar=[_kayit(1.0, True)] * 5)
    assert sonuc["karar"] == "yetersiz"
    assert "yetersiz" in sonuc["metin"].lower()
    assert "fazla" not in sonuc["veri"]          # yetersizken fark hesaplanmaz
    assert "kalsın" not in sonuc["metin"]        # yön önerisi yok


def test_esik_asilirsa_kalsin_onerisi():
    kayitlar = [_kayit(6.0, True)] * O.it.MIN_GOZLEM + [_kayit(1.0, False)] * O.it.MIN_GOZLEM
    sonuc = O.tazele(store=None, kayitlar=kayitlar)
    assert sonuc["karar"] == "bayrak_kalsin"
    assert sonuc["veri"]["fazla"] == 5.0
    assert "kalsın" in sonuc["metin"]


def test_esik_altinda_kaldirilsin_onerisi():
    kayitlar = [_kayit(1.0, True)] * O.it.MIN_GOZLEM + [_kayit(0.0, False)] * O.it.MIN_GOZLEM
    sonuc = O.tazele(store=None, kayitlar=kayitlar)
    assert sonuc["karar"] == "bayrak_kaldirilsin"
    assert "kaldırılsın" in sonuc["metin"]


def test_defter_bossa_tablodan_okur():
    store = SahteStore(ozet_satirlari=[
        {"bayrak": True, "n": 120, "ortalama_yuzde": 4.0},
        {"bayrak": False, "n": 130, "ortalama_yuzde": 1.0},
    ], sayilar={})
    sonuc = O.tazele(store=store, kayitlar=[])
    assert sonuc["veri"]["kaynak"] == "tablo"
    assert sonuc["karar"] == "bayrak_kalsin"
    assert "v_ileri_test_ozet" in store.cagrilar


def test_arsiv_bos_tablolari_uyarir():
    store = SahteStore(sayilar={"f2_formations": 1126, "f2_events": 0,
                                "f2_outcome_links": 0, "f2_snapshots": 0})
    saglik = O.arsiv_sagligi(store)
    assert saglik["sayilar"]["f2_formations"] == 1126
    assert any("f2_events" in u for u in saglik["uyarilar"])
    assert any("f2_outcome_links" in u for u in saglik["uyarilar"])

    # dolu arşivde uyarı yok
    dolu = SahteStore(sayilar={t: 10 for t in O.ARSIV_TABLOLARI})
    assert O.arsiv_sagligi(dolu)["uyarilar"] == []


def test_arsiv_erisimi_yoksa_uydurma_sayi_yok():
    saglik = O.arsiv_sagligi(None)
    assert set(saglik["sayilar"].values()) == {None}
    assert saglik["uyarilar"] == []


def test_uyari_metni_arsiv_uyarisini_tasir():
    store = SahteStore(sayilar={"f2_formations": 5, "f2_events": 0,
                                "f2_outcome_links": 0, "f2_snapshots": 0})
    sonuc = O.tazele(store=store, kayitlar=[_kayit(1.0, True)] * 3)
    assert "Arşiv:" in sonuc["metin"]
    assert sonuc["veri"]["arsiv"]["uyarilar"]


def test_hukum_hicbir_seyi_degistirmez():
    """Modül yalnız metin/veri döner; kart, eşik, sıralama dokunulmaz."""
    kayitlar = [_kayit(6.0, True)] * O.it.MIN_GOZLEM + [_kayit(1.0, False)] * O.it.MIN_GOZLEM
    onceki_esik = O.it.ESIK_FAZLA_PUAN
    onceki_min = O.it.MIN_GOZLEM
    O.tazele(store=None, kayitlar=kayitlar)
    assert O.it.ESIK_FAZLA_PUAN == onceki_esik
    assert O.it.MIN_GOZLEM == onceki_min
