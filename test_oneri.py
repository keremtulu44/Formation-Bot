# -*- coding: utf-8 -*-
"""`/evet` · `/hayır` — gece önerisinin karar defteri.

SALT HESAP: dosya tmp_path, Supabase/Telegram taklit. Ağ yok.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import main as M
import oneri


class SahteStore:
    def __init__(self):
        self.kayitlar = {}
        self.upsert_sayisi = 0

    def upsert(self, anahtar, veri):
        self.kayitlar[anahtar] = veri
        self.upsert_sayisi += 1
        return True

    def get_many(self, anahtarlar):
        return {a: self.kayitlar[a] for a in anahtarlar if a in self.kayitlar}


class SahteNotifier:
    enabled = True

    def __init__(self):
        self.mesajlar = []

    def send_text(self, metin, deneme=2):
        self.mesajlar.append(metin)
        return True, "mesaj gonderildi"


def _oneri_metni():
    return ("🌙 Gece denetimi\nÖlçüm: fazla -1.20 yüzde puanı, eşik +3 → "
            "bayrak kaldırılsın önerisi.\n/evet ile onayla ya da /hayır ile reddet.")


def _bekleyen(monkeypatch, tmp_path, metin=None):
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(tmp_path / "o.json"))
    oneri.kaydet({"gun": "2026-10-25", "metin": metin or _oneri_metni(),
                  "karar": "bayrak_kaldirilsin", "ozet": "bayrak kaldırılsın",
                  "durum": "bekliyor"})


# --- defter -----------------------------------------------------------------

def test_evet_karari_yazar(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    cevap = oneri.cevapla("evet")
    assert "onaylandı" in cevap
    assert "kendiliğinden hiçbir eşiği" in cevap        # otomatik uygulama YOK
    kayit = oneri.yukle()["oneri"]
    assert kayit["durum"] == "onaylandi" and kayit["cevap_zamani"]
    assert oneri.bekleyen() is None


def test_hayir_karari_yazar_ve_tekrar_susar(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    cevap = oneri.cevapla("hayır")
    assert "reddedildi" in cevap
    assert "Ölçüm aynen sürer" in cevap                  # ölçüm durdurulmuyor
    assert oneri.yukle()["oneri"]["durum"] == "reddedildi"
    assert oneri.bekleyen() is None


def test_bekleyen_yoksa_acikca_soyler(monkeypatch, tmp_path):
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(tmp_path / "yok.json"))
    for cevap in ("evet", "hayır"):
        metin = oneri.cevapla(cevap)
        assert "Bekleyen gece önerisi yok" in metin


def test_anlasilmayan_yanit_kayit_yazmaz(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    metin = oneri.cevapla("belki")
    assert "anlaşılmadı" in metin
    assert oneri.bekleyen() is not None                  # öneri hâlâ bekliyor


def test_tekrar_korumasi_ayni_metinde_calisir(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    oneri.cevapla("evet")
    assert oneri.tekrar_mi(_oneri_metni()) is True
    # farklı metin (koşullar değişti) → yeniden sorulur
    assert oneri.tekrar_mi("başka öneri") is False
    # 7 günden sonra tekrar sorulur
    sonra = datetime.now() + timedelta(days=8)
    assert oneri.tekrar_mi(_oneri_metni(), simdi=sonra) is False


def test_yanitlanmamis_oneri_tekrar_sayilmaz(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    assert oneri.tekrar_mi(_oneri_metni()) is False


def test_karar_supabase_yedegine_de_yazilir(monkeypatch, tmp_path):
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(tmp_path / "o.json"))
    store = SahteStore()
    oneri.kaydet({"gun": "2026-10-25", "metin": _oneri_metni(), "durum": "bekliyor"},
                 store=store)
    oneri.cevapla("hayır", store=store)
    assert store.kayitlar[oneri.SUPABASE_KEY]["oneri"]["durum"] == "reddedildi"
    assert store.upsert_sayisi == 2


def test_dosya_bozuksa_calismayi_dusurmez(monkeypatch, tmp_path):
    yol = tmp_path / "bozuk.json"
    yol.write_text("{bozuk", encoding="utf-8")
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(yol))
    assert oneri.yukle() == {"oneri": None}
    assert "Bekleyen gece önerisi yok" in oneri.cevapla("evet")


# --- komut bağlantısı -------------------------------------------------------

def test_komutlar_tabloda_ve_yardimda():
    assert M.TELEGRAM_KOMUTLARI["evet"] is M._komut_evet
    assert M.TELEGRAM_KOMUTLARI["hayır"] is M._komut_hayir
    for ad in ("evet", "onay", "kabul", "hayir", "hayır", "red"):
        assert ad in M.TELEGRAM_KOMUTLARI
        assert f"/{ad}" in M.KOMUT_YARDIM.lower()


def test_komut_gece_onerisini_yanitlar(monkeypatch, tmp_path):
    _bekleyen(monkeypatch, tmp_path)
    monkeypatch.setattr(M, "_supabase_store_ref", None, raising=False)
    assert "onaylandı" in M._komut_evet("")


def test_komut_hatasi_sessiz_kalmaz(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "_supabase_store_ref", None, raising=False)

    def patlat(*a, **k):
        raise RuntimeError("defter okunamadı")
    monkeypatch.setattr(oneri, "cevapla", patlat)
    assert "okunamadı" in M._komut_hayir("")


# --- gece önerisi → DM → defter --------------------------------------------

def test_gece_onerisi_deftere_bekliyor_olarak_yazilir(monkeypatch, tmp_path):
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(tmp_path / "o.json"))
    notifier = SahteNotifier()
    monkeypatch.setattr(M, "_notifier_ref", notifier, raising=False)
    monkeypatch.setattr(M, "_supabase_store_ref", None, raising=False)
    M._gece_onerisi_gonder({"kontrol": 3, "sapma": 1,
                            "sapmalar": [{"sembol": "THYAO", "tf": "1h",
                                          "neden": "desen: A → B"}]},
                           {"karar": "yetersiz", "metin": "Ölçüm: yetersiz veri."},
                           gun="2026-10-25")
    assert len(notifier.mesajlar) == 1
    kayit = oneri.bekleyen()
    assert kayit and kayit["gun"] == "2026-10-25" and kayit["sapma"] == 1
    # aynı metin yanıtlandıysa bir sonraki gece tekrar gönderilmez
    oneri.cevapla("evet")
    assert M._gece_onerisi_gonder({"kontrol": 3, "sapma": 1,
                                   "sapmalar": [{"sembol": "THYAO", "tf": "1h",
                                                 "neden": "desen: A → B"}]},
                                  {"karar": "yetersiz", "metin": "Ölçüm: yetersiz veri."},
                                  gun="2026-10-26") is False
    assert len(notifier.mesajlar) == 1


def test_yanit_hicbir_depoya_yazilamazsa_kaydedildi_denmez(tmp_path):
    # Öneri uzak kaynaktan okunur; yerel yol yazılamaz, uzak upsert başarısız.
    engel = tmp_path / "dosya"
    engel.write_text("dizin değil", encoding="utf-8")
    store = SahteStore()
    store.kayitlar[oneri.SUPABASE_KEY] = {"oneri": {"gun": "2026-10-30", "durum": "bekliyor"}}
    store.upsert = lambda *_args: False

    metin = oneri.cevapla("evet", store=store, data_dir=str(engel))
    assert "kaydedilemedi" in metin and "tamamlanmadı" in metin
    assert "onaylandı" not in metin and "kayda geçti" not in metin
    assert oneri.bekleyen(store=store, data_dir=str(engel)) is not None


def test_yerel_yazilamasa_uzak_basari_karari_kaydeder(tmp_path):
    engel = tmp_path / "dosya"
    engel.write_text("dizin değil", encoding="utf-8")
    store = SahteStore()
    store.kayitlar[oneri.SUPABASE_KEY] = {"oneri": {"gun": "2026-10-30", "durum": "bekliyor"}}

    metin = oneri.cevapla("hayır", store=store, data_dir=str(engel))
    assert "reddedildi" in metin
    assert store.kayitlar[oneri.SUPABASE_KEY]["oneri"]["durum"] == "reddedildi"
    assert oneri.bekleyen(store=store, data_dir=str(engel)) is None


def test_gece_onerisi_defter_hatasi_ayri_uyari_gonderir(monkeypatch, tmp_path):
    monkeypatch.setattr(oneri, "dosya_yolu", lambda data_dir=None: str(tmp_path / "o.json"))
    notifier = SahteNotifier()
    monkeypatch.setattr(M, "_notifier_ref", notifier)
    monkeypatch.setattr(M, "_supabase_store_ref", None)
    monkeypatch.setattr(oneri, "kaydet", lambda *_args, **_kwargs: False)

    assert M._gece_onerisi_gonder({"kontrol": 1, "sapma": 1}, {}, gun="2026-10-30")
    assert len(notifier.mesajlar) == 2
    assert "/evet" in notifier.mesajlar[0]
    assert "kaydedilemedi" in notifier.mesajlar[1] and "yanıtlanamaz" in notifier.mesajlar[1]
