#!/usr/bin/env python3
"""Build ten comparable, no-lookahead 4h context packets and a replay audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from alarm_context_packet import build_context_packet, packet_json, to_jsonable  # noqa: E402
from config import ISTANBUL_TZ  # noqa: E402
from data import mum_kapanis_anlari  # noqa: E402
from domain_engines.runner import run_domain_engines, run_stabil_domain  # noqa: E402
from research.arsiv import tf_frame  # noqa: E402

DEFAULT_SYMBOLS = (
    "ASTOR", "THYAO", "GARAN", "ASELS", "SISE",
    "TUPRS", "BIMAS", "EREGL", "FROTO", "SNGYO",
)
DEFAULT_AS_OF = "2026-10-16T13:30:00+03:00"
REPLAY_RECORDED_AT = "2026-10-30"
REPLAY_DATA_THROUGH = "2026-10-19"
REPLAY_CANDIDATE_FILE = ROOT / "docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz"
REPLAY_REPORT = "docs/arastirma/KIRILIM_TEYIT_REPLAY_SONUCLARI_2026-10-30.md"
REPLAY_DETAIL = "docs/arastirma/KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md"


def _counts(series: pd.Series) -> dict[str, int]:
    counts = series.fillna("<missing>").astype(str).value_counts(dropna=False)
    return {str(key): int(value) for key, value in sorted(counts.items())}


def _median(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float(numeric.median())


def _fmt_number(value: object, places: int = 3) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return str(value)


def _counts_text(values: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(values.items())) or "kayıt yok"


def _is_true(value: object) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _examples(valid_nonoverlap: pd.DataFrame, limit: int = 3) -> list[dict]:
    columns = (
        "anchor", "period", "direction", "candidate_state", "pattern", "status",
        "outcome_status", "end_atr", "max_favorable_atr", "max_adverse_atr",
        "confirm_bars", "outcome_end_time",
    )
    records = []
    for row in valid_nonoverlap.sort_values("anchor").tail(limit).to_dict("records"):
        records.append({key: to_jsonable(row.get(key)) for key in columns})
    return records


def _all_replay_rows(rows: pd.DataFrame) -> list[dict]:
    """Preserve every selected symbol/4h replay row without dropping columns."""
    return [
        {str(key): to_jsonable(value) for key, value in row.items()}
        for row in rows.sort_values(["anchor", "local_index"]).to_dict("records")
    ]


def _symbol_replay_finding(
    symbol: str,
    replay_rows: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    source_sha256: str,
    cutoff_bar_close: pd.Timestamp | None,
) -> dict:
    rows = replay_rows.loc[
        replay_rows["symbol"].astype(str).str.upper().eq(symbol)
        & replay_rows["tf"].astype(str).str.lower().eq("4h")
    ].copy()
    nonoverlap_mask = rows["nonoverlap"].map(_is_true)
    valid_mask = rows["outcome_status"].eq("VALID")
    valid_nonoverlap = rows.loc[valid_mask & nonoverlap_mask]
    cutoff_utc = as_of.tz_convert("UTC")
    anchors = pd.to_datetime(rows["anchor"], utc=True, errors="coerce")
    at_cutoff_anchor = int(anchors.eq(cutoff_utc).sum())

    outcome_counts = _counts(rows["outcome_status"])
    status_counts = _counts(rows["status"])
    period_counts = _counts(rows["period"])
    end_median = _median(valid_nonoverlap["end_atr"])
    median_text = "hesaplanamadı" if end_median is None else f"{end_median:+.3f} ATR"
    if cutoff_bar_close is None:
        cutoff_bar_note = "arşivde 13:30 etiketli bar bulunamadı"
    elif cutoff_bar_close > as_of:
        cutoff_bar_note = (
            f"{as_of.isoformat()} açılış etiketli mum {cutoff_bar_close.isoformat()}'de kapanır; "
            "kesitte henüz tamamlanmamıştır"
        )
    else:
        cutoff_bar_note = f"bar kapanışı {cutoff_bar_close.isoformat()}"

    return {
        "finding_id": f"{symbol.lower()}-4h-breakout-replay-2026-10-30",
        "symbol": symbol,
        "recorded_at": REPLAY_RECORDED_AT,
        "data_through": REPLAY_DATA_THROUGH,
        "timeline_note": (
            "Bu sembol-özel özet 174 sembol/696 seri araştırma replay'inden türetilmiştir; "
            "2026-10-30 tarihli rapor ve 2026-10-19'a uzanan sonuçlar 2026-10-16 kesitinden sonradır."
        ),
        "domains": ["formation_alert"],
        "title": f"{symbol} 4h sembol-özel kırılım replay özeti",
        "summary": (
            f"4h replay'de {len(rows)} aday satırı; VALID ve nonoverlap alt kümesinde "
            f"n={len(valid_nonoverlap)}, 10. kapanışın yönlü ATR ortancası {median_text}. "
            f"13:30 etiketli aday satırı n={at_cutoff_anchor}; {cutoff_bar_note}."
        ),
        "scope": {
            "run_id": "breakout-confirm-replay-2026-10-30",
            "symbol": symbol,
            "symbols": 174,
            "series": 696,
            "timeframe": "4h",
            "period": "2025-05-07 .. 2026-10-19",
            "unit": "aday/deneme olayı; her satır işlem veya alarm teslimatı değildir",
            "n": int(len(rows)),
            "valid_nonoverlap_n": int(len(valid_nonoverlap)),
            "candidate_data_through": REPLAY_DATA_THROUGH,
        },
        "sample": (
            f"{symbol} 4h aday satırı n={len(rows)}; dönemlere göre {period_counts}; "
            f"outcome_status'a göre {outcome_counts}; VALID ve nonoverlap=true n={len(valid_nonoverlap)}."
        ),
        "metrics": {
            "candidate_rows": int(len(rows)),
            "period_counts": period_counts,
            "outcome_status_counts": outcome_counts,
            "replay_state_counts": status_counts,
            "valid_nonoverlap_n": int(len(valid_nonoverlap)),
            "median_signed_end_atr": end_median,
            "median_max_favorable_atr": _median(valid_nonoverlap["max_favorable_atr"]),
            "median_max_adverse_atr": _median(valid_nonoverlap["max_adverse_atr"]),
            "median_confirm_bars": _median(valid_nonoverlap["confirm_bars"]),
            "recent_valid_nonoverlap_examples": _examples(valid_nonoverlap),
            "cutoff_anchor_audit": {
                "anchor_label": as_of.isoformat(),
                "matching_replay_rows": at_cutoff_anchor,
                "candidate_bar_close": None if cutoff_bar_close is None else cutoff_bar_close.isoformat(),
                "bar_complete_at_snapshot": (
                    None if cutoff_bar_close is None else bool(cutoff_bar_close <= as_of)
                ),
                "interpretation": cutoff_bar_note,
            },
        },
        "replay_events": _all_replay_rows(rows),
        "method": (
            "Adaylar dosyasından yalnız sembolün 4h satırları özetlendi. Medyanlar "
            "yalnız outcome_status=VALID ve nonoverlap=true satırlarında hesaplandı. "
            "end_atr, aday kapanışı ve aday anındaki sabit ATR'ye göre sonraki onuncu "
            "kapanışın kırılım yönündeki ATR-normalize değişimidir."
        ),
        "limitations": [
            "Replay raporu 2026-10-30'da kaydedilmiş ve verisi 2026-10-19'a kadar uzanmıştır; 2026-10-16 snapshot'ında bilinmiyordu.",
            "Bu çıktı 4h kırılım/formasyon replay'idir; canlı alarm, gerçek bildirim veya sembole ait başarı olasılığı değildir.",
            "Medyan end_atr gerçekleşmiş işlem getirisi değildir; maliyet, emir, mum içi sıra ve gerçekleşme ölçülmez.",
            "Sembol başına örneklem küçüktür ve seçili 10 sembol piyasa temsili/bağımsız örneklem değildir.",
            "Replay aday satırındaki 13:30 etiketi bar açılışını gösterir; kapanışı snapshot sonrasındaysa o satır o anki context'e katılmaz.",
        ],
        "sources": [
            REPLAY_REPORT,
            REPLAY_DETAIL,
            "docs/arastirma/sonuclar/kirilim_replay/adaylar.csv.gz",
        ],
        "source_sha256": source_sha256,
    }


def _compact_packet_for_review(packet: dict) -> dict:
    """Keep only the small fields needed for the Markdown review in memory."""
    return {
        "as_of": packet["as_of"],
        "snapshot": packet["snapshot"],
        "domain_outputs": {
            name: {
                "status": item["status"],
                "data_quality": item.get("data_quality"),
                "summary": item.get("summary", {}),
            }
            for name, item in packet["domain_outputs"].items()
        },
        "replay_evidence": {"symbol_specific": packet["replay_evidence"]["symbol_specific"]},
    }


def _trend_summary(packet: dict) -> str:
    status = packet["domain_outputs"]["stabil"]["status"]
    if status != "available":
        return f"{status}"
    states = packet["domain_outputs"]["stabil"]["summary"].get("trend_states", {})
    return ", ".join(f"{key}={row.get('state', '—')}" for key, row in states.items()) or "trend alanı yok"


def _interpretation(packet: dict) -> list[str]:
    outputs = packet["domain_outputs"]
    missing = [name for name, item in outputs.items() if item["status"] != "available"]
    parts = []
    if missing:
        parts.append("Eksik/çalışmayan domain: " + ", ".join(
            f"{name}={outputs[name]['status']}" for name in missing
        ) + ".")
    else:
        parts.append("Beş domainin tamamı çıktı verdi.")

    ms = outputs["market_structure"].get("summary", {})
    scopes = ms.get("scopes", {})
    external = scopes.get("external", {})
    internal = scopes.get("internal", {})
    if external or internal:
        parts.append(
            "MS dış/iç: "
            f"{external.get('state', '—')}/{external.get('direction', '—')} · "
            f"{internal.get('state', '—')}/{internal.get('direction', '—')}."
        )

    vp_entry = outputs["volume_participation"]
    if vp_entry["status"] == "available":
        vp = vp_entry.get("summary", {})
        parts.append(
            "Hacim: "
            f"durum={vp.get('state', '—')}, RVOL={_fmt_number(vp.get('rvol'))}, "
            f"katılım={vp.get('participation_stage', '—')}, kırılım={vp.get('break_stage', '—')}."
        )

    ob_entry = outputs["order_block"]
    if ob_entry["status"] == "available":
        ob = ob_entry.get("summary", {})
        parts.append(
            f"OB: aktif {ob.get('active_records_count', '—')} / toplam {ob.get('records_count', '—')}; "
            "tam kayıtlar JSON native bölümünde."
        )
    fvg_entry = outputs["fvg"]
    if fvg_entry["status"] == "available":
        fvg = fvg_entry.get("summary", {})
        bull = len(fvg.get("active_bullish_fvg", []))
        bear = len(fvg.get("active_bearish_fvg", []))
        parts.append(
            f"FVG: oluşum geçmişi {fvg.get('formation_count', '—')}, aktif boğa/ayı={bull}/{bear}."
        )
    if outputs["stabil"]["status"] == "available":
        stabil = outputs["stabil"].get("summary", {})
        parts.append(
            f"Stabil: destek ilişkisi={stabil.get('latest_support_relation', '—')}; "
            f"trend: {_trend_summary(packet)}."
        )

    replay = packet["replay_evidence"].get("symbol_specific", [])
    if replay:
        finding = replay[0]
        metrics = finding["metrics"]
        parts.append(
            "Sembole özel 4h replay daha sonraki araştırmadır: "
            f"aday n={metrics['candidate_rows']}, VALID/nonoverlap n={metrics['valid_nonoverlap_n']}, "
            f"yönlü 10. kapanış medyanı={_fmt_number(metrics['median_signed_end_atr'])} ATR; "
            "tarihsel 13:30 bilgi kümesine dahil değil."
        )
    parts.append("Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.")
    return parts


def _report_section(index: int, symbol: str, packet: dict, raw_h4_rows: int) -> str:
    outputs = packet["domain_outputs"]
    snapshot = packet["snapshot"]
    finding = packet["replay_evidence"]["symbol_specific"][0]
    metrics = finding["metrics"]
    lines = [
        f"## {index}. {symbol} — {snapshot['reference_price']:.2f} · {snapshot['closed_bar_count']} tamamlanmış H4 mum",
        "",
        f"- Kesit `{packet['as_of']}`; bu kesitteki H4 kapanış sayısı `{snapshot['closed_bar_count']}`; arşivdeki H4 satır sayısı `{raw_h4_rows}`.",
        "- Domain durumları: " + ", ".join(f"`{name}={item['status']}`" for name, item in outputs.items()) + ".",
        "- " + " ".join(_interpretation(packet)),
        f"- Replay (sonradan): toplam aday `{metrics['candidate_rows']}`, outcome dağılımı `{_counts_text(metrics['outcome_status_counts'])}`, "
        f"VALID/nonoverlap n=`{metrics['valid_nonoverlap_n']}`, medyan yönlü 10. kapanış `{_fmt_number(metrics['median_signed_end_atr'])}` ATR.",
        f"- 13:30 açılış etiketli aday satırı: `{metrics['cutoff_anchor_audit']['matching_replay_rows']}`; "
        f"bar kapanışı `{metrics['cutoff_anchor_audit']['candidate_bar_close']}`; "
        f"snapshot'ta tamamlanmış mı: `{metrics['cutoff_anchor_audit']['bar_complete_at_snapshot']}`.",
        "- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.",
        "",
    ]
    return "\n".join(lines)


def build_symbol_packet(
    symbol: str,
    *,
    as_of: pd.Timestamp,
    replay_rows: pd.DataFrame,
    replay_sha256: str,
) -> tuple[dict, int]:
    daily = tf_frame(symbol, "1d")
    h4 = tf_frame(symbol, "4h")
    close_times = pd.DatetimeIndex(
        mum_kapanis_anlari(h4.index.tz_convert(ISTANBUL_TZ), "4h")
    )
    if len(close_times) != len(h4):
        raise RuntimeError(f"{symbol}: H4 close-time count does not match archive rows")
    closed_mask = close_times <= as_of
    closed_h4 = h4.loc[closed_mask].copy()
    if closed_h4.empty:
        raise RuntimeError(f"{symbol}: no completed H4 bar at {as_of.isoformat()}")
    last_close_time = close_times[closed_mask][-1]
    if last_close_time != as_of:
        raise RuntimeError(
            f"{symbol}: common-cut requirement failed; last close {last_close_time}, expected {as_of}"
        )

    candidate_position = h4.index.get_indexer([as_of.tz_convert("UTC")])[0]
    cutoff_bar_close = None if candidate_position < 0 else close_times[candidate_position]
    domain_results = run_domain_engines(symbol, "4h", closed_h4, isolated=True)
    domain_results["stabil"] = run_stabil_domain(
        symbol,
        "4h",
        h4,
        daily_frame=daily,
        h4_frame=h4,
        as_of_close=as_of,
        isolated=True,
    )
    supplemental = _symbol_replay_finding(
        symbol,
        replay_rows,
        as_of=as_of,
        source_sha256=replay_sha256,
        cutoff_bar_close=cutoff_bar_close,
    )
    packet = build_context_packet(
        symbol=symbol,
        timeframe="4h",
        as_of=as_of,
        domain_results=domain_results,
        trigger=None,
        context_kind="historical_sample",
        generated_at=pd.Timestamp.now(tz=ISTANBUL_TZ),
        reference_price=float(closed_h4.iloc[-1]["close"]),
        price_time=last_close_time,
        closed_bar_count=len(closed_h4),
        data_source=f"backfill_data/{symbol}_1h.csv.gz + {symbol}_1d.csv.gz (4h derived)",
        supplemental_replay_findings=[supplemental],
    )
    return packet, len(h4)


def _render_report(records: list[dict], as_of: pd.Timestamp, replay_sha256: str) -> str:
    lines = [
        "# 10 sembol alarm-context JSON denemesi ve yorum notları",
        "",
        f"**Kesit:** `{as_of.isoformat()}` · **TF:** `4h` · **sembol sayısı:** `{len(records)}` · **native runner:** izole (`isolated=True`).",
        "",
        "Bu, 10 farklı sembolde tam domain JSON paketini birer birer üretme denemesidir. Aynı kapalı H4 kesit tarihi kullanıldı; 13:30 etiketiyle başlayan yeni mumun kapanışı 17:30 olduğundan o mumun içeriği anlık domain çıktısına dahil edilmedi.",
        "",
        "## Replay eklentisi kontrolü",
        "",
        "- Her paketteki `replay_evidence` alanında domain bazlı kaynaklı aggregate bulgular var. Bunlar 176 sembol/704 seri ve başka ayrı araştırma evrenlerinden gelir; tek sembole ait olasılık değildir.",
        "- Bu denemede ayrıca `replay_evidence.symbol_specific` eklendi: sembolün 4h aday satırlarının tamamı (`replay_events`) ve `VALID + nonoverlap=true` ölçüleri 174 sembol/696 seri, 2026-10-30 raporundan alınmıştır."
        "- Sembol-özel replay verisi `2026-10-19`'a kadar sürer ve raporu `2026-10-30` tarihlidir. Bu nedenle 2026-10-16 kesitinde `available_at_snapshot=false`; canlı context'e/özet yoruma geriye dönük bilgi diye katılmadı.",
        "- Bu replay aday/deneme sonuçları gerçek alarm/Telegram teslimi, işlem getirisi veya kalıcı başarı olasılığı değildir. `end_atr`, başlangıçta sabit ATR ile yönlü onuncu kapanış farkıdır; işlem maliyeti ve emir gerçekleşmesi ölçülmez.",
        f"- Replay CSV SHA-256: `{replay_sha256}`.",
        "",
        "## Hızlı karşılaştırma",
        "",
        "| Sembol | Kapanış | Domain durumu | MS dış | VP | Aktif OB | Aktif FVG boğa/ayı | Stabil trend | 4h aday / valid-nonoverlap | Medyan end ATR* |",
        "|---|---:|---|---|---|---:|---:|---|---:|---:|",
    ]
    for record in records:
        packet = record["packet"]
        outputs = packet["domain_outputs"]
        ms = outputs["market_structure"].get("summary", {}).get("scopes", {}).get("external", {})
        vp = outputs["volume_participation"].get("summary", {})
        ob = outputs["order_block"].get("summary", {})
        fvg = outputs["fvg"].get("summary", {})
        replay = packet["replay_evidence"]["symbol_specific"][0]["metrics"]
        active_fvg = f"{len(fvg.get('active_bullish_fvg', []))}/{len(fvg.get('active_bearish_fvg', []))}"
        statuses = ", ".join(
            name for name, item in outputs.items() if item["status"] != "available"
        ) or "5/5 available"
        direction = f"{ms.get('state', '—')}/{ms.get('direction', '—')}"
        vp_label = f"{vp.get('state', '—')} · RVOL {_fmt_number(vp.get('rvol'))}"
        lines.append(
            f"| {record['symbol']} | {packet['snapshot']['reference_price']:.2f} | {statuses} | {direction} | {vp_label} | "
            f"{ob.get('active_records_count', '—')} | {active_fvg} | {_trend_summary(packet)} | "
            f"{replay['candidate_rows']}/{replay['valid_nonoverlap_n']} | {_fmt_number(replay['median_signed_end_atr'])} |"
        )
    lines.extend([
        "",
        "\\* Medyan yalnız sembolün kendi VALID ve örtüşmeyen 4h replay adaylarından; post-cutoff araştırma, getiri/probability değildir.",
        "",
        "## Sembol bazında: mevcut, eksik ve yorum",
        "",
    ])
    for index, record in enumerate(records, 1):
        lines.append(_report_section(index, record["symbol"], record["packet"], record["raw_h4_rows"]))
    lines.extend([
        "## Deneme özeti ve dikkat edilen hatalar",
        "",
        "- Standart domain JSON'ında beş alanın her biri ayrıca `available/not_returned/skipped/error` durumuyla yer aldı. Bir alanın `available` olması, içindeki state'in güçlü/olumlu olduğu anlamına gelmiyor.",
        "- Alan denetimi: Market Structure `data_quality` üst düzeyde 10/10 `null`; bu eksik domain değil, engine bu alanı bildirmiyor ve external/internal scope quality değerleri mevcut. Builder null'u koruyor, yapay kalite değeri üretmiyor. VP alanı mevcut state'i taşırken OB/FVG/Stabil `OK` bildiriyor.",
        "- 10 paketin her biri strict JSON olarak serileştirildi ve tekrar parse edildi; geleceğe ait native domain zamanları context'e sızarsa builder hata veriyor.",
        "- Sembol replay sonuçlarıyla anlık 13:30 domain kesiti karıştırılmadı. JSON'da her sembolün tüm 4h replay event satırları ayrı evidence altında tutuldu. Özellikle ASTOR'daki 13:30 açılış etiketli aday, 17:30'da kapanacağı için yalnız sonraki replay kaydı olarak yer aldı."
        "- Örneklem seçilmiş 10 hissedir; sektör/likidite bakımından BIST temsilî örneklemi değildir. Piyasa ve domain uyuşmazlıkları tek skora indirgenmedi.",
        "- Bu deneme canlı akışa, Telegram'a, depolamaya veya işlem kararına bağlı değildir.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument(
        "--output-zip",
        type=Path,
        default=ROOT / "docs/arastirma/samples/ALARM_CONTEXT_10_SEMBOL_2026-10-16.zip",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=ROOT / "docs/arastirma/samples/ALARM_CONTEXT_10_SEMBOL_INCELEME_2026-10-16.md",
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        help="Optional directory for individual uncompressed JSONs; default stores them only in the ZIP.",
    )
    args = parser.parse_args()
    symbols = [str(symbol).strip().upper() for symbol in args.symbols]
    if len(symbols) != 10 or len(set(symbols)) != 10:
        parser.error("This review requires exactly 10 unique symbols")
    as_of = pd.Timestamp(args.as_of)
    if as_of.tzinfo is None:
        parser.error("--as-of must include a timezone offset")
    if not REPLAY_CANDIDATE_FILE.exists():
        parser.error(f"Replay candidate file not found: {REPLAY_CANDIDATE_FILE}")

    replay_sha256 = hashlib.sha256(REPLAY_CANDIDATE_FILE.read_bytes()).hexdigest()
    replay_rows = pd.read_csv(REPLAY_CANDIDATE_FILE, compression="gzip", low_memory=False)
    required_replay_columns = {
        "symbol", "tf", "anchor", "period", "direction", "candidate_state", "pattern",
        "status", "outcome_status", "end_atr", "max_favorable_atr", "max_adverse_atr",
        "confirm_bars", "outcome_end_time", "nonoverlap",
    }
    missing_replay_columns = required_replay_columns - set(replay_rows.columns)
    if missing_replay_columns:
        parser.error(f"Replay candidate file is missing fields: {sorted(missing_replay_columns)}")
    replay_symbols = replay_rows["symbol"].astype(str).str.upper()
    replay_timeframes = replay_rows["tf"].astype(str).str.lower()
    for symbol in symbols:
        for timeframe in ("1h", "1d"):
            source = ROOT / "backfill_data" / f"{symbol}_{timeframe}.csv.gz"
            if not source.exists():
                parser.error(f"Archive source missing for {symbol}/{timeframe}: {source}")
        if not (replay_symbols.eq(symbol) & replay_timeframes.eq("4h")).any():
            parser.error(f"No symbol-specific 4h replay rows for {symbol}")

    records = []
    json_manifest = []
    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    if args.json_dir:
        args.json_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, symbol in enumerate(symbols, 1):
            print(f"[{index}/10] Building {symbol} 4h packet at {as_of.isoformat()}...", flush=True)
            packet, raw_h4_rows = build_symbol_packet(
                symbol,
                as_of=as_of,
                replay_rows=replay_rows,
                replay_sha256=replay_sha256,
            )
            payload = packet_json(packet)
            decoded = json.loads(payload)
            if (
                decoded["symbol"] != symbol
                or decoded["as_of"] != as_of.isoformat()
                or decoded["snapshot"]["price_time"] != as_of.isoformat()
                or decoded["snapshot"]["closed_bar_count"] is None
            ):
                raise RuntimeError(f"{symbol}: output identity/as-of/closed-bar validation failed")
            member = f"{symbol}_4h_{as_of.strftime('%Y-%m-%d_%H-%M-%S%z').replace('+', 'plus')}.json"
            payload_bytes = payload.encode("utf-8")
            archive.writestr(member, payload_bytes)
            if args.json_dir:
                (args.json_dir / member).write_bytes(payload_bytes)
            statuses = {
                name: item["status"] for name, item in packet["domain_outputs"].items()
            }
            finding = packet["replay_evidence"]["symbol_specific"][0]
            json_manifest.append({
                "symbol": symbol,
                "member": member,
                "size_bytes": len(payload_bytes),
                "sha256": hashlib.sha256(payload_bytes).hexdigest(),
                "closed_bar_count": packet["snapshot"]["closed_bar_count"],
                "reference_price": packet["snapshot"]["reference_price"],
                "domain_statuses": statuses,
                "replay_candidate_rows_4h": finding["metrics"]["candidate_rows"],
                "replay_valid_nonoverlap_n": finding["metrics"]["valid_nonoverlap_n"],
                "replay_median_signed_end_atr": finding["metrics"]["median_signed_end_atr"],
                "replay_available_at_snapshot": finding["timeline"]["available_at_snapshot"],
            })
            reference_price = packet["snapshot"]["reference_price"]
            records.append({
                "symbol": symbol,
                "packet": _compact_packet_for_review(packet),
                "raw_h4_rows": raw_h4_rows,
            })
            del decoded, payload, payload_bytes, packet
            print(
                f"    {statuses}; close={reference_price:.2f}; "
                f"4h replay n={finding['metrics']['candidate_rows']}, "
                f"valid/nonoverlap={finding['metrics']['valid_nonoverlap_n']} (post-cutoff).",
                flush=True,
            )

        report = _render_report(records, as_of, replay_sha256)
        archive.writestr("INDEX.md", report.encode("utf-8"))
        manifest = {
            "format": "Formation-Bot alarm context ten-symbol trial",
            "schema_version": "1.1",
            "as_of": as_of.isoformat(),
            "timeframe": "4h",
            "symbol_count": len(symbols),
            "symbols": symbols,
            "domain_outputs_per_symbol": 5,
            "replay_source_sha256": replay_sha256,
            "json_outputs": json_manifest,
            "limitations": [
                "Historical context sample, not live alarm delivery.",
                "Symbol-specific replay findings are explicitly later than the historical snapshot.",
                "No trading advice or symbol-specific success probability is generated.",
            ],
        }
        archive.writestr(
            "MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"),
        )

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(report, encoding="utf-8")
    print(f"Wrote 10 full JSON packets: {args.output_zip} ({args.output_zip.stat().st_size:,} bytes)")
    print(f"Wrote symbol-by-symbol review: {args.report_output}")
    if args.json_dir:
        print(f"Also wrote uncompressed JSON members to: {args.json_dir}")


if __name__ == "__main__":
    main()
