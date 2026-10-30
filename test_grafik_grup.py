# -*- coding: utf-8 -*-
"""`/grafik` gruptan çağrıldığında kareler GRUBA gider (2026-10-28).

Kullanıcı: "Bağlantı bu grubun, düzelt gruba gelsin" — grup
`https://t.me/FormationBot1`. Eskiden `/grafik` grupta açılsa bile kareler
DM'e gidiyordu (işleyici yalnız `arguman` alıyor, hedefi bilmiyordu).

Bu dosya üç sözleşmeyi kilitler:
  1. Dinleyici, komutun geldiği PUBLIC sohbeti bağlama yazar; DM'de boştur.
  2. `/grafik` bu bağlamı isteğe kopyalar; yalnız NEGATİF (grup) kimliği kabul eder.
  3. Teslim `grafik_sohbete_gonder(chat_id=…)` ile gruba, sonuç metni
     `send_to_chat` ile gruba gider; DM davranışı birebir korunur.

Ağa çıkılmaz: `requests` ve taşıma fonksiyonları sahtelenir.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

import main as M
import notifier as notifier_mod
import telegram_commands as tc

GRUP = "-1003990563366"
DM = "8374119250"


# ------------------------------------------------------------------ yardımcılar


class _SahteYanit:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        return self._payload

    @property
    def text(self):
        return "{}"


class _SahteRequests(types.ModuleType):
    def __init__(self):
        super().__init__("requests")
        self.cagrilar = []

    def post(self, url, json=None, timeout=None):
        self.cagrilar.append((url, dict(json or {})))
        return _SahteYanit(200)


class _SahteSession:
    def __init__(self):
        self.post_cagrilari = []

    def post(self, url, json=None, timeout=None):
        self.post_cagrilari.append((url, dict(json or {})))
        return _SahteYanit(200)


def _grup_mesaji(metin, chat_id=GRUP):
    import time

    return {"update_id": 1,
            "message": {"message_id": 11, "date": int(time.time()),
                        "chat": {"id": int(chat_id), "type": "supergroup"},
                        "from": {"id": 555, "is_bot": False, "first_name": "K"},
                        "text": metin}}


def _dm_mesaji(metin, chat_id=DM):
    import time

    return {"update_id": 2,
            "message": {"message_id": 22, "date": int(time.time()),
                        "chat": {"id": int(chat_id), "type": "private"},
                        "from": {"id": int(chat_id), "is_bot": False,
                                 "first_name": "K"},
                        "text": metin}}


def _dinleyici(handlers):
    return tc.TelegramCommandListener(
        token="111:AAA", allowed_chat_id=DM, handlers=handlers, help_text="YARDIM",
        session=_SahteSession(), public_chat_ids=[GRUP],
        public_commands={"durum"}, admin_checker=lambda _c, _u: True)


# ------------------------------------------------- 1) bağlam: hangi sohbet?


def test_public_komutta_baglam_grup_kimligini_tasir():
    gorulen = {}

    def isleyici(_arguman):
        gorulen["sohbet"] = tc.komut_sohbeti()
        return "ok"

    _dinleyici({"durum": isleyici}).handle_update(_grup_mesaji("/durum"))
    assert gorulen["sohbet"] == GRUP


def test_dm_komutunda_baglam_bostur():
    """DM yolu değişmez: hedef yine `notifier.chat_id`."""
    gorulen = {}

    def isleyici(_arguman):
        gorulen["sohbet"] = tc.komut_sohbeti()
        return "ok"

    _dinleyici({"durum": isleyici}).handle_update(_dm_mesaji("/durum"))
    assert gorulen["sohbet"] == ""


def test_baglam_komuttan_sonra_geri_alınır():
    """İşleyici başka komuta sızmasın: finally ile eski değer geri konur."""
    assert tc.komut_sohbeti() == ""
    _dinleyici({"durum": lambda _a: "ok"}).handle_update(_grup_mesaji("/durum"))
    assert tc.komut_sohbeti() == ""


def test_isleyici_patlarsa_da_baglam_geri_alınır():
    def patla(_arguman):
        raise RuntimeError("boom")

    d = _dinleyici({"durum": patla})
    d.handle_update(_grup_mesaji("/durum"))
    assert tc.komut_sohbeti() == ""


# ------------------------------- 2) `/grafik` isteği hedefi kopyalar


@pytest.fixture
def komut_ortami(monkeypatch):
    metinler = []
    n = SimpleNamespace(enabled=True, token="test-secret",
                        send_text=lambda m: (metinler.append(m) or True, ""))
    monkeypatch.setattr(M, "_notifier_ref", n)
    monkeypatch.setattr(M, "_deque_manager_ref", None)
    M._grafik_aktif_is.clear()
    yield n, metinler
    M._grafik_aktif_is.clear()


def test_grafik_gruptan_istenirse_hedef_gruba_yazilir(monkeypatch, komut_ortami):
    monkeypatch.setattr(M, "komut_sohbeti", lambda: GRUP, raising=False)
    yanit = M._komut_grafik("THYAO 4s")

    assert M._grafik_aktif_is["hedef_sohbet"] == GRUP
    assert "bu gruba" in str(yanit)
    assert "DM'e" not in str(yanit)


def test_grafik_dmden_istenirse_eski_davranis(monkeypatch, komut_ortami):
    monkeypatch.setattr(M, "komut_sohbeti", lambda: "", raising=False)
    yanit = M._komut_grafik("THYAO 4s")

    assert M._grafik_aktif_is["hedef_sohbet"] == ""
    assert "DM'e" in str(yanit)


def test_pozitif_ya_da_bozuk_kimlik_grup_sayilmaz(monkeypatch, komut_ortami):
    """DM kimliği (pozitif) veya çöp değer grup hedefi olamaz: dosya sızmasın."""
    for deger in (DM, "abc", "0"):
        M._grafik_aktif_is.clear()
        monkeypatch.setattr(M, "komut_sohbeti", lambda d=deger: d, raising=False)
        yanit = M._komut_grafik("THYAO 4s")
        assert M._grafik_aktif_is["hedef_sohbet"] == ""
        assert "DM'e" in str(yanit)


# --------------------------------- 3) teslim: kareler ve sonuç gruba gider


def _sahte_notifier():
    kayit = {"album": [], "dm_album": [], "metinler": [], "sohbet_metinleri": []}

    def sohbete_gonder(paketler, chat_id=None):
        kayit["album"].append((chat_id, list(paketler)))
        return [True] * len(paketler)

    def dm_album(paketler):
        kayit["dm_album"].append(list(paketler))
        return [True] * len(paketler)

    n = SimpleNamespace(
        enabled=True, token="test-secret",
        send_text=lambda m: (kayit["metinler"].append(m) or True, ""),
        send_to_chat=lambda m, chat_id: (kayit["sohbet_metinleri"].append((chat_id, m)) or True),
        grafik_sohbete_gonder=sohbete_gonder,
        grafik_toplu_gonder=dm_album,
    )
    return n, kayit


def test_grup_isteginde_kareler_gruba_sonuc_metni_gruba(monkeypatch, tmp_path):
    import grafik
    import grafik_uret as U

    n, kayit = _sahte_notifier()
    dosyalar = []

    def kare_yolu(hisse, tf):
        yol = tmp_path / f"{hisse}-{tf}.png"
        yol.write_bytes(b"png")
        dosyalar.append(str(yol))
        return str(yol)

    def kare_uret(hisse, tf, **kwargs):
        return {"yol": str(tmp_path / f"{hisse}-{tf}.png"),
                "meta": {"mum_sayisi": 120, "son_bar_ts": "2026-10-28T18:00:00+03:00"}}

    monkeypatch.setattr(grafik, "kare_yolu", kare_yolu)
    monkeypatch.setattr(U, "kare_uret", kare_uret)
    monkeypatch.setattr(M, "_cache_verisi_kullanilabilir", lambda *a, **k: True)

    istek = {"hisse": "THYAO", "tfler": ("1h", "4h"), "hedef_sohbet": GRUP}
    M._grafik_isi_yurut(istek, n, None)

    # Kareler gruba TEK çağrıda gitti, DM yoluna hiç dokunulmadı.
    assert len(kayit["album"]) == 1
    hedef, paketler = kayit["album"][0]
    assert hedef == GRUP
    assert len(paketler) == 2
    assert kayit["dm_album"] == []

    # Sonuç metni de gruba gitti; DM'e kopya düşmedi.
    assert kayit["sohbet_metinleri"]
    assert all(chat == GRUP for chat, _m in kayit["sohbet_metinleri"])
    assert kayit["metinler"] == []


def test_dm_isteginde_teslim_eskisi_gibi(monkeypatch, tmp_path):
    import grafik
    import grafik_uret as U

    n, kayit = _sahte_notifier()

    def kare_yolu(hisse, tf):
        yol = tmp_path / f"{hisse}-{tf}.png"
        yol.write_bytes(b"png")
        return str(yol)

    monkeypatch.setattr(grafik, "kare_yolu", kare_yolu)
    monkeypatch.setattr(U, "kare_uret",
                        lambda h, tf, **k: {"yol": kare_yolu(h, tf), "meta": {}})
    M._grafik_isi_yurut({"hisse": "THYAO", "tfler": ("4h",)}, n, None)

    assert len(kayit["dm_album"]) == 1
    assert kayit["album"] == []
    assert kayit["sohbet_metinleri"] == []
    assert kayit["metinler"]          # sonuç DM'e


def test_grup_teslimi_patlarsa_sonuc_dm_e_duser(monkeypatch, tmp_path):
    """Grup gönderimi çökse bile istek sessiz kalmaz (sonuç DM'e düşer)."""
    import grafik
    import grafik_uret as U

    n, kayit = _sahte_notifier()

    def patla(_m, _chat_id):
        raise RuntimeError("telegram down")

    n.send_to_chat = patla
    monkeypatch.setattr(grafik, "kare_yolu",
                        lambda h, tf: (tmp_path / "x.png").write_bytes(b"png")
                        or str(tmp_path / "x.png"))
    monkeypatch.setattr(U, "kare_uret",
                        lambda h, tf, **k: {"yol": str(tmp_path / "x.png"), "meta": {}})
    M._grafik_isi_yurut({"hisse": "THYAO", "tfler": ("4h",),
                         "hedef_sohbet": GRUP}, n, None)

    assert kayit["metinler"], "grup hatasında DM'e düşülmeliydi"
    assert "gruba gönderilemedi" in kayit["metinler"][-1]
    assert "DM'e aktarıldı" in kayit["metinler"][-1]


# --------------------------------------- 4) notifier: hedefli teslim yolu


@pytest.fixture
def temiz_notifier(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:" + "A" * 30)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", DM)
    monkeypatch.setenv("TELEGRAM_GROUP_ID", GRUP)
    n = notifier_mod.TelegramNotifier()
    n.public_min_aralik_sn = 0
    n.retry_bekleme_sn = 0
    return n


def test_grafik_sohbete_gonder_albumu_gruba_yollar(monkeypatch, temiz_notifier, tmp_path):
    import transport.telegram as T

    n = temiz_notifier
    kayit = {}

    def sahte_album(yollar, captions=None, chat_id=None, notifier=None, **k):
        kayit["yollar"] = list(yollar)
        kayit["chat_id"] = chat_id
        return True, "ok"

    monkeypatch.setattr(T, "medya_grubu_gonder", sahte_album)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    for p in (a, b):
        p.write_bytes(b"png")

    sonuc = n.grafik_sohbete_gonder([(str(a), "A"), (str(b), "B")], chat_id=GRUP)

    assert sonuc == [True, True]
    assert kayit["chat_id"] == GRUP
    assert not a.exists() and not b.exists()      # dosyalar silinir


def test_grafik_sohbete_gonder_tek_kare_sendphoto(monkeypatch, temiz_notifier, tmp_path):
    import transport.telegram as T

    n = temiz_notifier
    kayit = {}

    def sahte_foto(yol, chat_id=None, notifier=None, caption="", **k):
        kayit["chat_id"] = chat_id
        kayit["caption"] = caption
        return True, "ok"

    monkeypatch.setattr(T, "foto_gonder", sahte_foto)
    p = tmp_path / "tek.png"
    p.write_bytes(b"png")

    assert n.grafik_sohbete_gonder([(str(p), "THYAO 4s")], chat_id=GRUP) == [True]
    assert kayit["chat_id"] == GRUP
    assert not p.exists()


def test_grafik_sohbete_gonder_dm_hedefinde_eski_yola_delege_eder(
        monkeypatch, temiz_notifier, tmp_path):
    n = temiz_notifier
    cagri = []
    monkeypatch.setattr(n, "grafik_toplu_gonder",
                        lambda paketler: (cagri.append(paketler) or [True]))
    p = tmp_path / "x.png"
    p.write_bytes(b"png")

    assert n.grafik_sohbete_gonder([(str(p), "c")], chat_id=DM) == [True]
    assert cagri and cagri[0][0][0] == str(p)


def test_send_to_chat_public_hedefte_butce_yolunu_kullanir(monkeypatch, temiz_notifier):
    n = temiz_notifier
    cagri = []
    monkeypatch.setattr(n, "send_to_public", lambda m, deneme=1: (cagri.append(m) or True))

    assert n.send_to_chat("merhaba", GRUP) is True
    assert cagri == ["merhaba"]


def test_send_to_chat_baska_sohbete_dogrudan_yollar(monkeypatch, temiz_notifier):
    n = temiz_notifier
    sahte = _SahteRequests()
    monkeypatch.setitem(sys.modules, "requests", sahte)

    assert n.send_to_chat("sonuc", "-100999") is True
    assert sahte.cagrilar[0][1]["chat_id"] == "-100999"


def test_send_to_chat_bos_hedefte_gondermez(temiz_notifier):
    assert temiz_notifier.send_to_chat("x", "") is False


def test_grup_kurulum_ve_grup_bildirimi_cokerse_dm_uyarisi_verilir(monkeypatch):
    n, kayit = _sahte_notifier()

    def kurulum_hatasi(*_args):
        raise RuntimeError("kurulum hatası")

    def grup_hatasi(*_args):
        raise RuntimeError("grup ulaşılamadı")

    monkeypatch.setattr(M, "_grafik_isi_yurut", kurulum_hatasi)
    n.send_to_chat = grup_hatasi
    M._grafik_aktif_is["hisse"] = "THYAO"
    M._grafik_isi_calistir({"hisse": "THYAO", "hedef_sohbet": GRUP}, n, None)
    assert "gruba gönderilemedi" in kayit["metinler"][-1]
    assert "tamamlanamadı" in kayit["metinler"][-1]
    assert not M._grafik_aktif_is
