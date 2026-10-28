"""MS kilitli-referans koruması: aday fork'unda saklanan snapshot + arşiv regresyonu.

Bu dosya 2026-10-28 denetiminde bulunan ve 704 serilik arşiv koşusunda 35 seride
görülen kırılmayı kilitler (bkz. docs/denetim/MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md):

Bir kırılım adayı (BOS/CHOCH) henüz **geçici** (provisional) bir swing'i origin/target
olarak referans alırken, aday slotuna daha güçlü bir pivot gelirse slot "prior identity
locked by break" kuralıyla **fork** edilir ve eski snapshot slottan çıkar. Eskiden bu
snapshot hiçbir yerde saklanmadığı için `finalize_confirmed_break` "confirmed break
references must still be active" ile patlardı ve `runner._execute_domain` hatayı
yuttuğu için o sembolün MS domaini **sessizce boş** kalırdı.

Koruma üç katman:
1. `MarketStructureEngine._candidate_update` — fork anında eski snapshot runtime'da
   kimlikle saklanır (`retain_locked_snapshot`).
2. `MarketStructureRuntimeBridge.process_scope` — recovery, slotta eş bulamazsa
   saklanan snapshot'ı dener (`pop_retained_snapshot`).
3. Aday çözüldüğünde (onay ya da false break) saklananlar temizlenir; bayat entry kalmaz.

Testler sentetik unit + gerçek arşiv regresyonu (arşiv yoksa atlanır) olarak iki katman;
sentetik katman `backfill_data/` olmadan da koşar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_KOKU = Path(__file__).resolve().parent
if str(REPO_KOKU) not in sys.path:
    sys.path.insert(0, str(REPO_KOKU))

from domain_engines.market_structure.market_structure import (  # noqa: E402
    CANDIDATE_NEW,
    SCOPE_EXTERNAL,
    SIDE_LOW,
    MarketStructureConfig,
    SwingPoint,
)
from domain_engines.market_structure.market_structure_engine import (  # noqa: E402
    MarketStructureEngine,
)
from domain_engines.market_structure.market_structure_state import (  # noqa: E402
    BreakCandidate,
)


def _kilitli_aday_motoru() -> MarketStructureEngine:
    """EXTERNAL scope'ta bekleyen bir break candidate'i olan motor kurar.

    Origin, aday slotundaki GEÇİCİ bir swing'e (identity=7, source_bar=10)
    işaret eder — arşivde patlayan senaryonun birebir minyatürü.
    """
    motor = MarketStructureEngine(config=MarketStructureConfig(profile="Dengeli"))
    motor._runtime.external.candidate = BreakCandidate(
        valid=True,
        identity=1,
        scope=SCOPE_EXTERNAL,
        direction=1,
        candidate_bar=20,
        broken_swing_identity=3,
        broken_source_bar=5,
        origin_swing_identity=7,
        origin_source_bar=10,
    )
    return motor


def _aday_snapshot(identity: int = 7, source_bar: int = 10, price: float = 100.0) -> SwingPoint:
    return SwingPoint(
        valid=True,
        identity=identity,
        scope=SCOPE_EXTERNAL,
        side=SIDE_LOW,
        source_bar=source_bar,
        confirm_bar=source_bar,
        price=price,
        atr_at_source=1.0,
        prominence_atr=0.9,
        distance_atr=1.2,
        quality=60.0,
    )


def test_kilitli_aday_fork_edilince_eski_snapshot_saklanir():
    """Kilit aktifken slot fork edilirse eski snapshot runtime'da saklanır."""
    motor = _kilitli_aday_motoru()
    slot = _aday_snapshot()
    # Daha güçlü (daha düşük) yeni tepe: fork tetiklenmeli.
    incoming = _aday_snapshot(identity=99, source_bar=12, price=95.0)

    updated, action = motor._candidate_update(slot, incoming, locked_by_break=False)

    assert action == CANDIDATE_NEW
    # Fork kimliği slotu taze kimliğe taşır; eski kimlik slotta kalmaz.
    assert updated.identity == 99
    saklanan = motor._runtime.external.retained_locked
    assert 7 in saklanan, "kilitli referans fork anında saklanmalıydı"
    assert saklanan[7].source_bar == 10
    assert saklanan[7].price == 100.0


