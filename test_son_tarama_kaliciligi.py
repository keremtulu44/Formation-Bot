"""Son tarama kalıcılığı: yalnızca sahte store ve tmp_path, gerçek ağ yok."""

import json
import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import config
import main as main_mod
from live_state import LiveState, SON_TARAMA_SURUMU


class SahteStore:
    def __init__(self, veriler=None, patlat=False, yazma_sonucu=True):
        self.veriler = deepcopy(veriler or {})
        self.patlat = patlat
        self.yazma_sonucu = yazma_sonucu
        self.yazilanlar = []
        self.okunanlar = []

    def upsert(self, anahtar, veri):
        self.yazilanlar.append((anahtar, deepcopy(veri)))
        if self.patlat:
            raise OSError("sahte Supabase yazma hatası")
        if self.yazma_sonucu:
            self.veriler[anahtar] = deepcopy(veri)
        return self.yazma_sonucu

    def get_many(self, anahtarlar):
        self.okunanlar.append(list(anahtarlar))
        if self.patlat:
            raise OSError("sahte Supabase okuma hatası")
        return {k: deepcopy(self.veriler[k]) for k in anahtarlar if k in self.veriler}


def _formasyon(stock="THYAO", timeframe="1h", quality=87.0, state="KIRILIM_TEYITLI"):
    return {
        "stock": stock,
        "timeframe": timeframe,
        "pattern_name": "Simetrik Üçgen",
        "quality": quality,
        "state": state,
        "break_dir": 1,
        "upper": 120.0,
        "lower": 110.0,
        "critical_price": 120.0,
        "min_quality": 75.0,
        "alert_gonderildi": True,
    }


def _tarama(kayitlar=None, durum=None):
    if kayitlar is None:
        kayitlar = [_formasyon(), _formasyon("GARAN", "4h", 76.0, "RETEST_BASARILI")]
    durum = LiveState() if durum is None else durum
    baslangic = datetime.now(timezone.utc) - timedelta(minutes=62)
    durum.mark_started(baslangic - timedelta(minutes=5))
    durum.begin_scan(baslangic)
    for kayit in kayitlar:
        durum.record_formation(kayit)
    durum.finish_scan(
        baslangic + timedelta(minutes=2),
        son_tarama_suresi_dk=2.0,
        son_tarama_hissesi=2,
        son_tarama_formasyonu=len(kayitlar),
    )
    return durum


def _kayit(kayitlar=None, zaman=None):
    veri = _tarama(kayitlar).snapshot()
    if zaman is not None:
        veri["kayit_zamani"] = zaman.isoformat()
    return veri


