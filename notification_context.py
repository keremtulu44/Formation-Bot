"""Format existing domain-engine exports for Telegram formation alerts.

This module is deliberately read-only and knows nothing about domain-engine
algorithms. It only renders the fresh exports returned by ``run_domain_engines``;
missing, skipped, errored, or empty outputs are omitted rather than guessed.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from reporting.format import sayi
from telegram_measure import SATIR_BUTCE, genislik

TIMEFRAME_ORDER = ("1h", "2h", "4h", "1d")
TIMEFRAME_LABELS = {"1h": "1s", "2h": "2s", "4h": "4s", "1d": "1g"}


#: Kart dilinde OB/FVG yerine okunur karşılığı: "blok" (order block) ve
#: "boşluk" (fair value gap). Kısaltma kartta yaşamaz (kullanıcı kararı
#: 2026-10-22: "herkesin anlayabileceği format"). `/panel`, export ve log
#: yüzeyleri teknik adı kullanmaya devam eder.
#: 2026-10-23: "blok" (order block) kullanıcıya bir şey söylemiyordu;
#: "bölge" aynı bilgiyi sade dilde taşır. FVG zaten "boşluk" olarak basılıyor.
_ZONE_SADE = {"OB": "bölgesi", "FVG": "boşluğu"}

#: Kart satırının güvenle sığdığı piksel eşiği (notifier._kart_esik_px ile aynı
#: mantık: bütçenin %5 güvenlik payının altında kal).
_KART_ESIK_PX = float(SATIR_BUTCE) * 0.95 - 6.0


def _sigdir(adaylar: list[str]) -> str:
    """Bütçeye sığan EN BİLGİLİ adayı seç; hiçbiri sığmazsa en kısasını döndür.

    Sade dil satırları teknik kısaltmalardan uzun (FVG → boşluk). Uzun fiyatlı
    sembollerde satırı bölmek yerine sıfat düşer, ölçü kalır (bilgi sırası:
    yön/ok → bölge türü → TF → fiyat → mesafe).
    """
    for aday in adaylar:
        if genislik(aday) <= _KART_ESIK_PX:
            return aday
    return min(adaylar, key=genislik)


def _field(value: Any, name: str, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _token(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip().upper()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _price(value: Any) -> str:
    """Fiyat metni: biçim `reporting.format.sayi`den (G0 tek standardı).

    Kart zaten virgül basıyordu; buradaki `.replace()` yerine aynı yardımcının
    çağrılması iki kuralın zamanla ayrışmasını engeller. Çıktı baytı değişmedi.
    """
    number = _number(value)
    return sayi(number) if number is not None else ""


def _usable_export(result: Any):
    if result is None or bool(_field(result, "skipped", False)) or _field(result, "error"):
        return None
    return _field(result, "export")


def _domain(results_by_timeframe: Any, timeframe: str, name: str):
    if not isinstance(results_by_timeframe, Mapping):
        return None
    per_tf = results_by_timeframe.get(timeframe)
    if not isinstance(per_tf, Mapping):
        return None
    return per_tf.get(name)


def _direction(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    if number > 0:
        return "↑"
    if number < 0:
        return "↓"
    return ""


def _structure_state(scope: Any, exported_code: Any) -> str:
    state = _structure_token(scope, exported_code)
    return _STRUCTURE_LABELS.get(state, "")


def _structure_token(scope: Any, exported_code: Any) -> str:
    """Engine state name ('STATE_BULLISH' ...) for a scope, falling back to code."""
    state = _token(_field(scope, "state"))
    if state:
        return state
    code = _number(exported_code)
    if code is None:
        return ""
    return {
        2.0: "STATE_BULLISH",
        1.0: "STATE_TRANSITION_UP",
        -2.0: "STATE_BEARISH",
        -1.0: "STATE_TRANSITION_DOWN",
        0.0: "STATE_NEUTRAL",
    }.get(code, "")


# Kart stili: telefon satırı bütçesi dar olduğu için durum kelimesi yön okuyla
# yazılır (veri aynı, metin kısa).
_STRUCTURE_LABELS = {
    "STATE_BULLISH": "yükseliş",
    "STATE_BEARISH": "düşüş",
    "STATE_TRANSITION_UP": "yukarı geçiş",
    "STATE_TRANSITION_DOWN": "aşağı geçiş",
    "STATE_NEUTRAL": "yatay",
}
_STRUCTURE_SHORT = {
    "STATE_BULLISH": "↑",
    "STATE_BEARISH": "↓",
    "STATE_TRANSITION_UP": "↑geçiş",
    "STATE_TRANSITION_DOWN": "↓geçiş",
    "STATE_NEUTRAL": "–",
}
#: Kart dili (2026-10-22): yapı durumu okla değil sözcükle yazılır. Ok, "yukarı
#: döndü" ile "yukarı" arasındaki farkı taşımıyordu; geçiş hâli ayrı sözcük.
_STRUCTURE_SADE = {
    "STATE_BULLISH": "yukarı",
    "STATE_BEARISH": "aşağı",
    "STATE_TRANSITION_UP": "yukarı döndü",
    "STATE_TRANSITION_DOWN": "aşağı döndü",
    "STATE_NEUTRAL": "yatay",
}
#: Aynı durumların bütçe daraldığında kullanılan kısa hâli ("döndü" düşer).
#: Nuance kaybı yalnız satır sığmadığında olur; sığdığında tam sözcük basılır.
_STRUCTURE_SADE_KISA = {
    "STATE_BULLISH": "yukarı",
    "STATE_BEARISH": "aşağı",
    "STATE_TRANSITION_UP": "yukarı",
    "STATE_TRANSITION_DOWN": "aşağı",
    "STATE_NEUTRAL": "yatay",
}


def _event_rows(export: Any) -> list[Any]:
    events = _field(export, "events", ()) or ()
    if not isinstance(events, (tuple, list)):
        events = ()
    # Older/partial exports may expose only the latest event fields.
    candidates = list(events)
    candidates.extend(
        event for event in (
            _field(export, "latest_external_event"),
            _field(export, "latest_internal_event"),
        ) if event is not None
    )
    seen: set[str] = set()
    output = []
    for event in candidates:
        uid = str(_field(event, "event_uid") or "")
        key = uid or "|".join(
            str(_field(event, field, ""))
            for field in ("scope", "event_type", "event_bar", "broken_level")
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(event)
    return output


_SEVIYE_ALANLARI = (
    ("PH", "external_protected_high", "korunan"),
    ("PL", "external_protected_low", "korunan"),
    ("WH", "external_weak_high", "zayıf"),
    ("WL", "external_weak_low", "zayıf"),
)


def _market_structure_rows(results_by_timeframe: Any) -> list[dict]:
    """Per-timeframe current structure: states, confirmed events, swing levels.

    Returns a plain structure so the verbose (legacy) renderer and the compact
    card renderer share exactly the same filtering: an event counts as current
    only when it is confirmed, valid, and not superseded/historical.
    """
    rows: list[dict] = []
    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "market_structure")
        export = _usable_export(result)
        if export is None:
            continue

        current_events = []
        for event in _event_rows(export):
            event_type = _token(_field(event, "event_type"))
            if event_type not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
                continue
            validity = _token(_field(event, "validity"))
            relevance = _token(_field(event, "relevance"))
            confirmation = _token(_field(event, "confirmation_status"))
            if confirmation != "CONFIRMED":
                continue
            if validity == "FAILED" or relevance in {"SUPERSEDED", "HISTORICAL"}:
                continue
            if not bool(_field(event, "is_active", True)):
                continue
            current_events.append(event)

        # At most the latest current BOS/CHoCH from each scope keeps the alert
        # concise without hiding the active external/internal direction.
        latest_by_scope: dict[str, Any] = {}
        for event in current_events:
            scope = _token(_field(event, "scope")) or "STRUCTURE"
            prior = latest_by_scope.get(scope)
            event_bar = _number(_field(event, "event_bar"))
            prior_bar = _number(_field(prior, "event_bar")) if prior is not None else None
            if prior is None or (event_bar is not None and (prior_bar is None or event_bar >= prior_bar)):
                latest_by_scope[scope] = event

        # The same fact is often reported by both scopes with the same level and
        # direction (25 Eyl akışında 4 satır/gün böyle kopyaydı). Tek satırda
        # "dış+iç" olarak birleştirilir; bilgi düşmez.
        olan: dict[tuple, dict] = {}
        for scope, event in latest_by_scope.items():
            raw_type = _token(_field(event, "event_type"))
            anahtar = (
                "CHoCH" if "CHOCH" in raw_type else "BOS",
                _direction(_field(event, "direction")),
                _price(_field(event, "broken_level")),
            )
            giris = olan.setdefault(anahtar, {"kapsam": [], "gecerli": False, "guncel": False})
            giris["kapsam"].append(
                "dış" if scope == "EXTERNAL" else "iç" if scope == "INTERNAL" else ""
            )
            if _token(_field(event, "validity")) == "VALID":
                giris["gecerli"] = True
            if _token(_field(event, "relevance")) == "CURRENT":
                giris["guncel"] = True

        olaylar = [
            {
                "etiket": etiket, "yon": yon, "seviye": seviye,
                "kapsam": "+".join(sorted({k for k in giris["kapsam"] if k})),
                "gecerli": giris["gecerli"], "guncel": giris["guncel"],
            }
            for (etiket, yon, seviye), giris in olan.items()
        ]
        salinim = [
            {"etiket": etiket, "seviye": _price(_field(export, alan)), "rol": rol}
            for etiket, alan, rol in _SEVIYE_ALANLARI
            if _price(_field(export, alan))
        ]
        rows.append({
            "timeframe": timeframe,
            "etiket": TIMEFRAME_LABELS[timeframe],
            "dis": _structure_token(_field(export, "external_scope"), _field(export, "external_state")),
            "ic": _structure_token(_field(export, "internal_scope"), _field(export, "internal_state")),
            "olaylar": olaylar,
            "salinim": salinim,
        })
    return rows


def _format_market_structure(rows: list[dict]) -> list[str]:
    """Verbose (legacy) rendering: full words, one line per event and swing."""
    lines: list[str] = []
    for satir in rows:
        state_parts = [
            part for part in (
                f"dış {_STRUCTURE_LABELS.get(satir['dis'], '')}" if satir["dis"] else "",
                f"iç {_STRUCTURE_LABELS.get(satir['ic'], '')}" if satir["ic"] else "",
            ) if part
        ]
        if state_parts:
            lines.append(f"• {satir['etiket']} yapı: " + " · ".join(state_parts))
        for olay in satir["olaylar"]:
            # `teyitli` basılmaz: filtre yalnız CONFIRMED olayları buraya bırakır,
            # yani kelime her satırda aynı sabit metindir (bilgi taşımaz).
            durum = " ".join(part for part in (
                "geçerli" if olay["gecerli"] else "",
                "güncel" if olay["guncel"] else "",
            ) if part)
            parcalar = [p for p in (olay["kapsam"], durum) if p]
            suffix = (" · " + " · ".join(parcalar)) if parcalar else ""
            seviye = f" {olay['seviye']}" if olay["seviye"] else ""
            lines.append(f"  {olay['etiket']} {olay['yon']}{seviye}{suffix}")
        if satir["salinim"]:
            lines.append("  " + " · ".join(
                f"{x['etiket']} {x['seviye']} ({x['rol']}, güncel)" for x in satir["salinim"]
            ))
    return lines


def _kart_market_structure(rows: list[dict], alarm_tf: str) -> list[str]:
    """Card rendering: alert timeframe lists its events, others one line each.

    Neden böyle: canlı akışta aynı hissenin iki farklı TF alarmındaki piyasa
    yapısı bloğu birebir aynıydı (638 kr kopya metin) — blok alarm TF'sine göre
    süzülmüyordu. Kart, alarm TF'sini ayırır; diğer TF'ler durum + tek salınım
    seviyesi olarak özetlenir (olay seviyeleri /tara'da).
    """
    # Alarm TF en üstte: kullanıcı önce kırılımın kendi zaman diliminin yapısını okur.
    rows = sorted(rows, key=lambda r: 0 if r["timeframe"] == alarm_tf else 1)
    lines: list[str] = []
    for satir in rows:
        dis = _STRUCTURE_SHORT.get(satir["dis"], "")
        ic = _STRUCTURE_SHORT.get(satir["ic"], "")
        if satir["timeframe"] == alarm_tf:
            parcalar = [p for p in (f"dış {dis}" if dis else "", f"iç {ic}" if ic else "") if p]
            baslik = f"◈ {satir['etiket']} yapı: " + " · ".join(parcalar)
            lines.append(baslik)
            for olay in satir["olaylar"]:
                parca = [
                    olay["kapsam"],
                    f"{olay['etiket']} {olay['yon']} {olay['seviye']}".strip(),
                    "geçerli" if olay["gecerli"] else "geçersiz",
                ]
                lines.append("   " + " · ".join(p for p in parca if p))
        else:
            durum = "/".join(p for p in (dis, ic) if p) or "–"
            ilk = satir["salinim"][:1]
            ek = f" · {ilk[0]['etiket']} {ilk[0]['seviye']}" if ilk else ""
            lines.append(f"▸ {satir['etiket']} {durum}{ek}")
    return lines


def _zone_location(top: float, bottom: float, reference: float | None) -> tuple[str, float] | None:
    if reference is None:
        return None
    if bottom > reference:
        return "üst", bottom - reference
    if top < reference:
        return "alt", reference - top
    return "içinde", 0.0


def _format_order_blocks(results_by_timeframe: Any, reference_price: float | None) -> list[str]:
    candidates: dict[str, list[tuple[float, str]]] = {"üst": [], "alt": []}
    if reference_price is None:
        return []

    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "order_block")
        export = _usable_export(result)
        if export is None:
            continue
        for side_key, side_label in (("bull", "boğa OB"), ("bear", "ayı OB")):
            side = _field(export, side_key)
            top = _number(_field(side, "top"))
            bottom = _number(_field(side, "bottom"))
            if top is None or bottom is None or top < bottom:
                continue
            location = _zone_location(top, bottom, reference_price)
            if location is None:
                continue
            group, distance = location
            # A zone containing the current close is neither above nor below;
            # this compact alert only allocates one slot to each requested side.
            if group not in candidates:
                continue
            fill = _number(_field(side, "fill"))
            state = _number(_field(side, "state"))
            parts = [
                f"{TIMEFRAME_LABELS[timeframe]} {side_label} "
                f"{_price(bottom)}–{_price(top)} TL"
            ]
            # OB tarafının `state` alanı yaşam döngüsü kodu değil, boğa/ayı
            # işaretidir (domain_engines/order_block/order_block.py:109 →
            # state = ±1.0). Eskiden "state != 0" her zaman true olduğu için her
            # OB satırına sabit "aktif" yazılıyordu: sıfır bilgi, ~7 kr/şer satır.
            # Artık yalnız gerçek bir yaşam döngüsü kodu gelirse etiketlenir.
            etiket = _OB_STATE_LABELS.get(abs(int(state))) if state is not None else None
            if etiket:
                parts.append(etiket)
            if fill is not None:
                parts.append(f"%{max(0, min(100, round(fill * 100)))} dolu")
            candidates[group].append((distance, " · ".join(parts)))

    lines = []
    for group, label in (("üst", "Üst"), ("alt", "Alt")):
        if candidates[group]:
            # Order-block exports do not expose a comparable score. The engine
            # already selects its per-TF candidate; choose the nearest exported
            # zone across timeframes without inventing a score or test count.
            _, text = min(candidates[group], key=lambda item: item[0])
            lines.append(f"• {label}: {text}")
    return lines


# OrderBlock tarafı için geçerli olabilecek yaşam döngüsü kodları; motor şu an
# yalnız ±1 gönderdiği için pratikte boş kalır (bilgi taşımayan "aktif" kelimesi
# bu yüzden basılmaz). Motor ileride gerçek state üretirse kart da otomatik gösterir.
_OB_STATE_LABELS: dict[int, str] = {}

_FVG_STATE_LABELS = {
    2: "aday",
    3: "aktif",
    4: "ilk temas",
    5: "kısmi dolum",
    6: "derin temas",
    8: "reaksiyon",
}
_FVG_TERMINAL_STATES = {7, 9, 10, 11}


def _format_fvgs(results_by_timeframe: Any, reference_price: float | None) -> list[str]:
    candidates: dict[str, list[tuple[float | None, float, str]]] = {"üst": [], "alt": []}
    if reference_price is None:
        return []

    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "fvg")
        export = _usable_export(result)
        if export is None:
            continue
        for side_key, side_label in (("bull_fvg", "boğa FVG"), ("bear_fvg", "ayı FVG")):
            side = _field(export, side_key)
            state = _number(_field(side, "state"))
            top = _number(_field(side, "top"))
            bottom = _number(_field(side, "bottom"))
            if state is None or top is None or bottom is None or top < bottom:
                continue
            state_code = abs(int(state))
            if state_code in _FVG_TERMINAL_STATES or state_code not in _FVG_STATE_LABELS:
                continue
            location = _zone_location(top, bottom, reference_price)
            if location is None:
                continue
            group, distance = location
            if group not in candidates:
                continue
            quality = _number(_field(side, "quality"))
            fill = _number(_field(side, "fill"))
            parts = [
                f"{TIMEFRAME_LABELS[timeframe]} {side_label} "
                f"{_price(bottom)}–{_price(top)} TL",
                _FVG_STATE_LABELS[state_code],
            ]
            if fill is not None:
                parts.append(f"%{max(0, min(100, round(fill * 100)))} dolu")
            # Quality is used only to choose the best exported zone; it is not
            # printed in the user-facing alert.
            candidates[group].append((quality, distance, " · ".join(parts)))

    lines = []
    for group, label in (("üst", "Üst"), ("alt", "Alt")):
        zones = candidates[group]
        if not zones:
            continue
        scored = [zone for zone in zones if zone[0] is not None]
        if scored:
            _, _, text = min(scored, key=lambda item: (-item[0], item[1]))
        else:
            _, _, text = min(zones, key=lambda item: item[1])
        lines.append(f"• {label}: {text}")
    return lines


_VOLUME_STATE_LABELS = {
    "PARTICIPATION_LOW": "katılım düşük",
    "PARTICIPATION_RISING": "katılım artıyor",
    "PARTICIPATION_ABNORMAL_VOLUME": "anormal hacim",
    "PARTICIPATION_ABNORMAL_CAPITAL": "anormal işlem değeri",
    "PARTICIPATION_ONE_BAR_SHOCK": "tek mumda olağandışı hareket",
    "PARTICIPATION_UP_CANDIDATE": "yukarı katılım adayı",
    "PARTICIPATION_DOWN_CANDIDATE": "aşağı katılım adayı",
    "PARTICIPATION_UP_CONFIRMED": "yukarı katılım teyitli",
    "PARTICIPATION_DOWN_CONFIRMED": "aşağı katılım teyitli",
    "PARTICIPATION_UP_PROTECTED": "yukarı katılım korunuyor",
    "PARTICIPATION_DOWN_PROTECTED": "aşağı katılım korunuyor",
    "PARTICIPATION_UP_WEAKENING": "yukarı katılım zayıflıyor",
    "PARTICIPATION_DOWN_WEAKENING": "aşağı katılım zayıflıyor",
    "PARTICIPATION_UP_ENDED": "yukarı katılım sona erdi",
    "PARTICIPATION_DOWN_ENDED": "aşağı katılım sona erdi",
    "PARTICIPATION_UPPER_ABSORPTION_CANDIDATE": "üst bölgede satış emilimi adayı",
    "PARTICIPATION_LOWER_ABSORPTION_CANDIDATE": "alt bölgede alış emilimi adayı",
    "PARTICIPATION_UPPER_ABSORPTION_CONFIRMED": "üst bölgede satış emilimi teyitli",
    "PARTICIPATION_LOWER_ABSORPTION_CONFIRMED": "alt bölgede alış emilimi teyitli",
    "PARTICIPATION_UPPER_ABSORPTION_INVALIDATED": "üst bölge emilim işareti geçersizleşti",
    "PARTICIPATION_LOWER_ABSORPTION_INVALIDATED": "alt bölge emilim işareti geçersizleşti",
    "PARTICIPATION_UP_BREAK_SUPPORTED": "yukarı kırılımda katılım desteği var",
    "PARTICIPATION_DOWN_BREAK_SUPPORTED": "aşağı kırılımda katılım desteği var",
    "PARTICIPATION_UP_BREAK_UNSUPPORTED": "yukarı kırılımda katılım desteği yok",
    "PARTICIPATION_DOWN_BREAK_UNSUPPORTED": "aşağı kırılımda katılım desteği yok",
    "PARTICIPATION_UP_BREAK_RECLAIMED": "yukarı kırılım seviyesi geri alındı",
    "PARTICIPATION_DOWN_BREAK_RECLAIMED": "aşağı kırılım seviyesi geri alındı",
    "PARTICIPATION_CONFLICT": "hacim/işlem değeri çelişkili",
}
_VOLUME_LEVEL_LABELS = {
    "VERY_LOW": "çok düşük",
    "LOW": "düşük",
    "NORMAL": "normal",
    "RISING": "yükselen",
    "HIGH": "yüksek",
    "ABNORMAL": "olağandışı",
}


def _format_volume(results_by_timeframe: Any) -> list[str]:
    lines = []
    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "volume_participation")
        export = _usable_export(result)
        if export is None:
            continue
        state = _token(_field(export, "state"))
        if state in {"", "PARTICIPATION_PENDING", "PARTICIPATION_VOLUME_UNAVAILABLE", "PARTICIPATION_NEUTRAL"}:
            state = ""
        findings = []
        if state:
            label = _VOLUME_STATE_LABELS.get(state)
            if label:
                findings.append(label)

        rvol = _number(_field(export, "rvol"))
        if rvol is not None and rvol > 0:
            findings.append(f"Son mum hacmi / 20 mumluk ortalama: {rvol:.2f}× (RVOL)".replace(".", ",", 1))
        relative_value = _number(_field(export, "relative_traded_value"))
        if relative_value is not None and relative_value > 0:
            findings.append(f"göreli işlem değeri {relative_value:.2f}×".replace(".", ",", 1))

        volume_level = _token(_field(export, "volume_level"))
        volume_label = _VOLUME_LEVEL_LABELS.get(volume_level)
        if volume_label and volume_level not in {"NORMAL"}:
            findings.append(f"hacim {volume_label}")
        capital_level = _token(_field(export, "capital_level"))
        capital_label = _VOLUME_LEVEL_LABELS.get(capital_level)
        if capital_label and capital_level not in {"NORMAL"}:
            findings.append(f"işlem değeri {capital_label}")

        absorption_stage = _token(_field(export, "absorption_stage"))
        absorption_side = _token(_field(export, "absorption_side"))
        if absorption_stage == "CONFIRMED" and absorption_side in {"UPPER", "LOWER"}:
            side_label = "üstte satış" if absorption_side == "UPPER" else "altta alış"
            level = _price(_field(export, "absorption_reference_level"))
            findings.append(f"{side_label} emilimi teyitli" + (f" {level}" if level else ""))

        break_stage = _token(_field(export, "break_stage"))
        break_direction = _direction(_field(export, "break_direction"))
        break_labels = {
            "SUPPORTED": "katılım desteği var",
            "PROTECTED": "katılım desteği korunuyor",
            "UNSUPPORTED": "katılım desteği yok",
            "RECLAIMED": "kırılım seviyesi geri alındı",
        }
        if break_stage in break_labels:
            break_text = break_labels[break_stage]
            if break_direction:
                break_text = f"{break_direction} yönde {break_text}"
            break_level = _price(_field(export, "break_level"))
            findings.append(break_text + (f" ({break_level} TL)" if break_level else ""))

        if findings:
            lines.append(f"• {TIMEFRAME_LABELS[timeframe]}: " + " · ".join(findings))
    return lines


def market_yapisi_hatali(results_by_timeframe: Any) -> bool:
    """MS (piyasa yapısı) motoru bu turda hata verdi mi? (`/durum` sayacı için)

    Kart bu bilgiyi basmaz (karar D); sayaç `/durum`da görünür.
    """
    return _market_structure_failed(results_by_timeframe)


def _market_structure_failed(results_by_timeframe: Any) -> bool:
    if not isinstance(results_by_timeframe, Mapping):
        return False
    for timeframe in TIMEFRAME_ORDER:
        result = _domain(results_by_timeframe, timeframe, "market_structure")
        if result is not None and not bool(_field(result, "skipped", False)) and _field(result, "error"):
            return True
    return False


# --- Kart (telefon) stili -------------------------------------------------
# Kurallar: tek satır = tek bilgi grubu, satır ≤ 283 px (telefonda sarmaz),
# bilgi kaybolursa satıra çıkartılır (kesilmez). Simgeler tofu riski olmayan
# geometrik karakterlerden seçildi.

def _kart_engel(results_by_timeframe: Any, reference: float | None,
                yon: int) -> list[str]:
    """Kırılımın ÖNÜNDEKİ ilk canlı OB/FVG bölgesi (tek satır).

    Neden kartta: alarm "neyi kırdı"yı söylüyordu ama "önünde ne var"ı
    söylemiyordu; oysa sıradaki engelin yeri, kırılımın ne kadar yol alabileceğini
    belirleyen tek sayı. Yön belirleyici: yukarı kırılımda üstteki bölge (direnç),
    aşağı kırılımda alttaki bölge (destek). Bölge yoksa satır da yoktur.
    """
    if reference is None or reference <= 0 or not yon:
        return []
    istenen = "üst" if yon > 0 else "alt"
    en_yakin: tuple[float, str] | None = None
    for timeframe in TIMEFRAME_ORDER:
        tf_label = TIMEFRAME_LABELS[timeframe]
        for alan, tip, yanlar in (
            ("order_block", "OB", (("bull", "boğa"), ("bear", "ayı"))),
            ("fvg", "FVG", (("bull_fvg", "boğa"), ("bear_fvg", "ayı"))),
        ):
            export = _usable_export(_domain(results_by_timeframe, timeframe, alan))
            if export is None:
                continue
            for anahtar, _yan in yanlar:
                yan = _field(export, anahtar)
                top = _number(_field(yan, "top"))
                bottom = _number(_field(yan, "bottom"))
                if top is None or bottom is None or top < bottom:
                    continue
                if tip == "FVG":
                    kod = _number(_field(yan, "state"))
                    if kod is None:
                        continue
                    kod = abs(int(kod))
                    if kod in _FVG_TERMINAL_STATES or kod not in _FVG_STATE_LABELS:
                        continue
                konum = _zone_location(top, bottom, reference)
                if konum is None:
                    continue
                grup, mesafe = konum
                if grup != istenen or mesafe <= 0:
                    continue
                seviye = bottom if istenen == "üst" else top
                ok = "▲" if istenen == "üst" else "▼"
                tur = "direnç" if istenen == "üst" else "destek"
                # 2026-10-23: "blok" (OB) ve işaretli yüzde (`−%0,8`)
                # okunmuyordu. Kısa ve düz: `▼ destek bölgesi 4s 70,40 (%0,8 uzak)`.
                marj = f"%{mesafe / reference * 100.0:.1f}".replace(".", ",")
                sade = _ZONE_SADE.get(tip, tip)
                metin = _sigdir([
                    f"{ok} {tur} {sade} {tf_label} {_price(seviye)} ({marj})",
                    f"{ok} {tur} {tf_label} {_price(seviye)} ({marj} uzak)",
                    f"{ok} {tur} {tf_label} {_price(seviye)}",
                ])
                if en_yakin is None or mesafe < en_yakin[0]:
                    en_yakin = (mesafe, metin)
    return [en_yakin[1]] if en_yakin else []


#: Metindeki "üst zaman dilimi". `main._UST_TF` (public görseli: 1 kare + üst TF)
#: ile AYNI eşleme: aynı alarmın metni ve görseli aynı üst TF'yi konuşur.
_UST_TF = {"1h": "4h", "2h": "4h", "4h": "1d"}


def _yapi_metni(satir: dict) -> str:
    """Bir yapı satırını kart cümlesine çevirir; ikisi de boşsa "" döner."""
    token_dis, token_ic = _token(satir["dis"]), _token(satir["ic"])
    dis = _STRUCTURE_SADE.get(token_dis, "")
    ic = _STRUCTURE_SADE.get(token_ic, "")
    if not dis and not ic:
        return ""
    kisa_dis = _STRUCTURE_SADE_KISA.get(token_dis, "")
    kisa_ic = _STRUCTURE_SADE_KISA.get(token_ic, "")
    etiket = f"◈ {satir['etiket']}"
    # Sade dil (2026-10-23, kullanıcı kararı): "4s yapı dış ve iç aşağı döndü"
    # iki jargonu arka arkaya koyuyordu ("yapı", "dış/iç"). Satır artık YÖNÜ
    # söyler, yapı ayrıntısı parantezde kalır:
    #   ◈ 4s yön aşağı (iç ve dış yapı)
    # Sığmazsa parantez kısalır, en sonda tamamen düşer (ölçü kaybolmaz).
    if dis and ic and token_dis == token_ic:
        # "döndü" nüansı korunur: yapı henüz döndüyse ("aşağı döndü") satırda
        # kalır, oturmuş yönde ("aşağı") parantez tam yazılır.
        dondu = dis != kisa_dis
        if dondu:
            adaylar = [f"{etiket} yön {dis} (iç, dış)",
                       f"{etiket} yön {dis}",
                       f"{etiket} yön {kisa_dis} (iç ve dış yapı)"]
        else:
            adaylar = [f"{etiket} yön {dis} (iç ve dış yapı)",
                       f"{etiket} yön {dis} (iç, dış)",
                       f"{etiket} yön {dis}",
                       f"{etiket} yön {kisa_dis}"]
        return _sigdir(adaylar)
    if dis and ic:
        # İki kapsam FARKLI yönde: "karışık" doğru sözcük (çelişki var).
        uzun = [f"dış {dis}", f"iç {ic}"]
        kisa = [f"dış {kisa_dis}" if kisa_dis else "", f"iç {kisa_ic}" if kisa_ic else ""]
        return _sigdir([f"{etiket} yön karışık (" + ", ".join(uzun) + ")",
                        f"{etiket} yön karışık (" + ", ".join(p for p in kisa if p) + ")"])
    # Tek kapsam biliniyor: "karışık" demek yanlış olurdu (çelişki yok, eksik
    # bilgi var). Kare başlığında `1g yön karışık (dış yukarı)` yazıyordu.
    tek = dis or ic
    kapsam = "dış" if dis else "iç"
    tek_kisa = kisa_dis if dis else kisa_ic
    return _sigdir([f"{etiket} yön {tek} ({kapsam} yapı)",
                    f"{etiket} yön {tek}",
                    f"{etiket} yön {tek_kisa}"])


def _kart_yapi_ozet(rows: list[dict], alarm_tf: str) -> list[str]:
    """Alarm TF'sinin yapı durumu tek satır: `◈ 1s yapı dış ↓, iç ↓`.

    Kartta (GÖRSEL-8) yapı bloğunun yalnız bu satırı kalır: olay seviyeleri
    `/tara`'da ve kârede duruyor, satır ise "kırılım yapıyla aynı yönde mi"
    sorusunu tek bakışta cevaplıyor.

    ÜST TF YEDEĞİ (2026-10-22): alarm TF'sinin yapı satırı yoksa (MS motoru o
    TF'de olay üretmedi/atladı) satır tamamen düşüyordu — public bültende
    yapı bloğu boş kalıyordu. Artık sırayla: alarm TF'si → public görselindeki
    üst TF → kalan üst TF'ler. Satır KENDİ etiketiyle yazılır (`◈ 4s yapı …`),
    yani alarm TF'siymiş gibi gösterilmez.
    """
    mevcut = {str(s.get("timeframe") or "").lower(): s for s in rows}
    sira = [str(alarm_tf or "").lower()]
    ust = _UST_TF.get(sira[0])
    if ust:
        sira.append(ust)
    try:
        baslangic = TIMEFRAME_ORDER.index(sira[0]) + 1
    except ValueError:
        baslangic = 0
    sira += [tf for tf in TIMEFRAME_ORDER[baslangic:] if tf not in sira]
    for tf in sira:
        satir = mevcut.get(tf)
        if satir is None:
            continue
        metin = _yapi_metni(satir)
        if metin:
            return [metin]
    return []


def _kart_zones(results_by_timeframe: Any, reference: float | None) -> dict[str, list[str]]:
    """OB + FVG tek listede, tarafa göre: ▲ üst (engel) / ▼ alt (destek).

    Döner: {"ust": [...], "alt": [...]} — satırların kendisi ▲/▼ ile başlar.

    Eskiden OB ve FVG ayrı bölümlerde kendi başına "en yakın/en kaliteli" bölgeyi
    seçiyordu; aynı bölge iki başlıkta iki kez görünebiliyordu. Kart taraf
    (üst/alt) temel alır ve mesafeye göre sıralar — kullanıcı hangi bölgenin
    gerçekten yakın olduğunu tek bakışta görür.
    """
    adaylar: dict[str, list[tuple[float, str]]] = {"içinde": [], "üst": [], "alt": []}
    if reference is None or reference <= 0:
        return {"ust": [], "alt": []}

    for timeframe in TIMEFRAME_ORDER:
        tf_label = TIMEFRAME_LABELS[timeframe]
        for alan, tip, yanlar in (
            ("order_block", "OB", (("bull", "boğa"), ("bear", "ayı"))),
            ("fvg", "FVG", (("bull_fvg", "boğa"), ("bear_fvg", "ayı"))),
        ):
            export = _usable_export(_domain(results_by_timeframe, timeframe, alan))
            if export is None:
                continue
            for yan_anahtar, yan_etiket in yanlar:
                yan = _field(export, yan_anahtar)
                top = _number(_field(yan, "top"))
                bottom = _number(_field(yan, "bottom"))
                if top is None or bottom is None or top < bottom:
                    continue
                durumlar: list[str] = []
                if tip == "FVG":
                    kod = _number(_field(yan, "state"))
                    if kod is None:
                        continue
                    kod = abs(int(kod))
                    if kod in _FVG_TERMINAL_STATES or kod not in _FVG_STATE_LABELS:
                        continue
                    durumlar.append(_FVG_STATE_LABELS[kod])
                else:
                    etiket = _OB_STATE_LABELS.get(abs(int(_number(_field(yan, "state")) or 0)))
                    if etiket:
                        durumlar.append(etiket)
                dolus = _number(_field(yan, "fill"))
                if dolus is not None:
                    durumlar.append(f"%{max(0, min(100, round(dolus * 100)))} dolu")
                konum = _zone_location(top, bottom, reference)
                if konum is None:
                    continue
                grup, mesafe = konum
                ok = {"üst": "▲", "alt": "▼", "içinde": "◉"}[grup]
                if grup == "içinde":
                    # Fiyat bandın içinde: mesafe yok, ama "şu an bu bölgedeyiz"
                    # bilgisi üst/alt listesinden daha karar vericidir → önce o basılır.
                    durumlar.append("fiyat bandın içinde")
                else:
                    marj = mesafe / reference * 100.0
                    isaret = "+" if grup == "üst" else "−"
                    durumlar.append(f"{isaret}%{marj:.1f}".replace(".", ","))
                baslik = (
                    f"{ok} {_ZONE_SADE.get(tip, tip)} {tf_label} {yan_etiket}"
                    f" · {_price(bottom)}–{_price(top)}"
                )
                adaylar[grup].append((mesafe, baslik, " · ".join(durumlar)))

    kisa_ad = {"içinde": "içinde", "üst": "ust", "alt": "alt"}
    bölgeler: dict[str, list[str]] = {"içinde": [], "ust": [], "alt": []}
    for grup, satirlar in adaylar.items():
        hedef = kisa_ad[grup]
        for mesafe, baslik, künye in sorted(satirlar, key=lambda x: x[0])[:2]:
            bölgeler[hedef].append(baslik)
            if künye:
                bölgeler[hedef].append(f"   {künye}")
    return bölgeler


# GÖRSEL-7 kısa sözlükler: kart satırı `katılım 1s destekliyor` gibi TEK yargı taşır.
# Eski biçim TF başına 3 satır basıyordu (yargı · sayılar · katkı) ve kart 11 satıra
# çıkıyordu; kâre şeritte RVOL çubuklarını zaten çiziyor, metin YORUMU taşır.
_KART_BREAK_KISA = {
    "SUPPORTED": "destekliyor",
    "PROTECTED": "destek korunuyor",
    "UNSUPPORTED": "destek yok",
    "RECLAIMED": "kırılım geri alındı",
}
_KART_STATE_KISA = {
    "PARTICIPATION_LOW": "düşük",
    "PARTICIPATION_RISING": "artıyor",
    "PARTICIPATION_ABNORMAL_VOLUME": "anormal hacim",
    "PARTICIPATION_ABNORMAL_CAPITAL": "anormal işlem değeri",
    "PARTICIPATION_ONE_BAR_SHOCK": "tek mumda şok",
    "PARTICIPATION_UP_CONFIRMED": "yukarı teyitli",
    "PARTICIPATION_DOWN_CONFIRMED": "aşağı teyitli",
    "PARTICIPATION_UP_PROTECTED": "yukarı korunuyor",
    "PARTICIPATION_DOWN_PROTECTED": "aşağı korunuyor",
    "PARTICIPATION_UP_WEAKENING": "yukarı zayıflıyor",
    "PARTICIPATION_DOWN_WEAKENING": "aşağı zayıflıyor",
    "PARTICIPATION_UP_CANDIDATE": "yukarı aday",
    "PARTICIPATION_DOWN_CANDIDATE": "aşağı aday",
    "PARTICIPATION_UPPER_ABSORPTION_CONFIRMED": "üstte satış emilimi",
    "PARTICIPATION_LOWER_ABSORPTION_CONFIRMED": "altta alış emilimi",
    "PARTICIPATION_UPPER_ABSORPTION_CANDIDATE": "üstte emilim adayı",
    "PARTICIPATION_LOWER_ABSORPTION_CANDIDATE": "altta emilim adayı",
    "PARTICIPATION_UPPER_ABSORPTION_INVALIDATED": "üst emilim işareti düştü",
    "PARTICIPATION_LOWER_ABSORPTION_INVALIDATED": "alt emilim işareti düştü",
    "PARTICIPATION_CONFLICT": "hacim/işlem çelişkili",
}


def _kart_oran(deger: Any) -> str:
    """RVOL sayısı kart dilinde: `0,42` (nokta değil virgül)."""
    sayi_deger = _number(deger)
    if sayi_deger is None or sayi_deger <= 0:
        return ""
    return f"{sayi_deger:.2f}".replace(".", ",")


def _hacim_yok_nedeni(sembol: str) -> str:
    """Hacim toplanamıyorsa NEDENİ (kartta "veri yok" demek yetersiz).

    Sağlayıcı endekslerde hacim sütununu 0/boş veriyor; makro sembollerde
    (ons altın/gümüş, kur, brent) hacim farklı birimde ve kapanış hizasızdır.
    Kullanıcı kararı (2026-10-22): satır silinmesin, açıklama olsun — "bilgi
    yok" ile "bilgi anlamsız" farklı şeylerdir.

    Bütçe notu: tek satırda "endeks hacmi toplanmıyor · yön fiyattan okunur"
    466 px ölçüldü (eşik 262,85) ve `_satir` bölüyordu. Bu yüzden açıklama
    İKİ kısa satıra ayrıldı: `hacim yok (endeks)` + `yön fiyattan okunur`.
    """
    import config as _config
    tur = _config.sembol_turu(sembol)
    if tur in ("endeks", "makro"):
        # Yalnız "yok (endeks)"; "hacim" sözcüğünü çağıran satır ekler
        # (`hacim 4s yok (endeks)` — 2026-10-23 düzeni).
        return f"yok ({tur})"
    return ""


def _hacim_yok_notu(sembol: str) -> str:
    """Sembol sınıfı hacim vermiyorsa tek satırlık yön notu; yoksa boş."""
    import config as _config
    return "yön fiyattan okunur" if _config.sembol_turu(sembol) in ("endeks", "makro") else ""


def _kart_volume(results_by_timeframe: Any, alarm_tf: str | None,
                 sembol: str = "") -> list[str]:
    """Katılım bölümü: satır = `katılım {tf} {kısa yargı}`, en fazla 2 satır.

    Neden bu biçim (GÖRSEL-7 ölçümü): eski hâl TF başına 3 satır ve 4 TF için
    11 satır üretiyordu; kartın %40'ı girintili devam satırıydı. Kârede hacim
    şeridi çizili olduğu için metin yalnız YARGIYI taşır:

      1. satır: alarm TF'sinin yargısı (kırılımın kendi zaman diliminde katılım
         var mı, korunuyor mu, yok mu) — veri yoksa bu da yazılır (sessiz geçilmez).
      2. satır: diğer TF'lerden EN DİKKAT ÇEKİCİ olanı — katılım bitti ise
         `0,52 ile bitti`, değilse RVOL'ü en düşük olan `0,42 zayıf`.
    """
    kayitlar: list[dict] = []
    for timeframe in TIMEFRAME_ORDER:
        tf_label = TIMEFRAME_LABELS[timeframe]
        result = _domain(results_by_timeframe, timeframe, "volume_participation")
        export = _usable_export(result)
        if export is None:
            if timeframe == str(alarm_tf or "").lower():
                hata = _token(_field(result, "error")) if result is not None else ""
                kayitlar.append({"tf": timeframe, "etiket": tf_label, "yargi": "",
                                 "rvol": "", "bitti": False,
                                 "bos": ("analiz yapılamadı" if hata else
                                         ("hacim " + _hacim_yok_nedeni(sembol)
                                          if _hacim_yok_nedeni(sembol) else "veri yok")),
                                 "hata": bool(hata)})
            continue
        durum = _token(_field(export, "state"))
        if durum in {"PARTICIPATION_PENDING", "PARTICIPATION_VOLUME_UNAVAILABLE",
                     "PARTICIPATION_NEUTRAL"}:
            durum = ""
        yargi = _KART_BREAK_KISA.get(_token(_field(export, "break_stage")), "")
        if not yargi:
            yargi = _KART_STATE_KISA.get(durum, "")
        kayitlar.append({
            "tf": timeframe,
            "etiket": tf_label,
            "yargi": yargi,
            "rvol": _kart_oran(_field(export, "rvol")),
            "bitti": durum.endswith("_ENDED"),
            "bos": "",
            "hata": False,
        })

    if not kayitlar:
        return []
    alarm_key = str(alarm_tf or "").lower()
    birincil = next((k for k in kayitlar if k["tf"] == alarm_key), kayitlar[0])
    satirlar: list[str] = []
    # 2026-10-23 (kullanıcı): "katılım" yerine "hacim"; hisse verisi yoksa satır
    # HİÇ basılmaz (bilgi yokluğu kart yerini hak etmiyor). Endeks/makro istisnası
    # duruyor: orada "veri yok" değil "bu sembolde hacim alanı yok" denir —
    # sebep bilgisi kullanıcı kararıyla (2026-10-22) korunuyor.
    if birincil["yargi"]:
        oran_eki = f" ({birincil['rvol']}×)" if birincil["rvol"] else ""
        satirlar.append(f"hacim: {birincil['etiket']} {birincil['yargi']}{oran_eki}")
    elif birincil["rvol"]:
        satirlar.append(f"hacim: {birincil['etiket']} normalin {birincil['rvol']} katı")
    elif _hacim_yok_nedeni(sembol) and not birincil["hata"]:
        satirlar.append(f"hacim: {birincil['etiket']} {_hacim_yok_nedeni(sembol)}")
        not_metni = _hacim_yok_notu(sembol)
        if not_metni:
            satirlar.append(not_metni)

    digerleri = [k for k in kayitlar if k is not birincil]
    bitenler = [k for k in digerleri if k["bitti"] and k["rvol"]]
    if bitenler:
        k = bitenler[0]
        satirlar.append(f"hacim: {k['etiket']} tükendi ({k['rvol']}×)")
    else:
        zayiflar = [k for k in digerleri if k["rvol"] and _number(str(k["rvol"]).replace(",", ".")) is not None
                    and float(str(k["rvol"]).replace(",", ".")) < 0.6]
        if zayiflar:
            k = min(zayiflar, key=lambda x: float(str(x["rvol"]).replace(",", ".")))
            satirlar.append(f"hacim: {k['etiket']} düşük ({k['rvol']}×)")
    return satirlar

# --- ampirik referans (arşiv ölçümü) ---------------------------------------
# Kart "/tara" gibi yüzeylerde "şu an ne oldu" bilgisinin yanına, aynı kurulumun
# arşivde nasıl sonuçlandığını koyar. Sayılar `ampirik_referans` tablolarından
# gelir; burada yalnız motor export'undan hangi özelliklerin okunacağı belirlenir.

def _alarm_tf_zone(results_by_timeframe: Any, alarm_tf: str,
                   reference: float | None) -> tuple[str, float, float, bool] | None:
    """Alarm TF'sindeki en yakın OB/FVG bölgesi: (aile, üst, alt, fiyat içinde mi).

    Ölçüm için gereken tek şey bölgenin geometrisidir; skor/kalite kullanılmaz
    (aday seçimi değil, olayın kendi bölgesi ölçülür).
    """
    if reference is None or reference <= 0:
        return None
    en_iyi: tuple[float, str, float, float, bool] | None = None
    for alan, aile, yanlar in (
        ("order_block", "OB", ("bull", "bear")),
        ("fvg", "FVG", ("bull_fvg", "bear_fvg")),
    ):
        export = _usable_export(_domain(results_by_timeframe, alarm_tf, alan))
        if export is None:
            continue
        for anahtar in yanlar:
            yan = _field(export, anahtar)
            top = _number(_field(yan, "top"))
            bottom = _number(_field(yan, "bottom"))
            if top is None or bottom is None or top < bottom:
                continue
            icinde = bottom <= reference <= top
            mesafe = 0.0 if icinde else min(abs(top - reference),
                                           abs(bottom - reference))
            if en_iyi is None or mesafe < en_iyi[0]:
                en_iyi = (mesafe, aile, top, bottom, icinde)
    if en_iyi is None:
        return None
    _, aile, top, bottom, icinde = en_iyi
    return aile, top, bottom, icinde


def _fiyat_zone_icinde(results_by_timeframe: Any, reference: float | None) -> bool | None:
    """Fiyat herhangi bir TF'de canlı OB/FVG bölgesinin içinde mi (FRM-19 tanımı)."""
    if reference is None or reference <= 0:
        return None
    bulundu = False
    for timeframe in TIMEFRAME_ORDER:
        zone = _alarm_tf_zone(results_by_timeframe, timeframe, reference)
        if zone is None:
            continue
        bulundu = True
        if zone[3]:
            return True
    return False if bulundu else None


