# -*- coding: utf-8 -*-
"""GÖRSEL-4: bölge kutuları sadeleşti + etiket KUTUNUN İÇİNDE, BOS/CHoCH mumun yanında.

Kullanıcı kararları (2026-10-15):
  1. FVG/OB kutularındaki "değişik çizim" (eğik tarama + 2 pt kalın vurgu barı)
     kalktı; etiket kutunun İÇİNE yazılıyor (`OB↓ %70`), sığmazsa sağ şeride yedek.
  2. BOS/CHoCH etiketleri şeritten grafiğe (olayın mumuna) taşındı — "fiyat değil
     konum önemli"; PH/PL etiketlerine seviye eklendi ("fiyat önemli").
  3. Geçersizleşmede tek kare (yalnız geçersizleşen TF) ve yalnız o TF'nin domain
     bölümleri.

Testler `bot_data/` önbelleğini yalnız OKUR.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

import grafik
import grafik_uret

IST = timezone(timedelta(hours=3))


# --------------------------------------------------------------- kutu çizimi


def _bolge(tip="fvg", yon=1, alt=100.0, ust=102.0, x0=10, x1=40, **ek):
    kayit = {"tip": tip, "yon": yon, "alt": alt, "ust": ust, "x0": x0, "x1": x1,
             "durum": "ACTIVE", "vurgu": "alt" if yon >= 0 else "ust"}
    kayit.update(ek)
    return kayit


def _eksen(n=60, alt=90.0, ust=115.0):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10.8, 8.1), dpi=100)
    ax = fig.add_axes([0.075, 0.1, 0.8, 0.8])
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(alt, ust)
    return fig, ax


def test_kutu_etiketi_kutunun_icinde_ve_tarama_yok():
    """Yazı kutunun İÇİNDE (`kutu-ici`), kutularda hatch YOK, şerit yedeği boş."""
    fig, ax = _eksen()
    zone = {"cizilen": [_bolge(doluluk=0.7, skor=95)]}
    sag: list = []
    ozet = grafik._zone_ciz(ax, zone, 60, (90.0, 115.0), sag)
    assert ozet["ic"] == 1 and ozet["serit"] == 0
    assert sag == [], "sığan etiket şeride de yazılmamalı"
    etiketler = [t for t in ax.texts if str(t.get_gid() or "") == "kutu-ici"]
    assert len(etiketler) == 1
    metin = str(etiketler[0].get_text())
    # FAZ 3 §1.B: FVG doluluk HESABI YAPMAZ — etiket yalnız tip + yön (yüzde yok).
    assert metin.startswith("FVG↑") and "%" not in metin
    from matplotlib.patches import Rectangle
    kutular = [p for p in ax.patches if isinstance(p, Rectangle)]
    assert kutular and all((p.get_hatch() is None) for p in kutular)   # eğik tarama kalktı
    # vurgu kenarı inceldi: 2,0 pt "havada duran çubuk" görüntüsü veriyordu
    assert float(grafik.SABITLER["zone_kalinlik"]["vurgu"]) <= 1.5


def test_kutu_ince_veya_dar_ise_etiket_seride_yedeklenir():
    """Sığmayan etiket KAYBOLMAZ: sağ şeride taşınır (kılavuz çizgisiyle birlikte)."""
    fig, ax = _eksen()
    ince = _bolge(alt=100.0, ust=100.15, skor=88)      # yükseklik: yazı sığmaz
    dar = _bolge(alt=105.0, ust=107.0, x0=10, x1=11)   # genişlik: 2 bar
    zone = {"cizilen": [ince, dar]}
    sag: list = []
    ozet = grafik._zone_ciz(ax, zone, 60, (90.0, 115.0), sag)
    assert ozet["ic"] == 0 and ozet["serit"] == 2
    assert len(sag) == 2 and all(a["kaynak"] == "zone" for a in sag)
    assert all("kilavuz_x" in a for a in sag)


def test_meta_kutu_ici_ve_serit_sayaclarini_tasir(tmp_path):
    sonuc = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True,
                                  mum=140, cikti=str(tmp_path / "GARAN_4h.png"))
    assert sonuc.get("hata") is None
    zone = sonuc["meta"]["zone"]
    assert set(zone) >= {"etiket_ic", "etiket_serit"}
    assert int(zone["etiket_ic"]) + int(zone["etiket_serit"]) == int(zone["cizilen"])


# --------------------------------------------------- BOS/CHoCH ve PH/PL yazısı


def _olay_goruntusu():
    return {
        "sembol": "TEST", "tf": "1h", "tf_kisa": "1s", "sol": 0, "sag": 120,
        "acilis": [100.0] * 60, "yuksek": [101.0] * 60, "dusuk": [99.0] * 60,
        "kapanis": [100.5] * 60,
        "zamanlar": [datetime(2026, 9, 1, 9, 30, tzinfo=IST) + timedelta(hours=i)
                     for i in range(60)],
        "formasyon": {}, "alarm": {}, "zone": {}, "temas": [], "isaretler": [],
        "serit": {},
        "olay": {
            "swinglar": [
                {"bar": 30, "fiyat": 103.0, "yon": "ust", "sinif": "LH", "durum": "teyitli"},
            ],
            "seviyeler": [
                {"bar": 10, "kaynak_bar": 10, "fiyat": 104.5, "etiket": "PH",
                 "rol": "PROTECTED_HIGH"},
                {"bar": 20, "kaynak_bar": 20, "fiyat": 96.25, "etiket": "PL",
                 "rol": "PROTECTED_LOW"},
            ],
            "olaylar": [
                {"bar": 40, "seviye": 102.0, "yon": "ust", "tur": "BOS"},
                {"bar": 50, "seviye": 98.0, "yon": "alt", "tur": "CHoCH"},
            ],
            "kritik": {},
        },
    }


def test_bos_choch_etiketi_seride_degil_mumun_yaninda():
    """BOS/CHoCH artık fiyat şeridinde DEĞİL: etiket olayın mumuna ilişir."""
    fig, ax = _eksen()
    sag: list = []
    goruntu = _olay_goruntusu()
    ozet = grafik._olay_ciz(ax, goruntu, 60, sag)
    olay_yazilari = [t for t in ax.texts if str(t.get_gid() or "") == "olay-ici"]
    assert sorted(str(t.get_text()) for t in olay_yazilari) == ["BOS↑", "CHoCH↓"]
    assert ozet["etiket_ic"] == 2
    # Dış PH/PL rol seviyeleri cetvele gider; iç LH etiketi grafikte kalır.
    assert {a["kaynak"] for a in sag} == {"swing"}
    assert sorted(a["metin"] for a in sag) == ["PH 104,50", "PL 96,25"]
    assert all("kilavuz_x" not in a for a in sag)  # çizgi katmanı ayrı çizildi


def test_ph_pl_cetvelde_fiyat_tasir_ic_yapi_kisa_kalir():
    """GÖRSEL-6: PH/PL fiyatı SAĞ ŞERİT cetvelinde; grafikte yalnız iç yapı kısa yazı."""
    fig, ax = _eksen()
    sag: list = []
    grafik._olay_ciz(ax, _olay_goruntusu(), 60, sag)
    yazilar = [str(t.get_text()) for t in ax.texts if str(t.get_text()).strip()]
    assert "LH" in yazilar                                       # iç yapı: kısa
    assert not any(y.startswith("LH ") for y in yazilar)
    # PH/PL grafikte YAZI DEĞİL (çift okuma yok), şeritte cetvel çipi:
    assert not any(y.startswith(("PH ", "PL ")) for y in yazilar)
    assert sorted(a["metin"] for a in sag) == ["PH 104,50", "PL 96,25"]
    assert all(a["kaynak"] == "swing" and a["oncelik"] == 4 for a in sag)


def test_kritik_yazisi_tek_kopya_kalir():
    """`kritik X` şeritte kalır ama olayın kendi etiketiyle ÇİFTLENMEZ (şerit yok)."""
    fig, ax = _eksen()
    sag: list = []
    goruntu = _olay_goruntusu()
    goruntu["olay"]["kritik"] = {"bar": 50, "seviye": 98.0, "tur": "CHoCH"}
    grafik._olay_ciz(ax, goruntu, 60, sag)
    metinler = [a["metin"] for a in sag]
    assert "kritik 98,00" in metinler
    assert "CHoCH↓" not in metinler          # olay etiketi grafikte, şeritte değil


# ------------------------------------------------------------- tek kare kuralı


def _cerceveler():
    import grafik_uret as gu

    yon = gu.cerceve_getir("THYAO", "1h", "bot_data")[0]
    from data import tamamlanmis_mumlar

    tf_alarm = "4h"
    df, _ = gu.cerceve_getir("THYAO", tf_alarm, "bot_data")
    return tf_alarm, tamamlanmis_mumlar(df, tf_alarm), {
        "1h": tamamlanmis_mumlar(yon, "1h"),
        "2h": tamamlanmis_mumlar(gu.cerceve_getir("THYAO", "2h", "bot_data")[0], "2h"),
        "1d": tamamlanmis_mumlar(gu.cerceve_getir("THYAO", "1d", "bot_data")[0], "1d"),
    }


def test_gecersizlesmede_tek_kare_uretilir(monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")     # kill-switch açık olmalı
    tf_alarm, df_alarm, ekler = _cerceveler()
    veri = grafik.kare_listesi(None, tf_alarm, df_alarm, ek_cerceveler=ekler,
                               alarm_turu="gecersiz", alarm_bar=len(df_alarm) - 2,
                               sembol="THYAO", zaman_damgasi=df_alarm.index[-1])
    assert [k["tf"] for k in veri["goruntular"]] == [tf_alarm]


def test_diger_alarmlarda_kare_kotasi_korunur(monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    tf_alarm, df_alarm, ekler = _cerceveler()
    veri = grafik.kare_listesi(None, tf_alarm, df_alarm, ek_cerceveler=ekler,
                               alarm_turu="teyit", alarm_bar=len(df_alarm) - 2,
                               sembol="THYAO", zaman_damgasi=df_alarm.index[-1])
    assert len(veri["goruntular"]) >= 2          # çoklu TF davranışı değişmedi


# ----------------------------------------- metin → hemen görsel (arka plan işçisi)
# Kullanıcı kararı: "bir metin geldi, ardından o metan görselleri, sonra bir metin".
# Not: `_gonder` metni yazdıktan sonra kuyruğa `gonder=True` ile ekler; kareler
# tur sonunu BEKLEMEZ, arka plan işçisi sırayla gönderir (tarama bekletilmez).


def _sahte_notifier(tmp_path, monkeypatch):
    import notifier as N

    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")     # kill-switch açık olmalı
    monkeypatch.setattr(N, "DATA_DIR", str(tmp_path))
    n = N.TelegramNotifier()
    n.enabled = True
    n.token = "123456:SAHTE"
    n.chat_id = "42"
    return n


def test_gonder_bayragi_arka_plan_iscisini_baslatir(tmp_path, monkeypatch):
    from test_grafik_iskelet import _goruntu

    n = _sahte_notifier(tmp_path, monkeypatch)
    cagrilar = []
    monkeypatch.setattr(n, "grafikleri_gonder",
                        lambda sinir=None: (cagrilar.append(1),
                                            {"gonderilen": 0, "hata": 0, "kare": 0,
                                             "sure_ms": 0, "atlanan": 0})[1])
    n.grafik_kuyruga_ekle({"stock_name": "AKBNK", "timeframe": "4h",
                           "grafik_verisi": {"sembol": "AKBNK", "kota": 0,
                                             "goruntular": [{"tf": "4h",
                                                             "goruntu": _goruntu(tf="4h")}]}},
                          gonder=True)
    for _ in range(50):                     # işçi en fazla bir kez dönmeli (kare=0)
        if cagrilar:
            break
        time.sleep(0.02)
    assert cagrilar == [1], "arka plan işçisi gönderimi tetiklemedi"
    time.sleep(0.05)
    assert cagrilar == [1], "işçi kare=0 görünce tekrar denememeli"


def test_ikinci_ekleme_ayni_iscinin_calismasini_etkilemez(tmp_path, monkeypatch):
    """Eşzamanlı iki olay: tek işçi, sıralı gönderim (metin→görsel sırası korunur)."""
    from test_grafik_iskelet import _goruntu

    n = _sahte_notifier(tmp_path, monkeypatch)
    cagri = []
    def yavas(sinir=None):
        cagri.append(1)
        return {"gonderilen": 0, "hata": 0, "kare": 1 if len(cagri) < 3 else 0,
                "sure_ms": 0, "atlanan": 0}
    monkeypatch.setattr(n, "grafikleri_gonder", yavas)
    for i in range(3):
        n.grafik_kuyruga_ekle({"stock_name": f"AKBNK{i}", "timeframe": "4h",
                               "grafik_verisi": {"sembol": "AKBNK", "kota": 0,
                                                 "goruntular": [{"tf": "4h",
                                                                 "goruntu": _goruntu(tf="4h")}]}},
                              gonder=True)
    for _ in range(100):
        if len(cagri) >= 3:
            break
        time.sleep(0.02)
    assert len(cagri) >= 3                   # kuyruk boşalana kadar döngü


def test_gecersizlesme_bolumleri_yalniz_alarm_tf():
    """Geçersizleşme kartı yalnız geçersizleşen TF'nin bölümlerini taşır."""
    from types import SimpleNamespace
    from notification_context import format_domain_context

    def _res(export=None, **a):
        return SimpleNamespace(export=export, skipped=False, error=None, **a)

    def _ms(seviye):
        event = SimpleNamespace(event_uid=f"e{seviye}", scope="EXTERNAL",
                                event_type="EVENT_BOS", event_bar=12, broken_level=seviye,
                                direction=1, validity="VALID", relevance="CURRENT",
                                confirmation_status="CONFIRMED", is_active=True)
        return SimpleNamespace(external_scope=SimpleNamespace(state="STATE_BULLISH"),
                               internal_scope=SimpleNamespace(state="STATE_NEUTRAL"),
                               events=[event], external_protected_high=seviye + 6,
                               external_protected_low=seviye - 6, external_weak_high=None,
                               external_weak_low=None)

    outputs = {tf: {"market_structure": _res(_ms(100.0 + i))}
               for i, tf in enumerate(("1h", "2h", "4h", "1d"))}
    tumu = format_domain_context(outputs, reference_price=100.0, alarm_tf="4h")
    yalniz = format_domain_context(outputs, reference_price=100.0, alarm_tf="4h",
                                   yalniz_tf=True)
    assert "1s yapı" in tumu and "1g yapı" in tumu           # eski davranış
    assert "4s yapı" in yalniz
    for yabanci in ("1s yapı", "2s yapı", "1g yapı"):
        assert yabanci not in yalniz, yalniz


