# -*- coding: utf-8 -*-
"""Örnek kart galerisi — çeşitli hisseler, çeşitli zamanlar, çeşitli biçimler.

Canlı akışla AYNI biçimleyicileri çağırır (`notifier.format_kart`); payload'lar
gerçek kart yapılarının (GÖRSEL-9) birebir kopyasıdır. Yorum katmanı yalnız
canlı akışın anahtarı (`kart_yorum_kapisi`) açıkken çalışır — betik onu da
yazarak gerçek kart yüzeyini gösterir.

Çalıştırma:  .venv/bin/python scripts/ornek_kartlar.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo kökü

import notifier
import notifier.format_kart as fk

CEVRE = "═" * 62
AYIRAC = "─" * 62


def _temel(**ek):
    """Canlı `alert_data` + `_attach_domain_context` iskeleti."""
    veri = {
        "state": "KIRILIM_TEYITLI",
        "break_dir": 1,
        "confidence_score": 84,
        "break_strength": 96,
        "retest_seen": False,
        "mtf_destek": True,
        "mtf_uyum": 1,
        "kart_yorum_kapisi": True,   # canlı akışın yorum anahtarı
    }
    veri.update(ek)
    return veri


# ── 1) ASELS · 1 saat · 10:15 ── 3◇ kapı: S15 temas+OB, S04 olgunluk, S11 yön
ASELS = _temel(
    stock_name="ASELS", timeframe="1h", pattern_name="Yükselen Üçgen",
    break_price=47.86, critical_price_level=47.86, candle_close_price=48.12,
    upper_now=47.90, upper_touches=2, lower_touches=1,
    age_bars=34, band_baslangic="2026-10-08T10:15:00+03:00",
    retest_seen=True,
    bar_time="2026-10-29T10:15:00+03:00",
    bar_kapanis="2026-10-29T10:15:00+03:00",
    domain_bolumleri={
        "engel": ["▲ direnç · 1s 48,50 +%0,8"],
        "yapi_ozet": ["◈ 1s yapı üstte ve dışarı"],
        "ust": ["▲ OB 1s 47,60-48,05 (2 temas)"],
        "alt": ["▼ OB 1s 46,90-47,20"],
        "hacim": ["hacim: 1s 1,8 kat", "hacim 1s yukarı korunuyor"],
        "olcum": ["◇ son5 formasyon · %72 tuttu",
                  "◇ tutunca ~0,45 TL · %0,9",
                  "◇ rol uyumlu %84 · 15724"],
    },
    domain_karsi=["4s momentum henüz onaylı değil"],
)

# ── 2) GSRAY · 4 saat · 13:45 ── 2◇ (S04, S17) + dikkat S08 (boşluk/FVG)
GSRAY = _temel(
    stock_name="GSRAY", timeframe="4h", pattern_name="Alçalan Takoz",
    break_price=27.38, critical_price_level=27.38, candle_close_price=27.55,
    upper_now=27.10, age_bars=9, band_baslangic="2026-10-20T13:45:00+03:00",
    bar_time="2026-10-29T13:45:00+03:00",
    bar_kapanis="2026-10-29T13:45:00+03:00",
    domain_bolumleri={
        "engel": ["▲ boşluk · 4s 27,45-27,60"],
        "yapi_ozet": ["◈ 4s yapı içinde yatay"],
        "ust": ["▲ FVG 4s 27,10-27,45"],
        "alt": ["▼ OB 4s 26,30-26,60"],
        "hacim": ["hacim: 4s 0,6 kat", "hacim 4s aşağı zayıflıyor"],
        "olcum": ["◇ son5 formasyon · %64 tuttu",
                  "◇ tutunca ~0,20 TL · %0,7",
                  "◇ rol uyumlu %71 · 9214"],
    },
    domain_karsi=["1s momentum aşağı döndü"],
)

# ── 3) SISE · günlük · 16:00 ── 3◇: S04, S10 (zayıf ilgi), S16 (uzun bant)
SISE = _temel(
    stock_name="SISE", timeframe="1d", pattern_name="Dikdörtgen",
    break_price=39.26, critical_price_level=39.26, candle_close_price=39.60,
    upper_now=39.96, age_bars=64, band_baslangic="2026-08-25T16:00:00+03:00",
    bar_time="2026-10-29T16:00:00+03:00",
    bar_kapanis="2026-10-29T16:00:00+03:00",
    domain_bolumleri={
        "engel": ["▲ direnç · 1g 40,10 +%1,3"],
        "yapi_ozet": ["◈ 1g yapı üstte sıkışıyor"],
        "ust": ["▲ OB 1g 38,90-39,50 (3 temas)"],
        "alt": ["▼ OB 1g 37,40-37,95"],
        "hacim": ["hacim: 1g 0,5 kat", "hacim 1g aşağı zayıflıyor"],
        "olcum": ["◇ son5 formasyon · %58 tuttu",
                  "◇ tutunca ~0,60 TL · %1,5",
                  "◇ rol uyumlu %69 · 11280"],
    },
)

# ── 4) THYAO · 4 saat · 11:30 ── KAPI YOK → eski kart birebir
THYAO = _temel(
    stock_name="THYAO", timeframe="4h", pattern_name="Üçgen",
    break_price=324.50, critical_price_level=324.50, candle_close_price=326.00,
    upper_now=323.80, age_bars=2, band_baslangic="2026-10-27T11:30:00+03:00",
    mtf_destek=False, mtf_uyum=0, break_strength=71,
    bar_time="2026-10-29T11:30:00+03:00",
    bar_kapanis="2026-10-29T11:30:00+03:00",
    domain_bolumleri={
        "yapi_ozet": ["◈ 4s yapı içinde sıkışma"],
        "ust": ["▲ direnç · 4s 328,00 +%0,6"],
        "hacim": ["hacim: 4s 1,1 kat", "hacim 4s artıyor"],
        "olcum": ["◇ son5 formasyon · %66 tuttu",
                  "◇ tutunca ~3,10 TL · %1,0",
                  "◇ rol uyumlu %77 · 6051"],
    },
    domain_karsi=["1s yapı kırılmadı"],
)

# ── 5) XU100 · 1 saat · 14:30 ── endeks (hacim yok) + 3◇: S04, S13, S31
XU100 = _temel(
    stock_name="XU100", timeframe="1h", pattern_name="Yükselen Kanal",
    break_price=10920.0, critical_price_level=10920.0, candle_close_price=10948.5,
    upper_now=10885.0, age_bars=12, band_baslangic="2026-10-22T14:30:00+03:00",
    bar_time="2026-10-29T14:30:00+03:00",
    bar_kapanis="2026-10-29T14:30:00+03:00",
    domain_bolumleri={
        "engel": ["▲ direnç · 1s 10.980 +%0,3"],
        "yapi_ozet": ["◈ 1s yapı üstte"],
        "ust": ["▲ OB 1s 10.850-10.940"],
        "hacim": ["hacim: 1s yok (endeks)", "yön fiyattan okunur"],
        "olcum": ["◇ son5 formasyon · %70 tuttu",
                  "◇ tutunca ~96 puan · %0,9",
                  "◇ rol uyumlu %81 · 4410"],
    },
)

# ── 6) THYAO · 1 saat · 15:10 ── KIRILIM İPTAL (yorum kapalı: teyitli değil)
THYAO_IPTAL = _temel(
    stock_name="THYAO", timeframe="1h", state="KIRILIM_GECERSIZLESTI",
    pattern_name="Üçgen", break_dir=-1,
    break_price=322.10, critical_price_level=322.10, candle_close_price=324.55,
    lower_now=324.00, age_bars=26, band_baslangic="2026-10-02T15:10:00+03:00",
    bar_time="2026-10-29T15:10:00+03:00",
    bar_kapanis="2026-10-29T15:10:00+03:00",
    domain_bolumleri={
        "hacim": ["hacim: 1s 0,9 kat", "hacim 1s aşağı zayıflıyor"],
        "olcum": ["◇ son5 formasyon · %61 tuttu"],
    },
)

# ── 7) SISE · 1 saat · 09:45 ── SEVİYE KORUNDU (retest; yorum kapalı)
SISE_RETEST = _temel(
    stock_name="SISE", timeframe="1h", state="RETEST_BASARILI",
    pattern_name="Yükselen Üçgen", break_price=39.26,
    critical_price_level=39.26, candle_close_price=39.44,
    upper_now=39.10, age_bars=41, band_baslangic="2026-09-18T09:45:00+03:00",
    retest_seen=True,
    bar_time="2026-10-29T09:45:00+03:00",
    bar_kapanis="2026-10-29T09:45:00+03:00",
    domain_bolumleri={
        "engel": ["▲ direnç · 1s 39,90 +%1,2"],
        "yapi_ozet": ["◈ 1s yapı üstte"],
        "hacim": ["hacim: 1s 1,4 kat", "hacim 1s yukarı korunuyor"],
        "olcum": ["◇ son5 formasyon · %74 tuttu"],
    },
)


def _baslik(no: str, metin: str) -> None:
    print(f"\n{CEVRE}\n{no}  {metin}\n{AYIRAC}")


def main() -> None:
    _baslik("1", "ASELS · 1 saat · 29 Ekim 10:15 · KIRILIM TEYİTLİ "
                 "(canlı sade kart — 3◇ kapı: temas, olgunluk, yön baskısı)")
    print(fk._format_lifecycle_alert_kart_sade(dict(ASELS)))

    _baslik("2", "GSRAY · 4 saat · 29 Ekim 13:45 · KIRILIM TEYİTLİ "
                 "(2◇ + dikkat: boşluk/geç hedef)")
    print(fk._format_lifecycle_alert_kart_sade(dict(GSRAY)))

    _baslik("3", "SISE · günlük · 29 Ekim 16:00 · KIRILIM TEYİTLİ "
                 "(3◇: zayıf ilgi, uzun bant, olgunluk)")
    print(fk._format_lifecycle_alert_kart_sade(dict(SISE)))

    _baslik("4", "THYAO · 4 saat · 29 Ekim 11:30 · KIRILIM TEYİTLİ "
                 "(KAPI YOK → ek satır yok, eski kart birebir)")
    print(fk._format_lifecycle_alert_kart_sade(dict(THYAO)))

    _baslik("5", "XU100 · 1 saat · 29 Ekim 14:30 · KIRILIM TEYİTLİ "
                 "(endeks: hacim yok + 3◇ + dikkat)")
    print(fk._format_lifecycle_alert_kart_sade(dict(XU100)))

    _baslik("6", "THYAO · 1 saat · 29 Ekim 15:10 · KIRILIM İPTAL "
                 "(geçersiz kart — yorum kapısı yalnız teyitlide açık)")
    print(fk._format_lifecycle_alert_kart_sade(dict(THYAO_IPTAL)))

    _baslik("7", "SISE · 1 saat · 29 Ekim 09:45 · SEVİYE KORUNDU "
                 "(retest — yorum kapısı yalnız teyitlide açık)")
    print(fk._format_lifecycle_alert_kart_sade(dict(SISE_RETEST)))

    _baslik("B", "AYNI ASELS — süzgeçsiz TAM kart (TELEGRAM_KART_SUZGEC=0; "
                 "canlıda süzgeç varsayılan açık → yorum satırları bu biçimde yok)")
    eski = getattr(notifier, "TELEGRAM_KART_SUZGEC", None)
    notifier.TELEGRAM_KART_SUZGEC = False
    try:
        print(fk._format_lifecycle_alert_kart(dict(ASELS)))
    finally:
        if eski is None:
            delattr(notifier, "TELEGRAM_KART_SUZGEC")
        else:
            notifier.TELEGRAM_KART_SUZGEC = eski

    _baslik("C", "AYNI ASELS — klasik biçim (TELEGRAM_ALERT_STYLE=klasik)")
    print(fk._format_lifecycle_alert_klasik(dict(ASELS)))
    print()


if __name__ == "__main__":
    main()