def _alarm_tf_ms_olayi(results_by_timeframe: Any, alarm_tf: str):
    """Alarm TF'sindeki en güncel teyitli BOS/CHoCH: (kapsam, tip, yön)."""
    export = _usable_export(_domain(results_by_timeframe, alarm_tf, "market_structure"))
    if export is None:
        return None, None, None
    en_son = None
    en_son_bar: float | None = None
    for event in _event_rows(export):
        tip = _token(_field(event, "event_type"))
        if tip not in {"EVENT_BOS", "BOS", "EVENT_CHOCH", "CHOCH"}:
            continue
        if _token(_field(event, "confirmation_status")) != "CONFIRMED":
            continue
        if _token(_field(event, "validity")) == "FAILED":
            continue
        if _token(_field(event, "relevance")) in {"SUPERSEDED", "HISTORICAL"}:
            continue
        if not bool(_field(event, "is_active", True)):
            continue
        bar = _number(_field(event, "event_bar"))
        if en_son is None or (bar is not None and (en_son_bar is None or bar >= en_son_bar)):
            en_son = event
            en_son_bar = bar
    if en_son is None:
        return None, None, None
    kapsam = _token(_field(en_son, "scope")) or "EXTERNAL"
    tip = "CHOCH" if "CHOCH" in _token(_field(en_son, "event_type")) else "BOS"
    yon = "UP" if (_number(_field(en_son, "direction")) or 0) > 0 else "DOWN"
    return kapsam, tip, yon


