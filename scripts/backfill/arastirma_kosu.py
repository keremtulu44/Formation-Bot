#!/usr/bin/env python3
"""Arşiv üzerinde ölçüm koşusu ve rapor üretimi.

Kullanım:

    # Küçük pilot (hızlı doğrulama)
    python scripts/backfill/arastirma_kosu.py --limit 3

    # Tam koşu (177 sembol x 4 zaman dilimi), arka planda
    python scripts/backfill/arastirma_kosu.py

    # Yalnız rapor (yeni ölçüm yapmadan, mevcut çıktıdan)
    python scripts/backfill/arastirma_kosu.py --agrega

Tasarım kararları:

**JSONL'e sembol bazında ekleme.** Koşu ~1 saat sürebilir; tek seferde bellekte
toplamak çökme halinde her şeyi kaybettirir. Her sembol bittiğinde satırlar
``arastirma_cikti/<kategori>.jsonl`` dosyasına eklenir ve dosya kapatılır.

**Idempotent devam.** ``meta.jsonl`` içinde kaydı olan ``(symbol, timeframe)``
çiftleri atlanır. Koşu yarıda kesilirse aynı komut kaldığı yerden devam eder;
``--zorla`` verilirse mevcut çıktı silinip baştan koşulur.

**Sembol bazında izole hata.** Bir sembol patlarsa koşu durmaz; hata
``hatalar.jsonl`` dosyasına yazılır ve diğer semboller devam eder. Sessiz
kısmi başarı yerine rapor sonunda hata sayısı açıkça gösterilir.

**BRENT havuz dışı.** BIST seans yapısı taşımadığı için varsayılan olarak
koşuya alınmaz; ``--havuz-disi-dahil`` ile dahil edilebilir.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

KATEGORILER = ("zone", "dokunus", "swing", "event", "frm", "frm_olay", "meta")
VARSAYILAN_CIKTI = "arastirma_cikti"
VARSAYILAN_RAPOR = "docs/arastirma/ARASTIRMA_BULGULARI.md"


def _repo_koku() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _json_serializable(deger: Any) -> Any:
    """pandas/numpy tiplerini JSON'a çevirir; bilinmeyen tip -> ``str``."""
    import math

    import pandas as pd

    if deger is None or isinstance(deger, (str, bool, int)):
        return deger
    if isinstance(deger, float):
        return deger if math.isfinite(deger) else None
    if isinstance(deger, (pd.Timestamp,)):
        return str(deger)
    if hasattr(deger, "item"):
        try:
            ic = deger.item()
            return ic if not isinstance(ic, float) or math.isfinite(ic) else None
        except (ValueError, TypeError):
            return str(deger)
    return str(deger)


def _ekle(yol: Path, satirlar: Iterable[dict[str, Any]]) -> int:
    """Satırları JSONL dosyasına ekler; kaç satır yazıldığını döndürür."""
    satirlar = list(satirlar)
    if not satirlar:
        return 0
    yol.parent.mkdir(parents=True, exist_ok=True)
    with yol.open("a", encoding="utf-8") as dosya:
        for satir in satirlar:
            temiz = {k: _json_serializable(v) for k, v in satir.items()}
            dosya.write(json.dumps(temiz, ensure_ascii=False) + "\n")
    return len(satirlar)


