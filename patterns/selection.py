# --- SELECTION PRIORITY (ADAY SEÇİMİ VE DEVAMLILIK) ---
# Pine: Bölüm 13-16 (f_selection_score, f_continuity_score, f_candidate_preferred,
# f_replacement_margin, f_same_completed_structure, f_identity_compatible).
# Eski Python'da selection_score alanı vardı ama HİÇ hesaplanmıyordu (Teşhis A2) — artık birebir.

from typing import Optional

from .candidate import PatternCandidate, effective_raw_quality
from .constants import f_is_terminal
from .mathutil import f_clamp, f_line_price


def quality_priority_gap(profile: str) -> float:
    """Pine: f_quality_priority_gap — bu farkı aşan kalite farkı bağlamı ezer."""
    return {"Hassas": 5.0, "Seçici": 7.0}.get(profile, 6.0)


def replacement_margin(state_value: str) -> float:
    """Pine: f_replacement_margin — yalnız YAKIN kalitede selection farkına uygulanır."""
    if state_value == "KIRILIM_HAZIRLIGI":
        return 14.0
    if state_value == "SIKISMA_GUCLENIYOR":
        return 12.0
    if state_value == "OLGUNLASIYOR":
        return 10.0
    if state_value == "FORMASYON_TANIMLANDI":
        return 8.0
    return 6.0


def identity_compatible(current: PatternCandidate, incoming: PatternCandidate) -> bool:
    """Pine: f_identity_compatible."""
    same_family = (current.valid and incoming.valid and current.family != "Yok"
                   and current.family == incoming.family)
    direction_compatible = (current.classic_dir == 0 or incoming.classic_dir == 0
                            or current.classic_dir == incoming.classic_dir)
    return same_family and direction_compatible


def pivot_overlap_count(first: PatternCandidate, second: PatternCandidate) -> int:
    """Pine: f_pivot_overlap_count."""
    count = 0
    count += 1 if first.hb1 in (second.hb1, second.hb2) else 0
    count += 1 if first.hb2 in (second.hb1, second.hb2) else 0
    count += 1 if first.lb1 in (second.lb1, second.lb2) else 0
    count += 1 if first.lb2 in (second.lb1, second.lb2) else 0
    return count


def overlap_ratio(upper_a: float, lower_a: float, upper_b: float, lower_b: float, mintick: float) -> float:
    """Pine: f_overlap_ratio — sınır aralıklarının kesişim/birim oranı."""
    intersection = max(0.0, min(upper_a, upper_b) - max(lower_a, lower_b))
    union_value = max(upper_a, upper_b) - min(lower_a, lower_b)
    if union_value > mintick:
        return f_clamp(intersection / union_value, 0.0, 1.0)
    return 0.0


def continuity_score(engine, current: PatternCandidate, incoming: PatternCandidate) -> float:
    """Pine: f_continuity_score — aktif formasyonla yapısal uyum (0-100)."""
    score = 0.0
    if not identity_compatible(current, incoming):
        return score
    score += 25.0 if current.pattern_type == incoming.pattern_type else 0.0
    start_distance = abs(current.start_bar - incoming.start_bar)
    if start_distance <= max(engine.min_touch_gap * 2, engine.pivot_len * 2):
        score += 15.0
    elif start_distance <= engine.min_age:
        score += 6.0
    score += pivot_overlap_count(current, incoming) / 4.0 * 25.0
    b = engine.bar_index
    current_upper = f_line_price(current.hb1, current.hp1, current.hb2, current.hp2, b)
    current_lower = f_line_price(current.lb1, current.lp1, current.lb2, current.lp2, b)
    incoming_upper = f_line_price(incoming.hb1, incoming.hp1, incoming.hb2, incoming.hp2, b)
    incoming_lower = f_line_price(incoming.lb1, incoming.lp1, incoming.lb2, incoming.lp2, b)
    continuity_atr = engine.pair_geometry_atr(current, incoming)
    boundary_distance = (abs(current_upper - incoming_upper) + abs(current_lower - incoming_lower)) / max(2.0 * continuity_atr, engine.mintick)
    score += f_clamp(1.0 - boundary_distance, 0.0, 1.0) * 20.0
    score += overlap_ratio(current_upper, current_lower, incoming_upper, incoming_lower, engine.mintick) * 15.0
    return score


