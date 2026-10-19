"""Trust, focus/context, mobile and explainability regressions (no live I/O)."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import chart_experience as E
import chart_report
import grafik
import grafik_uret
from test_grafik_iskelet import _goruntu

IST = timezone(timedelta(hours=3))


def dt(day, hour=19, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


def fake_calendar(monkeypatch, unknown=False):
    import bist_calendar as C
    def session(day):
        status = C.SessionStatus.UNKNOWN if unknown else (
            C.SessionStatus.CLOSED if day.weekday() >= 5 else C.SessionStatus.TRADING)
        from datetime import time
        return C.BistSession(day, status, time(10), time(18))
    monkeypatch.setattr(C, 'bist_session_for', session)


@pytest.mark.parametrize('now,last,state', [
    (dt(16), dt(16, 17, 30), 'CURRENT'),
    (dt(17), dt(16, 17, 30), 'CURRENT'),  # weekend is NOT stale
    (dt(19, 10, 0), dt(16, 17, 30), 'CURRENT'),  # no new bar closed yet
    (dt(19, 10, 36), dt(16, 17, 30), 'STALE'),
    (dt(16), dt(15, 17, 30), 'STALE'),
    (dt(16), dt(19, 17, 30), 'FUTURE'),
])
def test_session_aware_freshness(monkeypatch, now, last, state):
    fake_calendar(monkeypatch)
    payload = E.trust_payload({'tf': '1h', 'son_bar_ts': last.isoformat()}, {},
                              now=now, anchor=dt(1, 9, 30))
    assert payload['durum'] == state


def test_unknown_calendar_never_claims_current(monkeypatch):
    fake_calendar(monkeypatch, unknown=True)
    result = E.trust_payload({'tf': '4h', 'son_bar_ts': dt(16, 17, 30)}, {},
                             now=dt(16), anchor=dt(1, 9, 30))
    assert result['durum'] == 'UNKNOWN'


def test_explicit_historical_and_source_depth():
    result = E.trust_payload({'tf': '1d', 'son_bar_ts': dt(1, 0), 'bar_sayisi': 40}, {},
                             now=dt(16), historical=True, source='resample(1d) ← /secret/path')
    assert result['durum'] == 'HISTORICAL'
    assert result['kaynak'] == 'saatlikten türetildi' and result['mum_sayisi'] == 40
    assert '/secret' not in str(result)
    text = E.date_text(dt(1, 0), daily=True)
    assert '2026' in text and 'TSİ' in text and '00:00' not in text


def test_real_holiday_and_half_day_use_existing_calendar():
    # Oct 29 Republic Day closed; Oct 28 has an explicit 13:00 cutoff.
    last = E.expected_bar(dt(29), '1h', dt(1, 9, 30))
    assert last.date().day == 28 and last.hour == 12 and last.minute == 30
    daily = E.expected_bar(dt(28, 13, 6), '1d', dt(1, 0))
    assert daily.date().day == 28


def test_timezone_normalization_matches_same_instant(monkeypatch):
    fake_calendar(monkeypatch)
    now = dt(16)
    assert E.expected_bar(now, '2h', dt(1, 9, 30)) == E.expected_bar(
        now.astimezone(timezone.utc), '2h', dt(1, 9, 30))


def test_readiness_separates_warmup_skip_error_and_ready():
    results = {
        'market_structure': NS(result=NS(state='UP')),
        'order_block': NS(error='secret provider exception'),
        'fvg': NS(skipped=True, reason='2h FVG requires explicit offline/replay opt-in'),
        'volume_participation': NS(details={'latest_metrics': NS(data_ready=False,
                                      capital_usable=False, volume_usable=True)})}
    before = deepcopy(results)
    data = E.readiness(results)
    assert [data[n]['durum'] for n in E.DOMAIN_LABELS] == ['READY', 'ERROR', 'SKIPPED', 'WARMUP']
    assert 'secret' not in str(data)
    assert vars(results['market_structure']) == vars(before['market_structure'])


@pytest.mark.parametrize('state,label', [('REACTION', 'tepki kaydı'), ('FULL_FILL', 'tam doldu'),
                                         ('INVALID', 'geçersiz'), ('CANDIDATE', 'aday'), ('ACTIVE', 'aktif')])
def test_lifecycle_is_explicit_in_right_chip(state, label):
    z = {'tip': 'fvg', 'yon': -1, 'durum': state, 'alt': 129.5, 'ust': 130.2}
    chip = grafik._zone_sag_adaylari({'cizilen': [z]}, 50)[0]
    assert label in chip['metin'] and '129,50–130,20' in chip['metin']
    assert 'dolum' not in chip['metin']


def snapshot():
    return {'sembol': 'TEST', 'tf': '1h', 'tf_kisa': '1s', 'sol': 0, 'sag': 3,
            'son_kapanis': 100., 'zamanlar': [dt(16, h, 30) for h in [10, 11, 12]],
            'dusuk': [99., 99., 99.], 'yuksek': [101., 101., 101.],
            'zone': {'atr': 1., 'kapak': {'ust': 3, 'alt': 3}, 'cizilen': [], 'tum': [
                {'tip': 'ob', 'yon': 1, 'alt': 99., 'ust': 101., 'kaynak': 1,
                 'kayit_kaynagi': 'active_records'},
                {'tip': 'ob', 'yon': 1, 'alt': 80., 'ust': 81., 'kaynak': 0,
                 'kayit_kaynagi': 'active_records'},
                {'tip': 'fvg', 'yon': -1, 'alt': 100., 'ust': 102.,
                 'durum': 'INVALID', 'tamamlandi': True}]},
            'olay': {'seviyeler': [{'fiyat': 60, 'etiket': 'PL'}], 'olaylar': []}}


def test_focus_context_and_inside_distance_without_mutation():
    s = snapshot(); before = deepcopy(s)
    focus = E.prepare_view(s)
    assert len(focus['zone']['cizilen']) == 1
    inside = focus['zone']['cizilen'][0]
    assert inside['konum'] == 'içinde' and inside['sinir_mesafe_atr'] == 0
    assert focus['gorunum']['gizlenen'] == 2 and focus['gorunum']['uzak_seviye'] == 1
    assert len(E.prepare_view(s, 'baglam')['zone']['cizilen']) == 3
    assert s == before
    detail = E.detail_payload(s, focus)
    assert len(detail['bolgeler']) == 3 and detail['bolgeler'][0]['gorunur']
    assert {z['gorunum_nedeni'] for z in detail['bolgeler']} == {'gösteriliyor', 'uzak bölge', 'geçmiş durum'}


def test_interval_and_center_distance_are_distinct():
    result = E.proximity({'alt': 69.8, 'ust': 71.05}, 70.95, 1.)
    assert result['sinir_mesafe_atr'] == 0 and result['merkez_mesafe_atr'] > 0
    assert result['konum'] == 'içinde'
    assert E.proximity({'alt': 69.8, 'ust': 71.05}, 72, 1)['sinir_mesafe_atr'] == pytest.approx(.95)


def test_no_atr_is_not_fabricated():
    s = snapshot(); s['zone']['atr'] = None
    view = E.prepare_view(s)
    assert len(view['zone']['cizilen']) == 1
    assert view['zone']['cizilen'][0]['sinir_mesafe_atr'] is None


def test_all_details_exclude_internal_and_engulf_even_legacy():
    s = snapshot()
    s['zone']['tum'].append({'tip': 'eng', 'alt': 90., 'ust': 100.})
    s['olay']['zaman_cizelgesi'] = [
        {'scope': 'INTERNAL', 'tur': 'HIDDEN', 'kaynak_bar': 2},
        {'scope': 'EXTERNAL', 'tur': 'BOS', 'kaynak_bar': 1, 'yas': 2}]
    detail = E.detail_payload(s, E.prepare_view(s))
    assert len(detail['bolgeler']) == 3 and len(detail['olaylar']) == 1
    assert 'HIDDEN' not in str(detail)


def test_product_view_no_repeated_inside_labels_and_metadata_is_complete(tmp_path):
    s = _goruntu(); s['zone'] = snapshot()['zone']; s.pop('guven', None); before = deepcopy(s)
    path, meta = grafik.ciz(s, '1h', {'cikti': str(tmp_path / 'chart.png'), 'gorunum': 'baglam'})
    assert path and meta['zone']['etiket_ic'] == 0
    assert meta['zone']['etiket_serit'] == meta['zone']['cizilen']
    assert meta['grafik_politikasi'] == E.POLICY and 'ayrinti' in meta
    assert any('Dolum yüzdesi başarı olasılığı değildir' in line for line in meta['guven_satirlari'])
    assert any('güncellik bilinmiyor' in line for line in meta['guven_satirlari'])
    assert s == before


def test_mobile_and_desktop_scopes_do_not_leak(tmp_path):
    s = _goruntu()
    _, mobile = grafik.ciz(s, '1h', {'cikti': str(tmp_path / 'mobile.png'), 'mobil': True})
    _, desktop = grafik.ciz(s, '1h', {'cikti': str(tmp_path / 'desktop.png')})
    assert (mobile['kare']['genislik'], mobile['kare']['yukseklik']) == (780, 1100)
    assert mobile['mod']['mobil'] and mobile['mod']['yazi_olcek'] >= 1.35
    assert desktop['kare']['genislik'] == 1080 and not desktop['mod']['mobil']
    assert grafik._MOD.yazi_olcek == 1.0 and not grafik._MOD.mobil


def test_sade_details_honestly_record_hidden_zones(tmp_path):
    s = _goruntu(); s['zone'] = snapshot()['zone']
    _, meta = grafik.ciz(s, '1h', {'cikti': str(tmp_path / 'simple.png'), 'sade': True})
    assert meta['gorunum']['gosterilen'] == 0
    assert not any(z['gorunur'] for z in meta['ayrinti']['bolgeler'])
    assert meta['ayrinti']['gorunum']['mod'] == 'sade'


def test_static_detail_report_escapes_untrusted_content():
    detail = E.detail_payload(snapshot(), E.prepare_view(snapshot()))
    detail['sembol'] = '<script>alert(1)</script>'
    detail['bolgeler'][0]['gorunum_nedeni'] = '<img src=x onerror=alert(2)>'
    doc = chart_report.render_report({'ayrinti': detail}, {})
    assert '<script>alert(1)' not in doc and '<img src=x' not in doc
    assert '&lt;script&gt;' in doc and '&lt;img src=x' in doc
    assert 'zone-state' in doc and 'Dış olay zaman çizelgesi' in doc


def test_official_pipeline_export_reuses_snapshot_no_extra_engine_calls(tmp_path, monkeypatch):
    import domain_engines.runner as R
    calls = []
    monkeypatch.setattr(R, 'run_domain_engines', lambda *a, **k: calls.append(a[:2]) or {})
    result = grafik_uret.kare_uret('TEST', '4h', demo=True, zone=True,
        tarihsel=True, cikti=str(tmp_path / 'out.png'), ayrinti_yol=str(tmp_path / 'out.html'))
    assert result['yol'] and result['ayrinti_yol'] and len(calls) == 1
    assert result['meta']['guven']['durum'] == 'HISTORICAL'
    doc = Path(result['ayrinti_yol']).read_text()
    assert 'data:image/png;base64,' in doc and 'Mobil' in doc and 'Bağlam' in doc
    assert 'http://' not in doc and 'https://' not in doc
    json.dumps(result['meta']['ayrinti'], allow_nan=False)


def test_cli_accepts_all_three_features(tmp_path):
    png, report = tmp_path / 'cli.png', tmp_path / 'cli.html'
    code = grafik_uret.main(['--hisse', 'TEST', '--tf', '1d', '--demo', '--zone',
        '--gorunum', 'baglam', '--mobil', '--tarihsel', '--cikti', str(png), '--ayrinti', str(report)])
    assert code == 0 and png.exists() and report.exists()


def test_active_fvg_keeps_visibility_slot():
    s = snapshot()
    s['zone']['kapak'] = {'ust': 2, 'alt': 2}
    s['zone']['tum'] = [
        {'tip': 'ob', 'yon': -1, 'alt': 100.5, 'ust': 101., 'kaynak': 1},
        {'tip': 'ob', 'yon': -1, 'alt': 101., 'ust': 101.5, 'kaynak': 2},
        {'tip': 'fvg', 'yon': -1, 'alt': 102., 'ust': 102.5, 'kaynak': 3, 'durum': 'ACTIVE'}]
    view = E.prepare_view(s)
    assert len(view['zone']['cizilen']) == 2
    assert any(z['tip'] == 'fvg' for z in view['zone']['cizilen'])


def test_hidden_structural_level_is_preserved_in_detail():
    s = snapshot(); view = E.prepare_view(s)
    detail = E.detail_payload(s, view)
    assert detail['seviyeler'][0]['fiyat'] == 60
    assert detail['seviyeler'][0]['gorunur'] is False
    assert 'Dış yapı seviyeleri' in chart_report.render_report({'ayrinti': detail}, {})


def test_timeline_captures_source_date_age_and_validity():
    from test_grafik_yapi import _ms, _olay
    from test_grafik_iskelet import _cerceve, ZAMAN
    native = _ms(olaylar=[_olay(10, 50., tur='EVENT_BOS')])
    frame = _cerceve(40)
    s = grafik.anlik_goruntu(None, '1h', frame, sonuclar=native, simdi=ZAMAN)
    detail = E.detail_payload(s, E.prepare_view(s))
    assert detail['olaylar'][0]['zaman'] == frame['zaman'][10].isoformat()
    assert detail['olaylar'][0]['yas'] == 3
    assert detail['olaylar'][0]['teyit'] == 'CONFIRMED'
    assert detail['olaylar'][0]['gecerlilik'] == 'VALID'


def test_optional_technical_legend_does_not_cover_trust_footer(tmp_path):
    from test_grafik_faz_kullanici import _kare_ciz
    fig, _meta, _path = _kare_ciz(_goruntu(), '1h', tmp_path, kare_lejant=True)
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    FigureCanvasAgg(fig)
    fig.canvas.draw(); renderer = fig.canvas.get_renderer()
    footer = [t.get_window_extent(renderer) for t in fig.texts if t.get_gid() == 'grafik-guven']
    others = [t.get_window_extent(renderer) for t in fig.texts if t.get_gid() != 'grafik-guven']
    assert footer and all(not f.overlaps(o) for f in footer for o in others)
    assert all(f.y0 >= 0 for f in footer)


def test_old_prepared_delivery_policy_is_refreshed_without_text_resend(tmp_path, monkeypatch):
    from notification_delivery import DeliveryOutbox
    from test_notification_delivery import owner, alert
    events, renders = [], []
    monkeypatch.setenv("TELEGRAM_GRAFIK", "alarm")
    def render(*args):
        renders.append(args[1])
        target = tmp_path / "render.png"
        target.write_bytes(b"new chart bytes")
        return str(target), {"mum_sayisi": 10}
    monkeypatch.setattr(grafik, "kareyi_yaz", render)
    box = DeliveryOutbox(owner(events), tmp_path)
    row = {"data": alert(), "prepared": True, "text_sent": True,
           "graph_policy": "external-ranges-v2", "images": []}
    box.prepare(row)
    assert row["graph_policy"] == E.POLICY and row["text_sent"] is True
    assert renders == ["1h"] and not events
    box.prepare(row)
    assert renders == ["1h"]


def test_price_chip_order_is_preserved_around_fixed_last_price():
    from test_grafik_gorsel4 import _eksen
    fig, ax = _eksen(alt=255, ust=325)
    zones = {'cizilen': [
        {'tip': 'ob', 'yon': 1, 'alt': 282.5, 'ust': 294., 'durum': 'ACTIVE', 'doluluk': .41},
        {'tip': 'fvg', 'yon': -1, 'alt': 294., 'ust': 297.25, 'durum': 'ACTIVE'}]}
    chips = grafik._zone_sag_adaylari(zones, 60)
    chips += [{'kaynak': 'son', 'y': 290.5, 'metin': '290,50', 'renk': '#ffffff', 'sabit': True, 'oncelik': 9},
              {'kaynak': 'olay', 'y': 289.25, 'metin': 'kritik 289,25 · BOS', 'renk': '#ffffff', 'oncelik': 5}]
    result = grafik._sag_ciz(ax, fig, chips, 60, (255, 325))
    ordered = sorted(chips, key=lambda c: c['y'])
    assert result['sirali'] and result['atlanan'] == 0
    assert [c['yy'] for c in ordered] == sorted(c['yy'] for c in ordered)
    assert chips[2]['yy'] == 290.5
