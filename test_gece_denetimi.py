# -*- coding: utf-8 -*-
"""Gece denetimi bağlantısı: değişiklik yok, sessiz gece, eylem varsa tek DM.

SALT HESAP: Supabase ve Telegram taklit; ağa çıkılmaz.
"""

from __future__ import annotations

from datetime import datetime

import main as M


class SahteStore:
    def __init__(self, patlat=False):
        self.yazilan = []
        self.patlat = patlat

    def request_table(self, tablo, method, *, params=None, json=None, headers=None):
        if self.patlat:
            raise RuntimeError("supabase yok")
        if method == "POST":                       # yalnız yazma sayılır
            self.yazilan.append((tablo, json))
        return object()

    def get_many(self, anahtarlar):
        return {}


class SahteNotifier:
    enabled = True

    def __init__(self):
        self.mesajlar = []

    def send_text(self, metin, deneme=2):
        self.mesajlar.append(metin)
        return True, "mesaj gonderildi"


def _hazirla(monkeypatch, store=None, notifier=None):
    monkeypatch.setattr(M, "_supabase_store_ref", store, raising=False)
    monkeypatch.setattr(M, "_notifier_ref", notifier, raising=False)
    monkeypatch.setattr(M, "_gece_denetim_son_gun", "", raising=False)


def _gece():
    return datetime(2026, 10, 25, 19, 30)


def test_saat_gelmeden_calismaz(monkeypatch):
    store, notifier = SahteStore(), SahteNotifier()
    _hazirla(monkeypatch, store, notifier)
    M._gece_denetimi(datetime(2026, 10, 25, 15, 0))
    assert store.yazilan == [] and notifier.mesajlar == []


def test_gunde_bir_kez_kosar(monkeypatch):
    store, notifier = SahteStore(), SahteNotifier()
    _hazirla(monkeypatch, store, notifier)
    M._gece_denetimi(_gece())
    ilk = len(store.yazilan)
    M._gece_denetimi(_gece())
    assert len(store.yazilan) == ilk == 1


def test_sessiz_gece_dm_gondermez(monkeypatch):
    """Sapma yok + ölçüm yetersiz → rapor yazılır, DM GİTMEZ."""
    store, notifier = SahteStore(), SahteNotifier()
    _hazirla(monkeypatch, store, notifier)
    M._gece_denetimi(_gece())
    assert store.yazilan and store.yazilan[0][0] == "gece_raporu"
    assert notifier.mesajlar == []
    satir = store.yazilan[0][1]
    assert satir["gun"] == "2026-10-25"
    assert satir["olcum"]["karar"] == "yetersiz"


def test_sapma_varsa_tek_dm_gider(monkeypatch):
    store, notifier = SahteStore(), SahteNotifier()
    _hazirla(monkeypatch, store, notifier)
    import tutarlilik

    def sahte_gunluk(kayitlar, **kw):
        return {"kontrol": 3, "ayni": 1, "sapma": 2, "veri_yok": 0, "gun": "2026-10-25",
                "sapmalar": [{"sembol": "THYAO", "tf": "1h", "bar": "x",
                              "neden": "desen: A → B"}], "detay": []}
    monkeypatch.setattr(tutarlilik, "gunluk", sahte_gunluk)
    M._gece_denetimi(_gece())
    assert len(notifier.mesajlar) == 1
    metin = notifier.mesajlar[0]
    assert "THYAO" in metin and "kendiliğinden" in metin


def test_bayrak_kaldirilsin_onerisi_dm_de(monkeypatch):
    import olcum_tazele

    store, notifier = SahteStore(), SahteNotifier()
    _hazirla(monkeypatch, store, notifier)
    monkeypatch.setattr(olcum_tazele, "tazele",
                        lambda **kw: {"karar": "bayrak_kaldirilsin",
                                      "metin": "Ölçüm: fazla -1.20 yüzde puanı → "
                                               "bayrak kaldırılsın önerisi.",
                                      "veri": {}})
    M._gece_denetimi(_gece())
    assert notifier.mesajlar and "kaldırılsın" in notifier.mesajlar[0]


def test_supabase_yoksa_denetim_yine_kosar(monkeypatch):
    """Store hatası gece işini düşürmemeli; ayrıca DM yolu da kilitlenmemeli."""
    notifier = SahteNotifier()
    _hazirla(monkeypatch, SahteStore(patlat=True), notifier)
    M._gece_denetimi(_gece())          # istisna dışarı çıkmamalı
    assert M._gece_denetim_son_gun == "2026-10-25"


def test_gece_raporu_detay_tasinmaz(monkeypatch):
    """Tek satırlık rapor: replay detayı tabloya taşınmaz, özet alanları kalır."""
    store = SahteStore()
    _hazirla(monkeypatch, store, SahteNotifier())
    import tutarlilik
    monkeypatch.setattr(tutarlilik, "gunluk",
                        lambda kayitlar, **kw: {"kontrol": 1, "ayni": 1, "sapma": 0,
                                                "veri_yok": 0, "sapmalar": [],
                                                "detay": [{"sembol": "THYAO"}],
                                                "gun": "2026-10-25"})
    M._gece_denetimi(_gece())
    satir = store.yazilan[0][1]
    assert "detay" not in satir["tutarlilik"]
    assert satir["tutarlilik"]["kontrol"] == 1