#: Raporun gerçekten kullandığı kolonlar. JSONL satırları geniştir (dokunuş
#: 124 kolon) ve JSON her satırda tüm anahtar adlarını tekrarladığı için
#: dokunus.jsonl tek başına 937 MB olur. Tamamını dict listesi olarak
#: belleğe almak ~4 GB'lık makinede OOM üretir (gerçekleşti: agregasyon
#: 187.046 zone satırını yükledikten sonra SIGKILL ile öldü). Kolonları
#: önceden kısıtlamak tepe belleği ~2 GB'dan onlarca MB'a indirir.
RAPOR_KOLONLARI: dict[str, tuple[str, ...] | None] = {
    "zone": (
        "symbol", "timeframe", "family", "zone_id", "direction",
        "temas_var", "temas_bar_sayisi", "native_price_violation",
        "native_full_fill", "native_terminal_category", "sansur",
        "omur_bar", "yukseklik_atr", "yukseklik_kovasi", "config_hash",
    ),
    "dokunus": (
        "symbol", "timeframe", "family", "zone_id", "direction", "dokunus_no",
        "arrival_side", "dokunulan_kenar", "kenar_olcum_yonu",
        "yukseklik_atr", "yukseklik_kovasi", "atr_at_touch",
        "yon_tepki_sinifi", "kenar_tepki_sinifi",
        "yon_h10", "yon_h12", "yon_tepe_atr", "yon_tepe_bar",
        "yon_pay_1", "yon_pay_3", "yon_pay_5", "yon_h12_decay",
        "yon_uzun_tepe_atr", "yon_uzun_tepe_bar", "yon_uzun_decay",
        "kenar_h12", "kenar_tepe_atr", "kenar_pay_5", "kenar_h12_decay",
        "kenar_uzun_tepe_atr",
        "yon_asim_025", "yon_asim_050", "yon_asim_100", "yon_asim_150", "yon_asim_200",
        "kenar_asim_025", "kenar_asim_050", "kenar_asim_100", "kenar_asim_150", "kenar_asim_200",
        "sansur_pencere", "sansur_terminal", "vp_rvol", "vp_volume_usable",
        "vp_data_ready", "vp_effort_result_class", "config_hash",
    ),
    "swing": (
        "symbol", "timeframe", "scope", "identity", "rol", "side", "rol_uci",
        "structural_role_final", "rol_ilk_bar", "rol_sure_bar", "rol_kapanis",
        "price", "broken", "broken_bar", "bars_to_break",
        "bars_to_break_from_rol", "deneme_epizot_025", "deneme_epizot_015",
        "deneme_epizot_050", "deneme_bar_025", "engelledi_025",
        "engelledi_015", "engelledi_050", "kirilim_bar", "max_yaklasma_atr",
        "sansur", "gecildi", "vp_rvol", "vp_volume_usable", "config_hash",
    ),
    "event": (
        "symbol", "timeframe", "scope", "event_uid", "event_type", "direction",
        "devamlilik_sinifi", "uyum", "devam_h12", "devam_tepe_atr",
        "devam_pay_5", "ters_h12", "onay_gecikmesi_bar", "outcome",
        "validity", "relevance", "bos_maturity", "quality", "age_bars",
        "sansur", "vp_rvol", "vp_volume_usable", "vp_effort_result_class",
        "config_hash",
    ),
    "frm": (
        "symbol", "timeframe", "stable_id", "pattern_type", "family", "classic_dir",
        "dogum_bar_time", "omur_bar", "terminal_state", "acik", "terminal_mi",
        "kirilim_var", "frm_yakinlik_ust_fitil_atr", "frm_yakinlik_alt_fitil_atr",
        "frm_yakinlik_ust_kapanis_atr", "frm_yakinlik_alt_kapanis_atr",
        "frm_asim_ust_fitil_atr", "frm_asim_alt_fitil_atr",
        "frm_temas_ust_epizot", "frm_temas_alt_epizot",
        "frm_faz_geometri_bar", "frm_faz_kirilim_bar", "frm_faz_retest_bar",
        "frm_faz_gecis_sayisi", "frm_kirilim_deneme", "frm_teyit_deneme_no",
        "frm_kirilim_deneme_var", "upper_touches_son", "lower_touches_son",
        "frm_pivot_temas_max", "frm_pivot_ezilme_var",
        "break_snapshot_bar", "break_snapshot_price", "break_snapshot_direction",
        "break_strength", "break_volume_score", "break_confirmation_strength",
        "break_gecikme_bar", "retest_var", "retest_gecikme_bar", "retest_derinlik_atr",
        "frm_teyit_sonrasi_mfe_atr", "frm_teyit_sonrasi_mfe_uzun_atr",
        "frm_teyit_sonrasi_mae_atr", "frm_dogum_ph_atr", "frm_dogum_pl_atr",
        "frm_dogum_rol_ucu", "frm_kirilim_ms_uyum", "frm_kirilim_zone_var",
        "frm_kirilim_ob_var", "frm_kirilim_fvg_var", "frm_gecersiz_state",
        "frm_vp_rvol_dogum", "frm_vp_rvol_olgunlasma", "frm_vp_rvol_teyit",
        "frm_vp_rvol_retest", "config_hash",
    ),
    "frm_olay": (
        "symbol", "timeframe", "stable_id", "olay_type", "olay_name",
        "direction", "quality", "fiyat", "bar", "bar_time", "state", "teyit_oncesi",
    ),
    "meta": None,  # küçük; tüm kolonlar
}


