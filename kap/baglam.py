"""BIST-Man tek dosya KAP alarm bağlam modülü (otomatik üretildi).

Görev ayrımı:
  - Arka planda: `KapCollectorService(db_yolu, universe=...).run_forever()`
    KAP listesini ortak okur, tek hisse ve tam cümle kanıtını doğrular, SQLite
    (WAL) arşivine gerçek gözlem saatiyle (`known_at`) sessizce yazar.
    Alarm üretmez, mesaj göndermez, ikinci AI çağrısı açmaz.
  - Grafik alarmı tetiklendiğinde: `kap_baglami_ekle(istek, db_yolu, hisse, alarm_zamani)`
    arşivi salt okunur sorgular; uygun kanıt varsa mevcut yorum isteğine ekler.

Dış bağımlılık: yalnız Python 3.11+ standart kütüphanesi ve `httpx`.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import json
import logging
import math
import random
import re
import sqlite3
import threading
import unicodedata
from collections import Counter
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException, InvalidOperation
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Literal, Protocol, runtime_checkable

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - yalnız ağsız/minimal kurulumda
    httpx = None  # type: ignore[assignment]

__all__ = [
    "DEFAULT_MAX_AGE",
    "AlarmArchive",
    "ReviewedReading",
    "open_archive",
    "kap_baglami_ekle",
    "KapCollectorService",
    "ScanReport",
    "EvidenceProposal",
    "EvidenceReviewer",
    "extract_verified_evidence",
    "ingest_feed",
    "sync_once",
    "KapClient",
    "KapError",
    "KapParseError",
    "KapUnavailable",
    "CompanyEntry",
    "CompanyMapError",
    "fetch_companies",
    "parse_companies",
    "build_company_resolver",
    "select_primary_ticker",
    "TickerResolver",
    "DisclosureStub",
    "DisclosureDetail",
    "FundamentalRow",
    "PublishedRow",
    "ArchiveCandidate",
    "PacketHeld",
    "build_packet",
    "make_candidate",
    "parse_light",
    "parse_detail",
    "parse_history",
    "body_text",
]


# ==========================================================================
# Kaynak: bistman/parsing/text.py
# ==========================================================================

_TR_MAP = str.maketrans(
    {
        "İ": "i",
        "I": "ı",
        "Ş": "ş",
        "Ğ": "ğ",
        "Ü": "ü",
        "Ö": "ö",
        "Ç": "ç",
    }
)

# Hukuki ekler yalnızca unvanın SONUNDA atılır (metnin ortasındaki "A.Ş." kalsın).
# Hem Türkçe hem ASCII yazım: A.Ş. / A.S. / T.A.Ş. / TAS / A.O. / LTD.ŞTİ.
_LEGAL_SUFFIX = re.compile(
    r"(?:(?<=\s)|^)(?:"
    r"a\.?\s?[şs]\.?"
    r"|a\.?\s?o\.?"
    r"|t\.?\s?a\.?\s?[şs]\.?"
    r"|t\.?\s?a\.?\s?o\.?"
    r"|anonim\s+[şs]irketi"
    r"|limited\s+[şs]irketi"
    r"|ltd\.?\s?[şs]ti\.?"
    r")\s*$",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)

# Eşleştirme için ASCII katlama: KAP unvanları Türkçe karakterle yazılı
# ("MATRİKS") ama kullanıcı/kaynak verisi ASCII yazabiliyor ("MATRIKS").
# tr_lower() Türkçe kuralına sadık kalır (I->ı); name_norm() eşleştirme
# anahtarı olduğu için diakritikleri sadeleştirir — ikisi aynı anahtara düşer.
_ASCII_FOLD = str.maketrans(
    {"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c", "â": "a", "î": "i", "û": "u"}
)
_SPACES = re.compile(r"\s+")

# KAP sembolü: 3-6 karakter, harfle başlar, rakam içerebilir (A1CAP, A1YEN).
SYMBOL_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,5}\b")
# KAP çok hisseli bildirimlerde semboller başlığın " / " sonrasında sıralanır:
#   "BORSA İSTANBUL BISTECH ... Bildirimi / MTRKS"
#   "BORSA İSTANBUL A.Ş. Hak Kullanımı / KRGYO, MTRKS"
_TITLE_SYMBOL_SPLIT = re.compile(r"\s/\s")

# Noktadan sonra büyük harf gelse bile cümleyi bitirmeyen Türkçe kısaltmalar
# ("Prof. Dr. Ahmet", "ABC Ltd. Şti.", "Bkz. Madde", "Av. Mehmet").
_ALWAYS_ABBREV = frozenset(
    {
        "prof", "dr", "av", "doç", "doc", "yrd", "uzm", "arş", "ars", "öğr", "ogr",
        "sn", "sayın", "bkz", "bknz", "ör", "örn", "orn", "vb", "vs", "vd", "yak",
        "md", "mad", "no", "nr", "tel", "faks", "cad", "sok", "mah", "blv", "bul", "apt",
        "ltd", "koop", "san", "tic", "paz", "ith", "ihr", "inş", "ins", "taah", "tur",
        "müh", "muh", "mim", "elk", "elek", "mak", "oto", "tek", "teks", "gıd", "gid",
        "kim", "sağ", "sag", "hiz", "dan", "nak", "yat", "men", "değ", "deg", "ort",
        "yön", "yon", "kur", "bşk", "bsk", "gen", "müd", "mud", "gn",
    }
)
# Kurum ve resmî baş harf kısaltmaları ("A.Ş.", "T.A.Ş.", "A.O.", "Şti.", "T.C.", "A.B.D.", "S.S."):
# aynı satırda cümle içinde çok sık geçer ("... T.C. Sağlık Bakanlığı arasında ...").
_CORP_ABBREV_RE = re.compile(
    r"(?:(?<=\s)|^)(?:t\.?\s*a\.?\s*[şs]|t\.?\s*a\.?\s*o|a\.?\s*[şs]|a\.?\s*o|[şs]ti)\.$",
    re.IGNORECASE,
)
_DOTTED_INITIALISM_RE = re.compile(
    r"(?:(?<=\s)|^)(?:[^\W\d_]\.\s*){2,}$",
    re.UNICODE,
)
_LAST_DOT_WORD_RE = re.compile(r"([^\W\d_]+)\.$", re.UNICODE)
_SINGLE_INITIAL_RE = re.compile(r"(?:(?<=\s)|^)[^\W\d_]\.$", re.UNICODE)
_ORDINAL_END_RE = re.compile(r"(?:(?<=\s)|^)\d{1,4}\.$")
_ORDINAL_NEXT_RE = re.compile(
    r"^\s*(?:dönem|çeyrek|yıl|ay|hafta|gün|madde|fıkra|bent|tertip|etap|faz|kısım|"
    r"bölüm|grup|derece|sıra|olağan|asliye|icra|idare|ağır|ticaret|hukuk|ceza|noter)\b",
    re.IGNORECASE,
)
_SENT_PUNCT_WS = re.compile(r"(?<=[.!?])[ \t]+|\n+|;[ \t]*")


def _first_alpha(text: str) -> str | None:
    for ch in text.lstrip():
        if ch.isalpha():
            return ch
        return ch
    return None


def is_abbreviation_break(before: str, after: str = "") -> bool:
    """`before` sonundaki nokta gerçek bir cümle sonu değil, kısaltma/sıra noktası mı?"""
    # O(1) pencere: büyük KAP gövdelerinde (50+ KB) tüm öneki kopyalayıp küçük harfe çevirme.
    end = len(before)
    has_newline = False
    while end > 0 and before[end - 1].isspace():
        if before[end - 1] == "\n":
            has_newline = True
        end -= 1
    if end == 0 or before[end - 1] != ".":
        return False
    win_start = max(0, end - 48)
    while win_start > 0 and (end - win_start) < 128 and not before[win_start - 1].isspace():
        win_start -= 1
    tail = before[win_start:end]
    tail_low = tr_lower(tail)
    after_head = after[:64]
    if _CORP_ABBREV_RE.search(tail_low) or _DOTTED_INITIALISM_RE.search(tail_low):
        # "ABC A.Ş. arasında" veya "T.C. Sağlık Bakanlığı" cümle sonu değildir.
        # Yalnız satır sonundan sonra yeni paragraf başlıyorsa cümle sınırı kabul edilir.
        return not has_newline
    if m := _LAST_DOT_WORD_RE.search(tail_low):
        if m.group(1) in _ALWAYS_ABBREV:
            return True
    if _SINGLE_INITIAL_RE.search(tail):
        return True
    if _ORDINAL_END_RE.search(tail):
        nxt = _first_alpha(after_head)
        if (nxt is not None and nxt.islower()) or _ORDINAL_NEXT_RE.match(tr_lower(after_head)):
            return True
    # Herhangi bir noktadan hemen sonra küçük harfle devam ediliyorsa (ör. "12-(4). maddesi")
    nxt = _first_alpha(after_head)
    if nxt is not None and nxt.isalpha() and nxt.islower() and not has_newline:
        return True
    return False


def split_clauses(text: str) -> list[str]:
    """Kısaltma noktalarını (`A.Ş.`, `Ltd. Şti.`, `Prof. Dr.`) bölmeden cümle/yan cümle ayırır."""
    if not text:
        return []
    parts: list[str] = []
    start = 0
    for match in _SENT_PUNCT_WS.finditer(text):
        sep = match.group(0)
        m_start, m_end = match.start(), match.end()
        if "\n" not in sep and not sep.startswith(";"):
            before_win = text[max(0, m_start - 128):m_start]
            after_win = text[m_end:m_end + 64]
            if is_abbreviation_break(before_win, after_win):
                continue
        chunk = text[start:m_start]
        if chunk.strip():
            parts.append(chunk)
        start = m_end
    tail = text[start:]
    if tail.strip():
        parts.append(tail)
    return parts


def symbols_in_title(title: str | None) -> tuple[str, ...]:
    r"""Başlıktaki `/` sonrası sembol listesini döndürür.

    Yalnız `\s/\s` varsa ayrıştırılır: şirket unvanlarındaki "A.Ş." gibi
    kısaltmalar sembol sanılmasın. KAP bu biçimi platform bildirimlerinde
    (devre kesici, tipe dönüşüm, işlem yasağı) kullanıyor; canlı akışta
    ticker alanı olmadığı için tek yol bu.
    """
    if not title or not _TITLE_SYMBOL_SPLIT.search(title):
        return ()
    tail = _TITLE_SYMBOL_SPLIT.split(title)[-1]
    return tuple(SYMBOL_RE.findall(tail))


def tr_lower(text: str) -> str:
    """Türkçe kurallarına uygun küçük harfe çevirir (ayrışık `I\\u0307` / `i\\u0307` dahil)."""
    if not text:
        return ""
    if "\u0307" in text:
        text = text.replace("I\u0307", "i").replace("i\u0307", "i").replace("\u0307", "")
    text = text.translate(_TR_MAP)
    text = text.replace("â", "a").replace("î", "i").replace("û", "u")
    return text.lower()


def name_norm(text: str) -> str:
    """Şirket unvanı eşleştirme anahtarı.

    TR-küçük harf + ASCII katlama + hukuki ek atma + noktalama temizliği:
        "MATRİKS FİNANSAL TEKNOLOJİLER A.Ş." -> "matriks finansal teknolojiler"
        "MATRIKS FINANSAL TEKNOLOJI"          -> "matriks finansal teknoloji"
    """
    if not text:
        return ""
    # Hukuki ek her durumda atılır (bu fonksiyon düz metne değil, yalnızca
    # unvan anahtarına uygulanır). İki tur: "T.A.Ş." -> "A.Ş." gibi zincirler için.
    for _ in range(2):
        new_text = _LEGAL_SUFFIX.sub("", text).strip()
        if new_text == text:
            break
        text = new_text
    text = tr_lower(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_ASCII_FOLD)
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


# ==========================================================================
# Kaynak: bistman/parsing/dates.py
# ==========================================================================

TRT = timezone(timedelta(hours=3), name="TRT")  # Europe/Istanbul sabit UTC+3 (2016'dan beri DST yok)

_YMD = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$")
_DMY_DT = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})[ T](\d{2}):(\d{2})(?::(\d{2}))?$")
_DMY_D = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_DMY_DASH = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
_RELATIVE = re.compile(r"^(bugün|dün)\s+(\d{2}):(\d{2})(?::(\d{2}))?$", re.IGNORECASE)


class UnparsableDate(ValueError):
    """Tanınmayan tarih formatı — sessizce None dönmek yerine patlar (bkz. triage felsefesi)."""


def _to_utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=TRT).astimezone(timezone.utc)


def parse_kap_datetime(raw: str, *, now: datetime | None = None) -> datetime:
    """KAP'tan gelen tarih metnini aware UTC datetime'a çevirir.

    Args:
        raw: Yukarıdaki formatlardan biri ("Bugün 14:53" dahil).
        now: Göreli ifadeler için referans (test edilebilirlik). Varsayılan: şimdi.

    Raises:
        UnparsableDate: format tanınmadıysa. Boş string yaygın olduğu için
            çağıran katman `None` kontrolünü kendi yapar.
    """
    if not raw or not raw.strip():
        raise UnparsableDate("boş tarih")
    s = raw.strip().replace("\u00a0", " ")

    if m := _YMD.match(s):
        y, mo, d, hh, mi, ss = m.groups()
        return _to_utc(int(y), int(mo), int(d), int(hh), int(mi), int(ss or 0))

    if m := _DMY_DT.match(s):
        d, mo, y, hh, mi, ss = m.groups()
        return _to_utc(int(y), int(mo), int(d), int(hh), int(mi), int(ss or 0))

    if m := _DMY_D.match(s) or _DMY_DASH.match(s):
        d, mo, y = m.groups()
        return _to_utc(int(y), int(mo), int(d))  # gün hassasiyeti -> 00:00 TRT

    if m := _RELATIVE.match(s):
        word, hh, mi, ss = m.groups()
        ref = (now or datetime.now(timezone.utc)).astimezone(TRT)
        day = ref.date() - (timedelta(days=1) if word.lower() == "dün" else timedelta(0))
        return _to_utc(day.year, day.month, day.day, int(hh), int(mi), int(ss or 0))

    raise UnparsableDate(f"tanınmayan tarih formatı: {raw!r}")


def try_parse_kap_datetime(raw: str, *, now: datetime | None = None) -> datetime | None:
    """Hata fırlatmayan sürüm; sadece 'bu alan yok/boş' durumları için."""
    try:
        return parse_kap_datetime(raw, now=now)
    except UnparsableDate:
        return None


def to_trt(dt: datetime) -> datetime:
    """Gösterim için TRT'ye çevir (DB'de her zaman UTC tutulur)."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime: UTC olduğunu varsaymıyoruz")
    return dt.astimezone(TRT)


# ==========================================================================
# Kaynak: bistman/parsing/money.py
# ==========================================================================

# --- Sabitler ---------------------------------------------------------------

MAGNITUDE = {
    "bin": Decimal(10) ** 3,
    "milyon": Decimal(10) ** 6,
    "milyar": Decimal(10) ** 9,
    "trilyon": Decimal(10) ** 12,
}

CURRENCY = {
    "tl": "TRY", "try": "TRY", "₺": "TRY", "türk lirası": "TRY",
    "usd": "USD", "dolar": "USD", "$": "USD", "abd doları": "USD",
    "eur": "EUR", "euro": "EUR", "€": "EUR", "avro": "EUR",
    "gbp": "GBP", "sterlin": "GBP", "£": "GBP",
    "chf": "CHF", "isviçre frangı": "CHF",
    "jpy": "JPY", "japon yeni": "JPY",
    "cny": "CNY", "yuan": "CNY",
    "rub": "RUB", "ruble": "RUB",
    "sar": "SAR", "aed": "AED", "cad": "CAD", "aud": "AUD",
    "₤": "UNKNOWN",  # genel lira işareti, TRY varsayma
}

# Sıra KRİTİK: TR binlik-gruplu -> EN virgül-gruplu -> EN ondalık -> TR ondalık -> düz.
# EN ondalık, "3.5 milyar"daki "3.5"i yakalayabilmek için düz sayıdan ÖNCE gelir;
# aksi hâlde motor "3"ü eşleyip ".5 milyar"ı atlar ve tutarı 5 milyar okur.
# EN virgül-gruplu ("1,234,567 USD", "12,500.50 USD") en az iki virgül grubu
# veya virgül+nokta ondalık ister; böylece TR ondalık ("1,250 milyar") bozulmaz.
_NUM = (
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?"
    r"|\d{1,3}(?:,\d{3}){2,}(?:\.\d{1,2})?"
    r"|\d{1,3}(?:,\d{3})+\.\d{1,2}"
    r"|\d+\.\d{1,2}"
    r"|\d+(?:,\d+)?)"
)
_MAG = "(?:" + "|".join(MAGNITUDE) + ")"
# Uzundan kısaya sırala ki "türk lirası" / "isviçre frangı" kısaltmaya takılmasın.
_CUR = "(?:" + "|".join(
    re.escape(k).replace(r"\ ", r"\s+") for k in sorted(CURRENCY, key=len, reverse=True)
) + ")"


def _unit_key(token: str) -> str:
    """Yalnız eşleşen birimi katla (MİLYON/MILYON); kaynak metne dokunma."""
    return " ".join(tr_lower(token).replace("ı", "i").split())


_CURRENCY_BY_KEY = {_unit_key(k): v for k, v in CURRENCY.items()}

# Yüzdeleri aynı taramada tüket: metinden silmek hem ofsetleri kaydırır hem
# de yüzde ifadesinin iki yanındaki bağımsız sayı ve para birimini birleştirir.
# `(?P<dash>[.,]-)` KAP metinlerindeki "250.000.000.- TL" / "1.500,- TL" yazımını destekler.
MONEY_RE = re.compile(
    rf"(?P<percent>(?:%\s*|\byüzde\s+){_NUM})|"
    rf"(?<![\w.,])(?:(?P<curpre>{_CUR})\s*)?(?P<num>{_NUM})(?:[.,]-)?"
    rf"(?:\s*(?P<mag>{_MAG}))?(?:\s*(?P<cur>{_CUR}))?(?!\w|[.,]\d)",
    re.IGNORECASE,
)

# "1.234.567,89 TL" gibi binlik gruplu sayı
_GROUPED = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
# "1,234,567" veya "12,500.50" -> EN virgül gruplu sayı
_EN_GROUPED = re.compile(r"\d{1,3}(?:,\d{3}){2,}(?:\.\d{1,2})?|\d{1,3}(?:,\d{3})+\.\d{1,2}")
# "1234,56" -> virgül ondalık (TR)
_TR_DECIMAL = re.compile(r"\d+,\d+")
# "1,250" / "12,500" -> büyüklük kelimesi olmadan tek virgül + 3 hane (EN binlik / TR ondalık belirsizliği)
_AMBIGUOUS_COMMA_THOUSAND = re.compile(r"[1-9]\d{0,2},\d{3}")
# "3.5" -> nokta ondalık (EN sızması); binlik grubu DEĞİL
_EN_DECIMAL = re.compile(r"\d+\.\d{1,2}")
_PLAIN = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal          # ham birimde (magnitude uygulanmış), ör. 500_000_000
    currency: str            # 'TRY' | 'USD' | 'EUR' | 'GBP' | 'UNKNOWN'
    raw: str                 # eşleşen ham metin (audit için)
    start: int
    end: int
    warnings: tuple[str, ...] = ()

    def to_try(self, fx: Mapping[str, Decimal] | None = None) -> Decimal | None:
        fx = fx or {}
        if self.currency == "TRY":
            return self.amount
        rate = fx.get(self.currency)
        if self.currency == "UNKNOWN" or rate is None:
            return None
        try:
            rate = Decimal(str(rate))
            if not rate.is_finite() or rate <= 0:
                return None
            return (self.amount * rate).quantize(Decimal("0.01"))
        except DecimalException:
            return None


# --- Sayı normalizasyonu ----------------------------------------------------

def _parse_number(tok: str) -> tuple[Decimal, tuple[str, ...]]:
    """TR (1.234.567,89) ve EN (3.5) formatlarını ayırt ederek Decimal üret."""
    warns: list[str] = []
    if _GROUPED.fullmatch(tok):
        # 1.234.567 veya 1.234.567,89
        return Decimal(tok.replace(".", "").replace(",", ".")), ()
    if _EN_GROUPED.fullmatch(tok):
        warns.append(f"en_format_grouped:{tok}")
        return Decimal(tok.replace(",", "")), tuple(warns)
    if _TR_DECIMAL.fullmatch(tok):
        return Decimal(tok.replace(",", ".")), ()
    if _EN_DECIMAL.fullmatch(tok):
        # Nokta ondalık: TR metninde 3.5 yerine 3,5 beklenir -> uyarı üret
        warns.append(f"en_format_decimal:{tok}")
        return Decimal(tok), tuple(warns)
    if _PLAIN.fullmatch(tok):
        return Decimal(tok), ()
    # Aşırı uzun / bozuk sayı: binlik ayırıcısı yanlış kullanılmış olabilir
    try:
        return Decimal(re.sub(r"[^\d]", "", tok)), (f"bozuk_sayi:{tok}",)
    except InvalidOperation:  # pragma: no cover
        raise ValueError(f"sayı çözümlenemedi: {tok!r}")


# --- Ana fonksiyon ---------------------------------------------------------

def find_amounts(text: str) -> list[Money]:
    """Metindeki tüm parasal tutarları döndürür (metin sırasıyla)."""
    if not text:
        return []

    out: list[Money] = []

    for m in MONEY_RE.finditer(text):
        if m.group("percent"):
            continue
        # Bitişik eksi işareti ("-50 milyon TL", "−1.250 USD"): pozitif tutar gibi okuma.
        m_start = m.start()
        if m_start > 0 and text[m_start - 1] in "-−":
            if m_start == 1 or not text[m_start - 2].isalnum():
                continue
        num_tok = m.group("num")
        mag_tok = _unit_key(m.group("mag") or "")
        cur_tok = _unit_key(m.group("cur") or m.group("curpre") or "")

        # Ne büyüklük ne para birimi varsa -> tutar değil
        if not mag_tok and not cur_tok:
            continue

        try:
            value, warns = _parse_number(num_tok)
        except (ValueError, InvalidOperation):
            continue

        if mag_tok:
            value = value * MAGNITUDE[mag_tok]

        currency = _CURRENCY_BY_KEY.get(cur_tok, "UNKNOWN")

        # Para birimi yok ama büyüklük var -> "15 milyar" (TL varsayımı
        # yapma, işaretle; FX kararı çağıran katmanın)
        warns_list = list(warns)
        if not mag_tok and _AMBIGUOUS_COMMA_THOUSAND.fullmatch(num_tok):
            warns_list.append(f"belirsiz_virgul_binlik:{num_tok}")
        if currency == "UNKNOWN":
            warns_list.append("para_birimi_yok")

        out.append(
            Money(
                amount=value,
                currency=currency,
                raw=m.group(0),
                start=m.start(),
                end=m.end(),
                warnings=tuple(warns_list),
            )
        )

    return out


def best_amount(text: str, fx: Mapping[str, Decimal] | None = None) -> Money | None:
    """Sayısal maksimum (inceleme aracı); olaya/şirkete ait bedeli belirlemez."""
    candidates = find_amounts(text)
    if not candidates:
        return None

    def key(m: Money) -> tuple[int, Decimal]:
        try_try = m.to_try(fx)
        # TRY'ye çevrilebilenler önce gelir
        return (1 if try_try is not None else 0, try_try or m.amount)

    return max(candidates, key=key)


# ==========================================================================
# Kaynak: bistman/parsing/kap_table.py
# ==========================================================================

# KAP sınıf kodları (HTML tabloda Türkçe kısaltmalar)
KNOWN_CLASSES = ("öda", "oda", "fr", "dkb", "dg")

_RE_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.S)
_RE_CELL = re.compile(r"<td[^>]*>.*?</td>", re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_CHECKBOX_ID = re.compile(r'id="(\d{6,})"\s+type="checkbox"')
_RE_TRUNCATED = re.compile(r"\(\+(\d+)\)")
_RE_DATETIME = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})\s+(\d{2}):(\d{2})")
_RE_RELATIVE = re.compile(r"(bugün|dün|bugun|dun)\s+(\d{1,2}):(\d{2})", re.I)
_RE_TABLE = re.compile(r"<table[^>]*>", re.I)


class KapTableError(ValueError):
    """Tablo beklenen yapıda değil — sessizce eksik geçmiş üretmektense patla."""


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """Geçmiş tablosundaki tek bildirim."""

    index: int
    published_at: datetime
    disclosure_class: str | None
    company_title: str
    subject: str
    summary: str
    tickers: tuple[str, ...]
    """`Kod` sütunu = ihraççının kodu. DKB'de (BISTECH duyuruları) BOŞTUR."""
    related: tuple[str, ...] = ()
    """İlgili hisseler sütunu. Birden fazla sembol olabilir (piyasa geneli duyuru)."""
    related_total: int | None = None
    """`(+N)` varsa ilgili hisse sayısı; hisse listesi o zaman EKSİKTİR."""
    period: str | None = None
    attachment_count: int = 0

    @property
    def related_truncated(self) -> bool:
        return self.related_total is not None

    @property
    def is_relative_date(self) -> bool:
        """Tarih 'Bugün/Dün' olarak gelmişse yıl-sınırı belirsizliği vardır."""
        return False  # parse sırasında çözüldü; alan geriye dönük uyum için duruyor