def _dosyaya_yaz(data_dir, veri):
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / main_mod.SON_TARAMA_DOSYA).write_text(
        json.dumps(veri, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def _izole_main(monkeypatch):
    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    monkeypatch.setattr(main_mod, "_supabase_store_ref", None)
    monkeypatch.setattr(main_mod, "_notifier_ref", None)
    monkeypatch.setattr(main_mod, "ACTIVE_STOCKS", ["THYAO", "GARAN"])

    def ag_yasak(*_args, **_kwargs):
        raise AssertionError("Bu testte gerçek ağ isteği yasak")

    monkeypatch.setattr("requests.sessions.Session.request", ag_yasak)


def test_snapshot_json_ve_tarama_surerken_yalnizca_tamamlanmis_liste():
    durum = _tarama()
    eski = durum.formations()
    durum.begin_scan()
    durum.record_formation(_formasyon("AKBNK", "2h", 99.0))

    veri = durum.snapshot()
    assert json.loads(json.dumps(veri, ensure_ascii=False)) == veri
    assert veri["surum"] == SON_TARAMA_SURUMU == 1
    assert datetime.fromisoformat(veri["kayit_zamani"]).tzinfo is not None
    assert veri["formations"] == eski
    assert veri["status"]["tarama_suruyor"] is False
    assert "snapshot_yuklendi" not in veri["status"]
    assert durum.status()["tarama_suruyor"] is True
    veri["formations"][0]["quality"] = 0.0
    veri["status"]["tarama_sayisi"] = 999
    assert durum.formations() == eski
    assert durum.status()["tarama_sayisi"] == 2


def test_hydrate_listeyi_ve_yalnizca_kalici_status_alanlarini_yukler():
    veri = _kayit()
    veri["formations"] += [None, "bozuk", {}, _formasyon(" thyao ", "1H", 91.0)]
    veri["status"].update(manuel_tarama=True, son_tarama_hatasi="eski hata")
    durum = LiveState()

    assert durum.hydrate(veri) == 2
    assert durum.formations()[0]["stock"] == "THYAO"
    assert durum.formations()[0]["timeframe"] == "1h"
    assert durum.formations()[0]["quality"] == 91.0  # Aynı slot tek kayıt.
    st = durum.status()
    for alan in ("son_tarama_baslangic", "son_tarama_bitis", "son_tarama_suresi_dk",
                 "son_tarama_hissesi", "son_tarama_formasyonu", "tarama_sayisi"):
        assert st[alan] == veri["status"][alan]
    assert st["baslangic"] is None
    assert st["manuel_tarama"] is False
    assert st["son_tarama_hatasi"] is None
    assert st["snapshot_yuklendi"] is True
    assert st["snapshot_zamani"] == veri["kayit_zamani"]
    assert st["snapshot_formasyon"] == 2
    veri["formations"][-1]["quality"] = 0.0
    assert durum.formations()[0]["quality"] == 91.0


def test_hydrate_bozuk_ve_bos_alanli_kayitlari_reddeder():
    bozuklar = [
        None, "metin", {}, {"formations": "liste değil"},
        {"formations": [None, 7, False, "metin", [], {},
                        {"stock": None, "timeframe": "1h"},
                        {"stock": "   ", "timeframe": "1h"},
                        {"stock": "THYAO", "timeframe": ""},
                        {"stock": "THYAO", "timeframe": None},
                        {"stock": ["THYAO"], "timeframe": "1h"}]},
    ]
    for veri in bozuklar:
        durum = LiveState()
        assert durum.hydrate(veri) == 0
        assert durum.formations() == []
        assert durum.status()["snapshot_yuklendi"] is False
    # Bozuk üst yapı mevcut yayındaki listeyi silmez.
    durum = _tarama()
    eski = durum.formations()
    assert durum.hydrate({"formations": "bozuk"}) == 0
    assert durum.formations() == eski


def test_hydrate_suruyor_true_olsa_bile_yeni_surecte_tarama_surmez():
    veri = _kayit()
    veri["status"]["tarama_suruyor"] = True
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation(_formasyon("AKBNK", "2h"))

    assert durum.hydrate(veri) == 2
    assert durum.status()["tarama_suruyor"] is False
    assert durum.snapshot()["formations"] == veri["formations"]
    assert durum._pending == {}
    # Status yapısı bozuk olsa da kayıtlar yüklenir.
    veri["status"] = "bozuk"
    assert LiveState().hydrate(veri) == 2


def test_begin_scan_kayitli_kopya_notunu_temizler():
    durum = main_mod._live_state
    durum.hydrate(_kayit())
    assert "♻️" in main_mod._panel_raporu("")
    eski = durum.formations()

    durum.begin_scan()
    assert durum.status()["snapshot_yuklendi"] is False
    assert durum.formations() == eski  # Yeni tarama bitene kadar eski liste yayında.
    assert "♻️" not in main_mod._panel_raporu("")


def test_bos_snapshot_kayitli_kopya_notu_cikarmaz():
    durum = main_mod._live_state
    veri = _kayit([])
    assert durum.hydrate(veri) == 0
    st = durum.status()
    assert st["snapshot_yuklendi"] is True
    assert st["snapshot_formasyon"] == 0
    assert st["son_tarama_formasyonu"] == 0
    assert st["son_tarama_bitis"] == veri["status"]["son_tarama_bitis"]
    assert "Son başarılı analiz:" in main_mod._komut_durum("")


def test_kaydet_atomik_dosya_ve_supabase_anahtari(tmp_path, monkeypatch, caplog):
    data_dir = tmp_path / "bot_data"
    store = SahteStore()
    monkeypatch.setattr(config, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(main_mod, "_supabase_store_ref", store)
    monkeypatch.setattr(main_mod, "_live_state", _tarama())
    caplog.set_level(logging.INFO, logger=main_mod.__name__)

    assert main_mod.son_tarama_kaydet() is True
    yol = data_dir / "son_tarama.json"
    veri = json.loads(yol.read_text(encoding="utf-8"))
    assert main_mod._son_tarama_yolu() == str(yol)
    assert store.yazilanlar == [("state:son_tarama", veri)]
    assert len(veri["formations"]) == 2
    assert not (data_dir / "son_tarama.json.tmp").exists()
    assert "Son tarama kaydedildi: 2 formasyon (supabase=var, dosya=var)" in caplog.text


def test_kaydet_hatalari_botu_durdurmaz_ve_eski_dosyayi_korur(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "_live_state", _tarama())
    data_dir = tmp_path / "bot_data"
    assert main_mod.son_tarama_kaydet(SahteStore(patlat=True), data_dir) is True
    yol = data_dir / "son_tarama.json"
    eski = yol.read_text(encoding="utf-8")

    def patla(*_args, **_kwargs):
        raise OSError("sahte disk hatası")

    store = SahteStore()
    with monkeypatch.context() as mp:
        mp.setattr(main_mod.os, "replace", patla)
        assert main_mod.son_tarama_kaydet(store, data_dir) is True  # Uzak kopya yazılır.
    assert yol.read_text(encoding="utf-8") == eski
    assert not (data_dir / "son_tarama.json.tmp").exists()
    assert store.yazilanlar[0][0] == "state:son_tarama"

    engel = tmp_path / "klasor_degil"
    engel.write_text("dosya", encoding="utf-8")
    assert main_mod.son_tarama_kaydet(SahteStore(), engel) is True
    assert main_mod.son_tarama_kaydet(SahteStore(patlat=True), engel) is False
    assert main_mod.son_tarama_kaydet(SahteStore(yazma_sonucu=False), engel) is False
    assert main_mod.son_tarama_kaydet(SahteStore(yazma_sonucu=False), data_dir) is True
    with monkeypatch.context() as mp:
        mp.setattr(main_mod._live_state, "snapshot", patla)
        assert main_mod.son_tarama_kaydet(store, data_dir) is False


def test_supabase_yok_veya_hatalisa_dosya_dosya_hatalisa_supabase(tmp_path, caplog):
    veri = _kayit()
    _dosyaya_yaz(tmp_path, veri)
    caplog.set_level(logging.INFO, logger=main_mod.__name__)
    assert main_mod.son_tarama_yukle(data_dir=tmp_path) == 2
    assert main_mod._live_state.formations() == veri["formations"]
    assert "Kayıtlı son tarama yüklendi (yerel dosya): 2 formasyon" in caplog.text

    store = SahteStore(patlat=True)
    assert main_mod.son_tarama_yukle(store, tmp_path) == 2
    assert store.okunanlar == [["state:son_tarama"]]
    engel = tmp_path / "klasor_degil"
    engel.write_text("dosya", encoding="utf-8")
    store = SahteStore({"state:son_tarama": veri})
    assert main_mod.son_tarama_yukle(store, engel) == 2
    assert "Kayıtlı son tarama yüklendi (Supabase): 2 formasyon" in caplog.text


def test_en_yeni_kopya_kazanir_ve_zaman_karsilastirmasi_guvenlidir(tmp_path, caplog):
    zaman = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    dosya_verisi = _kayit([_formasyon()], zaman)
    uzak_veri = _kayit([_formasyon("GARAN", "4h")], zaman + timedelta(minutes=5))
    store = SahteStore({"state:son_tarama": uzak_veri})
    _dosyaya_yaz(tmp_path, dosya_verisi)
    caplog.set_level(logging.INFO, logger=main_mod.__name__)

    assert main_mod.son_tarama_yukle(store, tmp_path) == 1
    assert main_mod._live_state.formations()[0]["stock"] == "GARAN"
    assert "yüklendi (Supabase): 1 formasyon" in caplog.text
    dosya_verisi["kayit_zamani"] = (zaman + timedelta(minutes=10)).isoformat()
    _dosyaya_yaz(tmp_path, dosya_verisi)
    assert main_mod.son_tarama_yukle(store, tmp_path) == 1
    assert main_mod._live_state.formations()[0]["stock"] == "THYAO"
    assert "yüklendi (yerel dosya): 1 formasyon" in caplog.text

    naive = _kayit([], zaman.replace(tzinfo=None) + timedelta(days=1))
    assert main_mod._yeni_snapshot(uzak_veri, naive) is uzak_veri
    assert main_mod._yeni_snapshot(naive, uzak_veri) is naive
    for bozuk in (None, "metin", {}, {"kayit_zamani": "yanlış"}, {"kayit_zamani": 4}):
        assert main_mod._kayit_zamani(bozuk) is None
    assert main_mod._yeni_snapshot({"formations": "bozuk"}, uzak_veri) is uzak_veri
    tarihsiz = {"formations": [], "kayit_zamani": "bozuk"}
    assert main_mod._yeni_snapshot(tarihsiz, uzak_veri) is uzak_veri
    assert main_mod._yeni_snapshot(uzak_veri, tarihsiz) is uzak_veri


def test_kayit_yok_veya_bozuksa_sessizce_sifir(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=main_mod.__name__)
    assert main_mod.son_tarama_yukle(SahteStore(), tmp_path) == 0
    assert not caplog.records
    yol = tmp_path / "son_tarama.json"
    for metin in ("bozuk JSON", "null", '"metin"', "{}",
                  '{"formations":"metin"}', '{"formations":[null,1,"bozuk"]}'):
        yol.write_text(metin, encoding="utf-8")
        caplog.clear()
        assert main_mod.son_tarama_yukle(SahteStore(), tmp_path) == 0
        assert not caplog.records
        assert main_mod._live_state.status()["snapshot_yuklendi"] is False
    store = SahteStore({"state:son_tarama": {"formations": "bozuk"}})
    assert main_mod.son_tarama_yukle(store, tmp_path) == 0
    assert not caplog.records


def test_restart_panel_canli_durum_ve_kirilim_son_taramayi_gosterir(tmp_path, monkeypatch):
    store = SahteStore()
    monkeypatch.setattr(main_mod, "_supabase_store_ref", store)
    monkeypatch.setattr(main_mod, "_live_state", _tarama())
    assert main_mod.son_tarama_kaydet(data_dir=tmp_path) is True
    monkeypatch.setattr(main_mod, "_live_state", LiveState())  # Yeni süreç.
    monkeypatch.setattr(main_mod, "tarama_penceresi_acik_mi", lambda _now: False)
    monkeypatch.setattr(main_mod, "time_until_next_open", lambda _now: 3600)
    assert main_mod.son_tarama_yukle(data_dir=tmp_path) == 2

    panel = main_mod._panel_raporu("")
    assert "dolu slot 2/8" in panel
    assert "GARAN 1h — · 2h — · 4h 76🎯" in panel
    assert "THYAO 1h 87🚀" in panel
    assert "Son başarılı tarama:" in panel and "dk önce" in panel
    assert "♻️ Önceki kayıt gösteriliyor" in panel
    assert "Henüz tamamlanmış tarama yok" not in panel
    canli = main_mod._komut_canli("")
    assert "THYAO 1h Simetrik Üçgen q87" in canli
    assert "GARAN 4h Simetrik Üçgen q76" in canli
    durum = main_mod._komut_durum("")
    assert "Piyasa: KAPALI" in durum and "Sonuçtaki formasyon: 2" in durum
    assert "Son başarılı analiz:" in durum
    assert "THYAO 1h" in main_mod._komut_kirilim("")


def test_yeni_tarama_kayitli_notunu_ve_eski_listeyi_yeniler(tmp_path):
    durum = main_mod._live_state
    durum.hydrate(_kayit())
    assert "Sonuçtaki formasyon: 2" in main_mod._komut_durum("")
    _tarama([_formasyon("THYAO", "2h", 90.0)], durum)
    assert main_mod.son_tarama_kaydet(data_dir=tmp_path) is True

    assert "♻️" not in main_mod._panel_raporu("")
    assert "Son başarılı analiz:" in main_mod._komut_durum("")
    assert "dolu slot 1/8" in main_mod._panel_raporu("")
    assert "THYAO 2h Simetrik Üçgen q90" in main_mod._komut_canli("")
    assert "GARAN" not in main_mod._komut_canli("")
    veri = json.loads((tmp_path / "son_tarama.json").read_text(encoding="utf-8"))
    assert len(veri["formations"]) == 1
    assert veri["status"]["tarama_sayisi"] == 2


def test_bos_kayitli_tarama_panelde_dogru_mesaji_verir(tmp_path, monkeypatch):
    _dosyaya_yaz(tmp_path, _kayit([]))
    assert main_mod.son_tarama_yukle(data_dir=tmp_path) == 0
    panel = main_mod._panel_raporu("")
    assert "dolu slot 0/8" in panel
    assert "Son başarılı analiz tamamlandı; canlı formasyon bulunmadı" in panel
    assert "Henüz tamamlanmış tarama yok" not in panel
    assert "♻️ Önceki kayıt gösteriliyor" in panel

    monkeypatch.setattr(main_mod, "_live_state", LiveState())
    assert "Henüz başarılı analiz yok" in main_mod._panel_raporu("")


def test_hisse_ozel_basarili_tarama_diger_hisselerin_sonucunu_korur():
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation(_formasyon("THYAO", "1h", 70))
    durum.record_formation(_formasyon("GARAN", "4h", 80))
    durum.finish_scan()

    durum.begin_scan(scope=["THYAO"], replace_all=False, beklenen_hisse=1)
    durum.record_formation(_formasyon("THYAO", "1h", 90))
    durum.finish_scan(son_tarama_hissesi=1, son_tarama_beklenen_hisse=1)

    formations = {(f["stock"], f["timeframe"]): f for f in durum.formations()}
    assert formations[("THYAO", "1h")]["quality"] == 90
    assert formations[("GARAN", "4h")]["quality"] == 80


def test_basarisiz_tarama_pending_boslugunu_yayimlamaz_onceki_sonucu_korur():
    durum = LiveState()
    durum.begin_scan()
    durum.record_formation(_formasyon("THYAO", "1h", 87))
    durum.finish_scan()
    onceki = durum.formations()

    durum.begin_scan(scope=["THYAO"], replace_all=False, beklenen_hisse=1)
    durum.record_formation(_formasyon("THYAO", "1h", 99))
    durum.fail_scan("Yahoo geçici hatası", istek_hisse=1, islenen_hisse=0, hata_hisse=1)

    assert durum.formations() == onceki
    assert durum.status()["son_tarama_durumu"] == "basarisiz"


def test_acilista_son_tarama_yukle_cagriliyor():
    """A1 regresyonu: hydratE eden çağrı main_loop'ta GERÇEKTEN yapılmalı.

    Neden bu test var: fonksiyon, LiveState.hydrate ve testleri vardı ama çağrı
    main_loop'tan düşmüştü; kalıcılık yazılıyor, okunmuyordu. Böyle bir durumda
    yalnız birim testleri yeşil kalır — bu yüzden çağrının kendisi denetlenir.
    """
    import ast
    from pathlib import Path

    kaynak = Path(main_mod.__file__).read_text(encoding="utf-8")
    agac = ast.parse(kaynak)
    main_loop = next(
        (d for d in ast.walk(agac)
         if isinstance(d, ast.FunctionDef) and d.name == "main_loop"), None,
    )
    assert main_loop is not None, "main_loop bulunamadı"

    cagrilar = [
        d for d in ast.walk(main_loop)
        if isinstance(d, ast.Call)
        and ((isinstance(d.func, ast.Name) and d.func.id == "son_tarama_yukle")
             or (isinstance(d.func, ast.Attribute) and d.func.attr == "son_tarama_yukle"))
    ]
    assert cagrilar, (
        "main_loop içinde son_tarama_yukle(...) çağrısı yok: restart/uyku sonrası "
        "/panel, /canli ve sabah özeti boş kalır (kalıcılık yazılır ama okunmaz)."
    )
    # Çağrı, tarama başlamadan önce (Store kurulumu bölgesinde) yapılmalı.
    satirlar = [n.lineno for n in ast.walk(main_loop) if isinstance(n, ast.Call)]
    assert cagrilar[0].lineno <= max(satirlar), "çağrı main_loop gövdesinde olmalı"
