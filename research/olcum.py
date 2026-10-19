"""Ölçüm çekirdeği: çapa sonrası fiyat yolunu ATR cinsinden ölçer.

Bu modül dört alanın (OB, FVG, Market Structure, swing seviyeleri) ortak
ölçüm dilidir. Tasarım kuralları ``supabase_backfill_schema.sql`` başındaki
9 kuralın ölçüm tarafına düşen kısmıdır:

* **Lookahead yok.** Her ölçüm yalnız çapa barından *sonraki* barları okur.
  Çapa barının kendisi uzanım hesabına katılmaz.
* **Normalizasyon ATR cinsindendir.** BIST 5 TL ile 500 TL arasında hisse
  barındırdığı için TL veya % havuzlanamaz; her uzanım çapa anındaki ATR'ye
  bölünür ve o ATR değeri gözlemle birlikte saklanır.
* **Sağdan sansür açıkça işaretlenir.** Pencere veri sonuna takıldıysa
  ``sansur=True`` olur ve o gözlem asla "başarılı direnç/destek" sayılmaz;
  ayrı bir kovada raporlanır.
* **Eşikler ön-tanımlıdır.** Ölçümden sonra eşik seçilmez; ``ESIK_IZGARA``
  sabittir ve sonuçlar ızgara olarak verilir.
* **Belirsiz gözlem düşürülmez.** Çapa barı zone'un iki kenarına birden
  değiyorsa ya da tamamen içindeyse yön belirlenemez; bu ``BELIRSIZ`` olarak
  ayrı raporlanır, ne yukarı ne aşağı ölçüme karıştırılır.

İki ölçüm ekseni birlikte taşınır ve raporda ikisi de gösterilir:

``yon_ancored``
    Zone'un kendi yönünden ölçer (bullish → yukarı). "Beklenen tepki"
    ölçüsüdür ve ``directional_zone_replay.directional_excursions`` ile
    aynı mantığı per-bar yol bilgisiyle genişletir.

``kenar_ancored``
    Dokunulan *kenardan* ölçer. Üst kenara değildi → aşağı, alt kenara
    değildi → yukarı. Kullanıcının direnç/destek kuralının birebir
    karşılığıdır ve zone yönüyle çeliştiği durumları (örneğin bullish OB'ye
    alttan gelip üst kenarında reddedilme) yakalar.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "HORIZONLAR",
    "ESIK_IZGARA",
    "YUKSEKLIK_KOVALARI",
    "PAY_PENCERELERI",
    "DENEME_ESIKLERI",
    "SWING_PENCERESI",
    "UZUN_PENCERE",
    "yukseklik_kovasi",
    "tepki_sinifi",
    "dokunulan_kenar",
    "kenar_yonu",
    "tek_yonlu_yol",
    "yol_ozeti",
    "yon_ancored_olcum",
    "kenar_ancored_olcum",
    "deneme_ozeti",
    "vp_ornek",
]

#: Uzanım pencereleri. ``directional_zone_replay.HORIZONS`` ile aynı tutulur
#: ki eski ve yeni ölçümler karşılaştırılabilir olsun.
HORIZONLAR: tuple[int, ...] = (10, 12)

#: Ön-tanımlı ATR eşik ızgarası. Raporda her eşik ayrı satır olur.
ESIK_IZGARA: tuple[float, ...] = (0.25, 0.50, 1.00, 1.50, 2.00)

#: Zone yüksekliği kovaları (ATR cinsinden). "Daha yüksek zone tepkinin
#: şeklini değiştiriyor mu?" sorusunun ön-tanımlı ayrımı.
YUKSEKLIK_KOVALARI: tuple[tuple[float, float], ...] = (
    (0.0, 0.5),
    (0.5, 1.0),
    (1.0, 2.0),
    (2.0, float("inf")),
)

#: Tepe paylaşımının ölçüldüğü kısa pencereler. "Tepki anlık mı?" sorusu
#: buradan cevaplanır: 1-3-5 barda tepenin ne kadarı gerçekleşti.
PAY_PENCERELERI: tuple[int, ...] = (1, 3, 5)

#: Swing seviyesine yaklaşma sayımı için ATR bantları. Kullanıcının seçtiği
#: 0.25 ana eşiktir; 0.15 ve 0.50 duyarlılık kontrolü olarak eklenmiştir.
DENEME_ESIKLERI: tuple[float, ...] = (0.25, 0.15, 0.50)

#: Swing sonrası gözlem penceresi (native TF barı). Pencere dışı "kırılmadı"
#: değil "gözlemlenmedi" anlamına gelir; sansür bu yüzden zorunludur.
SWING_PENCERESI: int = 40

#: "Yavaş ama kalıcı" ayrımı için uzun uzanım penceresi (native TF barı).
#: Ana horizon (12) tepkinin varlığını, bu pencere kalıcılığını ölçer.
UZUN_PENCERE: int = 40


def _esik_etiketi(esik: float) -> str:
    """``0.25`` -> ``025``, ``2.0`` -> ``200``. Kolon adlarında nokta yok.

    Eski sürüm ``str(esik).replace(".", "")`` kullanıyordu ve ``2.0`` ->
    ``"20"`` -> ``zfill(3)`` -> ``"020"`` üretiyordu; yani 2.0 ATR eşiği
    0.20 ATR gibi okunuyordu. Yüzdelik tam sayıya çevirmek çakışmayı ve
    yanlış okumayı kaldırır.
    """
    return str(int(round(float(esik) * 100))).zfill(3)


def tepki_sinifi(tepe_atr: float | None) -> str:
    """Çapa sonrası tepkiyi ön-tanımlı sınıfa atar.

    ``tepe_atr`` ölçüm yönünde, ana horizon içinde gerçekleşen en büyük
    uzanımdır. Negatifse fiyat ölçüm yönüne **hiç** gitmemiştir — bu "tepki
    yok"tan farklı bir durumdur ve ayrı sınıf alır. Eşikler ``ESIK_IZGARA``
    ile tutarlı ve ölçümden önce sabittir.
    """
    if tepe_atr is None or not math.isfinite(float(tepe_atr)):
        return "OLCULEMEDI"
    deger = float(tepe_atr)
    if deger < 0:
        return "TERS"
    if deger >= 1.0:
        return "CALISTI"
    if deger >= 0.25:
        return "AZ"
    return "YOK"


def yukseklik_kovasi(yukseklik_atr: float | None) -> str:
    """Zone yüksekliğini ön-tanımlı kovaya atar. Ölçülemiyorsa ``BILINMEYEN``."""
    if yukseklik_atr is None or not math.isfinite(float(yukseklik_atr)):
        return "BILINMEYEN"
    deger = float(yukseklik_atr)
    for alt, ust in YUKSEKLIK_KOVALARI:
        if alt <= deger < ust:
            if math.isinf(ust):
                return f">={alt:g}"
            return f"{alt:g}-{ust:g}"
    return "<0.5" if deger < YUKSEKLIK_KOVALARI[0][1] else "BILINMEYEN"


def dokunulan_kenar(bar: Mapping[str, Any], zone_lower: float, zone_upper: float) -> str:
    """Çapa barının zone ile geometrik ilişkisine göre dokunulan kenarı bulur.

    Dönen değerler:

    ``UST_KENAR``
        Barın yüksekliği zone üstüne değdi/geçti ama altına inmedi.
    ``ALT_KENAR``
        Barın düşüğü zone altına değdi/geçti ama üstüne çıkmadı.
    ``TUM_ZONE``
        Bar zone'un iki kenarına birden değdi. Yön belirlenemez.
    ``ZONE_ICI``
        Bar zone sınırları içinde kaldı, hiçbir kenara değmedi.
    ``GECERSIZ``
        Zone yüksekliği pozitif değil.
    """
    try:
        high, low = float(bar["high"]), float(bar["low"])
        alt, ust = float(zone_lower), float(zone_upper)
    except (KeyError, TypeError, ValueError):
        return "GECERSIZ"
    if not math.isfinite(alt) or not math.isfinite(ust) or ust <= alt:
        return "GECERSIZ"
    degdi_ust = high >= ust
    degdi_alt = low <= alt
    if degdi_ust and degdi_alt:
        return "TUM_ZONE"
    if degdi_ust:
        return "UST_KENAR"
    if degdi_alt:
        return "ALT_KENAR"
    return "ZONE_ICI"


def kenar_yonu(kenar: str) -> str | None:
    """Dokunulan kenardan ölçüm yönünü üretir (direnç/destek mantığı).

    Üst kenar → aşağı ölçülür, alt kenar → yukarı. Yönü belirlenemeyen
    kenarlar ``None`` döner; çağıran taraf bu gözlemi ayrı raporlamalıdır.
    """
    if kenar == "UST_KENAR":
        return "DOWN"
    if kenar == "ALT_KENAR":
        return "UP"
    return None


def _atr_gecerli(atr: float | None) -> bool:
    return atr is not None and math.isfinite(float(atr)) and float(atr) > 0


def tek_yonlu_yol(
    yon: str,
    referans: float,
    barlar: Sequence[Mapping[str, Any]],
    atr: float | None,
) -> list[float | None]:
    """Çapa sonrası her bar için tek yönlü ATR uzanımını döndürür.

    ``barlar`` çapadan *sonraki* barlardır; ``barlar[0]`` çapayı izleyen ilk
    bardır. Negatif değerler korunur çünkü fiyatın referansın ters tarafına
    geçtiğini gösterir (örneğin yukarı ölçümde fiyatın referansın altına
    inmesi). Bu bilgi ``max(0, ...)`` ile kırpılırsa kaybolur.
    """
    if yon not in ("UP", "DOWN"):
        raise ValueError("yon 'UP' veya 'DOWN' olmalı")
    if not _atr_gecerli(atr):
        return [None] * len(barlar)
    referans = float(referans)
    bolen = float(atr)
    yol: list[float | None] = []
    for bar in barlar:
        try:
            if yon == "UP":
                fark = float(bar["high"]) - referans
            else:
                fark = referans - float(bar["low"])
        except (KeyError, TypeError, ValueError):
            yol.append(None)
            continue
        yol.append(fark / bolen)
    return yol


def yol_ozeti(yol: Sequence[float | None], horizons: Iterable[int] = HORIZONLAR) -> dict[str, Any]:
    """Tek yönlü uzanım yolundan şekil metriklerini üretir.

    ``directional_excursions`` yalnız pencere içi ``max`` verir; tepeye kaç
    barda ulaşıldığı ve tepenin ne kadarının korunduğu bilgisi kaybolur. Bu
    özet o kaybı kapatır: "yüksek zone tepkisi anlık mı, yoksa yavaş ama
    kalıcı mı?" sorusu yalnız buradan cevaplanabilir.

    **Tüm tepe metrikleri SINIRLI pencerede hesaplanır.** Sınırsız gelecekte
    tepe almak uzun vadeli sürüklenmeyi "tepki" gibi gösterir: 12 barda hiç
    tepki vermeyen bir zone, 800 bar sonraki fiyat aralığı sayesinde dev bir
    tepe alır ve ``pay_5`` anlamsız (negatif) çıkar. Bu yüzden:

    ``tepe_atr``
        En büyük horizon (12 bar) içindeki tepe. Ana tepki ölçüsü.
    ``uzun_tepe_atr``
        ``UZUN_PENCERE`` (40 bar) içindeki tepe. "Yavaş ama kalıcı" ayrımı
        ``tepe_atr`` ile karşılaştırılarak yapılır.
    """
    degerler = [v for v in yol if v is not None and math.isfinite(v)]
    gozlenen = len(degerler)
    horizonlar = tuple(horizons)
    ana_horizon = max(horizonlar) if horizonlar else 12
    sonuc: dict[str, Any] = {
        "gozlenen_bar": gozlenen,
        "tepe_atr": None,
        "tepe_bar": None,
        "dip_atr": None,
        "uzun_tepe_atr": None,
        "uzun_tepe_bar": None,
        "uzun_kapanis_atr": None,
        "uzun_decay": None,
        "uzun_sansur": True,
    }
    if not degerler:
        for h in horizonlar:
            sonuc[f"h{h}"] = None
            sonuc[f"h{h}_sansur"] = True
            sonuc[f"h{h}_kapanis_atr"] = None
            sonuc[f"h{h}_decay"] = None
        for p in PAY_PENCERELERI:
            sonuc[f"pay_{p}"] = None
        for esik in ESIK_IZGARA:
            sonuc[f"asim_{_esik_etiketi(esik)}"] = None
            sonuc[f"asim_{_esik_etiketi(esik)}_bar"] = None
        return sonuc

    # Ana horizon penceresi: tepki ölçüsünün sınırı.
    ana = degerler[:ana_horizon]
    if ana:
        tepe = max(ana)
        sonuc["tepe_atr"] = tepe
        sonuc["tepe_bar"] = ana.index(tepe) + 1
        sonuc["dip_atr"] = min(ana)
        # Tepe paylaşımı: k barda ana tepenin ne kadarı gerçekleşti.
        # pay_5 ~ 1 -> tepki ANLIK; pay_5 düşük + uzun tepe yüksek -> YAVAŞ AMA KALICI.
        for p in PAY_PENCERELERI:
            kisa = ana[:p]
            sonuc[f"pay_{p}"] = (max(kisa) / tepe) if (kisa and tepe > 0) else None
        for esik in ESIK_IZGARA:
            etiket = _esik_etiketi(esik)
            sonuc[f"asim_{etiket}"] = tepe >= esik
            sonuc[f"asim_{etiket}_bar"] = next((i + 1 for i, v in enumerate(ana) if v >= esik), None)
    else:
        sonuc["dip_atr"] = None
        for p in PAY_PENCERELERI:
            sonuc[f"pay_{p}"] = None
        for esik in ESIK_IZGARA:
            etiket = _esik_etiketi(esik)
            sonuc[f"asim_{etiket}"] = None
            sonuc[f"asim_{etiket}_bar"] = None

    for h in horizonlar:
        pencere = degerler[:h]
        sansur = gozlenen < h
        sonuc[f"h{h}_sansur"] = sansur
        if not pencere:
            sonuc[f"h{h}"] = None
            sonuc[f"h{h}_kapanis_atr"] = None
            sonuc[f"h{h}_decay"] = None
            continue
        tepe_h = max(pencere)
        sonuc[f"h{h}"] = tepe_h
        kapanis = pencere[-1]
        sonuc[f"h{h}_kapanis_atr"] = kapanis
        # decay: tepenin ne kadarı pencere sonunda geri verildi. Yüksek değer
        # "anlık tepki sonra solma", düşük değer "yavaş ama kalıcı" demektir.
        sonuc[f"h{h}_decay"] = ((tepe_h - kapanis) / tepe_h) if tepe_h > 0 else None

    uzun = degerler[:UZUN_PENCERE]
    if uzun:
        sonuc["uzun_sansur"] = gozlenen < UZUN_PENCERE
        uzun_tepe = max(uzun)
        sonuc["uzun_tepe_atr"] = uzun_tepe
        sonuc["uzun_tepe_bar"] = uzun.index(uzun_tepe) + 1
        uzun_kapanis = uzun[-1]
        sonuc["uzun_kapanis_atr"] = uzun_kapanis
        sonuc["uzun_decay"] = ((uzun_tepe - uzun_kapanis) / uzun_tepe) if uzun_tepe > 0 else None
    return sonuc


def yon_ancored_olcum(
    direction: str,
    zone_lower: float,
    zone_upper: float,
    future_bars: Sequence[Mapping[str, Any]],
    atr: float | None,
) -> dict[str, Any]:
    """Zone yönünden ölçüm: bullish → yukarı (üst kenardan), bearish → aşağı.

    Bu, motordaki "beklenen tepki" ölçüsüdür. Referans fiyat native kenardır:
    bullish için ``zone_upper`` (yukarı uzanımın başlangıcı), bearish için
    ``zone_lower``.
    """
    yon = "UP" if str(direction).lower() == "bullish" else "DOWN"
    referans = float(zone_upper) if yon == "UP" else float(zone_lower)
    return yol_ozeti(tek_yonlu_yol(yon, referans, future_bars, atr))


def kenar_ancored_olcum(
    kenar: str,
    zone_lower: float,
    zone_upper: float,
    future_bars: Sequence[Mapping[str, Any]],
    atr: float | None,
) -> dict[str, Any]:
    """Dokunulan kenardan ölçüm (kullanıcının direnç/destek kuralı).

    Üst kenara değildi → aşağı ölçülür, referans ``zone_upper``.
    Alt kenara değildi → yukarı ölçülür, referans ``zone_lower``.
    Yön belirlenemiyorsa ``olculmedi`` gerekçesiyle boş özet döner; gözlem
    raporda ``BELIRSIZ`` kovasında tutulur, sessizce atılmaz.
    """
    yon = kenar_yonu(kenar)
    if yon is None:
        ozet = yol_ozeti([])
        ozet["olculmedi"] = kenar
        return ozet
    referans = float(zone_upper) if yon == "DOWN" else float(zone_lower)
    ozet = yol_ozeti(tek_yonlu_yol(yon, referans, future_bars, atr))
    ozet["olcum_yonu"] = yon
    return ozet


def _yaklasma_epizotlari(işaretler: Sequence[bool]) -> int:
    """Ardışık ``True`` barlarını tek epizot sayar (OB dokunuş mantığıyla aynı)."""
    sayi = 0
    onceki = False
    for deger in işaretler:
        if deger and not onceki:
            sayi += 1
        onceki = deger
    return sayi


def deneme_ozeti(
    seviye: float,
    rol: str,
    future_bars: Sequence[Mapping[str, Any]],
    atr: float | None,
    esikler: Iterable[float] = DENEME_ESIKLERI,
) -> dict[str, Any]:
    """Bir swing seviyesinin kaç kere denendiğini ve engel olup olmadığını ölçer.

    ``rol`` ``"HIGH"`` ise seviye dirençtir: yaklaşma, barın yüksekliğinin
    seviyenin ``esik*ATR`` altına kadar çıkmasıdır; kırılım kapanışın
    seviyenin üstüne geçmesidir. ``"LOW"`` için simetriktir.

    ``engelledi`` üç değerlidir: ``True`` (pencere içinde kırılmadı),
    ``False`` (kırıldı), ``None`` (pencere veri sonuna takıldı → sansürlü,
    karar verilemez). "Henüz kırılmadı" ile "başarılı direnç" ayrımı budur.
    """
    if rol not in ("HIGH", "LOW"):
        raise ValueError("rol 'HIGH' veya 'LOW' olmalı")
    gozlenen = len(future_bars)
    sonuc: dict[str, Any] = {
        "gozlenen_bar": gozlenen,
        "sansur": False,
        "max_yaklasma_atr": None,
        "max_yaklasma_bar": None,
        "kirilim_bar": None,
        "kirilim_atr": None,
        "red_magnitude_atr": None,
    }
    if not gozlenen:
        for esik in esikler:
            e = _esik_etiketi(esik)
            sonuc[f"deneme_bar_{e}"] = 0
            sonuc[f"deneme_epizot_{e}"] = 0
            sonuc[f"engelledi_{e}"] = None
        sonuc["sansur"] = True
        return sonuc
    sonuc["sansur"] = gozlenen < SWING_PENCERESI

    atr_ok = _atr_gecerli(atr)
    bant = float(atr) if atr_ok else 0.0
    seviye = float(seviye)

    if rol == "HIGH":
        yaklasma = [float(b["high"]) - seviye for b in future_bars]
        kirdi = [float(b["close"]) > seviye for b in future_bars]
    else:
        yaklasma = [seviye - float(b["low"]) for b in future_bars]
        kirdi = [float(b["close"]) < seviye for b in future_bars]

    # yaklasma > 0 : seviye aşıldı. yaklasma < 0 : seviyeye |değer| kadar yaklaşıldı.
    asildi = [v for v in yaklasma if v > 0]
    sonuc["max_yaklasma_atr"] = (max(asildi) / bant) if (asildi and atr_ok) else (0.0 if asildi and not atr_ok else None)
    if asildi:
        sonuc["max_yaklasma_bar"] = yaklasma.index(max(asildi)) + 1
        sonuc["gecildi"] = True
    else:
        en_yakin = min(yaklasma, key=lambda v: abs(v))
        sonuc["max_yaklasma_atr"] = (yaklasma[yaklasma.index(en_yakin)] / bant) if atr_ok else None
        sonuc["max_yaklasma_bar"] = yaklasma.index(en_yakin) + 1
        sonuc["gecildi"] = False

    kirilim_bar = next((i + 1 for i, k in enumerate(kirdi) if k), None)
    sonuc["kirilim_bar"] = kirilim_bar
    if kirilim_bar is not None:
        sonuc["kirilim_atr"] = (yaklasma[kirilim_bar - 1] / bant) if atr_ok else None
        # red büyüklüğü: kırılımdan sonra fiyatın ters yöne ne kadar gittiği
        sonraki = future_bars[kirilim_bar:]
        if sonraki and atr_ok:
            if rol == "HIGH":
                sonuc["red_magnitude_atr"] = (float(future_bars[kirilim_bar - 1]["close"]) - min(float(b["low"]) for b in sonraki)) / bant
            else:
                sonuc["red_magnitude_atr"] = (max(float(b["high"]) for b in sonraki) - float(future_bars[kirilim_bar - 1]["close"])) / bant

    for esik in esikler:
        etiket = _esik_etiketi(esik)
        bant_esik = esik * bant
        # HIGH: seviyeye esik*ATR kadar yaklaşan barlar. LOW: simetrik.
        if rol == "HIGH":
            yaklasti = [float(b["high"]) >= seviye - bant_esik for b in future_bars]
        else:
            yaklasti = [float(b["low"]) <= seviye + bant_esik for b in future_bars]
        sonuc[f"deneme_bar_{etiket}"] = sum(1 for y in yaklasti if y)
        sonuc[f"deneme_epizot_{etiket}"] = _yaklasma_epizotlari(yaklasti)
        if kirilim_bar is None:
            # Kırılım yok. Pencere tamsa "engelledi", sansürlüyse karar yok.
            sonuc[f"engelledi_{etiket}"] = None if sonuc["sansur"] else True
        else:
            # Kırılım varsa: kırılım anında seviyeyi esikten fazla geçti mi?
            gecti = yaklasma[kirilim_bar - 1] > bant_esik if atr_ok else None
            sonuc[f"engelledi_{etiket}"] = (not gecti) if gecti is not None else None
    return sonuc


def vp_ornek(metrics_history: Any, index: int | None) -> dict[str, Any]:
    """VP metriklerini yalnız çapa anında örnekler (depolama bombası önlemi).

    ``metrics_history`` bar başına bir kayıt tutar ve 1h'de 3000+ kayıt olur;
    tamamını saklamak koşu başına 45-70 MB demektir. Bu yüzden yalnız çapa
    barındaki değerler alınır. Alanlar ``volume_participation_engine``
    çıktısıyla birebir aynıdır; eksik/``None`` değer düşürülmez, olduğu gibi
    taşınır ki ``volume_usable=False`` satırları kaybolmasın.
    """
    alanlar = (
        "rvol",
        "volume_z_score",
        "volume_percent_rank",
        "volume_slope",
        "rtv",
        "capital_z_score",
        "directional_value_pressure_5",
        "directional_value_pressure_10",
        "net_progress_atr",
        "directional_efficiency",
        "volume_result_efficiency",
        "capital_result_efficiency",
        "effort_result_class",
        "data_ready",
        "volume_usable",
        "capital_usable",
    )
    ornek: dict[str, Any] = {f"vp_{alan}": None for alan in alanlar}
    if metrics_history is None or index is None:
        return ornek
    try:
        kayit = metrics_history[int(index)]
    except (IndexError, TypeError, ValueError, KeyError):
        return ornek
    if kayit is None:
        return ornek
    for alan in alanlar:
        deger = getattr(kayit, alan, None)
        if deger is None and isinstance(kayit, Mapping):
            deger = kayit.get(alan)
        if isinstance(deger, bool):
            ornek[f"vp_{alan}"] = bool(deger)
        elif isinstance(deger, (int, float)) and math.isfinite(float(deger)):
            ornek[f"vp_{alan}"] = float(deger)
        elif isinstance(deger, str):
            ornek[f"vp_{alan}"] = deger
        else:
            ornek[f"vp_{alan}"] = None
    return ornek
