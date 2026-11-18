"""Bildirim kuyruğu zehirli-satır düzeltmeleri (2026-11-15 incelemesi).

Sorun: DeliveryOutbox FIFO'sunda tek bir kalıcı bozuk satır (tekrar kapısına
takılan, karesi hiç üretilemeyen ya da metni hiç gidemeyen) arkadaki bütün
bildirimleri sonsuza kadar kilitleyebiliyordu; süreç uyanık, /health 200
iken Telegram'a hiçbir şey gitmiyordu.
"""
from datetime import timedelta
from types import SimpleNamespace

from notification_delivery import DeliveryOutbox


def _alert(stock="TCELL", identity="formation-1"):
    return dict(stock_name=stock, timeframe="1h", formation_id=identity,
                state="KIRILIM_TEYITLI", pattern_name="Alçalan Kama",
                break_dir=-1,
                grafik_verisi={"goruntular": [{"tf": "1h", "goruntu": {"tf_kisa": "1h"}}]})


def _owner(events, **kw):
    base = dict(initial_store_data={}, persistent_store=None,
                can_send=lambda *a, **k: True,
                format_message=lambda d: "metin:" + d["stock_name"],
                _gonder_metin=lambda d: events.append("text:" + d["stock_name"]) or True,
                chat_id="42", public_chat_id="", _grafik_pace=lambda: None,
                grafik_gonderilen=0, _son_engel=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_tekrar_kapisindaki_satir_kuyrugu_kilitlemez(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    events = []
    own = _owner(events)

    def can_send(stock, *a, **k):
        if stock == "TCELL":
            own._son_engel = "tekrar"
            return False
        own._son_engel = None
        return True

    own.can_send = can_send
    box = DeliveryOutbox(own, tmp_path)
    assert box.submit(_alert("TCELL")) is False  # tekrar: kapatıldı
    assert box.submit(_alert("SISE", "formation-2")) is True  # arkadaki gitti
    assert events == ["text:SISE"]
    assert box.status()["pending"] == 0


def test_kalici_kare_hatasi_uc_denemeden_sonra_metni_serbest_birakir(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    import grafik
    monkeypatch.setattr(grafik, "kareyi_yaz", lambda *a: (None, {}))
    events = []
    box = DeliveryOutbox(_owner(events), tmp_path)
    assert box.submit(_alert()) is False
    assert events == []
    # 30 sn backoff'u aşıp denemeleri sürdür; 4. denemede metin karesiz gider.
    for _ in range(4):
        clock = box.now()
        monkeypatch.setattr(box, "now", lambda c=clock: c + timedelta(seconds=31))
        box.flush(force=True)
        monkeypatch.setattr(box, "now", DeliveryOutbox.now.__get__(box, DeliveryOutbox))
    assert events == ["text:TCELL"]
    assert box.status()["pending"] == 0


def test_metin_hatasi_backoff_basar_ve_sonsuz_tekrar_olmaz(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_GRAFIK", "yok")
    events = []
    own = _owner(events, _gonder_metin=lambda d: False)
    box = DeliveryOutbox(own, tmp_path)
    assert box.submit(_alert()) is False
    row = box.state["rows"][0]
    assert row.get("retry_at")  # backoff basıldı
    assert row.get("attempts") == 1
    assert box.flush() == 0  # backoff dolmadan yeniden denenmez
    assert row.get("attempts") == 1
