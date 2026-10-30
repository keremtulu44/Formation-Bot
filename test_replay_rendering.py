"""Replay uses the ordinary chart pipeline without future leakage or live-state writes."""
from copy import deepcopy
import random
import re

import pytest

from research import replay_egitim as eg


@pytest.fixture
def question():
    return eg.soru_sec("ASTOR", rng=random.Random(7))


@pytest.mark.parametrize("tf", eg.TFS)
def test_replay_snapshot_uses_same_normal_analysis_and_view(question, tf, monkeypatch, tmp_path):
    import chart_experience
    import domain_engines.runner as runner
    import grafik
    import grafik_uret

    monkeypatch.setattr(runner, "_latest_by_series", {})
    monkeypatch.setattr(runner, "_incremental_states_by_series", {})
    monkeypatch.setattr(runner, "_series_state_locks", {})
    monkeypatch.setenv("GRAFIK_GORUNUM", "odak")
    q = question
    p = q.positions[tf]
    history = q.frames[tf].iloc[max(0, p + 1 - 900):p + 1].copy(deep=True)
    replay = eg._soru_goruntusu(q, tf)
    assert runner.get_latest_domain_results(q.sembol, tf) is None
    captured = {}
    monkeypatch.setattr(grafik_uret, "cerceve_getir", lambda *a, **kw: (history, "arşiv"))
    def capture(snapshot, timeframe, secenekler):
        captured["snapshot"] = deepcopy(snapshot)
        return str(tmp_path / "normal.png"), {"uyarilar": []}
    monkeypatch.setattr(grafik, "ciz", capture)
    normal = grafik_uret.kare_uret(
        q.sembol, tf, zone=True, formasyon_tara=True, tarihsel=True,
        simdi=q.closes[tf][p].to_pydatetime(), cikti=str(tmp_path / "normal.png"),
    )
    assert normal["hata"] is None
    expected = chart_experience.prepare_view(captured["snapshot"], "odak")
    for name in ("zamanlar", "acilis", "yuksek", "dusuk", "kapanis", "formasyon",
                 "alarm", "temas", "isaretler", "olay", "serit", "gorunum"):
        assert replay[name] == expected[name], name
    for key in ("tum", "cizilen"):
        for zone in expected["zone"].get(key) or []:
            zone.pop("zaman", None)
    assert replay["zone"] == expected["zone"]
    assert replay["replay"]["kesit"] == len(replay["zamanlar"]) - 1
    assert replay["guven"]["durum"] == "HISTORICAL"


@pytest.mark.parametrize("tf", eg.TFS)
def test_future_candles_cannot_change_any_question_analysis(question, tf):
    original = eg._soru_goruntusu(question, tf)
    altered = deepcopy(question)
    altered.snapshots.clear()
    p = altered.positions[tf]
    for col in ("open", "high", "low", "close", "volume"):
        altered.frames[tf].iloc[p + 1:, altered.frames[tf].columns.get_loc(col)] *= 4
    assert eg._soru_goruntusu(altered, tf) == original


@pytest.mark.parametrize("tf", eg.TFS)
def test_result_keeps_question_view_and_shows_every_future_candle(question, tf, tmp_path):
    q = question
    q.tf, q.horizon = "1d", 20
    answer = eg.sonuc(q, "yatay")
    p = q.positions[tf]
    end = int(q.closes[tf].searchsorted(answer["finish"], side="right") - 1)
    before = eg._soru_goruntusu(q, tf)
    result = eg._sonuc_goruntusu(q, tf, end)
    n = len(before["zamanlar"])
    assert result["replay"]["kesit"] == n - 1
    assert result["kapanis"][:n] == before["kapanis"]
    assert result["kapanis"][n:] == q.frames[tf]["close"].iloc[p + 1:end + 1].tolist()
    assert len(result["zamanlar"]) == n + end - p
    for key in ("zone", "olay", "formasyon", "serit", "sol", "gorunum"):
        assert result[key] == before[key]
    meta = eg._draw(q, tf, end, str(tmp_path / f"{tf}.png"), result=True)
    assert meta["mum_sayisi"] == n + end - p
    assert meta["zone"]["cizilen"] == len(before["zone"].get("cizilen") or [])
    assert meta["gorunum"] == before["gorunum"]
    assert not meta.get("cekme"), meta.get("uyarilar")


