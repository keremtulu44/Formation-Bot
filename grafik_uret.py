# -*- coding: utf-8 -*-
"""Grafik CLI'ı — gerçek önbellekten tek kare üretir (G1 doğrulama aracı).

Neden ayrı betik: bot'un çizim yolu motoru YENİDEN ÇALIŞTIRMAZ (§14.2) ve kareyi
kaynağında denetlemek gerekir. Bu araç aynı zinciri kurar: önbellek →
`data.resample_ohlcv` → `grafik.anlik_goruntu` → `grafik.ciz`. Formasyon
kaydı `--formasyon` ile verilmezse kare mumlarla çizilir ve `uyarilar` bunu yazar
(uydurma formasyon çizilmez).

Örnekler:
    python grafik_uret.py --hisse AKBNK --tf 1h --mum 180 --cikti /tmp/a.png
    python grafik_uret.py --hisse THYAO --tum-tf --json
    python grafik_uret.py --hisse AKBNK --tf 1d --demo --mum 180
    python grafik_uret.py --hisse ALARK --tf 4h --zone --formasyon-tara

`--formasyon-tara`: formasyonu botun canlı tarama motoru ve kullanılabilirlik
kapısıyla bulur (profil `config.PROFILE`). Bulunmazsa uydurma yapılmaz; kare
"tarama: … formasyon yok" uyarısıyla çizilir.

`--demo`: cache okumadan, ayrı render→PNG doğrulaması için (bu depo `bot_data/*_gunluk.json`
içermez) 500 barlık GüNLÜK çerçeveyi sentetik üretir. Neden `bot_data/` içine
dosya yazmıyoruz: o dizin canlı botun okuduğu önbellektir, sentetik veri oraya
karışırsa gerçek taramayı zehirler (§22'de kayıtlı sapma).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ISTANBUL_TZ = timezone(timedelta(hours=3))
TF_LISTESI = ("1h", "2h", "4h", "1d")


def _veri_dizini(secenek: str | None) -> str:
    import config

    # Aynı çözümleyici: Render varsayılanı ve göreli yol/cwd sözleşmesi ayrışmaz.
    if secenek:
        return config._resolve_app_path(secenek, secenek)
    return str(config.DATA_DIR)


class VeriYok(Exception):
    """Çizilecek çerçeve önbellekte yok.

    Neden ayrı tür: `/grafik` komutu bu durumu kullanıcıya „önbellekte veri yok"
    diye ANLATMAK zorunda (§4: canlı çekme YOK); CLI ise çıkış kodu ile düşmeli.
    Aynı okumayı iki yüzeyin ayrı ayrı yapmaması için tek yerde tanımlı.
    """


def cerceve_getir(hisse: str, tf: str, veri_dizin: str, demo: bool = False, *,
                  yonetici=None):
    """Önbellekten (veya demo) çerçeve: `(df, kaynak)`; yoksa `VeriYok` kaldırır.

    `1d` için `to_gunluk_dataframe` (derin, ~500 bar) denenir; yoksa 1s
    önbelleğinden `resample_ohlcv` ile üretilir — ölçüm: 360 × 1s → ~44 bar,
    yani bu depo için günlük kadraj YÜZEYSEL kalır (§18.6).
    """
    from data import StockDequeManager, resample_ohlcv

    # Demo bilinçli ayrı yol: gerçek cache'i ne okur ne yazar.
    if demo:
        return _demo_cerceve(500 if tf == "1d" else 360), "demo (sentetik)"
    yonetici = yonetici if yonetici is not None else StockDequeManager(data_dir=veri_dizin)
    anahtar = hisse.upper().replace(".IS", "")   # önbellek adı: AKBNK.json
    def kaynak(gunluk=False):
        bellek = yonetici.gunluk_deques if gunluk else yonetici.deques
        dosya = anahtar + ("_gunluk.json" if gunluk else ".json")
        return (f"bellek/{'1d' if gunluk else '1h'} ({yonetici.data_dir})"
                if anahtar in bellek else yonetici._okuma_yolu(dosya))

    saatlik_kaynak, gunluk_kaynak = kaynak(), kaynak(True)
    if tf == "1d":
        df_1g = yonetici.to_gunluk_dataframe(anahtar)
        if df_1g is not None and len(df_1g) > 1:
            return df_1g.copy(deep=True), gunluk_kaynak
    df_1s = yonetici.to_dataframe(anahtar)
    if df_1s is None or len(df_1s) < 5:
        raise VeriYok(f"veri yok: {saatlik_kaynak} okunamadı veya yetersiz; "
                      "grafik için güvenli bağımsız canlı fetch yolu yok. "
                      "Botun mevcut veri yüklemesini kontrol edin.")
    df_1s = df_1s.copy(deep=True)
    if tf == "1h":
        return df_1s, saatlik_kaynak
    return resample_ohlcv(df_1s, tf), f"resample({tf}) ← {saatlik_kaynak}"


def _cerceve_yukle(hisse: str, tf: str, veri_dizin: str, demo: bool):
    """CLI uyumluluğu: `VeriYok` çıkış koduna dönüşür (testler bu adı çağırıyor)."""
    try:
        return cerceve_getir(hisse, tf, veri_dizin, demo)
    except VeriYok as hata:
        raise SystemExit(str(hata))


def _cikti_yolu(cikti: str | None, hisse: str, tf: str, tfler: tuple) -> str:
    """PNG yolu: birden çok TF çiziliyorsa ad zaman dilimiyle ayrışır."""
    yol = cikti or f"/tmp/grafik_{str(hisse).upper()}_{tf}.png"
    if len(tfler) > 1:
        return str(Path(yol).with_name(f"{Path(yol).stem}_{tf}.png"))
    return yol


def kare_uret(hisse: str, tf: str, *, veri_dizin: str | None = None, zone: bool = False,
              mum: int | None = None, serit: bool = True, etiket_detay: bool = False,
              formasyon_yol: str | None = None, formasyon: dict | None = None,
              formasyon_tara: bool = False,
              alarm_turu: str | None = None, cikti: str | None = None,
              demo: bool = False, yonetici=None, asama=None,
              tazelik_kontrol=None) -> dict:
    """Tek kare üretir: önbellek → (istersen domain motorları) → PNG.

    `main()` (CLI) ve `/grafik` komutu AYNI bu fonksiyonu çağırır — iki yüzeyin
    kadraj/motor/çizim davranışının ayrışmaması için (§14.2 kuralı burada da
    geçerli: motorlar ancak `zone=True` ile ve ÇERÇEVENİN KOPYASI üzerinde çalışır).

    Hata fırlatmaz: çerçeve yoksa `{"hata": "veri yok: ..."}`, çizim reddedilirse
    `yol=None` + `meta["uyarilar"]`. `veri_dizin` None → `config.DATA_DIR`; opsiyonel mevcut `yonetici`.
    """
    import grafik

    dizin = _veri_dizini(veri_dizin)
    if demo and cikti and "bot_data" in Path(cikti).expanduser().resolve().parts[:-1]:
        return {"tf": tf, "yol": None, "meta": {}, "kaynak": "demo (sentetik)",
                "hata": "sentetik çıktı bot_data içine yazılamaz"}
    try:
        if asama:
            asama("cache yükleme/resample")
        cerceve, kaynak = cerceve_getir(hisse, tf, dizin, demo, yonetici=yonetici)
        from data import tamamlanmis_mumlar
        if not demo:
            cerceve = tamamlanmis_mumlar(cerceve, tf).copy(deep=True)
        if cerceve is None or len(cerceve) < 2:
            raise VeriYok("veri yok: en az iki kapanmış mum gerekli")
        if tazelik_kontrol:
            tazelik_kontrol(cerceve, kaynak)
    except VeriYok as hata:
        return {"tf": tf, "yol": None, "meta": {}, "kaynak": "", "uyarilar": [],
                "hata": str(hata)}
    uyari: list[str] = []
    if formasyon is None:
        if formasyon_tara:
            formasyon, uyarilar = _formasyon_tara(cerceve)
        else:
            formasyon, uyarilar = _formasyon_yukle(formasyon_yol, cerceve)
        uyari += list(uyarilar)
    sonuclar = None
    if zone:
        if asama:
            asama("seçilen TF domain motorları")
        from domain_engines.runner import run_domain_engines

        sonuclar = run_domain_engines(str(hisse).upper().replace(".IS", ""), tf,
                                       cerceve.copy(deep=True))
    goruntu = grafik.anlik_goruntu(formasyon, tf, cerceve, sembol=str(hisse).upper(),
                                   alarm_turu=alarm_turu, sonuclar=sonuclar,
                                   kare_mum=mum, etiket_detay=etiket_detay)
    for u in uyari:
        goruntu["uyarilar"].append(u)
    if asama:
        asama("PNG çizimi (ortak çizim kilidi dahil)")
    yol, meta = grafik.ciz(goruntu, tf, secenekler={
        "cikti": cikti or f"/tmp/grafik_{str(hisse).upper()}_{tf}.png",
        "serit": serit,
        "etiket_detay": etiket_detay,
    })
    meta["kaynak"] = kaynak
    return {"tf": tf, "yol": yol, "meta": meta, "kaynak": kaynak,
            "uyarilar": list(meta.get("uyarilar") or []), "hata": None}


def _demo_cerceve(bar_sayisi: int):
    """Deterministik sentetik günlük çerçeve (yalnız CLI/sim; önbelleğe yazılmaz)."""
    import pandas as pd
    import random

    rastgele = random.Random(7)
    kapanislar: list[float] = []
    fiyat = 60.0
    gun = datetime(2025, 1, 2, 9, 30, tzinfo=ISTANBUL_TZ)
    zamanlar, satirlar = [], []
    acilis = fiyat
    for _ in range(bar_sayisi):
        while gun.weekday() > 4:
            gun += timedelta(days=1)
        dalga = 0.004 * (1 if (len(kapanislar) // 40) % 2 == 0 else -1)
        fiyat = max(1.0, fiyat * (1 + rastgele.gauss(dalga, 0.014)))
        yuksek = max(acilis, fiyat) * 1.007
        dusuk = min(acilis, fiyat) * 0.993
        satirlar.append({"open": round(acilis, 2), "high": round(yuksek, 2),
                         "low": round(dusuk, 2), "close": round(fiyat, 2),
                         "volume": float(1_000_000 + rastgele.randint(0, 4_000_000))})
        kapanislar.append(fiyat)
        zamanlar.append(gun)
        acilis = fiyat
        gun = gun + timedelta(days=1)
    df = pd.DataFrame(satirlar, index=pd.DatetimeIndex(zamanlar, name="timestamp"))
    return df


def _formasyon_tara(cerceve) -> tuple[Any, list[str]]:
    """Botun canlı taramasıyla AYNI motor ve AYNI kullanılabilirlik kapısı.

    Canlı yol `canli_tarama`/`main` → `PatternLifecycleManager.scan` →
    `ArgentEngine.process(df)`; kapı `patterns.detect._usable_active(snap,
    TRIANGLE_FAMILIES + SPECIALIZED_FAMILIES)`. Burada motor doğrudan kurulur:
    lifecycle'ın geçmiş defterine yazması CLI'da istenmez. Profil ve mintick
    botla aynıdır (`config.PROFILE`, varsayılan mintick 0,01). Çerçeve kopyalanır.
    Dönüş: `(PatternCandidate | None, uyarılar)`; formasyon yoksa uydurma yok.
    """
    from config import PROFILE
    from patterns.detect import SPECIALIZED_FAMILIES, TRIANGLE_FAMILIES, _usable_active
    from patterns.lifecycle import ArgentEngine

    snap = ArgentEngine(PROFILE, 0.01).process(cerceve.copy(deep=True))
    aday = _usable_active(snap, TRIANGLE_FAMILIES + SPECIALIZED_FAMILIES)
    if aday is None:
        return None, ["tarama: bu karede kullanılabilir formasyon yok (canlı tarama kapısı)"]
    return aday, []


def _formasyon_yukle(yol: str | None, cerceve) -> tuple[dict | None, list[str]]:
    """`--formasyon` JSON'unu okur; yoksa None + uyarı (sessiz kabahat yok)."""
    if not yol:
        return None, ["formasyon verisi verilmedi: bant/işaret çizilmedi"]
    dosya = Path(yol).expanduser()
    if not dosya.exists():
        return None, [f"formasyon dosyası yok: {dosya}"]
    try:
        kayit = json.loads(dosya.read_text(encoding="utf-8"))
    except (OSError, ValueError) as hata:
        return None, [f"formasyon dosyası okunamadı: {type(hata).__name__}"]
    n = len(cerceve)
    # JSON'da bar indeksi yoksa son kapanan muma sabitlenir: kart da alarm
    # bilgisini kapanan bardan okuyor, CLI'da uydurma indeks üretilmez.
    kayit.setdefault("end_bar", n - 1)
    return kayit, []


