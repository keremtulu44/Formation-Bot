# -*- coding: utf-8 -*-
"""Albüm teslimi: kareler TEK `sendMediaGroup` olarak gider; araya metin girmez.

Kapsam (ağ yok — `transport.telegram._multipart_cagri` kaydedici sahteyle değişir):
  1. Çok kare → tam bir `sendMediaGroup`, `photo` yok, öğe sırası ve altyazı korunur.
  2. Albüm reddedilirse kareler tek tek yeniden denenir; hiçbir kare kaybolmaz.
  3. Tek kare → `sendPhoto` (albüm 2–10 öğe ister).
  4. DM dışı hedef → hiçbir çağrı yok, dosyalar yine silinir.
  5. Alarm kuyruğu: bir olayın kareleri tek albüm olur.
  6. `/grafik` kullanıcıya görünen formasyon uyarısı üretmez; altyazı tarih biçimli.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

import grafik
import grafik_uret
from transport import telegram as tg


@pytest.fixture()
def cagrilar(monkeypatch):
    """Her Telegram API çağrısını kaydeder; istenirse albümü reddettirir."""
    kayit = {"cagri": [], "album_red": False}

    class Yanit:
        def __init__(self, ok=True):
            self.status_code = 200 if ok else 400
            self._ok = ok

        def json(self):
            return {"ok": self._ok, "description": "" if self._ok else "reddedildi"}

    def sahte(method, token, alanlar, dosyalar, timeout=20):
        kayit["cagri"].append({"method": method, "alanlar": dict(alanlar),
                               "dosyalar": sorted(dosyalar)})
        ok = not (method == "sendMediaGroup" and kayit["album_red"])
        return Yanit(ok)

    monkeypatch.setattr(tg, "_multipart_cagri", sahte)
    return kayit


@pytest.fixture()
def notifier(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAtestsecret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")       # pozitif → DM
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    import notifier as N
    n = N.TelegramNotifier()
    monkeypatch.setattr(n, "public_chat_id", "", raising=False)
    n.enabled = True
    return n


def _png(tmp_path, ad):
    yol = tmp_path / ad
    yol.write_bytes(b"\x89PNG\r\n\x1a\n" + ad.encode())
    return str(yol)


def test_medya_grubu_tek_album_cagrisi_ve_sira(tmp_path, cagrilar, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAtestsecret")
    yollar = [_png(tmp_path, f"k{i}.png") for i in range(4)]
    caps = ["AKBNK · 1s", "AKBNK · 2s", "AKBNK · 4s", "AKBNK · 1g"]
    ok, aciklama = tg.medya_grubu_gonder(yollar, caps, chat_id="12345", token="123456789:AAx")
    assert ok is True                              # yanit_oku başarıda "HTTP 200" açıklar
    assert len(cagrilar["cagri"]) == 1
    c = cagrilar["cagri"][0]
    assert c["method"] == "sendMediaGroup"
    medya = json.loads(c["alanlar"]["media"])
    assert [m["media"] for m in medya] == [f"attach://photo{i}" for i in range(4)]
    assert [m["caption"] for m in medya] == caps
    assert c["dosyalar"] == ["photo0", "photo1", "photo2", "photo3"]


def test_medya_grubu_tek_ogede_reddeder(tmp_path, cagrilar):
    yol = _png(tmp_path, "tek.png")
    ok, aciklama = tg.medya_grubu_gonder([yol], ["x"], chat_id="1", token="123456789:AAx")
    assert ok is False and "2-10" in aciklama
    assert cagrilar["cagri"] == []                 # ağa çıkılmadı


def test_toplu_gonder_dort_kare_tek_album(notifier, cagrilar, tmp_path):
    paketler = [(_png(tmp_path, f"t{i}.png"), f"AKBNK · {i}") for i in range(4)]
    sonuc = notifier.grafik_toplu_gonder(paketler)
    assert sonuc == [True] * 4
    metodlar = [c["method"] for c in cagrilar["cagri"]]
    assert metodlar == ["sendMediaGroup"]          # sendPhoto/sendMessage YOK
    assert notifier.grafik_gonderilen == 4
    assert all(not os.path.exists(y) for y, _c in paketler)   # dosyalar silindi


def test_toplu_gonder_album_reddedilince_kare_kare_dener(notifier, cagrilar, tmp_path):
    cagrilar["album_red"] = True
    paketler = [(_png(tmp_path, f"r{i}.png"), f"c{i}") for i in range(3)]
    sonuc = notifier.grafik_toplu_gonder(paketler)
    assert sonuc == [True] * 3                     # hiçbir kare kaybolmadı
    metodlar = [c["method"] for c in cagrilar["cagri"]]
    assert metodlar[0] == "sendMediaGroup"
    assert metodlar[1:] == ["sendPhoto"] * 3
    assert all(not os.path.exists(y) for y, _c in paketler)


def test_toplu_gonder_tek_kare_sendphoto(notifier, cagrilar, tmp_path):
    paketler = [(_png(tmp_path, "tek2.png"), "tek")]
    assert notifier.grafik_toplu_gonder(paketler) == [True]
    assert [c["method"] for c in cagrilar["cagri"]] == ["sendPhoto"]
    assert not os.path.exists(paketler[0][0])


def test_toplu_gonder_dm_disi_hedefte_cagri_yok_ve_temizlik(notifier, cagrilar, tmp_path):
    notifier.chat_id = "-100999"                   # grup kimliği → DM değil
    paketler = [(_png(tmp_path, f"g{i}.png"), "c") for i in range(2)]
    assert notifier.grafik_toplu_gonder(paketler) == [False, False]
    assert cagrilar["cagri"] == []
    assert all(not os.path.exists(y) for y, _c in paketler)
    assert notifier.grafik_atlanan_hata == 2


def test_alarm_kuyrugu_olay_basina_tek_album(notifier, cagrilar, tmp_path, monkeypatch):
    """Bir alarmın 2 karesi → tek albüm; ayrı metin/foto yok."""
    monkeypatch.setattr(grafik, "kareyi_yaz",
                        lambda goruntu, tf: (_png(tmp_path, f"a_{tf}.png"),
                                             {"mum_sayisi": 120, "son_bar_ts": None,
                                              "uyarilar": []}))
    notifier._grafik_kuyruk.append({
        "anahtar": ("AKBNK", "4h", "TEYIT"), "sembol": "AKBNK",
        "goruntular": [{"goruntu": {"tf_kisa": "4s"}, "tf": "4h"},
                       {"goruntu": {"tf_kisa": "1s"}, "tf": "1h"}],
        "kota": 0})
    ozet = notifier.grafikleri_gonder()
    assert ozet["gonderilen"] == 2
    metodlar = [c["method"] for c in cagrilar["cagri"]]
    assert metodlar == ["sendMediaGroup"]


def test_formasyon_verilmediyse_uyari_yok():
    """Kullanıcıya 'formasyon verisi verilmedi' gibi hata görünmez."""
    formasyon, uyarilar = grafik_uret._formasyon_yukle(None, None)
    assert formasyon is None and uyarilar == []


def test_kare_altyazisi_tarih_ve_mum(monkeypatch):
    import main as M
    alt = M._kare_altyazisi("AKBNK", "4h", {"mum_sayisi": 120,
                                            "son_bar_ts": "2026-09-25T17:30:00+03:00"})
    assert alt == "AKBNK · 4s · 120 mum · formasyon yok · son kapanan 25.09.2026 17:30"
    alt2 = M._kare_altyazisi("THYAO", "1d", {"son_bar_ts": "bozuk"})
    assert alt2 == "THYAO · 1g · formasyon yok · son kapanan bozuk"


def test_kare_altyazisi_formasyon_adini_yazar():
    import main as M
    alt = M._kare_altyazisi("ALARK", "4h", {"mum_sayisi": 120, "formasyon_ad": "Alçalan Üçgen",
                                            "son_bar_ts": "2026-09-25T17:30:00+03:00"})
    assert alt == "ALARK · 4s · 120 mum · Alçalan Üçgen · son kapanan 25.09.2026 17:30"


def test_kare_altyazisi_sade_gorunumu_belirtir():
    import main as M
    alt = M._kare_altyazisi("THYAO", "1h", {"mum_sayisi": 180,
        "mod": {"sade": True}, "son_bar_ts": "2026-10-15T18:00:00+03:00"})
    assert alt.startswith("THYAO · 1s · sade · 180 mum")


def test_kare_altyazisi_lejant_kisaltmasini_bildirir():
    import main as M
    alt = M._kare_altyazisi("AKBNK", "4h", {"lejant_atlanan": 3})
    assert "lejant kısaltıldı (+3)" in alt


def test_alarm_kare_altyazisi_lejant_kisaltmasini_bildirir():
    from notifier import _grafik_basligi
    alt = _grafik_basligi({"sembol": "AKBNK"},
                          {"goruntu": {"tf_kisa": "4s"}},
                          {"mum_sayisi": 120, "lejant_atlanan": 2})
    assert alt == "AKBNK · 4s · 120 mum · lejant kısaltıldı (+2)"


def test_komut_grafik_taramayi_acar(monkeypatch):
    """`/grafik` formasyonu bulmak için botun kapısını kullanır (eskiden hiç çağrılmıyordu)."""
    import main as M
    import grafik_uret as U
    cagri = []
    def uret(hisse, tf, **k):
        cagri.append(k.get("formasyon_tara"))
        return {"yol": None, "meta": {"uyarilar": ["çizim reddi"]}, "hata": "test"}
    monkeypatch.setattr(U, "kare_uret", uret)
    monkeypatch.setattr(M, "_cache_verisi_kullanilabilir", lambda *a: True)
    sahte = SimpleNamespace(enabled=True, metinler=[], send_text=lambda m: (True, ""))
    monkeypatch.setattr(M, "_notifier_ref", sahte)
    monkeypatch.setattr(M, "_deque_manager_ref", None)
    M._grafik_isi_yurut({"hisse": "AKBNK", "tfler": ("4h",), "asama": "x"}, sahte, None)
    assert cagri == [True]


def test_formasyon_tara_hatasi_kareyi_dusurmez(monkeypatch):
    """Tarama istisnası → uyarı + formasyonsuz kare; /grafik akışı bozulmaz."""
    import grafik_uret as U
    import patterns.lifecycle as L
    class Patlar:
        def __init__(self, *a, **k): pass
        def process(self, *a, **k): raise RuntimeError("motor patladı")
    monkeypatch.setattr(L, "ArgentEngine", Patlar)
    import pandas as pd
    df = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0],
                       "volume": [1.0]})
    aday, uyarilar = U._formasyon_tara(df)
    assert aday is None
    assert uyarilar and "tarama hatası" in uyarilar[0]
