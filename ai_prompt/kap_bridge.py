"""KAP arşivi çıktısını `ai_prompt` API istemine bağlayan saf, ağsız köprü.

Görevleri:
  1) `kap.baglam` UTC saatlerini Formation-Bot'un İstanbul (TSİ) saatine çevirmek.
  2) `durum="var"`, `durum="yok"` (gerçek yokluk) ve belirsiz/bekleyen
     (`detay_bekleniyor`, `surum_celiskisi`, `tarama_geride`, `tarama_kaydi_yok`)
     durumlarını birbirine karıştırmadan açıkça ayırmak.
  3) Yalnızca doğrulanmış haber (`durum="var"`) olduğunda statik ve
     önbelleklenebilir KAP sentez kuralının `system` mesajına eklenmesini işaretlemek.
  4) Bilanço/sözleşme oranı verilmişse olduğu gibi aktarmak (keyfi eşik uydurmamak),
     dış metni karakter bütçesinde ve güvenli veri sınırında tutmak.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd

_MAX_KAP_SECTION_CHARS = 950
_MAX_QUOTE_CHARS = 480

_KONU_LABELS: dict[str, str] = {
    "satis_sozlesmesi": "satış/iş sözleşmesi",
    "uretim_durusu": "üretim/faaliyet duruşu",
    "sirket_aciklamasi": "şirket açıklaması",
    "endeks_parametresi": "piyasa/endeks duyurusu",
}

_SEANS_LABELS: dict[str, str] = {
    "seans_ici": "seans içi",
    "seans_oncesi": "seans öncesi",
    "seans_sonrasi": "seans sonrası",
    "hafta_sonu": "hafta sonu",
}

_ALISKANLIK_LABELS: dict[str, str] = {
    "seyrek": "seyrek (son 30 günde nadir bildirim)",
    "normal": "normal",
    "sik": "sık (son 30 günde düzenli/sık bildirim)",
}

_INCOMPLETE_REASONS = frozenset({
    "detay_bekleniyor",
    "surum_celiskisi",
    "tarama_geride",
    "tarama_kaydi_yok",
})

KAP_SYNTHESIS_INSTRUCTION = (
    "KAP VE MALİ BAĞLAM (`<ek_baglam ad=\"kap_baglam\">`)\n"
    "- Haberi ayrı başlık açmadan üç başlığın içine (özellikle Mevcut durum ve Bağlam) yedir; olası "
    "etkisini teknik görünümle birlikte koşullu dille değerlendir.\n"
    "- Teknikle haber/mali bağlam aynı yöndeyse destekleyici arka plan, ayrışıyorsa açık karşı risk "
    "olarak yaz; birini diğerine ezdirme, kanıtlanmamış doğrudan sebep-sonuç kurma.\n"
    "- Bildirim alışkanlığını (seyrek/normal/sık) ve zamanlamayı (seans öncesi/sonrası, hafta sonu, "
    "yayın yaşı) ağırlıkta gözet; yeni/seans dışı haberde ilk tepkiyle sonraki kapanışı ayır.\n"
    "- Sözleşme/ciro oranı ve mali tablo varsa olduğu gibi kullan, kâr tahmini çıkarma; tablo/kur sınırı "
    "varsa ölçek uydurma. Revizyon veya bekleyen bildirim varsa ek belirsizlik notu düş."
)


def _clean_inline(text: Any, *, limit: int | None = None) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", str(text or "")).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if limit is not None and len(cleaned) > limit:
        return cleaned[: max(0, limit - 1)].rstrip() + "…"
    return cleaned


def _to_istanbul(ts: Any) -> pd.Timestamp | None:
    if ts is None or ts == "":
        return None
    try:
        stamp = pd.Timestamp(ts)
    except (TypeError, ValueError):
        return None
    if pd.isna(stamp):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert("Europe/Istanbul")


def _fmt_ist(ts: Any, *, ref_year: int | None = None) -> str:
    stamp = _to_istanbul(ts)
    if stamp is None:
        return "bilinmiyor"
    if ref_year is not None and stamp.year == ref_year:
        return stamp.strftime("%d.%m %H:%M")
    return stamp.strftime("%d.%m.%Y %H:%M")


def _age_label(pub_ts: Any, as_of: Any) -> str:
    pub = _to_istanbul(pub_ts)
    cut = _to_istanbul(as_of)
    if pub is None or cut is None:
        return ""
    diff_sec = (cut - pub).total_seconds()
    if diff_sec < 0:
        return ""
    days = (cut.date() - pub.date()).days
    if days == 0:
        hours = int(diff_sec // 3600)
        return "aynı gün" if hours < 1 else f"aynı gün, {hours} saat önce"
    return f"{days} gün önce"


def _extract_profile(kap_context: Mapping[str, Any]) -> tuple[str | None, int | None]:
    prof = kap_context.get("sirket_profili")
    if not isinstance(prof, Mapping):
        return None, None
    habit = str(prof.get("aliskanlik") or "").strip().lower() or None
    count: int | None = None
    for key, val in prof.items():
        if str(key).startswith("son_") and str(key).endswith("_bildirim_sayisi"):
            try:
                count = int(val)
            except (TypeError, ValueError):
                count = None
            break
    return habit, count


def format_kap_for_prompt(
    kap_context: Mapping[str, Any] | None,
    *,
    as_of: Any = None,
    max_age_gun: int = 7,
) -> dict[str, Any]:
    """`alarm_kap_baglami_oku` çıktısını prompt için temiz, TSİ-uyumlu bloğa çevirir."""
    if not isinstance(kap_context, Mapping):
        return {
            "status": "kapali",
            "include_kap_rules": False,
            "section_name": None,
            "section_text": "",
            "meta_summary": None,
        }

    durum = str(kap_context.get("durum") or "").strip().lower()
    cut_ist = _to_istanbul(as_of)
    ref_year = cut_ist.year if cut_ist is not None else None

    if durum == "var" and isinstance(kap_context.get("baglam"), Mapping):
        baglam = kap_context["baglam"]
        konu_raw = str(baglam.get("konu") or "").strip()
        konu_tr = _KONU_LABELS.get(konu_raw, konu_raw or "bildirim")
        seans_raw = str(baglam.get("seans_durumu") or "").strip()
        seans_tr = _SEANS_LABELS.get(seans_raw, seans_raw)
        yayin_ist = _fmt_ist(baglam.get("yayin_zamani"), ref_year=ref_year)
        yas = _age_label(baglam.get("yayin_zamani"), as_of)
        olay = _clean_inline(baglam.get("olay"), limit=_MAX_QUOTE_CHARS)
        habit, count_30 = _extract_profile(kap_context)

        when_parts = [f"{yayin_ist} TSİ"]
        if seans_tr:
            when_parts.append(seans_tr)
        if yas:
            when_parts.append(yas)

        lines: list[str] = [
            f"Durum: doğrulanmış KAP gelişmesi var ({konu_tr}; {', '.join(when_parts)}).",
        ]
        if olay:
            lines.append(f"Doğrulanmış metin: {olay}")

        onemi = _clean_inline(baglam.get("onemi"), limit=220)
        if onemi:
            lines.append(f"Ölçek/önem notu: {onemi}")

        mali = baglam.get("mali_tablo")
        if isinstance(mali, Mapping):
            m_parts: list[str] = []
            if mali.get("donem_sonu"):
                m_parts.append(f"dönem sonu {mali['donem_sonu']}")
            if mali.get("yayin_zamani"):
                m_parts.append(f"tablo yayını {_fmt_ist(mali['yayin_zamani'], ref_year=ref_year)} TSİ")
            if mali.get("kaynak"):
                m_parts.append(f"kaynak {_clean_inline(mali['kaynak'], limit=60)}")
            if m_parts:
                lines.append("Referans mali tablo: " + ", ".join(m_parts) + ".")

        if habit:
            habit_tr = _ALISKANLIK_LABELS.get(habit, habit)
            if count_30 is not None:
                lines.append(f"Şirket bildirim alışkanlığı: {habit_tr} (son 30 gün: {count_30}).")
            else:
                lines.append(f"Şirket bildirim alışkanlığı: {habit_tr}.")

        rev = baglam.get("revizyon")
        if isinstance(rev, Mapping):
            lines.append("Revizyon notu: Bu bildirim önceki bir KAP açıklamasının düzeltmesidir.")

        pending = kap_context.get("bekleyen_bildirim")
        if isinstance(pending, Mapping):
            p_time = _fmt_ist(pending.get("yayin_zamani"), ref_year=ref_year)
            lines.append(f"Bekleyen bildirim: {p_time} TSİ tarihli daha yeni bildirimin detayı henüz bekleniyor.")

        section_text = "\n".join(lines)
        if len(section_text) > _MAX_KAP_SECTION_CHARS:
            # Trim only the raw quote body so structured metadata (habit/timing/warnings) is never lost.
            overflow = len(section_text) - _MAX_KAP_SECTION_CHARS + 16
            shorter_quote = _clean_inline(baglam.get("olay"), limit=max(120, _MAX_QUOTE_CHARS - overflow))
            lines[1] = f"Doğrulanmış metin: {shorter_quote}"
            section_text = "\n".join(lines)[:_MAX_KAP_SECTION_CHARS].rstrip()

        return {
            "status": "var",
            "include_kap_rules": True,
            "section_name": "kap_baglam",
            "section_text": section_text,
            "meta_summary": {
                "durum": "var",
                "neden": None,
                "konu": konu_raw or None,
                "yayin_zamani": baglam.get("yayin_zamani"),
                "seans_durumu": seans_raw or None,
                "aliskanlik": habit,
                "son_30_gun_bildirim_sayisi": count_30,
                "has_mali_tablo": isinstance(mali, Mapping),
                "has_revizyon": isinstance(rev, Mapping),
                "has_bekleyen_bildirim": isinstance(pending, Mapping),
                "kaynak": baglam.get("kaynak"),
            },
        }

    # durum == "yok" -> distinguish true absence vs incomplete/pending scan!
    neden = str(kap_context.get("neden") or "uygun_gelisme_yok").strip().lower()
    sessizlik = kap_context.get("sessizlik") if isinstance(kap_context.get("sessizlik"), Mapping) else None
    sessizlik_gun = sessizlik.get("sessizlik_gun") if sessizlik is not None else None

    if neden in _INCOMPLETE_REASONS:
        reason_text_map = {
            "detay_bekleniyor": (
                "KAP durumu: Kesit penceresinde detayı henüz beklenmekte olan bir bildirim var; "
                "bunu haber yokluğu sayma."
            ),
            "surum_celiskisi": (
                "KAP durumu: Kesit penceresindeki bildirim sürümü doğrulama çelişkisinde; "
                "bunu haber yokluğu sayma."
            ),
            "tarama_geride": (
                "KAP durumu: KAP arşiv taraması kesit saatine göre geride; haber yokluğu doğrulanmadı."
            ),
            "tarama_kaydi_yok": (
                "KAP durumu: KAP arşivinde bu kesit için tarama kaydı yok; haber yokluğu doğrulanmadı."
            ),
        }
        return {
            "status": "beklemede",
            "include_kap_rules": False,
            "section_name": "kap_durum",
            "section_text": reason_text_map[neden],
            "meta_summary": {
                "durum": "yok",
                "neden": neden,
                "konu": None,
                "sessizlik_gun": sessizlik_gun,
                "son_tarama": kap_context.get("son_tarama"),
            },
        }

    days_window = max(1, int(max_age_gun))
    no_news_line = f"Son {days_window} günde hisseye özgü güncel doğrulanmış KAP gelişmesi yok."
    if sessizlik_gun is not None:
        try:
            g_val: float | None = float(sessizlik_gun)
        except (TypeError, ValueError):
            g_val = None
        if g_val is not None and g_val >= days_window:
            g_str = f"{g_val:.0f}" if g_val >= 10 else f"{g_val:.1f}".replace(".", ",")
            no_news_line += f" (Son doğrulanmış bildirimden bu yana {g_str} gün geçmiş.)"

    return {
        "status": "yok",
        "include_kap_rules": False,
        "section_name": "kap_durum",
        "section_text": no_news_line,
        "meta_summary": {
            "durum": "yok",
            "neden": neden,
            "konu": None,
            "sessizlik_gun": sessizlik_gun,
            "son_tarama": kap_context.get("son_tarama"),
        },
    }