def main(giris: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ayristirici.add_argument("--hisse", required=True, help="Kod, örn. AKBNK (`.IS` eklenmez)")
    ayristirici.add_argument("--tf", default="1h", choices=TF_LISTESI, help="zaman dilimi")
    ayristirici.add_argument("--mum", type=int, default=None,
                             help=f"kadraj tavanı (varsayılan grafik.SABİTLER['kare_mum'])")
    ayristirici.add_argument("--cikti", default=None, help="PNG yolu (vars: /tmp/...)")
    ayristirici.add_argument("--veri-dizin", default=None, help="önbellek dizini (DATA_DIR)")
    ayristirici.add_argument("--formasyon", default=None,
                             help="kart payload'ı biçiminde JSON: bant/işaret/alarm verisi")
    ayristirici.add_argument("--formasyon-tara", action="store_true",
                             help="formasyonu botun canlı tarama motoru ve kapısıyla bul "
                                  "(--formasyon yerine; uydurma yok, bulunmazsa uyarı yazar)")
    ayristirici.add_argument("--alarm-turu", default=None,
                             choices=["aday", "kritik", "teyit", "retest", "gecersiz", "ihlal"])
    ayristirici.add_argument("--zone", action="store_true",
                             help="domain motorlarını ÇALIŞTIR: bölge kutuları + yapı (swing/BOS/CHoCH/kritik)"
                                  " (yalnız bu CLI: botun çizim yolu motoru yeniden çağırmaz, §14.2)")
    ayristirici.add_argument("--serit-yok", action="store_true", help="katılım kulvarını kapat")
    ayristirici.add_argument("--etiket-detay", action="store_true",
                             help="motorun `evidence_text` satırını da yaz (§2.6)")
    ayristirici.add_argument("--tum-tf", action="store_true",
                             help="1s/2s/4s/1g için ayrı ayrı kare üret (/grafik provası)")
    ayristirici.add_argument("--demo", action="store_true",
                             help="cache okumadan deterministik sentetik render→PNG testi")
    ayristirici.add_argument("--json", action="store_true", help="meta çıktısını yazdır")
    secenek = ayristirici.parse_args(giris)

    veri_dizin = _veri_dizini(secenek.veri_dizin)
    tfler = TF_LISTESI if secenek.tum_tf else (secenek.tf,)
    durum = 0
    for tf in tfler:
        # Tek yol: `/grafik` komutu da AYNI `kare_uret`i çağırır; CLI yalnız çıktıyı
        # biçimlendirir. Böylece kadraj/motor/çizim davranışı iki yüzeyde
        # ayrışamaz (ayrı kopyalar G1'de gerçekten ayrışmıştı).
        try:
            sonuc = kare_uret(secenek.hisse, tf, veri_dizin=veri_dizin, zone=secenek.zone,
                              mum=secenek.mum, serit=not secenek.serit_yok,
                              etiket_detay=secenek.etiket_detay,
                              formasyon_yol=secenek.formasyon, formasyon_tara=secenek.formasyon_tara,
                              alarm_turu=secenek.alarm_turu, demo=secenek.demo,
                              cikti=_cikti_yolu(secenek.cikti, secenek.hisse, tf, tfler))
        except SystemExit as hata:        # `_cerceve_yukle` uyumluluğu
            print(hata, file=sys.stderr)
            return 2
        meta = sonuc.get("meta") or {}
        if sonuc.get("hata"):
            print(sonuc["hata"], file=sys.stderr)
            return 2
        if secenek.json:
            print(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
        if sonuc.get("yol"):
            print(f"{sonuc['yol']}  ·  {meta['mum_sayisi']} mum  ·  {meta['png_kb']} KB"
                  f"  ·  {meta['sure_ms']} ms  ·  kaynak: {sonuc['kaynak']}")
        else:
            durum = 2
            print(f"çizilmedi ({tf}): " + " · ".join(meta.get("uyarilar") or []),
                  file=sys.stderr)
    return durum


if __name__ == "__main__":
    raise SystemExit(main())
