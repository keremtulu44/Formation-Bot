from types import SimpleNamespace

from notification_context import format_domain_context


def _result(export=None, **attrs):
    return SimpleNamespace(export=export, skipped=False, error=None, **attrs)


def test_domain_context_renders_existing_exports_and_omits_empty_domains():
    event = SimpleNamespace(
        event_uid="external-bos-1",
        scope="EXTERNAL",
        event_type="EVENT_BOS",
        event_bar=12,
        broken_level=101.5,
        direction=1,
        validity="VALID",
        relevance="CURRENT",
        confirmation_status="CONFIRMED",
        is_active=True,
    )
    market_structure = SimpleNamespace(
        external_scope=SimpleNamespace(state="STATE_BULLISH"),
        internal_scope=SimpleNamespace(state="STATE_NEUTRAL"),
        events=[event],
        external_protected_high=110.0,
        external_protected_low=90.0,
        external_weak_high=None,
        external_weak_low=None,
    )
    order_blocks = SimpleNamespace(
        bull=SimpleNamespace(top=104.0, bottom=102.0, fill=0.25),
        bear=SimpleNamespace(top=None, bottom=None, fill=None),
    )
    fvgs = SimpleNamespace(
        bull_fvg=SimpleNamespace(state=3, top=98.0, bottom=96.0, fill=0.5, quality=82),
        bear_fvg=SimpleNamespace(state=7, top=110.0, bottom=108.0, fill=1.0, quality=90),
    )
    volume = SimpleNamespace(
        state="PARTICIPATION_UP_CONFIRMED",
        rvol=1.7,
        relative_traded_value=1.4,
        volume_level="HIGH",
        capital_level="RISING",
        absorption_stage="NONE",
        break_stage="NONE",
    )
    outputs = {
        "1h": {
            "market_structure": _result(market_structure),
            "order_block": _result(order_blocks),
            # The native runner marks 1h FVG unsupported; do not invent it.
            "fvg": SimpleNamespace(skipped=True, export=fvgs, error=None),
            "volume_participation": _result(volume),
        },
        "2h": {"fvg": _result(fvgs)},
        "4h": {"market_structure": SimpleNamespace(error="engine error", export=None)},
        "1d": {"order_block": _result(None)},
    }

    context = format_domain_context(outputs, reference_price=100.0)

    assert "🏗 Piyasa Yapısı" in context
    assert "1s yapı: dış yükseliş · iç yatay" in context
    # `teyitli` bilinçli olarak basılmaz: filtre yalnız CONFIRMED olayları bırakır,
    # yani kelime her satırda aynı sabit metindir (bilgi taşımaz).
    assert "BOS ↑ 101,50 · dış · geçerli güncel" in context
    assert "· teyitli geçerli" not in context  # MS satırındaki sabit kelime kaldırıldı
    assert "PH 110,00 (korunan, güncel)" in context
    assert "🧱 Order Block" in context and "Üst: 1s boğa OB 102,00–104,00 TL" in context
    assert "%25 dolu" in context
    assert "🟪 Fair Value Gap" in context and "Alt: 2s boğa FVG 96,00–98,00 TL" in context
    # `aktif` yalnız FVG'nin gerçek yaşam döngüsü kodundan gelir; OB tarafının
    # state alanı ±1 işaret olduğu için orada sabit süs olarak basılmaz.
    assert "boğa FVG 96,00–98,00 TL · aktif · %50 dolu" in context
    assert "boğa OB 102,00–104,00 TL · %25 dolu" in context
    assert "📊 Hacim / Katılım" in context
    assert "yukarı katılım teyitli" in context
    assert "Son mum hacmi / 20 mumluk ortalama: 1,70× (RVOL)" in context
    assert "göreli işlem değeri 1,40×" in context
    assert "Piyasa yapısı analizi tamamlanamadı" in context
    assert "bear FVG" not in context and "4s yapı" not in context
    assert "kalite 82" not in context and "kalite 90" not in context


def test_domain_context_missing_skipped_or_failed_outputs_have_no_empty_headings():
    context = format_domain_context({
        "1h": {
            "market_structure": None,
            "order_block": SimpleNamespace(skipped=True, export=object(), error=None),
            "fvg": SimpleNamespace(error="failed", export=object(), skipped=False),
            "volume_participation": _result(None),
        },
        "2h": {},
    })
    assert context == ""


