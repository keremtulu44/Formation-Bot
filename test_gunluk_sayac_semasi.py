# -*- coding: utf-8 -*-
"""Günlük sayaç şeması ↔ gün değişimi sıfırlama sözleşmesi.

Neden: `daily_stats` sözlüğüne yeni sayaç eklemek iki yerde birden iş
gerektirir — şema (`bot/statestore.py`) ve gün değişimi sıfırlaması
(`bot/counters.reset_daily_if_needed`). 2026-11-16 denetiminde:
  * kodda artırılan ama şemada olmayan 3 sayaç (`grafik_kare`, `grafik_hata`,
    `alerts_makro_kapali`) ilk kullanımda sessizce oluşuyordu,
  * şemada olup gün değişiminde sıfırlanmayan 4 sayaç (`cache_reddi`,
    `bosluk_tamir_fetch`, `bosluklu_analiz`, `alerts_makro_kapali`) dünün
    değerini bugünün özetine taşıyordu.
Bu test o sınıfı kilitler.
"""
from __future__ import annotations

import copy
import re
from datetime import date, timedelta

import bot.counters as counters
import bot.statestore as statestore
import main as main_module


def _sema_anahtarlari() -> set[str]:
    return set(statestore.daily_stats.keys())


def test_kodda_artirilan_her_sayac_semada_tanimli():
    """`daily_stats['x'] = ...` / `+= ...` yazan her anahtar şemada olmalı."""
    import pathlib

    sema = _sema_anahtarlari()
    kullanim: dict[str, set[str]] = {}
    for yol in pathlib.Path(".").rglob("*.py"):
        if yol.name.startswith("test_") or ".git" in str(yol):
            continue
        metin = yol.read_text(errors="ignore")
        for eslesme in re.finditer(r"daily_stats\[['\"]([a-z_0-9]+)['\"]\]", metin):
            kullanim.setdefault(eslesme.group(1), set()).add(str(yol))

    eksik = {k: v for k, v in kullanim.items() if k not in sema}
    assert not eksik, f"şemada tanımsız sayaç(lar): {sorted(eksik)} -> {eksik}"


def test_gun_degisiminde_tum_sayaclar_sifirlanir(monkeypatch):
    """Gün değişince her sayaç varsayılana döner (dünün değeri taşınmaz)."""
    varsayilan = copy.deepcopy(statestore.daily_stats)
    dolu = {k: (99 if isinstance(v, int) and not isinstance(v, bool) else v)
            for k, v in varsayilan.items()}
    dolu["last_reset"] = date.today() - timedelta(days=3)

    monkeypatch.setattr(main_module, "daily_stats", dolu)
    monkeypatch.setattr(main_module, "_gunluk_sayac_kaydet", lambda: None)
    monkeypatch.setattr(main_module, "_daily_pattern_keys", set())
    monkeypatch.setattr(main_module, "_daily_lifecycle_event_keys", set())
    monkeypatch.setattr(main_module, "_daily_unannounced_invalidation_keys", set())
    monkeypatch.setattr(main_module, "_daily_basarisiz_keys", set())

    counters.reset_daily_if_needed()

    sifirlanmayan = {
        k: v for k, v in dolu.items()
        if isinstance(varsayilan[k], int) and not isinstance(varsayilan[k], bool)
        and v != 0
    }
    assert not sifirlanmayan, f"gün değişiminde sıfırlanmayan sayaç(lar): {sifirlanmayan}"
    assert dolu["last_reset"] == counters._pkg.datetime.now(counters.ISTANBUL_TZ).date()
