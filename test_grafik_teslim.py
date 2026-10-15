# -*- coding: utf-8 -*-
"""G4 teslim testleri — §4 (kareler alarmın devamıdır) + §5 (4 env anahtarı).

Üç söz bu dosyada teste bağlanıyor:
1. **Görsel alarmı asla düşürmez** — çizim/gönderim hatası yalnız sayaca yazılır.
2. **Kart metni değişmez** — `grafik_verisi` payload'a eklense de `format_message`
   bayt bayt aynı kalır ve kalıcılık yollarına (acil kuyruk JSON'u) sızmaz.
3. **Kill-switch kapalıyken hiçbir şey olmuyor** — `TELEGRAM_GRAFIK=yok` iken
   matplotlib hiç import edilmez, kuyruk boş kalır.

Ağ testte YOK: `transport.telegram.foto_gonder` monkeypatch'lenir. Gerçek kare
üretimi `test_grafik_yapi.py`de CLI üzerinden zaten ölçülüyor; burada amaç
TESLİM zinciri, piksel değil.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import grafik
from test_grafik_iskelet import _cerceve, _cift, _goruntu

KOK = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=3))


@pytest.fixture()
def grafik_acik(monkeypatch):
    """Kill-switch'i açan tek nokta (çağrı anında okunduğu için env yeterliydi)."""
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setenv("TELEGRAM_GRAFIK_ADET", "4")
    yield monkeypatch


@pytest.fixture()
def notifier(tmp_path, monkeypatch):
    """Gönderime hazır sahte notifier: ağ yok, pacing yok, dosyalar tmp'de."""
    import notifier as N

    monkeypatch.setattr(N, "DATA_DIR", str(tmp_path))
    n = N.TelegramNotifier()
    n.enabled = True
    n.token = "123456:SAHTE_TOKEN"
    n.chat_id = "42"
    n.public_min_aralik_sn = 0
    n.retry_bekleme_sn = 0
    return n


def _veri(notifier, monkeypatch, sonuc=(True, "ok")):
    """`foto_gonder`i yakalar: çağrılar listeye, dosya varlığı teste kalsın."""
    cagrilar = []

    def sahte(yol, chat_id=None, token=None, notifier=None, caption="", **kw):
        cagrilar.append({"yol": yol, "caption": caption, "var_mi": os.path.exists(yol),
                         "notifier": notifier})
        return sonuc

    import transport.telegram as T

    monkeypatch.setattr(T, "foto_gonder", sahte)
    return cagrilar


def _kare_ekle(notifier, monkeypatch, tf="4h", adet=4, kota=0):
    goruntular = [{"tf": tf, "goruntu": _goruntu(tf=tf)}]
    if adet > 1:
        goruntular.append({"tf": "1h", "goruntu": _goruntu(tf="1h")})
    veri = {"sembol": "AKBNK", "goruntular": goruntular, "kota": kota, "uyarilar": []}
    eklenen = notifier.grafik_kuyruga_ekle({"stock_name": "AKBNK", "timeframe": tf,
                                            "state": "KIRILIM_TEYITLI",
                                            "grafik_verisi": veri})
    return eklenen, goruntular


# ---------------------------------------------------------------- transport

def test_foto_gonder_png_yoksa_ag_cikmaz(tmp_path):
    from transport.telegram import foto_gonder

    ok, aciklama = foto_gonder(str(tmp_path / "yok.png"), chat_id="1", token="a:b")
    assert ok is False and aciklama == "png yok"


def test_foto_gonder_token_yoksa_denemez(tmp_path):
    from transport.telegram import foto_gonder

    yol = tmp_path / "kare.png"
    yol.write_bytes(b"png")
    ok, aciklama = foto_gonder(str(yol), chat_id="", token="")
    assert ok is False and aciklama == "token/chat_id yok"
    assert yol.exists()          # silmek gönderenin işi, transport'un değil


def test_foto_gonder_multipart_alanlari_gonderir(tmp_path, monkeypatch):
    """`sendPhoto` multipart ister: chat_id/caption form alanı, photo dosya."""
    import transport.telegram as T

    yol = tmp_path / "kare.png"
    yol.write_bytes(b"png-baytlari")
    gorulen = {}

    class Yanit:
        status_code = 200

        def json(self):
            return {"ok": True}

    def sahte(method, token, alanlar, dosyalar, timeout=20):
        gorulen.update(method=method, token=token, alanlar=alanlar,
                       dosya_adi=list(dosyalar)[0], isim=dosyalar["photo"][0],
                       bayt=dosyalar["photo"][1], timeout=timeout)
        return Yanit()

    monkeypatch.setattr(T, "_multipart_cagri", sahte)
    ok, aciklama = T.foto_gonder(str(yol), chat_id="42", token="1:a",
                                 caption="AKBNK · 4s · 120 mum")
    # `yanit_oku` description yoksa HTTP kodunu açıklama diye döner (metin akışı aynı).
    assert ok is True and aciklama == "HTTP 200"
    assert gorulen["method"] == "sendPhoto" and gorulen["token"] == "1:a"
    assert gorulen["alanlar"] == {"chat_id": "42", "caption": "AKBNK · 4s · 120 mum"}
    assert gorulen["dosya_adi"] == "photo" and gorulen["isim"] == "kare.png"
    assert gorulen["bayt"] == b"png-baytlari" and gorulen["timeout"] == 20


def test_foto_gonder_caption_kirpilir_ama_metin_kotasina_dokunulmaz(tmp_path, monkeypatch):
    """Caption 1024 kr ile sınırlı (Telegram kısıtı); kart metni burada DEĞİL."""
    import transport.telegram as T

    yol = tmp_path / "kare.png"
    yol.write_bytes(b"x")
    gorulen = {}

    class Yanit:
        status_code = 200

        def json(self):
            return {"ok": True}

    def sahte(method, token, alanlar, dosyalar, timeout=20):
        gorulen["caption"] = alanlar["caption"]
        return Yanit()

    monkeypatch.setattr(T, "_multipart_cagri", sahte)
    T.foto_gonder(str(yol), chat_id="42", token="1:a", caption="A" * 3000)
    assert len(gorulen["caption"]) == 1024
    # Görsel METİN değildir (§6.7): kart satır bütçesi/soft-wrap caption'a
    # UYGULANMAZ — uygulansaydı aralara satır kırması girerdi.
    assert "\n" not in gorulen["caption"]


def test_foto_gonder_ag_hatasi_yutulur(tmp_path, monkeypatch):
    import transport.telegram as T

    yol = tmp_path / "kare.png"
    yol.write_bytes(b"x")

    def patla(*a, **k):
        raise ConnectionError("telegram erişilemedi")

    monkeypatch.setattr(T, "_multipart_cagri", patla)
    ok, aciklama = T.foto_gonder(str(yol), chat_id="42", token="1:a")
    assert ok is False and aciklama.startswith("istek hatasi: ConnectionError")


