#!/usr/bin/env python3
"""ApiWrapper + 2× Ücretsiz Gemini yedek zinciri bağımsız test aracı.

Varsayılan mod (`--mock`) tamamen ağsızdır ve gerçek bir BIST promptu üzerinde
tüm SSE / yedek geçiş senaryolarını doğrular. Gerçek API denemesi için açıkça
`--live` verilmelidir (ortam değişkenlerinden `AI_WRAPPER_*` ve `GEMINI_API_KEY_*`
okur; Telegram'a veya canlı bota asla dokunmaz).

Örnek kullanım:
    .venv/bin/python scripts/diagnostics/ai_client_test.py --mock
    .venv/bin/python scripts/diagnostics/ai_client_test.py --live --symbol BIMAS --as-of "2026-09-25 18:05+03:00"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_prompt import (  # noqa: E402
    AIClientRouter,
    ApiWrapperClient,
    GeminiFreeClient,
    build_api_prompt,
    build_from_local_cache,
)

SAMPLE_VALID_REPLY = (
    "🧭 Mevcut durum\n"
    "BIMAS 4H grafikte Simetrik Üçgen yukarı kırılım sonrası retest bekliyor; "
    "dış yapı aşağı geçişte kaldığı için görüş koşullu kararsız, yukarı eğilime yakın. "
    "En önemli karşı kanıt 4H dış yapıda henüz yukarı BOS teyidi olmamasıdır. "
    "410,75 altı kalıcı kapanış bu görünümü zayıflatır.\n\n"
    "🔎 Bağlam\n"
    "4H hacim motoru hazır değil, yerel hacim teyit sayılmaz. Günlük Stabil destek 390,00 "
    "seviyesinde ve fiyat bu desteğin üzerinde seyrediyor; kısa seans mumu teyit sayılmaz.\n\n"
    "🕯️ Replay notu\n"
    "4H +OB 410,75–423,50 iki temas grubu sonrası son kapanışta orijinal bandın üzerinde; "
    "sonraki kapanmış mum henüz oluşmamış. 432,00–437,50 −OB temas almamış.\n\n"
    "[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"
)


def _load_bundle(
    symbol: str,
    as_of: str,
    main_tf: str,
    research_mode: str,
    kap_arsiv: str | None,
    kap_origin: str,
) -> dict[str, Any]:
    packet = build_from_local_cache(
        symbol,
        as_of=as_of,
        main_tf=main_tf,
        research_mode=research_mode,
        data_dir=str(REPO_ROOT / "bot_data"),
    )
    kap_ctx = None
    if kap_arsiv:
        from kap import alarm_kap_baglami_oku

        cut_dt = pd.Timestamp(as_of).to_pydatetime()
        kap_ctx = alarm_kap_baglami_oku(
            symbol,
            cut_dt,
            arsiv_yolu=kap_arsiv,
            origin=kap_origin,  # type: ignore[arg-type]
            force=True,
        )
    return build_api_prompt(
        packet,
        modality="text_only",
        include_hidden_verdict=True,
        kap_context=kap_ctx,
    )


def _run_mock_suite(bundle: dict[str, Any]) -> int:
    print(
        f"=== AI İSTEMCİ ÇEVRİMDIŞI TESTİ "
        f"(sembol={bundle['metadata']['symbol']}, system={bundle['budget']['system']['utf16']} u16, "
        f"user={bundle['user_size']} u16) ==="
    )

    ascii_done_line = "data: " + json.dumps(
        {"status": "done", "text": SAMPLE_VALID_REPLY, "elapsed": 34.2, "id": "req-1", "extra": "ok"},
        ensure_ascii=True,
    )

    # 1) ApiWrapper: yorum satırı + 2 wait + ASCII kaçışlı Türkçe done -> doğrudan başarılı
    def _wrap_ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/ask"
        assert request.headers["authorization"] == "Bearer test-wrapper-key"
        body = json.loads(request.content.decode("utf-8"))
        assert "prompt" in body and "system" in body and "model" not in body
        sse = (
            ": keepalive comment\n"
            "\n"
            'data: {"status": "wait", "elapsed": 30}\n'
            "\n"
            'data: {"status": "wait", "elapsed": 45}\n'
            "\n"
            f"{ascii_done_line}\n"
        )
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})

    # 2) ApiWrapper: problem -> tekrar denemeden Gemini #1'e geçiş
    wrapper_calls = {"n": 0}

    def _wrap_problem(request: httpx.Request) -> httpx.Response:
        del request
        wrapper_calls["n"] += 1
        return httpx.Response(200, text='data: {"status": "problem"}\n')

    def _gemini_ok(request: httpx.Request) -> httpx.Response:
        assert "x-goog-api-key" in request.headers
        assert "key=" not in str(request.url)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": SAMPLE_VALID_REPLY}]}}]},
        )

    def _gemini_429(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(429, json={"error": {"message": "quota exceeded"}})

    def _wrap_503(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, text="unavailable")

    # Senaryo A
    r_a = AIClientRouter([
        ApiWrapperClient("https://wrapper.example", "test-wrapper-key", transport=httpx.MockTransport(_wrap_ok)),
        GeminiFreeClient("gem-1", name="gemini_free_1", transport=httpx.MockTransport(_gemini_ok)),
        GeminiFreeClient("gem-2", name="gemini_free_2", transport=httpx.MockTransport(_gemini_ok)),
    ]).ask_bundle(bundle, require_verdict=True)
    assert r_a["result"].ok and r_a["result"].provider == "api_wrapper"
    assert r_a["result"].attempts[0].wait_events == 2
    assert r_a["parsed"]["ok_for_telegram"] and r_a["parsed"]["verdict"]["egilim"] == "yukari"
    print("  [OK] Senaryo A: ApiWrapper (2× wait + Türkçe \\u kaçışı + done) -> api_wrapper")

    # Senaryo B
    r_b = AIClientRouter([
        ApiWrapperClient("https://wrapper.example", "test-wrapper-key", transport=httpx.MockTransport(_wrap_problem)),
        GeminiFreeClient("gem-1", name="gemini_free_1", transport=httpx.MockTransport(_gemini_ok)),
        GeminiFreeClient("gem-2", name="gemini_free_2", transport=httpx.MockTransport(_gemini_ok)),
    ]).ask_bundle(bundle, require_verdict=True)
    assert wrapper_calls["n"] == 1  # ApiWrapper'a tekrar gönderilmedi!
    assert r_b["result"].ok and r_b["result"].provider == "gemini_free_1"
    print("  [OK] Senaryo B: ApiWrapper problem (tekrarsız) -> gemini_free_1")

    # Senaryo C
    r_c = AIClientRouter([
        ApiWrapperClient("https://wrapper.example", "test-wrapper-key", transport=httpx.MockTransport(_wrap_503)),
        GeminiFreeClient("gem-1", name="gemini_free_1", transport=httpx.MockTransport(_gemini_429)),
        GeminiFreeClient("gem-2", name="gemini_free_2", transport=httpx.MockTransport(_gemini_ok)),
    ]).ask_bundle(bundle, require_verdict=True)
    assert r_c["result"].ok and r_c["result"].provider == "gemini_free_2"
    print("  [OK] Senaryo C: ApiWrapper 503 + Gemini #1 429 -> gemini_free_2")

    # Senaryo D
    r_d = AIClientRouter([
        ApiWrapperClient("https://wrapper.example", "test-wrapper-key", transport=httpx.MockTransport(_wrap_problem)),
        GeminiFreeClient("gem-1", name="gemini_free_1", transport=httpx.MockTransport(_gemini_429)),
        GeminiFreeClient("gem-2", name="gemini_free_2", transport=httpx.MockTransport(_gemini_429)),
    ]).ask_bundle(bundle, require_verdict=False)
    assert not r_d["result"].ok and r_d["fallback_to_normal_alarm"] is True
    assert len(r_d["result"].attempts) == 3
    print("  [OK] Senaryo D: 3 sağlayıcı da düştü -> normal alarm yedeğine güvenli dönüş")

    print("SONUÇ: TÜM ÇEVRİMDIŞI İSTEMCİ SENARYOLARI GEÇTİ.")
    return 0


def _run_live(bundle: dict[str, Any], *, max_wall_seconds: float | None) -> int:
    router = AIClientRouter.from_env()
    names = router.provider_names()
    if not names:
        print(
            "HATA: Ortamda yapılandırılmış AI sağlayıcısı yok "
            "(AI_WRAPPER_BASE_URL+AI_WRAPPER_API_KEY veya GEMINI_API_KEY_1/2 tanımlayın).",
            file=sys.stderr,
        )
        return 2

    print(
        f"Canlı deneme başlıyor -> sağlayıcı zinciri: {', '.join(names)} "
        f"(sembol={bundle['metadata']['symbol']}, system={bundle['budget']['system']['utf16']} u16, "
        f"user={bundle['user_size']} u16)"
    )
    out = router.ask_bundle(
        bundle,
        parse_response=True,
        require_verdict=False,
        max_wall_seconds_per_provider=max_wall_seconds,
    )
    res = out["result"]
    print("\nDenemeler:")
    for att in res.attempts:
        print(
            f"  - {att.provider:14s} ok={att.ok} outcome={att.outcome} "
            f"http={att.http_status} wait={att.wait_events} elapsed={att.elapsed_s}s "
            f"model={att.model or '-'} detail={att.detail or '-'}"
        )

    if not res.ok:
        print("\nSONUÇ: Tüm AI sağlayıcıları başarısız -> normal alarm yedeği devreye girer.")
        return 1

    parsed = out["parsed"] or {}
    print(f"\nKazanan sağlayıcı: {res.provider} (model={res.model or 'varsayılan'}, toplam={res.total_elapsed_s}s)")
    print(f"Doğrulama: tg_ok={parsed.get('ok_for_telegram')} shadow_ok={parsed.get('ok_for_shadow_log')} "
          f"verdict={parsed.get('verdict')} warnings={(parsed.get('validation') or {}).get('warnings')}")
    print("\n--- GÖRÜNÜR YORUM (gizli blok ayıklanmış) ---")
    print(parsed.get("visible_text") or res.text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ApiWrapper + 2× Gemini AI istemci test aracı")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="Ağsız sahte SSE + yedek zincir testi (varsayılan)")
    mode.add_argument("--live", action="store_true", help="Ortam değişkenleriyle gerçek API testi")
    parser.add_argument("--symbol", default="BIMAS", help="Test hissesi (varsayılan: BIMAS)")
    parser.add_argument("--as-of", default="2026-09-25 18:05+03:00", help="Kesit zamanı (TSİ)")
    parser.add_argument("--main-tf", default="4h", help="Ana TF (varsayılan: 4h)")
    parser.add_argument("--research-mode", default="strict", choices=("strict", "retrospective"))
    parser.add_argument("--kap-arsiv", default=None, help="İsteğe bağlı KAP SQLite arşiv yolu")
    parser.add_argument("--kap-origin", default="kap_arsiv", help="KAP arşiv origin etiketi")
    parser.add_argument(
        "--max-wall-seconds",
        type=float,
        default=None,
        help="İsteğe bağlı sağlayıcı başına üst süre sınırı (varsayılan: sınırsız)",
    )
    args = parser.parse_args(argv)

    bundle = _load_bundle(
        args.symbol,
        args.as_of,
        args.main_tf,
        args.research_mode,
        args.kap_arsiv,
        args.kap_origin,
    )
    if args.live:
        return _run_live(bundle, max_wall_seconds=args.max_wall_seconds)
    return _run_mock_suite(bundle)


if __name__ == "__main__":
    raise SystemExit(main())