# ------------------------------------------- 2B yerleşim: katman yazıları muma binmez
# Ölçüm (20 kare, önce): `katman_cakisan`da 4 olay etiketi + birkaç kutu etiketi
# mum gövdesiyle çakışıyordu. Yerleşim artık gerçek `get_window_extent` ile
# ölçülüp çakışmasız aday aranıyor.


def test_olay_etiketi_mum_cakismasi_olcumu_sifir():
    """BOS/CHoCH etiketleri mum kutusuyla çakışmaz (bilinçli ölçüm kanalı)."""
    import grafik_uret

    sonuc = grafik_uret.kare_uret("GARAN", "4h", veri_dizin="bot_data", zone=True,
                                  mum=140, cikti="/tmp/kare/_gorsel4_olay.png")
    kalite = sonuc["meta"]["kalite"]
    assert kalite["mum_cakisan"] == 0            # şerit/başlık kapısı katı kalır
    olay_cakisan = [y for y in kalite["katman_cakisan"] if y.startswith(("BOS", "CHoCH"))]
    assert olay_cakisan == [], kalite["katman_cakisan"]


def test_kutu_yazisi_mum_cakismasini_azaltir():
    """Kutu içi yazı yerleşimi ölçümle seçilir: aynı karede yazı sayısı korunur."""
    import grafik_uret

    sonuc = grafik_uret.kare_uret("TUPRS", "4h", veri_dizin="bot_data", zone=True,
                                  mum=150, cikti="/tmp/kare/_gorsel4_kutu.png")
    zone = sonuc["meta"]["zone"]
    assert zone["etiket_ic"] + zone["etiket_serit"] == zone["cizilen"]
    # Ölçüm alanı her zaman döner (bilinçli katman yazıları ayrı sayılır).
    assert "katman_cakisan" in sonuc["meta"]["kalite"]
