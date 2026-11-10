"""Stop ve sermaye koruma replay'i — teyitli kırılım girişlerinde ilk-dokunuş yarışı.

NE YAPAR (salt ölçüm; canlı kararı değiştirmez):
  * Girdi: docs/arastirma/sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz
    (174 hisse × 4 TF; giriş = teyit barının kapanışı, birim = teyit anındaki ATR).
  * Her giriş için teyit barından SONRAKİ kapanmış barların yolu yeniden okunur
    (arşiv backfill_data/; 2h/4h seansa hizalı resample, 1d native).
  * Izgara: stop S ∈ {0.5, 0.75, 1.0, 1.25, 1.5} ATR × hedef T ∈ {1.0, 1.5, 2.0} ATR
    × ufuk H ∈ {10, 20} bar. İlk dokunuş yarışı: aynı barda ikisi de dokunursa
    MUHAFAZAKÂR sayım → stop (karne kuralı).
  * Ayrım: keşif/doğrulama (dönem kolonu), TF kırılımı, otokorelasyon için
    sembol×TF bazında 20 bar örtüşmesiz seçme.
  * Sermaye koruma: baz hücrede (S=1.0, T=1.5, H=10) sembol başına ardışık
    sıra simülasyonu — üst üste stoplar, aynı günde 2+ stop, "günde 2 stop →
    gün sonu dur" kuralının etkisi, ATR cinsinden equity/maksimum düşüş.

YASAKLAR: geleceğe bakma yok (yalnız ileri barlar); sansürlü/eksik pencere
kazanç/kayb sayılmaz; n < 30 hücre "yetersiz" etiketli raporlanır; bu bir
kârlılık iddiası değildir (maliyet/kayma modellenmedi).

Çıktılar: docs/arastirma/sonuclar/stop_sermaye/*
Kullanım: python scripts/stop_sermaye_replay.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

GIRDI = KOK / "docs/arastirma/sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz"
CIKTI_KOK = KOK / "docs/arastirma/sonuclar/stop_sermaye"

STOP_KOVALARI = (0.5, 0.75, 1.0, 1.25, 1.5)
HEDEF_KOVALARI = (1.0, 1.5, 2.0)
UFUKLAR = (10, 20)
PENCERE = 20  # örtüşmesizlik penceresi (en büyük ufuk)
N_ESIGI = 30

# BAZ HÜCRE — karne varsayılanları (1,5 hedef / 1,0 stop / 10 bar)
BAZ = (1.0, 1.5, 10)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for parc in iter(lambda: f.read(1 << 20), b""):
            h.update(parc)
    return h.hexdigest()


def olaylari_yukle() -> pd.DataFrame:
    df = pd.read_csv(GIRDI)
    df["confirm_time_ts"] = pd.to_datetime(df["confirm_time"], utc=True)
    df["confirm_atr"] = pd.to_numeric(df["confirm_atr"], errors="coerce")
    df["confirm_close"] = pd.to_numeric(df["confirm_close"], errors="coerce")
    df["direction"] = pd.to_numeric(df["direction"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["confirm_atr", "confirm_close", "direction"])
    df = df[(df["confirm_atr"] > 0) & (df["confirm_close"] > 0)]
    return df.reset_index(drop=True)


def serileri_yukle(semboller: list[str], tfs: list[str]) -> dict[tuple[str, str], pd.DataFrame]:
    from research.arsiv import tf_frame

    depo: dict[tuple[str, str], pd.DataFrame] = {}
    for sembol in semboller:
        for tf in tfs:
            try:
                f = tf_frame(sembol, tf)
                f = f[~f.index.duplicated(keep="last")].sort_index()
                depo[(sembol, tf)] = f
            except Exception as hata:  # noqa: BLE001 — seri yoksa atla, say
                print(f"  ! {sembol}/{tf}: {hata}")
    return depo


def bar_bul(index: pd.Timestamp, zaman: pd.Timestamp) -> int:
    """confirm barının seri içindeki konumu (tam eşitlik; yoksa -1)."""
    return int(index.get_indexer([zaman])[0])


def yolu_al(frame: pd.DataFrame, idx: int, halk: int, giriş: float, atr: float, yon: int) -> np.ndarray | None:
    """Teyit barından sonraki `halk` kapanışın ATR cinsinden yönlü yolu."""
    kapanislar = frame["close"].to_numpy(dtype=float)
    ileri = kapanislar[idx + 1: idx + 1 + halk]
    if len(ileri) < halk:
        return None  # sağdan sansürlü — sonuç sayılmaz
    return yon * (ileri - giriş) / atr


def yarisi(yol: np.ndarray, stop: float, hedef: float) -> tuple[str, int | None]:
    """İlk dokunuş yarışı: 'stop' | 'hedef' | 'yok'. Aynı bar → stop."""
    hedef_idx = np.argmax(yol >= hedef) if np.any(yol >= hedef) else None
    stop_idx = np.argmax(yol <= -stop) if np.any(yol <= -stop) else None
    if hedef_idx is None and stop_idx is None:
        return "yok", None
    if stop_idx is None:
        return "hedef", int(hedef_idx)
    if hedef_idx is None:
        return "stop", int(stop_idx)
    if stop_idx <= hedef_idx:  # eşitlik → muhafazakâr: stop
        return "stop", int(stop_idx)
    return "hedef", int(hedef_idx)


def main() -> int:
    CIKTI_KOK.mkdir(parents=True, exist_ok=True)
    print("1) Olaylar okunuyor…")
    df = olaylari_yukle()
    ham_n = len(df)
    tfs = sorted(df["tf"].unique())
    semboller = sorted(df["symbol"].unique())
    print(f"   {ham_n} olay · {len(semboller)} sembol · TF {tfs}")

    print("2) Seriler yükleniyor…")
    depo = serileri_yukle(semboller, tfs)

    print("3) Yollar + yarışlar hesaplanıyor…")
    kayitlar: list[dict] = []
    eslesmeyen = 0
    sansurlu = 0
    for row in df.itertuples(index=False):
        anahtar = (row.symbol, row.tf)
        frame = depo.get(anahtar)
        if frame is None:
            eslesmeyen += 1
            continue
        idx = bar_bul(frame.index, row.confirm_time_ts)
        if idx < 0:
            eslesmeyen += 1
            continue
        yol20 = yolu_al(frame, idx, PENCERE, float(row.confirm_close),
                        float(row.confirm_atr), int(row.direction))
        if yol20 is None:
            sansurlu += 1
            continue
        kayitlar.append({
            "symbol": row.symbol, "tf": row.tf, "period": row.period,
            "confirm_idx": idx, "confirm_time": row.confirm_time_ts,
            "yol": yol20,
        })

    print(f"   geçerli yol: {len(kayitlar)} · eşleşmeyen: {eslesmeyen} · sansürlü: {sansurlu}")

    # --- örtüşmesiz seçme (sömine × TF, kronolojik, pencere 20) --------------
    grup: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for k in kayitlar:
        grup[(k["symbol"], k["tf"])].append(k)
    secim: list[dict] = []
    for (_, _), liste in grup.items():
        liste.sort(key=lambda x: x["confirm_idx"])
        son = -10**9
        for k in liste:
            if k["confirm_idx"] >= son + PENCERE:
                secim.append(k)
                son = k["confirm_idx"]
    print(f"   örtüşmesiz: {len(secim)} (ham {len(kayitlar)})")

    # --- ızgara istatistikleri ----------------------------------------------
    def hucreler(kaynak: list[dict]) -> list[dict]:
        cikti = []
        for ufuk in UFUKLAR:
            for stop in STOP_KOVALARI:
                for hedef in HEDEF_KOVALARI:
                    say = defaultdict(int)
                    cozum_barlari = []
                    for k in kaynak:
                        yol = k["yol"][:ufuk]
                        sonuc, bar = yarisi(yol, stop, hedef)
                        say[sonuc] += 1
                        if bar is not None:
                            cozum_barlari.append(bar + 1)
                    n = say["stop"] + say["hedef"] + say["yok"]
                    if n == 0:
                        continue
                    cozun = say["stop"] + say["hedef"]
                    cikti.append({
                        "ufuk": ufuk, "stop_atr": stop, "hedef_atr": hedef,
                        "n": n, "stop": say["stop"], "hedef": say["hedef"], "yok": say["yok"],
                        "stop_yuzde": round(100 * say["stop"] / n, 2),
                        "hedef_yuzde": round(100 * say["hedef"] / n, 2),
                        "yok_yuzde": round(100 * say["yok"] / n, 2),
                        "cozunme_yuzde": round(100 * cozun / n, 2) if n else 0.0,
                        "kosullu_hedef_yuzde": round(100 * say["hedef"] / cozun, 2) if cozun else 0.0,
                        "medyan_cozunme_bar": int(np.median(cozum_barlari)) if cozum_barlari else None,
                        "beklenti_atr": round(
                            (say["hedef"] * hedef - say["stop"] * stop) / n, 4),
                        "guven": "yeterli" if n >= N_ESIGI else ("kismi" if n >= 15 else "zayif"),
                    })
        return cikti

    print("4) Izgara yazılıyor…")
    grid = hucreler(secim)
    pd.DataFrame(grid).to_csv(CIKTI_KOK / "stop_grid.csv", index=False)

    # TF kırılımı (baz hücre dışındaki hücreler tek tek TF'ye bölünmez — baz hücre TF'li)
    tf_satirlari = []
    for tf in tfs:
        alt = [k for k in secim if k["tf"] == tf]
        if not alt:
            continue
        for ufuk in UFUKLAR:
            for stop, hedef in [(0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (1.0, 2.0), (1.5, 1.5)]:
                say = defaultdict(int)
                for k in alt:
                    sonuc, _ = yarisi(k["yol"][:ufuk], stop, hedef)
                    say[sonuc] += 1
                n = sum(say.values())
                tf_satirlari.append({
                    "tf": tf, "ufuk": ufuk, "stop_atr": stop, "hedef_atr": hedef,
                    "n": n, "stop": say["stop"], "hedef": say["hedef"], "yok": say["yok"],
                    "stop_yuzde": round(100 * say["stop"] / n, 2),
                    "hedef_yuzde": round(100 * say["hedef"] / n, 2),
                    "beklenti_atr": round((say["hedef"] * hedef - say["stop"] * stop) / n, 4),
                    "guven": "yeterli" if n >= N_ESIGI else ("kismi" if n >= 15 else "zayif"),
                })
    pd.DataFrame(tf_satirlari).to_csv(CIKTI_KOK / "stop_grid_tf.csv", index=False)

    # Dönem (keşif/doğrulama) kırılımı — baz hücre
    donem_satirlari = []
    for donem in sorted({k["period"] for k in secim}):
        alt = [k for k in secim if k["period"] == donem]
        say = defaultdict(int)
        for k in alt:
            sonuc, _ = yarisi(k["yol"][:BAZ[2]], BAZ[0], BAZ[1])
            say[sonuc] += 1
        n = sum(say.values())
        donem_satirlari.append({
            "period": donem, "stop_atr": BAZ[0], "hedef_atr": BAZ[1], "ufuk": BAZ[2],
            "n": n, "stop": say["stop"], "hedef": say["hedef"], "yok": say["yok"],
            "stop_yuzde": round(100 * say["stop"] / n, 2),
            "hedef_yuzde": round(100 * say["hedef"] / n, 2),
            "beklenti_atr": round((say["hedef"] * BAZ[1] - say["stop"] * BAZ[0]) / n, 4),
        })
    pd.DataFrame(donem_satirlari).to_csv(CIKTI_KOK / "stop_grid_donem.csv", index=False)

    # --- MAE (hedefe gidenlerde geri çekilme) + zaman dağılımı ---------------
    print("5) MAE/zaman dağılımı…")
    mae_satirlari = []
    zaman_satirlari = []
    for ufuk in UFUKLAR:
        kazanan_mae, cozum_barlari = [], []
        for k in secim:
            yol = k["yol"][:ufuk]
            sonuc, bar = yarisi(yol, BAZ[0], BAZ[1])
            if sonuc == "hedef" and bar is not None:
                mae_satirlari_ = float(-np.min(np.concatenate([[0.0], yol[: bar + 1]])))
                kazanan_mae.append(mae_satirlari_)
            if bar is not None:
                cozum_barlari.append(bar + 1)
        if kazanan_mae:
            arr = np.array(kazanan_mae)
            zaman_satirlari.append({
                "ufuk": ufuk, "olcum": "kazanclar_mae_atr",
                "n": len(arr), "p50": round(float(np.percentile(arr, 50)), 3),
                "p75": round(float(np.percentile(arr, 75)), 3),
                "p90": round(float(np.percentile(arr, 90)), 3),
                "p95": round(float(np.percentile(arr, 95)), 3),
                "maks": round(float(arr.max()), 3),
            })
        if cozum_barlari:
            arr = np.array(cozum_barlari)
            zaman_satirlari.append({
                "ufuk": ufuk, "olcum": "cozunme_bar",
                "n": len(arr), "p50": int(np.percentile(arr, 50)),
                "p75": int(np.percentile(arr, 75)), "p90": int(np.percentile(arr, 90)),
                "p95": int(np.percentile(arr, 95)), "maks": int(arr.max()),
                "bar5_icinde_yuzde": round(100 * float((arr <= 5).mean()), 2),
                "bar3_icinde_yuzde": round(100 * float((arr <= 3).mean()), 2),
            })
    pd.DataFrame(zaman_satirlari).to_csv(CIKTI_KOK / "mae_ve_zaman.csv", index=False)

    # --- 7) Kısıtsız gürültü toleransı (+1,5'e VARDIĞI halde ne kadar geri çekilindi) ---
    print("7) Kısıtsız MAE + dar-stop pişmanlığı + maliyet duyarlılığı…")
    kisitsiz: dict[str, list[float]] = defaultdict(list)
    for k in secim:
        yol = k["yol"][:UFUKLAR[-1]]
        if np.any(yol >= BAZ[1]):
            i = int(np.argmax(yol >= BAZ[1]))
            mae = float(-np.min(np.concatenate([[0.0], yol[: i + 1]])))
            kisitsiz["tumu"].append(mae)
            kisitsiz[k["tf"]].append(mae)
    kisitsiz_satirlari = []
    for grup_adi, degerler in kisitsiz.items():
        if not degerler:
            continue
        arr = np.array(degerler)
        kisitsiz_satirlari.append({
            "grup": grup_adi, "n": len(arr),
            "p50": round(float(np.percentile(arr, 50)), 3),
            "p75": round(float(np.percentile(arr, 75)), 3),
            "p90": round(float(np.percentile(arr, 90)), 3),
            "p95": round(float(np.percentile(arr, 95)), 3),
            "maks": round(float(arr.max()), 3),
            "yuzde_05_uzerinde": round(100 * float((arr > 0.5).mean()), 2),
            "yuzde_10_uzerinde": round(100 * float((arr > 1.0).mean()), 2),
            "yuzde_15_uzerinde": round(100 * float((arr > 1.5).mean()), 2),
        })
    pd.DataFrame(kisitsiz_satirlari).to_csv(CIKTI_KOK / "kisitsiz_mae.csv", index=False)

    # --- 8) Dar-stop pişmanlığı: S=1.0 ile stop yiyenler, S=1.5 ile ne olurdu? ---
    pisman = defaultdict(int)
    for k in secim:
        yol = k["yol"][:BAZ[2]]
        if yarisi(yol, 1.0, BAZ[1])[0] == "stop":
            pisman[yarisi(yol, 1.5, BAZ[1])[0]] += 1
    toplam_pisman = sum(pisman.values()) or 1
    pisman_satiri = [{
        "durum": "S=1.0_stop_yiyenler_S=1.5_altinda",
        "n": toplam_pisman,
        "hedefe_varan_yuzde": round(100 * pisman["hedef"] / toplam_pisman, 2),
        "yine_stop_yuzde": round(100 * pisman["stop"] / toplam_pisman, 2),
        "yok_yuzde": round(100 * pisman["yok"] / toplam_pisman, 2),
        "yani_dar_stop_pismanligi_yuzde": round(100 * pisman["hedef"] / toplam_pisman, 2),
    }]
    pd.DataFrame(pisman_satiri).to_csv(CIKTI_KOK / "dar_stop_pismanligi.csv", index=False)

    # --- 8b) Aynı pişmanlık H=20'de + seri (streak) kuralları ------------------
    pisman20 = defaultdict(int)
    for k in secim:
        yol = k["yol"][:UFUKLAR[-1]]
        if yarisi(yol, 1.0, BAZ[1])[0] == "stop":
            pisman20[yarisi(yol, 1.5, BAZ[1])[0]] += 1
    t20 = sum(pisman20.values()) or 1
    pd.DataFrame([{
        "durum": "S=1.0_stop_yiyenler_S=1.5_altinda_UFUK20",
        "n": t20,
        "hedefe_varan_yuzde": round(100 * pisman20["hedef"] / t20, 2),
        "yine_stop_yuzde": round(100 * pisman20["stop"] / t20, 2),
        "yok_yuzde": round(100 * pisman20["yok"] / t20, 2),
    }]).to_csv(CIKTI_KOK / "dar_stop_pismanligi_ufuk20.csv", index=False)

    # --- 9) Maliyet duyarlılığı (varsayımsal tur-başı maliyet, ATR) ----------
    maliyet_satirlari = []
    for hücre in grid:
        for maliyet in (0.0, 0.05, 0.10, 0.20):
            maliyet_satirlari.append({
                "ufuk": hücre["ufuk"], "stop_atr": hücre["stop_atr"],
                "hedef_atr": hücre["hedef_atr"],
                "maliyet_atr": maliyet,
                "net_beklenti_atr": round(hücre["beklenti_atr"] - maliyet, 4),
                "net_pozitif": hücre["beklenti_atr"] - maliyet > 0,
            })
    pd.DataFrame(maliyet_satirlari).to_csv(CIKTI_KOK / "maliyet_duyarlilik.csv", index=False)

    # --- Sermaye koruma simülasyonu (baz hücre, örtüşmesiz sıra) -------------
    print("6) Sermaye simülasyonu…")
    stop_b, hedef_b, ufuk_b = BAZ
    sim_satirlari = []
    toplam = {"kural_yok": 0.0, "kural_var": 0.0}
    gunluk_sayimlar = []
    for (sembol, tf), liste in grup.items():
        liste.sort(key=lambda x: x["confirm_idx"])
        secili, son = [], -10**9
        for k in liste:
            if k["confirm_idx"] >= son + PENCERE:
                secili.append(k)
                son = k["confirm_idx"]
        if not secili:
            continue
        sonuclar = []
        for k in secili:
            sonuc, _ = yarisi(k["yol"][:ufuk_b], stop_b, hedef_b)
            sonuclar.append((k, sonuc))
        pnl = {"hedef": hedef_b, "stop": -stop_b, "yok": 0.0}
        # kural yok
        seri = [pnl[s] for _, s in sonuclar]
        # kural var: aynı takvim gününde 2. stop'tan sonra o günün işlemleri durur
        gun_sayaci: dict[str, int] = defaultdict(int)
        seri_kural, duran = [], 0
        for k, s in sonuclar:
            gun = str(pd.Timestamp(k["confirm_time"]).date())
            if gun_sayaci[gun] >= 2 and s != "hedef":
                duran += 1
                continue
            seri_kural.append(pnl[s])
            if s == "stop":
                gun_sayaci[gun] += 1
        # metrikler
        def metrikler(seri: list[float]) -> dict:
            if not seri:
                return {"toplam_atr": 0.0, "maks_dusus_atr": 0.0, "maks_ust_uste_stop": 0}
            eq = np.cumsum(seri)
            doruk = np.maximum.accumulate(np.concatenate([[0.0], eq]))
            dusus = float((doruk[1:] - eq).max()) if len(eq) else 0.0
            en_ust, cur = 0, 0
            for s in seri:
                cur = cur + 1 if s < 0 else 0
                en_ust = max(en_ust, cur)
            return {"toplam_atr": round(float(sum(seri)), 3),
                    "maks_dusus_atr": round(dusus, 3),
                    "maks_ust_uste_stop": en_ust}
        m0, m1 = metrikler(seri), metrikler(seri_kural)
        # gün içi stop yoğunluğu
        gun_stop = defaultdict(int)
        for k, s in sonuclar:
            if s == "stop":
                gun_stop[str(pd.Timestamp(k["confirm_time"]).date())] += 1
        gunluk_sayimlar.extend(gun_stop.values())
        sim_satirlari.append({
            "symbol": sembol, "tf": tf, "islem": len(seri),
            "kural_yok_toplam_atr": m0["toplam_atr"],
            "kural_yok_maks_dusus_atr": m0["maks_dusus_atr"],
            "kural_yok_maks_ust_uste_stop": m0["maks_ust_uste_stop"],
            "kural_var_toplam_atr": m1["toplam_atr"],
            "kural_var_maks_dusus_atr": m1["maks_dusus_atr"],
            "kural_var_maks_ust_uste_stop": m1["maks_ust_uste_stop"],
            "duran_islem": duran,
        })
        toplam["kural_yok"] += m0["toplam_atr"]
        toplam["kural_var"] += m1["toplam_atr"]
    sim_df = pd.DataFrame(sim_satirlari)
    sim_df.to_csv(CIKTI_KOK / "sermaye_sim.csv", index=False)

    # --- 10) Seri kuralı: sembol×TF'de 3 üst üste stop → sıradakini atla ------
    seri_kural_toplam, seri_duran, seri_ust_uste = 0.0, 0, []
    for (sembol, tf), liste in grup.items():
        liste.sort(key=lambda x: x["confirm_idx"])
        secili, son = [], -10**9
        for k in liste:
            if k["confirm_idx"] >= son + PENCERE:
                secili.append(k)
                son = k["confirm_idx"]
        pnl = {"hedef": BAZ[1], "stop": -BAZ[0], "yok": 0.0}
        ust_ham, ust_kural, enbuyuk = 0, 0, 0
        for k in secili:
            s, _ = yarisi(k["yol"][:BAZ[2]], BAZ[0], BAZ[1])
            # kural-dışı seri (raporlama için)
            ust_ham = ust_ham + 1 if s == "stop" else 0
            enbuyuk = max(enbuyuk, ust_ham)
            # kural: 3 üst üste stoptan sonra sıradaki işlemi atla
            if ust_kural >= 3:
                seri_duran += 1
                ust_kural = 0
                continue
            seri_kural_toplam += pnl[s]
            ust_kural = ust_kural + 1 if s == "stop" else 0
        if enbuyuk:
            seri_ust_uste.append(enbuyuk)
    seri_arr = np.array(seri_ust_uste) if seri_ust_uste else np.array([0])
    seri_ozet = {
        "kural": "sembol×TF'de 3 üst üste stop → sıradaki işlem atlanır",
        "toplam_atr_kural_var": round(seri_kural_toplam, 3),
        "toplam_atr_kural_yok": round(float(toplam["kural_yok"]), 3),
        "duran_islem": seri_duran,
        "streak_3plus_seri_orani_yuzde": round(100 * float((seri_arr >= 3).mean()), 2),
        "streak_5plus_seri_orani_yuzde": round(100 * float((seri_arr >= 5).mean()), 2),
        "streak_maks": int(seri_arr.max()),
    }
    (CIKTI_KOK / "seri_kural_ozet.json").write_text(
        json.dumps(seri_ozet, ensure_ascii=False, indent=2), encoding="utf-8")

    gun_arr = np.array(gunluk_sayimlar) if gunluk_sayimlar else np.array([0])
    sermaye_ozet = {
        "baz_hucre": {"stop_atr": stop_b, "hedef_atr": hedef_b, "ufuk": ufuk_b},
        "sembol_tf_sayisi": len(sim_df),
        "toplam_islem_kural_yok": int(sim_df["islem"].sum()),
        "toplam_atr_kural_yok": round(float(toplam["kural_yok"]), 3),
        "toplam_atr_kural_var": round(float(toplam["kural_var"]), 3),
        "kural_etkisi_atr": round(float(toplam["kural_var"] - toplam["kural_yok"]), 3),
        "duran_islem_toplam": int(sim_df["duran_islem"].sum()),
        "gunluk_stop_max": int(gun_arr.max()),
        "gunluk_stop_2plus_pay_yuzde": round(100 * float((gun_arr >= 2).mean()), 2),
        "gunluk_stop_3plus_pay_yuzde": round(100 * float((gun_arr >= 3).mean()), 2),
        "maks_ust_uste_stop_medyan": float(sim_df["kural_yok_maks_ust_uste_stop"].median()),
        "maks_ust_uste_stop_maks": int(sim_df["kural_yok_maks_ust_uste_stop"].max()),
        "maks_dusus_atr_medyan": float(sim_df["kural_yok_maks_dusus_atr"].median()),
        "maks_dusus_atr_maks": float(sim_df["kural_yok_maks_dusus_atr"].max()),
    }
    (CIKTI_KOK / "sermaye_ozet.json").write_text(
        json.dumps(sermaye_ozet, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- manifest ------------------------------------------------------------
    manifest = {
        "girdi": str(GIRDI.relative_to(KOK)),
        "girdi_sha256": sha256(GIRDI),
        "arsiv_kok": "backfill_data/",
        "ham_olay": ham_n,
        "gecerli_yol": len(kayitlar),
        "ortusesiz_secim": len(secim),
        "eslesmeyen": eslesmeyen,
        "sansurlu": sansurlu,
        "kovalar": {"stop": STOP_KOVALARI, "hedef": HEDEF_KOVALARI, "ufuk": UFUKLAR},
        "baz_hucre": {"stop_atr": BAZ[0], "hedef_atr": BAZ[1], "ufuk": BAZ[2]},
        "kural": "aynı barda çift dokunuş → stop (muhafazakâr); yalnız ileri barlar; "
                 "eksik pencere sansür, sonuç sayılmaz",
        "girdi_period_degerleri": sorted(df["period"].dropna().unique().tolist()),
    }
    (CIKTI_KOK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Bitti → {CIKTI_KOK}")
    print(json.dumps(sermaye_ozet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