def test_market_structure_error_is_explicit_not_reported_as_empty_findings():
    context = format_domain_context({
        "1h": {
            "market_structure": SimpleNamespace(
                error="engine failed", export=None, skipped=False
            )
        }
    })
    assert "Piyasa yapısı analizi tamamlanamadı" in context
    assert "bulgu yok" not in context.lower()


def test_at_most_one_best_ob_and_fvg_candidate_per_side_and_no_raw_scores():
    outputs = {
        "1h": {
            "order_block": _result(SimpleNamespace(
                bull=SimpleNamespace(top=112.0, bottom=110.0, fill=0.2),
                bear=SimpleNamespace(top=92.0, bottom=90.0, fill=0.3),
            )),
            "fvg": _result(SimpleNamespace(
                bull_fvg=SimpleNamespace(state=3, top=115.0, bottom=113.0, fill=0.1, quality=70),
                bear_fvg=SimpleNamespace(state=3, top=89.0, bottom=87.0, fill=0.2, quality=75),
            )),
        },
        "2h": {
            "order_block": _result(SimpleNamespace(
                bull=SimpleNamespace(top=106.0, bottom=104.0, fill=0.4),
                bear=SimpleNamespace(top=98.0, bottom=96.0, fill=0.5),
            )),
            "fvg": _result(SimpleNamespace(
                bull_fvg=SimpleNamespace(state=3, top=109.0, bottom=107.0, fill=0.6, quality=96),
                bear_fvg=SimpleNamespace(state=3, top=95.0, bottom=93.0, fill=0.7, quality=91),
            )),
        },
    }

    context = format_domain_context(outputs, reference_price=100.0)

    assert context.count("• Üst:") == 2
    assert context.count("• Alt:") == 2
    assert "2s boğa OB 104,00–106,00 TL" in context  # nearest exported OB above
    assert "2s ayı OB 96,00–98,00 TL" in context  # nearest exported OB below
    assert "2s boğa FVG 107,00–109,00 TL" in context  # best exported quality above
    assert "2s ayı FVG 93,00–95,00 TL" in context  # best exported quality below
    assert "kalite 96" not in context and "kalite 91" not in context
    assert "kalite 70" not in context and "kalite 75" not in context


# --- Üst TF yapı yedeği (public'te boş yapı bloğu) -------------------------

def _ms(dis, ic):
    return SimpleNamespace(
        external_scope=SimpleNamespace(state=dis),
        internal_scope=SimpleNamespace(state=ic),
        events=[],
        external_protected_high=None, external_protected_low=None,
        external_weak_high=None, external_weak_low=None,
    )


def _yapi_ozet(outputs, alarm_tf):
    import notification_context as nc
    return nc.domain_bolumleri(outputs, 100.0, stil="kart",
                               alarm_tf=alarm_tf).get("yapi_ozet") or []


def test_alarm_tf_yapisi_yoksa_ust_tf_satiri_basilir():
    """Public bültende yapı bloğu boş kalıyordu: alarm TF'si MS üretmediyse
    (motor atladı/hata) satır tamamen düşüyordu. Artık üst TF yedeği var ve
    satır KENDİ etiketiyle yazılır (`4s`, `1s` değil)."""
    outputs = {
        "1h": {"market_structure": SimpleNamespace(skipped=True, export=None, error=None)},
        "4h": {"market_structure": _result(_ms("STATE_BEARISH", "STATE_BEARISH"))},
    }
    ozet = _yapi_ozet(outputs, "1h")
    assert ozet == ["◈ 4s yön aşağı (iç ve dış yapı)"]


def test_ust_tf_yedegi_alarm_tf_satiri_varsa_devreye_girmez():
    outputs = {
        "1h": {"market_structure": _result(_ms("STATE_BULLISH", "STATE_NEUTRAL"))},
        "4h": {"market_structure": _result(_ms("STATE_BEARISH", "STATE_BEARISH"))},
    }
    assert _yapi_ozet(outputs, "1h") == ["◈ 1s yön karışık (dış yukarı, iç yatay)"]


def test_ust_tf_de_yoksa_yapi_satiri_uydurulmaz():
    """Yedek de boşsa satır yok: boş yapı yerine uydurma cümle yazılmaz."""
    outputs = {"1h": {"market_structure": SimpleNamespace(skipped=True, export=None,
                                                          error=None)}}
    assert _yapi_ozet(outputs, "1h") == []