@pytest.mark.parametrize("mode", ["odak", "baglam"])
def test_all_visible_text_hides_dates_in_question_and_result(question, mode, monkeypatch, tmp_path):
    from matplotlib.figure import Figure
    from matplotlib.text import Text
    from PIL import Image

    monkeypatch.setenv("GRAFIK_GORUNUM", mode)
    monkeypatch.setenv("GRAFIK_LEJANT_KARE", "1")
    captured = []
    savefig = Figure.savefig
    def capture(fig, *args, **kwargs):
        fig.canvas.draw()
        captured.append([item.get_text() for item in fig.findobj(match=Text)
                         if item.get_visible() and item.get_text()])
        return savefig(fig, *args, **kwargs)
    monkeypatch.setattr(Figure, "savefig", capture)
    q = question
    q.tf, q.horizon = "4h", 8
    answer = eg.sonuc(q, "yatay")
    for tf in eg.TFS:
        p = q.positions[tf]
        eg._draw(q, tf, p, str(tmp_path / f"q-{tf}.png"))
        end = int(q.closes[tf].searchsorted(answer["finish"], side="right") - 1)
        path = tmp_path / f"r-{tf}.png"
        eg._draw(q, tf, end, str(path), result=True)
        with Image.open(path) as image:
            assert not re.search(r"20\d{2}[-/]\d{2}", str(image.info))
    assert len(captured) == 8
    for i, labels in enumerate(captured):
        text = "\n".join(labels)
        assert "TARİHSEL" in text and "tarihler gizli" in text
        assert not re.search(r"\b(?:20\d{2}[-/.]\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]20\d{2})\b", text)
        assert not re.search(r"\b\d{1,2}:\d{2}\b", text)
        assert not re.search(r"\b\d{1,2}\s+(?:Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\b", text)
        if i % 2:
            assert "TAHMİN ANI" in text
            assert "Soru anı:" in text and "sonuç kapanışı" in text
            assert "analiz ve çizimler soru anına aittir" in text
        else:
            assert "TAHMİN ANI" not in text
            assert "±" not in text  # ATR threshold/value is not revealed before the answer


def test_result_labels_pin_formation_and_structure_to_question_time():
    from grafik.panels import _metinler

    snapshot = {
        "sembol": "ASTOR", "tf": "1d", "tf_kisa": "1g", "son_kapanis": 146.7,
        "replay": {"asama": "sonuc"},
        "formasyon": {"ad": "Alçalan Üçgen", "quality": 77, "state": "SIKISMA"},
        "yapı_satırı": "1g yön karışık (dış aşağı, iç yukarı)",
    }
    labels = _metinler(snapshot, {"mum_sayisi": 100}, 1080, [], False)
    assert any(p["metin"].startswith("Soru anı: Alçalan Üçgen") for p in labels["pill_listesi"])
    assert any(line.startswith("Soru anı: 1g yön") for line in labels["satirlar"])
    assert labels["sag"].startswith("sonuç kapanışı")


def test_result_volume_warning_includes_new_candles(question):
    import numpy as np

    tf = "1h"
    p = question.positions[tf]
    before = eg._soru_goruntusu(question, tf)
    volume_column = question.frames[tf].columns.get_loc("volume")
    question.frames[tf].iloc[p + 1:p + 4, volume_column] = [0, np.nan, 1]
    result = eg._sonuc_goruntusu(question, tf, p + 3)
    assert result["hacimsiz_bar"] == before["hacimsiz_bar"] + 2
    assert eg._soru_goruntusu(question, tf)["hacimsiz_bar"] == before["hacimsiz_bar"]


def test_long_result_with_mobile_setting_still_draws_candles(question, monkeypatch, tmp_path):
    monkeypatch.setenv("GRAFIK_MOBIL", "1")
    q = question
    q.tf, q.horizon = "1d", 20
    finish = eg.sonuc(q, "yatay")["finish"]
    end = int(q.closes["1h"].searchsorted(finish, side="right") - 1)
    meta = eg._draw(q, "1h", end, str(tmp_path / "mobile-result.png"), result=True)
    assert meta["mum_sayisi"] > 150
    assert not meta["mod"]["mobil"]
    assert not meta["cekme"]