def _alarm_tf_rvol(results_by_timeframe: Any, alarm_tf: str) -> float | None:
    export = _usable_export(_domain(results_by_timeframe, alarm_tf, "volume_participation"))
    if export is None:
        return None
    return _number(_field(export, "rvol"))


def _korunan_seviyeler(results_by_timeframe: Any, alarm_tf: str) -> tuple[float | None, float | None]:
    """Alarm TF'sinin korunan tepe/dibi (PH/PL) — FRM-20 uyum ölçümü için."""
    export = _usable_export(_domain(results_by_timeframe, alarm_tf, "market_structure"))
    if export is None:
        return None, None
    return (_number(_field(export, "external_protected_high")),
            _number(_field(export, "external_protected_low")))


def olcum_bolumu(results_by_timeframe: Any, reference_price: Any = None, *,
                 alarm_tf: str | None = None, atr: float | None = None,
                 yon: int = 0, retest_seen: bool | None = None,
                 azami: int = 2, aile: str = "",
                 beklenti: bool = False) -> list[str]:
    """Kuruluma koşullu ölçüm satırları (`ampirik_referans`).

    Veri yoksa veya tabloda o kesit yoksa satır üretilmez; uydurma yapılmaz.

    `beklenti=True` (varsayılan KAPALI): ölçüm satırlarının ÖNÜNE beklenti
    hükmü eklenir (`◇ beklenti: devam` + sayaç). Hüküm varsa en çok 1 ölçüm
    satırı kalır — kart 3 satırı aşmaz (tasarım: TAHMIN_KATMANI.md §8).
    Yön kanıtı yoksa beklenti satırı **hiç** basılmaz.
    """
    import ampirik_referans as ar

    tf = str(alarm_tf or "").lower()
    if not tf:
        return []
    reference = _number(reference_price)
    kapsam, tip, ms_yon = _alarm_tf_ms_olayi(results_by_timeframe, tf)
    try:
        yon_sayi = int(yon or 0)
    except (TypeError, ValueError):
        yon_sayi = 0
    zone = _alarm_tf_zone(results_by_timeframe, tf, reference)
    ph, pl = _korunan_seviyeler(results_by_timeframe, tf)
    kurulum = ar.Kurulum(
        tf=tf,
        yon=yon_sayi if yon_sayi else (1 if ms_yon == "UP" else -1 if ms_yon == "DOWN" else 0),
        atr=atr,
        bolge_top=zone[1] if zone else None,
        bolge_alt=zone[2] if zone else None,
        rvol=_alarm_tf_rvol(results_by_timeframe, tf),
        retest_seen=retest_seen,
        zone_icinde=_fiyat_zone_icinde(results_by_timeframe, reference),
        ph=ph,
        pl=pl,
        break_price=reference,
        ms_kapsam=kapsam,
        ms_tip=tip,
        ms_yon=ms_yon,
        aile=str(aile or ""),
    )
    if not beklenti:
        return ar.olcum_satirlari(kurulum, azami=azami)
    hukum_satirlari = ar.beklenti_satirlari(kurulum)
    if not hukum_satirlari:
        # Yön kanıtı yok: hüküm satırı yok, ölçümler normal akışta.
        return ar.olcum_satirlari(kurulum, azami=azami)
    kalan = max(0, int(azami) - len(hukum_satirlari))
    return hukum_satirlari + ar.olcum_satirlari(kurulum, azami=kalan)


