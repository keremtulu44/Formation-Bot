"""Generate readable descriptive tables and weak-arrow CSV from a completed replay.

This operates only on exported event/manifest files, not on live state. The
cluster bootstrap is exploratory: it resamples symbols, not calendar dates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "docs/arastirma/stabil_ok_replay_2026_11_05"


def _bools(series: pd.Series) -> pd.Series:
    return series.isin([True, "True"])


def groups(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    result = []
    for key, group in frame.groupby(columns, dropna=False, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        n = len(group)
        result.append({"grup": " / ".join(str(k) for k in key), "n": n,
                       "hisse": int(group.symbol.nunique()),
                       "zayif": int(_bools(group.weak_mfe_8).sum()),
                       "zayif_yuzde": 100 * float(_bools(group.weak_mfe_8).mean()),
                       "medyan_kapanis_atr": float(group.return_atr_8.median()),
                       "ilk_yukari_yuzde": 100 * float((group.first_1atr_8 == "UP_FIRST").mean()),
                       "ilk_asagi_yuzde": 100 * float((group.first_1atr_8 == "DOWN_FIRST").mean())})
    return result


def cluster_difference(frame: pd.DataFrame, draws: int = 5000) -> tuple[float, float, float] | None:
    """Symbol-clustered interval for LOW minus HIGH weak-event proportion."""
    subset = frame[frame.volume_bucket.isin(["LOW_LT_0.8", "HIGH_GE_1.2"])].copy()
    if subset.empty or subset.symbol.nunique() < 2:
        return None
    subset["weak"] = _bools(subset.weak_mfe_8).astype(int)
    cross = subset.groupby(["symbol", "volume_bucket"]).weak.agg(["size", "sum"])
    matrix = np.zeros((subset.symbol.nunique(), 4), dtype=float)
    for i, symbol in enumerate(sorted(subset.symbol.unique())):
        for j, bucket in enumerate(("LOW_LT_0.8", "HIGH_GE_1.2")):
            if (symbol, bucket) in cross.index:
                matrix[i, 2 * j:2 * j + 2] = cross.loc[(symbol, bucket), ["size", "sum"]].to_numpy()
    totals = matrix.sum(axis=0)
    if totals[0] == 0 or totals[2] == 0:
        return None
    rng = np.random.default_rng(20261105)
    indices = rng.integers(0, len(matrix), size=(draws, len(matrix)))
    sampled = matrix[indices].sum(axis=1)
    usable = sampled[(sampled[:, 0] > 0) & (sampled[:, 2] > 0)]
    if not len(usable):
        return None
    differences = 100 * (usable[:, 1] / usable[:, 0] - usable[:, 3] / usable[:, 2])
    point = 100 * (totals[1] / totals[0] - totals[3] / totals[2])
    return float(point), float(np.quantile(differences, .025)), float(np.quantile(differences, .975))


def _table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "*Gözlem yok.*\n"
    lines = ["| Grup | Olay n | Hisse n | Zayıf n | Zayıf % | Medyan kapanış (ATR) | +1 ATR önce % | −1 ATR önce % |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['grup']} | {row['n']} | {row['hisse']} | {row['zayif']} | "
                     f"{row['zayif_yuzde']:.1f} | {row['medyan_kapanis_atr']:+.2f} | "
                     f"{row['ilk_yukari_yuzde']:.1f} | {row['ilk_asagi_yuzde']:.1f} |")
    return "\n".join(lines) + "\n"


def weak_csv(events: pd.DataFrame, destination: Path) -> int:
    valid = events[(events.event_class == "UP_ARROW") & (events.status_8 == "VALID")].copy()
    weak = valid[_bools(valid.weak_mfe_8)].copy()
    names = {
        "symbol": "sembol", "event_close_time": "olay_kapanisi_istanbul", "kind": "ok_turu",
        "regime_proxy": "destek_rejimi_proxy", "price": "fiyat", "support": "destek",
        "atr14_4h": "atr14_4s", "volume_ratio20": "hacim_onceki20_orani", "volume_bucket": "hacim_grubu",
        "volume_domain_level": "hacim_motoru", "ob_ahead": "ob_konumu", "ob_distance_atr": "ob_uzaklik_atr",
        "ob_remaining_low": "ob_kalan_alt", "ob_remaining_high": "ob_kalan_ust", "ob_fill_ratio": "ob_dolum",
        "fvg_ahead": "fvg_konumu", "fvg_distance_atr": "fvg_uzaklik_atr",
        "fvg_remaining_low": "fvg_kalan_alt", "fvg_remaining_high": "fvg_kalan_ust",
        "ms_external_state": "dis_yapi", "stabil_daily_raw_state": "stabil_gunluk",
        "stabil_h4_state": "stabil_4s", "mfe_atr_8": "mfe_8_atr", "mae_atr_8": "mae_8_atr",
        "return_atr_8": "kapanis_8_atr", "first_1atr_8": "ilk_1atr", "nonoverlap_8": "en_az_8_bar_ayrik",
        "domain_errors": "motor_hatalari",
    }
    weak = weak[list(names)].rename(columns=names)
    weak.to_csv(destination, index=False, encoding="utf-8", float_format="%.6f", lineterminator="\n")
    return len(weak)


def generate(events_path: Path, manifest_path: Path, output: Path) -> str:
    events = pd.read_csv(events_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if events.empty:
        raise ValueError("Replay contains no events")
    output.mkdir(parents=True, exist_ok=True)
    weak_count = weak_csv(events, output / "zayif_oklar.csv")
    arrows = events[events.event_class == "UP_ARROW"].copy()
    valid_all = events[events.status_8 == "VALID"].copy()
    valid = arrows[arrows.status_8 == "VALID"].copy()
    valid["kapanis_saati"] = valid.event_close_time.str.slice(11, 16)
    valid["engel_cifti"] = np.where(
        (valid.ob_ahead == "UNKNOWN") | (valid.fvg_ahead == "UNKNOWN"), "UNKNOWN",
        np.where((valid.ob_ahead == "NEAR_1ATR") & (valid.fvg_ahead == "NEAR_1ATR"), "ikisi yakın",
                 np.where(valid.ob_ahead == "NEAR_1ATR", "yalnız OB yakın",
                          np.where(valid.fvg_ahead == "NEAR_1ATR", "yalnız FVG yakın", "ikisi de yakın değil"))))
    coverage = manifest["symbol_coverage"]
    classes = events.event_class.value_counts().to_dict()
    statuses = arrows.status_8.value_counts().to_dict()
    first = valid.first_1atr_8.value_counts().to_dict()
    separated = valid[_bools(valid.nonoverlap_8)]
    captures_4h = sum(c.get("excluded_unclosed_4h", 0) for c in coverage)
    captures_1d = sum(c.get("excluded_unclosed_1d", 0) for c in coverage)
    lines = [
        f"Başarılı/istenen hisse: **{len(manifest['symbols_successful'])}/{len(manifest['symbols_requested'])}**; "
        f"hatalı: **{len(manifest['symbols_failed'])}**. Tüm olaylar: **{len(events)}**; sınıflar: "
        + ", ".join(f"`{k}` {v}" for k, v in sorted(classes.items())) + ".",
        f"Arşiv yakalama sınırıyla kapanmamış **{captures_4h} adet 4s** ve **{captures_1d} adet günlük** "
        "bar dışlandı. Bu, eksik seansları bağımsız denetlemez.",
        f"`▲` 8-bar durumları: " + ", ".join(f"`{k}` {v}" for k, v in sorted(statuses.items())) + ".",
        f"Geçerli 8 barlı **{len(valid)} ▲** içinde zayıf MFE (<0,5 ATR) **{weak_count} "
        f"(%{100 * weak_count / len(valid):.1f})**; en az 8 bar ayrılmış geçerli ok **{len(separated)}**."
        if len(valid) else "Geçerli 8 barlı ▲ bulunmadı; zayıf oranı hesaplanmadı.",
        "8 bar ±1 ATR ilk temas sayıları: " + ", ".join(f"`{k}` {v}" for k, v in sorted(first.items())) + ".",
        "",
        "Aşağıdaki yüzde paydası, her satırdaki **geçerli 8-barlık olay n**'dir. "
        "İlk-temas yüzdeleri aynı-bar belirsiz ve hiç temas etmeyenleri de paydada tutar. "
        "Az n/hisse sayılı gruplar kararsızdır; olaylar ve tarihler bağımsız değildir.", "",
        "### Ok/uyarı sınıfları (farklı popülasyonlar)", _table(groups(valid_all, ["event_class"])),
        "Bastırılmış önceki ▲ adayları ile kalan ▲ okları aynı olaylar değildir; "
        "bu tablo politikanın nedensel etkisi veya ▼ sonrası düşüş garantisi değildir.", "",
        "### Hacim karşılaştırması", _table(groups(valid, ["volume_bucket"])),
        "### Kapanış saati × hacim", _table(groups(valid, ["kapanis_saati", "volume_bucket"])),
        "Kısa seans-sonu kovaları önceki 20 karma uzunluktaki bara karşı düşük hacimli görünebilir; "
        "saat içi karşılaştırmalar da nedensel ayarlama değildir.", "",
        "### Öndeki bearish OB ve seçili bearish FVG", _table(groups(valid, ["ob_ahead"])),
        _table(groups(valid, ["fvg_ahead"])),
        "### Yakın OB/FVG birlikte", _table(groups(valid, ["engel_cifti"])),
        "### Dış piyasa yapısı", _table(groups(valid, ["ms_external_state"])),
        "### Stabil 4s ve günlük bağlam", _table(groups(valid, ["stabil_h4_state"])),
        _table(groups(valid, ["stabil_daily_raw_state"])),
        "### Ok türü ve destek rejimi proxy'si", _table(groups(valid, ["kind"])),
        _table(groups(valid, ["regime_proxy"])),
        "### Hisse başına en az 8 bar ayrılmış alt kümede hacim", _table(groups(separated, ["volume_bucket"])),
    ]
    interval = cluster_difference(valid)
    if interval is not None:
        point, low, high = interval
        lines.extend([f"Düşük eksi yüksek hacim için zayıf tepki oranı farkı **{point:+.1f} yüzde puan**; "
                      f"5.000 hisse-kümeli bootstrap ile betimsel %95 aralık **[{low:+.1f}, {high:+.1f}] puan**. "
                      "Hisseler ortak tarih şoklarını paylaşır, seçim/çoklu deneme ve gün korelasyonu "
                      "bu aralıkla düzeltilmemiştir; nedensel kanıt veya canlı tahmin değildir.", ""])
    lines.extend(["### Farklı pencerelerde zayıf MFE",
                  "Her ufuk için yalnız o ufkun tam/geçerli olayları; farklı paydalar aynı olayı izleme garantisi vermez.", "",
                  "| Sonraki bar | Geçerli ▲ | Zayıf MFE n | Zayıf % |",
                  "|---:|---:|---:|---:|"])
    for horizon in (4, 8, 16):
        current = arrows[arrows[f"status_{horizon}"] == "VALID"]
        count = int(_bools(current[f"weak_mfe_{horizon}"]).sum())
        rate = f"{100 * count / len(current):.1f}" if len(current) else "—"
        lines.append(f"| {horizon} | {len(current)} | {count} | {rate} |")
    text = "\n".join(lines).rstrip() + "\n"
    (output / "toplu_bulgular.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(generate(args.input / "events.csv.gz", args.input / "summary.json", args.output))


if __name__ == "__main__":
    main()
