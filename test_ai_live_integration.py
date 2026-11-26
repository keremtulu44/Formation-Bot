"""End-to-end live integration tests for AI alarm replacement, fallback to plain card,
shadow persistence, /ai DM command, /health summary, and Render/deploy_check parity.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pandas as pd

import config
import deploy_check
import main as main_mod
from ai_prompt import (
    AIClientRouter,
    ApiWrapperClient,
    GeminiFreeClient,
    ai_health_summary,
    enrich_alarm_with_ai,
    load_local_shadow_records,
    run_manual_ai_analysis,
)
from bot.domain_alarm_service import DomainAlarmCandidate, dispatch_domain_alarm_candidates
from bot.stabil_service import StabilAlarmCandidate, dispatch_stabil_scan_candidates
from notifier import TelegramNotifier
from telegram_commands import ArkaPlanYaniti


VALID_AI_REPLY = (
    "🧭 Mevcut durum\n"
    "BIMAS 4H grafikte Simetrik Üçgen yukarı kırılım sonrası retest bekliyor; "
    "dış yapı aşağı geçişte kaldığı için görüş koşullu kararsız, yukarı eğilime yakın. "
    "En önemli karşı kanıt 4H dış yapıda henüz yukarı BOS teyidi olmamasıdır. "
    "410,75 altı kalıcı kapanış bu görünümü zayıflatır ve eski aralığa dönüş riskini artırır.\n\n"
    "🔎 Bağlam\n"
    "4H hacim motoru hazır değil, yerel hacim teyit sayılmaz. Günlük Stabil destek 390,00 "
    "seviyesinde ve fiyat bu desteğin üzerinde seyrediyor; kısa seans mumu teyit sayılmaz "
    "ve üst zaman dilimi teyidi sınırlı kalıyor.\n\n"
    "🕯️ Replay notu\n"
    "4H +OB 410,75–423,50 iki temas grubu sonrası son kapanışta orijinal bandın üzerinde; "
    "sonraki kapanmış mum henüz oluşmamış. 432,00–437,50 −OB bölgesi henüz temas almamış "
    "ve izlenecek ilk üst direnç alanı olarak duruyor.\n\n"
    "[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"
)


def _load_bimas_1h_frame() -> pd.DataFrame:
    raw = json.loads(Path("bot_data/BIMAS.json").read_text(encoding="utf-8"))
    rows = raw["candles"] if isinstance(raw, dict) and "candles" in raw else raw
    df = pd.DataFrame(rows)
    ts_col = "timestamp" if "timestamp" in df.columns else "time"
    idx = pd.to_datetime(df[ts_col], utc=True).dt.tz_convert("Europe/Istanbul")
    out = pd.DataFrame(
        {
            "Open": df["open"].astype(float).values,
            "High": df["high"].astype(float).values,
            "Low": df["low"].astype(float).values,
            "Close": df["close"].astype(float).values,
            "Volume": df["volume"].astype(float).values,
        },
        index=idx,
    )
    return out.sort_index()


def _sample_alert_data() -> dict:
    return {
        "stock_name": "BIMAS",
        "timeframe": "4h",
        "pattern_name": "Simetrik Üçgen",
        "state": "KIRILIM_TEYITLI",
        "formation_id": "BIMAS|4h|Simetrik Üçgen|100",
        "confidence_score": 92.0,
        "critical_price_level": 415.0,
        "candle_close_price": 421.5,
        "close_price": 421.5,
        "break_price": 415.0,
        "break_dir": 1,
        "break_strength": 0.9,
        "upper_now": 415.0,
        "lower_now": 402.0,
        "upper_touches": 3,
        "lower_touches": 3,
        "age_bars": 28,
        "retest_seen": True,
        "mtf_destek": True,
        "mtf_uyum": "uyumlu",
        "mtf_kontrol_edildi": True,
        "mtf_yon_biliniyor": True,
        "bant_mesafe_atr": 0.4,
        "bar_metni": "25 Eyl 14:00–18:00",
        "timestamp": pd.Timestamp("2026-09-25 18:00+03:00"),
    }


def _mock_router_wrapper_ok() -> AIClientRouter:
    sse = (
        'data: {"status": "wait", "elapsed": 15}\n'
        "data: " + json.dumps({"status": "done", "text": VALID_AI_REPLY}) + "\n"
    )
    return AIClientRouter([
        ApiWrapperClient(
            "https://wrap.example.test",
            "secret-wrap-key",
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text=sse)),
        ),
    ])


def _mock_router_fallback_to_gemini2() -> AIClientRouter:
    return AIClientRouter([
        ApiWrapperClient(
            "https://wrap.example.test",
            "secret-wrap-key",
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text='data: {"status":"problem"}\n')),
        ),
        GeminiFreeClient(
            "g1-key",
            name="gemini_free_1",
            transport=httpx.MockTransport(lambda req: httpx.Response(429, text="quota")),
        ),
        GeminiFreeClient(
            "g2-key",
            name="gemini_free_2",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    json={"candidates": [{"content": {"parts": [{"text": VALID_AI_REPLY}]}}]},
                )
            ),
        ),
    ])


def _mock_router_all_fail() -> AIClientRouter:
    return AIClientRouter([
        ApiWrapperClient(
            "https://wrap.example.test",
            "secret-wrap-key",
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text='data: {"status":"problem"}\n')),
        ),
        GeminiFreeClient(
            "g1-key",
            name="gemini_free_1",
            transport=httpx.MockTransport(lambda req: httpx.Response(429, text="quota")),
        ),
        GeminiFreeClient(
            "g2-key",
            name="gemini_free_2",
            transport=httpx.MockTransport(lambda req: httpx.Response(503, text="down")),
        ),
    ])


class _FakeWritableStore:
    enabled = True
    writable = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[dict]]] = []

    def request_table(self, table, method, *, params=None, json=None, headers=None):
        del params, headers
        self.calls.append((table, method, list(json or [])))
        return SimpleNamespace(status_code=201)


def _make_test_notifier(tmp_path, monkeypatch) -> TelegramNotifier:
    import notifier as notifier_mod

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(notifier_mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAtestTokenForUnitTests000000000000")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1001")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-100999")
    n = TelegramNotifier()
    n.public_min_aralik_sn = 0
    return n


def test_alarm_replaced_by_ai_on_both_dm_and_public_and_shadow_saved(tmp_path, monkeypatch):
    df_1h = _load_bimas_1h_frame()
    alert = _sample_alert_data()
    shadow_file = tmp_path / "ai_yorum_test.json"
    fake_store = _FakeWritableStore()

    ok = enrich_alarm_with_ai(
        alert,
        df_1h=df_1h,
        as_of="2026-09-25 18:05+03:00",
        router=_mock_router_fallback_to_gemini2(),
        shadow_local_path=shadow_file,
        shadow_store=fake_store,
    )
    assert ok is True
    assert alert["ai_yorum_saglayici"] == "gemini_free_2"

    notifier = _make_test_notifier(tmp_path, monkeypatch)
    dm_text = notifier.format_message(alert)
    pub_text = notifier.format_public_tekil(alert)

    # BOTH DM and Public receive the AI commentary IN PLACE OF the plain card!
    assert dm_text == pub_text
    assert dm_text.startswith("🤖 BIMAS · 4s · Simetrik Üçgen (Kırılım Teyitli)")
    assert "🧭 Mevcut durum" in dm_text
    assert "🔎 Bağlam" in dm_text
    assert "🕯️ Replay notu" in dm_text
    # Hidden [AI_SONUC ...] block MUST NEVER appear in Telegram!
    assert "AI_SONUC" not in dm_text
    assert "AI_SONUC" not in pub_text

    # Public queue preserves ai_yorum_mesaji cleanly.
    notifier._delivery.now = lambda: datetime(2026, 9, 25, 18, 5, tzinfo=config.ISTANBUL_TZ)
    queued = notifier.public_kuyruk(dict(alert))
    assert queued is True
    assert notifier._public_kuyruk[-1]["ai_yorum_mesaji"] == alert["ai_yorum_mesaji"]

    # Shadow record saved both locally AND to Supabase ai_yorum_test!
    rows = load_local_shadow_records(shadow_file)
    assert len(rows) == 1
    assert rows[0]["egilim"] == "yukari"
    assert rows[0]["telegrama_gitti"] is True
    assert len(fake_store.calls) == 1
    assert fake_store.calls[0][0] == "ai_yorum_test"


def test_alarm_falls_back_to_plain_card_when_all_ai_providers_fail_or_invalid_reply(tmp_path, monkeypatch):
    df_1h = _load_bimas_1h_frame()
    notifier = _make_test_notifier(tmp_path, monkeypatch)

    # 1) All 3 providers fail -> plain card on both DM & Public
    alert_fail = _sample_alert_data()
    ok_fail = enrich_alarm_with_ai(
        alert_fail,
        df_1h=df_1h,
        as_of="2026-09-25 18:05+03:00",
        router=_mock_router_all_fail(),
        shadow_local_path=tmp_path / "fail.json",
    )
    assert ok_fail is False
    assert "ai_yorum_mesaji" not in alert_fail
    dm_plain = notifier.format_message(alert_fail)
    pub_plain = notifier.format_public_tekil(alert_fail)
    assert "BIMAS" in dm_plain and "🤖 BIMAS" not in dm_plain
    assert "BIMAS" in pub_plain and "🤖 BIMAS" not in pub_plain

    # 2) AI returns garbled text failing validation -> falls back to plain card!
    bad_router = AIClientRouter([
        ApiWrapperClient(
            "https://wrap.example.test",
            "k",
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, text='data: {"status":"done","text":"bozuk yanit"}\n')
            ),
        ),
    ])
    alert_bad = _sample_alert_data()
    ok_bad = enrich_alarm_with_ai(
        alert_bad,
        df_1h=df_1h,
        as_of="2026-09-25 18:05+03:00",
        router=bad_router,
        shadow_local_path=tmp_path / "bad.json",
    )
    assert ok_bad is False
    assert "ai_yorum_mesaji" not in alert_bad
    assert "🤖 BIMAS" not in notifier.format_message(alert_bad)


def test_stabil_and_domain_single_cards_use_ai_or_fallback_to_plain_card(tmp_path, monkeypatch):
    df_1h = _load_bimas_1h_frame()
    frames_map = {"BIMAS": (df_1h, None, pd.Timestamp("2026-09-25 18:05+03:00"))}
    sent_dm: list[str] = []
    sent_pub: list[str] = []

    class _DummyNotifier:
        enabled = True
        public_enabled = True

        def send_text(self, text):
            sent_dm.append(text)
            return True, "ok"

        def send_to_public(self, text):
            sent_pub.append(text)
            return True

    # 1) Stabil 4H card replaced by AI
    beh = SimpleNamespace(
        reclaim_kind="intrabar_sweep_reclaim",
        rank_score=9.5,
        support_level=390.0,
        close_price=421.5,
        dist_atr=0.8,
        touch_count=3,
        unchanged_days=12,
        reclaim_bars_ago=0,
        momentum_kind=None,
        vol_ratio=1.6,
    )
    st_cand = StabilAlarmCandidate(
        symbol="BIMAS",
        bar_open_ts="2026-09-25T14:00:00+03:00",
        bar_close_ts="2026-09-25T18:00:00+03:00",
        bar_label="25 Eyl 14:00–18:00",
        close_price=421.5,
        support_level=390.0,
        behavior=beh,
        card_lines=("Stabil destek üstünde",),
    )
    monkeypatch.setattr(config, "AI_SHADOW_LOG", False)
    dispatch_stabil_scan_candidates(
        [st_cand],
        _DummyNotifier(),
        state_path=str(tmp_path / "stabil_state.json"),
        frames_by_symbol=frames_map,
        router=_mock_router_wrapper_ok(),
    )
    assert len(sent_dm) == 1 and sent_dm[0].startswith("🤖 BIMAS · 4s")
    assert len(sent_pub) == 1 and sent_pub[0] == sent_dm[0]
    assert "AI_SONUC" not in sent_dm[0]

    # 2) Yeni Domain card falls back to plain card when AI fails
    sent_dm.clear()
    sent_pub.clear()
    monkeypatch.setattr(config, "YENI_DOMAIN_ALARM", True)
    dom_cand = DomainAlarmCandidate(
        symbol="BIMAS",
        timeframe="4h",
        bar_open="2026-09-25T14:00:00+03:00",
        bar_close="2026-09-25T18:00:00+03:00",
        bar_label="25 Eyl 14:00–18:00",
        bar_index=100,
        close_price=421.5,
        support_level=390.0,
        dist_atr=0.8,
        relation="destek üstünde",
        reasons=("BOS ↑",),
        volume_rvol=1.4,
        volume_tier=None,
        volume_source="OK",
        data_quality="OK",
        card_lines=("Stabil destek üstünde",),
        rank_score=7.5,
    )
    dispatch_domain_alarm_candidates(
        [dom_cand],
        _DummyNotifier(),
        state_path=str(tmp_path / "domain_state.json"),
        frames_by_symbol=frames_map,
        router=_mock_router_all_fail(),
    )
    assert len(sent_dm) == 1 and "BIMAS" in sent_dm[0] and "🤖 BIMAS" not in sent_dm[0]


def test_dm_ai_command_runs_in_background_and_rejects_public_group(monkeypatch, tmp_path):
    # Direct manual helper check
    reply = run_manual_ai_analysis(
        "BIMAS",
        "4h",
        now=datetime(2026, 9, 25, 18, 5, tzinfo=config.ISTANBUL_TZ),
        router=_mock_router_wrapper_ok(),
        shadow_local_path=tmp_path / "manual_shadow.json",
    )
    assert reply.startswith("🤖 BIMAS · 4s · AI Analiz (ApiWrapper")
    assert "🧭 Mevcut durum" in reply
    assert "🧪 Özet: eğilim=yukari" in reply
    assert "[AI_SONUC" not in reply

    # Command handler: must NOT be in PUBLIC_KOMUT_ISLEYICILERI and rejects group chat id
    assert "ai" in main_mod.TELEGRAM_KOMUTLARI
    assert main_mod._komut_ai not in main_mod.PUBLIC_KOMUT_ISLEYICILERI

    monkeypatch.setattr(main_mod, "komut_sohbeti", lambda: "-1001234567890", raising=False)
    assert "özel sahip DM" in main_mod._komut_ai("BIMAS 4s")

    # DM happy path returns ArkaPlanYaniti
    monkeypatch.setattr(main_mod, "komut_sohbeti", lambda: "123456", raising=False)
    monkeypatch.setenv("AI_WRAPPER_BASE_URL", "https://wrap.example.test")
    monkeypatch.setenv("AI_WRAPPER_API_KEY", "secret-wrapper")
    monkeypatch.setattr(main_mod, "_notifier_ref", SimpleNamespace(enabled=True, send_text=lambda m: (True, "ok")))
    resp = main_mod._komut_ai("BIMAS 4s")
    assert isinstance(resp, ArkaPlanYaniti)
    assert "BIMAS" in str(resp)
    # Clean lock state after inspection (without spawning real network thread)
    with main_mod._ai_is_kilidi:
        main_mod._ai_aktif_is.clear()


def test_health_and_render_yaml_and_deploy_check_env_parity(monkeypatch, capsys):
    # 1) render.yaml exposes all AI/KAP env vars with sync: false for secrets
    lines = Path("render.yaml").read_text(encoding="utf-8").splitlines()
    env_map: dict[str, dict[str, str]] = {}
    current_key: str | None = None
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("- key:"):
            current_key = stripped.split(":", 1)[1].strip()
            env_map[current_key] = {}
        elif current_key and ":" in stripped and not stripped.startswith("#"):
            k, v = stripped.split(":", 1)
            env_map[current_key][k.strip()] = v.strip().strip('"').strip("'")
        elif stripped and not stripped.startswith("#") and not raw.startswith("      "):
            current_key = None

    for secret_key in (
        "AI_WRAPPER_BASE_URL",
        "AI_WRAPPER_API_KEY",
        "AI_WRAPPER_MODEL",
        "GEMINI_API_KEY_1",
        "GEMINI_API_KEY_2",
    ):
        assert secret_key in env_map
        assert env_map[secret_key].get("sync") == "false"
        assert "value" not in env_map[secret_key]
    for on_key in (
        "AI_YORUM_AKTIF",
        "AI_YORUM_DM",
        "AI_YORUM_PUBLIC",
        "AI_SHADOW_LOG",
        "KAP_BAGLAM_AKTIF",
        "KAP_WARMUP_ACILISTA",
    ):
        assert env_map[on_key]["value"] == "1"

    # 2) /health exposes provider names and NEVER exposes secrets
    summary = ai_health_summary({
        "AI_WRAPPER_BASE_URL": "https://wrap.example.test",
        "AI_WRAPPER_API_KEY": "TOP_SECRET_WRAPPER",
        "GEMINI_API_KEY_1": "TOP_SECRET_GEM1",
        "GEMINI_API_KEY_2": "TOP_SECRET_GEM2",
    })
    assert summary["saglayicilar"] == ["api_wrapper", "gemini_free_1", "gemini_free_2"]
    assert summary["hazir"] is True
    assert "TOP_SECRET" not in json.dumps(summary)

    # 3) deploy_check reports ready chain without leaking secrets
    env = {
        "TELEGRAM_BOT_TOKEN": "123:abc",
        "TELEGRAM_CHAT_ID": "12345",
        "TELEGRAM_GRAFIK": "yok",
        "AI_WRAPPER_BASE_URL": "https://wrap.example.test",
        "AI_WRAPPER_API_KEY": "TOP_SECRET_WRAPPER",
        "GEMINI_API_KEY_1": "TOP_SECRET_GEM1",
        "GEMINI_API_KEY_2": "TOP_SECRET_GEM2",
    }
    monkeypatch.setattr(deploy_check, "env_degeri", lambda name, _dosya: env.get(name, ""))
    deploy_check.kontrol_env({}, canli_mod=False)
    out = capsys.readouterr().out
    assert "AI alarm zinciri hazır: ApiWrapper -> Gemini#1 -> Gemini#2 -> düz kart" in out
    assert "TOP_SECRET" not in out