def domain_bolumleri(results_by_timeframe: Any, reference_price: Any = None, *,
                     stil: str = "klasik", alarm_tf: str | None = None,
                     yalniz_tf: bool = False, olcum: bool = False,
                     atr: float | None = None, yon: int = 0,
                     retest_seen: bool | None = None,
                     azami_olcum: int = 2, aile: str = "",
                     beklenti: bool = False, sembol: str = "") -> dict:
    """Domain bağlamını bölüm bölüm döndürür (kart biçimleyicisi için).

    `stil="kart"`: `yapi`/`ust`/`alt`/`hacim` anahtarlarında hazır satırlar.
    `stil="klasik"`: eski başlıksız satırlar (`ob`/`fvg` ayrı), mesaj metni
    `format_domain_context` ile aynı kalır.
    `yalniz_tf=True` (GÖRSEL-4): yalnız `alarm_tf` bölümleri üretilir. Kullanıcı
    kararı: "geçersizleşince sadece formasyon bilgisi gelsin" — teyitli kırılım
    banda geri döndüğünde 4 zaman diliminin yapı/bölge/hacim dökümü gereksizdi.

    `olcum=True`: `olcum` bölümünde arşiv ölçümü satırları eklenir
    (`ampirik_referans`). Varsayılan kapalıdır: mevcut çağıranların metni
    bayt bayt aynı kalır; ölçüm satırını isteyen yüzey açıkça ister.
    """
    reference = _number(reference_price)
    if yalniz_tf and alarm_tf:
        hedef = str(alarm_tf).lower()
        if isinstance(results_by_timeframe, dict):
            results_by_timeframe = {k: v for k, v in results_by_timeframe.items()
                                    if str(k).lower() == hedef}
    satirlar = _market_structure_rows(results_by_timeframe)
    hata = ""
    if _market_structure_failed(results_by_timeframe):
        hata = "⚠️ Piyasa yapısı analizi tamamlanamadı"
    # Bölüm anahtarları ASCII: kart biçimleyicisi bunları sözlük anahtarı olarak
    # okur (mesaj metnindeki Türkçe karakterlerden bağımsız kalsın).
    bolumler: dict[str, list[str]] = {"yapi": [], "ob": [], "fvg": [], "hacim": [],
                                      "içinde": [], "ust": [], "alt": [], "olcum": [],
                                      "engel": [], "yapi_ozet": [], "uyari": []}
    if stil == "kart":
        bolumler["yapi"] = _kart_market_structure(satirlar, str(alarm_tf or "").lower())
        bolumler["yapi_ozet"] = _kart_yapi_ozet(satirlar, str(alarm_tf or "").lower())
        bolumler["engel"] = _kart_engel(results_by_timeframe, reference, int(yon or 0))
        bolumler.update(_kart_zones(results_by_timeframe, reference))
        bolumler["hacim"] = _kart_volume(results_by_timeframe, str(alarm_tf or "").lower(),
                                         sembol=sembol)
        if hata:
            # MS (piyasa yapısı) motoru hata verdiğinde kart UYARI BASMAZ
            # (kullanıcı kararı 2026-10-22, karar D): alarm kartı karar belgesidir,
            # altyapı arıza notu oraya girmez — tek yeri `/durum`. Bilgi yine
            # taşınır (`uyari` anahtarı); kart biçimleyicisi bu anahtarı okumaz.
            bolumler["uyari"].append(hata)
        if olcum:
            bolumler["olcum"] = olcum_bolumu(
                results_by_timeframe, reference, alarm_tf=alarm_tf, atr=atr,
                yon=yon, retest_seen=retest_seen, azami=azami_olcum, aile=aile,
                beklenti=beklenti,
            )
        return {k: v for k, v in bolumler.items() if v}
    bolumler["yapi"] = _format_market_structure(satirlar)
    if hata:
        bolumler["yapi"].append(hata)
    bolumler["ob"] = _format_order_blocks(results_by_timeframe, reference)
    bolumler["fvg"] = _format_fvgs(results_by_timeframe, reference)
    bolumler["hacim"] = _format_volume(results_by_timeframe)
    if olcum:
        bolumler["olcum"] = olcum_bolumu(
            results_by_timeframe, reference, alarm_tf=alarm_tf, atr=atr,
            yon=yon, retest_seen=retest_seen, azami=azami_olcum, aile=aile,
            beklenti=beklenti,
        )
    return {k: v for k, v in bolumler.items() if v}