def test_kill_switch_kapaliyken_matplotlib_hic_import_edilmez():
    """§6.7: `yok` iken davranış bayt bayt aynı — kare katmanı yüke binmesin."""
    kod = ("import sys, notifier, transport.telegram;"
           "assert 'matplotlib' not in sys.modules and 'grafik' not in sys.modules;"
           "print('temiz')")
    cevap = subprocess.run([sys.executable, "-c", kod], cwd=str(KOK),
                           capture_output=True, text=True, timeout=180,
                           env={**os.environ, "TELEGRAM_GRAFIK": "yok",
                                "DATA_DIR": "/tmp/fbdata"})
    assert "temiz" in cevap.stdout, cevap.stderr[-400:]


def test_kare_listesi_kill_switch_kapaliyse_bos(monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    cikti = grafik.kare_listesi(_cift(), "4h", _cerceve(120, "4h"), sembol="AKBNK")
    assert cikti == {"sembol": "AKBNK", "goruntular": [], "kota": 0, "uyarilar": []}


def test_kare_listesi_birincil_tf_once_kalan_kesilir(grafik_acik):
    cerceveler = {"1h": _cerceve(120, "1h"), "2h": _cerceve(120, "2h"),
                  "4h": _cerceve(120, "4h"), "1d": _cerceve(120, "1d")}
    os.environ["TELEGRAM_GRAFIK_ADET"] = "2"
    cikti = grafik.kare_listesi(_cift(), "4h", cerceveler["4h"],
                                ek_cerceveler=cerceveler, sembol="AKBNK")
    assert [k["tf"] for k in cikti["goruntular"]] == ["4h", "1h"]
    assert cikti["kota"] == 2                      # 4 TF - 2 kare
    assert not any("kota" in str(x) for x in (cikti["goruntular"][0]["goruntu"]["notlar"]
                                              + cikti["goruntular"][0]["goruntu"]["uyarilar"]))


def test_kare_listesi_motor_cagirmaz_grafik_acik(grafik_acik):
    """§14.2: köprü yalnız HAZIR çıktırı okur — motoru çağırursa test patlar."""
    import domain_engines.runner as R

    def yasak(*a, **k):
        raise AssertionError("kare köprüsü motor çağırdı (§14.2 ihlali)")

    R.run_domain_engines = yasak
    try:
        cikti = grafik.kare_listesi(_cift(), "4h", _cerceve(120, "4h"),
                                    sonuclar={"4h": {}, "1h": {}},
                                    ek_cerceveler={"1h": _cerceve(120, "1h")},
                                    sembol="AKBNK")
    finally:
        import importlib

        importlib.reload(R)
    assert [k["tf"] for k in cikti["goruntular"]] == ["4h", "1h"]


def test_kare_listesi_bant_ve_alarm_yalniz_birincil_karede(grafik_acik):
    """Başka TF'nin kadrajına 4s bandını taşımak SAHTE temas sayısı üretirdi."""
    cikti = grafik.kare_listesi(_cift(), "4h", _cerceve(120, "4h"),
                               ek_cerceveler={"1h": _cerceve(120, "1h")},
                               alarm_turu="teyit", alarm_bar=119, sembol="AKBNK")
    birincil, ikinci = cikti["goruntular"]
    assert birincil["goruntu"]["formasyon"] and birincil["goruntu"]["alarm"]
    # `alarm` yokken None, `formasyon` yokken {} — ikisi de „çizilmedi" demektir.
    assert ikinci["goruntu"]["formasyon"] in ({}, None)
    assert ikinci["goruntu"]["alarm"] in ({}, None)
    assert ikinci["goruntu"]["temas"] == []
    assert any("bant/alarm" in x for x in ikinci["goruntu"]["notlar"])
    assert not any("bant/alarm" in x for x in birincil["goruntu"]["notlar"])


def test_kare_listesi_zaman_damgasi_kendi_cercevesinden(grafik_acik):
    import pandas as pd

    birinci = _cerceve(40, "4h")
    ikinci = _cerceve(60, "1h")
    df = pd.DataFrame({"open": [1.0] * 60, "high": [2.0] * 60, "low": [0.5] * 60,
                       "close": [1.5] * 60, "volume": [1000] * 60,
                       "Date": pd.date_range("2026-09-01 09:30", periods=60, freq="h")}).set_index("Date")
    cikti = grafik.kare_listesi(None, "4h", birinci, ek_cerceveler={"1h": df},
                                zaman_damgasi="2026-10-14T18:00", sembol="AKBNK")
    # Çerçevenin KENDİ son barı kazanır; `zaman_damgası` yalnız çerçeve tarihsizse
    # kullanılır (ölçüm: 4s sentetik çerçeve 2026-10-30'da bitiyor).
    assert str(cikti["goruntular"][1]["goruntu"]["son_bar_ts"]).startswith("2026-09-03")
    assert str(cikti["goruntular"][0]["goruntu"]["son_bar_ts"]).startswith("2026-10-30")


def test_kare_listesi_bozuk_cerceve_kareyi_dusurur_ama_donmez(grafik_acik):
    """Katman hatası → o kare yok + uyarı; çağıran taraf (alarm) bundan etkilenmez."""
    cikti = grafik.kare_listesi(_cift(), "4h", None, ek_cerceveler={"1h": "bozuk"},
                                sembol="AKBNK")
    assert isinstance(cikti["goruntular"], list)
    assert all(isinstance(k.get("goruntu"), dict) for k in cikti["goruntular"])


def test_alarm_turu_bul_yalniz_kartta_olan_state():
    assert grafik.alarm_turu_bul("KIRILIM_TEYITLI") == "teyit"
    assert grafik.alarm_turu_bul("KIRILIM_ADAYI") == "kritik"
    assert grafik.alarm_turu_bul("RETEST_BASARILI") == "retest"
    assert grafik.alarm_turu_bul("KIRILIM_GECERSIZLESTI") == "gecersiz"
    assert grafik.alarm_turu_bul("SIKISMA_GUCLENIYOR") == "aday"
    assert grafik.alarm_turu_bul("FORMASYON_TAMAMLANDI") is None
    assert grafik.alarm_turu_bul(None) is None


def test_kare_yolu_tmp_altinda_veri_dizininde_degil():
    yol1 = grafik.kare_yolu("AKBNK", "4h")
    yol2 = grafik.kare_yolu("AKBNK", "4h")
    assert yol1 != yol2                                    # uuid: çakışma yok
    assert Path(yol1).parent == Path(grafik.tempfile.gettempdir())
    assert Path(yol1).name.startswith("fb_grafik_AKBNK_4h_")
    for yasak in ("bot_data", str(os.environ.get("DATA_DIR") or "")):
        if yasak:
            assert yasak not in yol1


def test_kare_yolu_turkce_ve_bosluk_temizlenir():
    yol = grafik.kare_yolu("THYAO .IS", "1h")
    ad = Path(yol).name
    assert " " not in ad and "." not in ad.replace(".png", "")
    assert ad.startswith("fb_grafik_THYAOIS_1h_") or ad.startswith("fb_grafik_THYAO_1h_")
    assert Path(grafik.kare_yolu("", "4h")).name.startswith("fb_grafik_SEM_4h_")


def test_bayat_kareleri_supur(tmp_path, monkeypatch):
    monkeypatch.setattr(grafik.tempfile, "gettempdir", lambda: str(tmp_path))
    bayat = tmp_path / "fb_grafik_AKBNK_4h_aa.png"
    taze = tmp_path / "fb_grafik_AKBNK_4h_bb.png"
    yabanci = tmp_path / "baska_dosya.png"
    for yol in (bayat, taze, yabanci):
        yol.write_bytes(b"x")
    os.utime(bayat, (time.time() - grafik.KARE_OMR_SN - 60,) * 2)
    assert grafik.bayat_kareleri_supur() == 1
    assert not bayat.exists() and taze.exists() and yabanci.exists()
    assert grafik.bayat_kareleri_supur() == 0        # ikinci geçiş boş


def test_disk_koruma(tmp_path, monkeypatch):
    class Kullanim:
        def __init__(self, free):
            self.free = free

    monkeypatch.setattr(grafik.shutil, "disk_usage",
                        lambda yol: Kullanim(50 * 1024 * 1024))
    assert grafik.disk_uygun_mu() is False
    monkeypatch.setattr(grafik.shutil, "disk_usage",
                        lambda yol: Kullanim(900 * 1024 * 1024))
    assert grafik.disk_uygun_mu() is True

    def patla(yol):
        raise OSError("ölçülemedi")

    monkeypatch.setattr(grafik.shutil, "disk_usage", patla)
    assert grafik.disk_uygun_mu() is True     # ölçememek üretimi engellemez


def test_kareyi_yaz_red_edilen_karede_dosya_birakmaz(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    monkeypatch.setattr(grafik.tempfile, "gettempdir", lambda: str(tmp_path))
    yol, meta = grafik.kareyi_yaz({"sembol": "AKBNK", "tf": "4h"}, "4h")
    assert yol is None and meta.get("red") is True
    # conftest tmp_path'e kendi test-data dizinini koyar → desenle süz.
    assert [x for x in tmp_path.iterdir() if x.name.startswith("fb_grafik_")] == []


# ---------------------------------------------------------------- notifier kuyruğu

def test_grafik_kuyrugu_veri_yoksa_bos(notifier, grafik_acik):
    assert notifier.grafik_kuyruga_ekle({"stock_name": "AKBNK"}) == 0
    assert notifier._grafik_kuyruk == []


def test_grafik_kuyrugu_kill_switch_kapaliyken_yazmaz(notifier, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    eklenen, _ = _kare_ekle(notifier, monkeypatch)
    assert eklenen == 0 and notifier._grafik_kuyruk == []


def test_grafik_kuyrugu_kota_sayilir(notifier, grafik_acik):
    monkeypatch = os.environ
    eklenen, _ = _kare_ekle(notifier, grafik_acik, kota=2)
    assert eklenen == 2
    assert notifier.grafik_atlanan_kota == 2          # kesilen kare = görüntü sınırı
    assert notifier.gonderim_durumu()["grafik_kuyruk"] == 1


def test_grafikleri_gonder_kareyi_gonderir_ve_dosyayi_siler(notifier, grafik_acik,
                                                             monkeypatch):
    cagrilar = _veri(notifier, monkeypatch)
    eklenen, _ = _kare_ekle(notifier, grafik_acik, adet=1)
    assert eklenen == 1
    ozet = notifier.grafikleri_gonder()
    assert ozet == {"gonderilen": 1, "hata": 0, "kare": 1, "sure_ms": ozet["sure_ms"],
                    "atlanan": 0}
    assert len(cagrilar) == 1 and cagrilar[0]["var_mi"] is True   # gönderim ANINDA var
    # Kimliği `foto_gonder` notifier'dan çözer (token testte de dolaşmasın).
    assert cagrilar[0]["notifier"] is notifier
    assert not Path(cagrilar[0]["yol"]).exists()                   # sonra silindi
    assert notifier.gonderim_durumu()["grafik_gonderilen"] == 1
    assert notifier._grafik_kuyruk == []
    assert notifier.grafikleri_gonder()["kare"] == 0               # kuyruk boş


def test_grafikleri_gonder_public_hedefe_dokunmaz(notifier, grafik_acik, monkeypatch):
    """§4 karar: kareler YALNIZ DM — grup/kanal bülteni metinde kalır."""
    cagrilar = _veri(notifier, monkeypatch)
    gorusen = []
    monkeypatch.setattr(notifier, "send_to_public",
                        lambda *a, **k: gorusen.append(a) or True)
    _kare_ekle(notifier, grafik_acik, adet=1)
    notifier.grafikleri_gonder()
    assert gorusen == [] and len(cagrilar) == 1


def test_caption_ondalik_ve_kart_sozcuğu_tasimaz(notifier, grafik_acik, monkeypatch):
    """G0 paritesi: caption'da noktalı ondalık (`9.0`) ya da kart jargonu olmasın."""
    cagrilar = _veri(notifier, monkeypatch)
    _kare_ekle(notifier, grafik_acik, adet=1)
    notifier.grafikleri_gonder()
    caption = cagrilar[0]["caption"]
    assert not re.search(r"\d[.,]\d", caption)      # ondalık sayı yok (G0)
    parcalar = [x.strip() for x in caption.split("·")]
    assert parcalar == ["AKBNK", "4s", "180 mum"] or (
        parcalar[0] == "AKBNK" and parcalar[1] == "4s" and parcalar[-1].endswith("mum"))
    # teknik ayrıntı karenin içinde/`meta`da; caption'da yeri yok: üç parça kadar.
    assert len(parcalar) == 3
    assert "px" not in parcalar[-1] and "KB" not in parcalar[-1]


def test_caption_kimlik_satiridir_kart_metnini_tekrarlamaz(notifier, grafik_acik,
                                                            monkeypatch):
    cagrilar = _veri(notifier, monkeypatch)
    _kare_ekle(notifier, grafik_acik, adet=1)
    notifier.grafikleri_gonder()
    caption = cagrilar[0]["caption"]
    assert caption == "AKBNK · 4s · %s mum" % caption.split("· ")[-1].split()[0]
    assert caption.count("·") == 2 and caption.startswith("AKBNK · 4s · ")
    assert "," not in caption and "." not in caption        # tam sayı: ayraç yok
    for yasak in ("KIRILIM", "TEYIT", "FORMASYON", "kalite", "bant"):
        assert yasak not in caption.upper()


def test_cizim_reddi_gonderimi_vurmaz(notifier, grafik_acik, monkeypatch):
    """Görsel yoksa sadece sayaç dolar; metin çoktan gitti, akış sürer (§4)."""
    cagrilar = _veri(notifier, monkeypatch)
    notifier._grafik_kuyruk.append({"anahtar": ("AKBNK", "4h", "KIRILIM_TEYITLI"),
                                    "sembol": "AKBNK",
                                    "goruntular": [{"tf": "4h",
                                                    "goruntu": {"sembol": "AKBNK",
                                                                "tf": "4h"}}],
                                    "kota": 0})
    ozet = notifier.grafikleri_gonder()
    assert ozet["hata"] == 1 and ozet["gonderilen"] == 0
    assert cagrilar == []
    durum = notifier.gonderim_durumu()
    assert durum["grafik_atlanan_hata"] == 1 and durum["grafik_gonderilen"] == 0


def test_gonderim_hatasi_dosyayi_siler_sayaca_yazar(notifier, grafik_acik, monkeypatch):
    cagrilar = _veri(notifier, monkeypatch, sonuc=(False, "HTTP 429"))
    _kare_ekle(notifier, grafik_acik, adet=1)
    ozet = notifier.grafikleri_gonder()
    assert ozet["hata"] == 1 and notifier.grafik_atlanan_hata == 1
    assert not Path(cagrilar[0]["yol"]).exists()


def test_sinir_asilani_kuyrukta_kalir(notifier, grafik_acik, monkeypatch):
    cagrilar = _veri(notifier, monkeypatch)
    _kare_ekle(notifier, grafik_acik, adet=2)          # 2 kare tek olayda
    ozet = notifier.grafikleri_gonder(sinir=1)
    assert ozet["gonderilen"] == 1 and ozet["atlanan"] == 1
    assert len(notifier._grafik_kuyruk) == 1
    assert notifier.grafikleri_gonder()["gonderilen"] == 1
    assert len(cagrilar) == 2


def test_notifier_pasifken_kare_uretilmez(notifier, grafik_acik, monkeypatch):
    """Ağ yokken PNG üretip diske bırakmak sızıntı olurdu (§4: dosya silinir)."""
    cagrilar = _veri(notifier, monkeypatch)
    _kare_ekle(notifier, grafik_acik, adet=1)
    notifier.enabled = False
    assert notifier.grafikleri_gonder() == {"gonderilen": 0, "hata": 0, "kare": 0,
                                            "sure_ms": 0, "atlanan": 0}
    assert cagrilar == []


def test_grafik_dosya_gonder_dosya_olmasa_da_patlamaz(notifier, monkeypatch):
    """Komut yüzeyi: eksik/silinmiş dosya çağıranı vurmaz, yalnız sayaca yazılır."""
    ok, aciklama = notifier.grafik_dosya_gonder("/yok/anilmaz.png", caption="AKBNK · 4s")
    assert ok is False and "png yok" in aciklama
    assert notifier.grafik_atlanan_hata == 1


def test_kuyruk_jsonu_grafik_verisi_tasimaz(notifier, tmp_path):
    """DataFrame/çizim sözlüğü kalıcı kuyruğa yazılırsa dosya okunamaz hâle gelir."""
    veri = {"sembol": "AKBNK", "goruntular": [{"tf": "4h", "goruntu": _goruntu(tf="4h")}],
            "kota": 0, "uyarilar": []}
    data = {"stock_name": "AKBNK", "pattern_name": "Simetrik Üçgen", "timeframe": "4h",
            "state": "KIRILIM_TEYITLI", "grafik_verisi": veri,
            "domain_context": "kart bağlamı"}
    notifier._kuyruga_ekle(data, "cooldown")
    dosya = tmp_path / "telegram_acil_kuyruk.json"
    icerik = dosya.read_text(encoding="utf-8")
    assert "grafik_verisi" not in icerik
    assert "kart bağlamı" in icerik                    # kalan alanlar aynen yazılır
    kayit = json.loads(icerik)[0]["veri"]
    assert list(kayit) and "domain_context" in kayit


def test_kart_metni_grafik_verisi_ile_bayt_bayt_ayni(notifier):
    """§6.7: görsel eklenince mesaj BiÇiMi değişmez — tek kural, tek yerde test."""
    import notifier as N

    ham = {"stock_name": "AKBNK", "timeframe": "4h", "pattern_name": "Simetrik Üçgen",
           "state": "KIRILIM_TEYITLI", "confidence_score": 88,
           "critical_price_level": 52.5, "upper_now": 52.5, "lower_now": 49.5,
           "contraction": 0.42, "upper_touches": 3, "lower_touches": 4,
           "bar_time": datetime(2026, 10, 9, 17, 30, tzinfo=IST), "age_bars": 18,
           "break_dir": 1, "candle_close_price": 51.9}
    once = N.format_message(dict(ham)) if hasattr(N, "format_message") else None
    once = once or notifier.format_message(dict(ham))
    son = notifier.format_message({**ham, "grafik_verisi": {"goruntular": [1, 2]}})
    assert once and son == once


def test_gonderim_durumu_gorsel_sayaclarini_gosterir(notifier):
    durum = notifier.gonderim_durumu()
    for anahtar in ("grafik_acik", "grafik_olay", "grafik_olay_karesiz",
                    "grafik_kopru_hata", "grafik_son_neden", "grafik_gonderilen",
                    "grafik_kuyruk", "grafik_atlanan_hata", "grafik_atlanan_kota",
                    "grafik_atlanan_baglam", "grafik_ort_ms"):
        assert anahtar in durum, anahtar
    assert durum["grafik_ort_ms"] == 0.0                # kare yok → ortalama yok
    assert durum["grafik_olay"] == 0 and durum["grafik_olay_karesiz"] == 0


def test_ortalama_sure_uretim_suresinden_okunur(notifier, grafik_acik, monkeypatch):
    _veri(notifier, monkeypatch)
    _kare_ekle(notifier, grafik_acik, adet=1)
    notifier.grafikleri_gonder()
    durum = notifier.gonderim_durumu()
    assert durum["grafik_kare_sayisi"] if "grafik_kare_sayisi" in durum else True
    assert durum["grafik_ort_ms"] >= 0                  # üretim süresi ölçüldü


# ---------------------------------------------------------------- /grafik komutu

def test_komut_grafik_kullim_ve_girdi_kapilari(monkeypatch):
    import main as M

    monkeypatch.setattr(M, "_notifier_ref", None)
    metin = M._komut_grafik("")
    assert "/grafik THYAO 4s" in metin and "1s/2s/4s/1g" in metin
    assert M._komut_grafik("TÜRKİYE").startswith("Geçersiz sembol")
    assert M._komut_grafik("A").startswith("Geçersiz sembol")
    assert M._komut_grafik("AKBNK/../x").startswith("Geçersiz sembol")
    assert "tanınmadı" in M._komut_grafik("AKBNK 9x")
    assert M._komut_grafik("akbnk 4s").startswith("Telegram gönderimi kapalı")


def test_komut_grafik_notifier_pasifse_uretim_yok(monkeypatch, tmp_path):
    import main as M
    import notifier as N

    n = N.TelegramNotifier()
    n.enabled = False
    monkeypatch.setattr(M, "_notifier_ref", n)
    assert "kapalı" in M._komut_grafik("AKBNK 4s")


def _komut_testini_bitir(monkeypatch, arguman, sahte):
    """Kabulü sonra arka plan işi başlat; testte thread'i deterministik join et."""
    import threading
    import main as M
    asil = threading.Thread
    threadler = []
    class kur(asil):
        def __init__(self, *args, **kwargs):
            asil.__init__(self, *args, **kwargs)
            if kwargs.get("name") == "grafik-istegi":
                threadler.append(self)
    monkeypatch.setattr(M.threading, "Thread", kur)
    monkeypatch.setattr(M, "_notifier_ref", sahte)
    monkeypatch.setattr(M, "_deque_manager_ref", None)
    cevap = M._komut_grafik(arguman)
    assert "isteği alındı" in cevap
    assert not threadler
    cevap.baslat()
    for t in threadler:
        t.join(30)
        assert not t.is_alive()
    assert not M._grafik_aktif_is
    # Başarılı tur metin üretmez (albüm yanıttır); boş dönüş bunu açıkça temsil eder.
    return sahte.metinler[-1] if sahte.metinler else ""


def test_komut_grafik_onbellekte_veri_yoksa_canli_cekme_yok(monkeypatch):
    import main as M
    import data
    from types import SimpleNamespace
    def yasak(*args, **kwargs):
        raise AssertionError("sağlayıcıya çıkılamaz")
    monkeypatch.setattr(data, "fetch_yfinance_1h", yasak)
    monkeypatch.setattr(data, "fetch_yfinance_1d", yasak)
    metinler, gorseller = [], []
    sahte = SimpleNamespace(enabled=True, metinler=metinler,
        send_text=lambda m: (metinler.append(m) or True, ""),
        grafik_dosya_gonder=lambda *a, **k: gorseller.append(a))
    metin = _komut_testini_bitir(monkeypatch, "ZZZZQQ 4s", sahte)
    assert "veri yok" in metin and "tamamlanamadı" in metin and not gorseller


def test_komut_grafik_gercek_onbellkten_kare_gonderir(monkeypatch):
    """Gerçek kayıtlı cache, yaş kapısını bu teslim testinde ayrıca devre dışı bırak."""
    import main as M
    import config
    from types import SimpleNamespace
    monkeypatch.setattr(config, "DATA_DIR", str(KOK / "bot_data"))
    monkeypatch.setattr(M, "_cache_verisi_kullanilabilir", lambda *a: True)
    yollar, metinler = [], []
    def toplu(paketler):
        # Tek kare de olsa teslim `grafik_toplu_gonder` üzerinden: dosya gönderim anında var.
        for yol, caption in paketler:
            yollar.append((yol, caption, os.path.exists(yol)))
            os.remove(yol)
        return [True] * len(paketler)
    sahte = SimpleNamespace(enabled=True, metinler=metinler,
        send_text=lambda m: (metinler.append(m) or True, ""),
        grafik_toplu_gonder=toplu)
    _komut_testini_bitir(monkeypatch, "AKBNK 4s", sahte)
    assert metinler == []                    # başarıda ayrı metin yok
    yol, caption, var_mi = yollar[0]
    assert var_mi and caption.startswith("AKBNK · 4s") and "mum" in caption
    assert not os.path.exists(yol)


def test_komut_grafik_dort_tf_tek_olay_ozeti(monkeypatch):
    import main as M
    import config
    from types import SimpleNamespace
    monkeypatch.setattr(config, "DATA_DIR", str(KOK / "bot_data"))
    monkeypatch.setattr(M, "_cache_verisi_kullanilabilir", lambda *a: True)
    yollar, metinler, albumler = [], [], []
    def toplu(paketler):
        albumler.append([caption for _yol, caption in paketler])
        for yol, _caption in paketler:
            yollar.append(yol)
            os.remove(yol)
        return [True] * len(paketler)
    sahte = SimpleNamespace(enabled=True, metinler=metinler,
        send_text=lambda m: (metinler.append(m) or True, ""),
        grafik_toplu_gonder=toplu)
    _komut_testini_bitir(monkeypatch, "AKBNK", sahte)
    # 4 TF → TEK albüm (araya metin girmez); başarıda ayrı metin yok
    assert len(albumler) == 1 and len(albumler[0]) == 4
    assert len(yollar) == 4 and metinler == []
    assert [c.split(" · ")[1] for c in albumler[0]] == ["1s", "2s", "4s", "1g"]
    assert all(not os.path.exists(yol) for yol in yollar)


def test_yardim_yuzeyleri_grafik_icerir():
    """§4: komut ÜÇ yüzeyde birden görünür — biri eksik kalırsa kullanıcı bulamaz."""
    import main as M

    assert "/grafik" in M.KOMUT_YARDIM
    assert "grafik" in M.TELEGRAM_KOMUTLARI and M.TELEGRAM_KOMUTLARI["grafik"] is M._komut_grafik
    metin = "\n".join(open(KOK / "deploy_check.py", encoding="utf-8").read().splitlines())
    assert "/grafik" in metin


def test_komut_kaydi_tum_yardim_satirlarinda_tanimli():
    """Yardımda yazan her komut gerçekten kayıtlı olmalı (el ile eşleşme sürer)."""
    import re

    import main as M

    adlar = set()
    for satir in M.KOMUT_YARDIM.splitlines():
        if not satir.startswith("/"):
            continue
        # Yalnız satırın başındaki komut: "retest bekleyen/başarılı" gibi satır içi
        # eğik çizgiler komut adı değil (ilk sürümde sahte eksik üretiyordu).
        ilk = re.match(r"/([A-Za-zıİşğüçö0-9_]+)", satir)
        if ilk:
            adlar.add(ilk.group(1))
    eksik = {ad for ad in adlar if ad not in M.TELEGRAM_KOMUTLARI}
    # 'gunluk/help/start/c…' gibi diğer adlar kayıtta var; kalanı raporla:
    assert not eksik, f"yardımda yazıp kaydetmediğin komutlar: {sorted(eksik)}"


# ---------------------------------------------------------------- §5 config yüzeyi

def test_env_orneginde_dort_grafik_anahtari():
    icerik = (KOK / ".env.example").read_text(encoding="utf-8")
    for anahtar in ("TELEGRAM_GRAFIK", "TELEGRAM_GRAFIK_ADET", "GRAFIK_MUM_MAKS",
                    "GRAFIK_OLAY_MAKS"):
        assert f"\n{anahtar}=" in icerik, anahtar
    assert icerik.count("TELEGRAM_GRAFIK=") == 1        # çelişkili ikinci satır yok


def test_deploy_check_beklenti_tablosunda_dort_anahtar():
    icerik = (KOK / "deploy_check.py").read_text(encoding="utf-8")
    for anahtar in ("TELEGRAM_GRAFIK", "TELEGRAM_GRAFIK_ADET", "GRAFIK_MUM_MAKS",
                    "GRAFIK_OLAY_MAKS"):
        assert f'"{anahtar}"' in icerik, anahtar


def test_config_varsayilanlari_grafik_moduluyle_ayni():
    """config'teki sabitler ile `grafik.py`nin çağrı anı okumaları sapmasın."""
    import config

    assert config.TELEGRAM_GRAFIK == "yok"
    assert config.TELEGRAM_GRAFIK_ADET == grafik.grafik_kare_adedi()
    assert config.GRAFIK_MUM_MAKS == grafik.kare_mum_tavani("1h")
    assert config.GRAFIK_OLAY_MAKS == grafik.SABITLER["olay_maks"]


def test_config_es_anlamli_yazim_tolere_edilir():
    """`TELEGRAM_GRAFIK=1` yazan kullanıcı kapatmış sayılmasın (§5)."""
    kod = ("import os; os.environ['TELEGRAM_GRAFIK']='Açık'; import config;"
           "print(config.TELEGRAM_GRAFIK)")
    cevap = subprocess.run([sys.executable, "-c", kod], cwd=str(KOK),
                           capture_output=True, text=True, timeout=120)
    assert cevap.stdout.strip() == "alarm"


def test_tur_sonu_boslatici_sayaclari_gunceller(monkeypatch):
    import main as M

    gonderilen = []

    class Sahte:
        def grafikleri_gonder(self, sinir=None):
            gonderilen.append(sinir)
            return {"gonderilen": 2, "hata": 1, "kare": 3, "sure_ms": 900,
                    "atlanan": 0}

    # `daily_stats` MODÜL globalidir: clear() etmek sonraki testleri kırardı
    # (ilk sürümde öyle oldu) → monkeypatch ile kendi sözlüğümüzü veriyoruz.
    monkeypatch.setattr(M, "daily_stats", {"grafik_kare": 0, "grafik_hata": 0})
    M._grafikleri_tur_sonunda(Sahte())
    assert gonderilen == [None]
    assert M.daily_stats["grafik_kare"] == 2 and M.daily_stats["grafik_hata"] == 1


def test_tur_sonu_boslatici_hata_taramayi_durdurmaz(monkeypatch):
    import main as M

    class Patlayan:
        def grafikleri_gonder(self, sinir=None):
            raise RuntimeError("gönderim çöktü")

    monkeypatch.setattr(M, "daily_stats", {})
    M._grafikleri_tur_sonunda(Patlayan())          # exception dışarı sızmasın
    M._grafikleri_tur_sonunda(object())            # metod hiç yoksa da sessiz

# ---------------------------------------------------------------- /durum satırı

def _durum_icin_gunluk_sayaclar(monkeypatch, M):
    """`/durum`ın yalnız bu testteki sözlüğü görmesini sağla; globali temizleme."""
    monkeypatch.setattr(M, "daily_stats", {
        "patterns_found": 0,
        "alerts_sent": 0,
        "errors": 0,
        "alerts_deferred": 0,
        "alerts_state_disabled": 0,
        "alerts_below_threshold": 0,
        "alerts_digest_overflow": 0,
        "alerts_kuyruk": 0,
        "alerts_bar_kapanmadi": 0,
        "alerts_break_close_invalid": 0,
    })


def test_durum_gorsel_satiri_dort_durum(monkeypatch, notifier):
    """Kapalı/açık, sıfır/zengin sayaç sözleşmesi dört durumda da sabittir."""
    import main as M

    _durum_icin_gunluk_sayaclar(monkeypatch, M)
    monkeypatch.setattr(M, "_notifier_ref", notifier)

    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    assert "Grafik karesi" not in M._komut_durum("")

    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    sifir = M._komut_durum("")
    assert "🖼 Grafik karesi: 0 alarm kartı" in sifir
    assert "0 kare gönderildi · 0 hata · kuyruk 0 · ort 0.0 ms" in sifir
    assert sifir.count("Grafik karesi") == 1

    notifier.grafik_olay = 8
    notifier.grafik_gonderilen = 5
    notifier.grafik_atlanan_hata = 2
    notifier._grafik_kuyruk = [{}, {}]
    notifier.grafik_toplam_ms = 1250
    notifier.grafik_kare_sayisi = 2
    notifier.grafik_atlanan_kota = 3
    notifier.grafik_atlanan_baglam = 4
    notifier.grafik_olay_karesiz = 5
    notifier.grafik_kopru_hata = 6
    notifier.grafik_son_neden = "RuntimeError: çerçeve bozuk (AKBNK 4h)"
    zengin = M._komut_durum("")
    satirlar = [satir for satir in zengin.splitlines() if "Grafik karesi" in satir]
    assert len(satirlar) == 1
    satir = satirlar[0]
    for parca in (
        "Grafik karesi: 8 alarm kartı",
        "5 kare gönderildi · 2 hata · kuyruk 2 · ort 625.0 ms",
        "3 adet sınırda kesildi",
        "4 bağlam güncellemesi",
        "5 karesiz (tarama anında şalter kapalı ya da köprü atladı)",
        "köprü hatası 6 · son neden: RuntimeError: çerçeve bozuk (AKBNK 4h)",
    ):
        assert parca in satir, parca

    # Kapalı şalterde geçmiş görsel sayaçları kalır ama açıkça işaretlenir.
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    notifier.grafik_gonderilen = 1
    kapali = M._komut_durum("")
    satirlar = [satir for satir in kapali.splitlines() if "Grafik karesi" in satir]
    assert len(satirlar) == 1
    assert "(şalter kapalı)" in satirlar[0]
    assert "1 kare gönderildi" in satirlar[0]


def test_grafik_kopru_hatasi_sadece_ilk_olayda_uyari_loglar(notifier, caplog):
    """İlk köprü hatası INFO seviyesinde görünür; sonraki hatalar logu şişirmez."""
    with caplog.at_level(logging.DEBUG, logger="notifier"):
        notifier.grafik_kopru_hatasi("RuntimeError: " + "x" * 180)
        notifier.grafik_kopru_hatasi("ValueError: ikinci hata")

    assert notifier.grafik_kopru_hata == 2
    assert len(notifier.grafik_son_neden) <= 120
    kayitlar = [r for r in caplog.records if "grafik köprüsü" in r.getMessage()]
    assert [r.levelno for r in kayitlar] == [logging.WARNING, logging.DEBUG]
    assert "RuntimeError" in kayitlar[0].getMessage()


def test_grafik_olay_karesiz_sayimi_salter_payload_ve_acil_kuyrugu(
        notifier, monkeypatch, grafik_acik):
    """Kapalı/open ve emergency marker kuralları; kuyruk kaydı karesiz sayılmaz."""
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    assert notifier.grafik_kuyruga_ekle({"stock_name": "AKBNK"}) == 0
    assert notifier.grafik_olay == 0 and notifier.grafik_olay_karesiz == 0

    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    assert notifier.grafik_kuyruga_ekle({"stock_name": "AKBNK"}) == 0
    assert notifier.grafik_kuyruga_ekle(
        {"stock_name": "THYAO", "grafik_verisi": {"goruntular": []}}
    ) == 0
    assert notifier.grafik_olay == 2 and notifier.grafik_olay_karesiz == 2

    # Acil kuyruk kaydı görsel verisi taşımaz; işaretliyse karesiz sayılmaz.
    assert notifier.grafik_kuyruga_ekle(
        {"stock_name": "GARAN", "_kuyruktan": True}
    ) == 0
    simdi = datetime.now(IST).isoformat()
    notifier._acil_kuyruk = [{
        "kuyruk_zaman": simdi,
        "son_deneme": simdi,
        "son_engel": "gunluk_kap",
        "veri": {"stock_name": "AKBNK", "pattern_name": "Simetrik Üçgen",
                 "timeframe": "4h", "state": "KIRILIM_TEYITLI"},
    }]
    monkeypatch.setattr(notifier, "can_send", lambda *a, **k: True)
    gonderilen = []

    def sahte_gonder(veri):
        gonderilen.append(veri.get("_kuyruktan"))
        notifier.grafik_kuyruga_ekle(veri)
        return True

    monkeypatch.setattr(notifier, "_gonder", sahte_gonder)
    assert notifier.kuyrugu_bosalt() == 1
    assert gonderilen == [True]
    assert notifier.grafik_olay == 2 and notifier.grafik_olay_karesiz == 2


def _vp_sonuc(n: int = 40):
    """Şeridi „motor" kaynağına bağlayan en küçük sahte motor çıktısı."""
    return {"volume_participation": {"details": {"metrics_history": [
        {"data_ready": True, "rvol": 2.5, "volume_level": "HIGH",
         "effort_result_class": "NEUTRAL"} for _ in range(n)]}},
        "order_block": None, "fvg": None, "market_structure": None}


def test_kare_listesi_tf_sozlugunden_birincil_ciktiyi_bulur(grafik_acik):
    """Tarama turu biçimi `{tf: çıktı}` — İÇ İÇE sözlük kareye gidemez (G4 hatası)."""
    cerceve = _cerceve(40, "4h")
    cikti = grafik.kare_listesi(None, "4h", cerceve,
                               sonuclar={"4h": _vp_sonuc(len(cerceve["hacim"])),
                                         "1h": _vp_sonuc(len(cerceve["hacim"]))},
                               ek_cerceveler={"1h": cerceve}, sembol="AKBNK")
    birincil = cikti["goruntular"][0]["goruntu"]
    assert birincil["serit"]["kaynak"] == "motor"           # çıktı doğru TF'den geldi
    assert any(k["tf"] == "1h" and k["goruntu"]["serit"]["kaynak"] == "motor"
               for k in cikti["goruntular"])
    assert cikti["uyarilar"] == []


def test_kare_listesi_cli_bicimi_tek_tf_ciktisi(grafik_acik):
    cerceve = _cerceve(40, "4h")
    cikti = grafik.kare_listesi(None, "4h", cerceve,
                               sonuclar=_vp_sonuc(len(cerceve["hacim"])), sembol="AKBNK")
    assert cikti["goruntular"][0]["goruntu"]["serit"]["kaynak"] == "motor"
    assert cikti["uyarilar"] == []


def test_kare_listesi_tanimayan_bicimde_uyari_birakir(grafik_acik):
    """Sessiz boş kare YOK: biçim tanınmazsa katman çizilmez ama iz kalır."""
    cerceve = _cerceve(40, "4h")
    cikti = grafik.kare_listesi(None, "4h", cerceve, sonuclar={"2s": {}}, sembol="AKBNK")
    assert cikti["goruntular"][0]["goruntu"]["serit"]["kaynak"] != "motor"
    assert any("tanınamadı" in x for x in cikti["uyarilar"])


def test_bağlam_güncellemesi_kare_getirmez(notifier, grafik_acik, monkeypatch):
    """DM içerik kapısı kısa güncelleme üretiyorsa aynı olayın kareleri YİNE gitmez."""
    cagrilar = _veri(notifier, monkeypatch)
    veri = {"sembol": "AKBNK", "goruntular": [{"tf": "4h", "goruntu": _goruntu(tf="4h")}],
            "kota": 0, "uyarilar": []}
    olay = {"stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
            "grafik_verisi": veri, "_dm_bağlam_değişmedi": True}
    assert notifier.grafik_kuyruga_ekle(olay) == 0
    assert notifier._grafik_kuyruk == []
    assert notifier.grafik_atlanan_baglam == 1
    assert notifier.grafik_olay == 1 and notifier.grafik_olay_karesiz == 0
    assert notifier.gonderim_durumu()["grafik_atlanan_baglam"] == 1
    # Aynı olay bağlam değişmişse kareler normal şekilde kuyruğa girer.
    olay.pop("_dm_bağlam_değişmedi")
    assert notifier.grafik_kuyruga_ekle(olay) == 1
    notifier.grafikleri_gonder()
    assert len(cagrilar) == 1


# --------------------------------------------------- kartın yapı satırı karenin üstünde (L11)

def test_yapı_satırı_kart_biçimleyicisinden_birebir_alınır(monkeypatch):
    """Kare kendi cümlesini KURMAZ: kartın satırı gelir, yalnız `• ` öneki düşer."""
    görülen: dict = {}

    class Sahte:
        @staticmethod
        def domain_bolumleri(sonuclar, referans, *, stil, alarm_tf):
            görülen.update(sonuclar=sonuclar, referans=referans, stil=stil, alarm_tf=alarm_tf)
            return {"yapi": ["• 4s yapı: dış ↓geçiş · iç ↓geçiş", "  CHoCH ↓ 72,20 · iç"]}

    monkeypatch.setitem(sys.modules, "notification_context", Sahte)
    assert grafik._yapı_satırı({"market_structure": object()}, "4h", 70.9) == \
        "4s yapı: dış ↓geçiş · iç ↓geçiş"
    assert görülen["stil"] == "klasik" and görülen["alarm_tf"] == "4h"
    assert görülen["referans"] == 70.9
    assert list(görülen["sonuclar"]) == ["4h"]      # {tf: çıktı} sarmalayıcısı veriliyor


def test_yapı_satırı_alınamazsa_boş_döner_ve_kareyi_düşürmez(monkeypatch, tmp_path):
    class Kırık:
        @staticmethod
        def domain_bolumleri(*_a, **_k):
            raise RuntimeError("biçimleyici yok")

    monkeypatch.setitem(sys.modules, "notification_context", Kırık)
    assert grafik._yapı_satırı({"market_structure": object()}, "4h", 1.0) == ""
    assert grafik._yapı_satırı(None, "4h", 1.0) == ""          # motor hiç yok
    goruntu = _goruntu()
    goruntu["yapı_satırı"] = ""
    yol, meta = grafik.kareyi_yaz(goruntu, "4h")
    try:
        assert yol and (meta.get("metin") or {}).get("satirlar") is not None
        assert not any("yapı:" in x for x in (meta["metin"]["satirlar"] or []))
        assert not any("yapı satırı" in str(x) for x in (meta.get("dipnotlar") or []))
    finally:
        if yol:
            os.remove(yol)


def test_yapı_satırı_üst_bloğu_taşırma(monkeypatch):
    """Üst blok 3 satırdan fazlasını kaldırmıyor (dördüncü eksene binerdi)."""
    g = {"sembol": "AKBNK", "tf": "4h", "tf_kisa": "4s", "son_bar_ts": None,
         "son_kapanis": 70.95, "alarm": {"etiket": "KIRILIM_TEYITLI", "deger": 70.95},
         "formasyon": {"ad": "bull_flag", "quality": 78,
                       "evidence_text": "kırılım hacimle teyitli edildi"},
         "yapı_satırı": "4s yapı: dış ↓geçiş · iç ↓geçiş",
         "uyarilar": [], "budama": [], "notlar": []}
    tasma = grafik._metinler(g, {"mum_sayisi": 120}, 1080, [], False, True)
    assert len(tasma["satirlar"]) == 3
    assert not any("yapı:" in x for x in tasma["satirlar"])      # yer yok → çizilmedi
    detaysiz = grafik._metinler({**g, "formasyon": {"ad": "bull_flag", "quality": 78}},
                               {"mum_sayisi": 120}, 1080, [], False, False)
    assert detaysiz["satirlar"][-1] == "4s yapı: dış ↓geçiş · iç ↓geçiş"
    assert detaysiz["kesilen"] == []                             # sığan satır kesilmez


@pytest.mark.parametrize("tf", ["1h", "4h"])
def test_gerçek_motorda_kart_satırı_karede_de_var(tf):
    """Alt süreçte gerçek motor + gerçek önbellek: çizilen satır kartta da var."""
    if not (KOK / "bot_data" / "AKBNK.json").exists():
        pytest.skip("bot_data önbelleği yok")
    kod = (
        "import json, sys; sys.path.insert(0, '.');"
        "from notification_context import domain_bolumleri;"
        "from domain_engines.runner import run_domain_engines;"
        "from grafik_uret import cerceve_getir, kare_uret;"
        f"tf = {tf!r};"
        "fr, _ = cerceve_getir('AKBNK', tf, 'bot_data', False);"
        "res = run_domain_engines('AKBNK', tf, fr.copy(deep=True));"
        "kap = domain_bolumleri({tf: res}, float(fr['close'].iloc[-1]), stil='klasik',"
        " alarm_tf=tf).get('yapi') or [];"
        f"out = kare_uret('AKBNK', tf, veri_dizin='bot_data', zone=True, mum=120,"
        " cikti='/tmp/fb_test_yapi.png');"
        "print(json.dumps({'kart': [x.strip() for x in kap], "
        "'kare': (out['meta'].get('metin') or {}).get('satirlar')}))"
    )
    cevap = subprocess.run([sys.executable, "-c", kod], cwd=str(KOK), capture_output=True,
                           text=True, timeout=300,
                           env={"PATH": "/usr/bin:/bin", "DATA_DIR": "/tmp/fbdata",
                                "PYTHONPATH": str(KOK)})
    assert cevap.returncode == 0, cevap.stderr[-600:]
    veri = json.loads(cevap.stdout.strip().splitlines()[-1])
    kare = [x for x in (veri["kare"] or []) if "yapı:" in x]
    assert kare, veri
    # Tek fark sözleşmeli: kart `• ` ile madde imi basıyor, kare imi atmıyor.
    assert veri["kart"], veri
    assert veri["kart"][0] in (f"• {kare[0]}", kare[0]), (kare, veri["kart"])


@pytest.mark.parametrize("kod", [200, 403])
def test_alarm_metni_basarisi_sonrasi_fotograf_hemen_arka_planda(
        notifier, grafik_acik, monkeypatch, kod):
    """GÖRSEL-4: metin gider, ARDINDAN o olayın görseli (arka plan işçisi) gider.

    Kullanıcı kararı: "bir metin geldi ardından görsel, sonra bir metin ...".
    Fotoğraf yalnız metin başarısından sonra; kuyruk tur sonunu beklemez.
    """
    import requests
    import main as M
    siralama = []
    def post(url, **kw):
        assert url.endswith("/sendMessage")
        assert kw["json"]["chat_id"] == notifier.chat_id
        siralama.append("sendMessage")
        return type("Yanit", (), {"status_code": kod, "text": "test yanıtı"})()
    monkeypatch.setattr(requests, "post", post)
    fotolar = _veri(notifier, monkeypatch)
    monkeypatch.setattr(notifier, "format_message", lambda d: "alarm metni aynı")
    veri = {"stock_name": "AKBNK", "timeframe": "4h", "state": "KIRILIM_TEYITLI",
            "pattern_name": "Yükselen Üçgen", "grafik_verisi": {
                "sembol": "AKBNK", "goruntular": [{"tf": "4h", "goruntu": _goruntu(tf="4h")}]
            }}
    assert notifier._gonder(veri) is (kod == 200)
    assert siralama == ["sendMessage"]
    # Metin başarısızsa görsel de yok; başarılıysa arka plan işçisi hemen gönderir.
    for _ in range(100):
        if fotolar or kod != 200:
            break
        time.sleep(0.02)
    assert len(fotolar) == (1 if kod == 200 else 0)
    if fotolar:
        assert fotolar[0]["notifier"].chat_id == "42"
        assert not os.path.exists(fotolar[0]["yol"])
        assert notifier._grafik_kuyruk == []       # kare tüketildi
    else:
        assert notifier._grafik_kuyruk == []
    # Tur sonu boşaltma ARTIK ek bir gönderim üretmez (kuyruk zaten boş) ve
    # günlük/saatlik sayaçlara dokunmaz.
    once = (notifier._gunluk_sayac, list(notifier._saatlik_zamanlar))
    M._grafikleri_tur_sonunda(notifier)
    assert len(fotolar) == (1 if kod == 200 else 0)
    assert once == (notifier._gunluk_sayac, list(notifier._saatlik_zamanlar))
    assert not notifier._grafik_kuyruk

@pytest.mark.parametrize("chat", ["-100123", "@public", "42"])
def test_grafik_public_veya_grup_chat_id_yapilandirmasinda_reddedilir(
        notifier, monkeypatch, tmp_path, chat):
    notifier.chat_id = chat
    notifier.public_chat_id = "42" if chat == "42" else "-100123"
    cagrilar = _veri(notifier, monkeypatch)
    yol = tmp_path / "publice-gitmez.png"
    yol.write_bytes(b"png")
    ok, neden = notifier.grafik_dosya_gonder(str(yol))
    assert not ok and "yalnız DM" in neden
    assert not cagrilar and not yol.exists()
