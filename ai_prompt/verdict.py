"""Kullanıcının görmeyeceği gizli `[AI_SONUC ...]` filtre bloğu kuralı ve ayıklayıcı.

Amaç: AI yorumlarını Telegram'a açmadan önce (gölge / shadow test) modelin
5 çekirdek filtredeki yapılandırılmış kararını yanıtın sonundaki `[AI_SONUC ...]`
bloğundan güvenle çekmek ve kullanıcıya gidecek metinden HER KOŞULDA tamamen
temizlemek (malformed olsa bile sızıntıyı önlemek).
"""
from __future__ import annotations

import re
from typing import Any

from .commentary import validate_ai_commentary

HIDDEN_VERDICT_TAG = "AI_SONUC"

VERDICT_SCHEMA: dict[str, tuple[str, ...]] = {
    "egilim": ("yukari", "asagi", "kararsiz"),
    "guc": ("dusuk", "orta", "yuksek"),
    "mtf_uyum": ("uyumlu", "karma", "celiskili"),
    "risk": ("dusuk", "orta", "yuksek"),
    "yayin_degeri": ("gonder", "izle", "pas"),
}

VERDICT_FIELDS: tuple[str, ...] = tuple(VERDICT_SCHEMA.keys())

HIDDEN_VERDICT_INSTRUCTION = (
    "GİZLİ SONUÇ (sistem kaydı; kullanıcı görmez)\n"
    "- Yorumun EN SONUNA tek satır ekle, her alandan tek değer seç, başka metin yazma:\n"
    "  [AI_SONUC egilim=yukari|asagi|kararsiz | guc=dusuk|orta|yuksek | "
    "mtf_uyum=uyumlu|karma|celiskili | risk=dusuk|orta|yuksek | yayin_degeri=gonder|izle|pas]\n"
    "- Metindeki görüşünle tutarlı ol; eksik veri veya güçlü çelişkide `yayin_degeri=gonder` yazma."
)

# Fenced or plain `[AI_SONUC ...]` / `[SONUC ...]` / `[SONUÇ ...]` blocks.
_FENCED_VERDICT_RE = re.compile(
    r"(?is)```[a-z0-9_-]*\s*\n\s*(\[\s*(?:ai[_\s-]*)?sonu[cç]\b[^\]]*\])\s*\n\s*```",
)
_PLAIN_VERDICT_RE = re.compile(
    r"(?is)\[\s*(?:ai[_\s-]*)?sonu[cç]\b([^\]]*)\]",
)
_PAIR_RE = re.compile(r"([a-zA-ZçğıöşüÇĞİÖŞÜ_]+)\s*[:=]\s*([^\s|;,\]\"']+)")

_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "İ": "i", "I": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
})

_KEY_ALIASES = {
    "egilim": "egilim",
    "yon": "egilim",
    "guc": "guc",
    "guven": "guc",
    "mtf_uyum": "mtf_uyum",
    "mtf": "mtf_uyum",
    "risk": "risk",
    "yayin_degeri": "yayin_degeri",
    "yayin": "yayin_degeri",
    "alarm_degeri": "yayin_degeri",
}

_FATAL_TELEGRAM_WARNINGS = frozenset({
    "tablo_iceriyor",
    "genel_yatirim_uyarisi",
    "yasak_tavsiye_veya_kesin_tahmin",
    "ic_jargon_veya_ham_enum",
})


def _norm_token(value: str) -> str:
    cleaned = value.strip().strip("\"'`").translate(_TR_MAP).lower()
    return re.sub(r"[\s-]+", "_", cleaned)


def append_hidden_verdict_instruction(prompt_text: str) -> str:
    """Mevcut kopyala-yapıştır veya API promptunun sonuna gizli `[AI_SONUC ...]` kuralını ekler."""
    base = str(prompt_text or "").rstrip()
    if HIDDEN_VERDICT_TAG in base:
        return base + "\n"
    return f"{base}\n\n{HIDDEN_VERDICT_INSTRUCTION}\n"