def test_saklanan_snapshot_tek_kullanimlik_ve_source_bar_ile_eslesmeli():
    """Recovery snapshot'ı yalnız doğru kimlik+source_bar ile alınır ve tüketilir."""
    motor = _kilitli_aday_motoru()
    motor._runtime.retain_locked_snapshot(SCOPE_EXTERNAL, _aday_snapshot())

    # Yanlış source_bar eşleşmez ve entry'yi tüketmez.
    yanlis = motor._runtime.pop_retained_snapshot(SCOPE_EXTERNAL, 7, 11)
    assert not yanlis.valid
    assert 7 in motor._runtime.external.retained_locked

    # Doğru eşleşme verir ve tüketir.
    dogru = motor._runtime.pop_retained_snapshot(SCOPE_EXTERNAL, 7, 10)
    assert dogru.valid and dogru.identity == 7
    assert 7 not in motor._runtime.external.retained_locked

    tekrar = motor._runtime.pop_retained_snapshot(SCOPE_EXTERNAL, 7, 10)
    assert not tekrar.valid


def test_kilitsiz_slot_guncellemesi_saklama_yapmaz():
    """Lock yokken normal REPLACE/REJECT akışı saklama üretmemeli (davranış değişmez)."""
    motor = _kilitli_aday_motoru()
    # Kilitli break candidate'i KALDIR: locks_candidate False dönmeli.
    motor._runtime.external.candidate = BreakCandidate()
    slot = _aday_snapshot()
    incoming = _aday_snapshot(identity=99, source_bar=12, price=95.0)

    motor._candidate_update(slot, incoming, locked_by_break=False)

    assert not motor._runtime.external.retained_locked


def test_gecersiz_snapshot_saklanmaz():
    motor = _kilitli_aday_motoru()
    motor._runtime.retain_locked_snapshot(SCOPE_EXTERNAL, SwingPoint())  # invalid
    motor._runtime.retain_locked_snapshot(SCOPE_EXTERNAL, _aday_snapshot(identity=0))
    assert not motor._runtime.external.retained_locked


# ---------------------------------------------------------------------------
# Katman 2 — gerçek arşiv regresyonu (bug'ı üreten seri)
# ---------------------------------------------------------------------------

_AEFES_1H = REPO_KOKU / "backfill_data" / "AEFES_1h.csv.gz"


@pytest.mark.skipif(not _AEFES_1H.exists(), reason="backfill_data/ arşiv yok; gerçek veri testi atlanır")
def test_arsivde_kilitli_referans_ms_domaini_cokurtmez():
    """AEFES/1h (eski 35 hatalı seriden) runner yolunda MS domaini hatasız bitmeli.

    Düzeltme ÖNCESİ: ValueError: confirmed break references must still be active
    → runner._execute_domain yutar → MS domaini sessiz boş.
    """
    from domain_engines.runner import run_domain_engines
    from research.arsiv import tf_frame

    frame = tf_frame("AEFES", "1h")
    cikti = run_domain_engines("AEFES", "1h", frame, profile="Dengeli")
    ms = cikti["market_structure"]

    assert ms.error is None, f"MS domaini düştü: {ms.error}"
    assert not ms.skipped


@pytest.mark.skipif(not _AEFES_1H.exists(), reason="backfill_data/ arşiv yok; gerçek veri testi atlanır")
def test_replay_sonunda_bekleyen_aday_disinda_sakli_kilit_kalmaz():
    """Fork'ta saklanan entry'ler aday çözülürken temizlenir (sızıntı invariantı)."""
    from domain_engines.adapter import to_domain_frame
    from research.arsiv import tf_frame

    frame = to_domain_frame(tf_frame("AEFES", "1h"))
    motor = MarketStructureEngine(config=MarketStructureConfig(profile="Dengeli"))
    motor.replay(frame)

    for ad_scope in ("EXTERNAL", "INTERNAL"):
        bekleyen = motor._runtime.scope(ad_scope).candidate.valid
        sakli = motor._runtime.scope(ad_scope).retained_locked
        if not bekleyen:
            assert not sakli, (
                f"{ad_scope} scope'ta bekleyen aday yok ama {len(sakli)} saklı kilit entry'si kaldı: "
                f"{sorted(sakli)}"
            )
