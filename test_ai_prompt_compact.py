"""Kompakt özet: sınır, nedensellik ve açık seçim sözleşmesi."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from ai_prompt import build_from_local_cache, render_compact_prompt
from ai_prompt.compact import (_compose, _drawn_context, _event_selection, _focus_indices,
                               _replay, _time)

ROOT = Path(__file__).resolve().parent
CUT = "2026-09-25T18:30:00+03:00"


@pytest.fixture(scope="module")
def bimas():
    return build_from_local_cache("BIMAS", as_of=CUT, research_mode="retrospective")


def _event(day, kind, direction):
    return {"bar_open": f"2026-09-{day:02d}T09:30:00+03:00", "type": kind,
            "direction": direction, "level": float(day)}


def test_recent_events_preserve_latest_bos_choch_each_direction():
    events = [_event(1, "BOS", "aşağı"), _event(2, "CHoCH", "aşağı"),
              _event(3, "BOS", "yukarı"), _event(4, "BOS", "yukarı"),
              _event(5, "CHoCH", "yukarı"), _event(6, "BOS", "yukarı"),
              _event(7, "BOS", "yukarı")]
    kept, omitted = _event_selection(list(reversed(events)))
    assert [x['bar_open'][8:10] for x in kept] == ['01', '02', '05', '06', '07']
    assert omitted == 2
    assert _event_selection([*events, {**events[0], "bar_open": None}])[1] == 0
    unknown = {**events[0], "direction": "bilinmiyor"}
    assert unknown in _event_selection([*events, unknown])[0]


def test_compact_bimas_latest_structure_and_selected_omissions_are_explicit(bimas):
    packet = deepcopy(bimas)
    text = render_compact_prompt(packet)
    assert packet == bimas  # renderer must not mutate packet/graphs
    assert len(text) <= 4500
    assert all(tf + " GRAFİK" in text for tf in ("1H", "2H", "4H", "1D"))
    h4 = text.split("4H GRAFİK", 1)[1].split("1D GRAFİK", 1)[0]
    assert "09.09 13:30 BOS ↑422,75" in h4
    assert "09.09 17:30 BOS ↑421,50" in h4
    assert "16.09 13:30 CHoCH ↓411,75" in h4
    assert "10.08 09:30 BOS" not in h4 and "2 diğer grafik olayı özet dışı" in h4
    assert "410,75–423,50" in h4 and "432,00–437,50" in h4
    assert "son kapanış orijinal bant üstünde" in text
    assert "sonraki kapanmış mum yok" in text and "devam ediyor olabilir" in text
    assert "kesit sonrası" in text.lower()
    assert "OB" in text and "Sembole özel olasılık değil" in text


def test_fail_closed_if_important_data_cannot_fit(bimas):
    with pytest.raises(ValueError, match="sessizce kesilmedi"):
        render_compact_prompt(bimas, target=100, maximum=100)
    with pytest.raises(ValueError, match="Sınırlar"):
        render_compact_prompt(bimas, target=4001, maximum=4000)
    with pytest.raises(ValueError, match="Sınırlar"):
        render_compact_prompt(bimas, target=4000, maximum=5000)


def test_replay_focus_keeps_nearest_in_each_direction_and_family():
    zones = [
        {"family": "OB", "direction": "pozitif", "lower": 90, "upper": 99, "replay_status": "ok"},
        {"family": "OB", "direction": "negatif", "lower": 109, "upper": 112, "replay_status": "ok"},
        {"family": "FVG", "direction": "negatif", "lower": 101, "upper": 102, "replay_status": "ok"},
        {"family": "OB", "direction": "pozitif", "lower": 50, "upper": 60, "replay_status": "ok"},
    ]
    assert _focus_indices(zones, 100) == {0, 1, 2}
    assert _focus_indices(zones, None) == {0, 1, 2, 3}


def test_omitted_replay_closes_and_historical_volume_are_reported(bimas):
    packet = deepcopy(bimas)
    full = _compose(packet, stage=0)
    reduced = _compose(packet, stage=5)
    assert "Önceki 1 ayrıntı yok" in reduced
    assert "diğer grafik rozeti özette yok" in reduced
    assert "son kapanış orijinal bant üstünde" in reduced
    assert "0 grup" in reduced
    assert "2: 25.09 13:30=422,00, 17:30=426,25" in reduced
    assert len(reduced) < len(full)


def test_zone_edges_and_unknown_do_not_invent_relative_position(bimas):
    row = deepcopy(bimas['timeframes']['4h'])
    row['replay']['zones'] = [row['replay']['zones'][0]]
    row['last_close'] = 423.5
    assert 'orijinal bant içinde/sınırında' in '\n'.join(_replay('4h', row, 2026, False))
    row['last_close'] = None
    assert 'son kapanış orijinal bant' not in '\n'.join(_replay('4h', row, 2026, False))


def test_strict_never_includes_future_research(bimas):
    packet = deepcopy(bimas)
    packet['research_mode'] = 'strict'
    for study in packet['research']:
        study['included'] = False
    text = render_compact_prompt(packet)
    assert '131.901' not in text
    assert 'kullanılabilirliği doğrulanmadı' in text


def test_badge_invalid_data_is_not_silently_dropped(bimas):
    row = deepcopy(bimas['timeframes']['1h'])
    row['chart_volume_badges'][0]['bar_open'] = None
    text = '\n'.join(_drawn_context('1h', row, 2026, compact_volume=2))
    assert 'bilinmiyor' in text
    assert 'diğer grafik rozeti özette yok' not in text


def test_timestamp_year_and_daily_fvg_context(bimas):
    assert _time('2025-12-31T17:30:00+03:00', 2026) == '31.12.2025 17:30'
    assert _time('2026-01-02T09:30:00+03:00', 2026) == '02.01 09:30'
    assert _time('2026-01-02T09:30:00', 2026) == 'bilinmiyor'
    row = deepcopy(bimas['timeframes']['4h'])
    zone = row['replay']['zones'][0]
    zone.update(family='FVG', width_atr_birth=0.7, width_atr_bucket='0.5-1')
    row['replay']['zones'] = [zone]
    daily = '\n'.join(_replay('1d', row, 2026, False))
    assert 'Wilder ATR(14)' in daily and 'grup alt sınırı dahil, üst sınırı hariç' in daily
    assert 'doğum yükseklik/ATR' in daily
    assert 'doğum yükseklik/ATR' not in '\n'.join(_replay('4h', row, 2026, False))


def test_cli_compact_default_and_full_opt_out(tmp_path):
    base = [sys.executable, 'scripts/diagnostics/ai_prompt_sample.py', 'BIMAS', '--as-of', CUT,
            '--main-tf', '4h', '--research-mode', 'retrospective']
    short = subprocess.run(base, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert short.returncode == 0 and len(short.stdout) <= 4500
    assert '2 diğer grafik olayı özet dışı' in short.stdout
    assert 'bilgi kapanışta bilinir' in short.stdout
    full = subprocess.run(base + ['--format', 'full'], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert full.returncode == 0 and len(full.stdout) > len(short.stdout)
    assert '10.08.26 09:30 BOS' in full.stdout


def test_research_manifest_change_never_uses_stale_compact_finding(bimas):
    from ai_prompt.compact import _research
    packet = deepcopy(bimas)
    item = next(r for r in packet['research'] if r['id'].startswith('ob-'))
    item['text'] = 'Değişmiş araştırma bulgusu; yalnız örnek.'
    text = '\n'.join(_research(packet, packet['timeframes']['4h'], '4h'))
    assert item['text'] in text and '131.901' not in text


def test_unknown_remaining_band_never_becomes_same_as_original(bimas):
    row = deepcopy(bimas['timeframes']['4h'])
    zone = row['replay']['zones'][0]
    zone.update(lower=None, upper=None, remaining_lower=None, remaining_upper=None)
    row['replay']['zones'] = [zone]
    text = '\n'.join(_replay('4h', row, 2026, False))
    assert 'kalan bilinmiyor–bilinmiyor' in text and 'kalan aynı' not in text


def test_target_does_not_discard_data_when_full_details_fit_cap(bimas):
    # A 4k target is not permission to omit important replay/research merely
    # to reduce an already compliant 4.0–4.5k prompt by a few characters.
    full = _compose(bimas, stage=0)
    assert 4000 < len(full) <= 4500
    assert render_compact_prompt(bimas, history_bars=None) == full
    assert 'Araştırma özeti dışında' not in full
    assert 'diğer grafik rozeti özette yok' not in full


def test_history_event_window_requires_diverse_recent_and_preserves_latest_choch():
    from ai_prompt.compact import _event_selection
    old_choch = {**_event(1, 'CHoCH', 'aşağı'), 'age_bars': 100}
    old_bos = {**_event(2, 'BOS', 'aşağı'), 'age_bars': 90}
    a = {**_event(3, 'BOS', 'yukarı'), 'age_bars': 59}
    b = {**_event(4, 'BOS', 'aşağı'), 'age_bars': 0}
    chosen, omitted = _event_selection([old_choch, old_bos, a, b], history_bars=60)
    assert chosen == [old_choch, a, b] and omitted == 1
    # A single recent event or two recent same-type/direction events are not
    # enough to hide the only older opposing context.
    b_same = {**b, 'direction': 'yukarı'}
    chosen, omitted = _event_selection([old_choch, old_bos, a, b_same], history_bars=60)
    assert old_bos in chosen and old_choch in chosen and omitted == 0
    unknown = {**old_bos, 'age_bars': None, 'bar_open': '2026-09-05T09:30:00+03:00'}
    chosen, _ = _event_selection([old_choch, old_bos, a, b, unknown], history_bars=60)
    assert unknown in chosen


def test_history_volume_keeps_latest_opposite_and_marks_older(bimas):
    row = deepcopy(bimas['timeframes']['1h'])
    row['chart_volume_badges'] = [
        {'bar_open': '2026-09-01T09:30:00+03:00', 'age_bars': 90, 'direction': 'artis', 'value': '3,1'},
        {'bar_open': '2026-09-02T09:30:00+03:00', 'age_bars': 89, 'direction': 'dusus', 'value': '0,3'},
        {'bar_open': '2026-09-03T09:30:00+03:00', 'age_bars': 10, 'direction': 'artis', 'value': '2,2'},
        {'bar_open': '2026-09-04T09:30:00+03:00', 'age_bars': 0, 'direction': 'artis', 'value': '2,1'},
    ]
    text = '\n'.join(_drawn_context('1h', row, 2026, history_bars=60))
    assert '01.09 09:30 A×3,1' not in text
    assert '02.09 09:30 K×0,3 [E]' in text
    assert '03.09 09:30 A×2,2' in text and '04.09 09:30 A×2,1' in text
    assert '1 diğer grafik rozeti özette yok' in text
    row['chart_volume_badges'][0]['age_bars'] = None
    assert '01.09 09:30 A×3,1' in '\n'.join(_drawn_context('1h', row, 2026, history_bars=60))


def test_history_replay_omits_old_details_only_after_two_same_family_direction(bimas):
    row = deepcopy(bimas['timeframes']['4h'])
    zone = row['replay']['zones'][0]
    # Two recent contacts in a zone cover its own older details, but cannot
    # erase another zone's history or unknown-age records.
    zone['recent_episodes'][0]['end_age_bars'] = 2
    zone['recent_episodes'][1]['end_age_bars'] = 1
    old_ep = deepcopy(zone['recent_episodes'][0])
    old_ep['end_age_bars'] = 60
    zone['recent_episodes'].insert(0, old_ep)
    older = deepcopy(zone)
    older['lower'], older['upper'] = 400.0, 405.0
    older['recent_episodes'] = [deepcopy(zone['recent_episodes'][0])]
    older['recent_episodes'][0]['end_age_bars'] = 60
    negative = deepcopy(older)
    negative['direction'] = 'negatif'
    unknown = deepcopy(older)
    unknown['lower'], unknown['upper'] = 390.0, 395.0
    unknown['recent_episodes'][0]['end_age_bars'] = None
    row['replay']['zones'] = [zone, older, negative, unknown]
    original = deepcopy(row)
    text = '\n'.join(_replay('4h', row, 2026, False, history_bars=60))
    assert 'sayım tüm pencere' in text
    assert '1 eski temasın kapanış ayrıntısı özet dışında' in text
    assert '+OB 400,00–405,00' in text and '−OB 400,00–405,00' in text
    assert '1 [E]:' in text  # the older negative OB is still needed for its direction
    assert row == original


def test_history_window_validation_and_default(bimas):
    assert render_compact_prompt(bimas) == render_compact_prompt(bimas, history_bars=60)
    assert 'son 60 kapanmış mum' not in render_compact_prompt(bimas, history_bars=None)
    for value in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match='Geçmiş penceresi'):
            render_compact_prompt(bimas, history_bars=value)
    text = render_compact_prompt(bimas, history_bars=60)
    assert 'son 60 kapanmış mum' in text and len(text) <= 4500


def test_history_boundaries_and_opposing_kind_are_not_mistaken_for_redundancy():
    old_up = {**_event(1, 'BOS', 'yukarı'), 'age_bars': 60}
    old_down = {**_event(2, 'BOS', 'aşağı'), 'age_bars': 61}
    newer_up = {**_event(3, 'BOS', 'yukarı'), 'age_bars': 59}
    newer_transition = {**_event(4, 'CHoCH', 'yukarı'), 'age_bars': 0}
    events = [newer_transition, old_down, newer_up, old_up]
    chosen, _ = _event_selection(events, history_bars=60)
    assert old_up not in chosen and old_down in chosen
    assert chosen == [old_down, newer_up, newer_transition]
    unknown = {**_event(5, 'BOS', 'yukarı'), 'age_bars': None}
    assert unknown in _event_selection(events + [unknown], history_bars=60)[0]
    unknown_time = {**old_up, 'bar_open': None}
    assert _event_selection(events + [unknown_time], history_bars=60)[1] == 0


@pytest.mark.parametrize('tf', ['1h', '2h', '4h', '1d'])
def test_history_age_labels_apply_to_each_tf_and_unknown_age_remains(tf, bimas):
    row = deepcopy(bimas['timeframes'][tf])
    row['chart_events'] = [{**_event(1, 'BOS', 'aşağı'), 'age_bars': 60},
                           {**_event(2, 'BOS', 'yukarı'), 'age_bars': None}]
    text = '\n'.join(_drawn_context(tf, row, 2026, history_bars=60))
    assert '01.09 09:30 BOS ↓1,00 [E]' in text
    assert '02.09 09:30 BOS ↑2,00' in text


def test_exact_cap_and_astral_unicode_are_fail_closed(monkeypatch):
    import ai_prompt.compact as compact
    # UTF-16-based clients count this emoji as two units, unlike Python len.
    exactly = '🧭' + 'a' * 4498
    assert len(exactly) == 4499 and compact._size(exactly) == 4500
    monkeypatch.setattr(compact, '_compose', lambda *args, **kwargs: exactly)
    assert compact.render_compact_prompt({}) == exactly
    over = '🧭' + 'a' * 4499
    assert len(over) == 4500 and compact._size(over) == 4501
    monkeypatch.setattr(compact, '_compose', lambda *args, **kwargs: over)
    with pytest.raises(ValueError, match='4501.*sessizce kesilmedi'):
        compact.render_compact_prompt({})


def test_compact_instructions_keep_interpretation_and_fixed_readable_headers():
    instruction = (ROOT / 'ai_prompt' / 'talimat_kisa.txt').read_text(encoding='utf-8')
    for text in ('karşı kanıt', 'görüşü değiştirecek koşul', 'Temasla sonraki kapanışı ayır',
                 'Formasyonun klasik eğilimini', 'gerçekleşmemiş kırılımı kesin sayma',
                 'Tek kapanış', '🧭 Mevcut durum', '🔎 Bağlam', '🕯️ Replay notu',
                 'yıldızsız', 'genel istatistik sembole özel olasılık değildir'):
        assert text in instruction
