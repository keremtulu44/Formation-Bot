"""T2 ölçüm — gölge zincir defterinden ölçüm, kör baz ve kural etkileri.

Girdi : ``docs/arastirma/sonuclar/golge_zincir/golge_defter.jsonl`` (+ ozet.json)
Çıktı : aynı dizin: ``plan_sonuc.csv``, ``kor_baz.csv``, ``olcum_ozet.json``

Ölçtükleri (plan belgesi §4, kapı girdisi):
* plan sonuçları: stop/hedef/zaman/yok + koşullu hedef + beklenti
  (maliyet ızgarası 0 / 0,05 / 0,10 ATR — **varsayımsal, etiketli**);
* **kör baz**: aynı tetikleyicilerde hüküm yok sayılsaydı (tüm geometrik
  tetikler, 20 bar açgözlü örtüşmesiz) → UYGUN'un farkı (K2);
* keşif/doğrulama, TF kırılımı;
* G1 negatif kontrolü (kapalıyken plan/UYGUN payı) ve K5 (RET sonrası plan);
* kural etkileri: streak / gün-durdur / tavan (kural-yok'a göre).

Reprodüksiyon: ``python research/golge_olcum.py`` — tüm sayılar defterden
yeniden üretilir.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from senaryo.defter import GolgeDefter  # noqa: E402
from senaryo.kurallar import gun_durdur_uygula, streak_uygula, tavan_uygula  # noqa: E402
from senaryo.yaris import yaris_penceresi  # noqa: E402

VARSAYILAN_DEFTER = KOK / "docs/arastirma/sonuclar/golge_zincir/golge_defter.jsonl"
MALIYETLER = (0.0, 0.05, 0.10)
ORTUSESIZ_BAR = 20
H_VARSAYILAN = 10


def _pnl_ozet(df: pd.DataFrame, maliyet: float = 0.0) -> dict[str, Any]:
    """Çözülmüş işlemlerden beklenti; sansür/süreç ayrı sayılır."""
    cozulmus = df[df["sonuc"].isin(["hedef", "stop", "zaman"])]
    n = len(df)
    sayim = Counter(df["sonuc"].tolist())
    kosullu = None
    if sayim["hedef"] + sayim["stop"] > 0:
        kosullu = round(100 * sayim["hedef"] / (sayim["hedef"] + sayim["stop"]), 2)
    beklenti = round(float(cozulmus["pnl_atr"].mean()) - maliyet, 4) if len(cozulmus) else None
    return {
        "n": n,
        "cozulen": int(len(cozulmus)),
        "sansurlu": int(sayim.get("yok", 0) + sayim.get("sansur", 0)),
        "sonuc": dict(sayim),
        "kosullu_hedef_yuzde": kosullu,
        "beklenti_atr": beklenti,
    }


def kor_baz(
    tetikler: list[dict[str, Any]],
    kapanislar: dict[tuple[str, str], list[float]],
) -> list[dict[str, Any]]:
    """Geometrik tüm tetikler → 20 bar açgözlü örtüşmesiz → yarış (hüküm yok)."""
    grup: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in tetikler:
        if not t.get("geometri"):
            continue
        grup[(t["sembol"], t["tf"])].append(t)
    cikti: list[dict[str, Any]] = []
    for (sembol, tf), liste in grup.items():
        kapanis = kapanislar.get((sembol, tf))
        if not kapanis:
            continue
        son = -10**9
        for t in sorted(liste, key=lambda x: int(x["bar_index"])):
            i = int(t["bar_index"])
            if i < son + ORTUSESIZ_BAR:
                continue
            son = i
            s, c, pnl, mae = yaris_penceresi(
                kapanis, i + 1, H_VARSAYILAN,
                float(t["giris"]), float(t["stop"]), float(t["hedef"]), float(t["atr"]),
            )
            cikti.append({
                "sembol": sembol, "tf": tf, "t": t["t"], "bar_index": i,
                "donem": t["donem"], "hukum": t["hukum"],
                "g1_kapali": t["g1_kapali"], "R": t["R"],
                "sonuc": s, "cozunme_bar": c,
                "pnl_atr": round(pnl, 4), "mae_atr": round(mae, 4),
            })
    return cikti


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="T2 ölçüm (gölge zincir)")
    p.add_argument("--defter", default=str(VARSAYILAN_DEFTER))
    p.add_argument("--cikti", default="", help="varsayılan: defterin dizini")
    args = p.parse_args(argv)

    defter_yol = Path(args.defter)
    cikti = Path(args.cikti) if args.cikti else defter_yol.parent
    cikti.mkdir(parents=True, exist_ok=True)

    kayitlar, bozuk = GolgeDefter.oku(defter_yol)
    if not kayitlar:
        print("defter boş", file=sys.stderr)
        return 1

    planlar = [k for k in kayitlar if k["tip"] == "plan"]
    sonuclar = {k["plan_id"]: k for k in kayitlar if k["tip"] == "sonuc"}
    tetikler = [k for k in kayitlar if k.get("tur") == "tetik"]
    hukum_sirasi = [k for k in kayitlar if k["tip"] == "hukum"]

    # --- plan + sonuc birleşimi --------------------------------------------
    psatirlar: list[dict[str, Any]] = []
    for pl in planlar:
        sc = sonuclar.get(pl["plan_id"])
        psatirlar.append({
            "plan_id": pl["plan_id"], "sembol": pl["sembol"], "tf": pl["tf"],
            "t": pl["t"], "bar_index": pl["bar_index"], "donem": pl["donem"],
            "R": pl["R"], "giris": pl["giris"], "stop": pl["stop"],
            "hedef": pl["hedef"], "zaman_stopu": pl["zaman_stopu"],
            "sonuc": sc["sonuc"] if sc else "sansur",
            "cozunme_bar": sc["cozunme_bar"] if sc else None,
            "pnl_atr": sc["pnl_atr"] if sc else 0.0,
            "mae_atr": sc["mae_atr"] if sc else None,
            "hukum_satiri": pl["hukum_satiri"],
        })
    plan_df = pd.DataFrame(psatirlar)

    # --- kör baz (çerçeveleri yeniden oku) ---------------------------------
    print(f"defter: {len(kayitlar)} kayıt (bozuk {bozuk}) · plan {len(planlar)} · "
          f"tetik {len(tetikler)}")
    geo_tetik = [t for t in tetikler if t.get("geometri")]
    kapanislar: dict[tuple[str, str], list[float]] = {}
    from research.arsiv import tf_frame
    for (sembol, tf) in sorted({(t["sembol"], t["tf"]) for t in geo_tetik}):
        try:
            frame = tf_frame(sembol, tf)
            kapanislar[(sembol, tf)] = [float(x) for x in frame["close"].tolist()]
        except Exception as hata:  # noqa: BLE001
            print(f"  ! {sembol}/{tf}: {hata}")
    kor = pd.DataFrame(kor_baz(tetikler, kapanislar))
    print(f"kör baz: {len(kor)} işlem ({len(kapanislar)} seri)")

    # --- ana ölçümler -------------------------------------------------------
    ozet: dict[str, Any] = {"defter": str(defter_yol), "bozuk_satir": bozuk}

    # 1) plan sonuçları (genel + dönem + TF)
    ozet["plan_genel"] = _pnl_ozet(plan_df)
    ozet["plan_donen"] = {
        d: _pnl_ozet(g) for d, g in plan_df.groupby("donem")}
    ozet["plan_tf"] = {tf: _pnl_ozet(g) for tf, g in plan_df.groupby("tf")}
    ozet["maliyet_izgarasi"] = {
        f"{d}_maliyet_{m}": _pnl_ozet(g, m)
        for d, g in plan_df.groupby("donem") for m in MALIYETLER}

    # 2) kör baz + hüküm kırılımı
    if len(kor):
        ozet["kor_genel"] = _pnl_ozet(kor)
        ozet["kor_donen"] = {d: _pnl_ozet(g) for d, g in kor.groupby("donem")}
        ozet["kor_hukum"] = {h: _pnl_ozet(g) for h, g in kor.groupby("hukum")}
        ozet["kor_tf"] = {tf: _pnl_ozet(g) for tf, g in kor.groupby("tf")}

    # 3) kapı girdisi (eşikler plan belgesinde önceden kayıtlı)
    dog = plan_df[plan_df["donem"] == "dogrulama"]
    dog_kor = kor[kor["donem"] == "dogrulama"] if len(kor) else pd.DataFrame()
    uygun_kos = ozet["plan_donen"].get("dogrulama", {}).get("kosullu_hedef_yuzde")
    kor_kos = (_pnl_ozet(dog_kor)["kosullu_hedef_yuzde"] if len(dog_kor) else None)
    g1_kapali_plan_ids = {t["plan_id"] for t in tetikler
                          if t.get("plan_id") and t.get("g1_kapali")}
    g1_kapali_plan = sum(1 for pl in planlar if pl["plan_id"] in g1_kapali_plan_ids)
    # K5: her planın öncesindeki son hüküm değişimi UYGUN olmalı
    son_degisim: str | None = None
    plan_id_sirasi = {pl["plan_id"] for pl in planlar}
    k5_ihlal = 0
    # defter sırası kronolojik yazımdır
    for k in kayitlar:
        if k["tip"] == "hukum":
            son_degisim = k["hukum"]
        elif k["tip"] == "plan" and k["plan_id"] in plan_id_sirasi:
            if son_degisim != "UYGUN":
                k5_ihlal += 1
    g1_kapali_tetik = [t for t in tetikler if t.get("g1_kapali")]
    ozet["kapi_girdisi"] = {
        "K1_dogrulama_uygun_n": int(len(dog)),
        "K2_kor_farki_puan": (
            round(uygun_kos - kor_kos, 2)
            if (uygun_kos is not None and kor_kos is not None) else None),
        "K2_uygun_kosullu": uygun_kos,
        "K2_kor_kosullu": kor_kos,
        "K3_dogrulama_beklenti": ozet["plan_donen"].get("dogrulama", {}).get("beklenti_atr"),
        "K4_g1_kapali_plan_orani": round(100 * g1_kapali_plan / max(1, len(planlar)), 2),
        "K4_g1_kapali_tetik_payi": round(100 * len(g1_kapali_tetik) / max(1, len(tetikler)), 2),
        "K5_ret_sonrasi_plan_ihlal": k5_ihlal,
        "K6_kesif_beklenti": ozet["plan_donen"].get("kesif", {}).get("beklenti_atr"),
        "K6_dogrulama_beklenti": ozet["plan_donen"].get("dogrulama", {}).get("beklenti_atr"),
    }

    # 3b) görünürlük GA'sı — sembol-gruplu bootstrap (rapor katmanı;
    #      KARAR KAPISI DEĞİL, yalnız belirsizlik görünürlüğü — denetçi notu)
    if len(dog) and len(dog_kor):
        import numpy as np

        def _sembol_toplam(df: pd.DataFrame) -> pd.DataFrame:
            coz = df[df["sonuc"].isin(["hedef", "stop", "zaman"])]
            return pd.DataFrame({
                "hedef": df[df["sonuc"] == "hedef"].groupby("sembol").size(),
                "stop": df[df["sonuc"] == "stop"].groupby("sembol").size(),
                "coz_pnl": coz.groupby("sembol")["pnl_atr"].sum(),
                "coz_n": coz.groupby("sembol")["pnl_atr"].count(),
            }).fillna(0.0)

        _pp, _pk = _sembol_toplam(dog), _sembol_toplam(dog_kor)
        _rng = np.random.default_rng(42)
        _k2, _k3 = [], []
        for _ in range(2000):
            sp = _pp.iloc[_rng.integers(0, len(_pp), len(_pp))]
            sk = _pk.iloc[_rng.integers(0, len(_pk), len(_pk))]
            hp, hs = float(sp["hedef"].sum()), float(sp["stop"].sum())
            kp, ks = float(sk["hedef"].sum()), float(sk["stop"].sum())
            if hp + hs > 0 and kp + ks > 0:
                _k2.append(100.0 * hp / (hp + hs) - 100.0 * kp / (kp + ks))
            if float(sp["coz_n"].sum()) > 0:
                _k3.append(float(sp["coz_pnl"].sum()) / float(sp["coz_n"].sum()))
        if _k2 and _k3:
            ozet["ga95"] = {
                "aciklama": ("sembol-gruplu bootstrap; B=2000, tohum=42; "
                             "yalnız görünürlük (rapor), karar kapısı değil"),
                "K2_puan": [round(float(np.percentile(_k2, 2.5)), 2),
                            round(float(np.percentile(_k2, 97.5)), 2)],
                "K3_beklenti": [round(float(np.percentile(_k3, 2.5)), 4),
                                round(float(np.percentile(_k3, 97.5)), 4)],
            }

    # 4) kural etkileri (kural-yok toplamına göre)
    if len(plan_df):
        ham = plan_df[plan_df["sonuc"] != "sansur"].to_dict("records")
        kurallar: dict[str, Any] = {}
        for ad, fn in (("streak", streak_uygula), ("gun_durdur", gun_durdur_uygula),
                       ("tavan", tavan_uygula)):
            yeni, o = fn(ham)
            df2 = pd.DataFrame(yeni)
            calisan = df2[df2["kural"] == "kural_yok"]
            atlanan = df2[df2["kural"] != "kural_yok"]
            o["ham_toplam_pnl"] = round(sum(r["pnl_atr"] for r in ham), 3)
            o["kural_sonrasi_toplam_pnl"] = round(float(calisan["pnl_atr"].sum()), 3)
            o["atlanan_islem_pnl_kaybi"] = round(
                o["ham_toplam_pnl"] - o["kural_sonrasi_toplam_pnl"], 3)
            o["atlanan_islemler"] = [
                {"plan_id": r["plan_id"], "sonuc": r["sonuc"], "pnl_atr": r["pnl_atr"]}
                for r in atlanan.to_dict("records")]
            kurallar[ad] = o
        ozet["kurallar"] = kurallar

    # 5) çözüm/MAE/R istatistikleri (çözülen planlar)
    cozulmus = plan_df[plan_df["sonuc"].isin(["hedef", "stop", "zaman"])]
    if len(cozulmus):
        ozet["cozunme"] = {
            "medyan_bar": float(cozulmus["cozunme_bar"].median()),
            "p75_bar": float(cozulmus["cozunme_bar"].quantile(0.75)),
            "R_medyan": float(cozulmus["R"].median()),
            "mae_p50": float(cozulmus["mae_atr"].median()),
            "mae_p90": float(cozulmus["mae_atr"].quantile(0.90)),
        }

    # 6) hüküm/kademe sayaçları
    ozet["hukum_degisim_sayim"] = dict(Counter(k["hukum"] for k in hukum_sirasi))
    ozet["tetik_sayim"] = {
        "toplam": len(tetikler),
        "geometri": len(geo_tetik),
        "hukum": dict(Counter(t["hukum"] for t in tetikler)),
        "g1_kapali": len(g1_kapali_tetik),
    }

    # --- pasaport (determinizm: aynı girdi → aynı sonuç,5 dk'da doğrulanır) --
    import hashlib
    import platform

    def _sha256(dosya: str) -> str:
        h = hashlib.sha256()
        with open(dosya, "rb") as f:
            for parca in iter(lambda: f.read(1 << 20), b""):
                h.update(parca)
        return h.hexdigest()

    ozet["pasaport"] = {
        "defter_sha256": _sha256(str(defter_yol)),
        "defter_boyut_bayt": Path(str(defter_yol)).stat().st_size,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "plan_n": int(len(plan_df)),
        "sembol_n": int(plan_df["sembol"].nunique()) if len(plan_df) else 0,
    }

    # --- dosyalar -----------------------------------------------------------
    plan_df.to_csv(cikti / "plan_sonuc.csv", index=False)
    kor.to_csv(cikti / "kor_baz.csv", index=False)
    (cikti / "olcum_ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(ozet["kapi_girdisi"], ensure_ascii=False, indent=2))
    print(f"yazıldı: {cikti}/plan_sonuc.csv, kor_baz.csv, olcum_ozet.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