def strip_hidden_verdict(text: str) -> tuple[str, str | None]:
    """Gizli `[AI_SONUC ...]` bloğunu metinden tamamen temizler.

    Dönen `(temiz_metin, son_ham_blok)`:
    - Kullanıcıya gösterilecek metinde hiçbir `[AI_SONUC ...]` / `[SONUC ...]` bloğu kalmaz.
    - Birden fazla blok varsa sonuncu ham blok döndürülür, tamamı metinden silinir.
    """
    src = str(text or "")
    last_raw: str | None = None

    def _capture_fenced(match: re.Match[str]) -> str:
        nonlocal last_raw
        last_raw = match.group(1).strip()
        return ""

    cleaned = _FENCED_VERDICT_RE.sub(_capture_fenced, src)

    def _capture_plain(match: re.Match[str]) -> str:
        nonlocal last_raw
        last_raw = match.group(0).strip()
        return ""

    cleaned = _PLAIN_VERDICT_RE.sub(_capture_plain, cleaned)
    # Clean trailing whitespace and redundant blank lines left after stripping.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, last_raw


def parse_verdict_block(raw_block: str | None) -> tuple[dict[str, str] | None, bool, list[str]]:
    """Ham `[AI_SONUC ...]` bloğunu çekirdek 5 filtre şemasına göre ayrıştır ve doğrula."""
    if not raw_block:
        return None, False, ["gizli_blok_yok"]
    match = _PLAIN_VERDICT_RE.search(raw_block)
    if not match:
        return None, False, ["gizli_blok_bicim_hatali"]
    body = match.group(1).strip().lstrip(":").strip()

    parsed_raw: dict[str, str] = {}
    errors: list[str] = []
    for raw_k, raw_v in _PAIR_RE.findall(body):
        key_norm = _norm_token(raw_k)
        canonical_key = _KEY_ALIASES.get(key_norm)
        if canonical_key is None:
            errors.append(f"tanimsiz_alan:{key_norm}")
            continue
        parsed_raw[canonical_key] = _norm_token(raw_v)

    verdict: dict[str, str] = {}
    for field in VERDICT_FIELDS:
        if field not in parsed_raw:
            errors.append(f"eksik:{field}")
            continue
        val = parsed_raw[field]
        if val not in VERDICT_SCHEMA[field]:
            errors.append(f"gecersiz:{field}={val}")
            continue
        verdict[field] = val

    valid = not errors and len(verdict) == len(VERDICT_FIELDS)
    return (verdict if verdict else None), valid, errors


def parse_ai_response(
    raw_text: str,
    *,
    require_verdict: bool = False,
    min_words: int = 80,
    max_words: int = 220,
) -> dict[str, Any]:
    """Ham AI çıktısından gizli bloğu ayır, görünür yorumu biçimle ve doğrula.

    `visible_text` her zaman `[AI_SONUC ...]` bloğundan arındırılmıştır.
    `require_verdict=True` ise geçersiz/eksik gizli blokta `ValueError` fırlatır.
    """
    stripped, raw_block = strip_hidden_verdict(raw_text)
    verdict, verdict_valid, verdict_errors = parse_verdict_block(raw_block)
    validation = validate_ai_commentary(stripped, min_words=min_words, max_words=max_words)

    if require_verdict and not verdict_valid:
        raise ValueError(f"Gizli AI_SONUC bloğu geçersiz: {', '.join(verdict_errors)}")

    warnings = list(validation.get("warnings") or [])
    fatal_warnings = [w for w in warnings if w in _FATAL_TELEGRAM_WARNINGS]
    visible_text = validation["formatted"] if validation["valid_structure"] else stripped

    return {
        "visible_text": visible_text,
        "verdict": verdict,
        "verdict_valid": verdict_valid,
        "verdict_errors": verdict_errors,
        "raw_verdict_block": raw_block,
        "validation": validation,
        "ok_for_telegram": bool(validation["valid_structure"] and not fatal_warnings),
        "ok_for_shadow_log": bool(validation["valid_structure"] and verdict_valid),
    }
