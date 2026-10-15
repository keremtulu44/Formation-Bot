from datetime import datetime, timedelta, time as dt_time

import main as main_module
from config import ISTANBUL_TZ


def test_successful_full_scan_guard_requires_today_full_success(monkeypatch):
    now = datetime.now(ISTANBUL_TZ)
    expected = len(main_module.ACTIVE_STOCKS)

    class FakeLiveState:
        status_data = {}

        def status(self):
            return dict(self.status_data)

    fake = FakeLiveState()
    monkeypatch.setattr(main_module, "_live_state", fake)
    fake.status_data = {
        "son_tarama_durumu": "tamamlandi",
        "son_tarama_beklenen_hisse": expected,
        "son_tarama_hissesi": expected,
        "son_tarama_bitis": now.isoformat(),
    }
    assert main_module._successful_full_scan_today(now) is True

    fake.status_data["son_tarama_hissesi"] = expected - 1
    assert main_module._successful_full_scan_today(now) is False
    fake.status_data["son_tarama_hissesi"] = expected
    fake.status_data["son_tarama_durumu"] = "basarisiz"
    assert main_module._successful_full_scan_today(now) is False
    fake.status_data["son_tarama_durumu"] = "tamamlandi"
    fake.status_data["son_tarama_bitis"] = (now - timedelta(days=1)).isoformat()
    assert main_module._successful_full_scan_today(now) is False


def test_summary_markers_merge_local_and_supabase(monkeypatch):
    local = {}

    class FakeStore:
        def __init__(self):
            self.markers = {"09:55": "2026-10-10", "public:18:45": "2026-10-11"}
            self.writes = []

        def get_many(self, keys):
            return {keys[0]: dict(self.markers)}

        def upsert(self, key, payload):
            self.writes.append((key, dict(payload)))
            self.markers = dict(payload)
            return True

    store = FakeStore()
    monkeypatch.setattr(main_module, "_supabase_store_ref", store)
    monkeypatch.setattr(main_module._state_persistence, "gunluk_durum_yukle",
                        lambda: dict(local))
    monkeypatch.setattr(main_module._state_persistence, "gunluk_durum_guncelle",
                        lambda update: local.update(update))

    dm, public = main_module._ozet_isaretlerini_yukle()
    assert dm["09:55"].isoformat() == "2026-10-10"
    assert public["18:45"].isoformat() == "2026-10-11"

    main_module._ozet_isaret_kaydet("18:45", datetime(2026, 10, 12).date())
    assert store.writes[-1][0] == main_module.SUMMARY_MARKERS_SUPABASE_KEY
    assert store.markers["18:45"] == "2026-10-12"
    assert store.markers["09:55"] == "2026-10-10"
    assert local["ozet_gunleri"]["18:45"] == "2026-10-12"


def test_summary_slot_guard_allows_once_per_day_and_retries_only_on_later_day():
    today = datetime.now(ISTANBUL_TZ).date()
    yesterday = today - timedelta(days=1)

    assert main_module._ozet_slot_gonderilmeli({}, "18:45", today) is True
    assert main_module._ozet_slot_gonderilmeli({"18:45": today}, "18:45", today) is False
    assert main_module._ozet_slot_gonderilmeli({"18:45": today.isoformat()}, "18:45", today) is False
    assert main_module._ozet_slot_gonderilmeli({"18:45": yesterday}, "18:45", today) is True
    assert main_module._ozet_slot_gonderilmeli({"09:55": today}, "18:45", today) is True