# --- karşı delil (tek satır) -----------------------------------------------
# Kart, "lehine ne var" değil "aleyhine ne var" bilgisini de taşır: kullanıcı bir
# teyitli kırılımda hangi kanalların ters olduğunu tek satırda görsün. Yalnız
# mevcut export'lardan üretilir; veri yoksa madde de yoktur (uydurma yok).
def karsi_deliller(results_by_timeframe: Any, alarm_tf: Any = None, break_dir: Any = None,
                   mtf_destek: Any = None, retest_seen: Any = None) -> list[str]:
    try:
        yon = int(break_dir or 0)
    except (TypeError, ValueError):
        yon = 0
    tf = str(alarm_tf or "").lower()
    bulgular: list[str] = []
    rows = {row["timeframe"]: row for row in _market_structure_rows(results_by_timeframe)}
    satir = rows.get(tf)
    if satir is not None and yon:
        # Karşı delil kartın "ters işaret" satırıdır; ok yerine sözcük yazılır
        # ("iç yapı ↓geçiş" → "iç yapı aşağı döndü"). Yön kıyası yine token
        # üzerinden yapılır, metin karşılaştırmasına bağlı değildir.
        ters = _STRUCTURE_SADE.get(_token(satir["ic"]), "")
        token_ic = _token(satir["ic"])
        if ters and token_ic in {"STATE_BEARISH", "STATE_TRANSITION_DOWN"} and yon > 0:
            bulgular.append(f"iç yapı {ters}")
        elif ters and token_ic in {"STATE_BULLISH", "STATE_TRANSITION_UP"} and yon < 0:
            bulgular.append(f"iç yapı {ters}")
        dis_token = _token(satir["dis"])
        dis = {"STATE_BEARISH": "aşağı", "STATE_BULLISH": "yukarı"}.get(dis_token, "")
        if dis and ((dis_token == "STATE_BEARISH" and yon > 0)
                    or (dis_token == "STATE_BULLISH" and yon < 0)):
            bulgular.append(f"dış yapı {dis}")
    export = _usable_export(_domain(results_by_timeframe, tf, "volume_participation")) if tf else None
    if export is None:
        # Alarm TF'sinde veri yoksa kartta "▤ {tf}: hacim verisi bekleniyor" zaten
        # yazılıyor; burada tekrarlamak yerine boş bırak.
        pass
    else:
        asama = _token(_field(export, "break_stage"))
        if asama == "UNSUPPORTED":
            bulgular.append("hacim desteği yok")
        elif asama == "RECLAIMED":
            bulgular.append("kırılım seviyesi geri alındı")
        elif not _VOLUME_STATE_LABELS.get(_token(_field(export, "state")), ""):
            bulgular.append("hacim teyidi yok")
    # `mtf_destek` ve `retest_seen` bilinçli olarak karşı delil sayılmaz: kartta
    # "▪ MTF: … onayı yok" ve "▪ … retest yok" satırları zaten basılıyor. Aynı
    # bilgiyi iki kez yazmak 25 Eyl biçiminin asıl şişkinliğiydi (yer değil, dikkat
    # kaybı). Parametreler imza uyumu için duruyor.
    return bulgular[:3]