def _df_optimize(df: "pd.DataFrame") -> "pd.DataFrame":
    """Nesne kolonlarını sayısal/kategorik tipe indirger (bellek için kritik).

    ``symbol``/``timeframe``/``family`` gibi kolonlar yüz binlerce satırda
    aynı birkaç değeri tekrarlar; ``object`` dtype her satırda ayrı Python
    nesnesi tutar, ``category`` ise tek bir sözlük tutar.
    """
    import pandas as pd

    for kolon in df.columns:
        # Metin kolonu iki tipte gelebilir: pandas < 3'te `object`, pandas 3'te
        # `str`/`StringDtype`. Yalnız `object`e bakmak pandas 3'te hiçbir kolonu
        # indirgemiyordu (200 bin satırlık raporda bellek şişmesi).
        if not (pd.api.types.is_object_dtype(df[kolon])
                or pd.api.types.is_string_dtype(df[kolon])):
            continue
        sayisal = pd.to_numeric(df[kolon], errors="coerce")
        bosluk = df[kolon].isna().sum()
        if sayisal.notna().sum() > 0 and int(sayisal.isna().sum()) == int(bosluk):
            df[kolon] = sayisal.astype("float64")
        else:
            df[kolon] = df[kolon].astype("category")
    return df


def _jsonl_oku_df(yol: Path, kolonlar: tuple[str, ...] | None = None, chunk: int = 25000) -> "pd.DataFrame":
    """JSONL'i parça parça akıtır; hiçbir anında tamamı bellekte değildir.

    Her parça ayrı DataFrame olur, tipleri indirgenir ve sonra birleştirilir.
    Böylece tepe bellek ``satır_sayısı x tüm_kolonlar`` yerine
    ``chunk x seçili_kolonlar`` mertebesinde kalır.
    """
    import pandas as pd

    if not yol.exists():
        return pd.DataFrame()
    parcalar: list[Any] = []
    tampon: list[dict[str, Any]] = []
    with yol.open("r", encoding="utf-8") as dosya:
        for satir in dosya:
            satir = satir.strip()
            if not satir:
                continue
            try:
                kayit = json.loads(satir)
            except json.JSONDecodeError:
                continue
            if kolonlar is not None:
                kayit = {k: kayit.get(k) for k in kolonlar}
            tampon.append(kayit)
            if len(tampon) >= chunk:
                parcalar.append(_df_optimize(pd.DataFrame(tampon)))
                tampon = []
    if tampon:
        parcalar.append(_df_optimize(pd.DataFrame(tampon)))
    if not parcalar:
        return pd.DataFrame()
    return pd.concat(parcalar, ignore_index=True)


def _jsonl_oku(yol: Path) -> list[dict[str, Any]]:
    if not yol.exists():
        return []
    kayitlar: list[dict[str, Any]] = []
    with yol.open("r", encoding="utf-8") as dosya:
        for satir in dosya:
            satir = satir.strip()
            if not satir:
                continue
            try:
                kayitlar.append(json.loads(satir))
            except json.JSONDecodeError:
                # Yarım kalmış son satır (çökme anı) atlanır; dosyanın gerisi
                # geçerlidir. Bu tolerans olmadan devam etmek imkânsız olurdu.
                continue
    return kayitlar