def test_acil_kuyruk_bireysel_gonderimi_digestten_once_kapanir():
    digest = dt_time(18, 45)
    once = ISTANBUL_TZ.localize(datetime(2026, 10, 15, 18, 42, 59))
    kesim = ISTANBUL_TZ.localize(datetime(2026, 10, 15, 18, 43, 0))
    digest_ani = ISTANBUL_TZ.localize(datetime(2026, 10, 15, 18, 45, 0))
    sonraki = ISTANBUL_TZ.localize(datetime(2026, 10, 16, 9, 0))

    assert main_module._acil_kuyruk_gonderim_penceresi_acik(once, digest) is True
    assert main_module._acil_kuyruk_gonderim_penceresi_acik(kesim, digest) is False
    assert main_module._acil_kuyruk_gonderim_penceresi_acik(digest_ani, digest) is False
    # Ertesi iş günü kuyruğun normal TTL kapısı çalışmaya devam eder.
    assert main_module._acil_kuyruk_gonderim_penceresi_acik(sonraki, digest) is True


def test_acilis_kuyrugu_ozet_sonrasinda_gondermez_ve_tuketir():
    class FakeNotifier:
        enabled = True

        def __init__(self):
            self.flushes = 0
            self.clears = 0

        def kuyruk_durumu(self):
            return {"bekleyen": 1}

        def kuyrugu_bosalt(self):
            self.flushes += 1
            return 1

        def kuyruk_tumunu_temizle(self):
            self.clears += 1
            return 1

    notifier = FakeNotifier()
    once = ISTANBUL_TZ.localize(datetime(2026, 10, 15, 18, 42))
    sonra = ISTANBUL_TZ.localize(datetime(2026, 10, 15, 18, 46))

    assert main_module._acil_kuyruk_acilista_isle(notifier, once, dt_time(18, 45)) == 1
    assert notifier.flushes == 1 and notifier.clears == 0
    assert main_module._acil_kuyruk_acilista_isle(
        notifier, sonra, dt_time(18, 45), kapanis_ozeti_gonderildi=False) == 0
    assert notifier.flushes == 1 and notifier.clears == 0  # özete bırakılır
    assert main_module._acil_kuyruk_acilista_isle(
        notifier, sonra, dt_time(18, 45), kapanis_ozeti_gonderildi=True) == 0
    assert notifier.flushes == 1 and notifier.clears == 1


def test_ozet_command_does_not_present_old_empty_snapshot_as_current(monkeypatch):
    calls = []

    class FakeLiveState:
        def formations(self):
            return []

        def status(self):
            return {
                "son_tarama_durumu": "basarisiz",
                "son_basarili_tam_tarama": "2026-10-11T18:00:00+03:00",
            }

    class FakeNotifier:
        def format_daily_summary(self, formations, payload):
            calls.append((formations, dict(payload)))
            return "stale-safe daily summary"

    monkeypatch.setattr(main_module, "_live_state", FakeLiveState())
    monkeypatch.setattr(main_module, "_notifier_ref", FakeNotifier())

    result = main_module._komut_ozet("")

    assert result == "stale-safe daily summary"
    assert calls and calls[0][0] == []
    assert calls[0][1]["tam_tarama_guncel"] is False
    assert calls[0][1]["son_basarili_tam_tarama"] == "2026-10-11T18:00:00+03:00"


def test_evening_maintenance_does_not_send_duplicate_summary(monkeypatch):
    calls = []

    class FakeNotifier:
        enabled = True

        def send_text(self, text):
            calls.append(("send_text", text))
            return True, "sent"

        def format_daily_summary(self, *args, **kwargs):
            calls.append(("format_daily_summary", args, kwargs))
            raise AssertionError("maintenance must not build/send another daily summary")

    class FakeLiveState:
        def status(self):
            return {"son_tarama_durumu": "tamamlandi"}

    class FakeDeque:
        def to_dataframe(self, _stock):
            return None

    monkeypatch.setattr(main_module, "ACTIVE_STOCKS", ["THYAO"])
    monkeypatch.setattr(main_module, "_notifier_ref", FakeNotifier())
    monkeypatch.setattr(main_module, "_live_state", FakeLiveState())

    main_module.evening_maintenance(FakeDeque(), object())

    assert calls == []
