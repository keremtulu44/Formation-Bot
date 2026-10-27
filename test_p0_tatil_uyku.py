# -*- coding: utf-8 -*-
"""P0 — Tatil uyku ve restart körlüğü regresyon testi (adım adım).

Bu test, SORUN_RAPORU.md:S1 ve E1'in tekrar etmemesini kilitler:
- Tatil/yarım günde time_until_next_open == 0 olmamalı (sonsuz döngü)
- BIST KAPALI dalında taban 60s uyku var
- main_loop başında son_tarama_yukle çağrısı var
"""

import datetime
from datetime import date, time, timedelta

from config import BIST_TATILLER, BIST_YARIM_GUNLER, BIST_OPEN, ISTANBUL_TZ
from data.replay import is_bist_open, time_until_next_open, tarama_penceresi_acik_mi, sonraki_islem_gunu


def _istanbul(yil, ay, gun, saat, dk=0):
    return ISTANBUL_TZ.localize(datetime.datetime(yil, ay, gun, saat, dk))


def test_tatil_gununde_bist_kapali_ve_next_open_sifir_degil():
    # 2026 Ramazan Bayramı 1. gün (tatil) — config.py'de var
    tatil = _istanbul(2026, 3, 20, 10, 30)
    assert not is_bist_open(tatil), "tatilde BIST açık olmamalı"
    assert not tarama_penceresi_acik_mi(tatil), "tatilde tarama penceresi kapalı olmalı"
    # Bir sonraki açılışa kadar >0 olmalı, yoksa ana döngü 0 sn uyur
    bekle = time_until_next_open(tatil)
    assert bekle > 0, f"tatilde bekle 0 olmamalı (sonsuz döngü): {bekle}"
    # Ertesi işlem günü tatil atlanarak bulunmalı
    assert bekle > 10 * 3600, "tatilde en az 10 saat uyku olmalı"


def test_hafta_sonu_bist_kapali_ve_next_open_hafta_icine_atlar():
    cumartesi = _istanbul(2026, 10, 24, 10, 0)  # Cumartesi
    assert not is_bist_open(cumartesi)
    bekle = time_until_next_open(cumartesi)
    assert bekle > 0
    # Pazartesi 09:30'a kadar ~2 gün
    assert bekle > 24 * 3600


def test_sonraki_islem_gunu_tatili_atlar():
    # 2026-03-19 yarım gün arefe, 2026-03-20 tam tatil
    aday = date(2026, 3, 19)
    sonraki = sonraki_islem_gunu(aday)
    assert sonraki == date(2026, 3, 23) or sonraki.weekday() < 5, f"arefe sonrası tatil atlanmalı: {sonraki}"
    assert sonraki not in BIST_TATILLER


def test_bist_kapali_dalinda_taban_uyku_60sn():
    # bot/app.py BIST KAPALI dalında sleep_time = max(sleep_time,60) olmalı
    import pathlib, re
    app = pathlib.Path("bot/app.py").read_text(encoding="utf-8")
    assert "max(sleep_time, 60" in app or "max(sleep_time, 60.0" in app, "taban 60s koruması yok"


def test_son_tarama_yukle_cagrisi_var():
    import pathlib
    app = pathlib.Path("bot/app.py").read_text(encoding="utf-8")
    assert "son_tarama_yukle" in app, "main_loop başında son_tarama_yukle çağrısı yok (E1 regresyon)"
    # Supabase ping sonrası çağrılmalı (bot/app.py:146 civarı)
    ping_idx = app.find("supabase_store.ping()")
    yukle_idx = app.find("son_tarama_yukle")
    assert ping_idx != -1 and yukle_idx != -1 and yukle_idx > ping_idx, "son_tarama_yukle ping sonrası olmalı"
