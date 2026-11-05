"""Build an internal, read-only context packet from existing domain outputs.

This module does not fetch data, run scanners, persist snapshots, or make
alarm/trading decisions. Callers provide one symbol/timeframe's already
computed native domain results and an explicit timezone-aware ``as_of`` cut.
The packet keeps the complete native result in JSON and adds a readable view
plus separately sourced replay evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

SCHEMA_VERSION = "1.1"
DOMAIN_ORDER = (
    "market_structure",
    "volume_participation",
    "order_block",
    "fvg",
    "stabil",
)
EVIDENCE_ORDER = (*DOMAIN_ORDER, "formation_alert")

# Manually curated from the checked-in reports. Every item deliberately carries
# its run/population, unit of n, method, source, and limitations. These are
# descriptive replay references, never symbol-specific probabilities.
REPLAY_FINDINGS: tuple[dict[str, Any], ...] = (
    {
        "finding_id": "zone-touch-response-replay-2026-10-21",
        "recorded_at": "2026-10-21",
        "data_through": "2026-10-19",
        "timeline_note": "Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.",
        "domains": ["order_block", "fvg"],
        "title": "OB + FVG ortak temas tepkisi",
        "summary": (
            "240.484 temas epizodunda, beklenen yönde en az 1 ATR tepki oranı "
            "zaman dilimine göre %65,0–%66,5 aralığındaydı."
        ),
        "sample": "n=240.484 temas epizodu; OB ve FVG birlikte.",
        "scope": {
            "run_id": "replay-2026-10-21",
            "symbols": 176,
            "series": 704,
            "timeframes": ["1h", "2h", "4h", "1d"],
            "intraday_period": "2025-05-07 .. 2026-10-19",
            "unit": "OB/FVG temas epizodu",
            "n": 240484,
        },
        "metrics": {
            "expected_direction_at_least_1_atr": "%65.0–%66.5 (TF aralığı)",
            "expected_direction_0_25_to_1_atr": "%14.9–%18.1",
            "no_expected_direction_reaction": "%4.1–%4.8",
            "opposite_direction": "%11.2–%14.8",
            "measurement_horizon": "12 native bars after the contact anchor",
        },
        "method": (
            "Temas epizodu başına, çapadan sonraki native mumların fiyat yolu "
            "ATR ile ölçüldü; CALISTI eşiği beklenen yönde >=1 ATR uzanımdır."
        ),
        "limitations": [
            "Sonuç OB ve FVG temaslarını birlikte özetler; aileye özel oran değildir.",
            "Zaman dilimleri arası aralık tek bir sabit oran değildir.",
            "Havuz düzeyindeki tarihsel sıklık bu sembolün olasılığı değildir.",
            "Maliyet, pozisyon, emir gerçekleşmesi veya kârlılık ölçülmedi.",
        ],
        "sources": [
            "docs/arastirma/REPLAY_OZET_2026-10-21.md §3",
            "docs/arastirma/ARASTIRMA_HATTI.md",
        ],
    },
    {
        "finding_id": "ob-lifecycle-replay-2026-10-21",
        "recorded_at": "2026-10-21",
        "data_through": "2026-10-19",
        "timeline_note": "Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.",
        "domains": ["order_block"],
        "title": "Order Block temas ve yaşam döngüsü",
        "summary": (
            "131.901 OB zone'un %10,7–%13,3'ü TF'ye göre en az üç temas epizodu "
            "gördü; zone düzeyinde fiyat ihlali oranı %85,4–%93,6 aralığındaydı."
        ),
        "sample": "n=131.901 OB zone; ayrıca n=197.521 temas epizodu.",
        "scope": {
            "run_id": "replay-2026-10-21",
            "symbols": 176,
            "series": 704,
            "timeframes": ["1h", "2h", "4h", "1d"],
            "intraday_period": "2025-05-07 .. 2026-10-19",
            "unit": "OB zone; temas ayrıca epizot olarak sayılır",
            "n_zones": 131901,
            "n_touch_episodes": 197521,
        },
        "metrics": {
            "one_contact_share_by_timeframe": "%59.4–%59.9",
            "two_contact_share_by_timeframe": "%19.1–%21.3",
            "three_plus_contact_share_by_timeframe": "%10.7–%13.3",
            "untouched_share_by_timeframe": "%5.4–%10.3",
            "three_plus_total": {"n": 17048, "share": "%12.9"},
            "price_violation_share_by_timeframe": "%85.4–%93.6",
        },
        "method": (
            "OB zone yaşam döngüsü native bar bar izlendi; terminal fiyat ihlali "
            "ölçüldü. OB için native_full_fill alanı yapısal olarak False olduğundan "
            "geçilme metriği native_price_violation'dır."
        ),
        "limitations": [
            "TF aralıkları birbirinden ayrı hücrelerdir; toplam oran diye okunmamalı.",
            "Fiyat ihlali, kalıcı bariyer olmadığını anlatır; tek temas tepkisini silmez.",
            "Bunlar geçmiş BIST havuzunun betimsel sayımlarıdır, ASTOR/SNGYO'ya özel değildir.",
        ],
        "sources": [
            "docs/arastirma/REPLAY_OZET_2026-10-21.md §2–4",
            "docs/arastirma/ARASTIRMA_SONUCLARI.md §1–2",
            "docs/arastirma/ARASTIRMA_HATTI.md §'Bulunan iki survivorship tuzağı'",
        ],
    },
    {
        "finding_id": "fvg-lifecycle-replay-2026-10-21",
        "recorded_at": "2026-10-21",
        "data_through": "2026-10-19",
        "timeline_note": "Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.",
        "domains": ["fvg"],
        "title": "FVG temas sıklığı",
        "summary": (
            "55.145 FVG zone'un 12.680'i (%23,0) gözlenen arşivde hiç temas almadı; "
            "3+ temas yalnız 4 zone'da (%0,007) görüldü."
        ),
        "sample": "n=55.145 FVG zone; temas ölçümünde 42.963 epizot; 3+ temaslı 4 zone.",
        "scope": {
            "run_id": "replay-2026-10-21",
            "symbols": 176,
            "series": 704,
            "timeframes": ["2h", "4h", "1d"],
            "excluded_timeframe": "1h (bu replay hattı 1h FVG üretmiyor)",
            "intraday_period": "2025-05-07 .. 2026-10-19",
            "unit": "FVG zone; temas ayrıca epizot olarak sayılır",
            "n_zones": 55145,
            "n_touch_episodes": 42963,
        },
        "metrics": {
            "one_contact_share_by_timeframe": "%71.4–%77.9",
            "two_contact_share_by_timeframe": "%0.6–%1.1",
            "three_plus_total": {"n": 4, "share": "%0.007", "maximum": 5},
            "untouched_total": {"n": 12680, "share": "%23.0"},
        },
        "method": (
            "FVG zone'ları native lifecycle boyunca, temas epizodu sayısıyla izlendi. "
            "FVG tekrar temas oranları zone düzeyinde; temas tepkisi ortak OB+FVG "
            "temas tablosundan ayrı tutulur."
        ),
        "limitations": [
            "FVG replay kapsamı 2h/4h/1d'dir; 1h için sonuç yoktur.",
            "Arşiv penceresinde hiç temas almamak gelecekte de temas olmayacağı demek değildir.",
            "Bir sembolün mevcut FVG'si için olay-bağımsız olasılık üretmez.",
        ],
        "sources": [
            "docs/arastirma/REPLAY_OZET_2026-10-21.md §2, §4",
            "docs/arastirma/ARASTIRMA_SONUCLARI.md §1",
        ],
    },
    {
        "finding_id": "ms-4h-external-bos-replay-2026-10-21",
        "recorded_at": "2026-10-21",
        "data_through": "2026-10-19",
        "timeline_note": "Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.",
        "domains": ["market_structure"],
        "title": "4h dış BOS takip ölçümü",
        "summary": (
            "Seçili 4h EXTERNAL BOS grubunda n=3.387 olay için yön uyumu %98,0, "
            "rapor tanımındaki CALISTI oranı %71,0, devam-yok %7,5 ve ters yön %0,9 idi."
        ),
        "sample": "n=3.387 seçilmiş 4h dış BOS olayı.",
        "scope": {
            "run_id": "replay-2026-10-21",
            "symbols": 176,
            "series": 704,
            "timeframe": "4h",
            "event_scope": "EXTERNAL BOS only",
            "unit": "onaylanmış Market Structure olayı",
            "n": 3387,
            "period": "2025-05-07 .. 2026-10-19 intraday arşivi",
        },
        "metrics": {
            "direction_alignment": "%98.0",
            "calisti": "%71.0",
            "devam_yok": "%7.5",
            "ters_yon": "%0.9",
            "mean_continuation_h12_atr": 2.5,
            "forward_horizon": "12 native 4h bars",
        },
        "method": (
            "Ölçüm çapası confirmed event_bar'dır; candidate_bar değildir. "
            "Sonraki 12 native mumdaki sonuçlar ATR ile normalize edilmiştir."
        ),
        "limitations": [
            "Bu hücre yalnız 4h dış BOS'tur; iç yapı, CHOCH, sweep ve diğer TF'ler farklıdır.",
            "Direction alignment ile forward CALISTI ayrı ölçülerdir; biri diğerinin garantisi değildir.",
            "BIST havuzundaki geçmiş olaylar mevcut sembolün başarı olasılığı değildir.",
            "İşlem maliyeti, emir gerçekleşmesi veya portföy getirisi ölçülmedi.",
        ],
        "sources": [
            "docs/arastirma/REPLAY_OZET_2026-10-21.md §8",
            "docs/arastirma/ARASTIRMA_HATTI.md §'Ölçüm sözleşmesi'",
        ],
    },
    {
        "finding_id": "volume-zone-and-ms-context-2026-10",
        "recorded_at": None,
        "data_through": "2026-10-19",
        "timeline_note": "Rapor tarihi/run_id tabloda yok; ölçüm dönemi kapsamda 2026-10-19'a kadar uzanır.",
        "domains": ["volume_participation"],
        "title": "Hacim etkisi koşula göre farklı yönlü",
        "summary": (
            "4h zone-temas grubunda Q4 yüksek RVOL tepkisi Q1'den düşüktü (%61,0 vs %70,1); "
            "ayrı 4h MS-event grubunda Q4 devamı Q1'den yüksekti (%69,5 vs %66,1)."
        ),
        "sample": (
            "4h zone-temas: Q1 n=6.740, Q4 n=11.928; 4h MS-event: "
            "Q1 n=5.233, Q4 n=8.248. Kohortlar ayrı ve toplanamaz."
        ),
        "scope": {
            "run_id": "not_recorded_in_report_table",
            "symbols": 176,
            "series": 704,
            "timeframe": "4h",
            "zone_unit": "temas epizodu",
            "ms_unit": "onaylanmış Market Structure olayı",
            "period": "2025-05-07 .. 2026-10-19 intraday arşivi",
        },
        "metrics": {
            "zone_touch": {
                "Q1_low_rvol": {"n": 6740, "expected_direction_calisti": "%70.1"},
                "Q4_high_rvol": {"n": 11928, "expected_direction_calisti": "%61.0"},
            },
            "ms_event": {
                "Q1_low_rvol": {"n": 5233, "calisti": "%66.1", "alignment": "%95.9"},
                "Q4_high_rvol": {"n": 8248, "calisti": "%69.5", "alignment": "%97.9"},
            },
        },
        "method": (
            "RVOL çeyrekleri olay ailesine göre ayrı hesaplanmıştır. Zone-temas tepkisi "
            "ve MS-olayı devamı farklı kohort ve farklı ölçüm sorularıdır."
        ),
        "limitations": [
            "Bu iki karşıt sonuç tek bir 'yüksek hacim iyi/kötü' kuralına indirgenemez.",
            "Q1/Q4 arşiv kovalarıdır; canlı RVOL eşlemesi yaklaşık olabilir.",
            "MS-event n'si ile zone-touch n'si aynı birim değildir ve toplanamaz.",
            "Hacim verisinin bazı sembol/etiket kalitesi ayrıca sınırlıdır.",
            "2026-10-28 tarihli 177 sembol/708 seri DZ yenilemesi ayrı bir popülasyondur; bu bulgu onunla birleştirilmemiştir.",
        ],
        "sources": [
            "docs/arastirma/ARASTIRMA_BULGULARI.md §'Hacim — koşullandırma değişkeni'",
            "docs/arastirma/ARASTIRMA_SONUCLARI.md §'Hacim'",
            "docs/arastirma/AMPIRIK_REFERANS.md §'RVOL çeyreği yaklaşıktır'",
        ],
    },
    {
        "finding_id": "stabil-contact-behavior-2026-11-01",
        "recorded_at": "2026-11-01",
        "data_through": None,
        "timeline_note": "Manifest 2026-11-01'de üretildi; kaynak veri sonu manifestte kayıtlı değil.",
        "domains": ["stabil"],
        "title": "Stabil desteğinde bağımsız temas sırası (C02)",
        "summary": (
            "8×4h tam ufukta ilk/ikinci/3+ temas gruplarının medyan korunan kapanış "
            "değişimi sırasıyla -0,066 / +0,155 / -0,376 ATR idi; 3+ grup küçük ve yoğundur."
        ),
        "sample": "Toplam n=1.976; tam 8×4h ufuk n=1.943; sansürlü n=33; ilk/ikinci/3+ gruplar n=1.773/137/33.",
        "scope": {
            "run_id": "stabil-bhv48-2026-11-01",
            "symbols": 100,
            "symbol_range": "AEFES .. KONTR (seçilmiş arşiv hisseleri, alfabetik)",
            "checkpoints_4h": 107441,
            "first_seen_support_events": 10417,
            "question_count": 48,
            "table_row_count": 642,
            "user_confirmed_regime": False,
            "unit": "bağımsız destek-temas olayı; arada en az 0,35 günlük ATR",
            "forward_horizon": "8 × 4h mum",
        },
        "metrics": {
            "n_total": 1976,
            "n_full_8x4h": 1943,
            "n_censored_8x4h": 33,
            "first_contact": {"n_full": 1773, "median_retained_atr": -0.066},
            "second_contact": {"n_full": 137, "median_retained_atr": 0.155},
            "third_plus_contact": {
                "n_full": 33,
                "median_retained_atr": -0.376,
                "top1_symbol_share": "%81.8",
            },
            "report_verdict": "betimsel ayrım",
        },
        "method": (
            "Arşiv Stabil davranış replay'i tamamlanmış 4h kesitleri, nedensel günlük/haftalık "
            "girdiler, girişte sabitlenen günlük ATR ve açık sağ-sansürleme kullanır. C02, "
            "aralarında en az 0,35 günlük ATR bulunan bağımsız temasları sayar."
        ),
        "limitations": [
            "3+ temas kovası n=33 ve tek sembol payı %81,8; genellenebilir sonuç gibi okunmamalı.",
            "İlk arşiv epizodunun temas yaşı bilinmeyebilir; unknown başlangıçlar dışlanır.",
            "Bu 100-sembol davranış araştırmasıdır; anlık alarmın ya da canlı bildirimin kaydı değildir.",
            "Aday dikey/yatay rejim kullanan B01–B06 bölümleri kullanıcı teyidi bekler; bu pakette kural gibi sunulmaz.",
            "Manifest kaynak/veri hashlerini, kesin veri kesim zamanını ve tam native checkpoint paketini içermiyor.",
        ],
        "sources": [
            "docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md §STB-BHV-C02",
            "docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json",
            "research/stabil_replay.py",
            "research/stabil_bhv48.py",
        ],
    },
    {
        "finding_id": "stabil-live-universe-systematic-2026-10",
        "recorded_at": None,
        "data_through": "2026-10-19",
        "timeline_note": "Sonuç JSON'ı çalışma tarihini yazmıyor; veri aralığı 2026-10-19'da biter.",
        "domains": ["stabil"],
        "title": "Stabil canlı-evren geri-alım systematic arşiv testi",
        "summary": (
            "Arşivde bulunan 50/53 canlı non-macro sembolde 284 sinyal / 75,9 hafta: "
            "sonraki 4h kapanışta destek üstünde kalma %91,5; 8×4h medyan kapanış "
            "değişimi +0,262 ATR idi."
        ),
        "sample": "Toplam sinyal n=284; getirilerin her ufkundaki geçerli alt-n aggregate JSON'da ayrıca yayımlanmamıştır.",
        "scope": {
            "run_id": "not_recorded_in_result_json",
            "symbols": 50,
            "series": 50,
            "excluded_or_missing": ["XU50", "XBANK", "XUSIN"],
            "timeframe": "4h",
            "period": "2025-05-07 .. 2026-10-19",
            "unit": "6 bar cooldown sonrası Stabil geri-alım olayı",
            "cooldown_bars": 6,
            "burst_cap_single": 3,
            "n": 284,
            "span_weeks": 75.9,
        },
        "metrics": {
            "next_bar_hold_pct": "%91.5",
            "median_ret_8x4h_atr": 0.262,
            "mean_ret_8x4h_atr": 0.381,
            "equal_symbol_median_ret_8x4h_atr": 0.301,
            "median_ret_16x4h_atr": 0.188,
            "plus_1atr_within_8_pct": "%65.4",
            "minus_1atr_within_8_pct": "%49.3",
            "early_half_median_8x4h_atr": 0.426,
            "late_half_median_8x4h_atr": 0.02,
        },
        "method": (
            "Tarihsel arşiv çalışması tamamlanmış 4h mumlarda Stabil geri-alım davranışını "
            "ölçer; sinyaller arasında 6 mum cooldown uygulanır. Sonraki-mumda tutunma, "
            "bir sonraki 4h kapanışının sinyal destek seviyesine göre kontrolüdür; 8×4h "
            "kapanış değişimi giriş ATR'siyle ölçülür."
        ),
        "limitations": [
            "53 canlı non-macro sembolün yalnız 50'si arşivdeydi; XU50, XBANK ve XUSIN yoktur.",
            "Sonraki mum destek tutunması ve ATR-normalize kapanış değişimi betimsel fiyat yolu ölçüleridir; gerçekleşmiş işlem/kârlılık değildir.",
            "Erken/geç yarı medyanları (+0,426 ve +0,020 ATR) farklıdır; toplu değeri sabit kabul etmeyin.",
            "Bu systematic çalışma 100-sembol/48-soru davranış replay'inden ayrıdır ve onunla birleştirilemez.",
            "Aggregate JSON'da kesin koşu tarihi, kaynak hashleri, sinyal bazlı native paket, emir/dolum/maliyet verisi yoktur.",
        ],
        "sources": [
            "docs/arastirma/stabil_live_systematic_results.json",
            "research/stabil_live_systematic.py",
            "domain_engines/stabil/signals.py",
        ],
    },
    {
        "finding_id": "formation-zone-context-2026-10",
        "recorded_at": None,
        "data_through": "2026-10-19",
        "timeline_note": "Rapor tarihi/run_id yazılmamış; formasyon doğum aralığı 2026-10-19'a kadar uzanır.",
        "domains": ["formation_alert"],
        "title": "Formasyon kırılımında zone ve MS-rol eşleşmeleri",
        "summary": (
            "FRM-19'da kırılımda zone bulunan grup %75,9, zone bulunmayan %77,0 tamamlandı "
            "(-1,1 puan; ayrı örneklem). FRM-20'de rol uyumlu grup %79,6, uyumsuz %73,2 idi."
        ),
        "sample": (
            "Toplam 33.964 formasyon; FRM-19: zone var n=11.905 / yok n=20.232; "
            "FRM-20: rol uyumlu n=17.103 / uyumsuz n=14.857. Alt gruplar ayrı kohorttur."
        ),
        "scope": {
            "run_id": "not_recorded_in_report",
            "symbols": 176,
            "series": 704,
            "formations_total": 33964,
            "open_right_censored": 171,
            "unit": "formasyon/kırılım kohortu; FRM-19 ve FRM-20 alt grupları farklıdır",
        },
        "metrics": {
            "FRM_19_zone_at_breakout": {
                "zone_present": {"n": 11905, "completion": "%75.9"},
                "zone_absent": {"n": 20232, "completion": "%77.0"},
                "difference_percentage_points": -1.1,
                "difference_interval": "-2.2 .. -0.2 pp",
            },
            "FRM_20_role_alignment": {
                "aligned": {"n": 17103, "completion": "%79.6"},
                "unaligned": {"n": 14857, "completion": "%73.2"},
                "difference_percentage_points": 6.4,
                "difference_interval": "+5.3 .. +7.5 pp",
            },
        },
        "method": (
            "Raporun tanımladığı formasyon kohortları ve güven aralıkları kullanılmıştır; "
            "iki karşılaştırmanın paydaları farklıdır ve toplanamaz."
        ),
        "limitations": [
            "Kohort ilişkisi canlı bir nedeni veya gelecek sonucu göstermez.",
            "FRM-19 zone-var/yok karşılaştırmasının olay birimi OB/FVG temas replay'iyle aynı değildir.",
            "FRM-20, rapordaki en yakın rol uyumu karşılaştırmasıdır; tek başına MS olay replay'i değildir.",
        ],
        "sources": [
            "docs/arastirma/FORMASYON_SONUCLARI.md §FRM-19–20",
            "docs/arastirma/KOLON_SOZLUGU.md §13",
        ],
    },
)


def to_jsonable(value: Any) -> Any:
    """Convert native domain values to strict JSON-safe primitives.

    Unsupported object types raise instead of silently disappearing from what
    is intended to be a complete raw result. Non-finite numeric values become
    ``None`` and timestamps retain their original timezone offset.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.DataFrame):
        return {
            "__type__": "pandas.DataFrame",
            "index": to_jsonable(value.index),
            "columns": to_jsonable(value.columns),
            "column_dtypes": [str(dtype) for dtype in value.dtypes],
            "data": [
                [to_jsonable(value.iat[row, column]) for column in range(value.shape[1])]
                for row in range(value.shape[0])
            ],
        }
    if isinstance(value, pd.Series):
        return {
            "__type__": "pandas.Series",
            "name": to_jsonable(value.name),
            "dtype": str(value.dtype),
            "index": to_jsonable(value.index),
            "data": to_jsonable(value.tolist()),
        }
    if isinstance(value, pd.Index):
        return {
            "__type__": f"pandas.{type(value).__name__}",
            "names": to_jsonable(list(value.names)),
            "dtype": str(value.dtype),
            "values": to_jsonable(value.tolist()),
        }
    if isinstance(value, np.ndarray):
        return {
            "__type__": "numpy.ndarray",
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "values": to_jsonable(value.tolist()),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if all(isinstance(key, str) for key in value):
            return {key: to_jsonable(item) for key, item in value.items()}
        return {
            "__type__": "mapping",
            "items": [
                {"key": to_jsonable(key), "value": to_jsonable(item)}
                for key, item in value.items()
            ],
        }
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [to_jsonable(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    if isinstance(value, (str,)):
        return value
    raise TypeError(f"unsupported value for complete JSON serialization: {type(value).__name__}")


def replay_findings_for_domain(domain: str) -> list[dict[str, Any]]:
    """Return a detached copy of the curated findings relevant to ``domain``."""
    return [
        deepcopy(finding)
        for finding in REPLAY_FINDINGS
        if domain in finding["domains"]
    ]


def _annotate_replay_timeline(finding: Mapping[str, Any], as_of: pd.Timestamp) -> dict[str, Any]:
    """Copy one replay finding and label its availability at the packet cutoff."""
    output = deepcopy(dict(finding))
    recorded_at = output.get("recorded_at")
    data_through = output.get("data_through")
    dated_values = [
        (name, pd.Timestamp(value).date())
        for name, value in (("recorded_at", recorded_at), ("data_through", data_through))
        if value is not None
    ]
    later_values = [(name, value) for name, value in dated_values if value > as_of.date()]
    same_day = [(name, value) for name, value in dated_values if value == as_of.date()]
    record_date = None if recorded_at is None else pd.Timestamp(recorded_at).date()
    data_date = None if data_through is None else pd.Timestamp(data_through).date()
    if later_values:
        relation = "later_than_snapshot"
        available = False
        note = (
            "Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; "
            f"{as_of.date()} tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz."
        )
    elif same_day:
        relation = "same_date_time_unknown"
        available = None
        note = "Tarih aynı olsa da kayıt/veri zamanı saat düzeyinde yok; kesitte bilinirliği belirsizdir."
    elif record_date is not None and data_date is not None:
        relation = "recorded_and_measured_by_snapshot"
        available = True
        note = "Kayıt ve ölçüm dönemi snapshot tarihine kadar tamamlanmıştır."
    elif record_date is not None:
        relation = "data_cutoff_unknown"
        available = None
        note = "Rapor tarihi biliniyor, fakat ölçüm verisinin son tarihi kayıtlı değil."
    elif data_date is not None:
        relation = "report_date_unknown"
        available = None
        note = "Ölçüm veri sonu biliniyor, fakat raporun o tarihte yayımlanıp yayımlanmadığı bilinmiyor."
    else:
        relation = "timeline_unknown"
        available = None
        note = "Rapor ve ölçüm veri tarihleri kayıtlı değil."
    output["timeline"] = {
        "recorded_at": recorded_at,
        "data_through": data_through,
        "snapshot_as_of": as_of.isoformat(),
        "relation": relation,
        "available_at_snapshot": available,
        "note": note,
    }
    return output


def _evidence_for_domain(domain: str, as_of: pd.Timestamp) -> list[dict[str, Any]]:
    """Annotate later/unknown research timing instead of implying hindsight was known."""
    return [
        _annotate_replay_timeline(finding, as_of)
        for finding in replay_findings_for_domain(domain)
    ]


def _supplemental_replay_evidence(
    findings: Sequence[Mapping[str, Any]],
    *,
    symbol: str,
    as_of: pd.Timestamp,
) -> list[dict[str, Any]]:
    """Validate and timeline-label caller-supplied symbol-specific replay context."""
    required = {
        "finding_id", "title", "summary", "recorded_at", "data_through", "scope",
        "sample", "metrics", "method", "limitations", "sources", "domains",
    }
    output: list[dict[str, Any]] = []
    for index, raw in enumerate(findings):
        if not isinstance(raw, Mapping):
            raise TypeError(f"supplemental replay finding {index} must be a mapping")
        missing = required - set(raw)
        if missing:
            raise ValueError(
                f"supplemental replay finding {index} missing fields: {sorted(missing)}"
            )
        if not raw.get("finding_id") or not raw.get("title") or not raw.get("summary"):
            raise ValueError(f"supplemental replay finding {index} needs id/title/summary")
        scope = raw.get("scope")
        if not isinstance(scope, Mapping) or not scope.get("run_id"):
            raise ValueError(f"supplemental replay finding {index} needs scope.run_id")
        if not raw.get("sample") or not raw.get("method"):
            raise ValueError(f"supplemental replay finding {index} needs sample and method")
        if not isinstance(raw.get("metrics"), Mapping) or not raw["metrics"]:
            raise TypeError(f"supplemental replay finding {index} metrics must be a non-empty mapping")
        if not isinstance(raw.get("limitations"), Sequence) or isinstance(raw.get("limitations"), str):
            raise TypeError(f"supplemental replay finding {index} limitations must be a sequence")
        if not raw["limitations"]:
            raise ValueError(f"supplemental replay finding {index} needs at least one caveat")
        if any(not isinstance(item, str) or not item for item in raw["limitations"]):
            raise TypeError(f"supplemental replay finding {index} caveats must be non-empty strings")
        if not isinstance(raw.get("sources"), Sequence) or isinstance(raw.get("sources"), str):
            raise TypeError(f"supplemental replay finding {index} sources must be a sequence")
        if not raw["sources"]:
            raise ValueError(f"supplemental replay finding {index} needs at least one source")
        if any(not isinstance(item, str) or not item for item in raw["sources"]):
            raise TypeError(f"supplemental replay finding {index} sources must be non-empty strings")
        if not isinstance(raw.get("domains"), Sequence) or isinstance(raw.get("domains"), str):
            raise TypeError(f"supplemental replay finding {index} domains must be a sequence")
        if not raw.get("domains"):
            raise ValueError(f"supplemental replay finding {index} needs at least one domain")
        if any(not isinstance(item, str) or not item for item in raw["domains"]):
            raise TypeError(f"supplemental replay finding {index} domains must be non-empty strings")
        if raw.get("symbol") and str(raw["symbol"]).strip().upper() != symbol:
            raise ValueError(f"supplemental replay finding {index} symbol does not match packet symbol")
        if scope.get("symbol") and str(scope["symbol"]).strip().upper() != symbol:
            raise ValueError(f"supplemental replay finding {index} scope.symbol does not match packet symbol")
        if raw.get("recorded_at") is None and raw.get("data_through") is None:
            raise ValueError(
                f"supplemental replay finding {index} needs recorded_at or data_through for timeline review"
            )
        item = dict(raw)
        item["symbol"] = symbol
        output.append(_annotate_replay_timeline(item, as_of))
    return output


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _text(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return str(value)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_observed_time(value: Any, *, name: str, as_of: pd.Timestamp) -> pd.Timestamp | None:
    if value is None:
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    if timestamp > as_of:
        raise ValueError(f"{name} is later than the packet as_of cutoff")
    return timestamp


def _assert_no_future_native_timestamps(
    value: Any, *, as_of: pd.Timestamp, path: str = "native"
) -> None:
    """Reject ISO date/time values beyond the snapshot in a supplied native result."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_no_future_native_timestamps(item, as_of=as_of, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_future_native_timestamps(item, as_of=as_of, path=f"{path}[{index}]")
        return
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?",
        value,
    ):
        return
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(as_of.tzinfo)
    if timestamp > as_of:
        raise ValueError(
            f"{path} contains {value!r}, later than the packet as_of cutoff {as_of.isoformat()}"
        )


def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if number is None:
        return _text(value)
    rendered = f"{number:,.{digits}f}"
    return rendered.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def _direction(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, Enum):
        name = getattr(value, "name", None)
        value = name if name is not None else value.value
    if isinstance(value, str):
        upper = value.upper()
        if "UP" in upper or "BULL" in upper:
            return "yukarı"
        if "DOWN" in upper or "BEAR" in upper:
            return "aşağı"
        return value
    number = _number(value)
    if number is None:
        return str(value)
    if number > 0:
        return "yukarı"
    if number < 0:
        return "aşağı"
    return "nötr"


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _native_field(result: Any, field: str) -> Any:
    return _get(result, field)


def _base_status(domain: str, result: Any) -> dict[str, Any]:
    if result is None:
        return {
            "domain": domain,
            "status": "not_returned",
            "message": "Bu kesitte domain sonucu çağıran tarafından verilmedi.",
            "data_quality": None,
            "reason": None,
            "error": None,
            "native": None,
        }

    error = _get(result, "error")
    skipped = bool(_get(result, "skipped", False))
    reason = _get(result, "reason")
    native = to_jsonable(result)
    if error:
        status = "error"
        message = "Domain çalışması hata bildirdi; boş bulgu olarak yorumlanmamalı."
    elif skipped:
        status = "skipped"
        message = "Domain bu zaman diliminde/çağrıda atlandı."
    else:
        status = "available"
        message = None

    return {
        "domain": _text(_get(result, "domain"), domain),
        "symbol": _get(result, "symbol"),
        "timeframe": _get(result, "timeframe"),
        "status": status,
        "message": message,
        "data_quality": to_jsonable(_get(result, "data_quality")),
        "reason": to_jsonable(reason),
        "error": to_jsonable(error),
        "native": native,
    }


def _ms_summary(result: Any) -> dict[str, Any]:
    export = _native_field(result, "export")
    scopes: dict[str, Any] = {}
    for key, label in (("external_scope", "external"), ("internal_scope", "internal")):
        scope = _get(export, key)
        if scope is None:
            scopes[label] = None
            continue
        event = _get(scope, "latest_event")
        if event is None:
            event = _get(export, "latest_external_event" if label == "external" else "latest_internal_event")
        scopes[label] = {
            "state": _text(_get(scope, "state")),
            "direction": _direction(_get(scope, "direction")),
            "quality": to_jsonable(_get(scope, "quality")),
            "evidence_text": _text(_get(scope, "evidence_text"), ""),
            "latest_event": None if event is None else {
                "event_type": _text(_get(event, "event_type")),
                "direction": _direction(_get(event, "direction")),
                "confirmed_at": to_jsonable(_get(event, "confirmed_at")),
                "relevance": _text(_get(event, "relevance")),
                "validity": _text(_get(event, "validity")),
                "outcome": _text(_get(event, "outcome")),
                "broken_level": to_jsonable(_get(event, "broken_level")),
                "quality": to_jsonable(_get(event, "quality")),
            },
        }
    levels = {
        key: to_jsonable(_get(export, key))
        for key in (
            "external_protected_high", "external_protected_low",
            "external_weak_high", "external_weak_low",
            "internal_protected_high", "internal_protected_low",
            "internal_weak_high", "internal_weak_low",
        )
        if _get(export, key) is not None
    }
    return {"scopes": scopes, "levels": levels}


def _volume_summary(result: Any) -> dict[str, Any]:
    export = _native_field(result, "export")
    keys = (
        "state", "support_direction", "engine_direction", "quality",
        "magnitude_quality", "rvol", "relative_traded_value", "volume_level",
        "capital_level", "volume_regime", "capital_regime",
        "directional_value_pressure_5", "directional_value_pressure_10",
        "net_progress_atr", "directional_efficiency", "effort_result_class",
        "participation_direction", "participation_stage", "controlled_pullback",
        "controlled_reaction", "break_direction", "break_stage", "break_level",
        "break_reference_source", "absorption_side", "absorption_stage",
        "absorption_reference_level", "heavy_conflict", "one_bar_shock",
        "shock_direction",
    )
    return {key: to_jsonable(_get(export, key)) for key in keys if _get(export, key) is not None}


def _ob_summary(result: Any, reference_price: float | None) -> dict[str, Any]:
    details = _native_field(result, "details") or {}
    all_records = _get(details, "records")
    active = _get(details, "active_records")
    if active is not None:
        active_records = list(active)
    else:
        active_records = []

    def distance(record: Any) -> tuple[float, str]:
        lower = _number(_get(record, "bottom"))
        upper = _number(_get(record, "top"))
        source_time = _text(_get(record, "source_time"), "")
        if reference_price is None or lower is None or upper is None:
            return (math.inf, source_time)
        if lower <= reference_price <= upper:
            gap = 0.0
        else:
            gap = min(abs(reference_price - lower), abs(reference_price - upper))
        return (gap, source_time)

    ordered = sorted(active_records, key=distance)
    nearest = []
    for record in ordered[:5]:
        nearest.append({
            "direction": "bullish" if bool(_get(record, "bullish")) else "bearish",
            "lower": to_jsonable(_get(record, "bottom")),
            "upper": to_jsonable(_get(record, "top")),
            "source_time": to_jsonable(_get(record, "source_time")),
            "base_score": to_jsonable(_get(record, "base_score")),
            "has_imbalance": to_jsonable(_get(record, "has_imbalance")),
            "fill_boundary": to_jsonable(_get(record, "fill_boundary")),
        })
    return {
        "records_count": len(all_records) if all_records is not None else None,
        "active_records_count": len(active_records) if active is not None else None,
        "active_records_returned": active is not None,
        "nearest_active_records": nearest,
        "nearest_list_limit": 5,
        "full_active_records_in_native": True,
    }


def _fvg_record_summary(record: Any) -> dict[str, Any]:
    return {
        "direction": _text(_get(record, "direction")),
        "state": _text(_get(record, "state")),
        "lower_boundary": to_jsonable(_get(record, "lower_boundary")),
        "upper_boundary": to_jsonable(_get(record, "upper_boundary")),
        "formation_time": to_jsonable(_get(record, "formation_time")),
        "quality": to_jsonable(_get(record, "quality")),
        "tested": to_jsonable(_get(record, "tested")),
        "maximum_fill_ratio": to_jsonable(_get(record, "maximum_fill_ratio")),
        "reaction_evidence_count": to_jsonable(_get(record, "reaction_evidence_count")),
        "reaction_confirmed": to_jsonable(_get(record, "reaction_confirmed")),
        "failed_reaction": to_jsonable(_get(record, "failed_reaction")),
        "invalid": to_jsonable(_get(record, "invalid")),
    }


def _fvg_summary(result: Any) -> dict[str, Any]:
    details = _native_field(result, "details") or {}
    active: dict[str, list[dict[str, Any]]] = {}
    for key in ("active_bullish_fvg", "active_bearish_fvg"):
        active[key] = [_fvg_record_summary(item) for item in _as_items(_get(details, key))]
    formations = _get(details, "fvg_formations")
    return {
        "formation_count": len(formations) if formations is not None else None,
        "active_bullish_fvg": active["active_bullish_fvg"],
        "active_bearish_fvg": active["active_bearish_fvg"],
        "full_formation_history_in_native": formations is not None,
    }


def _stabil_summary(result: Any) -> dict[str, Any]:
    native_result = _native_field(result, "result")
    details = _native_field(result, "details") or {}
    trend = _get(native_result, "trend_context") or _get(details, "trend_context")
    support = _get(native_result, "support_snapshot") or _get(details, "support_snapshot")
    behavior = _get(native_result, "latest_behavior") or _get(details, "latest_behavior")
    readiness = _get(native_result, "role_readiness") or _get(details, "role_readiness") or {}

    trend_states = {}
    for name in ("weekly", "daily", "h4"):
        row = _get(trend, name)
        if row is not None:
            trend_states[name] = {
                "state": _text(_get(row, "state")),
                "data_ready": to_jsonable(_get(row, "data_ready")),
                "structure_usable": to_jsonable(_get(row, "structure_usable")),
            }

    readiness_summary = {}
    if isinstance(readiness, Mapping):
        for name, item in readiness.items():
            readiness_summary[str(name)] = {
                "status": _text(_get(item, "status")),
                "reason": to_jsonable(_get(item, "reason")),
            }

    support_summary = None
    if support is not None:
        support_summary = {
            key: to_jsonable(_get(support, key))
            for key in (
                "as_of", "support_level", "support_floor", "validity", "dynamics",
                "progression", "distance_pct", "distance_atr", "distance_delta_atr",
                "bars_since_support", "bars_above_support", "bars_below_support",
                "reclaim_count", "intrabar_below_support", "close_below_support",
                "close_below_floor",
            )
            if _get(support, key) is not None
        }

    behavior_summary = None
    if behavior is not None:
        behavior_summary = {
            key: to_jsonable(_get(behavior, key))
            for key in (
                "bar_close_time", "support_level", "close_price", "pct_vs_support",
                "dist_atr", "low_dist_atr", "body_atr", "close_pos", "vol_ratio",
                "fixed_support", "regime", "unchanged_days", "touch_count",
                "prev_breach_bars", "prev_breach_depth_atr", "reclaim_kind",
                "weak_reclaim", "rank_score", "momentum_kind",
            )
            if _get(behavior, key) is not None
        }

    return {
        "latest_close": to_jsonable(_get(native_result, "latest_close")),
        "latest_support_relation": to_jsonable(_get(native_result, "latest_support_relation")),
        "support": support_summary,
        "trend_states": trend_states,
        "role_readiness": readiness_summary,
        "latest_behavior": behavior_summary,
        "full_native_history_in_native": True,
    }


def _domain_summary(domain: str, result: Any, reference_price: float | None) -> dict[str, Any]:
    if result is None or _get(result, "error") or bool(_get(result, "skipped", False)):
        return {}
    if domain == "market_structure":
        return _ms_summary(result)
    if domain == "volume_participation":
        return _volume_summary(result)
    if domain == "order_block":
        return _ob_summary(result, reference_price)
    if domain == "fvg":
        return _fvg_summary(result)
    if domain == "stabil":
        return _stabil_summary(result)
    return {}


def _domain_lines(domain: str, entry: Mapping[str, Any]) -> list[str]:
    title = {
        "market_structure": "Piyasa yapısı",
        "volume_participation": "Hacim / katılım",
        "order_block": "Order Block",
        "fvg": "FVG",
        "stabil": "Stabil",
    }.get(domain, domain)
    lines = [f"## {title} · {entry.get('timeframe') or 'TF yok'}"]
    status = entry["status"]
    if status != "available":
        lines.append(f"Durum: {status} — {entry.get('message') or entry.get('reason') or entry.get('error') or 'açıklama yok'}")
        if entry.get("error"):
            lines.append(f"Hata: {entry['error']}")
        return lines

    quality = entry.get("data_quality")
    if quality is not None:
        lines.append(f"Veri/çıktı durumu: {_text(quality)}")
    summary = entry.get("summary") or {}

    if domain == "market_structure":
        for scope_name, label in (("external", "Dış"), ("internal", "İç")):
            scope = (summary.get("scopes") or {}).get(scope_name)
            if not scope:
                lines.append(f"{label}: snapshot yok.")
                continue
            line = (
                f"{label}: {scope['state']} ({scope['direction']}), "
                f"kalite {_text(scope['quality'])}/100"
            )
            event = scope.get("latest_event")
            if event:
                line += (
                    f"; son {event['event_type']} {event['direction']} "
                    f"@ {_text(event['confirmed_at'])}, "
                    f"ilişki={event['relevance']}, geçerlilik={event['validity']}"
                )
                if event.get("broken_level") is not None:
                    line += f", seviye {_fmt(event['broken_level'])}"
            lines.append(line)
        if summary.get("levels"):
            lines.append("Korunan/zayıf seviyeler: " + "; ".join(
                f"{key}={_fmt(value)}" for key, value in summary["levels"].items()
            ))

    elif domain == "volume_participation":
        fields_to_show = (
            ("state", "durum"), ("rvol", "RVOL"),
            ("relative_traded_value", "göreli işlem değeri"),
            ("volume_level", "hacim sınıfı"), ("capital_level", "sermaye sınıfı"),
            ("quality", "motor kalitesi"), ("effort_result_class", "efor/sonuç"),
            ("participation_stage", "katılım aşaması"),
            ("break_stage", "kırılım aşaması"), ("break_level", "kırılım seviyesi"),
            ("absorption_stage", "emilim aşaması"),
            ("heavy_conflict", "yüksek çatışma"), ("one_bar_shock", "tek mum şoku"),
        )
        for key, label in fields_to_show:
            if key not in summary:
                continue
            value = summary[key]
            if key in {"rvol", "relative_traded_value"}:
                value = f"{_fmt(value, 3)}×"
            elif key in {"quality", "magnitude_quality"}:
                value = f"{_fmt(value, 1)}/100"
            elif key == "break_level":
                value = _fmt(value)
            lines.append(f"{label}: {_text(value)}")

    elif domain == "order_block":
        lines.append(
            f"Kayıt: {_text(summary.get('records_count'))}; "
            f"aktif kayıt: {_text(summary.get('active_records_count'))}."
        )
        nearest = summary.get("nearest_active_records") or []
        if not summary.get("active_records_returned"):
            lines.append("Aktif kayıt ayrıntısı döndürülmedi; JSON'da eksik alan olarak korunur.")
        elif not nearest:
            lines.append("Aktif OB kaydı yok.")
        else:
            lines.append(f"En yakındaki {len(nearest)} aktif OB (tam liste JSON native alanındadır):")
            for record in nearest:
                lines.append(
                    f"- {record['direction']} {_fmt(record['lower'])}–{_fmt(record['upper'])}; "
                    f"oluşum {_text(record['source_time'])}; "
                    f"imbalance={_text(record['has_imbalance'])}; "
                    f"dolum sınırı={_fmt(record['fill_boundary'])}"
                )

    elif domain == "fvg":
        count = summary.get("formation_count")
        lines.append(f"Geçmiş formasyon kaydı: {_text(count)}.")
        for key, label in (("active_bullish_fvg", "Boğa"), ("active_bearish_fvg", "Ayı")):
            records = summary.get(key) or []
            if not records:
                lines.append(f"{label} yönünde aktif FVG kaydı yok.")
            for record in records:
                lines.append(
                    f"{label} FVG {_fmt(record['lower_boundary'])}–{_fmt(record['upper_boundary'])}; "
                    f"durum={record['state']}, oluşum={_text(record['formation_time'])}, "
                    f"test={_text(record['tested'])}, dolum={_fmt(record['maximum_fill_ratio'], 3)}, "
                    f"tepki kanıtı={_text(record['reaction_evidence_count'])}, "
                    f"onay={_text(record['reaction_confirmed'])}, kalite={_text(record['quality'])}"
                )

    elif domain == "stabil":
        lines.append(
            f"Son kapanış {_fmt(summary.get('latest_close'))}; "
            f"destek ilişkisi={_text(summary.get('latest_support_relation'))}."
        )
        support = summary.get("support")
        if support:
            lines.append(
                f"Destek={_fmt(support.get('support_level'))}, taban={_fmt(support.get('support_floor'))}; "
                f"seviye zamanı={_text(support.get('as_of'))}, "
                f"geçerlilik={_text(support.get('validity'))}, dinamik={_text(support.get('dynamics'))}, "
                f"ilerleme={_text(support.get('progression'))}, "
                f"uzaklık={_fmt(support.get('distance_pct'))}% / {_fmt(support.get('distance_atr'))} ATR; "
                f"destek yaşı={_text(support.get('bars_since_support'))} mum."
            )
        if summary.get("trend_states"):
            lines.append("Trend bağlamı: " + "; ".join(
                f"{name}={row['state']} (hazır={_text(row['data_ready'])}, kullanılabilir={_text(row['structure_usable'])})"
                for name, row in summary["trend_states"].items()
            ))
        if summary.get("role_readiness"):
            lines.append("Rol hazırlığı: " + "; ".join(
                f"{name}={item['status']}" for name, item in summary["role_readiness"].items()
            ))
        behavior = summary.get("latest_behavior")
        if behavior:
            lines.append(
                f"Son mum davranışı: rejim={_text(behavior.get('regime'))}, "
                f"temas sayısı={_text(behavior.get('touch_count'))}, "
                f"hacim oranı={_fmt(behavior.get('vol_ratio'), 3)}×, "
                f"geri-alım türü={_text(behavior.get('reclaim_kind'))}."
            )
    return lines


def _replay_finding_lines(finding: Mapping[str, Any]) -> list[str]:
    scope = finding["scope"]
    population_parts: list[str] = []
    if scope.get("symbols") is not None and scope.get("series") is not None:
        population_parts.append(f"{scope['symbols']} sembol / {scope['series']} seri")
    timeframe = scope.get("timeframe")
    if timeframe:
        population_parts.append(f"TF={timeframe}")
    elif scope.get("timeframes"):
        population_parts.append("TF=" + ", ".join(scope["timeframes"]))
    if scope.get("symbol_range"):
        population_parts.append(f"sembol aralığı={scope['symbol_range']}")
    if scope.get("user_confirmed_regime") is False:
        population_parts.append("aday rejim eşlemesi kullanıcı teyitli değil")
    period = scope.get("intraday_period", scope.get("period"))
    if period:
        population_parts.append(f"dönem={period}")
    unit = scope.get("unit")
    if unit:
        population_parts.append(f"birim={unit}")
    if scope.get("zone_unit") or scope.get("ms_unit"):
        population_parts.append(
            f"birim: zone={scope.get('zone_unit', '—')}; MS={scope.get('ms_unit', '—')}"
        )
    if scope.get("n_zones") is not None:
        population_parts.append(f"zone n={scope['n_zones']}")
    if scope.get("n_touch_episodes") is not None:
        population_parts.append(f"temas epizodu n={scope['n_touch_episodes']}")
    if scope.get("checkpoints_4h") is not None:
        population_parts.append(f"4h kesiti n={scope['checkpoints_4h']}")
    if scope.get("first_seen_support_events") is not None:
        population_parts.append(f"ilk görülen destek olayı n={scope['first_seen_support_events']}")
    if scope.get("question_count") is not None:
        population_parts.append(f"soru n={scope['question_count']}")
    if scope.get("table_row_count") is not None:
        population_parts.append(f"tablo satırı n={scope['table_row_count']}")
    if scope.get("formations_total") is not None:
        population_parts.append(f"formasyon n={scope['formations_total']}")
    if scope.get("open_right_censored") is not None:
        population_parts.append(f"sağdan sansürlü/açık={scope['open_right_censored']}")
    if scope.get("excluded_timeframe"):
        population_parts.append(f"hariç={scope['excluded_timeframe']}")

    run_id = scope.get("run_id", "not_recorded")
    if run_id in {
        "not_recorded", "not_recorded_in_report", "not_recorded_in_report_table",
        "not_recorded_in_result_json",
    }:
        run_label = "rapor tablosunda run_id kaydedilmemiş"
    else:
        run_label = f"run_id={run_id}"

    lines = [f"- {finding['title']}: {finding['summary']}"]
    if population_parts:
        lines.append("  Kapsam: " + "; ".join(population_parts) + f"; {run_label}.")
    else:
        lines.append(f"  Kapsam: {run_label}.")
    timeline = finding.get("timeline")
    if timeline:
        available = timeline.get("available_at_snapshot")
        availability_label = (
            "kesitte erişilebilir"
            if available is True
            else "SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu"
            if available is False
            else "kesitte erişilebilirliği belirsiz"
        )
        lines.append(
            f"  Zaman: kayıt={timeline.get('recorded_at') or 'tarih yok'}; "
            f"veri sonu={timeline.get('data_through') or 'bilinmiyor'}; "
            f"{availability_label}. {timeline['note']}"
        )
    if finding.get("timeline_note"):
        lines.append(f"  Zaman notu: {finding['timeline_note']}")
    if finding.get("sample"):
        lines.append(f"  Örneklem: {finding['sample']}")
    if finding.get("method"):
        lines.append(f"  Yöntem: {finding['method']}")
    limitations = finding.get("limitations", finding.get("caveats", []))
    if limitations:
        lines.append("  Sınır: " + " ".join(limitations))
    if finding.get("sources"):
        lines.append("  Kaynak: " + "; ".join(finding["sources"]))
    return lines


def _render_text(packet: Mapping[str, Any]) -> str:
    snap = packet["snapshot"]
    price_time = snap.get("price_time")
    lines = [
        f"# {packet['symbol']} {packet['timeframe']} · domain context",
        f"Kesit: {packet['as_of']} · tür: {packet['context_kind']} · "
        f"referans kapanış: {_fmt(snap.get('reference_price'))} · "
        f"fiyat zamanı: {_text(price_time)}",
    ]
    if snap.get("closed_bar_count") is not None:
        lines.append(f"Tamamlanmış mum sayısı: {snap['closed_bar_count']}.")
    trigger = packet.get("trigger")
    if trigger is None:
        lines.append("Tetikleyici: manuel/on-demand istek; alarm olayı eklenmedi.")
    else:
        lines.append(
            "Tetikleyici: " + "; ".join(
                f"{key}={_text(value)}"
                for key, value in trigger.items()
                if value is not None and key not in {"symbol", "timeframe"}
            )
        )

    for domain in DOMAIN_ORDER:
        lines.extend(_domain_lines(domain, packet["domain_outputs"][domain]))
        findings = packet["replay_evidence"].get(domain, [])
        if findings:
            lines.append("Replay bağlamı (bu sembolün olasılığı değildir):")
            for finding in findings:
                lines.extend(_replay_finding_lines(finding))

    formation = packet["replay_evidence"].get("formation_alert", [])
    if formation:
        lines.append("## Formasyon alarmına ilişkin arşiv bağlamı")
        for finding in formation:
            lines.extend(_replay_finding_lines(finding))

    symbol_specific = packet["replay_evidence"].get("symbol_specific", [])
    if symbol_specific:
        lines.append("## Sembole özgü replay incelemesi · tarihsel kesitten ayrı")
        for finding in symbol_specific:
            lines.extend(_replay_finding_lines(finding))

    lines.append(
        "\nBu paket açıklayıcı bağlamdır; al/sat, pozisyon, fiyat hedefi veya "
        "işlem tavsiyesi üretmez. Canlı alarm kararı ve domain motorlarını değiştirmez."
    )
    return "\n".join(lines)


def build_context_packet(
    *,
    symbol: str,
    timeframe: str,
    as_of: Any,
    domain_results: Mapping[str, Any],
    trigger: Mapping[str, Any] | None = None,
    context_kind: str = "request",
    generated_at: Any | None = None,
    reference_price: Any | None = None,
    price_time: Any | None = None,
    closed_bar_count: int | None = None,
    data_source: str = "caller_supplied_snapshot",
    supplemental_replay_findings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a complete JSON/text packet for a supplied alarm or request cut.

    ``domain_results`` is a same-symbol/same-timeframe map keyed by domain
    name. Missing engines are represented explicitly. This helper does not
    call engines; request/alarm integrations remain responsible for creating a
    properly closed-bar, as-of result before calling it. Caller-supplied
    ``supplemental_replay_findings`` are validated and kept under a separate
    ``replay_evidence.symbol_specific`` key with explicit snapshot timing; they
    never enter the native current-domain output.
    """
    normalized_symbol = str(symbol).strip().upper()
    normalized_tf = str(timeframe).strip().lower()
    unknown_domains = set(domain_results) - set(DOMAIN_ORDER)
    if unknown_domains:
        raise ValueError(f"unknown domain result(s): {sorted(unknown_domains)}")
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if normalized_tf not in {"1h", "2h", "4h", "1d"}:
        raise ValueError(f"unsupported Formation-Bot timeframe: {timeframe!r}")
    if context_kind not in {"alarm", "request", "historical_sample"}:
        raise ValueError("context_kind must be alarm, request, or historical_sample")

    as_of_ts = pd.Timestamp(as_of)
    if as_of_ts.tzinfo is None:
        raise ValueError("as_of must be timezone-aware; naive time is ambiguous")
    generated_ts = pd.Timestamp(generated_at or datetime.now(timezone.utc))
    if generated_ts.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    price_ts = _validate_observed_time(price_time, name="price_time", as_of=as_of_ts)
    if closed_bar_count is not None:
        if isinstance(closed_bar_count, bool) or not isinstance(closed_bar_count, (int, np.integer)):
            raise TypeError("closed_bar_count must be a non-negative integer")
        if closed_bar_count < 0:
            raise ValueError("closed_bar_count must be a non-negative integer")

    trigger_json = None if trigger is None else to_jsonable(trigger)
    if context_kind == "alarm" and trigger_json is None:
        raise ValueError("alarm context requires the original trigger payload")
    if trigger_json is not None:
        if not isinstance(trigger_json, Mapping):
            raise TypeError("trigger must serialize to a mapping")
        if context_kind == "alarm" and trigger_json.get("triggered_at") is None:
            raise ValueError("alarm trigger must include timezone-aware triggered_at")
        trigger_symbol = trigger_json.get("symbol")
        trigger_tf = trigger_json.get("timeframe")
        if trigger_symbol and str(trigger_symbol).strip().upper() != normalized_symbol:
            raise ValueError("trigger symbol does not match packet symbol")
        if trigger_tf and str(trigger_tf).strip().lower() != normalized_tf:
            raise ValueError("trigger timeframe does not match packet timeframe")
        for time_key in ("triggered_at", "candidate_at", "candidate_bar_time", "confirmed_at"):
            if trigger_json.get(time_key) is not None:
                _validate_observed_time(
                    trigger_json[time_key], name=f"trigger.{time_key}", as_of=as_of_ts
                )

    ref_price = _number(reference_price)
    domain_outputs: dict[str, Any] = {}
    for domain in DOMAIN_ORDER:
        result = domain_results.get(domain)
        entry = _base_status(domain, result)
        if entry["status"] == "available":
            _assert_no_future_native_timestamps(
                entry["native"], as_of=as_of_ts, path=f"domain_outputs.{domain}.native"
            )
        output_symbol = entry.get("symbol")
        output_tf = entry.get("timeframe")
        if output_symbol and str(output_symbol).strip().upper() != normalized_symbol:
            raise ValueError(f"{domain} result symbol does not match packet symbol")
        if output_tf and str(output_tf).strip().lower() != normalized_tf:
            raise ValueError(f"{domain} result timeframe does not match packet timeframe")
        entry["summary"] = _domain_summary(domain, result, ref_price)
        domain_outputs[domain] = entry

    replay_evidence = {
        domain: _evidence_for_domain(domain, as_of_ts)
        for domain in EVIDENCE_ORDER
    }
    replay_evidence["symbol_specific"] = _supplemental_replay_evidence(
        supplemental_replay_findings,
        symbol=normalized_symbol,
        as_of=as_of_ts,
    )
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "packet_type": "domain_context",
        "context_kind": context_kind,
        "symbol": normalized_symbol,
        "timeframe": normalized_tf,
        "as_of": as_of_ts.isoformat(),
        "generated_at": generated_ts.isoformat(),
        "data_source": str(data_source),
        "snapshot": {
            "reference_price": ref_price,
            "price_time": None if price_ts is None else to_jsonable(price_ts),
            "closed_bar_count": None if closed_bar_count is None else int(closed_bar_count),
            "closed_bar_cut_required": True,
        },
        "trigger": trigger_json,
        "domain_outputs": domain_outputs,
        "replay_evidence": replay_evidence,
        "interpretation_policy": {
            "nature": "descriptive_context_only",
            "not_symbol_specific_probability": True,
            "not_a_trading_recommendation": True,
            "replay_populations_must_not_be_merged": True,
            "current_snapshot_and_historical_replay_are_separate": True,
        },
    }
    packet["readable_text"] = _render_text(packet)
    # Fail here rather than returning a packet that downstream JSON encoders
    # would silently emit with NaN/Infinity or an unsupported domain object.
    json.dumps(packet, ensure_ascii=False, allow_nan=False)
    return packet


def packet_json(packet: Mapping[str, Any], *, indent: int = 2) -> str:
    """Serialize a packet as strict UTF-8 JSON text."""
    return json.dumps(packet, ensure_ascii=False, indent=indent, allow_nan=False)


def packet_text(packet: Mapping[str, Any]) -> str:
    """Return the human-readable rendering already embedded in the packet."""
    return str(packet["readable_text"])