def _tamamlananlar(cikti: Path) -> set[tuple[str, str]]:
    """``meta.jsonl`` kayıtlarından bitmiş (symbol, timeframe) çiftleri."""
    return {(r.get("symbol"), r.get("timeframe")) for r in _jsonl_oku(cikti / "meta.jsonl")}


def _kilit_yolu(cikti: Path) -> Path:
    """Kilit dosyası çıktı dizininin KARDEŞİDİR.

    Sebep: ``--zorla`` çıktı dizinini ``rmtree`` ile siler. Kilit içeride
    olsaydı silinir ve koruma ortadan kalkardı.
    """
    return cikti.parent / f".{cikti.name}.kilit"


def _pid_yasamda(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import os

        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class _Kilit:
    """Tek örnek kilidi: aynı çıktı dizinine eşzamanlı iki koşuyu engeller.

    Bu koruma gerçek bir olaydan sonra eklendi. Bir koşu ``stop_process`` ile
    durdurulmuş *göründü* ama süreç hayatta kaldı ve düzeltilmiş ikinci koşu
    başlatıldı; iki süreç aynı JSONL dosyalarına ekledi. Sonuç: 704 işin
    501'i çift yazıldı ve çiftlerin yarısı düzeltilmemiş kodun çıktısıydı.
    Agregasyon bunu fark etmedi çünkü satırlar tek tek geçerliydi.

    Kilit ``O_CREAT|O_EXCL`` ile atomik alınır; bayat kilit (sahibi ölmüş)
    otomatik devralınır.
    """

    def __init__(self, yol: Path) -> None:
        self.yol = yol
        self.alindi = False

    def __enter__(self) -> "_Kilit":
        import os

        self.yol.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(self.yol), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                with os.fdopen(fd, "w", encoding="utf-8") as dosya:
                    dosya.write(str(os.getpid()))
                self.alindi = True
                return self
            except FileExistsError:
                sahip = 0
                try:
                    sahip = int(self.yol.read_text(encoding="utf-8").strip() or 0)
                except (OSError, ValueError):
                    sahip = 0
                if sahip and sahip != os.getpid() and _pid_yasamda(sahip):
                    raise SystemExit(
                        f"BAŞKA BİR KOŞU ZATEN ÇALIŞIYOR (pid {sahip}).\n"
                        f"  kilit: {self.yol}\n"
                        f"  İki eşzamanlı koşu aynı JSONL dosyalarına ekler ve\n"
                        f"  satırları çift sayar. Bitmesini bekleyin ya da o süreci\n"
                        f"  gerçekten öldürdüğünüzü doğrulayın (pgrep -f arastirma_kosu).\n"
                        f"  Sahip öldüyse kilidi elle silin: rm {self.yol}"
                    )
                # Bayat kilit: sahibi ölmüş, devral.
                try:
                    self.yol.unlink()
                except OSError:
                    pass
        raise SystemExit(f"kilit alınamadı: {self.yol}")

    def __exit__(self, *exc: Any) -> None:
        if self.alindi:
            try:
                self.yol.unlink()
            except OSError:
                pass


def _koşu_planı(args: argparse.Namespace) -> list[str]:
    from research import arsiv

    if args.semboller:
        return [s.strip().upper() for s in args.semboller.split(",") if s.strip()]
    semboller = arsiv.arsiv_sembolleri()
    if not args.havuz_disi_dahil:
        semboller = [s for s in semboller if s not in arsiv.HAVUZ_DISI_SEMBOLLER]
    if args.limit:
        semboller = semboller[: args.limit]
    return semboller


def kosu(args: argparse.Namespace) -> int:
    """Ölçüm koşusunu yürütür. Süreç çıkış kodu olarak hata sayısını döndürür."""
    sys.path.insert(0, str(_repo_koku()))
    from research import arsiv, kayit

    cikti = Path(args.cikti)
    # Kilit her şeyden önce alınır. `--zorla` çıktı dizinini siler ama kilit
    # dosyası kardeş konumda olduğu için bu sıralama korumayı bozmaz.
    with _Kilit(_kilit_yolu(cikti)):
        return _kosu_govdesi(args, cikti)


def _kosu_govdesi(args: argparse.Namespace, cikti: Path) -> int:
    from research import arsiv, kayit

    if args.zorla and cikti.exists():
        import shutil

        shutil.rmtree(cikti)
    cikti.mkdir(parents=True, exist_ok=True)

    timeframeler = [t.strip().lower() for t in args.timeframe.split(",") if t.strip()]
    semboller = _koşu_planı(args)
    tamamlanan = set() if args.zorla else _tamamlananlar(cikti)

    plan = [(s, tf) for s in semboller for tf in timeframeler if (s, tf) not in tamamlanan]
    atlanan = len(semboller) * len(timeframeler) - len(plan)
    print(
        f"[plan] {len(semboller)} sembol x {len(timeframeler)} tf = {len(plan)} is"
        f" · atlanan (tamamlanmis): {atlanan}",
        flush=True,
    )

    baslangic = time.time()
    hata_sayisi = 0
    for i, (sembol, tf) in enumerate(plan, 1):
        t0 = time.time()
        try:
            frame = arsiv.tf_frame(sembol, tf)
            gozlem = kayit.sembol_timeframe_gozlem(sembol, tf, frame)
            for kategori in KATEGORILER:
                _ekle(cikti / f"{kategori}.jsonl", gozlem.get(kategori, []))
            sure = time.time() - t0
            m = (gozlem.get("meta") or [{}])[0]
            print(f"[{i}/{len(plan)}] {sembol:8} {tf:3} {sure:6.1f}s "
                  f"bar={m.get('bar_sayisi')} zone={m.get('zone_sayisi')} "
                  f"epizot={m.get('epizot_sayisi')} swing={m.get('swing_sayisi')} "
                  f"event={m.get('event_sayisi')} rol={m.get('rol_araligi_sayisi')} "
                  f"frm={m.get('formasyon_sayisi')}", flush=True)
        except Exception as exc:  # noqa: BLE001 - sembol bazında izolasyon
            hata_sayisi += 1
            _ekle(cikti / "hatalar.jsonl", [{
                "symbol": sembol,
                "timeframe": tf,
                "hata": f"{type(exc).__name__}: {exc}",
                "iz": traceback.format_exc(limit=6),
            }])
            print(f"[{i}/{len(plan)}] {sembol:8} {tf:3} HATA: {type(exc).__name__}: {exc}", flush=True)
        finally:
            # Önbellek her sembolde şişer; 1h çerçeveleri 3000+ bar ve
            # VP metrics_history ile birlikte yüzlerce MB'a ulaşabilir.
            arsiv._OBELLEK.clear()

    gecen = time.time() - baslangic
    print(f"\n[bitti] {len(plan)} iş, {gecen:.0f}s, hata={hata_sayisi}", flush=True)
    if hata_sayisi:
        print(f"  hatalar: {cikti / 'hatalar.jsonl'}", flush=True)
    if not args.rapor_atla:
        rapor_args = argparse.Namespace(**{**vars(args), "agrega": True})
        return agregasyon(rapor_args) or hata_sayisi
    return hata_sayisi


def agregasyon(args: argparse.Namespace) -> int:
    """JSONL çıktısını tablolara çevirip Markdown raporu üretir."""
    sys.path.insert(0, str(_repo_koku()))
    import pandas as pd

    from research import arsiv, rapor

    cikti = Path(args.cikti)
    tablolar: dict[str, pd.DataFrame] = {}
    for kategori in KATEGORILER:
        df = _jsonl_oku_df(cikti / f"{kategori}.jsonl", RAPOR_KOLONLARI.get(kategori))
        tablolar[kategori] = df
        print(f"[agrega] {kategori}: {len(df)} satır, {len(df.columns)} kolon", flush=True)

    # ÇİFT KAYIT BEKÇİSİ. meta.jsonl bir koşuda her (symbol, timeframe) için
    # tam bir satır üretir; yinelenme ancak iki sürecin aynı dosyaya eklemesi
    # ile olur. Bu, her satırı tek tek geçerli olduğu için başka hiçbir
    # kontrolün yakalamadığı bir kirlenmedir ve yüzdeleri sessizce bozar
    # (aynı gözlem iki kez sayılır). Rapor üretmek yerine durdurmak doğrudur.
    meta_df = tablolar.get("meta")
    if meta_df is not None and len(meta_df) and {"symbol", "timeframe"}.issubset(meta_df.columns):
        yinelenen = int(meta_df.duplicated(subset=["symbol", "timeframe"]).sum())
        if yinelenen:
            ornekler = (
                meta_df[meta_df.duplicated(subset=["symbol", "timeframe"], keep=False)]
                .groupby(["symbol", "timeframe"], observed=True).size().sort_values(ascending=False).head(5)
            )
            raise SystemExit(
                f"ÇİFT KAYIT: meta.jsonl içinde {yinelenen} yinelenen (symbol, timeframe) var.\n"
                f"  Bu, aynı çıktı dizinine eşzamanlı iki koşunun eklemesiyle olur ve\n"
                f"  rapor yüzdelerini sessizce bozar (gözlemler iki kez sayılır).\n"
                f"  En çok yinelenenler:\n{ornekler.to_string()}\n"
                f"  Çözüm: pgrep -f arastirma_kosu ile süreç kalmadığını doğrulayın,\n"
                f"  sonra temiz koşun: python scripts/backfill/arastirma_kosu.py --zorla"
            )

    hatalar = _jsonl_oku(cikti / "hatalar.jsonl")

    # Havuz dışı semboller raporun kendisinde ayrıca işaretlenir; ölçülmüşlerse
    # havuz istatistiğinden çıkarılır.
    havuz_disi = list(arsiv.HAVUZ_DISI_SEMBOLLER)
    if not args.havuz_disi_dahil:
        for kategori, df in list(tablolar.items()):
            if len(df) and "symbol" in df.columns:
                tablolar[kategori] = df[~df["symbol"].isin(havuz_disi)].reset_index(drop=True)

    meta = tablolar.get("meta")
    sembol_sayisi = int(meta["symbol"].nunique()) if meta is not None and len(meta) and "symbol" in meta.columns else 0

    notlar = [
        "Ölçüm birimi **çapa sonrası** barlardır; çapa barının kendisi hiçbir uzanıma katılmaz (anti-lookahead).",
        "Tüm uzanımlar **ATR cinsindendir**; TL/% kullanılmaz çünkü BIST 5-500 TL aralığında hisse barındırır.",
        "`sansur` alanı pencerenin veri sonuna takıldığını gösterir; sansürlü gözlem başarı sayılmaz.",
        "OB popülasyonu `replay_ob_zones` ile yeniden kurulur: motor dolan zone'ları listesinden sildiği için final snapshot yalnız hayatta kalanları verir.",
        "PH/PL/WH/WL rolleri bar bar izlenir: `structural_role` zamanla mutate olur ve final değer tarihsel atamaları kaybetmiştir.",
        "`TUM_ZONE`/`ZONE_ICI` temaslarında kenar-ancored yön belirlenemez; bunlar `OLCULEMEDI` kovasında ayrı raporlanır, düşürülmez.",
        "Güven etiketi: n>=30 YETERLI, n>=15 KISMI, altı ZAYIF (`analytics/backtest.py` ile aynı eşikler).",
    ]
    if hatalar:
        notlar.append(f"**{len(hatalar)} sembol x zaman dilimi hatayla atlandı** (`hatalar.jsonl`); rapor kalan veriyi yansıtır.")

    metin = rapor.rapor_uret(
        tablolar,
        sembol_sayisi=sembol_sayisi,
        havuz_disi=havuz_disi,
        notlar=notlar,
    )

    rapor_yolu = Path(args.rapor)
    rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
    rapor_yolu.write_text(metin, encoding="utf-8")
    print(f"[agrega] rapor yazıldı: {rapor_yolu} ({len(metin)} karakter, {sembol_sayisi} sembol)", flush=True)

    # Formasyon cevap kartları ayrı belgeye yazılır: ana rapor tablo eki,
    # formasyon raporu ise soru-cevap formatında okunabilir çıktıdır.
    frm_yolu = Path(getattr(args, "frm_rapor", "") or (rapor_yolu.parent / "FORMASYON_SONUCLARI.md"))
    if (cikti / "frm.jsonl").exists():
        try:
            from research import formasyon_rapor
            frm_metin = formasyon_rapor.rapor_uret(cikti, frm_yolu)
            print(f"[agrega] formasyon raporu: {frm_yolu} ({len(frm_metin)} karakter)", flush=True)
        except Exception as exc:  # noqa: BLE001 - ana raporu düşürmesin
            print(f"[agrega] formasyon raporu ÜRETİLEMEDİ: {type(exc).__name__}: {exc}", flush=True)

    # Ham JSONL zaten kalıcı depodur. Ek CSV.gz yazımı varsayılan olarak
    # KAPALIDIR: 994 bin satırı tek DataFrame olarak CSV'ye basmak belleği
    # zorlar ve JSONL'in birebir kopyasını üretir. Yalnız gerçekten
    # gerektiğinde `--csv-yaz` ile açılır.
    if getattr(args, "csv_yaz", False):
        for kategori in KATEGORILER:
            df = tablolar.get(kategori)
            if df is None or len(df) == 0:
                continue
            hedef = cikti / f"{kategori}.csv.gz"
            df.to_csv(hedef, index=False, compression="gzip")
            print(f"[agrega] {hedef} ({len(df)} satır)", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Formation-Bot arşiv araştırma koşusu")
    parser.add_argument("--limit", type=int, default=0, help="kaç sembol (0 = hepsi)")
    parser.add_argument("--semboller", type=str, default="", help="virgülle sembol listesi")
    parser.add_argument("--timeframe", type=str, default="1h,2h,4h,1d", help="virgülle zaman dilimleri")
    parser.add_argument("--cikti", type=str, default=VARSAYILAN_CIKTI, help="JSONL çıktı dizini")
    parser.add_argument("--rapor", type=str, default=VARSAYILAN_RAPOR, help="Markdown rapor yolu")
    parser.add_argument("--agrega", action="store_true", help="ölçüm yapma, mevcut çıktıdan rapor üret")
    parser.add_argument("--zorla", action="store_true", help="mevcut çıktıyı silip baştan koş")
    parser.add_argument("--rapor-atla", action="store_true", help="koşu sonunda rapor üretme")
    parser.add_argument("--frm-rapor", type=str, default="",
                        help="formasyon cevap kartlarının yolu (varsayılan: ana raporun yanında "
                             "FORMASYON_SONUCLARI.md)")
    parser.add_argument(
        "--csv-yaz",
        action="store_true",
        help="agregasyonda ek CSV.gz üret (varsayılan kapalı: JSONL zaten kalıcı "
             "depodur ve ~1M satırı CSV'ye basmak belleği zorlar)",
    )
    parser.add_argument("--havuz-disi-dahil", action="store_true", help="BRENT gibi havuz dışı sembolleri dahil et")
    args = parser.parse_args(argv)

    if args.agrega:
        return agregasyon(args)
    return kosu(args)


if __name__ == "__main__":
    raise SystemExit(main())
