from __future__ import annotations

from collections.abc import Callable

from .market_structure import SIDE_HIGH, SwingPoint
from .market_structure_runtime import MarketStructureRuntime as _BaseRuntime
from .market_structure_state import active_by_id


CommitProvisional = Callable[[SwingPoint, int, str, float], SwingPoint]


class MarketStructureRuntime(_BaseRuntime):
    """Runtime bridge for Pine's provisional target/origin commit step.

    Tur 2's finalize function intentionally accepts confirmed references only.
    Pine may let a gated live swing candidate become structural *because* the
    break confirms it. This bridge performs that commit immediately before the
    already-validated finalize path, without changing break/state math.
    """

    @staticmethod
    def _matching_candidate(
        high_candidate: SwingPoint,
        low_candidate: SwingPoint,
        identity: int,
        source_bar: int,
    ) -> SwingPoint:
        for candidate in (high_candidate, low_candidate):
            if (
                candidate.valid
                and candidate.identity == identity
                and candidate.source_bar == source_bar
            ):
                return candidate
        return SwingPoint()

    def _commit_missing_reference(
        self,
        *,
        swings: list[SwingPoint],
        candidate_snapshot: SwingPoint,
        scope: str,
        bar_index: int,
        origin_role: bool,
        commit_provisional: CommitProvisional | None,
    ) -> bool:
        if not candidate_snapshot.valid or commit_provisional is None:
            return False
        if not self._provisional_gate(candidate_snapshot, scope, bar_index, origin_role):
            return False
        evidence = "confirmed by structure break" if origin_role else "confirmed as broken structural target"
        quality_floor = 55.0 if origin_role else 52.0
        committed = commit_provisional(candidate_snapshot, bar_index, evidence, quality_floor)
        return committed.valid

    def process_scope(
        self,
        *,
        scope: str,
        swings: list[SwingPoint],
        high_candidate: SwingPoint,
        low_candidate: SwingPoint,
        bar_index: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        safe_atr: float,
        commit_provisional: CommitProvisional | None = None,
    ):
        try:
            return super().process_scope(
                scope=scope,
                swings=swings,
                high_candidate=high_candidate,
                low_candidate=low_candidate,
                bar_index=bar_index,
                open_=open_,
                high=high,
                low=low,
                close=close,
                safe_atr=safe_atr,
            )
        except ValueError as exc:
            if str(exc) != "confirmed break references must still be active":
                raise

            runtime = self.scope(scope)
            bc = runtime.candidate
            if not bc.valid:
                raise

            broken = active_by_id(swings, bc.broken_swing_identity)
            if not broken.valid:
                snapshot = self._matching_candidate(
                    high_candidate,
                    low_candidate,
                    bc.broken_swing_identity,
                    bc.broken_source_bar,
                )
                if not self._commit_missing_reference(
                    swings=swings,
                    candidate_snapshot=snapshot,
                    scope=scope,
                    bar_index=bc.candidate_bar,
                    origin_role=False,
                    commit_provisional=commit_provisional,
                ):
                    raise

            origin = active_by_id(swings, bc.origin_swing_identity)
            if not origin.valid:
                snapshot = self._matching_candidate(
                    high_candidate,
                    low_candidate,
                    bc.origin_swing_identity,
                    bc.origin_source_bar,
                )
                if not self._commit_missing_reference(
                    swings=swings,
                    candidate_snapshot=snapshot,
                    scope=scope,
                    bar_index=bc.candidate_bar,
                    origin_role=True,
                    commit_provisional=commit_provisional,
                ):
                    raise

            # Retry the same closed bar after provisional references have been
            # committed. The candidate remains frozen from the first attempt.
            return super().process_scope(
                scope=scope,
                swings=swings,
                high_candidate=high_candidate,
                low_candidate=low_candidate,
                bar_index=bar_index,
                open_=open_,
                high=high,
                low=low,
                close=close,
                safe_atr=safe_atr,
            )
