#!/usr/bin/env python3
"""Telegram'a açmadan önce gizli `[AI_SONUC ...]` gölge değerlendirme CLI aracı.

Sağlayıcıdan bağımsızdır: hiçbir AI API çağrısı yapmaz ve Telegram'a mesaj
göndermez. Üç alt komut sunar:
  1) prompt : Sembol + kesit için gizli `[AI_SONUC ...]` kurallı prompt üretir.
  2) parse  : Ham AI yanıtından `[AI_SONUC ...]` bloğunu ayıklar, kullanıcıya
              gösterilecek temiz yorumu + 5 filtre JSON'unu gösterir ve
              isteğe bağlı olarak yerel JSON'a / Supabase `ai_yorum_test`
              tablosuna (`--supabase-kaydet` açıkça verilirse) kaydeder.
  3) olcum  : Yerel gölge defterindeki olgunlaşmış kayıtları yerel `bot_data`
              barlarıyla ölçer (gelecek sızıntısız).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_prompt import (  # noqa: E402
    DEFAULT_LOCAL_SHADOW_FILE,
    append_hidden_verdict_instruction,
    build_api_prompt,
    build_from_local_cache,
    build_shadow_record,
    evaluate_shadow_outcome,
    load_local_shadow_records,
    render_compact_prompt,
    save_local_shadow_records,
    save_shadow_record,
    write_shadow_records_to_supabase,
)
from data import resample_all_timeframes  # noqa: E402


def _read_local_frame(symbol: str, tf: str, data_dir: str) -> pd.DataFrame | None:
    sym = symbol.strip().upper()
    directory = Path(data_dir)
    path = directory / (f"{sym}_gunluk.json" if tf == "1d" else f"{sym}.json")
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        return None
    df = pd.DataFrame(raw)
    if "timestamp" not in df:
        return None
    stamps = [pd.Timestamp(x) for x in df.pop("timestamp")]
    df = df.rename(columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    df.index = pd.DatetimeIndex(
        [x.tz_localize("Europe/Istanbul") if x.tzinfo is None else x.tz_convert("Europe/Istanbul") for x in stamps],
        name="timestamp",
    )
    if tf == "1d":
        return df.sort_index()
    resampled = resample_all_timeframes(df.sort_index())
    return resampled.get(tf)


def _load_kap_context(args: argparse.Namespace, symbol: str, as_of: str) -> dict | None:
    arsiv = getattr(args, "kap_arsiv", None)
    if not arsiv:
        return None
    from kap.runtime import alarm_kap_baglami_oku

    return alarm_kap_baglami_oku(
        symbol,
        pd.Timestamp(as_of).to_pydatetime(),
        arsiv_yolu=arsiv,
        origin=getattr(args, "kap_origin", "kap_arsiv"),
        force=True,
    )


def _cmd_prompt(args: argparse.Namespace) -> int:
    packet = build_from_local_cache(
        args.symbol,
        as_of=args.as_of,
        main_tf=args.main_tf,
        data_dir=args.data_dir,
        research_mode=args.research_mode,
    )
    if args.format == "compact":
        text = render_compact_prompt(packet, history_bars=args.history_bars)
        if args.with_verdict:
            text = append_hidden_verdict_instruction(text)
        print(text)
        return 0

    kap_ctx = _load_kap_context(args, packet["symbol"], packet["as_of"])
    bundle = build_api_prompt(
        packet,
        modality=args.modality,
        history_bars=args.history_bars,
        include_hidden_verdict=args.with_verdict,
        kap_context=kap_ctx,
    )
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        print("=== SYSTEM ===")
        print(bundle["system"])
        print("\n=== USER ===")
        print(bundle["user"])
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    raw_text = (
        Path(args.response_file).read_text(encoding="utf-8")
        if args.response_file and args.response_file != "-"
        else sys.stdin.read()
    )
    packet = build_from_local_cache(
        args.symbol,
        as_of=args.as_of,
        main_tf=args.main_tf,
        data_dir=args.data_dir,
        research_mode=args.research_mode,
    )
    kap_ctx = _load_kap_context(args, packet["symbol"], packet["as_of"])
    bundle = build_api_prompt(
        packet,
        modality=args.modality,
        include_hidden_verdict=True,
        kap_context=kap_ctx,
    )
    record, parsed = build_shadow_record(
        packet,
        raw_text,
        model_adi=args.model,
        prompt_surumu=bundle["prompt_version"],
        system_sha256=bundle["system_sha256"],
        kaynak_turu=args.kaynak_turu,
        tetikleyici_tur=args.tetikleyici_tur or None,
        kap_context=kap_ctx,
        telegrama_gitti=False,
    )

    store = None
    if args.supabase_kaydet:
        from supabase_store import SupabaseStore

        store = SupabaseStore.from_env(read_only=False)
        if store is None:
            print("UYARI: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY eksik; Supabase yazımı atlandı.", file=sys.stderr)

    save_info = save_shadow_record(
        record,
        store=store,
        local_path=args.local_file,
        allow_supabase_write=bool(args.supabase_kaydet),
    )

    output = {
        "anahtar": record["anahtar"],
        "sembol": record["sembol"],
        "tf": record["tf"],
        "referans_fiyat": record["referans_fiyat"],
        "verdict": parsed["verdict"],
        "verdict_valid": parsed["verdict_valid"],
        "verdict_errors": parsed["verdict_errors"],
        "ok_for_telegram": parsed["ok_for_telegram"],
        "ok_for_shadow_log": parsed["ok_for_shadow_log"],
        "warnings": parsed["validation"]["warnings"],
        "word_count": parsed["validation"]["word_count"],
        "save_info": save_info,
        "visible_text": parsed["visible_text"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _cmd_olcum(args: argparse.Namespace) -> int:
    records = load_local_shadow_records(args.local_file)
    updated: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    cache: dict[tuple[str, str], pd.DataFrame | None] = {}

    for rec in records:
        if rec.get("sonuc") is not None and not args.yeniden:
            continue
        sym = str(rec.get("sembol") or "").upper()
        tf = str(rec.get("tf") or "4h").lower()
        key = (sym, tf)
        if key not in cache:
            cache[key] = _read_local_frame(sym, tf, args.data_dir)
        outcome = evaluate_shadow_outcome(rec, cache[key], horizon_bars=args.horizon_bars)
        if outcome is None:
            continue
        rec["sonuc"] = outcome
        rec["olcum_zamani"] = now_iso
        rec["updated_at"] = now_iso
        updated.append(rec)

    if updated:
        save_local_shadow_records(updated, args.local_file)
        if args.supabase_kaydet:
            from supabase_store import SupabaseStore

            store = SupabaseStore.from_env(read_only=False)
            write_shadow_records_to_supabase(updated, store, allow_supabase_write=True)

    print(json.dumps({"toplam": len(records), "olculen": len(updated)}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI gölge (shadow) yorum & gizli [AI_SONUC] aracı")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prompt = sub.add_parser("prompt", help="Gizli [AI_SONUC] kurallı prompt üret")
    p_prompt.add_argument("symbol")
    p_prompt.add_argument("--as-of", required=True)
    p_prompt.add_argument("--main-tf", default="4h")
    p_prompt.add_argument("--data-dir", default="bot_data")
    p_prompt.add_argument("--format", choices=["api", "compact"], default="api")
    p_prompt.add_argument("--modality", choices=["text_only", "multimodal"], default="text_only")
    p_prompt.add_argument("--research-mode", choices=["strict", "retrospective"], default="strict")
    p_prompt.add_argument("--history-bars", type=int, default=60)
    p_prompt.add_argument("--with-verdict", action=argparse.BooleanOptionalAction, default=True)
    p_prompt.add_argument("--kap-arsiv", default=None, help="İsteğe bağlı salt-okunur KAP SQLite arşivi")
    p_prompt.add_argument("--kap-origin", choices=["kap_arsiv", "sentetik"], default="kap_arsiv")
    p_prompt.add_argument("--json", action="store_true")
    p_prompt.set_defaults(func=_cmd_prompt)

    p_parse = sub.add_parser("parse", help="Ham AI yanıtından gizli bloğu ayıkla ve kaydet")
    p_parse.add_argument("symbol")
    p_parse.add_argument("--as-of", required=True)
    p_parse.add_argument("--response-file", default="-", help="Ham AI yanıtı dosya yolu veya '-' (stdin)")
    p_parse.add_argument("--main-tf", default="4h")
    p_parse.add_argument("--data-dir", default="bot_data")
    p_parse.add_argument("--modality", choices=["text_only", "multimodal"], default="text_only")
    p_parse.add_argument("--research-mode", choices=["strict", "retrospective"], default="strict")
    p_parse.add_argument("--model", default="")
    p_parse.add_argument("--kaynak-turu", default="manuel")
    p_parse.add_argument("--tetikleyici-tur", default="")
    p_parse.add_argument("--kap-arsiv", default=None, help="İsteğe bağlı salt-okunur KAP SQLite arşivi")
    p_parse.add_argument("--kap-origin", choices=["kap_arsiv", "sentetik"], default="kap_arsiv")
    p_parse.add_argument("--local-file", default=str(Path("bot_data") / DEFAULT_LOCAL_SHADOW_FILE))
    p_parse.add_argument("--supabase-kaydet", action="store_true",
                         help="Açıkça verilmedikçe Supabase'e hiçbir veri yazılmaz.")
    p_parse.set_defaults(func=_cmd_parse)

    p_olcum = sub.add_parser("olcum", help="Yerel gölge kayıtlarının ileri fiyat sonucunu ölç")
    p_olcum.add_argument("--data-dir", default="bot_data")
    p_olcum.add_argument("--local-file", default=str(Path("bot_data") / DEFAULT_LOCAL_SHADOW_FILE))
    p_olcum.add_argument("--horizon-bars", type=int, default=None)
    p_olcum.add_argument("--yeniden", action="store_true")
    p_olcum.add_argument("--supabase-kaydet", action="store_true")
    p_olcum.set_defaults(func=_cmd_olcum)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