# --------------------------------------------------------------- HTML -> metin


def html_to_text(raw: str) -> str:
    """HTML'i düz metne çevirir. `<br>` satır sonu olur, etiketler boşluk."""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"</(p|div|tr|td|li)>", "\n", text, flags=re.I)
    text = _RE_TAG.sub(" ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line:
            out.append(line)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out).strip()


def _drop_elements_with_class(raw: str, needle: str) -> str:
    """`class` özniteliği `needle` sınıfını içeren elemanları (iç içe olanlarla) siler.

    KAP gövdesinde İngilizce kopya `content-en` sınıfıyla geliyor. Yalnız açılış
    etiketindeki `class=...` değeri kontrol edilir; Türkçe metnin içinde geçen
    ifadeler kapsayıcı etiketi sildiremez.
    """
    token = re.escape(needle)
    open_with_class = re.compile(
        rf"<(?P<tag>[a-zA-Z][\w-]*)\b[^>]*\bclass\s*=\s*"
        rf"(?:\"[^\"]*(?<![\w-]){token}(?![\w-])[^\"]*\""
        rf"|'[^']*(?<![\w-]){token}(?![\w-])[^']*'"
        rf"|{token}(?=[\s/>]))[^>]*>",
        re.I,
    )
    pos = 0
    while True:
        hit = open_with_class.search(raw, pos)
        if hit is None:
            return raw
        start = hit.start()
        if hit.group(0).rstrip().endswith("/>"):
            raw = raw[:start] + raw[hit.end():]
            pos = start
            continue
        tag = hit.group("tag").lower()
        depth = 0
        end = -1
        for m in re.finditer(rf"<{tag}\b[^>]*>|</{tag}\s*>", raw[start:], re.I):
            piece = m.group(0)
            if piece.startswith("</"):
                depth -= 1
                if depth == 0:
                    end = start + m.end()
                    break
            elif not piece.rstrip().endswith("/>"):
                depth += 1
        if end < 0:
            end = len(raw)
        raw = raw[:start] + raw[end:]
        pos = start


_RE_FIELD_MARKER = re.compile(r"^[a-z][a-z0-9]*_[A-Z][A-Za-z0-9]+\|$")
_RE_PLACEHOLDER = re.compile(r"^\[[A-Z0-9_]+\]$")


def body_text(raw: str) -> str:
    """Bildirim gövdesini düz metne çevirir.

    Üç temizlik yapılır:
      1. `content-en` kopyaları atılır (aynı tutar iki kez görünmesin),
      2. GWT alan işaretleri (`oda_ExplanationTextBlock|`) silinir,
      3. doldurulmamış yer tutucular (`[CONSOLIDATION_METHOD]`) silinir.
    """
    text = html_to_text(_drop_elements_with_class(raw, "content-en"))
    kept: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _RE_FIELD_MARKER.match(stripped) or _RE_PLACEHOLDER.match(stripped):
            continue
        kept.append(stripped)
    return "\n".join(kept)


# ------------------------------------------------------------------ tek hücre


def parse_related(cell: str) -> tuple[tuple[str, ...], int | None]:
    """İlgili hisse hücresi -> (kodlar, toplam|None).

    >>> parse_related("MTRKS")
    (('MTRKS',), None)
    >>> parse_related("IDH IEV (+6)")
    (('IDH', 'IEV'), 8)
    """
    text = html_to_text(cell)
    if not text or text.strip() in {"-", "—"}:
        return (), None
    tickers = tuple(SYMBOL_RE.findall(text))
    m = _RE_TRUNCATED.search(text)
    total = len(tickers) + int(m.group(1)) if m else None
    return tickers, total


def parse_when(cell: str, *, today: date | None = None) -> datetime:
    """Tarih hücresi -> datetime. 'Bugün 14:53' / 'Dün 09:12' de çözülür."""
    text = html_to_text(cell)
    m = _RE_DATETIME.search(text)
    if m:
        d, mo, y, hh, mm = (int(g) for g in m.groups())
        try:
            return datetime(y, mo, d, hh, mm)
        except ValueError as exc:
            raise UnparsableDate(f"geçersiz tarih: {text!r}") from exc
    rel = _RE_RELATIVE.search(text)
    if rel:
        # Sunucu UTC çalışsa bile KAP'taki "Bugün/Dün" Türkiye saatine (TRT) göredir.
        base = today or datetime.now(TRT).date()
        word = rel.group(1).lower()
        if word in {"dün", "dun"}:
            base = base - timedelta(days=1)
        return datetime(base.year, base.month, base.day, int(rel.group(2)), int(rel.group(3)))
    # Son çare: gün/ay/yıl biçimi (KAP detay ucunda noktalı gelir)
    try:
        return parse_kap_datetime(text)
    except UnparsableDate as exc:
        raise UnparsableDate(f"tarih çözümlenemedi: {text!r}") from exc


def _clean_title(cell: str, subject: str) -> str:
    """'Unvan + konu' birleşik sütunundan unvanı ayıklar.

    Tabloda unvan ve konu aynı hücrede: "MATRİKS ... A.Ş. Haber ve Söylentilere
    İlişkin Açıklama". Konu eklenmiş haldeyken unvan eşleştirmesi (ticker_map)
    yanlış kelime kapsamı görür; konuyu sondan kesiyoruz.
    """
    title = cell.strip()
    subj = subject.strip()
    if subj and title.endswith(subj):
        title = title[: -len(subj)].strip()
    return title


def _class_of(text: str) -> str | None:
    value = text.strip().lower()
    return value if value in KNOWN_CLASSES else None


def _cell_texts(row_html: str) -> list[str]:
    return [html_to_text(td) for td in _RE_CELL.findall(row_html)]


def _index_of(row_html: str) -> int | None:
    m = _RE_CHECKBOX_ID.search(row_html)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- tablo


def parse_history(
    raw: str | bytes,
    *,
    today: date | None = None,
    strict: bool = True,
) -> list[HistoryRow]:
    """`bildirim-sorgu-sonuc` HTML'inden bildirim listesi çıkarır.

    `today`: 'Bugün/Dün' ifadelerini mutlak tarihe çevirmek için; testte sabitlenir.
    `strict`: yapı beklenenden farklıysa (12 sütundan az) hata at. Sessizce
    eksik geçmiş üretmek, backfill'de en tehlikeli hata.
    """
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    if "<table" not in text.lower():
        raise KapTableError("geçmiş tablosu bulunamadı (HTML değil veya giriş engeli)")

    start = _RE_TABLE.search(text)
    assert start is not None
    table = text[start.start():]

    rows: list[HistoryRow] = []
    skipped = 0
    for row_html in _RE_ROW.findall(table):
        if "<td" not in row_html:  # başlık satırı (<th>)
            continue
        cells = _cell_texts(row_html)
        index = _index_of(row_html)
        if index is None or len(cells) < 12:
            skipped += 1
            continue
        relation, total = parse_related(cells[8])
        issuer = cells[3].strip().upper()
        tickers = (issuer,) if SYMBOL_RE.fullmatch(issuer) else ()
        period = cells[10].strip()
        attachment_raw = cells[11].strip()
        rows.append(
            HistoryRow(
                index=index,
                published_at=parse_when(cells[2], today=today),
                disclosure_class=_class_of(cells[5]),
                company_title=_clean_title(cells[4], cells[6]),
                subject=cells[6],
                summary=cells[7],
                tickers=tickers,
                related=relation,
                related_total=total,
                period=None if period in {"", "-", "—"} else period,
                attachment_count=int(attachment_raw) if attachment_raw.isdigit() else 0,
            )
        )

    if strict and skipped:
        raise KapTableError(
            f"{skipped} satır beklenen 12 sütun yapısında değil (KAP tablosu değişmiş olabilir)"
        )
    if strict and not rows:
        raise KapTableError("tablo bulundu ama hiç bildirim satırı ayrıştırılamadı")
    return rows


def summarize(rows: Iterable[HistoryRow]) -> dict[str, int]:
    """Sınıf bazında sayım — backfill raporu için."""
    counts: dict[str, int] = {}
    for row in rows:
        key = row.disclosure_class or "bilinmeyen"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


# ==========================================================================
# Kaynak: bistman/parsing/evidence.py
# ==========================================================================

_OTHER_BASIS = re.compile(
    r"\b(?:proje(?:nin)?|konsorsiyum(?:un)?)\s+(?:toplam\s+)?(?:bütçe|bedel|tutar)"
    r"|\b(?:pay|hisse) başına\b"
)
_CONTRACT_BACKGROUND = re.compile(
    r"\b(?:ödenmiş sermaye|sermayemiz|ciromuz|geçici teminat|kesin teminat)\w*"
    r"|\b(?:geçen\s+yıl|bir\s+önceki\s+yıl|önceki\s+hesap\s+dönem\w*)\b"
)
_OWN_SHARE = re.compile(r"\b(?:şirketimiz(?:e düşen pay|in payı)|payımıza düşen|payımız\b)")
_KDV_NOTE = r"(?:(?:\(\s*)?(?:\+\s*)?kdv(?:\s+(?:hariç|dahil))?(?:\s*\))?)"
_PRICE_BEFORE = re.compile(
    rf"\b(?:(?:sözleşme(?:nin)?|satış|sipariş(?:in)?|ihale(?:nin)?|iş(?:in)?)\s+(?:toplam\s+)?(?:bedeli|tutarı)"
    rf"|şirketimize düşen pay|şirketimizin payı|payımıza düşen (?:bedel|tutar))"
    rf"\s*[:=]?\s*(?:toplam\s+)?(?:{_KDV_NOTE}\s*)?$"
)
_DESC_TOKEN = r"[^\W\d_]+(?:[-/][^\W\d_]+)?"
_PRICE_AFTER = re.compile(
    rf"^\s*(?:{_KDV_NOTE}\s*)?(?:bedelli|tutarında|tutarındaki|değerinde|değerindeki)\s+"
    rf"(?:(?:{_DESC_TOKEN}|ve)\s+){{0,6}}"
    r"(?:sözleşme\w*|sipariş\w*|ihale\w*|işi?\b)",
    re.UNICODE,
)
_ISSUER_SUBJECT = re.compile(
    r"(?:^\s*(?:(?:\d{1,2}[./-]\d{1,2}[./-]\d{4}\s+tarihinde|bugün(?:\s+itibarıyla)?|dün)\s*,?\s*)?"
    r"şirketimiz(?:ce|in|le)?(?:\s*[,:]|\s+))"
    r"|\b(?:şirketimiz(?:ce|le)?\s+(?:ile\s+.+?\s+arasında|tarafından|arasında))\b"
    r"|\buhdemizde\s+kalan\b"
)
_THIRD_PARTY_ONLY = re.compile(
    r"^\s*(?:başka\s+bir\s+şirket|rakip\s+şirket|üçüncü\s+kişi)"
)
_NON_SALE_CONTRACT = re.compile(
    r"\b(?:alım|satın\s+alma|kira|kiralama|kredi|finansman|refinansman|teminat|ipotek|"
    r"gizlilik|danışmanlık|sigorta|lisans\s+alım|abonelik)\s+sözleşme"
)
_SIGNATURE = re.compile(
    r"\b(?P<sale>"
    r"(?:(?:[^\W\d_]+\s+){0,3})?satış\s+sözleşme(?:si(?:ni)?|yi)?"
    r"|ihracat\s+sözleşme(?:si(?:ni)?|yi)?"
    r"|(?:anahtar\s+teslim\s+)?yapım\s+işi\s+sözleşme(?:si(?:ni)?|yi)?"
    r"|taahhüt\s+sözleşme(?:si(?:ni)?|yi)?"
    r"|anahtar\s+teslim\s+(?:[^\W\d_]+\s+){0,3}sözleşme(?:si(?:ni)?|yi)?"
    r")\s+(?:(?:\w+\s+){0,8})?imza(?:landı|lanmıştır|ladı|ladık|lamıştır)\b"
    r"|\b(?P<order>"
    r"(?:yeni\s+)?(?:(?:[^\W\d_]+\s+){0,3})?sipariş(?:i(?:ni)?)?"
    r"|(?:(?:[^\W\d_]+\s+){0,2})(?:teslimat\w*|üretim\w*|imalat\w*|kurulum\w*|montaj\w*|"
    r"yapım\w*|inşaat\w*|mühendislik|modernizasyon|elektrifikasyon|yazılım)\s+işi"
    r")\s+(?:alındı|alınmıştır|aldı|aldık|almıştır)\b"
    r"|\b(?P<contract>(?:tedarik\s+|iş\s+|hizmet\s+|yapım\s+)?sözleşme(?:si(?:ni)?|yi)?)\s+"
    r"(?:(?:\w+\s+){0,6})?imza(?:landı|lanmıştır|ladı|ladık|lamıştır)\b",
    re.UNICODE,
)
ContractKind = Literal["sale", "contract"]

# Olumsuzlanmış fesih/iptal ifadeleri ("feshedilmemiştir", "iptal edilmedi")
# geçerli bir sözleşmeyi yanlışlıkla iptal edilmiş saymasın.
_NEGATED_QUALIFICATION = re.compile(
    r"\b(?:feshedilme(?:di|miştir|mektedir|yecek\w*)|fesh\s*edilme(?:di|miştir)"
    r"|iptal\s+edilme(?:di|miştir|mektedir|yecek\w*)"
    r"|(?:fesih|iptal)\s+(?:edilmesi\s+)?söz\s+konusu\s+değil\w*)\b"
)
# Dar koruma: geçmiş bir imzayı anlatan cümleden sonraki feshi/koşulu koparma.
# Eşleşmemesi, hukukî kesinlik garantisi değildir.
_QUALIFICATION = re.compile(
    r"\b(?:iptal|fesih|fesh|feshet|feshed|imzalanmadı|imzalanmamış|imzalamadı"
    r"|alınmadı|alınmamış|almadı|yalanla|iddia)"
    r"|\b(?:ön\s+protokol|niyet\s+mektubu|mutabakat\s+zaptı)\b"
    r"|gerçeği\s+yansıtm|bağlayıcı\s+(?:değil|olma)|yürürlüğe\s+girmemiş|askıya\s+alın"
    r"|(?:iznine|onayına|koşuluna|şartına|opsiyona|opsiyonuna)\s+(?:bağlı|tabi)"
    r"|\bopsiyon\s+kapsamında\b|\bön\s+(?:koşul|şart)"
)

# Üretim duruşu: olumlu duruş beyanı ve bunu çürüten olumsuzluk/yeniden başlama.
_STOPPAGE_AFFIRMATIVE = re.compile(
    r"\b(?:üretim\w*|faaliyet\w*)\s+(?:(?:\w+\s+){0,3})?"
    r"(?:ara\s+veril(?:di|miştir|mektedir|ecek|ecektir)"
    r"|durdurul(?:du|muştur|maktadır|acak|acaktır)|dur(?:du|muştur))\b"
    r"|\b(?:üretim\s+|faaliyet\s+|hat\w*\s+|tesis\w*\s+)?duruş\w*\s+"
    r"(?:yaşan(?:dı|mıştır|maktadır)|meydana\s+gel(?:di|miştir)|gerçekleş(?:ti|miştir)|başla(?:dı|mıştır))\b"
)
_STOPPAGE_CONTRADICTION = re.compile(
    r"\b(?:ara\s+verilme(?:di|miştir|mektedir|yecek\w*)"
    r"|durdurulma(?:dı|mıştır|maktadır|yacak\w*)|durma(?:dı|mıştır)"
    r"|ara\s+verilmesi\s+söz\s+konusu\s+değil\w*)\b"
    r"|\bduruş\w*\s+(?:(?:\w+\s+){0,2})?(?:yaşanma(?:dı|mıştır|maktadır)"
    r"|gerçekleşme(?:di|miştir|mektedir)|meydana\s+gelme(?:di|miştir)"
    r"|bulunmama\w*|yok(?:tur)?|olma(?:dı|mıştır)|söz\s+konusu\s+değil\w*)\b"
    r"|\b(?:üretim\w*|faaliyet\w*)\s+(?:kesintisiz\s+|normal\s+(?:şekilde\s+|seyrinde\s+)?"
    r"|planlandığı\s+(?:şekilde\s+|gibi\s+)?)?devam\s+etmekte"
    r"|\b(?:üretim\w*|faaliyet\w*)\s+(?:yeniden|tekrar)\s+başla(?:dı|mıştır|tıldı|tılmıştır|nıldı|nılmıştır)\b"
    r"|\b(?:yeniden|tekrar)\s+(?:üretim\w*\s+)?başla(?:dı|mıştır|tıldı|tılmıştır|nıldı|nılmıştır)\b"
    r"|\bduruş\w*\s+sona\s+er(?:di|miştir)\b|\b(?:yeniden|tekrar)\s+devreye\s+alın(?:dı|mıştır)\b"
    r"|gerçeği\s+yansıtm|\byalanla|\biddia\w*\s+asılsız"
)

# Açık yokluk/ret içeren alıntının, hiç olumsuzluk taşımayan bir editör okumasıyla
# tersine çevrilmesini önleyen koruma ("yaptırım bulunmamaktadır" -> "ceza verildi").
_SOURCE_DENIAL = re.compile(
    r"\b(?:bulunmamaktadır|yoktur|söz\s+konusu\s+değildir|gerçeği\s+yansıtmamaktadır"
    r"|uygulanmamıştır|verilmemiştir|açılmamıştır|yaşanmamıştır|gerçekleşmemiştir"
    r"|kesilmemiştir|alınmamıştır|edilmemiştir|yapılmamıştır|asılsızdır)\b"
)
_READING_NEGATION = re.compile(
    r"\b(?:değil\w*|yok(?:tur)?|bulunma\w*|reddet\w*|yalanla\w*|asılsız\w*|olmaksızın|olmadığ\w*|olmayan)\b"
    r"|\w+m[ae](?:dı|di|du|dü|mış|miş|muş|müş|dığ|diğ|duğ|düğ|makta|mekte|yacak|yecek)\w*"
    r"|\w+m[ıiuü]yor\w*"
)


def _is_sale_match(match: re.Match[str], clause: str) -> bool:
    if _NON_SALE_CONTRACT.search(clause):
        return False
    return bool(match.group("sale") or match.group("order"))


def issuer_signature(*fields: str) -> ContractKind | None:
    """Dar, olumlu şirket beyanı. Bir ihalenin başlığı imza, her imza da satış değildir."""
    kind: ContractKind | None = None
    for raw_field in fields:
        for clause in split_clauses(raw_field):
            lower = tr_lower(clause)
            if _THIRD_PARTY_ONLY.match(lower) or not _ISSUER_SUBJECT.search(lower):
                continue
            if match := _SIGNATURE.search(lower):
                if _is_sale_match(match, lower):
                    return "sale"
                if not _NON_SALE_CONTRACT.search(lower):
                    kind = "contract"
    return kind


def sale_qualified(*fields: str) -> bool:
    for text in fields:
        cleaned = _NEGATED_QUALIFICATION.sub(" ", tr_lower(text))
        if _QUALIFICATION.search(cleaned):
            return True
    return False


def stoppage_confirmed(quote: str) -> bool:
    """Alıntı gerçekten olumlu bir üretim/faaliyet duruşu bildiriyor mu?"""
    lower = tr_lower(quote)
    return bool(_STOPPAGE_AFFIRMATIVE.search(lower)) and not bool(_STOPPAGE_CONTRADICTION.search(lower))


def stoppage_contradicted(*fields: str) -> bool:
    """Alıntı veya sonraki metin duruşu yalanlıyor ya da yeniden başlamayı bildiriyor mu?"""
    return any(_STOPPAGE_CONTRADICTION.search(tr_lower(text)) for text in fields if text)


def polarity_inverted(quote: str, *reading_parts: str) -> bool:
    """Kaynak açıkça 'yok/bulunmamaktadır' derken okuma tümüyle olumlu iddia mı kuruyor?"""
    if not _SOURCE_DENIAL.search(tr_lower(quote)):
        return False
    combined = tr_lower(" ".join(p for p in reading_parts if p))
    return not bool(_READING_NEGATION.search(combined))


@dataclass(frozen=True, slots=True)
class EventAmount:
    money: Money | None = None
    clause: str = ""  # money.start/end bu özgün parçaya göre
    issue: str | None = None

    def as_try(self, fx: Mapping[str, Decimal] | None = None) -> tuple[Decimal | None, tuple[str, ...]]:
        if self.money is None:
            assert self.issue is not None
            return None, (self.issue,)
        value = self.money.to_try(fx)
        return (None, ("fx_fallback",)) if value is None else (value, ())


def event_amount(*fields: str, contract: bool = False) -> EventAmount:
    """Farklı olası bedeller arasında büyüklük veya kur bulunurluğu ile seçim YOK.

    Dar istisna: ayrı cümlede açık proje toplamı/birim değer varsa, kalan bedel
    ancak açık şirket payı veya şirketin imzaladığı satış ise kullanılabilir.
    """
    candidates: dict[tuple[str, Decimal], EventAmount] = {}
    other_basis = False
    for raw_field in fields:
        for clause in split_clauses(raw_field):
            amounts = find_amounts(clause)
            if not amounts:
                continue
            lower = tr_lower(clause)
            if _OTHER_BASIS.search(lower) or (contract and _CONTRACT_BACKGROUND.search(lower)):
                if len(amounts) != 1:
                    return EventAmount(issue="ambiguous_amount")
                other_basis = True
                continue
            for money in amounts:
                key = (money.currency, money.amount)
                candidates[key] = EventAmount(money, clause)
    if len(candidates) > 1:
        return EventAmount(issue="ambiguous_amount")
    if not candidates:
        return EventAmount(issue="unattributed_amount" if other_basis else "no_amount")
    (event,) = candidates.values()
    assert event.money is not None
    clause = event.clause
    lower_clause = tr_lower(clause)
    signature = _SIGNATURE.search(lower_clause)
    if signature and _is_sale_match(signature, lower_clause) and issuer_signature(clause) != "sale":
        return EventAmount(issue="unattributed_amount")
    if contract and not (_PRICE_BEFORE.search(tr_lower(clause[:event.money.start]))
                         or _PRICE_AFTER.search(tr_lower(clause[event.money.end:]))):
        return EventAmount(issue="unattributed_amount")
    if other_basis:
        if not (_OWN_SHARE.search(lower_clause) or issuer_signature(clause) == "sale"):
            return EventAmount(issue="unattributed_amount")
    return event


# ==========================================================================
# Kaynak: bistman/sources/base.py
# ==========================================================================

@dataclass(frozen=True, slots=True)
class DisclosureStub:
    """Liste ucundan gelen hafif bildirim kaydı (gövde YOK).

    `tickers` boş olabilir: /api/disclosure/list/light ticker vermiyor,
    sadece `title` (şirket unvanı) var. Unvan→kod eşlemesi ayrı katmanda yapılır.
    """

    index: int
    """/api'deki `disclosureIndex` — cursor ve dedup anahtarı."""

    published_at: datetime
    """aware UTC. KAP TRT verir, kaynak katmanı çevirir."""

    title: str
    """Şirket unvanı (light feed'de ticker yerine bu gelir)."""

    subject: str
    """Bildirim konusu — triyajın anahtarı."""

    summary: str | None = None
    disclosure_class: str | None = None
    """'ODA' | 'FR' | 'DKB' | None."""
    tickers: tuple[str, ...] = ()
    """Dolu ise yapısal hisse kodları (detay ucu / geçmiş tablosu)."""
    member_oid: str | None = None
    """Şirketin KAP üye OID'i — geçmiş sorgusu ve detay için gerekir."""
    minute_precision: bool = False
    """Üye geçmişi HTML tablosu saniye vermez (HH:MM); detay eşlemesinde dikkate alınır."""


@dataclass(frozen=True, slots=True)
class FundamentalRow:
    """Finansal snapshot (append-only yazılır)."""

    ticker: str
    period_end: str  # ISO date; ayrıştırma sınırında tek forma indirgenir
    statement: str = "consolidated"  # 'consolidated' | 'solo'
    statement_type: str = "industrial"  # 'industrial' | 'bank'  (banka -> UFRS şablonu)
    revenue_ttm: float | None = None
    net_income_ttm: float | None = None
    equity: float | None = None
    currency: str = "TRY"
    source: str = "borsapy/isyatirim"
    flags: tuple[str, ...] = field(default_factory=tuple)
    """ttm_gap, mixed_restatement_vintage, bank_template_mismatch ..."""


@runtime_checkable
class DisclosureFeed(Protocol):
    """Piyasa geneli bildirim akışı (borsapy'de YOK, bizim katman)."""

    async def latest(self) -> list[DisclosureStub]:
        """Bugünün/ son çekilen akış. Boş liste = 'haber yok' DEĞİL, şüpheli."""
        ...

    async def history(self, member_oid: str) -> list[DisclosureStub]:
        """Bir şirketin geçmiş bildirimleri (backfill: 50 istek ~ 1 yıl)."""
        ...

    async def detail(self, index: int) -> DisclosureStub:
        """Tek bildirim detayı — yapısal `tickers` ve gövde için."""
        ...


@runtime_checkable
class FundamentalsSource(Protocol):
    async def snapshot(self, ticker: str, statement_type: str) -> FundamentalRow | None:
        """`statement_type`: 'industrial' | 'bank'. Banka -> financial_group='UFRS'."""
        ...