def format_domain_context(results_by_timeframe: Any, reference_price: Any = None, *,
                          stil: str = "klasik", alarm_tf: str | None = None,
                          yalniz_tf: bool = False, olcum: bool = False,
                          atr: float | None = None, yon: int = 0,
                          retest_seen: bool | None = None,
                          azami_olcum: int = 2) -> str:
    """Render concise, read-only context from fresh domain-engine exports.

    Candidate scores are selection-only. Missing/skipped results are omitted;
    a real Market Structure execution error is explicitly identified instead of
    being made to look like a successful analysis with no findings.

    `stil="kart"` kompakt telefon kartını (alarm TF odaklı) üretir; varsayılan
    davranış (klasik) önceki biçimlerle birebir aynıdır.
    """
    bolumler = domain_bolumleri(results_by_timeframe, reference_price,
                                stil=stil, alarm_tf=alarm_tf, yalniz_tf=yalniz_tf,
                                olcum=olcum, atr=atr, yon=yon,
                                retest_seen=retest_seen, azami_olcum=azami_olcum)
    if stil == "kart":
        parcalar = []
        if bolumler.get("yapi"):
            parcalar.append("\n".join(bolumler["yapi"]))
        bolge = [*bolumler.get("ust", []), *bolumler.get("alt", [])]
        if bolge:
            parcalar.append("\n".join(bolge))
        if bolumler.get("hacim"):
            parcalar.append("\n".join(bolumler["hacim"]))
        if bolumler.get("olcum"):
            parcalar.append("\n".join(bolumler["olcum"]))
        return "\n\n".join(parcalar)
    bölümler = []
    for baslik, anahtar in (
        ("🏗 Piyasa Yapısı", "yapi"),
        ("🧱 Order Block (OB)", "ob"),
        ("🟪 Fair Value Gap (FVG)", "fvg"),
        ("📊 Hacim / Katılım", "hacim"),
        ("◇ Arşiv Ölçümü", "olcum"),
    ):
        satirlar = bolumler.get(anahtar) or []
        if satirlar:
            bölümler.append(baslik + "\n" + "\n".join(satirlar))
    return "\n\n".join(bölümler)
