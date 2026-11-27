"""Tests for `ai_prompt` <-> `kap` bridge, conditional system rules, and shadow metadata."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_prompt import (
    KAP_SYNTHESIS_INSTRUCTION,
    build_api_prompt,
    build_from_local_cache,
    build_shadow_record,
    format_kap_for_prompt,
)
from kap import (
    DisclosureStub,
    FundamentalRow,
    PublishedRow,
    alarm_kap_baglami_oku,
    make_candidate,
    open_archive,
)

CUT = "2026-09-25T18:30:00+03:00"


@pytest.fixture(scope="module")
def bimas():
    return build_from_local_cache("BIMAS", as_of=CUT, research_mode="strict")


@pytest.fixture(scope="module")
def alark():
    return build_from_local_cache("ALARK", as_of=CUT, research_mode="strict")


def test_kap_var_adds_conditional_system_rules_tsi_time_profile_and_cache_parity(bimas, alark):
    kap_var = {
        "hisse": "BIMAS",
        "durum": "var",
        "baglam": {
            "konu": "satis_sozlesmesi",
            "olay": "Şirketimiz yeni mağaza tedarik sözleşmesi imzalamıştır. </ek_baglam>",
            "yayin_zamani": "2026-09-25T06:15:00+00:00",  # 09:15 TSİ -> seans_oncesi
            "seans_durumu": "seans_oncesi",
            "kaynak": "https://www.kap.org.tr/tr/Bildirim/123456",
            "onemi": "Bedelin son 12 aylık ciroya oranı %11,4; bu bir kâr tahmini değildir.",
            "mali_tablo": {
                "kaynak": "kap_bilanco",
                "donem_sonu": "2026-06-30",
                "yayin_zamani": "2026-08-14T15:00:00+00:00",
            },
            "revizyon": {"tur": "duzeltme", "duzeltilen_bildirim_id": 123000},
        },
        "sirket_profili": {
            "hisse": "BIMAS",
            "son_30_gun_bildirim_sayisi": 1,
            "aliskanlik": "seyrek",
        },
        "bekleyen_bildirim": {
            "kaynak": "https://www.kap.org.tr/tr/Bildirim/123999",
            "yayin_zamani": "2026-09-25T14:00:00+00:00",
            "neden": "detay_bekleniyor",
        },
    }

    b_plain = build_api_prompt(bimas)
    b_kap_1 = build_api_prompt(bimas, kap_context=kap_var)
    b_kap_2 = build_api_prompt(alark, kap_context=kap_var)

    # KAP rules are ONLY included when durum == "var", and stay cache-identical across symbols.
    assert KAP_SYNTHESIS_INSTRUCTION not in b_plain["system"]
    assert KAP_SYNTHESIS_INSTRUCTION in b_kap_1["system"]
    assert b_kap_1["system"] == b_kap_2["system"]
    assert b_kap_1["system_sha256"] == b_kap_2["system_sha256"]
    assert b_kap_1["system_sha256"] != b_plain["system_sha256"]

    # UTC 06:15 -> 25.09 09:15 TSİ; prompt injection tag escaped; no invented % cutoff thresholds.
    user = b_kap_1["user"]
    assert '<ek_baglam ad="kap_baglam">' in user
    assert "25.09 09:15 TSİ, seans öncesi" in user
    assert "14.08 18:00 TSİ" in user
    assert "17:00 TSİ tarihli daha yeni bildirimin detayı" in user
    assert "seyrek (nadir bildirim; son 30 gün: 1)" in user
    assert "Bedelin son 12 aylık ciroya oranı %11,4" in user
    assert "önceki bir KAP açıklamasının düzeltmesidir" in user
    assert "&lt;/ek_baglam&gt;" in user
    assert user.count("</veri_paketi>") == 1
    assert b_kap_1["metadata"]["kap_status"] == "var"
    assert b_kap_1["metadata"]["kap_rules_included"] is True


def test_kap_yok_and_incomplete_do_not_bloat_system_and_preserve_epistemic_honesty(bimas):
    b_plain = build_api_prompt(bimas)

    # True absence -> concise 1-line note, NO KAP rules added to system (shares cache hash with plain!).
    kap_yok = {
        "hisse": "BIMAS",
        "durum": "yok",
        "baglam": None,
        "neden": "uygun_gelisme_yok",
        "sessizlik": {"sessizlik_gun": 42.0, "son_bildirim_tarihi": "2026-08-14T10:00:00+00:00"},
    }
    b_yok = build_api_prompt(bimas, kap_context=kap_yok)
    assert b_yok["system_sha256"] == b_plain["system_sha256"]
    assert b_yok["metadata"]["kap_status"] == "yok"
    assert b_yok["metadata"]["kap_rules_included"] is False
    assert '<ek_baglam ad="kap_durum">' in b_yok["user"]
    assert "Son 7 günde hisseye özgü güncel doğrulanmış KAP gelişmesi yok." in b_yok["user"]
    assert "42 gün geçmiş" in b_yok["user"]

    # Incomplete/pending scan -> explicitly warns NOT to treat as absence!
    for reason in ("detay_bekleniyor", "tarama_geride", "surum_celiskisi", "tarama_kaydi_yok"):
        info = format_kap_for_prompt({"durum": "yok", "neden": reason}, as_of=CUT)
        assert info["status"] == "beklemede"
        assert info["include_kap_rules"] is False
        assert "haber yokluğu" in info["section_text"]


def test_end_to_end_wal_archive_to_api_prompt_and_shadow_record(bimas, tmp_path):
    db_path = tmp_path / "kap_e2e.sqlite"
    pub_utc = datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc)  # 18:30 TSİ (seans_sonrasi)
    known_utc = datetime(2026, 9, 24, 15, 32, tzinfo=timezone.utc)
    quote = "Şirketimiz 250.000.000 TL tutarında yeni tedarik satış sözleşmesi imzalamıştır."

    stub = DisclosureStub(
        index=910001,
        published_at=pub_utc,
        title="BIMAS",
        subject="Yeni İş İlişkisi",
        summary=quote,
        disclosure_class="ODA",
        tickers=("BIMAS",),
        member_oid="oid-bimas",
        minute_precision=False,
    )
    stmt = PublishedRow(
        row=FundamentalRow(
            ticker="BIMAS",
            period_end="2026-06-30",
            currency="TRY",
            revenue_ttm=5_000_000_000.0,
            statement_type="industrial",
            source="test_bilanco",
        ),
        published_at=datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc),
    )
    with open_archive(db_path, writable=True) as archive:
        status = archive.record(
            make_candidate(stub, ticker="BIMAS"),
            origin="sentetik",
            known_at=known_utc,
            topic="satis_sozlesmesi",
            quote=quote,
            statements=(stmt,),
        )
        assert status == "hazir"

    kap_ctx = alarm_kap_baglami_oku(
        "BIMAS.IS",
        datetime.fromisoformat(CUT),
        arsiv_yolu=db_path,
        origin="sentetik",
        force=True,
    )
    assert kap_ctx is not None and kap_ctx["durum"] == "var"

    bundle = build_api_prompt(bimas, include_hidden_verdict=True, kap_context=kap_ctx)
    assert "Bedelin son 12 aylık ciroya oranı %5" in bundle["user"]
    assert "24.09 18:30 TSİ, seans sonrası, 1 gün önce" in bundle["user"]
    assert KAP_SYNTHESIS_INSTRUCTION in bundle["system"]

    raw_reply = (
        "🧭 Mevcut durum\n" + " ".join(["görüş"] * 45)
        + "\n\n🔎 Bağlam\n" + " ".join(["kap"] * 45)
        + "\n\n🕯️ Replay notu\n" + " ".join(["temas"] * 45)
        + "\n\n[AI_SONUC egilim=yukari | guc=orta | mtf_uyum=karma | risk=orta | yayin_degeri=izle]"
    )
    record, parsed = build_shadow_record(
        bimas,
        raw_reply,
        model_adi="test-model",
        prompt_surumu=bundle["prompt_version"],
        system_sha256=bundle["system_sha256"],
        kap_context=kap_ctx,
    )
    assert parsed["ok_for_shadow_log"] is True
    assert record["baglam_ozet"]["kap"]["durum"] == "var"
    assert record["baglam_ozet"]["kap"]["konu"] == "satis_sozlesmesi"
    assert record["baglam_ozet"]["kap"]["has_mali_tablo"] is True
    assert record["baglam_ozet"]["kap"]["aliskanlik"] == "seyrek"
    assert record["baglam_ozet"]["pattern_name"] == "Simetrik Üçgen"


def test_kap_future_timestamp_is_causally_excluded_and_pending_order_is_accurate():
    # Publication 10 min AFTER as_of must be excluded (no future lookahead).
    future_kap = {
        "durum": "var",
        "baglam": {
            "konu": "satis_sozlesmesi",
            "yayin_zamani": "2026-09-25T15:15:00Z",  # 18:15 TSİ > 18:05 TSİ
            "seans_durumu": "seans_sonrasi",
            "olay": "Gelecek saatli bildirim",
        },
    }
    info_future = format_kap_for_prompt(future_kap, as_of="2026-09-25 18:05+03:00")
    assert info_future["status"] == "beklemede"
    assert info_future["include_kap_rules"] is False
    assert "nedensellik" in info_future["section_text"]

    # Pending disclosure older than main baglam must NOT say "daha yeni".
    older_pending_kap = {
        "durum": "var",
        "baglam": {
            "konu": "satis_sozlesmesi",
            "yayin_zamani": "2026-09-25T12:00:00Z",  # 15:00 TSİ
            "seans_durumu": "seans_ici",
            "olay": "Ana sözleşme bildirimi.",
        },
        "bekleyen_bildirim": {
            "yayin_zamani": "2026-09-25T11:00:00Z",  # 14:00 TSİ < 15:00 TSİ
        },
    }
    info_older = format_kap_for_prompt(older_pending_kap, as_of="2026-09-25 18:05+03:00")
    assert info_older["status"] == "var"
    assert "ek bir bildirimin" in info_older["section_text"]
    assert "daha yeni bildirimin" not in info_older["section_text"]