def selection_score(engine, candidate: PatternCandidate) -> float:
    """Pine: f_selection_score — recency + proximity + continuity; kalite burada tekrar puanlanmaz."""
    recency_priority = 0.0
    if candidate.end_bar is not None:
        recency_priority = f_clamp(16.0 - float(engine.bar_index - candidate.end_bar) * 0.65, -10.0, 16.0)
    upper_distance = abs(engine.close[engine.bar_index] - candidate.upper_now) / max(engine.safe_atr, engine.mintick)
    lower_distance = abs(engine.close[engine.bar_index] - candidate.lower_now) / max(engine.safe_atr, engine.mintick)
    proximity_priority = f_clamp(10.0 - min(upper_distance, lower_distance) * 3.5, -8.0, 10.0)
    same_active_identity = (engine.active.valid and candidate.identity != 0
                            and candidate.identity == engine.active.identity)
    if same_active_identity:
        continuity_value = 100.0
    elif engine.active.valid and not f_is_terminal(engine.pattern_state):
        continuity_value = continuity_score(engine, engine.active, candidate)
    else:
        continuity_value = 0.0
    continuity_priority = continuity_value * 0.22
    partial_overlap_penalty = (8.0 if (engine.active.valid and not same_active_identity
                                       and 20.0 <= continuity_value < 60.0) else 0.0)
    return recency_priority + proximity_priority + continuity_priority - partial_overlap_penalty


def candidate_preferred(engine, incoming: PatternCandidate, current_best: PatternCandidate) -> bool:
    """Pine: f_candidate_preferred — kalite farkı eşiği aşarsa kalite, değilse selection belirler."""
    preferred = not current_best.valid
    if incoming.valid and current_best.valid:
        incoming_quality = effective_raw_quality(incoming)
        current_quality = effective_raw_quality(current_best)
        gap = quality_priority_gap(engine.profile)
        quality_difference = incoming_quality - current_quality
        if abs(quality_difference) >= gap:
            preferred = quality_difference > 0.0
        elif incoming.selection_score != current_best.selection_score:
            preferred = incoming.selection_score > current_best.selection_score
        else:
            preferred = incoming_quality > current_quality
    return preferred


def same_completed_structure(engine, candidate: PatternCandidate) -> bool:
    """Pine: f_same_completed_structure — az önce tamamlanan yapıyı yeniden seçme koruması."""
    same_type = candidate.pattern_type == engine.completed_type
    near_start = (engine.completed_start_bar is not None and candidate.start_bar is not None
                  and abs(candidate.start_bar - engine.completed_start_bar) <= max(engine.min_touch_gap * 2, engine.pivot_len * 2))
    near_end = (engine.completed_end_bar is not None and candidate.end_bar is not None
                and abs(candidate.end_bar - engine.completed_end_bar) <= max(engine.min_touch_gap * 3, engine.min_age))
    pivot_overlap = 0
    pivot_overlap += 1 if candidate.hb1 in (engine.completed_hb1, engine.completed_hb2) else 0
    pivot_overlap += 1 if candidate.hb2 in (engine.completed_hb1, engine.completed_hb2) else 0
    pivot_overlap += 1 if candidate.lb1 in (engine.completed_lb1, engine.completed_lb2) else 0
    pivot_overlap += 1 if candidate.lb2 in (engine.completed_lb1, engine.completed_lb2) else 0
    candidate_upper_at_end = f_line_price(candidate.hb1, candidate.hp1, candidate.hb2, candidate.hp2, candidate.end_bar)
    candidate_lower_at_end = f_line_price(candidate.lb1, candidate.lp1, candidate.lb2, candidate.lp2, candidate.end_bar)
    candidate_geometry_atr = max(candidate.geometry_atr if candidate.geometry_atr is not None else engine.safe_atr,
                                 engine.mintick * 10.0)
    completed_reference_atr = max(engine.completed_geometry_atr if engine.completed_geometry_atr is not None
                                  else candidate_geometry_atr, engine.mintick * 10.0)
    completed_pair_atr = max((candidate_geometry_atr + completed_reference_atr) * 0.5, engine.mintick * 10.0)
    boundary_distance = 0.0
    similar_boundaries = False
    if engine.completed_upper_at_end is not None and engine.completed_lower_at_end is not None:
        boundary_distance = (abs(candidate_upper_at_end - engine.completed_upper_at_end)
                             + abs(candidate_lower_at_end - engine.completed_lower_at_end)) / max(2.0 * completed_pair_atr, engine.mintick)
        similar_boundaries = boundary_distance <= 0.85
    return same_type and near_start and near_end and pivot_overlap >= 3 and similar_boundaries
