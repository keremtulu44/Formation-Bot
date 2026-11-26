"""Tests for `kap/` package layout, backward-compatible shim, runtime bridge, and CI parity."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import config
import deploy_check
import kap
import kap_baglam
from kap import (
    CompanyEntry,
    DisclosureStub,
    KapBackgroundRunner,
    active_kap_universe,
    alarm_kap_baglami_ekle,
    alarm_kap_baglami_oku,
    kap_arsiv_durumu,
    kap_arsiv_yolu,
    make_candidate,
    normalize_bist_ticker,
    open_archive,
)
from kap.baglam import ParseResult
from state.paths import KAP_ARSIV_DOSYA, kap_arsiv_yolu as paths_kap_arsiv_yolu


def test_package_layout_and_top_level_shim_stay_in_sync():
    assert kap.kap_baglami_ekle is kap_baglam.kap_baglami_ekle
    assert kap.KapCollectorService is kap_baglam.KapCollectorService
    assert kap.open_archive is kap_baglam.open_archive
    assert kap.AlarmArchive is kap_baglam.AlarmArchive
    assert config.KAP_BAGLAM_AKTIF is True
    assert config.kap_baglam_enabled() is True


def test_ticker_universe_and_archive_path_helpers(tmp_path, monkeypatch):
    assert normalize_bist_ticker("thyao.is") == "THYAO"
    assert normalize_bist_ticker(" BIMAS ") == "BIMAS"
    assert active_kap_universe(["THYAO.IS", "BIMAS", "thyao", ""]) == ("THYAO", "BIMAS")

    assert paths_kap_arsiv_yolu(str(tmp_path)).endswith(KAP_ARSIV_DOSYA)
    assert kap_arsiv_yolu(tmp_path) == tmp_path / KAP_ARSIV_DOSYA

    custom = tmp_path / "custom_kap.sqlite"
    monkeypatch.setattr(config, "KAP_ARSIV_YOLU", str(custom))
    assert kap_arsiv_yolu() == custom


def test_alarm_kap_baglami_respects_disabled_flag_and_missing_db(tmp_path, monkeypatch):
    db_path = tmp_path / "kap_arsiv.sqlite"
    istek: dict[str, object] = {"kap_baglami": {"eski": True}, "sembol": "THYAO"}

    # Default disabled: clears stale keys and does not touch disk.
    monkeypatch.setattr(config, "KAP_BAGLAM_AKTIF", False)
    assert alarm_kap_baglami_ekle(istek, "THYAO.IS", arsiv_yolu=db_path) is None
    assert "kap_baglami" not in istek
    assert not db_path.exists()

    # Enabled but archive missing: fail-open None, never creates empty DB.
    monkeypatch.setattr(config, "KAP_BAGLAM_AKTIF", True)
    assert alarm_kap_baglami_ekle(istek, "THYAO.IS", arsiv_yolu=db_path) is None
    assert not db_path.exists()


def test_alarm_kap_baglami_reads_verified_wal_archive_with_is_suffix_and_naive_trt(tmp_path):
    db_path = tmp_path / "kap_arsiv.sqlite"
    pub_utc = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)  # 13:00 TRT
    known_utc = datetime(2026, 9, 25, 10, 2, tzinfo=timezone.utc)
    quote = "Şirketimiz yeni üretim hattının devreye alınmasına karar vermiştir."

    stub = DisclosureStub(
        index=900001,
        published_at=pub_utc,
        title="THYAO",
        subject="Özel Durum Açıklaması (Genel)",
        summary=quote,
        disclosure_class="ODA",
        tickers=("THYAO",),
        member_oid="oid-thyao",
        minute_precision=False,
    )
    cand = make_candidate(stub, ticker="THYAO")

    with open_archive(db_path, writable=True) as archive:
        status = archive.record(
            cand,
            origin="sentetik",
            known_at=known_utc,
            topic="sirket_aciklamasi",
            quote=quote,
        )
        assert status == "hazir"

    # Naive TRT 15:00 (= 12:00 UTC) > known_utc (10:02 UTC) -> should find the verified item.
    istek: dict[str, object] = {}
    sonuc = alarm_kap_baglami_ekle(
        istek,
        "THYAO.IS",
        datetime(2026, 9, 25, 15, 0),
        arsiv_yolu=db_path,
        origin="sentetik",
        force=True,
    )
    assert sonuc is not None and sonuc["durum"] == "var"
    assert sonuc["hisse"] == "THYAO"
    assert isinstance(istek.get("kap_baglami"), dict)
    assert istek["kap_baglami"]["konu"] == "sirket_aciklamasi"
    assert istek["kap_baglami"]["olay"] == quote
    assert istek["kap_sirket_profili"]["hisse"] == "THYAO"

    # Read-only helper returns the same context without mutating caller dict.
    okunan = alarm_kap_baglami_oku(
        "THYAO",
        datetime(2026, 9, 25, 15, 0),
        arsiv_yolu=db_path,
        origin="sentetik",
        force=True,
    )
    assert okunan is not None and okunan["durum"] == "var"

    durum = kap_arsiv_durumu(db_path, origin="sentetik")
    assert durum["archive_exists"] is True
    assert durum["stats"]["hazir_baglam"] == 1


def test_kap_background_runner_starts_and_stops_cleanly_without_network(tmp_path):
    class FakeKapClient:
        def __init__(self):
            self.light_calls = 0

        async def get_text(self, path: str) -> str:
            return "[]"

        async def light(self) -> ParseResult:
            self.light_calls += 1
            return ParseResult(stubs=[])

    fake = FakeKapClient()
    db_path = tmp_path / "kap_bg.sqlite"
    with open_archive(db_path, writable=True) as archive:
        archive.save_companies(
            [
                CompanyEntry("THYAO", "oid-thyao", "TÜRK HAVA YOLLARI A.O."),
                CompanyEntry("BIMAS", "oid-bimas", "BİM BİRLEŞİK MAĞAZALAR A.Ş."),
            ],
            updated_at=datetime.now(timezone.utc),
        )
    runner = KapBackgroundRunner(
        db_path,
        universe=["THYAO.IS", "BIMAS"],
        interval_seconds=60.0,
        warmup_on_start=False,
        kap=fake,
    )
    assert runner.start() is True
    assert runner.start() is False  # idempotent while running
    deadline = time.monotonic() + 3.0
    while fake.light_calls == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    runner.stop(timeout=3.0)

    assert runner.is_running is False
    assert fake.light_calls >= 1
    assert runner.status()["last_error"] is None
    assert db_path.exists()


def test_deploy_check_verifies_kap_env_flag(monkeypatch, capsys):
    env = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
        "TELEGRAM_GRAFIK": "yok",
        "KAP_BAGLAM_AKTIF": "1",
    }
    monkeypatch.setattr(deploy_check, "env_degeri", lambda name, _dosya: env.get(name, ""))
    deploy_check.kontrol_env({}, canli_mod=False)
    out = capsys.readouterr().out
    assert "KAP_BAGLAM_AKTIF açık ve kap/httpx modülleri hazır" in out


def test_health_summary_reports_kap_ai_shadow_and_ai_client():
    import main as main_mod

    ozet = main_mod._saglik_ozeti()
    assert ozet["kap_baglam"] == {"aktif": True, "calisiyor": False, "son_hata": None}
    assert ozet["ai_shadow_aktif"] is True
    assert ozet["ai_istemci"]["aktif"] is True
    assert ozet["ai_istemci"]["dm_aktif"] is True
    assert ozet["ai_istemci"]["public_aktif"] is True
    assert isinstance(ozet["ai_istemci"]["saglayicilar"], list)