@runtime_checkable
class UniverseSource(Protocol):
    async def tickers(self) -> Sequence[str]:
        """Endeks bileşenleri (XU050). Boş dönerse config fallback'i devreye girer."""
        ...


@dataclass(frozen=True, slots=True)
class DisclosureDetail:
    """Detay ucunun (`/api/notification/attachment-detail/{idx}`) iç modeli."""

    stub: DisclosureStub
    body_html: str
    attachment_count: int
    is_late: bool = False

    def matches_record(self, expected: DisclosureStub) -> bool:
        """Liste/geçmiş ve detayın aynı bildirim kimliği ve yayın zamanına aitliği."""
        if self.stub.index != expected.index:
            return False
        if self.stub.published_at == expected.published_at:
            return True
        if expected.minute_precision and not self.stub.minute_precision:
            return (
                self.stub.published_at.replace(second=0, microsecond=0)
                == expected.published_at.replace(second=0, microsecond=0)
            )
        return False

    def matches(self, expected: DisclosureStub, ticker: str | None) -> bool:
        """Liste ve detayın aynı kayda ait olduğu ve yapısal hissenin çelişmediği sınır."""
        return self.matches_record(expected) and (
            not self.stub.tickers or set(self.stub.tickers) == {ticker}
        )


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Ayrıştırma sonucu: sessizce satır düşürmemek için reddedilenleri de taşır.

    `items` boş + `rejected` boş ise bu "haber yok" DEĞİL, **şüpheli** demektir
    (MIMARI.md §2 — sessiz ölüm). Çağıran katman boşluğu firehose ile çapraz
    kontrol etmekle yükümlü.
    """

    items: list[DisclosureStub]
    rejected: list[tuple[int, str]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)


# ==========================================================================
# Kaynak: bistman/triage.py
# ==========================================================================

CLASS_ODA = "oda"
CLASS_FR = "fr"
CLASS_DKB = "dkb"
CLASS_DG = "dg"

INDEX_SUBJECT = "Endekslerde Kullanılan Fiili Dolaşımdaki Pay Oranı Değişiklikleri"


def is_index_agenda(title: str, subject: str, tickers: tuple[str, ...]) -> bool:
    """BİST yayımladı diye her tek-pay duyurusunu piyasa gündemi yapma."""
    return title == "BORSA İSTANBUL A.Ş." and subject == INDEX_SUBJECT and not tickers


_CLASS_ALIASES = {
    "öda": CLASS_ODA,
    "oda": CLASS_ODA,
    "özel durum açıklaması": CLASS_ODA,
    "özel durum": CLASS_ODA,
    "fr": CLASS_FR,
    "finansal rapor": CLASS_FR,
    "dkb": CLASS_DKB,
    "diğer bildirimler": CLASS_DKB,
    "dg": CLASS_DG,
    "diğer": CLASS_DG,
}


class Route(str, Enum):
    """Bir bildirimin yazgısı. `disclosure.status` alanına birebir yazılır."""

    PIPELINE = "pipeline"
    """Skorlanır, eşiği geçerse bildirilir."""

    FUNDAMENTALS_REFRESH = "fundamentals_refresh"
    """Finansal rapor: push edilmez; finansal veri tazelemesini TETİKLER + özete girer."""

    ROUTINE = "routine"
    """Rutin: kaydedilir, skorlanmaz."""

    MECHANICAL = "mechanical"
    """Mekanik (devre kesici vb.): kaydedilir, skorlanmaz ama SAYILIR —
    aynı hissede gün içi 3+ devre kesici olağandışı harekettir (ayrı uyarı)."""


# ÖDA içinde rutin sayılan konular (tr_lower ile karşılaştırılır: parça eşleşmesi)
_ROUTINE_SUBJECTS: tuple[str, ...] = (
    "pay dökümü",
    "şirket genel bilgi formu",
    "genel kurul işlemlerine ilişkin",
    "genel kurul",
    "kayıtlı sermaye tavanı",
    "sorumluluk beyanı",
    "faaliyet raporu",
    "pay dışında sermaye piyasası aracı işlemlerine ilişkin",  # kupon/itfa
    "borsa dışı repo",
    "portföy dağılım raporu",
)

# DKB içinde mekanik ama bilgi değeri taşımayan kalıplar
_MECHANICAL_PATTERNS: tuple[str, ...] = (
    "devre kesici",
    "borçlanma araçları, yatırım fonları ve varant itfa",
    "varantların veya sertifikaların işlem görmeye başlaması",
)

# DG (idari form) ama içeriği fiyat taşıyabilecek istisnalar — hatta alınır
_DG_ESCALATE: tuple[str, ...] = (
    "sermaye artırımı",
    "sermaye azaltımı",
    "pay alım satım",
    "pay alım-satım",
    "kar dağıtımı",
    "kâr dağıtımı",
    "temettü",
)

# DKB olmasına rağmen ÖNEMLİ olan istisnalar (SPK II-15.1 md.12-4 duyurusu, VBTS, sıra kapatma vb.)
_IMPORTANT_DKB_PATTERNS: tuple[str, ...] = (
    "kamuyu aydınlatma platformu duyurusu",
    # Gerçek geçmiş tablosunda görüldü (MTRKS, 30.12.2025): işlem yasağı / VBTS /
    # pay sırasının kapatılması piyasa olayıdır, mekanik gürültü değil.
    "işlem yasağı",
    "işlem yasagi",
    "tedbir kararı",
    "volatilite bazlı tedbir",
    "vbts",
    "işleme kapatılma",
    "işleme açılma",
    "işlem sırasının durdurulma",
    "işlem sırasının yeniden açılma",
    "brüt takas",
)


def normalize_class(raw: str | None) -> str | None:
    """'ÖDA' / 'ODA' / 'oda' / 'Özel Durum Açıklaması' -> 'oda'."""
    if not raw:
        return None
    return _CLASS_ALIASES.get(tr_lower(raw).strip())


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(n in haystack for n in needles)


def route(
    disclosure_class: str | None,
    subject: str | None,
    summary: str | None = None,
) -> Route:
    """Bir bildirimi en ucuz bilgiyle sınıflandırır. Ağ/DB erişimi yok.

    Fail-open: sınıf tanınmıyorsa PIPELINE'a düşer (kaçırmak, gürültüden pahalı).
    """
    cls = normalize_class(disclosure_class)
    subject_n = tr_lower(subject or "")
    summary_n = tr_lower(summary or "")

    if cls == CLASS_ODA:
        if _contains_any(subject_n, _ROUTINE_SUBJECTS):
            return Route.ROUTINE
        return Route.PIPELINE

    if cls == CLASS_FR:
        return Route.FUNDAMENTALS_REFRESH

    if cls == CLASS_DKB:
        if subject == INDEX_SUBJECT or _contains_any(subject_n, _IMPORTANT_DKB_PATTERNS):
            return Route.PIPELINE
        if _contains_any(subject_n, _MECHANICAL_PATTERNS) or _contains_any(
            summary_n, _MECHANICAL_PATTERNS
        ):
            return Route.MECHANICAL
        return Route.ROUTINE

    if cls == CLASS_DG:
        if _contains_any(subject_n, _DG_ESCALATE):
            return Route.PIPELINE
        return Route.ROUTINE

    # Sınıf YOK: /api/disclosure/list/light bu alanı hiç vermiyor (canlı doğrulandı).
    # O yüzden konu/özet üzerinden mekanik ve rutin kalıpları yine de yakalarız;
    # hiçbir kalıba uymuyorsa fail-open (kaçırmak, gürültüden pahalı).
    if subject_n.strip() in {"finansal rapor", "finansal rapor (konsolide)", "finansal rapor (konsolide olmayan)"}:
        return Route.FUNDAMENTALS_REFRESH
    if _contains_any(subject_n, _IMPORTANT_DKB_PATTERNS):
        return Route.PIPELINE
    if _contains_any(subject_n, _MECHANICAL_PATTERNS) or _contains_any(
        summary_n, _MECHANICAL_PATTERNS
    ):
        return Route.MECHANICAL
    if _contains_any(subject_n, _ROUTINE_SUBJECTS):
        return Route.ROUTINE
    return Route.PIPELINE


_FUND_MARKERS: tuple[str, ...] = ("portföy", "portfoy", "yatırım fonu", "yatirim fonu", " serbest fon")


def looks_like_fund(title: str) -> bool:
    """Fon/portföy bildirimi mi? (Hisse senedi değil -> unresolved kuyruğunu kirletmesin)

    KAP akışının büyük kısmı fon bildirimi (canlı örnekte 9 kaydın 2'si).
    Bunları "eşleşmeyen hisse" saymak, gerçekten eşleşmeyen hisseleri gürültü
    içinde kaybettirir. Ayrı durum: `filtered_fund`.
    """
    text = tr_lower(title or "")
    if any(marker in text for marker in _FUND_MARKERS):
        return True
    return text.rstrip().endswith("fonu") or " fon " in text


def should_push(route_result: Route) -> bool:
    """v1 bildirim politikası: yalnızca PIPELINE anında bildirim adayıdır."""
    return route_result is Route.PIPELINE


# ==========================================================================
# Kaynak: bistman/ticker_map.py
# ==========================================================================

Method = Literal["exact", "fuzzy", "none", "ambiguous"]
DEFAULT_CUTOFF = 0.88
AMBIGUITY_MARGIN = 0.02


@dataclass(frozen=True, slots=True)
class Resolution:
    ticker: str | None
    method: Method
    score: float = 0.0
    candidates: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TickerResolver:
    """`from_pairs([("MTRKS", "MATRİKS FİNANSAL TEKNOLOJİLER A.Ş."), ...])`"""

    _exact: dict[str, str]
    _names: tuple[tuple[str, str], ...]  # (name_norm, ticker)
    _collisions: tuple[str, ...] = ()  # aynı anahtara düşen farklı kodlar
    cutoff: float = DEFAULT_CUTOFF

    @classmethod
    def from_pairs(
        cls, pairs: Iterable[tuple[str, str]], *, cutoff: float = DEFAULT_CUTOFF
    ) -> TickerResolver:
        exact: dict[str, str] = {}
        collisions: set[str] = set()
        names: list[tuple[str, str]] = []
        for ticker, title in pairs:
            key = name_norm(title)
            if not key:
                continue
            if (existing := exact.get(key)) is not None and existing != ticker:
                # ASCII katlama iki farklı şirketi aynı anahtara düşürdüyse
                # tahmin etme: anahtarı exact eşleşmeden çıkar.
                collisions.add(key)
            exact[key] = ticker
            names.append((key, ticker))
        for key in collisions:
            exact.pop(key, None)
        return cls(
            _exact=exact,
            _names=tuple(names),
            _collisions=tuple(sorted(collisions)),
            cutoff=cutoff,
        )

    def __len__(self) -> int:
        return len(self._exact)

    def has_ticker(self, ticker: str) -> bool:
        """Verilen sembol bu çözümleyicinin şirket evreninde tanımlı mı?"""
        code = (ticker or "").strip().upper()
        return bool(code) and any(t == code for _, t in self._names)

    def resolve(self, title: str) -> Resolution:
        key = name_norm(title)
        if not key:
            return Resolution(None, "none")

        if key in self._collisions:
            return Resolution(None, "ambiguous", 1.0)

        if (hit := self._exact.get(key)) is not None:
            return Resolution(hit, "exact", 1.0)

        scored = sorted(
            ((_similarity(key, candidate), ticker) for candidate, ticker in self._names),
            reverse=True,
        )
        if not scored:
            return Resolution(None, "none")

        best_score, best_ticker = scored[0]
        if best_score < self.cutoff:
            return Resolution(None, "none", best_score)

        close = [(s, t) for s, t in scored[:2] if best_score - s <= AMBIGUITY_MARGIN]
        if len({t for _s, t in close}) > 1:
            return Resolution(
                None, "ambiguous", best_score, tuple(t for _s, t in close)
            )
        return Resolution(best_ticker, "fuzzy", best_score)


# Unvanlarda ayırt edici olmayan kelimeler (hukuki ve genel ticaret ekleri).
# Dikkat: "ak" ve "is" (AK YATIRIM vs İŞ YATIRIM) ayırt edici marka köküdür, burada YOKTUR;
# "pazarlama", "yatirim", "holding", "uretim" de grup iştiraklerini ayırdığı için silinmez.
_GENERIC = frozenset(
    {
        "ve", "a", "s", "as", "ao", "ta", "tas", "tao", "tc",
        "anonim", "sirketi", "ticaret", "sanayi", "sanayii", "ltd", "sti",
        "turkiye", "turkiyedeki",
    }
)
# Birçok farklı şirketin unvanında ortak geçen sektör/faaliyet kelimeleri:
# "HALK YATIRIM MENKUL DEĞERLER" ile "İŞ YATIRIM MENKUL DEĞERLER" veya
# "HALK FİNANSAL KİRALAMA" ile "VAKIF FİNANSAL KİRALAMA" yalnız bu kelimeler
# benziyor diye eşleşemez; marka köklerinin de bire-bir uyuşması şarttır.
_SECTOR_WORDS = frozenset(
    {
        "yatirim", "yatirimlari", "menkul", "degerler", "kiymetler",
        "finansal", "finansman", "kiralama", "faktoring",
        "gayrimenkul", "girisim", "sermayesi", "ortakligi",
        "portfoy", "yonetimi", "emeklilik", "hayat", "sigorta",
        "bankasi", "holding", "sirketler", "grubu",
        "enerji", "elektrik", "uretim", "uretimi", "santralleri",
        "teknoloji", "teknolojiler", "teknolojileri",
        "hizmet", "hizmetleri", "iletisim", "bilisim", "sistemleri",
        "gida", "cimento", "otomotiv", "elektronik", "madencilik",
        "insaat", "turizm", "tekstil", "kimya", "tarim",
        "pazarlama", "perakende", "magazalari", "lojistik", "tasimacilik",
        "saglik", "servis", "dis", "ic",
    }
)
# Türkçe çekim ekleri (çoğul/iyelik): "teknoloji"~"teknolojiler", "hizmet"~"hizmetleri".
# Serbest önek eşleşmesi "turk"~"turkcell" veya "enerji"~"enerjisa" hatası üretir.
_INFLECTION_SUFFIXES = frozenset(
    {"i", "si", "u", "su", "ler", "lar", "leri", "lari", "yi", "yu"}
)
MIN_SIGNIFICANT_TOKENS = 2


def _significant_tokens(text: str) -> list[str]:
    return [t for t in text.split() if t not in _GENERIC and len(t) >= 2]


def _token_match(a: str, b: str, *, allow_typo: bool = False) -> bool:
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 4 and long.startswith(short):
        if long[len(short):] in _INFLECTION_SUFFIXES:
            return True
    if allow_typo and len(short) >= 5 and len(long) - len(short) <= 1:
        return SequenceMatcher(None, a, b).ratio() >= 0.88
    return False


def _paired_matches(
    sig_a: list[str], sig_b: list[str], *, allow_typo: bool = False
) -> int:
    """Bire-bir kelime eşleşmesi: aynı kökten iki kelime tek hedefe iki kez sayılamaz."""
    used: set[int] = set()
    matched = 0
    for token in sig_a:
        hit = next(
            (idx for idx, candidate in enumerate(sig_b)
             if idx not in used and _token_match(token, candidate, allow_typo=allow_typo)),
            None,
        )
        if hit is not None:
            used.add(hit)
            matched += 1
    return matched


def _brands_compatible(sig_a: list[str], sig_b: list[str]) -> bool:
    """Sektör kelimeleri çıkarıldığında kalan ayırt edici marka kökleri bire-bir uyuşuyor mu?"""
    brand_a = [t for t in sig_a if t not in _SECTOR_WORDS]
    brand_b = [t for t in sig_b if t not in _SECTOR_WORDS]
    if not brand_a and not brand_b:
        return True
    if len(brand_a) != len(brand_b):
        return False
    return _paired_matches(brand_a, brand_b, allow_typo=True) == len(brand_a)


def _similarity(a: str, b: str) -> float:
    """İki unvan arası benzerlik: marka kökü korumalı harf + simetrik kelime örtüşmesi.

    - Ayırt edici marka kelimeleri uyuşmuyorsa ("AK YATIRIM" vs "İŞ YATIRIM",
      "ZİRAAT YATIRIM" vs "İŞ YATIRIM", "ALARKO TARIM" vs "ALARKO CARRIER")
      ortak sektör/ticaret ekleri skoru şişiremez -> `0.0`.
    - Simetrik (`max`) payda sayesinde halka açık şirketin kelimelerini kapsayan
      bağlı ortaklıklar ("ENERJİSA ÜRETİM SANTRALLERİ", "ARÇELİK PAZARLAMA")
      ana hisseye bağlanmaz; gerçek çekim farkları ("TEKNOLOJİ"~"TEKNOLOJİLER") korunur.
    """
    direct = SequenceMatcher(None, a, b).ratio()
    if direct >= 0.99:
        return direct

    sig_a = _significant_tokens(a)
    sig_b = _significant_tokens(b)
    if not _brands_compatible(sig_a, sig_b):
        return 0.0

    # Genel ticaret ekleri ("sanayi ve ticaret") iki farklı iştirakin harf oranını şişirmesin.
    core_a = " ".join(sig_a) if sig_a else a
    core_b = " ".join(sig_b) if sig_b else b
    char_score = max(
        SequenceMatcher(None, core_a, core_b).ratio(),
        SequenceMatcher(None, " ".join(sorted(sig_a)), " ".join(sorted(sig_b))).ratio()
        if sig_a and sig_b else 0.0,
    )

    if len(sig_a) < MIN_SIGNIFICANT_TOKENS or len(sig_b) < MIN_SIGNIFICANT_TOKENS:
        return char_score

    overlap = _paired_matches(sig_a, sig_b, allow_typo=True) / max(len(sig_a), len(sig_b))
    # Aynı marka altında farklı sektör iştiraki ("ALARKO TARIM" vs "ALARKO GIDA") elenir.
    if overlap < 0.75:
        return min(char_score, overlap)
    return max(char_score, overlap)


# ==========================================================================
# Kaynak: bistman/sources/kap.py
# ==========================================================================

BASE_URL = "https://www.kap.org.tr"
LIGHT_PATH = "/tr/api/disclosure/list/light"
DETAIL_PATH = "/tr/api/notification/attachment-detail/{index}"
MEMBER_HISTORY_PATH = "/tr/bildirim-sorgu-sonuc"

# Kendini tanıtan UA: KAP WAF'ı boş/otomatik UA'ları kesiyor (gözlem)
USER_AGENT: str = (
    "bistman/0.1 (kisisel arastirma; +https://github.com/keremtulu44/BIST--Man)"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": f"{BASE_URL}/tr/bildirim-sorgu",
}


class KapError(RuntimeError):
    """KAP katmanı hatalarının taban sınıfı."""


class KapParseError(KapError):
    """Yanıt beklenen şekilde değil. Sessizce boş dönmek yerine fırlatılır."""


class KapUnavailable(KapError):
    """Retry bütçesi tükendi (429/5xx/transport)."""


# ---------------------------------------------------------------- ayrıştırma


def _require_list(payload: Any, what: str) -> list[Any]:
    if not isinstance(payload, list):
        raise KapParseError(f"{what}: JSON dizi bekleniyordu, {type(payload).__name__} geldi")
    return payload


def _tickers_from(raw: Any) -> tuple[str, ...]:
    """`stockCode` / `relatedStocks` -> normalize edilmiş ticker demeti.

    `relatedStocks` çok hisseli bildirimlerde "IDH, IEV, IJB" gibi gelir;
    tek hisselide `null` olup `stockCode` doludur.
    """
    codes: list[str] = []
    for chunk in (raw,) if isinstance(raw, str) else (raw or []):
        if not isinstance(chunk, str):
            continue
        for part in chunk.replace(";", ",").split(","):
            code = part.strip().upper()
            # KAP kodları 4-5 karakter (THYAO, MTRKS, ISMEN); sayı/boşluk ele
            if 3 <= len(code) <= 6 and code.isalnum() and not code.isdigit():
                codes.append(code)
    return tuple(dict.fromkeys(codes))


def _text(row: dict, key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{key}: metin bekleniyordu")
    return value.strip()


def parse_light(raw: bytes | str) -> ParseResult:
    """`/api/disclosure/list/light` yanıtını `DisclosureStub` listesine çevirir."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KapParseError(f"light: JSON çözümlenemedi: {exc}") from exc

    rows = _require_list(payload, "light")
    items: list[DisclosureStub] = []
    rejected: list[tuple[int, str]] = []

    for pos, row in enumerate(rows):
        if not isinstance(row, dict):
            rejected.append((pos, "satır dict değil"))
            continue
        try:
            index = int(row["disclosureIndex"])
            subject = _text(row, "subject")
            if not subject:
                raise ValueError("subject boş")
            items.append(
                DisclosureStub(
                    index=index,
                    published_at=parse_kap_datetime(str(row["publishDate"])),
                    title=_text(row, "title"),
                    subject=subject,
                    summary=_text(row, "summary") or None,
                    # light ucunda sınıf/ticker YOK — bu yüzden .get() ile boş bırakıyoruz
                    disclosure_class=_text(row, "disclosureClass") or None,
                )
            )
        except (KeyError, TypeError, ValueError, UnparsableDate) as exc:
            rejected.append((pos, f"{type(exc).__name__}: {exc}"))

    return ParseResult(items=items, rejected=rejected)


def parse_detail(raw: bytes | str) -> DisclosureDetail:
    """Detay ucu yanıtını `DisclosureDetail`'e çevirir (yapısal ticker burada)."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KapParseError(f"detail: JSON çözümlenemedi: {exc}") from exc

    rows = _require_list(payload, "detail")
    if not rows:
        raise KapParseError("detail: boş dizi (bildirim bulunamadı)")

    entry = rows[0]
    try:
        basic = entry["disclosure"]["disclosureBasic"]
        index = int(basic["disclosureIndex"])
        published_at = parse_kap_datetime(str(basic["publishDate"]))
    except (KeyError, TypeError, ValueError, UnparsableDate) as exc:
        raise KapParseError(f"detail: beklenen alanlar yok: {exc}") from exc

    tickers = _tickers_from(basic.get("stockCode"))
    if not tickers:
        tickers = _tickers_from(basic.get("relatedStocks"))

    body_parts = entry.get("disclosureBody")
    if body_parts is None:
        body_parts = []
    if not isinstance(body_parts, list) or not all(isinstance(p, str) for p in body_parts):
        raise KapParseError("detail: disclosureBody metin dizisi değil")
    body_html = "\n".join(p for p in body_parts if p)

    stub = DisclosureStub(
        index=index,
        published_at=published_at,
        title=(basic.get("companyTitle") or "").strip(),
        subject=(basic.get("title") or "").strip(),
        summary=basic.get("summary") or None,
        disclosure_class=basic.get("disclosureClass") or None,
        tickers=tickers,
        member_oid=basic.get("mkkMemberOid") or None,
    )
    return DisclosureDetail(
        stub=stub,
        body_html=body_html,
        attachment_count=int(basic.get("attachmentCount") or 0),
        is_late=bool(basic.get("isLate") or False),
    )


# ---------------------------------------------------------------- istemci


class KapClient:
    """KAP uçları için asenkron istemci. Testlerde `transport` enjekte edilir."""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        max_attempts: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
        base_url: str = BASE_URL,
    ) -> None:
        self._owns_client = client is None
        if client is None and httpx is None:
            raise RuntimeError("KapClient için 'httpx' paketi kurulu olmalı")
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers=DEFAULT_HEADERS,
            transport=transport,
            follow_redirects=True,
        )
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._base = base_url

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> KapClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, path: str, *, referer: str | None = None) -> httpx.Response:
        url = f"{self._base}{path}"
        headers = {"Referer": referer} if referer else None
        last_exc: Exception | None = None

        transport_err = httpx.TransportError if httpx is not None else OSError
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.get(url, headers=headers)
            except transport_err as exc:  # timeout, DNS, bağlantı
                last_exc = exc
            else:
                if response.status_code == 200:
                    return response
                if response.status_code == 429 or response.status_code >= 500:
                    last_exc = KapUnavailable(f"HTTP {response.status_code}: {url}")
                    retry_after = _retry_after_seconds(response)
                    if retry_after is not None:
                        await self._sleep(retry_after)
                        continue
                else:
                    # 4xx (403/404): retry anlamsız
                    raise KapError(f"HTTP {response.status_code}: {url}")

            # üstel backoff + jitter (rate limit cezasına yakalanmamak için)
            await self._sleep(min(2 ** (attempt - 1), 30) + random.random())

        raise KapUnavailable(f"{self._max_attempts} deneme başarısız: {url}") from last_exc

    async def get_text(self, path: str) -> str:
        """Ham metin/HTML yanıtı — JSON olmayan uçlar için (şirket listesi vb.)."""
        response = await self._get(path)
        return response.text

    async def light(self) -> ParseResult:
        """Bugünün tüm bildirim akışı. Boş sonuç **şüpheli**dir (çağıran kontrol eder)."""
        response = await self._get(LIGHT_PATH)
        return parse_light(response.content)

    async def detail(self, index: int) -> DisclosureDetail:
        """Tek bildirim detayı — yapısal `stockCode` ve gövde için."""
        response = await self._get(
            DETAIL_PATH.format(index=index),
            referer=f"{self._base}/tr/Bildirim/{index}",
        )
        detail = parse_detail(response.content)
        if detail.stub.index != index:
            raise KapParseError(f"detail: istenen bildirim {index}, gelen {detail.stub.index}")
        return detail

    async def member_history_raw(self, member_oid: str) -> str:
        """Üye bazlı geçmiş (varsayılan 1 yıl) — HAM HTML.

        Ayrıştırma `parsing.kap_table.parse_history`'de; bu metot sadece indirir.
        Tek istek = 1 yıllık tam geçmiş (17.11.2026 doğrulandı: 89 bildirim).
        """
        response = await self._get(f"{MEMBER_HISTORY_PATH}?member={member_oid}")
        return response.text

    async def fetch_history(self, member_oid: str, *, today: date | None = None) -> list:
        """Üye geçmişini ayrıştırılmış satırlar olarak döndürür (backfill birimi)."""
        pass

        raw = await self.member_history_raw(member_oid)
        return parse_history(raw, today=today)

    async def fetch_body(self, index: int) -> tuple[str, DisclosureDetail]:
        """Bildirim gövdesini **düz metin** olarak indirir (pipeline `body_provider`'ı).

        Gövde HTML'i TR + EN iki kopya içeriyor; düz metne çevrilirken İngilizce
        kopya atılır (aynı tutarın iki kez görünmemesi için). Ağ maliyeti:
        bildirim başına 1 istek — yalnız adaylar için çağrılmalı.
        """
        pass

        detail = await self.detail(index)
        return body_text(detail.body_html), detail


MAX_RETRY_AFTER = 60.0


def _retry_after_seconds(response: httpx.Response, *, cap: float = MAX_RETRY_AFTER) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return min(cap, max(0.0, value))


# ==========================================================================
# Kaynak: bistman/sources/kap_companies.py
# ==========================================================================

BIST_COMPANIES_PATH = "/tr/bist-sirketler"
BIST_COMPANIES_URL = "https://www.kap.org.tr" + BIST_COMPANIES_PATH

# Ham HTML'de ters bölü ile kaçışlanmış JSON alanları (`\"` sınırı aşılmaz, `\u0130` korunur)
_COMPANY_PATTERN = re.compile(
    r'\\"mkkMemberOid\\":\\"((?:\\[^"]|[^"\\])+)\\",'
    r'\\"kapMemberTitle\\":\\"((?:\\[^"]|[^"\\])*)\\",'
    r'\\"relatedMemberTitle\\":\\"(?:\\[^"]|[^"\\])*\\",'
    r'\\"stockCode\\":\\"((?:\\[^"]|[^"\\])*)\\"'
)
# Next.js flight parçaları (`self.__next_f.push([1,"..."])`): tek bir şirket kaydı
# iki ayrı `<script>` bloğuna bölünebildiği için önce akış birleştirilir.
_NEXT_FLIGHT_CHUNK = re.compile(
    r'self\.__next_f\.push\(\[\s*1\s*,\s*"((?:\\.|[^"\\])*)"\s*\]\)'
)
_UNESCAPED_COMPANY_PATTERN = re.compile(
    r'"mkkMemberOid":"((?:\\.|[^"\\])+)",'
    r'"kapMemberTitle":"((?:\\.|[^"\\])*)",'
    r'"relatedMemberTitle":"(?:\\.|[^"\\])*",?'
    r'"stockCode":"((?:\\.|[^"\\])*)"'
)

# Çok pay gruplu BIST şirketlerinde ana likit tahta kodu (evren belirtilmediğinde).
_PREFERRED_SHARE_CLASS = frozenset({"ISCTR", "KRDMD"})


@dataclass(frozen=True, slots=True)
class CompanyEntry:
    """KAP şirket listesindeki tek hisse satırı (OID + resmî unvan)."""

    ticker: str
    oid: str
    title: str


class CompanyMapError(RuntimeError):
    """Şirket listesi alınamadı veya beklenen biçimde değil."""


def _unescape_json_str(raw: str) -> str:
    try:
        return str(json.loads(f'"{raw}"'))
    except json.JSONDecodeError:
        return raw


def _collect_matches(
    matches: Iterable[tuple[str, str, str]], out: dict[str, CompanyEntry]
) -> None:
    for raw_oid, raw_title, raw_codes in matches:
        oid = _unescape_json_str(raw_oid).strip()
        title = _unescape_json_str(raw_title).strip()
        for part in _unescape_json_str(raw_codes).split(","):
            ticker = part.strip().upper()
            if ticker and oid:
                out[ticker] = CompanyEntry(ticker=ticker, oid=oid, title=title)


def parse_companies(html: str) -> list[CompanyEntry]:
    """KAP `bist-sirketler` HTML'inden `(ticker, oid, unvan)` listesi çıkarır.

    Canlı `/api/disclosure/list/light` akışında hisse kodu yoktur; hem geçmiş
    sorgusu için OID hem de `TickerResolver` için resmî KAP unvanı aynı sayfadan gelir.
    İki ayrı `self.__next_f.push` parçasına bölünmüş kayıtlar da birleştirilerek çözülür.
    """
    if not html or "mkkMemberOid" not in html:
        raise CompanyMapError("sayfada mkkMemberOid yok (bot koruması veya biçim değişti)")
    by_ticker: dict[str, CompanyEntry] = {}
    _collect_matches(_COMPANY_PATTERN.findall(html), by_ticker)
    chunks = _NEXT_FLIGHT_CHUNK.findall(html)
    if chunks:
        joined_raw = "".join(chunks)
        _collect_matches(_COMPANY_PATTERN.findall(joined_raw), by_ticker)
        decoded = "".join(_unescape_json_str(c) for c in chunks)
        if '"mkkMemberOid":"' in decoded:
            _collect_matches(_UNESCAPED_COMPANY_PATTERN.findall(decoded), by_ticker)
    if not by_ticker:
        raise CompanyMapError("eşleme boş: desen sayfayla uyuşmuyor")
    return list(by_ticker.values())


def parse_company_map(html: str) -> dict[str, str]:
    """KAP `bist-sirketler` HTML'inden {ticker: oid} çıkarır.

    Ticker'lar büyük harfe çevrilir; aynı koda iki OID düşerse son kayıt kalır ama
    bu durum pratikte görülmez (kod tekil).
    """
    return {entry.ticker: entry.oid for entry in parse_companies(html)}


def select_primary_ticker(
    codes: Iterable[str],
    *,
    allowed: set[str] | None = None,
) -> str | None:
    """Aynı `mkkMemberOid`'e ait kodlar içinden birincil BIST pay kodunu seçer.

    Öncelik: (1) izlenen evrendeki kod, (2) çok pay gruplu şirketin ana tahtası
    (`ISCTR`, `KRDMD`), (3) 4–5 harfli standart BIST pay kodu (`GARAN` > `TGB`,
    `HALKB` > `THB`), (4) KAP listesindeki ilk sıra.
    """
    ordered = list(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))
    if not ordered:
        return None
    if allowed is not None:
        in_universe = [c for c in ordered if c in allowed]
        if in_universe:
            ordered = in_universe
    best_idx = min(
        range(len(ordered)),
        key=lambda idx: (
            0 if ordered[idx] in _PREFERRED_SHARE_CLASS else 1,
            0 if len(ordered[idx]) in {4, 5} and ordered[idx].isalpha() else 1,
            idx,
        ),
    )
    return ordered[best_idx]


def build_company_resolver(
    entries: Iterable[CompanyEntry],
    *,
    universe: Iterable[str] | None = None,
    preferred: Iterable[str] | None = None,
) -> TickerResolver:
    """`CompanyEntry` listesinden unvan→kod çözümleyici üretir.

    - `universe`: verilirse yalnız bu evrendeki kodlar çözümleyiciye alınır.
    - `preferred`: tüm BIST şirketlerini çözümleyicide tutarken (evren dışı
      şirketleri `dis_evren` olarak tanımak için) çok kodlu şirketlerde
      (`GARAN, TGB`, `ISA, ISB, ISCTR, ISKUR`, `KRDMA, KRDMB, KRDMD`) izlenen
      pay koduna öncelik verir; belirtilmezse ana tahta kodu (`ISCTR`, `KRDMD`,
      `GARAN`) seçilir.
    """
    allowed = {t.strip().upper() for t in universe} if universe is not None else None
    favored = (
        {t.strip().upper() for t in preferred}
        if preferred is not None
        else allowed
    )
    by_oid: dict[str, list[CompanyEntry]] = {}
    for entry in entries:
        if not entry.title:
            continue
        if allowed is not None and entry.ticker not in allowed:
            continue
        by_oid.setdefault(entry.oid, []).append(entry)
    pairs: list[tuple[str, str]] = []
    for group in by_oid.values():
        chosen = select_primary_ticker((e.ticker for e in group), allowed=favored)
        if chosen is None:
            continue
        title = next((e.title for e in group if e.ticker == chosen), group[0].title)
        pairs.append((chosen, title))
    return TickerResolver.from_pairs(pairs)


def missing_tickers(mapping: Mapping[str, str], wanted: Iterable[str]) -> list[str]:
    """İstenen evrenden eşleşmeyen kodlar (sessizce atlanmasın diye raporlanır)."""
    return [t for t in wanted if t.upper() not in mapping]


async def fetch_companies(client: object | None = None) -> list[CompanyEntry]:
    """KAP sayfasını indirip `(ticker, oid, unvan)` listesi döndürür."""
    if client is not None and hasattr(client, "get_text"):
        html = await client.get_text(BIST_COMPANIES_PATH)  # type: ignore[attr-defined]
    else:
        pass

        async with KapClient() as kap:
            html = await kap.get_text(BIST_COMPANIES_PATH)
    return parse_companies(html)


async def fetch_company_map(client: object | None = None) -> dict[str, str]:
    """KAP sayfasını indirip {ticker: oid} eşlemesini döndürür.

    `client`: `KapClient` benzeri, `get_text(url)` sunan nesne (test enjeksiyonu).
    """
    return {entry.ticker: entry.oid for entry in await fetch_companies(client)}


# ==========================================================================
# Kaynak: bistman/fundamentals.py
# ==========================================================================

@dataclass(frozen=True, slots=True)
class PublishedRow:
    row: FundamentalRow
    published_at: datetime | None  # dönem sonu değil, bu SÜRÜMÜN yayını


def period_at(row: FundamentalRow, at: datetime) -> date | None:
    try:
        end = date.fromisoformat(row.period_end)
    except (TypeError, ValueError):
        return None
    return end if end <= to_trt(at).date() else None


def statement_at(rows: Sequence[PublishedRow], ticker: str, at: datetime) -> PublishedRow | None:
    candidates = []
    for version in rows:
        ts = version.published_at
        if version.row.ticker != ticker or ts is None or ts.utcoffset() is None or ts > at:
            continue
        end = period_at(version.row, ts)
        if end is not None:
            candidates.append((end, ts, version))
    # En son dönem, o dönemin haber anında bilinen en son revizyonu.
    return max(candidates, key=lambda v: v[:2])[2] if candidates else None


Snapshot = FundamentalRow | Sequence[PublishedRow]


def scoring_snapshot(snapshot: Snapshot | None, ticker: str, at: datetime) -> tuple[FundamentalRow | None, str | None]:
    if not isinstance(snapshot, FundamentalRow):
        version = statement_at(snapshot or (), ticker, at)
        row = version.row if version else None
        note = None
    else:
        row, note = snapshot, "tek snapshot: tablo yayın saati doğrulanmadı"
    if row and (row.ticker != ticker or row.currency != "TRY" or period_at(row, at) is None):
        return None, "tablo hisse, dönem veya para birimiyle eşleşmedi"
    return row, note


# ==========================================================================
# Kaynak: bistman/context_packet.py
# ==========================================================================

Topic = Literal["satis_sozlesmesi", "uretim_durusu", "sirket_aciklamasi", "endeks_parametresi"]
Origin = Literal["kap_arsiv", "sentetik", "dogrulanmamis"]
MAX_CHARS = 1000  # Kompakt JSON'un Unicode karakterleri; token veya API maliyeti değil.
IMPLAUSIBLE_RATIO_PCT = 100.0
UNRELIABLE_TTM = frozenset({
    "ttm_gap", "data_gap", "unit_mismatch", "stale_fundamentals",
    "mixed_restatement_vintage", "assumed_mode", "bank_template_mismatch",
})


def _revenue_ratio_pct(amount_try: Decimal, revenue_ttm: Decimal) -> float | None:
    if amount_try <= 0 or revenue_ttm <= 0:
        return None
    try:
        pct = float((amount_try / revenue_ttm) * Decimal(100))
    except (InvalidOperation, OverflowError, ZeroDivisionError):
        return None
    return pct if math.isfinite(pct) and pct > 0 else None


class DisclosureItem(Protocol):
    """Paketleyici ve arşivin ihtiyaç duyduğu dar sözleşme (skor motoru şart değil)."""

    @property
    def disclosure(self) -> DisclosureStub: ...
    @property
    def route(self) -> Route: ...
    @property
    def status(self) -> str: ...
    @property
    def ticker(self) -> str | None: ...


@dataclass(frozen=True, slots=True)
class ArchiveCandidate:
    """Eski skor/bildirim hattına girmeden arşive yazılabilen yalın aday."""

    disclosure: DisclosureStub
    route: Route
    status: str
    ticker: str | None = None


def make_candidate(disclosure: DisclosureStub, ticker: str | None = None) -> ArchiveCandidate:
    """Ham bildirim + çözülmüş hisseden skorsuz `ArchiveCandidate` üretir."""
    r = route(disclosure.disclosure_class, disclosure.subject, disclosure.summary)
    if r is not Route.PIPELINE:
        status = {
            Route.ROUTINE: "filtered_routine",
            Route.MECHANICAL: "filtered_mechanical",
            Route.FUNDAMENTALS_REFRESH: "fundamentals_refresh",
        }[r]
        return ArchiveCandidate(disclosure, r, status, None)
    if is_index_agenda(disclosure.title, disclosure.subject, disclosure.tickers):
        return ArchiveCandidate(disclosure, r, "agenda", None)
    code = (ticker or "").strip().upper() or None
    if code is None:
        return ArchiveCandidate(disclosure, r, "unresolved_ticker", None)
    return ArchiveCandidate(disclosure, r, "no_fundamentals", code)


class PacketHeld(ValueError):
    """Eksik kimlik/kanıt: bu kayıt API'ye hazır değil. Mesajı denetim nedenidir."""


def compact_json(packet: dict[str, object]) -> str:
    return json.dumps(packet, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _sale_context(
    quote: str, record: Sequence[str], ticker: str, at: datetime, rows: Sequence[PublishedRow],
) -> dict[str, object]:
    amounts = find_amounts(quote)
    if len(amounts) != 1:
        # Konsorsiyum toplamı, şirket payı, eski/yeni bedel: en büyüğünü seçme.
        return {"sinir": "ana_tutar_belirsiz" if amounts else "tutar_verilmedi"}
    amount = event_amount(quote, contract=True).money
    if amount is None:
        return {"sinir": "ana_tutar_belirsiz"}
    full = event_amount(*record, contract=True).money
    if full is None or (full.amount, full.currency) != (amount.amount, amount.currency):
        raise PacketHeld("bedel_baglamla_celisiyor")
    if any(w.startswith("belirsiz_virgul_binlik:") for w in amount.warnings):
        return {"sinir": "tutar_bicimi_belirsiz"}
    fields: dict[str, object] = {"tutar": {"deger": str(amount.amount), "birim": amount.currency}}
    if amount.currency != "TRY":
        return {**fields, "sinir": "para_birimi_belirsiz" if amount.currency == "UNKNOWN" else "tarihli_kur_yok"}

    version = statement_at(rows, ticker, at)
    if version is None:
        return {**fields, "sinir": "haber_aninda_yayimlanmis_tablo_yok"}
    row = version.row
    revenue = row.revenue_ttm
    if (
        row.currency != "TRY" or row.statement_type != "industrial" or not row.source
        or revenue is None or not math.isfinite(revenue) or revenue <= 0
        or UNRELIABLE_TTM.intersection(row.flags)
    ):
        return {**fields, "sinir": "karsilastirilabilir_ttm_ciro_yok"}
    ratio = _revenue_ratio_pct(amount.amount, Decimal(str(revenue)))
    assert version.published_at is not None
    if ratio is None:
        return {**fields, "sinir": "oran_hesaplanamadi"}
    rounded_pct = round(ratio, 2) if ratio >= 0.005 else round(ratio, 6)
    fields["olcek"] = {
        "ttm_ciro_try": row.revenue_ttm, "bedel_ciro_yuzde": rounded_pct,
        "donem_sonu": row.period_end, "tablo_yayini": version.published_at.isoformat(),
        "kaynak": row.source,
    }
    if ratio > IMPLAUSIBLE_RATIO_PCT:
        return {**fields, "sinir": "oran_dogrulanmali"}
    return fields


def _starts_with_lowercase_word(quote: str) -> bool:
    stripped = quote.lstrip()
    return bool(stripped) and stripped[0].isalpha() and stripped[0].islower()


def _whole_excerpt(text: str, quote: str) -> bool:
    # Tüm alan (ör. noktasız KAP başlığı) ya da gerçek cümle/paragraf sınırları
    # arasında bir alıntı. O(1) sınır penceresiyle büyük gövdelerde karesel tarama yapmaz.
    # - '... yaptırım kararı bulunmamaktadır' içinden yalnız 'yaptırım kararı' alınamaz.
    # - 'İddiaların aksine Prof. Dr. Ahmet ...' içinden 'Ahmet ...' alınamaz.
    # - 'Örnek A.Ş. hakkında ceza ...' içinden 'hakkında ceza ...' alınamaz.
    # - 'Açıklamalar\nSon günlerde ...' gibi başlık sonrası paragraf başı geçerlidir.
    if text.strip() == quote:
        return True
    if not quote or not quote.endswith((".", "!", "?")) or _starts_with_lowercase_word(quote):
        return False
    qlen = len(quote)
    tlen = len(text)
    pos = text.find(quote)
    while pos != -1:
        end = pos + qlen
        if end == tlen or text[end].isspace():
            # Sağ sınır: alıntı bir kısaltma noktasıyla aynı satırda kesilmemiş olmalı.
            ws_end = end
            after_nl = False
            while ws_end < tlen and text[ws_end].isspace():
                if text[ws_end] == "\n":
                    after_nl = True
                    break
                ws_end += 1
            after_ok = (
                end == tlen
                or after_nl
                or not is_abbreviation_break(quote, text[end:min(tlen, ws_end + 64)])
            )
            if after_ok:
                # Sol sınır: metin/paragraf başı ya da kısaltma olmayan önceki cümle sonu.
                b_idx = pos
                before_nl = False
                while b_idx > 0 and text[b_idx - 1].isspace():
                    if text[b_idx - 1] == "\n":
                        before_nl = True
                    b_idx -= 1
                starts_paragraph = b_idx == 0 or before_nl
                starts_sentence = (
                    not starts_paragraph
                    and b_idx < pos
                    and text[b_idx - 1] in ".!?"
                    and not is_abbreviation_break(
                        text[max(0, b_idx - 128):pos],
                        text[pos:min(tlen, pos + 64)],
                    )
                )
                if starts_paragraph or starts_sentence:
                    return True
        pos = text.find(quote, pos + 1)
    return False


def build_packet(
    item: DisclosureItem, *, origin: Origin, topic: Topic, quote: str,
    detail: DisclosureDetail | None = None, statements: Sequence[PublishedRow] = (),
) -> dict[str, object]:
    """KAP kaydı veya açıkça sentetik girdiden tek paket; yetersizse `PacketHeld`.

    `origin` arşivi yükleyen tarafın bilgisidir; URL'den güven çıkarılmaz.
    `detail` kimliği denetlendikten sonra TR metnine çevrilir. Ana tutar yalnız seçilen
    satış sözleşmesi alıntısından okunur, başka paragraflardan taşınmaz.
    """
    d = item.disclosure
    if origin not in {"kap_arsiv", "sentetik"}:
        raise PacketHeld("kaynak_dogrulanmadi")
    if d.index <= 0 or d.published_at.utcoffset() is None:
        raise PacketHeld("kimlik_veya_yayin_zamani_eksik")

    ref = (f"https://www.kap.org.tr/tr/Bildirim/{d.index}" if origin == "kap_arsiv"
           else f"senaryo:{d.index}")
    published_at = d.published_at
    packet: dict[str, object] = {
        "konu": topic, "kaynak": ref, "yayin": published_at.astimezone(timezone.utc).isoformat(),
    }
    if topic == "endeks_parametresi":
        # Pilotun doğrulanmış dar piyasa sınıfı. Hissesiz her KAP/BİST kaydı
        # piyasa duyurusu değildir (ör. tek payda hak kullanımı/devre kesici).
        if item.ticker or not is_index_agenda(d.title, d.subject, d.tickers):
            raise PacketHeld("piyasa_kapsami_dogrulanmadi")
        packet.update(kapsam="piyasa_gundemi", kurum=d.title)
    elif topic in {"satis_sozlesmesi", "uretim_durusu", "sirket_aciklamasi"}:
        if item.status not in {"scored", "no_fundamentals"} or not item.ticker:
            raise PacketHeld(item.status)
        packet.update(kapsam="hisse", hisse=item.ticker)
    else:
        raise PacketHeld("konu_kapsam_disi")

    body = ""
    if detail is not None:
        if not detail.matches(d, item.ticker):
            raise PacketHeld("detay_kayit_uyusmazligi")
        body = body_text(detail.body_html)
        if d.minute_precision and not detail.stub.minute_precision:
            published_at = detail.stub.published_at
            packet["yayin"] = published_at.astimezone(timezone.utc).isoformat()

    if quote.strip() in {"", "-", "—"}:
        raise PacketHeld("olay_kaniti_eksik")
    sources = (("govde", body), ("ozet", d.summary), ("baslik", d.subject))
    matches = [(loc, text) for loc, text in sources if text and quote in text]
    if not matches:
        raise PacketHeld("alinti_kayitta_yok")
    location = next((loc for loc, text in matches if _whole_excerpt(text, quote)), None)
    if location is None:
        raise PacketHeld("alinti_cumle_sinirinda_degil")
    if d.subject == "İhale Süreci / Sonucu" and location != "govde":
        # Pilot kuralı: ihale sürecinin duyurulması, satışın kesinleşmesi değildir.
        raise PacketHeld("ihale_sonucu_icin_detay_gerekli")
    packet.update(kanit_yeri=location, kanit=quote)
    if topic == "satis_sozlesmesi":
        if issuer_signature(quote) != "sale" or sale_qualified(d.subject, d.summary or "", body):
            raise PacketHeld("satis_kaniti_yetersiz")
        assert item.ticker is not None
        packet.update(_sale_context(quote, (d.subject, d.summary or "", body), item.ticker, published_at, statements))
    elif topic == "uretim_durusu":
        if not stoppage_confirmed(quote) or stoppage_contradicted(d.subject, d.summary or "", body):
            raise PacketHeld("durus_kaniti_yetersiz")
    if len(compact_json(packet)) > MAX_CHARS:
        # Alıntının sonundaki bir olumsuzluğu/koşulu sessizce kesmemek için.
        raise PacketHeld("daha_kisa_tam_kanit_sec")
    return packet


# ==========================================================================
# Kaynak: bistman/alarm_context.py
# ==========================================================================

_TRT_TZ = timezone(timedelta(hours=3), name="TRT")


def seans_durumu(dt: datetime) -> str:
    """Yayın veya alarm anının BIST seans takvimindeki yerini belirler (TRT)."""
    trt_dt = dt.astimezone(_TRT_TZ)
    if trt_dt.weekday() in (5, 6):
        return "hafta_sonu"
    from datetime import time
    t = trt_dt.time()
    if time(10, 0) <= t <= time(18, 5):
        return "seans_ici"
    elif t < time(10, 0):
        return "seans_oncesi"
    else:
        return "seans_sonrasi"


DEFAULT_MAX_AGE = timedelta(days=7)  # takvim süresi; ölçülmüş bir önem eşiği değil
SQLITE_BUSY_TIMEOUT_MS = 5000

# Kaynak metin hiç değişmemişken yalnız alıntı/okuma seçiminden kaynaklanan hatalar:
# aynı kaynağın önceden doğrulanmış cevabını sessizce silmemeli.
_EDITORIAL_HOLDS = frozenset({
    "alinti_kayitta_yok",
    "alinti_cumle_sinirinda_degil",
    "olay_kaniti_eksik",
    "yalniz_baslik",
    "daha_kisa_tam_kanit_sec",
    "okuma_anlam_celiskisi",
})

# Sonuç/detay/inceleme beklediği için henüz cevap veremeyen aday nedenleri.
_PENDING_HOLDS = frozenset({
    "ihale_sonucu_icin_detay_gerekli",
    "detay_bekleniyor",
    "inceleme_bekleniyor",
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alarm_versions (
    origin TEXT NOT NULL, disclosure_id INTEGER NOT NULL, version BLOB NOT NULL,
    ticker TEXT NOT NULL, published TEXT NOT NULL, known TEXT NOT NULL,
    strength INTEGER NOT NULL, live INTEGER NOT NULL DEFAULT 1,
    minute_pub INTEGER NOT NULL DEFAULT 0,
    source_hash BLOB, valid_until TEXT, evidence TEXT, answer TEXT, held TEXT,
    CHECK ((answer IS NULL) = (evidence IS NULL) AND (answer IS NULL) != (held IS NULL)),
    PRIMARY KEY (origin, disclosure_id, version)
);
CREATE INDEX IF NOT EXISTS alarm_stock ON alarm_versions(origin, ticker, published DESC, disclosure_id DESC);
CREATE INDEX IF NOT EXISTS alarm_revision ON alarm_versions(origin, disclosure_id, strength, known);
CREATE TABLE IF NOT EXISTS alarm_replacements (
    origin TEXT NOT NULL, target INTEGER NOT NULL, replacement INTEGER NOT NULL,
    known TEXT NOT NULL, live INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (origin, target, replacement)
);
CREATE TABLE IF NOT EXISTS alarm_pending_replacements (
    origin TEXT NOT NULL, target INTEGER NOT NULL, replacement INTEGER NOT NULL,
    version BLOB NOT NULL, ticker TEXT NOT NULL, published TEXT NOT NULL,
    known TEXT NOT NULL, live INTEGER NOT NULL, minute_pub INTEGER NOT NULL DEFAULT 0,
    source_hash BLOB NOT NULL, valid_until TEXT, evidence TEXT NOT NULL, answer TEXT NOT NULL,
    PRIMARY KEY (origin, target, replacement, version)
);
CREATE TABLE IF NOT EXISTS alarm_scans (
    origin TEXT NOT NULL, observed TEXT NOT NULL, covered TEXT NOT NULL,
    CHECK (covered <= observed),
    PRIMARY KEY (origin, observed)
);
CREATE INDEX IF NOT EXISTS alarm_scan_lookup ON alarm_scans(origin, observed DESC);
CREATE TABLE IF NOT EXISTS alarm_seen (
    origin TEXT NOT NULL, disclosure_id INTEGER NOT NULL,
    fingerprint BLOB NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL,
    PRIMARY KEY (origin, disclosure_id)
);
CREATE TABLE IF NOT EXISTS alarm_companies (
    ticker TEXT PRIMARY KEY,
    oid TEXT NOT NULL,
    title TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""

# Canlı kayıtta (live=1) ilk kullanılabilir an korunur: ne ileri ne geri kayar.
# Yalnız açıkça sırasız geçmiş oynatmasında (live=0 + excluded.live=0) en erken an tutulur.
_INSERT = """
INSERT INTO alarm_versions(origin, disclosure_id, version, ticker, published, known,
                           strength, live, minute_pub, source_hash, valid_until, evidence, answer, held)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(origin, disclosure_id, version) DO UPDATE SET
    known = CASE WHEN alarm_versions.live = 0 AND excluded.live = 0
                 THEN min(alarm_versions.known, excluded.known)
                 ELSE alarm_versions.known END,
    live = max(alarm_versions.live, excluded.live)
"""

_INSERT_REPLACEMENT = """
INSERT INTO alarm_replacements(origin, target, replacement, known, live)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(origin, target, replacement) DO UPDATE SET
    known = CASE WHEN alarm_replacements.live = 0 AND excluded.live = 0
                 THEN min(alarm_replacements.known, excluded.known)
                 ELSE alarm_replacements.known END,
    live = max(alarm_replacements.live, excluded.live)
"""

# Önce alarm anında bilinen sürümler arasında tek kazanan gerekir. Daha güçlü,
# daha yeni ya da eşdeğer fakat farklı bir sürüm, kendisi BEKLET/yanlış hisse/
# geri çekilmiş/süresi dolmuş olsa da eski olumlu cevabı eler.
_SELECT = """
SELECT v.answer, v.published, v.disclosure_id FROM alarm_versions v
WHERE v.origin=:origin AND v.ticker=:ticker AND v.published BETWEEN :since AND :at
  AND v.known <= :at AND v.answer IS NOT NULL AND (v.valid_until IS NULL OR :at < v.valid_until)
  AND NOT EXISTS (
    SELECT 1 FROM alarm_versions other
    WHERE other.origin=v.origin AND other.disclosure_id=v.disclosure_id AND other.known <= :at
      AND (other.strength, other.known) >= (v.strength, v.known) AND other.version != v.version
  )
  AND NOT EXISTS (
    SELECT 1 FROM alarm_replacements r WHERE r.origin=v.origin AND r.target=v.disclosure_id AND r.known<=:at
  )
ORDER BY v.published DESC, v.disclosure_id DESC LIMIT 1
"""

# Seçilen doğrulanmış haberden DAHA YENİ, henüz detayı/incelemesi tamamlanmamış bildirim var mı?
_SELECT_NEWER_PENDING = """
SELECT v.disclosure_id, v.published FROM alarm_versions v
WHERE v.origin=:origin AND v.ticker=:ticker AND v.published BETWEEN :since AND :at
  AND v.known <= :at
  AND v.held IN ('ihale_sonucu_icin_detay_gerekli', 'detay_bekleniyor', 'inceleme_bekleniyor')
  AND (v.valid_until IS NULL OR :at < v.valid_until)
  AND (v.published, v.disclosure_id) > (:chosen_pub, :chosen_id)
  AND NOT EXISTS (
    SELECT 1 FROM alarm_versions other
    WHERE other.origin=v.origin AND other.disclosure_id=v.disclosure_id AND other.known <= :at
      AND (other.strength, other.known) > (v.strength, v.known)
  )
  AND NOT EXISTS (
    SELECT 1 FROM alarm_replacements r WHERE r.origin=v.origin AND r.target=v.disclosure_id AND r.known<=:at
  )
ORDER BY v.published DESC, v.disclosure_id DESC LIMIT 1
"""

# Cevap çıkmadığında, pencerede bu hisse için bekleyen/çelişen güncel aday var mı?
_SELECT_STATUS = """
SELECT v.held,
       EXISTS (
         SELECT 1 FROM alarm_versions eq
         WHERE eq.origin=v.origin AND eq.disclosure_id=v.disclosure_id
           AND eq.strength=v.strength AND eq.known=v.known AND eq.version!=v.version
       ) AS conflicted
FROM alarm_versions v
WHERE v.origin=:origin AND v.ticker=:ticker AND v.published BETWEEN :since AND :at
  AND v.known <= :at AND (v.valid_until IS NULL OR :at < v.valid_until)
  AND NOT EXISTS (
    SELECT 1 FROM alarm_versions other
    WHERE other.origin=v.origin AND other.disclosure_id=v.disclosure_id AND other.known <= :at
      AND (other.strength, other.known) > (v.strength, v.known)
  )
  AND NOT EXISTS (
    SELECT 1 FROM alarm_replacements r WHERE r.origin=v.origin AND r.target=v.disclosure_id AND r.known<=:at
  )
ORDER BY v.published DESC, v.disclosure_id DESC
"""


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("saat dilimli bir tarih-saat gerekli (ör. +03:00)")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    # SQL metin karşılaştırmasında sabit ofset ve mikrosaniye hassasiyeti.
    return _utc(value).isoformat(timespec="microseconds")


def _hash(parts: Sequence[object]) -> bytes:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).digest()


# BIST pay kodu: 3–5 karakter, harfle başlar ve biter (ör. SISE, THYAO, A1CAP, ISCTR).
# Rakamla biten endeks/varant kodları (XU100, THYAO1) elenir.
_EQUITY_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9]{1,3}[A-Z]$")


def _ticker(value: str) -> str:
    token = value.strip() if isinstance(value, str) else ""
    if not token or not token.isascii():
        raise ValueError("tek BIST hisse kodu gerekli (ör. MTRKS, BIST:MTRKS veya MTRKS.E)")
    symbol = token.upper().removeprefix("BIST:")
    if symbol.endswith(".E"):
        symbol = symbol[:-2]
    elif symbol.endswith(".IS"):
        symbol = symbol[:-3]
    if not _EQUITY_TICKER_RE.fullmatch(symbol):
        raise ValueError("tek BIST hisse kodu gerekli (ör. MTRKS, BIST:MTRKS veya MTRKS.E)")
    return symbol


def _check_origin(origin: Origin) -> None:
    if origin not in {"kap_arsiv", "sentetik"}:
        raise ValueError("doğrulanmamış kaynak; arşiv ile senaryo ayrı tutulur")


def _ensure_migrations(db: sqlite3.Connection) -> None:
    """Eski şemayla oluşturulmuş arşiv dosyalarına eksik sütunları güvenle ekler."""
    vcols = {row[1] for row in db.execute("PRAGMA table_info(alarm_versions)").fetchall()}
    if "live" not in vcols:
        db.execute("ALTER TABLE alarm_versions ADD COLUMN live INTEGER NOT NULL DEFAULT 1")
    if "minute_pub" not in vcols:
        db.execute("ALTER TABLE alarm_versions ADD COLUMN minute_pub INTEGER NOT NULL DEFAULT 0")
    if "source_hash" not in vcols:
        db.execute("ALTER TABLE alarm_versions ADD COLUMN source_hash BLOB")
    rcols = {row[1] for row in db.execute("PRAGMA table_info(alarm_replacements)").fetchall()}
    if "live" not in rcols:
        db.execute("ALTER TABLE alarm_replacements ADD COLUMN live INTEGER NOT NULL DEFAULT 1")
    if _has_table(db, "alarm_pending_replacements"):
        pcols = {
            row[1] for row in db.execute("PRAGMA table_info(alarm_pending_replacements)").fetchall()
        }
        if "minute_pub" not in pcols:
            db.execute(
                "ALTER TABLE alarm_pending_replacements "
                "ADD COLUMN minute_pub INTEGER NOT NULL DEFAULT 0"
            )


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


@dataclass(frozen=True, slots=True)
class ReviewedReading:
    """Editörün bu alıntı için yazdığı kısa okuma, alıntının kendisi değil."""

    event: str
    significance: str


def _reading(packet: dict, reviewed: ReviewedReading | None) -> dict:
    context = {"konu": packet["konu"], "olay": packet["kanit"],
               "yayin_zamani": packet["yayin"], "kaynak": packet["kaynak"]}
    if reviewed is not None:
        if packet["konu"] != "sirket_aciklamasi":
            raise ValueError("serbest okuma yalnız incelenmiş şirket açıklaması içindir")
        event, why = reviewed.event.strip(), reviewed.significance.strip()
        if not event or not why or len(event) + len(why) > 400:
            raise ValueError("olay ve önemi boş olamaz, toplam en çok 400 karakter olmalı")
        if polarity_inverted(str(packet["kanit"]), event, why):
            raise PacketHeld("okuma_anlam_celiskisi")
        context.update(olay=event, onemi=why)
    elif packet["konu"] == "satis_sozlesmesi":
        if packet.get("olcek") and not packet.get("sinir"):
            scale = packet["olcek"]
            ratio_val = float(scale["bedel_ciro_yuzde"])
            if 0 < ratio_val < 0.005:
                context["onemi"] = (
                    "Bedelin son 12 aylık ciroya oranı %0,01'den düşük; bu bir kâr tahmini değildir."
                )
            else:
                pct = format(round(ratio_val, 2), "g").replace(".", ",")
                context["onemi"] = f"Bedelin son 12 aylık ciroya oranı %{pct}; bu bir kâr tahmini değildir."
            context["mali_tablo"] = {"kaynak": scale["kaynak"], "donem_sonu": scale["donem_sonu"],
                                     "yayin_zamani": scale["tablo_yayini"]}
        elif packet.get("sinir") == "tarihli_kur_yok":
            context["onemi"] = "Teslimatlar satışları destekleyebilir; tarihli kur olmadan TL ciroyla kıyaslanamaz."
        else:
            context["onemi"] = "Teslimatlar satışları destekleyebilir; bedelin ciroya oranı doğrulanamadı."
    elif packet["konu"] == "uretim_durusu":
        context["onemi"] = "Teslimatlara etkisi duruşun süresine ve etkilenen kapasiteye bağlıdır."
    # Başka kanıt yoksa sadece tam alıntı; bağımsız neden/yön uydurma.
    return context


class AlarmArchive:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._lock = threading.RLock()

    def record(
        self, item: DisclosureItem, *, origin: Origin, known_at: datetime,
        topic: Topic, quote: str, detail: DisclosureDetail | None = None,
        statements: Sequence[PublishedRow] = (), valid_until: datetime | None = None,
        supersedes: int | None = None, reviewed: ReviewedReading | None = None,
        replay: bool = False, defer_missing_target: bool = False,
    ) -> str:
        """İncelenmiş sürümü sakla: `hazir`, `kapsam_disi`, `geri_cekildi` veya bekletme nedeni.

        `replay=False` (varsayılan canlı mod): sürümün ilk kaydedilen `known_at`
        saati kilitlenir; sonradan yayın saati verilse bile geriye çekilemez.
        `replay=True`: sırasız geçmiş kayıtlarını oynatırken en erken gözlemi tutar,
        ancak canlı kilitlenmiş bir kaydı yine de geriye tarihleyemez.
        `defer_missing_target=True`: `supersedes` hedefi henüz arşive girmemişse
        düzeltmeyi beklemeye alır; hedef geldiğinde doğrulayıp otomatik uygular.
        """
        _check_origin(origin)
        d = item.disclosure
        exact_from_detail = (
            detail is not None and d.minute_precision and not detail.stub.minute_precision
            and detail.matches_record(d)
        )
        eff_published = detail.stub.published_at if exact_from_detail else d.published_at
        minute_pub = int(d.minute_precision and not exact_from_detail)
        published, known = _stamp(eff_published), _stamp(known_at)
        until = _stamp(valid_until) if valid_until is not None else None
        if d.index <= 0 or known < published or (until is not None and until < published):
            raise ValueError("geçersiz bildirim kimliği veya yayın/sürüm zamanı")
        live = 0 if replay else 1

        out_of_scope = (
            item.route != Route.PIPELINE
            or item.status not in {"scored", "no_fundamentals"}
            or not item.ticker
            or topic == "endeks_parametresi"
        )
        if out_of_scope:
            if detail is not None and not detail.matches_record(d):
                raise ValueError("detay kaydı uyuşmadı")
            return self._retract_if_present(
                origin, d.index, published, known, live=live,
                minute_precision=d.minute_precision, reason="kapsam_disi_geri_cekildi",
            )

        assert item.ticker is not None
        ticker = _ticker(item.ticker)
        if d.tickers and set(d.tickers) != {ticker}:
            raise ValueError("yapısal hisse uyuşmadı")
        if detail is not None and not detail.matches(d, ticker):
            raise ValueError("detay kaydı uyuşmadı")  # yabancı gövde var olan kaydı da bastıramaz
        body = body_text(detail.body_html) if detail is not None else ""
        source_hash = _hash([ticker, published, d.subject, d.summary, body])
        body_evidence = False
        try:
            packet = build_packet(item, origin=origin, topic=topic, quote=quote,
                                  detail=detail, statements=statements)
            if packet["kanit_yeri"] == "baslik" or quote.strip() == d.subject.strip():
                raise PacketHeld("yalniz_baslik")
            answer_dict = _reading(packet, reviewed)
        except PacketHeld as exc:
            evidence = answer = None
            held = str(exc)
            qualified = (
                (topic == "satis_sozlesmesi" and sale_qualified(d.subject, d.summary or "", body))
                or (topic == "uretim_durusu" and stoppage_contradicted(d.subject, d.summary or "", body))
            )
            strength = int(bool(body) or qualified)
        else:
            body_evidence = packet["kanit_yeri"] == "govde"
            strength = int(body_evidence)  # ilgisiz bir gövdenin varlığı, özeti güçlendirmez
            evidence, answer = compact_json(packet), compact_json(answer_dict)
            held = None

        identity = [ticker, published, until, strength, d.subject, d.summary, body,
                    evidence, answer, held, supersedes]
        version = _hash(identity)

        with self._lock, self._db:
            if held in _EDITORIAL_HOLDS and supersedes is None:
                # Kaynak metin birebir aynıyken yanlış alıntı/okuma verilmişse
                # önceden doğrulanmış cevabı ezme; kaynaktaki gerçek değişiklikse yaz.
                same_source_ok = self._db.execute(
                    "SELECT 1 FROM alarm_versions WHERE origin=? AND disclosure_id=? "
                    "AND source_hash=? AND answer IS NOT NULL LIMIT 1",
                    (origin, d.index, source_hash),
                ).fetchone()
                if same_source_ok is not None:
                    return held

            if supersedes is not None:
                if not body_evidence or evidence is None or answer is None:
                    raise ValueError("düzeltme için doğrulanmış gövde kanıtı gerekli")
                status = self._prepare_replacement(
                    origin=origin, target=supersedes, replacement=d.index,
                    version=version, ticker=ticker, published=published, known=known,
                    live=live, minute_pub=minute_pub, source_hash=source_hash,
                    valid_until=until, evidence=evidence, answer=answer,
                    defer_missing=defer_missing_target,
                )
                if status == "hedef_bekleniyor":
                    return status

            self._db.execute(_INSERT, (
                origin, d.index, version, ticker, published, known,
                strength, live, minute_pub, source_hash, until, evidence, answer, held,
            ))

            if answer is not None:
                self._resolve_pending_for(origin, d.index, ticker, published, known)

            conflict = self._db.execute("""
                SELECT 1 FROM alarm_versions v
                JOIN alarm_versions other USING (origin, disclosure_id, strength, known)
                WHERE v.origin=? AND v.disclosure_id=? AND v.version=? AND other.version!=v.version
                LIMIT 1
            """, (origin, d.index, version)).fetchone()
        return "surum_celiskisi" if conflict else (held or "hazir")

    def retract(
        self, disclosure_id: int, *, published_at: datetime, known_at: datetime,
        reason: str = "yanlis_atif", origin: Origin = "kap_arsiv",
        replay: bool = False, minute_precision: bool = False,
    ) -> str:
        """Önceden yazılmış yanlış atıflı/çok hisseli kaydı öğrenildiği andan itibaren geri çeker."""
        _check_origin(origin)
        published, known = _stamp(published_at), _stamp(known_at)
        if disclosure_id <= 0 or known < published:
            raise ValueError("geçersiz bildirim kimliği veya geri çekme zamanı")
        clean_reason = reason.strip() or "yanlis_atif"
        return self._retract_if_present(
            origin, disclosure_id, published, known, live=0 if replay else 1,
            minute_precision=minute_precision, reason=clean_reason,
        )

    def _retract_if_present(
        self, origin: Origin, disclosure_id: int, published: str, known: str,
        *, live: int, minute_precision: bool, reason: str,
    ) -> str:
        with self._lock, self._db:
            rows = self._db.execute(
                "SELECT published, strength, ticker, minute_pub FROM alarm_versions "
                "WHERE origin=? AND disclosure_id=?",
                (origin, disclosure_id),
            ).fetchall()
            active = [r for r in rows if r[2] != ""]
            if not active:
                return "kapsam_disi"
            stored_pub = active[0][0]
            any_minute = minute_precision or any(bool(r[3]) for r in active)
            same_time = stored_pub == published or (
                any_minute and stored_pub[:16] == published[:16]
            )
            if not same_time:
                raise ValueError("geri çekme yayın zamanı mevcut kayıtla uyuşmadı")
            # Eski özet veya gövde kaydı tekrar oynatılsa bile geri çekmeyi aşamasın.
            strength = max(1, max(r[1] for r in active))
            version = _hash(["", published, strength, reason])
            self._db.execute(_INSERT, (
                origin, disclosure_id, version, "", published, known,
                strength, live, int(minute_precision), None, None, None, None, reason,
            ))
        return "geri_cekildi"

    def record_pending(
        self, disclosure: DisclosureStub, *, ticker: str, known_at: datetime,
        reason: str = "detay_bekleniyor", origin: Origin = "kap_arsiv", replay: bool = False,
    ) -> str:
        """Henüz detayı/incelemesi tamamlanmamış adayı cevap uydurmadan işaretler.

        `strength = -1` ile yazıldığı için aynı `known_at` anında bile doğrulanmış
        özet (`0`) veya gövde (`1`) kaydıyla çakışma üretmez; kanıt geldiği anda ezilir.
        """
        _check_origin(origin)
        symbol = _ticker(ticker)
        published, known = _stamp(disclosure.published_at), _stamp(known_at)
        if disclosure.index <= 0 or known < published:
            raise ValueError("geçersiz bildirim kimliği veya bekleme zamanı")
        if reason not in _PENDING_HOLDS:
            raise ValueError("geçersiz bekleme nedeni")
        live = 0 if replay else 1
        minute_pub = int(disclosure.minute_precision)
        version = _hash([symbol, published, -1, disclosure.subject, disclosure.summary, reason])
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT 1 FROM alarm_versions WHERE origin=? AND disclosure_id=? "
                "AND answer IS NOT NULL LIMIT 1",
                (origin, disclosure.index),
            ).fetchone()
            if existing is not None:
                return "zaten_hazir"
            self._db.execute(_INSERT, (
                origin, disclosure.index, version, symbol, published, known,
                -1, live, minute_pub, None, None, None, None, reason,
            ))
        return reason

    def record_scan(
        self, covered_until: datetime, *, observed_at: datetime | None = None,
        origin: Origin = "kap_arsiv",
    ) -> None:
        """Başarılı bir taramanın hangi yayın anına kadar kapsadığını kaydeder."""
        _check_origin(origin)
        covered = _stamp(covered_until)
        observed = _stamp(observed_at) if observed_at is not None else covered
        if covered > observed:
            raise ValueError("taranan dönem gözlem zamanını aşamaz")
        with self._lock, self._db:
            self._db.execute("""
                INSERT INTO alarm_scans(origin, observed, covered) VALUES (?, ?, ?)
                ON CONFLICT(origin, observed) DO UPDATE SET covered = max(covered, excluded.covered)
            """, (origin, observed, covered))

    def last_scan(
        self, at: datetime | None = None, *, origin: Origin = "kap_arsiv",
    ) -> datetime | None:
        """Verilen anda (veya en son) bilinen en ileri başarılı tarama zamanı."""
        _check_origin(origin)
        with self._lock:
            if not _has_table(self._db, "alarm_scans"):
                return None
            if at is None:
                row = self._db.execute(
                    "SELECT max(covered) FROM alarm_scans WHERE origin=?", (origin,)
                ).fetchone()
            else:
                row = self._db.execute(
                    "SELECT max(covered) FROM alarm_scans WHERE origin=? AND observed<=?",
                    (origin, _stamp(at)),
                ).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def seen_status(
        self, disclosure_id: int, fingerprint: bytes, *, origin: Origin = "kap_arsiv",
    ) -> str | None:
        """Toplayıcı tekrar kontrolü: aynı parmak iziyle işlenmişse durumunu döndürür."""
        _check_origin(origin)
        with self._lock:
            if not _has_table(self._db, "alarm_seen"):
                return None
            row = self._db.execute(
                "SELECT fingerprint, status FROM alarm_seen WHERE origin=? AND disclosure_id=?",
                (origin, disclosure_id),
            ).fetchone()
        if row is None or row[0] != fingerprint:
            return None
        return str(row[1])

    def mark_seen(
        self, disclosure_id: int, fingerprint: bytes, status: str, *,
        updated_at: datetime, origin: Origin = "kap_arsiv",
    ) -> None:
        """Toplayıcı işlem izini saklar (yeniden başlatmada gereksiz detay indirmeyi önler)."""
        _check_origin(origin)
        with self._lock, self._db:
            self._db.execute("""
                INSERT INTO alarm_seen(origin, disclosure_id, fingerprint, status, updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(origin, disclosure_id) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    status = excluded.status,
                    updated = excluded.updated
            """, (origin, disclosure_id, fingerprint, status, _stamp(updated_at)))

    def _prepare_replacement(
        self, *, origin: Origin, target: int, replacement: int, version: bytes,
        ticker: str, published: str, known: str, live: int, minute_pub: int,
        source_hash: bytes, valid_until: str | None, evidence: str, answer: str,
        defer_missing: bool,
    ) -> str:
        if target <= 0 or target == replacement:
            raise ValueError("düzeltme hedefi bu hisseye ait, o anda bilinen önceki bir kayıt değil")
        # Hedefte daha önce hisse düzeltmesi yapılmışsa güncel kazanan sürüme bakılır.
        prior = self._db.execute("""
            SELECT DISTINCT v.ticker, v.published FROM alarm_versions v
            WHERE v.origin=? AND v.disclosure_id=? AND v.known<=?
              AND NOT EXISTS (
                SELECT 1 FROM alarm_versions other
                WHERE other.origin=v.origin AND other.disclosure_id=v.disclosure_id
                  AND other.known<=? AND (other.strength, other.known) > (v.strength, v.known)
              )
        """, (origin, target, known, known)).fetchall()
        if not prior:
            any_target = self._db.execute(
                "SELECT 1 FROM alarm_versions WHERE origin=? AND disclosure_id=? LIMIT 1",
                (origin, target),
            ).fetchone()
            if defer_missing and any_target is None:
                self._db.execute("""
                    INSERT INTO alarm_pending_replacements(
                        origin, target, replacement, version, ticker, published,
                        known, live, minute_pub, source_hash, valid_until, evidence, answer
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(origin, target, replacement, version) DO UPDATE SET
                        known = CASE WHEN alarm_pending_replacements.live = 0 AND excluded.live = 0
                                     THEN min(alarm_pending_replacements.known, excluded.known)
                                     ELSE alarm_pending_replacements.known END,
                        live = max(alarm_pending_replacements.live, excluded.live),
                        minute_pub = min(alarm_pending_replacements.minute_pub, excluded.minute_pub)
                """, (
                    origin, target, replacement, version, ticker, published,
                    known, live, minute_pub, source_hash, valid_until, evidence, answer,
                ))
                return "hedef_bekleniyor"
            raise ValueError("düzeltme hedefi bu hisseye ait, o anda bilinen önceki bir kayıt değil")
        if (
            len(prior) != 1
            or not prior[0][0]
            or prior[0][0] != ticker
            or (prior[0][1], target) >= (published, replacement)
        ):
            raise ValueError("düzeltme hedefi bu hisseye ait, o anda bilinen önceki bir kayıt değil")
        self._db.execute(_INSERT_REPLACEMENT, (origin, target, replacement, known, live))
        return "baglandi"

    def _resolve_pending_for(
        self, origin: Origin, target: int, ticker: str, published: str, known: str,
    ) -> None:
        """Sırasız gelip hedefini bekleyen düzeltmeleri hedef doğrulandığında uygular."""
        pending = self._db.execute("""
            SELECT replacement, version, ticker, published, known, live,
                   minute_pub, source_hash, valid_until, evidence, answer
            FROM alarm_pending_replacements WHERE origin=? AND target=?
        """, (origin, target)).fetchall()
        if not pending:
            return
        for (rep, ver, rep_ticker, rep_pub, rep_known, rep_live, rep_minute,
             rep_src, rep_until, rep_ev, rep_ans) in pending:
            if rep_ticker == ticker and (published, target) < (rep_pub, rep):
                # Bağ, hem hedef hem düzeltme bilindiği andan itibaren geçerlidir.
                eff_known = max(known, rep_known)
                self._db.execute(_INSERT, (
                    origin, rep, ver, rep_ticker, rep_pub, eff_known,
                    1, rep_live, rep_minute, rep_src, rep_until, rep_ev, rep_ans, None,
                ))
                self._db.execute(
                    _INSERT_REPLACEMENT, (origin, target, rep, eff_known, rep_live)
                )
            # Eşleşmeyen (yanlış hisse / eski tarih) bekleyen düzeltme yayımlanmadan düşürülür.
            self._db.execute(
                "DELETE FROM alarm_pending_replacements WHERE origin=? AND target=? "
                "AND replacement=? AND version=?",
                (origin, target, rep, ver),
            )

    def _empty_reason(
        self, origin: Origin, ticker: str, at_stamp: str, since_stamp: str,
    ) -> tuple[str, str | None]:
        params = dict(origin=origin, ticker=ticker, at=at_stamp, since=since_stamp)
        candidates = self._db.execute(_SELECT_STATUS, params).fetchall()
        if any(conflicted for _, conflicted in candidates):
            reason: str | None = "surum_celiskisi"
        elif any(held in _PENDING_HOLDS for held, _ in candidates):
            reason = "detay_bekleniyor"
        else:
            reason = None

        scanned: str | None = None
        if _has_table(self._db, "alarm_scans"):
            row = self._db.execute(
                "SELECT max(covered) FROM alarm_scans WHERE origin=? AND observed<=?",
                (origin, at_stamp),
            ).fetchone()
            scanned = row[0] if row and row[0] else None

        if reason is None:
            if scanned is None:
                reason = "tarama_kaydi_yok"
            elif scanned < at_stamp:
                reason = "tarama_geride"
            else:
                reason = "uygun_gelisme_yok"
        scan_iso = datetime.fromisoformat(scanned).isoformat() if scanned else None
        return reason, scan_iso

    def save_companies(
        self, entries: Sequence[CompanyEntry], *, updated_at: datetime | None = None,
    ) -> int:
        """KAP şirket listesini (kod, OID, unvan) yerel SQLite önbelleğine yazar."""
        if not entries:
            return 0
        stamp = _stamp(updated_at or datetime.now(timezone.utc))
        rows = [(e.ticker, e.oid, e.title, stamp) for e in entries if e.ticker and e.oid]
        if not rows:
            return 0
        with self._lock, self._db:
            self._db.execute("DELETE FROM alarm_companies")
            self._db.executemany(
                "INSERT INTO alarm_companies(ticker, oid, title, updated) VALUES (?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def load_companies(
        self,
        *,
        as_of: datetime | None = None,
        max_age: timedelta | None = timedelta(hours=24),
    ) -> list[CompanyEntry]:
        """Önbellekteki şirket listesini döndürür (`max_age=None` bayat yedeği de verir)."""
        with self._lock:
            if not _has_table(self._db, "alarm_companies"):
                return []
            rows = self._db.execute(
                "SELECT ticker, oid, title, updated FROM alarm_companies ORDER BY ticker"
            ).fetchall()
        if not rows:
            return []
        if max_age is not None:
            now = _utc(as_of) if as_of is not None else datetime.now(timezone.utc)
            updated = datetime.fromisoformat(rows[0][3])
            if now - updated > max_age:
                return []
        return [CompanyEntry(ticker=r[0], oid=r[1], title=r[2]) for r in rows]

    def prune(
        self,
        as_of: datetime | None = None,
        *,
        seen_days: int = 14,
        version_days: int | None = 30,
        origin: Origin | None = None,
    ) -> dict[str, int]:
        """7/24 çalışan ortamda eski imleç/tarama/sürüm kayıtlarını güvenle budar.

        Her kaynak için en son `alarm_scans` satırı her zaman korunur; böylece
        tarama damgası kaybolmaz. `version_days=None` verilirse sürümler silinmez.
        """
        if origin is not None:
            _check_origin(origin)
        if seen_days <= 0 or (version_days is not None and version_days < 8):
            raise ValueError("seen_days > 0 ve version_days >= 8 (veya None) olmalı")
        now = _utc(as_of) if as_of is not None else datetime.now(timezone.utc)
        seen_cutoff = _stamp(now - timedelta(days=seen_days))
        origins = (origin,) if origin is not None else ("kap_arsiv", "sentetik")
        deleted = {"seen": 0, "scans": 0, "pending_replacements": 0, "versions": 0, "replacements": 0}
        with self._lock, self._db:
            for org in origins:
                deleted["seen"] += self._db.execute(
                    "DELETE FROM alarm_seen WHERE origin=? AND updated < ?",
                    (org, seen_cutoff),
                ).rowcount
                deleted["scans"] += self._db.execute(
                    """
                    DELETE FROM alarm_scans WHERE origin=? AND observed < ?
                      AND observed != (SELECT max(observed) FROM alarm_scans WHERE origin=?)
                      AND covered != (SELECT max(covered) FROM alarm_scans WHERE origin=?)
                    """,
                    (org, seen_cutoff, org, org),
                ).rowcount
                deleted["pending_replacements"] += self._db.execute(
                    "DELETE FROM alarm_pending_replacements WHERE origin=? AND known < ?",
                    (org, seen_cutoff),
                ).rowcount
                if version_days is not None:
                    ver_cutoff = _stamp(now - timedelta(days=version_days))
                    deleted["versions"] += self._db.execute(
                        "DELETE FROM alarm_versions WHERE origin=? AND published < ? AND known < ?",
                        (org, ver_cutoff, ver_cutoff),
                    ).rowcount
                    deleted["replacements"] += self._db.execute(
                        """
                        DELETE FROM alarm_replacements WHERE origin=? AND known < ?
                          AND NOT EXISTS (
                            SELECT 1 FROM alarm_versions v
                            WHERE v.origin=alarm_replacements.origin
                              AND v.disclosure_id=alarm_replacements.target
                          )
                        """,
                        (org, ver_cutoff),
                    ).rowcount
        return deleted

    def stats(self, *, origin: Origin = "kap_arsiv") -> dict[str, object]:
        """Arşivin durumunu ve sağlık metriklerini raporlar (salt okunur)."""
        _check_origin(origin)
        with self._lock:
            scanned: str | None = None
            if _has_table(self._db, "alarm_scans"):
                row = self._db.execute(
                    "SELECT max(covered) FROM alarm_scans WHERE origin=?", (origin,)
                ).fetchone()
                if row and row[0]:
                    scanned = str(row[0])

            total_seen = 0
            seen_by_status: dict[str, int] = {}
            if _has_table(self._db, "alarm_seen"):
                r_seen = self._db.execute(
                    "SELECT count(*) FROM alarm_seen WHERE origin=?", (origin,)
                ).fetchone()
                total_seen = int(r_seen[0]) if r_seen else 0
                for st, cnt in self._db.execute(
                    "SELECT status, count(*) FROM alarm_seen WHERE origin=? GROUP BY status", (origin,)
                ):
                    seen_by_status[str(st)] = int(cnt)

            total_versions = 0
            ready_versions = 0
            held_versions = 0
            if _has_table(self._db, "alarm_versions"):
                r_ver = self._db.execute(
                    "SELECT count(*) FROM alarm_versions WHERE origin=?", (origin,)
                ).fetchone()
                total_versions = int(r_ver[0]) if r_ver else 0
                r_rdy = self._db.execute(
                    "SELECT count(*) FROM alarm_versions WHERE origin=? AND answer IS NOT NULL", (origin,)
                ).fetchone()
                ready_versions = int(r_rdy[0]) if r_rdy else 0
                r_hld = self._db.execute(
                    "SELECT count(*) FROM alarm_versions WHERE origin=? AND held IS NOT NULL", (origin,)
                ).fetchone()
                held_versions = int(r_hld[0]) if r_hld else 0

            companies_count = 0
            companies_updated: str | None = None
            if _has_table(self._db, "alarm_companies"):
                r_cmp = self._db.execute("SELECT count(*), max(updated) FROM alarm_companies").fetchone()
                if r_cmp and r_cmp[0] is not None:
                    companies_count = int(r_cmp[0])
                    companies_updated = str(r_cmp[1]) if r_cmp[1] else None

            return {
                "origin": origin,
                "son_tarama": scanned,
                "toplam_gorulen": total_seen,
                "gorulen_durumlari": seen_by_status,
                "toplam_surum": total_versions,
                "hazir_baglam": ready_versions,
                "bekletilen_surum": held_versions,
                "kayitli_sirket": companies_count,
                "sirket_listesi_guncelleme": companies_updated,
            }

    def sirket_profili(
        self, hisse: str, alarm_zamani: datetime, *, days: int = 30,
        origin: Origin = "kap_arsiv",
    ) -> dict[str, object]:
        """Hissenin son `days` gün içindeki KAP bildirim sıklığı ve alışkanlık profili."""
        _check_origin(origin)
        if days <= 0:
            raise ValueError("gün sayısı pozitif olmalı")
        ticker, at = _ticker(hisse), _utc(alarm_zamani)
        at_stamp = _stamp(at)
        since_stamp = _stamp(at - timedelta(days=days))
        with self._lock:
            if not _has_table(self._db, "alarm_versions"):
                return {"hisse": ticker, "son_30_gun_bildirim_sayisi": 0, "aliskanlik": "seyrek"}
            row = self._db.execute(
                """
                SELECT count(DISTINCT disclosure_id)
                FROM alarm_versions
                WHERE origin=? AND ticker=? AND published BETWEEN ? AND ?
                  AND known <= ? AND answer IS NOT NULL
                """,
                (origin, ticker, since_stamp, at_stamp, at_stamp),
            ).fetchone()
            count = int(row[0]) if row and row[0] is not None else 0
            if count <= 1:
                aliskanlik = "seyrek"
            elif count <= 4:
                aliskanlik = "normal"
            else:
                aliskanlik = "sik"
            return {
                "hisse": ticker,
                f"son_{days}_gun_bildirim_sayisi": count,
                "aliskanlik": aliskanlik,
            }

    def sessizlik_bilgisi(
        self, hisse: str, alarm_zamani: datetime, *, origin: Origin = "kap_arsiv",
    ) -> dict[str, object] | None:
        """Hissenin alarm anından önceki son doğrulanmış bildiriminden bu yana geçen süreyi hesaplar."""
        _check_origin(origin)
        ticker, at = _ticker(hisse), _utc(alarm_zamani)
        at_stamp = _stamp(at)
        with self._lock:
            if not _has_table(self._db, "alarm_versions"):
                return None
            row = self._db.execute(
                """
                SELECT max(published)
                FROM alarm_versions
                WHERE origin=? AND ticker=? AND published <= ? AND known <= ? AND answer IS NOT NULL
                """,
                (origin, ticker, at_stamp, at_stamp),
            ).fetchone()
            if row and row[0]:
                last_dt = datetime.fromisoformat(row[0])
                diff_sec = max(0.0, (at - last_dt).total_seconds())
                return {
                    "sessizlik_gun": round(diff_sec / 86400, 1),
                    "son_bildirim_tarihi": row[0],
                }
            return None

    def revizyon_bilgisi(
        self, disclosure_id: int, *, origin: Origin = "kap_arsiv",
    ) -> dict[str, object] | None:
        """Bildirimin bir önceki düzeltilen hedefi varsa özetler."""
        _check_origin(origin)
        with self._lock:
            if not _has_table(self._db, "alarm_replacements"):
                return None
            row = self._db.execute(
                "SELECT target FROM alarm_replacements WHERE origin=? AND replacement=?",
                (origin, disclosure_id),
            ).fetchone()
            if row and row[0]:
                t_id = int(row[0])
                return {
                    "tur": "duzeltme",
                    "duzeltilen_bildirim_id": t_id,
                    "duzeltilen_kaynak": (
                        f"https://www.kap.org.tr/tr/Bildirim/{t_id}"
                        if origin == "kap_arsiv" else f"senaryo:{t_id}"
                    ),
                }
            return None

    def alarm_baglami(
        self, hisse: str, alarm_zamani: datetime, *, max_age: timedelta = DEFAULT_MAX_AGE,
        origin: Origin = "kap_arsiv",
    ) -> dict[str, object]:
        """Tek dış alarma en çok bir kaynaklı gelişme. Yazma, gönderim, ağ erişimi yok."""
        _check_origin(origin)
        ticker, at = _ticker(hisse), _utc(alarm_zamani)
        if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
            raise ValueError("güncellik penceresi pozitif olmalı")
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        since = at - min(max_age, at - earliest)
        at_stamp, since_stamp = _stamp(at), _stamp(since)
        with self._lock:
            row = self._db.execute(
                _SELECT, dict(origin=origin, ticker=ticker, at=at_stamp, since=since_stamp)
            ).fetchone()
            head: dict[str, object] = {"hisse": ticker, "alarm_zamani": at.isoformat()}
            if row is not None:
                newer = self._db.execute(
                    _SELECT_NEWER_PENDING,
                    dict(origin=origin, ticker=ticker, at=at_stamp, since=since_stamp,
                         chosen_pub=row[1], chosen_id=row[2]),
                ).fetchone()
                baglam_obj = json.loads(row[0])
                pub_dt = datetime.fromisoformat(row[1])
                baglam_obj["seans_durumu"] = seans_durumu(pub_dt)
                chosen_disc_id = int(row[2])
                rev = self.revizyon_bilgisi(chosen_disc_id, origin=origin)
                if rev is not None:
                    baglam_obj["revizyon"] = rev
                out_var: dict[str, object] = {
                    **head,
                    "durum": "var",
                    "baglam": baglam_obj,
                    "sirket_profili": self.sirket_profili(ticker, at, origin=origin),
                }
                if newer is not None:
                    p_id, p_pub = int(newer[0]), str(newer[1])
                    ref = (f"https://www.kap.org.tr/tr/Bildirim/{p_id}"
                           if origin == "kap_arsiv" else f"senaryo:{p_id}")
                    out_var["bekleyen_bildirim"] = {
                        "kaynak": ref,
                        "yayin_zamani": datetime.fromisoformat(p_pub).isoformat(),
                        "neden": "detay_bekleniyor",
                    }
                return out_var
            reason, scan_iso = self._empty_reason(origin, ticker, at_stamp, since_stamp)
            sessizlik = self.sessizlik_bilgisi(ticker, at, origin=origin)
        out: dict[str, object] = {
            **head,
            "durum": "yok",
            "baglam": None,
            "neden": reason,
            "mesaj": "İlgili güncel gelişme bulunamadı.",
        }
        if sessizlik is not None:
            out["sessizlik"] = sessizlik
        if scan_iso is not None:
            out["son_tarama"] = scan_iso
        return out


@contextmanager
def open_archive(path: str | Path, *, writable: bool = False) -> Iterator[AlarmArchive]:
    """Varsayılan salt okunur: olmayan arşivi oluşturup 'haber yok' deme.

    Yazılabilir bağlantıda WAL ve `busy_timeout` açılır; böylece arka plan
    toplayıcısı yazarken grafik alarmı sorgusu kilitlenmeden okuyabilir.
    """
    if writable:
        db = sqlite3.connect(
            path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000, check_same_thread=False
        )
    else:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        db = sqlite3.connect(
            uri, uri=True, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000, check_same_thread=False
        )
    try:
        db.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        if writable:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(_SCHEMA)
            _ensure_migrations(db)
        else:
            db.execute("PRAGMA query_only = ON")
        yield AlarmArchive(db)
    finally:
        if writable:
            try:
                # PASSIVE açık okuyucuları bloklamadan hazır sayfaları aktarır.
                db.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                pass
        db.close()


def kap_baglami_ekle(
    yorum_istegi: dict[str, object],
    arsiv_yolu: str | Path,
    hisse: str,
    tetik_zamani: datetime,
    *,
    max_age: timedelta = DEFAULT_MAX_AGE,
    origin: Origin = "kap_arsiv",
    logger: logging.Logger | None = None,
) -> dict[str, object] | None:
    """Ana sistemin mevcut grafik alarmı yorum isteğine doğrulanmış KAP bağlamı ekler.

    - `durum == "var"` ise `yorum_istegi["kap_baglami"]` doldurulur.
    - `durum == "yok"` veya hata durumunda önceki çağrıdan kalmış `kap_baglami` /
      `kap_bekleyen_bildirim` anahtarları temizlenir (yeniden kullanılan sözlük güvenliği).
    - Arşiv/girdi hatasında `'haber yok'` uydurulmaz; hata loglanır, `None` döner ve
      grafik alarmı kendi akışına kesintisiz devam eder.
    """
    yorum_istegi.pop("kap_baglami", None)
    yorum_istegi.pop("kap_bekleyen_bildirim", None)
    yorum_istegi.pop("kap_sirket_profili", None)
    yorum_istegi.pop("kap_sessizlik", None)
    try:
        with open_archive(arsiv_yolu) as arsiv:
            sonuc = arsiv.alarm_baglami(hisse, tetik_zamani, max_age=max_age, origin=origin)
    except (ValueError, OSError, sqlite3.Error) as hata:
        (logger or logging.getLogger(__name__)).warning(
            "%s için KAP bağlamı okunamadı: %s", hisse, hata
        )
        return None
    if sonuc["durum"] == "var":
        yorum_istegi["kap_baglami"] = sonuc["baglam"]
        if "sirket_profili" in sonuc:
            yorum_istegi["kap_sirket_profili"] = sonuc["sirket_profili"]
        if "bekleyen_bildirim" in sonuc:
            yorum_istegi["kap_bekleyen_bildirim"] = sonuc["bekleyen_bildirim"]
    elif sonuc["durum"] == "yok":
        if "sessizlik" in sonuc:
            yorum_istegi["kap_sessizlik"] = sonuc["sessizlik"]
    return sonuc


# ==========================================================================
# Kaynak: bistman/collector.py
# ==========================================================================

DetailFetcher = Callable[[int], Awaitable[DisclosureDetail]]

# Tekrar taramada yeniden detay indirme gerektirmeyen durumlar.
_TERMINAL_SEEN = frozenset({
    "hazir",
    "filtered_routine",
    "filtered_mechanical",
    "fundamentals_refresh",
    "filtered_non_equity",
    "filtered_low_signal",
    "agenda",
    "cok_hisseli",
    "dis_evren",
    "kapsam_disi",
    "geri_cekildi",
    "satis_kaniti_yetersiz",
    "durus_kaniti_yetersiz",
    "bedel_baglamla_celisiyor",
    "inceleme_bekleniyor",
    "ihale_sonucu_icin_detay_gerekli",
})

_NON_EQUITY_SUBJECTS: tuple[str, ...] = (
    "fon sürekli bilgilendirme formu",
    "fon ihraç sözleşmesi",
    "fon içtüzüğü",
    "yatırım kuruluşu varant - sertifika - senetlerine i̇lişkin bildirim",
    "yatırım kuruluşu varant - sertifika - senetlerine ilişkin bildirim",
    "yapılandırılmış yatırım araçları",
    "borsa yatırım fonlarına ilişkin",
)
_NON_EQUITY_SUMMARY_MARKERS: tuple[str, ...] = (
    "yatırım fonlarına ilişkin rehber",
    "yatırım fonu katılma pay",
)

# İdari/bürokratik bildirimler: hisse alarmında olay bağlamı taşımaz,
# gereksiz detay isteği ve sahte 'detay_bekleniyor' üretmemesi için ayrılır.
_LOW_SIGNAL_SUBJECTS: tuple[str, ...] = (
    "herhangi bir otoriteye mali tablo verilmesi",
    "bağımsız denetim kuruluşunun belirlenmesi",
    "kurumsal yönetim bilgi formu",
    "kurumsal yönetim ilkelerine uyum",
    "sürdürülebilirlik uyum",
    "yönetim kurulu komiteleri",
    "şirket merkezi değişikliği",
    "iletişim bilgileri",
    "likidite sağlayıcılık kapsamındaki işlemler",
    "sermaye artırımından elde edilecek - edilen fonun kullanımına ilişkin rapor",
    "eski payların yenileriyle değiştirilmesi",
)

# Liste satırında şirket adı yerine kurum adı taşıyan bildirimler:
# hedef hisse kodu yalnız detaydaki `stockCode` / `relatedStocks` içindedir.
_OPAQUE_ISSUERS = frozenset({
    "kamuyu aydınlatma platformu",
    "borsa istanbul a.ş.",
    "sermaye piyasası kurulu",
    "merkezi kayıt kuruluşu a.ş.",
})

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_MAX_QUOTE_LEN = MAX_CHARS - 180

# Standart KAP şablon kapanış/giriş cümleleri: asla olay kanıtı olarak seçilmez.
_BOILERPLATE_RE = re.compile(
    r"(?:yukarıdaki\s+açıklamalarımızın\s+sermaye\s+piyasası"
    r"|kamuoyuna\s+(?:ve\s+yatırımcılarımıza\s+)?saygıyla\s+duyurulur"
    r"|tasarruf\s+sahiplerinin\s+ve\s+kamuoyunun\s+bilgisine"
    r"|yatırımcılarımızın\s+ve\s+kamuoyunun\s+bilgisine\s+sunulur"
    r"|aşağıdaki\s+açıklamanın\s+yapılmasına\s+gerek\s+duyulmuştur"
    r"|işbu\s+açıklamamızın\s+ingilizce\s+çeviri"
    r"|çeviri\s+metin\s+arasında\s+herhangi\s+bir\s+farklılık"
    r"|toplantısında\s+aşağıdaki\s+kararlar\s+alınmıştır)",
)

# --- Doğrulanabilir BIST şirket açıklaması kalıpları (yalnız birebir cümle seçimi) ---

# Hem edilgen ("karar verildi/verilmiştir") hem etken ("karar verdi/vermiştir") YK kalıbı.
_DECIDED = r"karar\s+ver(?:il)?(?:di|miştir)"

# Olumsuzlanmış, henüz plan aşamasındaki veya yalanlanan ifadeler olumlu karar sayılmaz.
# Not: "kâr payı dağıtılmamasına karar verilmiştir" gerçek bir YK kararı olduğu için korunur.
_NEGATED_DECISION_RE = re.compile(
    r"(?:\bkarar\s+ver(?:il)?me(?:di|miştir)"
    r"|\bonaylanma(?:dı|mıştır)|\bkabul\s+edilme(?:di|miştir)"
    r"|\bbaşlatılma(?:dı|mıştır|masına)|\byapılmamasına\s+karar"
    r"|\b(?:satın\s+)?alınmamasına\s+karar|\bsatılmamasına\s+karar"
    r"|\bvazgeçilme(?:di|miştir)"
    r"|\buygulanma(?:dı|mıştır|maktadır|yacak\w*)"
    r"|\bkesilme(?:di|miştir)|\bverilme(?:di|miştir)|\bhükmedilme(?:di|miştir)"
    r"|\bdevreye\s+alınma(?:dı|mıştır)|\biptal\s+edilme(?:di|miştir)|\bfeshedilme(?:di|miştir)"
    r"|\b(?:planlanmakta|hedeflenmekte|öngörülmekte|değerlendirilmekte)\w*"
    r"|\bsöz\s+konusu\s+değil\w*|\bgerçeği\s+yansıtm)",
)

_CONTRACT_TERMINATION_RE = re.compile(
    r"\b(?:sözleşme\w*|anlaşma\w*|sipariş\w*)\s+.{0,90}?\b"
    r"(?:feshedil(?:di|miştir)|fesh\s*edil(?:di|miştir)|iptal\s+edil(?:di|miştir)|sona\s+erdiril(?:di|miştir))\b",
)

_TENDER_AWARD_RE = re.compile(
    r"(?:\bihale\w*\s+(?:(?:\w+\s+){0,4})?uhdemizde\s+kal(?:dı|mıştır)"
    r"|\bşirketimiz\s+lehine\s+sonuçlan(?:dı|mıştır)"
    r"|\ben\s+avantajlı\s+teklif\w*\s+.+?\bşirketimiz(?:ce|\s+tarafından)\s+veril(?:di|miş)"
    r"|\bihale(?:yi)?\s+(?:(?:\w+\s+){0,4})?(?:şirketimiz\s+)?kazan(?:dı|mış|mıştır)"
    r"|\bkesinleşen\s+ihale\s+kararı\s+(?:şirketimize\s+)?tebliğ\s+edil(?:di|miştir)"
    r"|\bsözleşme\s+(?:imzalanmasına\s+ilişkin\s+)?davet\w*\s+(?:şirketimize\s+|tarafımıza\s+)?(?:ulaş|tebliğ\s+edil|alın|gönderil)(?:dı|di|mıştır|miştir))",
)
_TENDER_DISQUALIFY_RE = re.compile(
    r"(?:\buhdemizde\s+kalma(?:dı|mıştır)|\bihale\w*\s+(?:(?:\w+\s+){0,3})?iptal\s+edil(?:di|miştir)"
    r"|\bkazanama(?:dı|mıştır)|\bdeğerlendirme\s+süreci\s+devam\s+etmekte|\belenmiş|\bgeçersiz\s+sayıl"
    r"|\byürürlüğe\s+girmemiş|\bgerçeği\s+yansıtm)",
)

_CAPITAL_ACTION_RE = re.compile(
    rf"(?:\b(?:çıkarılmış|ödenmiş)\s+sermaye\w*\s+.+?\b"
    rf"(?:(?:bedelsiz|bedelli|tahsisli)\s+.*?\b(?:{_DECIDED}|artırıl(?:dı|mıştır)|başvuru\w*\s+yapıl(?:dı|mıştır)|onaylan(?:dı|mıştır))"
    rf"|(?:artırılmasına|azaltılmasına)\s+{_DECIDED})"
    rf"|\b(?:bedelsiz|bedelli|tahsisli)\s+sermaye\s+artırım\w*\s+.+?\b"
    rf"(?:{_DECIDED}|başvuru\w*\s+yapıl(?:dı|mıştır)|başvuru\s+yap(?:tı|mıştır)"
    rf"|onaylan(?:dı|mıştır)|reddedil(?:di|miştir)|iptal\s+edil(?:di|miştir)))",
)

_DIVIDEND_RE = re.compile(
    rf"(?:\b(?:nakit\s+|pay\s+biçiminde\s+)?(?:k[aâ]r\s+payı|temettü)\s+"
    rf"(?:dağıtılmasına|dağıtılmamasına|ödenmesine|dağıtılmasının)\s+.{{0,80}}?\b"
    rf"(?:{_DECIDED}|onayına\s+sunulmasına\s+{_DECIDED})"
    rf"|\bpay\s+başına\s+(?:brüt|net)\s+\d[\d.,]*\s*(?:tl|kr|kuruş)\s+(?:nakit\s+)?(?:k[aâ]r\s+payı|temettü))",
)

_BUYBACK_RE = re.compile(
    rf"(?:\bpay(?:larımızın|larının)?\s+geri\s+alınmasına\s+.{{0,120}}?\b{_DECIDED}"
    rf"|\bpay(?:larımızın|larının)?\s+geri\s+alınmasına\s+{_DECIDED}"
    rf"|\bgeri\s+alım\s+programı\w*\s+.{{0,100}}?\b"
    rf"(?:başlatıl(?:dı|mıştır)|başlatılmasına\s+{_DECIDED}|sonlandırıl(?:dı|mıştır)"
    rf"|sonlandırılmasına\s+{_DECIDED}|tamamlan(?:dı|mıştır)|kabul\s+edil(?:di|miştir)|{_DECIDED})"
    rf"|\bgeri\s+alım\s+işlemi\s+gerçekleştiril(?:di|miştir))",
)
# Günlük geri alım işlemi bildirimlerinde önceki YK kararına atıf ("kararı kapsamında ... pay geri alınmıştır")
_BUYBACK_DAILY_TX_RE = re.compile(
    r"\b[\d.,]+\s*(?:adet|tl\s+nominal|nominal(?:\s+değerli)?)\s+(?:\w+\s+){0,3}pay\w*\s+geri\s+alın(?:dı|mıştır)"
)

_REGULATORY_MEASURE_RE = re.compile(
    rf"(?:\baçığa\s+satışa?\s+ve\s+kredili\s+işlem\w*"
    rf"|\bbrüt\s+takas\s+(?:tedbiri\s+)?(?:uygulan\w*|sona\s+er(?:di|miştir)|kaldırıl(?:dı|mıştır))"
    rf"|\bemir\s+paketi\s+tedbiri\s+(?:uygulan\w*|sona\s+er(?:di|miştir)|kaldırıl(?:dı|mıştır))"
    rf"|\btek\s+fiyat\s+işlem\s+yöntemi\s+(?:uygulan\w*|sona\s+er(?:di|miştir)|kaldırıl(?:dı|mıştır))"
    rf"|\b(?:pay\s+sırası|işlem\s+sırası)\s+.{{0,80}}?\b(?:işleme\s+kapatıl(?:dı|mıştır)|durdurul(?:du|muştur)|yeniden\s+işleme\s+açıl(?:dı|mıştır))"
    rf"|\b(?:geçici\s+)?işlem\s+yasağı\s+(?:uygulan(?:dı|mıştır|acaktır)|getiril(?:di|miştir)|kararı\s+(?:alın|veril)(?:dı|di|mıştır|miştir))"
    rf"|\bidari\s+para\s+cezası\s+(?:uygulan(?:dı|mıştır|masına)|veril(?:di|miştir|mesine)|kesil(?:di|miştir|mesine))(?:\s+{_DECIDED})?)",
)

# Haber/söylenti açıklamalarında şirketin doğrudan netleştirici/sonuç cümlesi.
_RUMOUR_CLARIFICATION_RE = re.compile(
    r"(?:\b(?:idari\s+para\s+cezası|işlem\s+yasağı|yaptırım\s+kararı)\s+bulunmamaktadır"
    r"|\bgerçeği\s+yansıtmamaktadır\b|\basılsızdır\b|\bdoğru\s+değildir\b"
    r"|\bherhangi\s+bir\s+(?:\w+\s+){0,4}(?:karar\w*|girişim\w*|görüşme\w*|sözleşme\w*|yaptırım\w*|ceza\w*)\s+bulunmamaktadır"
    r"|\biddialarda\s+adı\s+geçen\s+.+?\byoktur\b"
    r"|\b(?:görüşmeler|değerlendirmeler)\s+devam\s+etmektedir\b)",
)

_STRATEGIC_ACTION_RE = re.compile(
    rf"(?:\b(?:taşınmaz\w*|gayrimenkul\w*|fabrika\w*|tesis\w*|arsa\w*|iştirak\w*|bağlı\s+ortaklık\w*|pay\w*)\s+"
    rf".+?\b(?:satılmasına|satın\s+alınmasına|devralınmasına|devredilmesine"
    rf"|satın\s+alınmasından\s+vazgeçilmesine|satışından\s+vazgeçilmesine)\s+{_DECIDED}"
    rf"|\byatırım\s+teşvik\s+belgesi\s+(?:alın(?:dı|mıştır)|onaylan(?:dı|mıştır))"
    rf"|\b(?:yeni\s+(?:\w+\s+){{0,4}})?(?:üretim\s+tesisi\w*|tesisi|fabrikası|üretim\s+hattı\w*|santral\w*|kapasite\s+artış\w*)\s*"
    rf"(?:.{{0,80}}?\s)?(?:devreye\s+alın(?:dı|mıştır)|yatırım\w*\s+karar\w*\s+alın(?:dı|mıştır)|{_DECIDED})"
    rf"|\b(?:birleşme|bölünme|halka\s+arz)\s+(?:işlem\w*|başvuru\w*)\s+.+?\b"
    rf"(?:{_DECIDED}|başvuru\w*\s+yapıl(?:dı|mıştır)|onaylan(?:dı|mıştır)|reddedil(?:di|miştir))"
    rf"|\b(?:grev|lokavt)\s+kararı\s+alın(?:dı|mıştır)"
    rf"|\bşirketimiz(?:in)?\s+.{{0,60}}?\blisans\w*\s+(?:iptal\s+edil(?:di|miştir)|veril(?:di|miştir)|yenilen(?:di|miştir))"
    rf"|\bşirketimiz\s+.{{0,80}}?\bkonkordato\s+(?:talebinde\s+bulun(?:du|muştur)|ilan\s+et(?:ti|miştir)|mühleti\s+(?:al(?:dı|mıştır)|veril(?:di|miştir)))"
    rf"|\bşirketimiz(?:in)?\s+.{{0,80}}?\b(?:ciro|hasılat|favök|satış|yatırım|büyüme)\s+(?:beklenti\w*|hedef\w*)\s+.{{0,60}}?\b(?:revize\s+et(?:ti|miştir)|revize\s+edil(?:di|miştir)|güncelle(?:di|miştir)|güncellen(?:di|miştir))"
    rf"|\b(?:uzun\s+vadeli\s+(?:ulusal|yabancı\s+para)|kredi\s+derecelendirme)\s+(?:kredi\s+derecelendirme\s+)?notu\w*\s+.+?\b"
    rf"(?:teyit\s+et(?:ti|miştir)|teyit\s+edil(?:di|miştir)|belirlen(?:di|miştir)|yükseltil(?:di|miştir)|düşürül(?:dü|müştür)|revize\s+edil(?:di|miştir)))",
)

_INSIDER_DISCLOSURE_RE = re.compile(
    r"(?:\bsermayesindeki\s+paylarım(?:/oy\s+haklarım)?\s+.+?\b"
    r"(?:ulaşmıştır|aşmıştır|altına\s+düşmüştür|olmuştur)"
    r"|\btoplam\s+[\d.,]+\s*(?:tl\s+)?toplam\s+nominal\s+tutarlı\s+alış\s+(?:ve/veya\s+[\d.,]+\s*(?:tl\s+)?toplam\s+nominal\s+tutarlı\s+satış\s+)?işlemi\s+gerçekleştirilmiştir"
    r"|\b[\d.,]+\s*(?:tl\s+)?nominal\s+tutarlı\s+(?:alış|satış)\s+işlemi\s+(?:tarafımca\s+|şirketimizce\s+)?gerçekleştirilmiştir)",
)

_TENDER_NOTE = "İhale sonucu bildirildi; kesin sözleşme imzası ayrıca izlenmelidir."


@dataclass(frozen=True, slots=True)
class EvidenceProposal:
    """Doğrulanmış kaynaktan seçilen konu ve tam cümle alıntısı."""

    topic: Topic
    quote: str
    reviewed: ReviewedReading | None = None
    supersedes: int | None = None
    valid_until: datetime | None = None


class EvidenceReviewer(Protocol):
    """İsteğe bağlı inceleyici: önerisi yine `AlarmArchive.record` kurallarından geçer."""

    async def propose(
        self,
        disclosure: DisclosureStub,
        ticker: str,
        detail: DisclosureDetail | None,
        body: str,
    ) -> EvidenceProposal | None: ...


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Tek tarama turunun denetlenebilir özeti (kullanıcı mesajı değil)."""

    total_rows: int
    rejected_rows: int
    counts: dict[str, int]
    detail_requests: int = 0
    unprobed_opaque: int = 0
    fundamentals_refresh: tuple[str, ...] = field(default_factory=tuple)
    scanned_until: datetime | None = None
    suspicious_empty: bool = False


def is_non_equity_disclosure(title: str, subject: str, summary: str | None = None) -> bool:
    """Yatırım fonu, varant ve ikraz iştirak senedi gibi hisse dışı bildirim mi?"""
    if looks_like_fund(title):
        return True
    subj = tr_lower(subject or "")
    if any(marker in subj for marker in _NON_EQUITY_SUBJECTS):
        return True
    if summary:
        summ = tr_lower(summary)
        if any(marker in summ for marker in _NON_EQUITY_SUMMARY_MARKERS):
            return True
    return False


def is_low_signal_corporate(subject: str) -> bool:
    """Rutin/idari kurumsal form bildirimi mi (alarm bağlamı taşımaz)?"""
    subj = tr_lower(subject or "")
    return any(marker in subj for marker in _LOW_SIGNAL_SUBJECTS)


def _is_opaque_issuer(title: str) -> bool:
    return tr_lower((title or "").strip()) in _OPAQUE_ISSUERS


def _iter_sentence_pairs(text: str) -> list[tuple[str, str]]:
    """`body_text` veya özetten `(tam_cumle, tr_lower(tam_cumle))` çiftlerini O(N) çıkarır."""
    if not text:
        return []
    pairs: list[tuple[str, str]] = []
    for paragraph in text.splitlines():
        line = paragraph.strip()
        if not line:
            continue
        llen = len(line)
        start = 0
        for match in _SENTENCE_END.finditer(line):
            end = match.end()
            if end < llen and is_abbreviation_break(
                line[max(0, end - 128):end],
                line[end:min(llen, end + 64)],
            ):
                continue
            cand = line[start:end].strip()
            start = end
            if (
                not cand
                or len(cand) > _MAX_QUOTE_LEN
                or _starts_with_lowercase_word(cand)
            ):
                continue
            low = tr_lower(cand)
            if not _BOILERPLATE_RE.search(low):
                pairs.append((cand, low))
    return pairs


def _first_matching(
    sentences: Sequence[tuple[str, str]],
    pattern: re.Pattern[str],
    *,
    reject_negated: bool = True,
) -> str | None:
    for sentence, low in sentences:
        if pattern.search(low):
            if reject_negated and _NEGATED_DECISION_RE.search(low):
                continue
            return sentence
    return None


def extract_verified_evidence(
    disclosure: DisclosureStub,
    body: str = "",
) -> EvidenceProposal | None:
    """Kural tabanlı, uydurmasız kanıt seçici.

    Her öneri kaynak metindeki birebir tam cümleye dayanır; yön/neden uydurmaz,
    olumsuzlanmış veya şarta bağlı ifadeleri olumlu olay gibi sunmaz. Cümleler
    tek geçişte (O(N)) ayrıştırılır. Şüphede `None` döndürür ve aday
    `detay_bekleniyor` olarak kalır.
    """
    summary = (disclosure.summary or "").strip()
    sources = [s for s in (body, summary) if s and s != disclosure.subject.strip()]
    if not sources:
        return None
    sentences: list[tuple[str, str]] = []
    for source in sources:
        sentences.extend(_iter_sentence_pairs(source))
    if not sentences:
        return None

    all_fields = (disclosure.subject, summary, body)
    subj_low = tr_lower(disclosure.subject or "")
    full_low = tr_lower(" ".join(f for f in all_fields if f))
    qualified_sale = sale_qualified(*all_fields)

    # 1a) Doğrulanmış, şartsız/iptalsiz imzalı satış sözleşmesi veya kesin sipariş
    if not qualified_sale:
        for sentence, _low in sentences:
            if issuer_signature(sentence) == "sale":
                return EvidenceProposal(topic="satis_sozlesmesi", quote=sentence)

    # 1b) Açık sözleşme feshi/iptali: önemli olumsuz gelişme, birebir `sirket_aciklamasi` olarak korunur
    # (aynı bildirim numarasında eski bir satışı da güncel gözlem anından itibaren değiştirir).
    if "ihale" not in subj_low:
        if hit := _first_matching(sentences, _CONTRACT_TERMINATION_RE):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 1c) Şarta bağlı / imzalanmamış / mutabakat zaptı satış adayı: olumlu satış gibi yayımlanmaz.
    if qualified_sale and (
        any(k in subj_low for k in ("sözleşme", "satış", "yeni iş"))
        or any(issuer_signature(s) == "sale" for s, _ in sentences)
    ):
        for sentence, _low in sentences:
            if sale_qualified(sentence) or issuer_signature(sentence) == "sale":
                return EvidenceProposal(topic="satis_sozlesmesi", quote=sentence)

    # 2) Doğrulanmış üretim / faaliyet duruşu (veya çelişen/yeniden başlayan güncelleme)
    contradicted_stop = stoppage_contradicted(*all_fields)
    if not contradicted_stop:
        for sentence, _low in sentences:
            if stoppage_confirmed(sentence):
                return EvidenceProposal(topic="uretim_durusu", quote=sentence)

    if contradicted_stop and any(k in subj_low for k in ("üretim", "duruş", "faaliyet")):
        for sentence, _low in sentences:
            if stoppage_contradicted(sentence):
                return EvidenceProposal(topic="uretim_durusu", quote=sentence)

    # 3) Kesinleşen ihale kazanımı / sözleşme daveti (yalnız teklif veya iptal elenir)
    if "ihale" in subj_low and not _TENDER_DISQUALIFY_RE.search(full_low):
        if hit := _first_matching(sentences, _TENDER_AWARD_RE):
            note = (
                ReviewedReading(hit, _TENDER_NOTE)
                if len(hit) + len(_TENDER_NOTE) <= 400
                and not sale_qualified(hit)
                else None
            )
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit, reviewed=note)

    # 4) Sermaye artırımı / azaltımı (bedelsiz, bedelli, tahsisli karar/başvuru/onay/ret)
    if any(k in subj_low for k in ("sermaye artırım", "sermaye azaltım", "bedelsiz", "bedelli", "tahsisli")):
        if hit := _first_matching(sentences, _CAPITAL_ACTION_RE):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 5) Kâr payı / temettü dağıtım (veya dağıtmama) kararı
    if any(k in subj_low for k in ("kar payı", "kâr payı", "kar dağıtım", "kâr dağıtım", "temettü")):
        if hit := _first_matching(sentences, _DIVIDEND_RE):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 6) Pay geri alım programı başlatma/sonlandırma/revizyon kararı
    # (önceki karara atıflı rutin günlük adet bildirimleri program kararı sayılmaz).
    if "geri alınmasına" in subj_low or "geri alım" in subj_low:
        if hit := _first_matching(sentences, _BUYBACK_RE):
            if not ("kapsamında" in tr_lower(hit) and _BUYBACK_DAILY_TX_RE.search(tr_lower(hit))):
                return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 7) VBTS / SPK işlem yasağı / pay sırası kapatma / idari para cezası
    if any(
        k in subj_low
        for k in ("vbts", "tedbir", "işlem yasağı", "işleme kapatılma", "işleme açılma", "işlem sırası", "idari para cezası")
    ):
        if hit := _first_matching(sentences, _REGULATORY_MEASURE_RE):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 8) Haber ve söylentilere ilişkin açıklama (MTRKS #1699030 dahil: birebir sonuç cümlesi)
    if "haber ve söylenti" in subj_low or "haber veya söylenti" in subj_low:
        if hit := _first_matching(sentences, _RUMOUR_CLARIFICATION_RE, reject_negated=False):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 9) Pay alım satım bildirimi (önemli ortak/yönetici pay eşiği veya işlem özeti)
    if "pay alım satım" in subj_low or "pay alım-satım" in subj_low:
        if hit := _first_matching(sentences, _INSIDER_DISCLOSURE_RE):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    # 10) Genel ÖDA ve stratejik kararlar (varlık alım/satım, tesis, grev, lisans, konkordato,
    # beklenti revizyonu, kredi notu, birleşme, sermaye, temettü, geri alım, tedbir, yalanlama)
    for pattern, guard in (
        (_STRATEGIC_ACTION_RE, True),
        (_CAPITAL_ACTION_RE, True),
        (_DIVIDEND_RE, True),
        (_BUYBACK_RE, True),
        (_REGULATORY_MEASURE_RE, True),
        (_RUMOUR_CLARIFICATION_RE, False),
    ):
        if hit := _first_matching(sentences, pattern, reject_negated=guard):
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit)

    if not _TENDER_DISQUALIFY_RE.search(full_low):
        if hit := _first_matching(sentences, _TENDER_AWARD_RE):
            note = (
                ReviewedReading(hit, _TENDER_NOTE)
                if len(hit) + len(_TENDER_NOTE) <= 400
                and not sale_qualified(hit)
                else None
            )
            return EvidenceProposal(topic="sirket_aciklamasi", quote=hit, reviewed=note)

    return None


def _fingerprint(stub: DisclosureStub) -> bytes:
    payload = [
        stub.index,
        stub.published_at.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        stub.title,
        stub.subject,
        stub.summary,
        stub.disclosure_class,
        list(stub.tickers),
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).digest()


def _collapse_company_codes(
    codes: Sequence[str],
    code_to_oid: Mapping[str, str],
    allowed: set[str] | None = None,
    *,
    member_oid: str | None = None,
) -> tuple[tuple[str, ...], bool]:
    """Hisse kodlarını tek ihraççıya indirger; farklı şirketlerse `((), True)` döndürür.

    `GARAN, TGB`, `HALKB, THB`, `AKBNK, TAB`, `VAKBN, TVB`, `SISE, TSC`,
    `ISA, ISB, ISCTR, ISKUR`, `KRDMA, KRDMB, KRDMD` gibi aynı `mkkMemberOid`
    altındaki kodlar tek şirkettir; `ASELS, THYAO` gibi ayrı şirketler `cok_hisseli` kalır.
    """
    unique = tuple(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))
    if not unique:
        return (), False
    if len(unique) == 1:
        return unique, False
    if code_to_oid:
        oids = [code_to_oid.get(c) for c in unique]
        if all(oids) and len(set(oids)) == 1:
            common_oid = oids[0]
            if member_oid and member_oid != common_oid:
                return (), True
            if allowed is not None:
                watched = tuple(c for c in unique if c in allowed)
                if watched:
                    return watched, False
            primary = select_primary_ticker(unique)
            return ((primary,) if primary else (unique[0],)), False
    return (), True


def _resolve_single_ticker(
    stub: DisclosureStub,
    resolver: TickerResolver,
    *,
    code_to_oid: Mapping[str, str],
    oid_to_codes: Mapping[str, tuple[str, ...]],
    allowed: set[str] | None = None,
) -> tuple[tuple[str, ...], bool]:
    """`(hedef_kodlar, cok_sirketli_mi)` döndürür. Çok şirketli kayıt asla tek hisseye yazılmaz."""
    if stub.tickers:
        return _collapse_company_codes(
            stub.tickers, code_to_oid, allowed, member_oid=stub.member_oid,
        )
    if stub.member_oid and oid_to_codes and not _is_opaque_issuer(stub.title):
        known = oid_to_codes.get(stub.member_oid)
        if known:
            return _collapse_company_codes(known, code_to_oid, allowed, member_oid=stub.member_oid)
        # BIST şirket listesinde olmayan ihraççı OID'i (ör. borsada işlem görmeyen aracı kurum)
        return (), False
    symbols = tuple(dict.fromkeys(symbols_in_title(stub.title)))
    if len(symbols) > 1:
        return _collapse_company_codes(symbols, code_to_oid, allowed)
    hit = resolver.resolve(stub.title).ticker
    if hit:
        return (hit,), False
    if symbols and resolver.has_ticker(symbols[0]):
        return (symbols[0],), False
    return (), False


def _detail_for_ticker(detail: DisclosureDetail, ticker: str) -> DisclosureDetail:
    """Aynı `mkkMemberOid` altındaki çok kodlu detayı doğrulanan tek pay koduna daraltır."""
    if detail.stub.tickers == (ticker,) or not detail.stub.tickers:
        return detail
    narrowed = DisclosureStub(
        index=detail.stub.index,
        published_at=detail.stub.published_at,
        title=detail.stub.title,
        subject=detail.stub.subject,
        summary=detail.stub.summary,
        disclosure_class=detail.stub.disclosure_class,
        tickers=(ticker,),
        member_oid=detail.stub.member_oid,
        minute_precision=detail.stub.minute_precision,
    )
    return DisclosureDetail(
        stub=narrowed,
        body_html=detail.body_html,
        attachment_count=detail.attachment_count,
    )


def _now_utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.utcoffset() is None:
        raise ValueError("clock saat dilimli datetime döndürmeli")
    return value.astimezone(timezone.utc)


async def ingest_feed(
    feed: ParseResult,
    archive: AlarmArchive,
    *,
    resolver: TickerResolver,
    detail_fetcher: DetailFetcher | None = None,
    reviewer: EvidenceReviewer | None = None,
    statements: Mapping[str, Sequence[PublishedRow]] | None = None,
    universe: Sequence[str] | None = None,
    companies: Sequence[CompanyEntry] = (),
    origin: Origin = "kap_arsiv",
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    probe_unresolved: bool = False,
    probe_opaque: bool = False,
    max_unresolved_probes: int = 25,
    strict_watermark: bool = False,
    update_watermark: bool = True,
) -> ScanReport:
    """Ayrıştırılmış KAP listesini sessizce doğrular ve `archive`'e işler.

    - `companies`: BIST şirket `(ticker, oid, unvan)` listesi verildiğinde hem aynı
      `mkkMemberOid` altındaki çok kodlu tek şirketler (`GARAN, TGB`, `ISA..ISCTR`,
      `KRDMA..KRDMD`) doğru paya indirgenir hem de borsada işlem görmeyen ihraççı
      OID'lerinin BIST hisselerine yanlış bağlanması engellenir.
    - `probe_opaque=True`: başlığı `KAMUYU AYDINLATMA PLATFORMU` / `SPK` / `BİST`
      olan hisse kodsuz satırların detayını çekip gerçek hisseyi bulur.
    - `probe_unresolved=True`: unvanı eşleşmeyen diğer kurumsal satırları da denetler.
    - `strict_watermark=True`: denetlenmemiş kurum başlıklı satır kaldıysa `son_tarama`
      imlecini o satırın önüne çeker; eksik kontrolü tam kapsam gibi göstermez.
    """
    scan_started = _now_utc(clock)
    if not feed.items and not feed.rejected:
        return ScanReport(0, 0, {}, suspicious_empty=True)

    allowed = {t.strip().upper() for t in universe} if universe is not None else None
    code_to_oid: dict[str, str] = {}
    oid_groups: dict[str, list[str]] = {}
    for entry in companies:
        code = entry.ticker.strip().upper()
        if code and entry.oid:
            code_to_oid[code] = entry.oid
            group = oid_groups.setdefault(entry.oid, [])
            if code not in group:
                group.append(code)
    oid_to_codes: dict[str, tuple[str, ...]] = {oid: tuple(grp) for oid, grp in oid_groups.items()}
    counts: Counter[str] = Counter()
    refresh_tickers: list[str] = []
    earliest_incomplete: datetime | None = None
    detail_calls = 0
    probes_used = 0
    unprobed_opaque = 0

    # Eskiden yeniye işle ki aynı turdaki düzeltme hedefinden sonra yazılabilsin.
    ordered = sorted(feed.items, key=lambda s: (s.published_at, s.index))

    for stub in ordered:
        fp = _fingerprint(stub)
        cached = archive.seen_status(stub.index, fp, origin=origin)
        if cached in _TERMINAL_SEEN:
            counts["atlandi_ayni"] += 1
            continue

        triage = route(stub.disclosure_class, stub.subject, stub.summary)
        now = max(_now_utc(clock), stub.published_at.astimezone(timezone.utc))

        if triage is not Route.PIPELINE:
            status = {
                Route.ROUTINE: "filtered_routine",
                Route.MECHANICAL: "filtered_mechanical",
                Route.FUNDAMENTALS_REFRESH: "fundamentals_refresh",
            }[triage]
            if triage is Route.FUNDAMENTALS_REFRESH:
                tkr, _ = _resolve_single_ticker(stub, resolver)
                if tkr and (allowed is None or tkr in allowed):
                    refresh_tickers.append(tkr)
            retracted = archive.retract(
                stub.index, published_at=stub.published_at, known_at=now,
                reason=status, origin=origin, minute_precision=stub.minute_precision,
            )
            final = retracted if retracted == "geri_cekildi" else status
            counts[final] += 1
            archive.mark_seen(stub.index, fp, final, updated_at=now, origin=origin)
            continue

        if is_index_agenda(stub.title, stub.subject, stub.tickers):
            retracted = archive.retract(
                stub.index, published_at=stub.published_at, known_at=now,
                reason="agenda", origin=origin, minute_precision=stub.minute_precision,
            )
            final = retracted if retracted == "geri_cekildi" else "agenda"
            counts[final] += 1
            archive.mark_seen(stub.index, fp, final, updated_at=now, origin=origin)
            continue

        if not stub.tickers and is_non_equity_disclosure(stub.title, stub.subject, stub.summary):
            retracted = archive.retract(
                stub.index, published_at=stub.published_at, known_at=now,
                reason="filtered_non_equity", origin=origin, minute_precision=stub.minute_precision,
            )
            final = retracted if retracted == "geri_cekildi" else "filtered_non_equity"
            counts[final] += 1
            archive.mark_seen(stub.index, fp, final, updated_at=now, origin=origin)
            continue

        if is_low_signal_corporate(stub.subject):
            retracted = archive.retract(
                stub.index, published_at=stub.published_at, known_at=now,
                reason="filtered_low_signal", origin=origin, minute_precision=stub.minute_precision,
            )
            final = retracted if retracted == "geri_cekildi" else "filtered_low_signal"
            counts[final] += 1
            archive.mark_seen(stub.index, fp, final, updated_at=now, origin=origin)
            continue

        targets, is_multi = _resolve_single_ticker(
            stub, resolver, code_to_oid=code_to_oid, oid_to_codes=oid_to_codes, allowed=allowed,
        )
        if is_multi:
            retracted = archive.retract(
                stub.index, published_at=stub.published_at, known_at=now,
                reason="cok_hisseli", origin=origin, minute_precision=stub.minute_precision,
            )
            final = retracted if retracted == "geri_cekildi" else "cok_hisseli"
            counts[final] += 1
            archive.mark_seen(stub.index, fp, final, updated_at=now, origin=origin)
            continue

        detail: DisclosureDetail | None = None
        if not targets:
            # BIST dışı ihraççı OID'i kesin olarak biliniyorsa gereksiz detay denemesi yapma.
            if (
                stub.member_oid
                and oid_to_codes
                and stub.member_oid not in oid_to_codes
                and not stub.tickers
                and not _is_opaque_issuer(stub.title)
            ):
                counts["kapsam_disi"] += 1
                archive.mark_seen(stub.index, fp, "kapsam_disi", updated_at=now, origin=origin)
                continue
            opaque = _is_opaque_issuer(stub.title)
            should_probe = (
                detail_fetcher is not None
                and (probe_unresolved or (probe_opaque and opaque))
                and probes_used < max_unresolved_probes
            )
            if should_probe:
                assert detail_fetcher is not None
                probes_used += 1
                try:
                    detail_calls += 1
                    fetched = await detail_fetcher(stub.index)
                except Exception:
                    counts["detay_hatasi"] += 1
                    earliest_incomplete = _min_dt(earliest_incomplete, stub.published_at)
                    continue
                if not fetched.matches_record(stub):
                    counts["detay_uyusmazligi"] += 1
                    continue
                detail = fetched
                targets, is_multi = _resolve_single_ticker(
                    detail.stub, resolver, code_to_oid=code_to_oid,
                    oid_to_codes=oid_to_codes, allowed=allowed,
                )
                if is_multi:
                    det_known = max(_now_utc(clock), detail.stub.published_at.astimezone(timezone.utc))
                    retracted = archive.retract(
                        stub.index, published_at=detail.stub.published_at,
                        known_at=det_known, reason="cok_hisseli", origin=origin,
                    )
                    final = retracted if retracted == "geri_cekildi" else "cok_hisseli"
                    counts[final] += 1
                    archive.mark_seen(stub.index, fp, final, updated_at=det_known, origin=origin)
                    continue
                if not targets:
                    # Detay da BIST hissesi taşımıyorsa (genel kurum/borsa dışı ihraççı) tekrar indirme.
                    counts["kapsam_disi"] += 1
                    archive.mark_seen(stub.index, fp, "kapsam_disi", updated_at=now, origin=origin)
                    continue
            else:
                if opaque:
                    unprobed_opaque += 1
                    if strict_watermark:
                        earliest_incomplete = _min_dt(earliest_incomplete, stub.published_at)
                counts["unresolved_ticker"] += 1
                continue

        if allowed is not None:
            targets = tuple(t for t in targets if t in allowed)
            if not targets:
                counts["dis_evren"] += 1
                archive.mark_seen(stub.index, fp, "dis_evren", updated_at=now, origin=origin)
                continue

        if detail is None and detail_fetcher is not None:
            try:
                detail_calls += 1
                fetched = await detail_fetcher(stub.index)
            except Exception:
                pending_at = max(_now_utc(clock), stub.published_at.astimezone(timezone.utc))
                for t in targets:
                    archive.record_pending(
                        stub, ticker=t, known_at=pending_at,
                        reason="detay_bekleniyor", origin=origin,
                    )
                archive.mark_seen(stub.index, fp, "detay_bekleniyor", updated_at=pending_at, origin=origin)
                counts["detay_bekleniyor"] += 1
                earliest_incomplete = _min_dt(earliest_incomplete, stub.published_at)
                continue
            if not fetched.matches_record(stub):
                counts["detay_uyusmazligi"] += 1
                continue
            detail = fetched

        ticker_switched = False
        det_codes: tuple[str, ...] = ()
        if detail is not None:
            det_codes = tuple(dict.fromkeys(c.strip().upper() for c in detail.stub.tickers if c and c.strip()))
            det_oid = detail.stub.member_oid
            det_known = max(_now_utc(clock), detail.stub.published_at.astimezone(timezone.utc))
            if det_codes:
                resolved_det, det_multi = _collapse_company_codes(
                    det_codes, code_to_oid, allowed,
                    member_oid=det_oid if (det_oid and not _is_opaque_issuer(detail.stub.title)) else None,
                )
                if det_multi:
                    retracted = archive.retract(
                        stub.index, published_at=detail.stub.published_at,
                        known_at=det_known, reason="cok_hisseli", origin=origin,
                    )
                    final = retracted if retracted == "geri_cekildi" else "cok_hisseli"
                    counts[final] += 1
                    archive.mark_seen(stub.index, fp, final, updated_at=det_known, origin=origin)
                    continue
                if set(resolved_det) != set(targets):
                    ticker_switched = True
                    targets = resolved_det
            elif det_oid and oid_to_codes and not _is_opaque_issuer(detail.stub.title):
                oid_codes = oid_to_codes.get(det_oid)
                if oid_codes is None:
                    # Detaydaki ihraççı OID'i BIST şirket listesinde yok (ör. borsada işlem görmeyen ihraççı).
                    retracted = archive.retract(
                        stub.index, published_at=detail.stub.published_at,
                        known_at=det_known, reason="kapsam_disi", origin=origin,
                    )
                    final = retracted if retracted == "geri_cekildi" else "kapsam_disi"
                    counts[final] += 1
                    archive.mark_seen(stub.index, fp, final, updated_at=det_known, origin=origin)
                    continue
                resolved_oid, _ = _collapse_company_codes(oid_codes, code_to_oid, allowed, member_oid=det_oid)
                if resolved_oid and set(resolved_oid) != set(targets):
                    ticker_switched = True
                    targets = resolved_oid
                det_codes = resolved_oid

            if allowed is not None:
                in_allowed = tuple(t for t in targets if t in allowed)
                if not in_allowed:
                    retracted = archive.retract(
                        stub.index, published_at=detail.stub.published_at,
                        known_at=det_known, reason="dis_evren", origin=origin,
                    )
                    final = retracted if retracted == "geri_cekildi" else "dis_evren"
                    counts[final] += 1
                    archive.mark_seen(stub.index, fp, final, updated_at=det_known, origin=origin)
                    continue
                targets = in_allowed

            det_subj = detail.stub.subject or stub.subject
            det_summ = detail.stub.summary or stub.summary
            det_route = route(
                detail.stub.disclosure_class or stub.disclosure_class, det_subj, det_summ,
            )
            if det_route is not Route.PIPELINE or is_low_signal_corporate(det_subj):
                status = (
                    "filtered_low_signal"
                    if det_route is Route.PIPELINE
                    else {
                        Route.ROUTINE: "filtered_routine",
                        Route.MECHANICAL: "filtered_mechanical",
                        Route.FUNDAMENTALS_REFRESH: "fundamentals_refresh",
                    }[det_route]
                )
                if det_route is Route.FUNDAMENTALS_REFRESH:
                    refresh_tickers.extend(targets)
                retracted = archive.retract(
                    stub.index, published_at=detail.stub.published_at,
                    known_at=det_known, reason=status, origin=origin,
                )
                final = retracted if retracted == "geri_cekildi" else status
                counts[final] += 1
                archive.mark_seen(stub.index, fp, final, updated_at=det_known, origin=origin)
                continue

        # Aynı şirket içinde birden çok izlenen pay sınıfı varsa (ör. hem KRDMA hem KRDMD
        # izleniyorsa) tek şirketin bildirimi ayrı disclosure_id kısıtına takılmadan birincil
        # izlenen koda yazılır.
        ticker = select_primary_ticker(targets, allowed=allowed) or targets[0]
        effective_detail = _detail_for_ticker(detail, ticker) if detail is not None else None
        if detail is not None:
            det_subj = detail.stub.subject or stub.subject
            effective_stub = DisclosureStub(
                index=stub.index,
                published_at=detail.stub.published_at,
                title=detail.stub.title or stub.title,
                subject=det_subj,
                summary=stub.summary if stub.summary is not None else detail.stub.summary,
                disclosure_class=detail.stub.disclosure_class or stub.disclosure_class,
                tickers=(ticker,) if det_codes else ((ticker,) if stub.tickers else ()),
                member_oid=detail.stub.member_oid or stub.member_oid,
            )
        else:
            effective_stub = (
                stub if not stub.tickers or stub.tickers == (ticker,)
                else DisclosureStub(
                    index=stub.index,
                    published_at=stub.published_at,
                    title=stub.title,
                    subject=stub.subject,
                    summary=stub.summary,
                    disclosure_class=stub.disclosure_class,
                    tickers=(ticker,),
                    member_oid=stub.member_oid,
                    minute_precision=stub.minute_precision,
                )
            )

        clean_body = body_text(detail.body_html) if detail is not None else ""
        proposal: EvidenceProposal | None = None
        if reviewer is not None:
            try:
                proposal = await reviewer.propose(effective_stub, ticker, effective_detail, clean_body)
            except Exception:
                proposal = None
        if proposal is None:
            proposal = extract_verified_evidence(effective_stub, clean_body)

        ready_at = max(_now_utc(clock), effective_stub.published_at.astimezone(timezone.utc))
        if proposal is not None:
            candidate = make_candidate(effective_stub, ticker)
            outcome = archive.record(
                candidate,
                origin=origin,
                known_at=ready_at,
                topic=proposal.topic,
                quote=proposal.quote,
                detail=effective_detail,
                statements=statements.get(ticker, ()) if statements else (),
                valid_until=proposal.valid_until,
                supersedes=proposal.supersedes,
                reviewed=proposal.reviewed,
                defer_missing_target=proposal.supersedes is not None,
            )
            counts[outcome] += 1
            archive.mark_seen(stub.index, fp, outcome, updated_at=ready_at, origin=origin)
        else:
            if ticker_switched:
                archive.retract(
                    effective_stub.index, published_at=effective_stub.published_at,
                    known_at=ready_at, reason="yanlis_atif", origin=origin,
                )
            pending_reason = (
                "detay_bekleniyor" if detail is None
                else ("ihale_sonucu_icin_detay_gerekli"
                      if "ihale" in tr_lower(effective_stub.subject)
                      else "inceleme_bekleniyor")
            )
            outcome = archive.record_pending(
                effective_stub, ticker=ticker, known_at=ready_at,
                reason=pending_reason, origin=origin,
            )
            counts[outcome] += 1
            archive.mark_seen(stub.index, fp, outcome, updated_at=ready_at, origin=origin)

    observed_end = _now_utc(clock)
    scanned_until = (
        _compute_watermark(
            feed=feed,
            scan_started=scan_started,
            observed_end=observed_end,
            earliest_incomplete=earliest_incomplete,
        )
        if update_watermark
        else None
    )
    if scanned_until is not None:
        archive.record_scan(
            scanned_until,
            observed_at=max(observed_end, scanned_until),
            origin=origin,
        )

    return ScanReport(
        total_rows=len(feed.items),
        rejected_rows=len(feed.rejected),
        counts=dict(counts),
        detail_requests=detail_calls,
        unprobed_opaque=unprobed_opaque,
        fundamentals_refresh=tuple(dict.fromkeys(refresh_tickers)),
        scanned_until=scanned_until,
        suspicious_empty=False,
    )


def _min_dt(current: datetime | None, candidate: datetime) -> datetime:
    utc = candidate.astimezone(timezone.utc)
    return utc if current is None or utc < current else current


def _compute_watermark(
    *,
    feed: ParseResult,
    scan_started: datetime,
    observed_end: datetime,
    earliest_incomplete: datetime | None,
) -> datetime | None:
    if feed.rejected or not feed.items:
        return None
    latest_pub = max(s.published_at.astimezone(timezone.utc) for s in feed.items)
    covered = min(max(scan_started, latest_pub), observed_end)
    if earliest_incomplete is not None:
        before_gap = earliest_incomplete - timedelta(microseconds=1)
        earliest_pub = min(s.published_at.astimezone(timezone.utc) for s in feed.items)
        if before_gap < earliest_pub:
            return None
        covered = min(covered, before_gap)
    return covered


async def sync_once(
    kap: KapClient,
    archive: AlarmArchive,
    *,
    resolver: TickerResolver,
    reviewer: EvidenceReviewer | None = None,
    statements: Mapping[str, Sequence[PublishedRow]] | None = None,
    universe: Sequence[str] | None = None,
    companies: Sequence[CompanyEntry] = (),
    origin: Origin = "kap_arsiv",
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    probe_unresolved: bool = False,
    probe_opaque: bool = False,
    max_unresolved_probes: int = 25,
    strict_watermark: bool = True,
) -> ScanReport:
    """Canlı KAP listesinden tek tur sessiz toplama yapar (arka plan zamanlayıcısı birimi)."""
    feed = await kap.light()
    return await ingest_feed(
        feed,
        archive,
        resolver=resolver,
        detail_fetcher=kap.detail,
        reviewer=reviewer,
        statements=statements,
        universe=universe,
        companies=companies,
        origin=origin,
        clock=clock,
        probe_unresolved=probe_unresolved,
        probe_opaque=probe_opaque,
        max_unresolved_probes=max_unresolved_probes,
        strict_watermark=strict_watermark,
    )


class KapCollectorService:
    """Tek uygulama / tek Render dağıtımı için arka plan sessiz KAP toplayıcısı.

    - Şirket unvan/OID listesini SQLite içinde önbellekler (`company_ttl`, varsayılan 24 saat).
    - KAP şirket listesi geçici hata verirse bayat önbellekle taramayı sürdürür.
    - `warmup()` ile soğuk başlangıç / restart sonrası izlenen hisselerin son `max_age`
      penceresindeki bildirimlerini gerçek gözlem saatiyle (`known_at`) arşive alır.
    - Eski imleç/tarama/sürüm satırlarını günde bir budar.
    """

    def __init__(
        self,
        archive_path: str | Path,
        *,
        universe: Sequence[str] | None = None,
        reviewer: EvidenceReviewer | None = None,
        statements: Mapping[str, Sequence[PublishedRow]] | None = None,
        kap: KapClient | None = None,
        company_ttl: timedelta = timedelta(hours=24),
        probe_opaque: bool = True,
        probe_unresolved: bool = False,
        max_unresolved_probes: int = 30,
        seen_retention_days: int = 14,
        version_retention_days: int | None = 30,
        origin: Origin = "kap_arsiv",
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self.archive_path = Path(archive_path)
        self.universe = tuple(dict.fromkeys(t.strip().upper() for t in universe if t.strip())) if universe else None
        self.reviewer = reviewer
        self.statements = statements
        self._external_kap = kap
        self.company_ttl = company_ttl
        self.probe_opaque = probe_opaque
        self.probe_unresolved = probe_unresolved
        self.max_unresolved_probes = max_unresolved_probes
        self.seen_retention_days = seen_retention_days
        self.version_retention_days = version_retention_days
        self.origin: Origin = origin
        self.clock = clock
        self._sleep = sleep
        self._log = logger or logging.getLogger(__name__)
        self._last_prune: datetime | None = None

    async def _ensure_companies(self, kap: KapClient, archive: AlarmArchive) -> list[CompanyEntry]:
        now = _now_utc(self.clock)
        fresh = archive.load_companies(as_of=now, max_age=self.company_ttl)
        if fresh:
            return fresh
        try:
            fetched = await fetch_companies(kap)
        except (KapError, CompanyMapError, OSError) as exc:
            stale = archive.load_companies(as_of=now, max_age=None)
            if stale:
                self._log.warning("KAP şirket listesi yenilenemedi, önbellek kullanılıyor: %s", exc)
                return stale
            raise
        archive.save_companies(fetched, updated_at=now)
        return fetched

    async def warmup(
        self,
        tickers: Sequence[str] | None = None,
        *,
        max_age: timedelta = DEFAULT_MAX_AGE,
        max_details_per_ticker: int = 10,
    ) -> ScanReport:
        """Restart sonrası izlenen hisselerin son `max_age` penceresindeki geçmişini doldurur."""
        targets = tuple(
            dict.fromkeys(t.strip().upper() for t in (tickers if tickers is not None else (self.universe or ())) if t.strip())
        )
        if not targets:
            return ScanReport(0, 0, {})

        async def _run(kap: KapClient) -> ScanReport:
            with open_archive(self.archive_path, writable=True) as archive:
                companies = await self._ensure_companies(kap, archive)
                oid_map = {c.ticker: c.oid for c in companies}
                resolver = build_company_resolver(companies, preferred=targets)
                now = _now_utc(self.clock)
                cutoff = now - max_age
                skew_ceiling = now + timedelta(seconds=60)
                today_trt = to_trt(now).date()
                stubs: list[DisclosureStub] = []
                seen_oids: set[str] = set()
                for ticker in targets:
                    oid = oid_map.get(ticker)
                    if not oid or oid in seen_oids:
                        continue
                    seen_oids.add(oid)
                    rows = await kap.fetch_history(oid, today=today_trt)
                    picked = 0
                    for row in rows:
                        row_pub = (
                            row.published_at.replace(tzinfo=TRT).astimezone(timezone.utc)
                            if row.published_at.utcoffset() is None
                            else row.published_at.astimezone(timezone.utc)
                        )
                        if row_pub < cutoff or row_pub > skew_ceiling:
                            continue
                        if route(row.disclosure_class, row.subject, row.summary) is not Route.PIPELINE:
                            continue
                        if is_low_signal_corporate(row.subject):
                            continue
                        stubs.append(DisclosureStub(
                            index=row.index,
                            published_at=row_pub,
                            title=ticker,
                            subject=row.subject,
                            summary=row.summary,
                            disclosure_class=row.disclosure_class,
                            tickers=(ticker,),
                            member_oid=oid,
                            minute_precision=True,
                        ))
                        picked += 1
                        if picked >= max_details_per_ticker:
                            break
                if not stubs:
                    return ScanReport(0, 0, {})
                return await ingest_feed(
                    ParseResult(stubs),
                    archive,
                    resolver=resolver,
                    detail_fetcher=kap.detail,
                    reviewer=self.reviewer,
                    statements=self.statements,
                    universe=targets,
                    companies=companies,
                    origin=self.origin,
                    clock=self.clock,
                    update_watermark=False,
                )

        if self._external_kap is not None:
            return await _run(self._external_kap)
        async with KapClient() as kap:
            return await _run(kap)

    async def run_once(self) -> ScanReport:
        """Şirket önbelleğini kontrol eder, tek tur tarama yapar ve gerekirse budar."""
        async def _run(kap: KapClient) -> ScanReport:
            with open_archive(self.archive_path, writable=True) as archive:
                companies = await self._ensure_companies(kap, archive)
                resolver = build_company_resolver(companies, preferred=self.universe)
                report = await sync_once(
                    kap,
                    archive,
                    resolver=resolver,
                    reviewer=self.reviewer,
                    statements=self.statements,
                    universe=self.universe,
                    companies=companies,
                    origin=self.origin,
                    clock=self.clock,
                    probe_unresolved=self.probe_unresolved,
                    probe_opaque=self.probe_opaque,
                    max_unresolved_probes=self.max_unresolved_probes,
                    strict_watermark=True,
                )
                now = _now_utc(self.clock)
                if self._last_prune is None or now - self._last_prune >= timedelta(hours=24):
                    archive.prune(
                        now,
                        seen_days=self.seen_retention_days,
                        version_days=self.version_retention_days,
                        origin=self.origin,
                    )
                    self._last_prune = now
                return report

        if self._external_kap is not None:
            return await _run(self._external_kap)
        async with KapClient() as kap:
            return await _run(kap)

    async def run_forever(
        self,
        *,
        interval_seconds: float = 180.0,
        warmup_on_start: bool = False,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Ana uygulama içinde `asyncio.create_task` ile çalıştırılacak dayanıklı döngü."""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds pozitif olmalı")

        async def _loop(kap: KapClient) -> None:
            bound = KapCollectorService(
                self.archive_path,
                universe=self.universe,
                reviewer=self.reviewer,
                statements=self.statements,
                kap=kap,
                company_ttl=self.company_ttl,
                probe_opaque=self.probe_opaque,
                probe_unresolved=self.probe_unresolved,
                max_unresolved_probes=self.max_unresolved_probes,
                seen_retention_days=self.seen_retention_days,
                version_retention_days=self.version_retention_days,
                origin=self.origin,
                clock=self.clock,
                sleep=self._sleep,
                logger=self._log,
            )
            if warmup_on_start and self.universe:
                need_warmup = True
                if self.archive_path.exists():
                    with open_archive(self.archive_path) as reader:
                        need_warmup = reader.last_scan(origin=self.origin) is None
                if need_warmup:
                    try:
                        await bound.warmup(self.universe)
                    except Exception as exc:
                        self._log.warning("KAP başlangıç ısınması tamamlanamadı: %s", exc)

            while stop_event is None or not stop_event.is_set():
                try:
                    report = await bound.run_once()
                    if report.suspicious_empty:
                        self._log.warning("KAP /list/light boş döndü; tarama damgası ilerletilmedi")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._log.warning("KAP tarama turu hatası (sonraki turda denenecek): %s", exc)
                if stop_event is not None:
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                        break
                    except TimeoutError:
                        continue
                await self._sleep(interval_seconds)

        if self._external_kap is not None:
            await _loop(self._external_kap)
            return
        async with KapClient() as kap:
            await _loop(kap)
