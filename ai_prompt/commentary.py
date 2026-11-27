"""İsteğe bağlı AI yanıtı başlık biçimleyicisi ve yapı/koruma denetçisi.

Bu modül model çağırmaz, metnin finansal doğruluğunu onaylamaz ve
alarm/Telegram akışına kendiliğinden bağlanmaz.
"""
from __future__ import annotations

import re

_HEADINGS = ("Mevcut durum", "Bağlam", "Replay notu")
_DECORATED = ("🧭 Mevcut durum", "🔎 Bağlam", "🕯️ Replay notu")
_EMOJIS = ("🧭", "🔎", "🕯️", "🕯")
_ZERO_WIDTH = str.maketrans("", "", "\ufeff\u200b\u200c\u200d")


def _tr_lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


_HEADING_LOOKUP = {_tr_lower(h): h for h in _HEADINGS}

_TABLE_RE = re.compile(r"(?m)^\s*\|?[^|\n]+\|[^\n]*\n\s*\|?\s*:?-{3,}:?\s*\|")
_DISCLAIMER_RE = re.compile(
    r"\b(?:yatırım\s+tavsiyesi\s+değildir|ytd|finansal\s+tavsiye\s+değildir)\b",
    re.IGNORECASE,
)
_DIRECTIVE_RE = re.compile(
    r"\b(?:hedef\s+fiyat|stop[- ]?loss|zarar\s+kes|kesin\s+yükselecek|"
    r"kesin\s+düşecek|alım\s+yapılmalı|satım\s+yapılmalı|al\s+sinyali|sat\s+sinyali)\b",
    re.IGNORECASE,
)
_INTERNAL_JARGON_RE = re.compile(
    r"\b(?:epizot\w*|checkpoint\w*|PARTICIPATION_[A-Z_]+|STATE_[A-Z_]+|"
    r"(?:WEEKLY|DAILY|H4)_[A-Z_]+|KIRILIM_[A-Z_]+|BASARISIZ_KIRILIM|"
    r"FORMASYON_[A-Z_]+|RETEST_[A-Z_]+|SIKISMA_GUCLENIYOR|"
    r"ADAY_OLUSUYOR|GEOMETRI_ADAYI|OLGUNLASIYOR)\b",
)


def _heading(line: str) -> str | None:
    candidate = line.translate(_ZERO_WIDTH).strip()
    candidate = re.sub(r"^#{1,4}\s+", "", candidate)
    # Support **Heading:**, **🧭 Heading**, and 🧭 **Heading:** forms without
    # matching arbitrary body text that happens to mention a heading.
    candidate = candidate.strip("*_ ").removesuffix(":").strip("*_ ")
    for emoji in _EMOJIS:
        if candidate.startswith(emoji):
            candidate = candidate[len(emoji):].lstrip("\ufe0f ").strip()
            candidate = candidate.strip("*_ ").removesuffix(":").strip("*_ ")
            break
    return _HEADING_LOOKUP.get(_tr_lower(candidate))


def format_ai_commentary(text: str) -> str:
    """Üç bilinen başlığı sırayla doğrula; içeriği yeniden yorumlama.

    Başlıklar ayrı satırda olmalı; eksik, boş, yinelenmiş veya sırası bozuk
    bölümler ve giriş metni hata verir. Başlık dışı metin aynen korunur;
    sembol/emoji veya finansal iddialar doğrulanmaz.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("AI yanıtı boş veya metin değil")
    lines = text.translate(_ZERO_WIDTH).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[list[str]] = []
    found: list[str] = []
    for line in lines:
        heading = _heading(line)
        if heading is not None:
            found.append(heading)
            sections.append([])
        elif not sections:
            if line.strip():
                raise ValueError("İlk başlık öncesinde metin var")
        else:
            sections[-1].append(line)
    if tuple(found) != _HEADINGS:
        raise ValueError("AI yanıtında üç başlık doğru sırayla ve birer kez bulunmalı")
    if any(not any(line.strip() for line in section) for section in sections):
        raise ValueError("AI yanıtında boş bölüm var")
    output = []
    for heading, body in zip(_DECORATED, sections):
        # Trim only leading/trailing blank separator lines, not section content.
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        output.append(heading + "\n" + "\n".join(body))
    return "\n\n".join(output)


def validate_ai_commentary(
    text: str,
    *,
    min_words: int = 80,
    max_words: int = 220,
) -> dict:
    """AI yanıtını yapı, kelime bütçesi ve temel koruma kuralları için denetle.

    Metni yeniden yazmaz; yalnız yapısal geçerlilik, biçimlenmiş çıktı (varsa),
    bölüm kelime sayıları ve denetim uyarılarını döndürür.
    """
    if min_words < 1 or max_words < min_words:
        raise ValueError("Kelime sınırları 1 <= min_words <= max_words olmalı")
    try:
        formatted = format_ai_commentary(text)
    except ValueError as exc:
        return {
            "valid_structure": False,
            "error": str(exc),
            "formatted": None,
            "word_count": 0,
            "section_word_counts": {},
            "warnings": [],
        }

    blocks = formatted.split("\n\n")
    section_counts: dict[str, int] = {}
    body_parts: list[str] = []
    for key, block in zip(_HEADINGS, blocks):
        _, _, body = block.partition("\n")
        words = re.findall(r"\S+", body)
        section_counts[key] = len(words)
        body_parts.append(body)

    full_body = "\n".join(body_parts)
    total_words = sum(section_counts.values())
    warnings: list[str] = []
    if total_words < min_words:
        warnings.append("cok_kisa")
    elif total_words > max_words:
        warnings.append("cok_uzun")
    if _TABLE_RE.search(full_body):
        warnings.append("tablo_iceriyor")
    if _DISCLAIMER_RE.search(full_body):
        warnings.append("genel_yatirim_uyarisi")
    if _DIRECTIVE_RE.search(full_body):
        warnings.append("yasak_tavsiye_veya_kesin_tahmin")
    if _INTERNAL_JARGON_RE.search(full_body):
        warnings.append("ic_jargon_veya_ham_enum")

    return {
        "valid_structure": True,
        "error": None,
        "formatted": formatted,
        "word_count": total_words,
        "section_word_counts": section_counts,
        "warnings": warnings,
    }
