#!/usr/bin/env python3
"""Baştan sona gerçek TCP soketli deploy + yapay alarm + API zinciri + KAP + Supabase + Telegram denetimi.

Bu teşhis aracı gerçek yerel HTTP sunucuları (ApiWrapper SSE, Gemini #1/#2,
Supabase PostgREST, Telegram Bot API) açar, gerçek SQLite WAL KAP arşivi kurar,
`main.py` `/health` + `SIGTERM` açılış/kapanışını doğrular ve gerçek
`scan_all_stocks(...)` akışında yapay alarmlar tetikleyerek tüm boru hattını
tek tek test eder.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import config  # noqa: E402
import main as main_mod  # noqa: E402
import notifier as notifier_mod  # noqa: E402
from bot.domain_alarm_service import DomainAlarmCandidate, dispatch_domain_alarm_candidates  # noqa: E402
from bot.stabil_service import StabilAlarmCandidate, dispatch_stabil_scan_candidates  # noqa: E402
from kap.baglam import DisclosureStub, make_candidate, open_archive  # noqa: E402
from kap.runtime import active_kap_universe  # noqa: E402
from telegram_commands import ArkaPlanYaniti  # noqa: E402

VALID_AI_TEXT = (
    "🧭 Mevcut durum\n"
    "Hisse 4H grafikte Simetrik Üçgen yukarı kırılım teyidi üretmiş görünüyor; "
    "dış yapı geçiş aşamasında kaldığı için görüş koşullu yukarı eğilimde. "
    "En önemli karşı kanıt üst zaman diliminde henüz teyitli yeni zirve olmamasıdır. "
    "Kırılım eşiği altı kalıcı kapanış bu görünümü zayıflatır ve eski banda dönüş riskini artırır.\n\n"
    "🔎 Bağlam\n"
    "Günlük Stabil destek seviyesi fiyatın altında korunuyor ve kısa vade zemin sağlıyor; "
    "yerel KAP arşivindeki geçmiş tarihli bildirim bağlam olarak not edilmiştir, "
    "gelecek tarihli hiçbir kayıt sızmamıştır.\n\n"
    "🕯️ Replay notu\n"
    "4H +OB bandı son kapanışta destek olarak korunmuş ve üst direnç bölgesine yaklaşmadan "
    "önce temiz alan bırakmıştır; sonraki kapanmış mumun hacim davranışı belirleyici olacaktır.\n\n"
    "[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=gonder]"
)

PAST_KAP_QUOTE = "Şirketimiz 250 milyon TL tutarında yeni yatırım sözleşmesi imzalamıştır."
FUTURE_KAP_QUOTE = "GELECEK_SIZINTI_TESTI_ASLA_GORUNMEMELI_2026_1930"

WRAPPER_SECRET = "AUDIT_WRAPPER_SECRET_TOKEN_999"
GEM1_SECRET = "AUDIT_GEM1_SECRET_KEY_111"
GEM2_SECRET = "AUDIT_GEM2_SECRET_KEY_222"
SUPA_SECRET = "sb_secret_AUDIT_SUPABASE_SECRET_333"
TG_TOKEN = "123456789:AAauditTelegramBotToken000000000000"


class AuditState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.wrapper_mode = "ok_sse"
        self.wrapper_calls: list[dict[str, Any]] = []
        self.wrapper_illegal_paths: list[str] = []
        self.gem1_mode = "ok"
        self.gem2_mode = "ok"
        self.gemini_calls: list[dict[str, Any]] = []
        self.gemini_url_key_leaks: list[str] = []
        self.supabase_rows: list[tuple[str, dict[str, Any], dict[str, str]]] = []
        self.supabase_bot_store_writes: list[str] = []
        self.telegram_messages: list[dict[str, Any]] = []


def _start_mock_servers(state: AuditState):
    class WrapperHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            del fmt, args

        def do_POST(self):
            if self.path != "/v1/ask":
                with state.lock:
                    state.wrapper_illegal_paths.append(self.path)
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized path")
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8")
            body = json.loads(raw)
            auth = self.headers.get("Authorization", "")
            with state.lock:
                mode = state.wrapper_mode
                state.wrapper_calls.append({"path": self.path, "auth": auth, "body": body, "mode": mode})
            if auth != f"Bearer {WRAPPER_SECRET}":
                self.send_response(401)
                self.end_headers()
                return
            if mode == "http_502":
                self.send_response(502)
                self.end_headers()
                self.wfile.write(b"bad gateway")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            if mode == "problem":
                self.wfile.write(b'data: {"status": "wait", "elapsed": 5}\n\n')
                self.wfile.flush()
                time.sleep(0.03)
                self.wfile.write(b'data: {"status": "problem"}\n\n')
                self.wfile.flush()
                return
            if mode == "eof_drop":
                self.wfile.write(b": keepalive\n\n")
                self.wfile.write(b'data: {"status": "wait", "elapsed": 10}\n\n')
                self.wfile.flush()
                return  # closes TCP without done/problem
            if mode == "invalid_text":
                self.wfile.write(b'data: {"status": "done", "text": "bozuk basliksiz yanit"}\n\n')
                self.wfile.flush()
                return
            # ok_sse: real streamed chunks + ASCII-escaped Turkish chars + split packet!
            self.wfile.write(b": keepalive ping\n\n")
            self.wfile.flush()
            time.sleep(0.04)
            self.wfile.write(b'data: {"status": "wait", "elapsed": 30, "id": "job-1"}\n\n')
            self.wfile.flush()
            time.sleep(0.04)
            self.wfile.write(b'data: {"status": "wait", "elapsed": 45, "future_key": 1}\n\n')
            self.wfile.flush()
            done_line = (
                "data: "
                + json.dumps(
                    {"status": "done", "text": VALID_AI_TEXT, "elapsed": 51.4, "id": "job-1"},
                    ensure_ascii=True,
                )
                + "\n\n"
            ).encode("utf-8")
            # Split across 2 TCP writes intentionally to test incremental line reassembly!
            mid = len(done_line) // 2
            self.wfile.write(done_line[:mid])
            self.wfile.flush()
            time.sleep(0.02)
            self.wfile.write(done_line[mid:])
            self.wfile.flush()

    class GeminiHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            del fmt, args

        def do_POST(self):
            if "key=" in self.path or GEM1_SECRET in self.path or GEM2_SECRET in self.path:
                with state.lock:
                    state.gemini_url_key_leaks.append(self.path)
            key = self.headers.get("x-goog-api-key", "")
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            with state.lock:
                mode = state.gem1_mode if key == GEM1_SECRET else state.gem2_mode
                state.gemini_calls.append({"path": self.path, "key": key, "body": body, "mode": mode})
            if mode == "429":
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": {"message": "quota exceeded"}}')
                return
            if mode == "503":
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"unavailable")
                return
            payload = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "INTERNAL_THOUGHT_MUST_NOT_LEAK"},
                                {"text": VALID_AI_TEXT},
                            ]
                        }
                    }
                ]
            }
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    class SupabaseHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            del fmt, args

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            hdrs = {k.lower(): v for k, v in self.headers.items()}
            with state.lock:
                if "/rest/v1/bot_store" in self.path:
                    state.supabase_bot_store_writes.append(self.path)
                for row in (body if isinstance(body, list) else [body]):
                    state.supabase_rows.append((self.path, row, hdrs))
            self.send_response(201)
            self.end_headers()

    class TelegramHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            del fmt, args

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            with state.lock:
                state.telegram_messages.append({"path": self.path, "body": body})
            resp = json.dumps({"ok": True, "result": {"message_id": len(state.telegram_messages)}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

    servers = [
        ThreadingHTTPServer(("127.0.0.1", 0), WrapperHandler),
        ThreadingHTTPServer(("127.0.0.1", 0), GeminiHandler),
        ThreadingHTTPServer(("127.0.0.1", 0), SupabaseHandler),
        ThreadingHTTPServer(("127.0.0.1", 0), TelegramHandler),
    ]
    for srv in servers:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return servers


def _load_frame_1h(symbol: str) -> pd.DataFrame:
    raw = json.loads((REPO_ROOT / "bot_data" / f"{symbol}.json").read_text(encoding="utf-8"))
    rows = raw["candles"] if isinstance(raw, dict) and "candles" in raw else raw
    df = pd.DataFrame(rows)
    ts_col = "timestamp" if "timestamp" in df.columns else "time"
    idx = pd.to_datetime(df[ts_col], utc=True).dt.tz_convert("Europe/Istanbul")
    return pd.DataFrame(
        {
            "open": df["open"].astype(float).values,
            "high": df["high"].astype(float).values,
            "low": df["low"].astype(float).values,
            "close": df["close"].astype(float).values,
            "volume": df["volume"].astype(float).values,
        },
        index=idx,
    ).sort_index()


def _seed_kap_wal_archive(db_path: Path, symbol: str) -> None:
    past_pub = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)      # 13:00 TRT (BEFORE 18:05 cut)
    past_known = datetime(2026, 9, 25, 10, 2, tzinfo=timezone.utc)
    future_pub = datetime(2026, 9, 25, 16, 30, tzinfo=timezone.utc)    # 19:30 TRT (AFTER 18:05 cut!)
    future_known = datetime(2026, 9, 25, 16, 31, tzinfo=timezone.utc)

    with open_archive(db_path, writable=True) as arsiv:
        for idx_no, pub, known, quote, subject in (
            (910001, past_pub, past_known, PAST_KAP_QUOTE, "Yeni Yatırım Sözleşmesi"),
            (910002, future_pub, future_known, FUTURE_KAP_QUOTE, "Gelecek Bildirim Testi"),
        ):
            stub = DisclosureStub(
                index=idx_no,
                published_at=pub,
                title=symbol,
                subject=subject,
                summary=quote,
                disclosure_class="ODA",
                tickers=(symbol,),
                member_oid=f"oid-{symbol.lower()}",
                minute_precision=False,
            )
            cand = make_candidate(stub, ticker=symbol)
            status = arsiv.record(
                cand,
                origin="kap_arsiv",
                known_at=known,
                topic="sirket_aciklamasi",
                quote=quote,
            )
            assert status == "hazir", f"KAP seed hatası: {status}"


def _run_synthetic_scan_alarm(
    symbol: str,
    df_1h: pd.DataFrame,
    notifier: notifier_mod.TelegramNotifier,
    now_dt: datetime,
    formation_suffix: str,
) -> None:
    """Gerçek `bot.scan.scan_all_stocks` fonksiyonunu tek sembol + yapay teyitli kırılımla koşturur."""
    # `df_1h`'yi `now_dt`'ye kadar kes ki son mum taze ve kapanmış olsun.
    df_cut = df_1h[df_1h.index <= pd.Timestamp(now_dt)].copy()
    last_close = float(df_cut["close"].iloc[-1])

    class FakeDequeManager:
        data_dir = config.DATA_DIR
        sureklilik_sorunlari: dict[str, list[Any]] = {}
        son_duzeltmeler: dict[str, Any] = {}
        bozuk_mumlar: dict[str, Any] = {}

        def to_dataframe(self, stock):
            return df_cut.copy() if stock == symbol else None

        def to_gunluk_dataframe(self, stock):
            del stock
            return None

        def append_dataframe(self, stock, df):
            del stock, df
            return True

        def save_to_disk(self, stock):
            del stock

        def gunluk_veri_eksik_mi(self, stock, *args):
            del stock, args
            return False

        def gunluk_fetch_denemesi_kaydet(self, stock, basarili=True):
            del stock, basarili

        def gunluk_veri_kaydet(self, stock, df):
            del stock, df
            return True

        def has_data(self, stock):
            return stock == symbol

        def bar_count(self, stock):
            return len(df_cut) if stock == symbol else 0

        def veri_kalitesi(self, stock):
            del stock
            return {"durum": "OK"}

    class FakeLifecycleManager:
        def scan(self, key, df_tf, tam_yeniden=True):
            del tam_yeniden
            if key == f"{symbol}_4h":
                pat = SimpleNamespace(
                    pattern_type="Simetrik Üçgen",
                    state="KIRILIM_TEYITLI",
                    stable_id=f"{symbol}|4h|Simetrik Üçgen|{formation_suffix}",
                    raw_quality=92.0,
                    quality=92.0,
                    break_dir=1,
                    break_price=round(last_close * 0.99, 2),
                    break_strength=0.92,
                    upper_now=round(last_close * 0.99, 2),
                    lower_now=round(last_close * 0.95, 2),
                    upper_line=SimpleNamespace(slope=-0.01, intercept=round(last_close * 0.99, 2)),
                    lower_line=SimpleNamespace(slope=0.01, intercept=round(last_close * 0.95, 2)),
                    contraction=0.35,
                    upper_touches=3,
                    lower_touches=3,
                    start_bar=max(0, len(df_tf) - 25),
                    end_bar=len(df_tf) - 1,
                    active=True,
                    retest_seen=True,
                    retest_bar=len(df_tf) - 1,
                )
                return SimpleNamespace(
                    active=pat,
                    state="KIRILIM_TEYITLI",
                    break_dir=1,
                    bar_index=len(df_tf) - 1,
                    effective_quality=92.0,
                    events=[],
                    retest_seen=True,
                    log="synthetic breakout confirmed",
                )
            return SimpleNamespace(
                active=None,
                state="Yok",
                break_dir=0,
                bar_index=-1,
                effective_quality=None,
                events=[],
                retest_seen=False,
                log="none",
            )

        def get_snapshot(self, key):
            del key
            return None

        def get_active_summary(self):
            return []

    # Yalnız veri çekimi ve duvar saati sentetik; alarm, AI, KAP, Supabase ve Telegram %100 GERÇEK!
    orig_dt = main_mod.datetime
    orig_fetch = main_mod.fetch_1h_stocks_paced
    orig_hb = main_mod.write_heartbeat
    orig_alarm_izni = main_mod._alarm_izni_var

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now_dt if tz is None else now_dt.astimezone(tz)

    main_mod.datetime = FrozenDatetime  # type: ignore[assignment]
    main_mod.fetch_1h_stocks_paced = lambda *args, **kwargs: ({symbol: df_cut}, {}, 0, 0)
    main_mod.write_heartbeat = lambda **kwargs: None
    main_mod._alarm_izni_var = lambda s: True
    try:
        main_mod.scan_all_stocks(
            FakeDequeManager(),
            FakeLifecycleManager(),
            notifier,
            manuel=False,
            stocks=[symbol],
            send_alerts=True,
        )
    finally:
        main_mod.datetime = orig_dt
        main_mod.fetch_1h_stocks_paced = orig_fetch
        main_mod.write_heartbeat = orig_hb
        main_mod._alarm_izni_var = orig_alarm_izni


def main() -> int:
    state = AuditState()
    srv_wrap, srv_gem, srv_supa, srv_tg = _start_mock_servers(state)
    wrap_url = f"http://127.0.0.1:{srv_wrap.server_address[1]}"
    gem_url = f"http://127.0.0.1:{srv_gem.server_address[1]}/v1beta"
    supa_url = f"http://127.0.0.1:{srv_supa.server_address[1]}"
    tg_url = f"http://127.0.0.1:{srv_tg.server_address[1]}"

    # Telegram HTTP çağrılarını yerel gerçek TCP sunucumuza yönlendir (kodun kendisi gerçek requests.post atar!)
    real_requests_post = requests.post

    def routed_post(url, *args, **kwargs):
        if isinstance(url, str) and url.startswith("https://api.telegram.org"):
            url = url.replace("https://api.telegram.org", tg_url, 1)
        return real_requests_post(url, *args, **kwargs)

    requests.post = routed_post  # type: ignore[assignment]

    try:
        with tempfile.TemporaryDirectory(prefix="formation-e2e-audit-") as tmp:
            tmp_dir = Path(tmp)
            kap_db = tmp_dir / "kap_arsiv.sqlite"

            # 1) Render/env ayarları (tırnaklı yapıştırma testi dahil!)
            os.environ["DATA_DIR"] = str(tmp_dir)
            os.environ["TELEGRAM_BOT_TOKEN"] = TG_TOKEN
            os.environ["TELEGRAM_CHAT_ID"] = "7770001"
            os.environ["TELEGRAM_GROUP_ID"] = "-1007770002"
            os.environ["TELEGRAM_GRAFIK"] = "yok"
            os.environ["AI_WRAPPER_BASE_URL"] = f'"{wrap_url}/"'  # tırnak + sonda slash!
            os.environ["AI_WRAPPER_API_KEY"] = f"'{WRAPPER_SECRET}'"  # tek tırnak!
            os.environ["GEMINI_BASE_URL"] = gem_url
            os.environ["GEMINI_API_KEY_1"] = GEM1_SECRET
            os.environ["GEMINI_API_KEY_2"] = GEM2_SECRET
            os.environ["SUPABASE_URL"] = supa_url
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = SUPA_SECRET
            os.environ["KAP_ARSIV_YOLU"] = str(kap_db)
            config.DATA_DIR = str(tmp_dir)
            notifier_mod.DATA_DIR = str(tmp_dir)
            config.KAP_ARSIV_YOLU = str(kap_db)

            # --- AŞAMA 1: Canlı main.py /health + SIGTERM deploy dumanı ---
            smoke_env = dict(os.environ)
            smoke_env["BOT_HEALTH_SMOKE_ONLY"] = "1"
            smoke_env["PORT"] = "18099"
            proc = subprocess.Popen(
                [sys.executable, str(REPO_ROOT / "main.py")],
                env=smoke_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                health_data = None
                for _ in range(40):
                    time.sleep(0.25)
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:18099/health", timeout=2) as r:
                            raw_h = r.read().decode("utf-8")
                            for sec in (WRAPPER_SECRET, GEM1_SECRET, GEM2_SECRET, SUPA_SECRET, TG_TOKEN):
                                assert sec not in raw_h, f"SECRET LEAK IN /health: {sec[:6]}"
                            health_data = json.loads(raw_h)
                            break
                    except Exception:
                        continue
                assert health_data is not None, "/health açılmadı"
                assert health_data["ai_istemci"]["hazir"] is True
                assert health_data["ai_istemci"]["saglayicilar"] == ["api_wrapper", "gemini_free_1", "gemini_free_2"]
                assert health_data["kap_baglam"]["aktif"] is True
                assert health_data["ai_shadow_aktif"] is True
            finally:
                proc.send_signal(signal.SIGTERM)
                rc = proc.wait(timeout=15)
                assert rc == 0, f"SIGTERM temiz kapanmadı: {rc}"
            print("[OK] Aşama 1: main.py deploy boot + /health + sıfır sır sızıntısı + SIGTERM exit 0")

            # --- Aşama 2: KAP evren filtresi + gerçek SQLite WAL arşivi ---
            kap_u = active_kap_universe(config.ACTIVE_STOCKS)
            for forbidden in ("XU100", "XAUUSD", "XAGUSD", "USDTRY", "BRENT"):
                assert forbidden not in kap_u, f"Makro/endeks KAP evrenine sızmış: {forbidden}"
            assert "BIMAS" in kap_u
            _seed_kap_wal_archive(kap_db, "BIMAS")
            print(f"[OK] Aşama 2: KAP evreni yalnız BIST hisseleri ({len(kap_u)} hisse) + WAL arşivi hazır")

            # --- Aşama 3: Gerçek scan_all_stocks -> ApiWrapper SSE + KAP nedenselliği + Supabase + DM/Public ---
            now_dt = datetime(2026, 9, 25, 18, 5, tzinfo=config.ISTANBUL_TZ)
            notifier = notifier_mod.TelegramNotifier()
            notifier.public_min_aralik_sn = 0
            notifier._delivery.now = lambda: now_dt
            bimas_1h = _load_frame_1h("BIMAS")

            state.wrapper_mode = "ok_sse"
            _run_synthetic_scan_alarm("BIMAS", bimas_1h, notifier, now_dt, "run1")

            assert len(state.wrapper_calls) == 1
            assert state.wrapper_illegal_paths == []
            sent_prompt = state.wrapper_calls[0]["body"]["prompt"]
            sent_system = state.wrapper_calls[0]["body"]["system"]
            assert PAST_KAP_QUOTE in sent_prompt, "Geçmiş KAP bildirimi canlı prompta girmemiş!"
            assert FUTURE_KAP_QUOTE not in sent_prompt, "GELECEK KAP bildirimi prompta sızmış!"
            assert "🧭 Mevcut durum" in sent_system
            assert len(state.gemini_calls) == 0  # ApiWrapper başarılı, yedek çağrılmadı!

            # Telegram DM + Public kontrolü
            assert len(state.telegram_messages) == 2, f"Beklenen 2 Telegram mesajı (DM+Public), gelen: {len(state.telegram_messages)}"
            dm_msg = next(m["body"]["text"] for m in state.telegram_messages if str(m["body"]["chat_id"]) == "7770001")
            pub_msg = next(m["body"]["text"] for m in state.telegram_messages if str(m["body"]["chat_id"]) == "-1007770002")
            assert dm_msg == pub_msg, "Public mesajı DM'den farklı (metni_sigdir bozması?)"
            assert dm_msg.startswith("🤖 BIMAS · 4s · Simetrik Üçgen (Kırılım Teyitli)")
            assert "🧭 Mevcut durum" in dm_msg and "🔎 Bağlam" in dm_msg and "🕯️ Replay notu" in dm_msg
            assert "AI_SONUC" not in dm_msg
            assert "\n   " not in pub_msg, "Public AI paragrafı yapay 3-boşluk girintiye bölünmüş!"

            # Supabase ai_yorum_test gerçek TCP UPSERT kontrolü
            assert len(state.supabase_rows) == 1, f"Supabase ai_yorum_test yazılmadı: {state.supabase_rows}"
            assert state.supabase_bot_store_writes == [], "Salt-okunur bot_store'a yazma girişimi!"
            supa_path, supa_row, supa_hdrs = state.supabase_rows[0]
            assert "/rest/v1/ai_yorum_test" in supa_path
            assert supa_hdrs.get("apikey") == SUPA_SECRET
            assert "authorization" not in supa_hdrs  # sb_secret_ anahtarda Bearer OLMAMALI!
            assert supa_row["sembol"] == "BIMAS" and supa_row["egilim"] == "yukari"
            assert supa_row["baglam_ozet"]["kap"]["durum"] == "var"
            print("[OK] Aşama 3: scan_all_stocks -> ApiWrapper SSE + nedensel KAP + Supabase UPSERT + DM=Public AI")

            # --- Aşama 4: ApiWrapper problem (tekrarsız) -> Gemini #1 429 -> Gemini #2 OK (thought temiz) ---
            state.telegram_messages.clear()
            state.wrapper_mode = "problem"
            state.gem1_mode = "429"
            state.gem2_mode = "ok"
            thyao_1h = _load_frame_1h("THYAO")
            _run_synthetic_scan_alarm("THYAO", thyao_1h, notifier, now_dt, "run2")

            assert len(state.wrapper_calls) == 2  # yalnız +1 çağrı (ASLA aynı soruda retry yok!)
            assert len(state.gemini_calls) == 2   # Gemini #1 (429) + Gemini #2 (200)
            assert state.gemini_url_key_leaks == []
            assert len(state.telegram_messages) == 2
            for m in state.telegram_messages:
                txt = m["body"]["text"]
                assert txt.startswith("🤖 THYAO · 4s")
                assert "INTERNAL_THOUGHT" not in txt
                assert "AI_SONUC" not in txt
            assert len(state.supabase_rows) == 2
            print("[OK] Aşama 4: ApiWrapper problem (0 retry) -> Gemini #1 429 -> Gemini #2 (thought temiz) -> DM+Public AI")

            # --- Aşama 5: Sonraki soruda önce ApiWrapper denenir; 3 sağlayıcı da düşer -> DÜZ KART ---
            state.telegram_messages.clear()
            state.wrapper_mode = "eof_drop"
            state.gem1_mode = "429"
            state.gem2_mode = "503"
            asels_1h = _load_frame_1h("ASELS")
            _run_synthetic_scan_alarm("ASELS", asels_1h, notifier, now_dt, "run3")

            assert len(state.wrapper_calls) == 3  # yeni soruda yine İLK ApiWrapper denendi!
            assert len(state.gemini_calls) == 4   # ardından Gemini #1 + #2
            assert len(state.telegram_messages) == 2
            for m in state.telegram_messages:
                txt = m["body"]["text"]
                assert "ASELS" in txt
                assert not txt.startswith("🤖 "), "3 sağlayıcı düştüğünde düz kart gitmeliydi!"
            print("[OK] Aşama 5: Yeni soruda tekrar ApiWrapper -> 3 hata -> DM+Public kesintisiz DÜZ KART yedeği")

            # --- Aşama 6: Stabil 4s AI değişimi + Yeni Domain bozuk AI yanıtında düz kart yedeği ---
            state.telegram_messages.clear()
            state.wrapper_mode = "ok_sse"
            beh = SimpleNamespace(
                reclaim_kind="intrabar_sweep_reclaim", rank_score=9.5, support_level=390.0,
                close_price=421.5, dist_atr=0.8, touch_count=3, unchanged_days=12,
                reclaim_bars_ago=0, momentum_kind=None, vol_ratio=1.6,
            )
            st_cand = StabilAlarmCandidate(
                symbol="BIMAS", bar_open_ts="2026-09-25T14:00:00+03:00",
                bar_close_ts="2026-09-25T18:00:00+03:00", bar_label="25 Eyl 14:00–18:00",
                close_price=421.5, support_level=390.0, behavior=beh,
                card_lines=("Stabil destek üstünde",),
            )
            dispatch_stabil_scan_candidates(
                [st_cand], notifier,
                state_path=str(tmp_dir / "stabil_state.json"),
                frames_by_symbol={"BIMAS": (bimas_1h, None, now_dt)},
            )
            assert len(state.telegram_messages) == 2
            assert all(m["body"]["text"].startswith("🤖 BIMAS · 4s") for m in state.telegram_messages)

            state.telegram_messages.clear()
            state.wrapper_mode = "invalid_text"
            config.YENI_DOMAIN_ALARM = True
            dom_cand = DomainAlarmCandidate(
                symbol="BIMAS", timeframe="4h",
                bar_open="2026-09-25T14:00:00+03:00", bar_close="2026-09-25T18:00:00+03:00",
                bar_label="25 Eyl 14:00–18:00", bar_index=100, close_price=421.5,
                support_level=390.0, dist_atr=0.8, relation="destek üstünde",
                reasons=("BOS ↑",), volume_rvol=1.4, volume_tier=None,
                volume_source="OK", data_quality="OK",
                card_lines=("Stabil destek üstünde",), rank_score=7.5,
            )
            dispatch_domain_alarm_candidates(
                [dom_cand], notifier,
                state_path=str(tmp_dir / "domain_state.json"),
                frames_by_symbol={"BIMAS": (bimas_1h, None, now_dt)},
            )
            assert len(state.telegram_messages) == 2
            assert all("BIMAS" in m["body"]["text"] and not m["body"]["text"].startswith("🤖 ")
                       for m in state.telegram_messages)
            print("[OK] Aşama 6: Stabil 4s AI değişimi + Yeni Domain geçersiz AI yanıtında düz kart yedeği")

            # --- Aşama 7: DM `/ai BIMAS 4s` arka plan komutu + Public reddi ---
            state.telegram_messages.clear()
            state.wrapper_mode = "ok_sse"
            main_mod._notifier_ref = notifier

            class _CmdDeque:
                def to_dataframe(self, stock):
                    return bimas_1h.copy() if stock == "BIMAS" else None

                def to_gunluk_dataframe(self, stock):
                    del stock
                    return None

            main_mod._deque_manager_ref = _CmdDeque()
            orig_ks = getattr(main_mod, "komut_sohbeti", None)
            orig_dt_cmd = main_mod.datetime

            class FrozenCmdDt(datetime):
                @classmethod
                def now(cls, tz=None):
                    return now_dt if tz is None else now_dt.astimezone(tz)

            main_mod.datetime = FrozenCmdDt  # type: ignore[assignment]
            try:
                main_mod.komut_sohbeti = lambda: "-1007770002"
                assert "özel sahip DM" in main_mod._komut_ai("BIMAS 4s")

                main_mod.komut_sohbeti = lambda: "7770001"
                resp = main_mod._komut_ai("BIMAS 4s")
                assert isinstance(resp, ArkaPlanYaniti)
                resp.baslat()
                for _ in range(60):
                    if state.telegram_messages:
                        break
                    time.sleep(0.1)
                assert len(state.telegram_messages) == 1
                ai_cmd_reply = state.telegram_messages[0]["body"]["text"]
                assert ai_cmd_reply.startswith("🤖 BIMAS · 4s · AI Analiz (ApiWrapper"), ai_cmd_reply
                assert "🧪 Özet: eğilim=yukari · güç=orta · MTF=karma · risk=orta · yayın=gonder" in ai_cmd_reply, ai_cmd_reply
                assert "\n   " not in ai_cmd_reply, "DM /ai mesajı yapay 3-boşlukla kırılmış!"
                assert "[AI_SONUC" not in ai_cmd_reply
            finally:
                main_mod._deque_manager_ref = None
                main_mod.datetime = orig_dt_cmd
                if orig_ks is None:
                    if hasattr(main_mod, "komut_sohbeti"):
                        delattr(main_mod, "komut_sohbeti")
                else:
                    main_mod.komut_sohbeti = orig_ks
            print("[OK] Aşama 7: DM `/ai BIMAS 4s` arka plan yürütmesi + Public grup reddi")

            # --- Son güvenlik taraması: hiçbir gizli anahtar Telegram'a veya yerel gölgeye sızmadı ---
            local_shadow = (tmp_dir / "ai_yorum_test.json").read_text(encoding="utf-8")
            all_tg_bodies = json.dumps([m["body"] for m in state.telegram_messages])
            for secret in (WRAPPER_SECRET, GEM1_SECRET, GEM2_SECRET, SUPA_SECRET, TG_TOKEN):
                assert secret not in local_shadow
                assert secret not in all_tg_bodies
            assert state.wrapper_illegal_paths == []
            assert state.gemini_url_key_leaks == []
            assert state.supabase_bot_store_writes == []

            print("\n=== UÇTAN UCA DEPLOY + ALARM + API DENETİMİ: 7/7 AŞAMA BAŞARIYLA GEÇTİ ===")
            return 0
    finally:
        requests.post = real_requests_post
        for srv in (srv_wrap, srv_gem, srv_supa, srv_tg):
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
