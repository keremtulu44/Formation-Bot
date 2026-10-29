"""Motor çıktılarını ölçülebilir gözlem satırlarına dönüştürür.

Bu modül motor **değiştirmez**. Dört kaynaktan beslenir:

``replay_ob_zones``
    OB popülasyonunun tamamı. Kritik nokta: OB motoru dolan/geçilen
    kayıtları ``_records`` listesinden *siler*, dolayısıyla final snapshot
    yalnız hayatta kalanları verir ve "%kaçı geçildi" sorusu oradan
    cevaplanamaz. Replay bar bar ``pre_active``/``post_active`` karşılaştırıp
    silinen zone'ları ``native_terminal_*`` ile kaydettiği için tam
    popülasyonu yeniden kurar.

``replay_fvg_zones``
    Aynı zone/terminal sözleşmesiyle FVG. OB ile aynı biçimde tüketilir.

``run_domain_engines``
    Market Structure (swing + event ledger) ve Volume Participation
    ``metrics_history``. VP bar başına kayıt üretir; tamamı saklanırsa koşu
    başına 45-70 MB olur, bu yüzden yalnız çapa anında örneklenir.

``build_touch_episodes`` / ``build_window_rows``
    Tekrarlanan temas barlarını epizotlara ayırır ve yön-ancored uzanımı
    hesaplar. Bu modül onların çıktısını **şekil**, **kenar-ancored**,
    **yükseklik** ve **VP** metrikleriyle zenginleştirir.

Anti-lookahead sözleşmesi: hiçbir ölçüm çapa barını veya öncesini okumaz.
MS eventlerinde çapa ``event_bar`` (onay) dir, ``candidate_bar`` değil;
aday anından ölçmek geleceği kullanmak olurdu.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

from research import olcum
from directional_zone_replay import (
    _normalize_frame,
    build_touch_episodes,
    build_window_rows,
    compute_wilder_atr,
    replay_fvg_zones,
    replay_ob_zones,
)

__all__ = [
    "ENGINE_VERSION",
    "config_hash",
    "FVG_TIMEFRAMELERI",
    "ROL_ALANLARI",
    "ms_adimli_kosu",
    "vp_kosu",
    "rol_araliklari_by_identity",
    "yon_metni",
    "devamlilik_sinifi",
    "zone_satirlari",
    "dokunus_satirlari",
    "swing_satirlari",
    "event_satirlari",
    "sembol_timeframe_gozlem",
]

#: Türetilmiş her satıra yazılan motor sürümü. Şema kuralı 6: engine_version
#: ve config_hash olmadan geçmiş koşular karşılaştırılamaz.
ENGINE_VERSION = "arastirma-olcum-v1"

#: FVG motorunun çalıştığı zaman dilimleri. ``domain_engines.runner`` ile aynı.
FVG_TIMEFRAMELERI = frozenset({"2h", "4h", "1d"})

#: ``StructureContext`` üzerindeki rol kimliği alanları ve kısa adları.
#: PH/PL "korunan tepe/dip" (direnç/destek sorusu), WH/WL "zayıf tepe/dip"
#: (ziyaret/süpürme sorusu), SH/SL "güçlü tepe/dip" (BOS hedefi).
ROL_ALANLARI: dict[str, str] = {
    "protected_high_identity": "PH",
    "protected_low_identity": "PL",
    "strong_high_identity": "SH",
    "strong_low_identity": "SL",
    "weak_high_identity": "WH",
    "weak_low_identity": "WL",
}

_ANAHTARLAR = (
    "HORIZONLAR",
    "ESIK_IZGARA",
    "YUKSEKLIK_KOVALARI",
    "PAY_PENCERELERI",
    "DENEME_ESIKLERI",
    "SWING_PENCERESI",
    "UZUN_PENCERE",
    # Formasyon yakınlık ızgarası (v1): eşik seçimi ölçümden ÖNCE sabitlenir.
    # Burada olmazsa config_hash değişmez ve eski/yeni satırlar sessizce karışır.
    "YAKINLIK_IZGARA",
)


def config_hash() -> str:
    """Ölçüm sabitlerinin kısa özeti. Eşik değişirse hash değişir, satırlar ayrışır."""
    parcalar = []
    for ad in _ANAHTARLAR:
        deger = getattr(olcum, ad)
        parcalar.append(f"{ad}={tuple(deger) if isinstance(deger, (tuple, list, frozenset)) else deger}")
    ham = "|".join(parcalar).encode("utf-8")
    return hashlib.sha256(ham).hexdigest()[:12]


def yon_metni(direction: Any) -> str:
    """MS ``Direction`` enum'unu ``UP``/``DOWN``/``BELIRSIZ`` olarak normalize eder."""
    if direction is None:
        return "BELIRSIZ"
    metin = str(getattr(direction, "value", direction)).upper()
    if any(k in metin for k in ("BULL", "UP", "POZITIF", "POSITIVE", "YUKARI")):
        return "UP"
    if any(k in metin for k in ("BEAR", "DOWN", "NEGATIF", "NEGATIVE", "ASAGI")):
        return "DOWN"
    # Sayısal yön temsili: +1 yukarı, -1 aşağı
    deger = getattr(direction, "value", None)
    if isinstance(deger, (int, float)):
        return "UP" if deger > 0 else ("DOWN" if deger < 0 else "BELIRSIZ")
    return "BELIRSIZ"


def devamlilik_sinifi(h12: float | None) -> str:
    """MS eventi sonrası devamlılığı ön-tanımlı sınıfa atar.

    ``h12`` onay barını izleyen 12 bar içinde event yönünde gerçekleşen en
    büyük ATR uzanımıdır. Negatifse fiyat event yönüne **hiç** gitmemiştir.
    Eşikler ölçümden önce sabitlenmiştir.
    """
    if h12 is None or not math.isfinite(float(h12)):
        return "OLCULEMEDI"
    deger = float(h12)
    if deger < 0:
        return "TERS"
    if deger >= 1.0:
        return "CALISTI"
    if deger >= 0.25:
        return "AZ_DEVAM"
    return "DEVAM_YOK"


def _bar_time(frame: Any, index: int | None) -> str | None:
    """Pencere içi indeks değil ``bar_time`` kimliği (şema kuralı 2).

    Çerçeve ``_normalize_frame`` çıktısıdır: RangeIndex + ``timestamp``
    kolonu. Bu yüzden ``.at[index, "timestamp"]`` pozisyonel olarak doğrudur
    ve ``directional_zone_replay`` içindeki indekslerle birebir hizalıdır.
    """
    if index is None or frame is None:
        return None
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None
    if idx < 0:
        return None
    try:
        if "timestamp" in getattr(frame, "columns", ()):
            return str(frame.at[idx, "timestamp"])
        return str(frame.index[idx])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def _atr_at(atr: Sequence[float | None], index: int | None) -> float | None:
    if index is None:
        return None
    try:
        deger = atr[int(index)]
    except (IndexError, TypeError, ValueError):
        return None
    return float(deger) if deger is not None and math.isfinite(float(deger)) else None


def _yuvarla(deger: Any, basamak: int = 6) -> Any:
    if deger is None:
        return None
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(sayi):
        return None
    return round(sayi, basamak)


def _ozet_duzlestir(ozet: Mapping[str, Any], onek: str) -> dict[str, Any]:
    """İç içe özet sözlüğünü tek seviyeye indirir (kolon adları sabit kalır).

    Sayılar yuvarlanır; ``bool``, ``str`` ve ``None`` OLDUĞU GİBİ taşınır.
    Önceki sürüm her değeri ``float()`` içinden geçiriyordu ve ``olcum_yonu``
    gibi string alanlar sessizce ``None`` oluyordu — ölçüm yapıldığı halde
    "yön belirlenemedi" gibi görünüyordu.
    """
    cikti: dict[str, Any] = {}
    for k, v in ozet.items():
        if v is None or isinstance(v, (bool, str)):
            cikti[f"{onek}{k}"] = v
        else:
            cikti[f"{onek}{k}"] = _yuvarla(v)
    return cikti


def zone_satirlari(zones: Iterable[Mapping[str, Any]], atr: Sequence[float | None], frame: Any) -> list[dict[str, Any]]:
    """Zone başına bir satır: doğum anı sınırları, yükseklik, terminal durumu.

    Sınırlar **doğum anında dondurulur** (şema kuralı 2). ``yukseklik_atr``
    doğum barındaki ATR ile hesaplanır; sonradan değişen ATR kullanılmaz.
    """
    satirlar: list[dict[str, Any]] = []
    for zone in zones:
        dogum = zone.get("origin_index")
        kullanilabilir = zone.get("available_index")
        atr_dogum = _atr_at(atr, dogum if dogum is not None else kullanilabilir)
        alt, ust = float(zone["zone_lower"]), float(zone["zone_upper"])
        yukseklik = ust - alt
        epizot = len(zone.get("touch_bars") or ())
        terminal_index = zone.get("native_terminal_index")
        gozlenen = len(frame)
        sansur = terminal_index is None and gozlenen > 0
        satirlar.append({
            "zone_id": zone.get("zone_id"),
            "symbol": zone.get("symbol"),
            "timeframe": zone.get("timeframe"),
            "family": zone.get("family"),
            "direction": zone.get("direction"),
            "beklenen_yon": zone.get("expected_reaction_direction"),
            "dogum_bar_time": _bar_time(frame, dogum),
            "kullanilabilir_bar_time": _bar_time(frame, kullanilabilir),
            "dogum_index": dogum,
            "zone_lower": _yuvarla(alt),
            "zone_upper": _yuvarla(ust),
            "yukseklik_fiyat": _yuvarla(yukseklik),
            "atr_at_birth": _yuvarla(atr_dogum),
            "yukseklik_atr": _yuvarla(yukseklik / atr_dogum) if atr_dogum else None,
            "yukseklik_kovasi": olcum.yukseklik_kovasi((yukseklik / atr_dogum) if atr_dogum else None),
            "native_terminal_category": zone.get("native_terminal_category"),
            "native_terminal_reason": zone.get("native_terminal_reason"),
            "native_terminal_state": zone.get("native_terminal_state"),
            "terminal_bar_time": _bar_time(frame, terminal_index),
            "terminal_index": terminal_index,
            "native_price_violation": bool(zone.get("native_price_violation")),
            "native_full_fill": bool(zone.get("native_full_fill")),
            "native_fill_ratio": _yuvarla(zone.get("native_fill_ratio_at_terminal_or_asof")),
            "temas_bar_sayisi": epizot,
            "temas_var": epizot > 0,
            "omur_bar": (int(terminal_index) - int(kullanilabilir)) if (terminal_index is not None and kullanilabilir is not None) else None,
            "sansur": bool(sansur),
            "engine_version": ENGINE_VERSION,
            "config_hash": config_hash(),
        })
    return satirlar


def dokunus_satirlari(
    episodes: Iterable[Mapping[str, Any]],
    window_rows: Iterable[Mapping[str, Any]],
    zones_by_id: Mapping[str, Mapping[str, Any]],
    frame: Any,
    atr: Sequence[float | None],
    vp_history: Any = None,
) -> list[dict[str, Any]]:
    """Epizot başına bir satır: yön-ancored + kenar-ancored + şekil + VP.

    ``build_window_rows`` çıktısı ``episode_id`` ile eşleştirilir ve üzerine
    üç yeni blok eklenir:

    * ``yon_*``  — zone yönünden ölçüm (mevcut mantık, per-bar yol bilgisiyle)
    * ``kenar_*`` — dokunulan kenardan ölçüm (kullanıcının direnç/destek kuralı)
    * ``sekil_*`` — tepeye kaç barda ulaşıldı, tepenin ne kadarı korundu

    Yükseklik kovası ve VP örneği de aynı satıra yazılır; böylece "yüksek
    zone tepkisi anlık mı" ve "hacim koşulu altında ne değişiyor" soruları
    tek tablodan çaprazlanır.
    """
    window_by_episode: dict[Any, list[dict[str, Any]]] = {}
    for row in window_rows:
        window_by_episode.setdefault(row.get("episode_id"), []).append(row)

    satirlar: list[dict[str, Any]] = []
    for ep in episodes:
        zone = zones_by_id.get(ep["zone_id"]) or {}
        basla, bitir = int(ep["touch_start_index"]), int(ep["touch_end_index"])
        atr_deger = _atr_at(atr, bitir)
        alt, ust = float(ep["zone_lower"]), float(ep["zone_upper"])

        # Dokunulan kenar İLK temas barından belirlenir (ön-tanımlı kural).
        ilk_bar = frame.iloc[basla].to_dict() if 0 <= basla < len(frame) else {}
        kenar = olcum.dokunulan_kenar(ilk_bar, alt, ust)
        kenar_yon = olcum.kenar_yonu(kenar)

        # Çapa sonrası barlar: epizot bitişini izleyen barlardan başlar.
        gozlenen = max(0, len(frame) - (bitir + 1))
        future = frame.iloc[bitir + 1:].to_dict("records")

        yon_olcum = olcum.yon_ancored_olcum(ep.get("direction") or "bullish", alt, ust, future, atr_deger)
        kenar_olcum = olcum.kenar_ancored_olcum(kenar, alt, ust, future, atr_deger)

        dogum = zone.get("origin_index")
        atr_dogum = _atr_at(atr, dogum if dogum is not None else basla)
        yukseklik_atr = ((ust - alt) / atr_dogum) if atr_dogum else None

        terminal_index = ep.get("native_terminal_index")
        en_buyuk_horizon = max(olcum.HORIZONLAR)
        sansur_pencere = gozlenen < en_buyuk_horizon
        sansur_terminal = terminal_index is None

        satir: dict[str, Any] = {
            "episode_id": ep.get("episode_id"),
            "zone_id": ep.get("zone_id"),
            "symbol": ep.get("symbol"),
            "timeframe": ep.get("timeframe"),
            "family": ep.get("family"),
            "direction": ep.get("direction"),
            "beklenen_yon": ep.get("expected_reaction_direction"),
            "dokunus_no": ep.get("touch_number_for_zone"),
            "dokunus_baslangic_bar_time": _bar_time(frame, basla),
            "dokunus_bitis_bar_time": _bar_time(frame, bitir),
            # Soru seti (S01/S15/S32): çapa indeksleri metinden yeniden
            # çözülmesin diye doğrudan yazılır.
            "dokunus_baslangic_index": int(basla),
            "dokunus_bitis_index": int(bitir),
            "dokunus_bar_sayisi": ep.get("touch_bar_count"),
            "sonraki_epizot_index": ep.get("_next_episode_start_index"),
            "arrival_side": ep.get("arrival_side"),
            "approach_direction": ep.get("approach_direction"),
            "dokunulan_kenar": kenar,
            "kenar_olcum_yonu": kenar_yon,
            "zone_lower": _yuvarla(alt),
            "zone_upper": _yuvarla(ust),
            "atr_at_touch": _yuvarla(atr_deger),
            "yukseklik_atr": _yuvarla(yukseklik_atr),
            "yukseklik_kovasi": olcum.yukseklik_kovasi(yukseklik_atr),
            "gozlenen_bar": gozlenen,
            "sansur_pencere": bool(sansur_pencere),
            "sansur_terminal": bool(sansur_terminal),
            "native_terminal_category": ep.get("native_terminal_category"),
            "native_price_violation": bool(ep.get("native_price_violation")),
            "native_full_fill": bool(ep.get("native_full_fill")),
            "terminal_dokunusta": bool(ep.get("native_terminal_at_touch")),
            "engine_version": ENGINE_VERSION,
            "config_hash": config_hash(),
        }
        satir.update(_ozet_duzlestir(yon_olcum, "yon_"))
        satir.update(_ozet_duzlestir(kenar_olcum, "kenar_"))
        # Tepki sınıfları: rapor yüzde üretirken ham ATR yerine bu ön-tanımlı
        # sınıfları kullanır, böylece eşik seçimi ölçümden SONRA yapılmamış olur.
        satir["yon_tepki_sinifi"] = olcum.tepki_sinifi(yon_olcum.get(f"h{en_buyuk_horizon}"))
        satir["kenar_tepki_sinifi"] = olcum.tepki_sinifi(kenar_olcum.get(f"h{en_buyuk_horizon}"))
        satir.update(olcum.vp_ornek(vp_history, bitir))

        # Repo'nun mevcut yön-ancored satırları da taşınır: eski/yeni ölçüm
        # karşılaştırılabilir olsun diye (regresyon kanıtı). Alan adları
        # `build_window_rows` çıktısıyla birebir aynıdır.
        # repoh{h}_ kopyası: S08/S09 için hedef kategorileri de dahil
        # (REPLAY_SORU_SETI_2026-10-29.md §8-E1).
        for pencere in window_by_episode.get(ep.get("episode_id"), []):
            horizon = pencere.get("horizon_bars")
            if horizon is None:
                continue
            onek = f"repoh{horizon}_"
            sabit_alanlar = (
                "full_window_favorable_excursion_atr",
                "full_window_adverse_excursion_atr",
                "favorable_excursion_before_native_terminal_atr",
                "favorable_excursion_on_terminal_bar_atr",
                "window_complete",
                "window_status",
                "native_terminal_within_full_horizon",
                "native_price_violation_within_full_horizon",
                "native_terminal_at_or_before_touch",
                "native_terminal_reason_in_window",
                "next_same_zone_touch_in_window",
                "observed_post_touch_bars",
                "preterminal_post_touch_bars",
                "active_target_eligible",
            )
            hedef_alanlar = tuple(
                f"target_{etiket}_atr_{alt}"
                for etiket in ("0p5", "1p0", "1p1p5")
                for alt in (
                    "hit_full_window",
                    "hit_before_native_terminal",
                    "possible_on_terminal_bar",
                    "hit_only_after_terminal",
                    "active_zone_category",
                )
            )
            for alan in sabit_alanlar + hedef_alanlar:
                if alan in pencere:
                    deger = pencere[alan]
                    satir[f"{onek}{alan}"] = deger if isinstance(deger, (bool, str)) or deger is None else _yuvarla(deger)
        satirlar.append(satir)
    return satirlar


def swing_satirlari(
    details: Mapping[str, Any],
    frame: Any,
    atr: Sequence[float | None],
    vp_history: Any,
    rol_grup: Mapping[tuple[str, int], Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """PH/PL/WL/WH soruları: swing başına deneme sayısı ve engelleme durumu.

    Hem ``external`` hem ``internal`` scope taşınır; kullanıcı ikisini de
    istedi.

    **Satır birimi (swing x rol aralığı)dır.** ``structural_role`` zamanla
    mutate olduğu için final değer yanıltıcıdır; ``ms_adimli_kosu``'nun
    ürettiği rol geçmişi kullanılır. Bir swing PH rolünü birden çok kez
    alabilir ve her aralık ayrı bir ölçüm birimidir.

    Çapa ``rol_ilk_bar`` dır — rolün ATANDIĞI an. Pencere oradan itibaren
    sabit ``SWING_PENCERESI`` bardır ve rolün ne zaman bittiğinden bağımsızdır.
    Bu seçim daireselliği önler: rol genellikle kırıldığında temizlendiği için
    pencereyi rol aralığıyla sınırlamak "engelledi mi" sorusunu baştan
    cevaplanmış varsaymak olurdu. Rol aralığı ayrı bir olgu olarak
    ``rol_sure_bar`` alanında taşınır.

    Rol aralığı olmayan swing'ler ``confirm_bar`` çapalı tek satır üretir;
    ``structural_role_final`` alanında final (yanlı) değer şeffaflık için
    korunur. Hiçbir swing düşürülmez.
    """
    rol_grup = rol_grup or {}
    satirlar: list[dict[str, Any]] = []
    for scope_alani in ("external_swings", "internal_swings"):
        varsayilan_scope = scope_alani.replace("_swings", "").upper()
        for swing in details.get(scope_alani) or ():
            confirm = getattr(swing, "confirm_bar", None)
            kaynak = getattr(swing, "source_bar", None)
            fiyat = getattr(swing, "price", None)
            side = str(getattr(swing, "side", "") or "").upper()
            rol_uci = "HIGH" if "HIGH" in side else ("LOW" if "LOW" in side else None)
            scope = str(getattr(swing, "scope", "") or varsayilan_scope).upper()
            identity = int(getattr(swing, "identity", 0) or 0)
            kirilim = getattr(swing, "broken_bar", None)

            temel: dict[str, Any] = {
                "scope": scope,
                "identity": identity,
                "side": side or None,
                "rol_uci": rol_uci,
                "swing_class": getattr(swing, "swing_class", None),
                "structural_role_final": getattr(swing, "structural_role", None),
                "state": getattr(swing, "state", None),
                "valid": bool(getattr(swing, "valid", False)),
                "finalized": bool(getattr(swing, "finalized", False)),
                "locked": bool(getattr(swing, "locked", False)),
                "source_bar": kaynak,
                "source_bar_time": _bar_time(frame, kaynak),
                "confirm_bar": confirm,
                "confirm_bar_time": _bar_time(frame, confirm),
                "price": _yuvarla(fiyat),
                "atr_at_source": _yuvarla(getattr(swing, "atr_at_source", None)),
                "prominence_atr": _yuvarla(getattr(swing, "prominence_atr", None)),
                "distance_atr": _yuvarla(getattr(swing, "distance_atr", None)),
                "quality": _yuvarla(getattr(swing, "quality", None)),
                "broken": bool(getattr(swing, "broken", False)),
                "broken_bar": kirilim,
                "broken_bar_time": _bar_time(frame, kirilim),
                "bars_to_break": (int(kirilim) - int(confirm)) if (kirilim is not None and confirm is not None) else None,
                "bars_to_break_sansur": kirilim is None,
                "engine_version": ENGINE_VERSION,
                "config_hash": config_hash(),
            }

            araliklar = list(rol_grup.get((scope, identity), ()))
            if not araliklar:
                araliklar = [{"rol": None, "rol_ilk_bar": confirm, "rol_son_bar": None,
                             "rol_sure_bar": None, "kapanis": "ROL_ATANMADI"}]

            for aralik in araliklar:
                satir = dict(temel)
                satir["rol"] = aralik.get("rol")
                satir["rol_ilk_bar"] = aralik.get("rol_ilk_bar")
                satir["rol_ilk_bar_time"] = _bar_time(frame, aralik.get("rol_ilk_bar"))
                satir["rol_son_bar"] = aralik.get("rol_son_bar")
                satir["rol_sure_bar"] = aralik.get("rol_sure_bar")
                satir["rol_kapanis"] = aralik.get("kapanis")

                capa = aralik.get("rol_ilk_bar")
                if capa is None or fiyat is None or rol_uci is None:
                    satir["olculmedi"] = (
                        "capa_yok" if capa is None else ("fiyat_yok" if fiyat is None else "rol_uci_belirsiz")
                    )
                    satir["sansur"] = True
                    satirlar.append(satir)
                    continue

                capa = int(capa)
                basla = capa + 1
                future = frame.iloc[basla: basla + olcum.SWING_PENCERESI].to_dict("records")
                atr_deger = _atr_at(atr, capa)
                ozet = olcum.deneme_ozeti(float(fiyat), rol_uci, future, atr_deger)
                satir["capa_bar"] = capa
                satir["capa_bar_time"] = _bar_time(frame, capa)
                satir["atr_at_capa"] = _yuvarla(atr_deger)
                satir["gozlenen_bar"] = ozet.pop("gozlenen_bar", None)
                satir.update({k: _yuvarla(v) if not isinstance(v, bool) else v for k, v in ozet.items()})
                # Rol atamasından kırılıma kadar geçen süre: "seviyeye ne kadar
                # sürede ulaşıldı" sorusunun rol-çapalı cevabı.
                satir["bars_to_break_from_rol"] = (int(kirilim) - capa) if kirilim is not None and int(kirilim) >= capa else None
                satir.update(olcum.vp_ornek(vp_history, capa))
                satirlar.append(satir)
    return satirlar


def event_satirlari(details: Mapping[str, Any], frame: Any, atr: Sequence[float | None], vp_history: Any) -> list[dict[str, Any]]:
    """BOS/CHOCH soruları: yön ile tepki uyuşuyor mu, ne kadar devam etti.

    Çapa ``event_bar`` (onay anı). Ölçüm event yönünde, referans fiyat onay
    barının kapanışı — yani olayı gören birinin o anki fiyatı. ``outcome``
    alanı motorun kendi takip kararıdır ve bağımsız bir çapraz kontrol
    sağlar; ikisi birlikte raporlanır.
    """
    satirlar: list[dict[str, Any]] = []
    for event in details.get("event_history") or ():
        bar = getattr(event, "event_bar", None)
        aday = getattr(event, "candidate_bar", None)
        yon = yon_metni(getattr(event, "direction", None))
        satir: dict[str, Any] = {
            "event_uid": getattr(event, "event_uid", None),
            "identity": getattr(event, "identity", None),
            "scope": getattr(event, "scope", None),
            "event_type": str(getattr(event, "event_type", "") or "") or None,
            "direction": yon,
            "candidate_bar": aday,
            "candidate_bar_time": _bar_time(frame, aday),
            "event_bar": bar,
            "event_bar_time": _bar_time(frame, bar),
            "onay_gecikmesi_bar": (int(bar) - int(aday)) if (bar is not None and aday is not None) else None,
            "broken_level": _yuvarla(getattr(event, "broken_level", None)),
            "broken_swing_identity": getattr(event, "broken_swing_identity", None),
            "origin_price": _yuvarla(getattr(event, "origin_price", None)),
            "quality": _yuvarla(getattr(event, "quality", None)),
            "confirmation_status": str(getattr(event, "confirmation_status", "") or "") or None,
            "validity": str(getattr(event, "validity", "") or "") or None,
            "relevance": str(getattr(event, "relevance", "") or "") or None,
            "outcome": str(getattr(event, "outcome", "") or "") or None,
            "bos_maturity": str(getattr(event, "bos_maturity", "") or "") or None,
            "age_bars": getattr(event, "age_bars", None),
            "confirmed_by": getattr(event, "confirmed_by_event_uid", None),
            "failed_by": getattr(event, "failed_by_event_uid", None),
            "engine_version": ENGINE_VERSION,
            "config_hash": config_hash(),
        }
        if bar is None:
            satir["olculmedi"] = "event_bar_yok"
            satir["sansur"] = True
            satir["devamlilik_sinifi"] = "OLCULEMEDI"
            satirlar.append(satir)
            continue

        bar = int(bar)
        atr_deger = _atr_at(atr, bar)
        referans = float(frame.iloc[bar]["close"]) if 0 <= bar < len(frame) else None
        future = frame.iloc[bar + 1:].to_dict("records")
        gozlenen = len(future)
        en_buyuk = max(olcum.HORIZONLAR)

        if referans is None or yon not in ("UP", "DOWN"):
            satir["olculmedi"] = "referans_yok" if referans is None else "yon_belirsiz"
            satir["sansur"] = True
            satir["devamlilik_sinifi"] = "OLCULEMEDI"
        else:
            yol = olcum.tek_yonlu_yol(yon, referans, future, atr_deger)
            ozet = olcum.yol_ozeti(yol)
            satir.update(_ozet_duzlestir(ozet, "devam_"))
            satir["devamlilik_sinifi"] = devamlilik_sinifi(ozet.get(f"h{en_buyuk}"))
            satir["referans_kapanis"] = _yuvarla(referans)
            satir["atr_at_event"] = _yuvarla(atr_deger)
            satir["gozlenen_bar"] = gozlenen
            satir["sansur"] = bool(gozlenen < en_buyuk)
            # Ters yön uzanımı: event yönünün TERSİ ne kadar gitti. "Tepki
            # uyuştu mu" sorusunun diğer yarısı budur.
            ters = "DOWN" if yon == "UP" else "UP"
            ters_ozet = olcum.yol_ozeti(olcum.tek_yonlu_yol(ters, referans, future, atr_deger))
            satir["ters_h12"] = _yuvarla(ters_ozet.get(f"h{en_buyuk}"))
            satir["uyum"] = "UYUMLU" if (ozet.get(f"h{en_buyuk}") or -1) > 0 else "UYUMSUZ"
        satir.update(olcum.vp_ornek(vp_history, int(bar)))
        satirlar.append(satir)
    return satirlar


def rol_gecmisi_guncelle(
    aktif: dict[tuple[str, str], tuple[int, int]],
    gecmis: list[dict[str, Any]],
    scope: str,
    ctx: Any,
    bar_index: int,
) -> None:
    """Bir bağlam okumasından rol aralığı geçişlerini çıkarır.

    Ayrık bir fonksiyon olmasının sebebi test edilebilirliktir: motor
    olmadan, sahte bağlam dizisiyle aralık mantığı doğrulanabilir.

    Sözleşme: ``aktif[(scope, rol)]`` şu an açık aralığın
    ``(identity, ilk_bar)`` değerini tutar. Kimlik değişmediği sürece
    ``ilk_bar`` **güncellenmez**; aksi halde aralık her bar 1'e çöker.
    """
    if ctx is None:
        return
    for alan, kisaltma in ROL_ALANLARI.items():
        kimlik = int(getattr(ctx, alan, 0) or 0)
        anahtar = (scope, kisaltma)
        onceki = aktif.get(anahtar)
        onceki_kimlik = onceki[0] if onceki is not None else 0
        if onceki_kimlik == kimlik:
            continue
        if onceki is not None:
            gecmis.append({
                "scope": scope,
                "rol": kisaltma,
                "identity": onceki_kimlik,
                "rol_ilk_bar": onceki[1],
                "rol_son_bar": bar_index - 1,
                "rol_sure_bar": (bar_index - 1) - onceki[1] + 1,
                # DEVREDILDI: rolü başka bir swing aldı.
                # TEMIZLENDI: rol 0'a düştü (kimse taşımıyor).
                "kapanis": "DEVREDILDI" if kimlik != 0 else "TEMIZLENDI",
            })
        if kimlik != 0:
            aktif[anahtar] = (kimlik, bar_index)
        else:
            aktif.pop(anahtar, None)


def ms_adimli_kosu(frame: Any, profile: str = "Dengeli") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """MS motorunu bar bar koşturur; final detayları VE rol geçmişini döndürür.

    Neden bar bar? ``structural_role`` zamanla **mutate olan** bir durumdur:
    ``market_structure_state.clear_role_if_matches`` bir rolü yeni bir swing'e
    atadığında aynı rolü taşıyan diğer swing'leri ``NEUTRAL_*``'a sıfırlar.
    Dolayısıyla replay sonundaki ``external_swings`` listesi yalnız rollerin
    *güncel* sahibini gösterir; tarihsel PH/PL/WH/WL atamaları kaybolmuştur.
    THYAO 4h'de ölçülen 359 swing içinde yalnız 2 PROTECTED_HIGH ve 0
    PROTECTED_LOW görünmesinin sebebi budur — bu, OB'deki "silinen zone"
    sorununun MS'deki karşılığıdır ve final snapshot'tan cevaplanamaz.

    Çözüm: her bardan sonra ``StructureContext`` üzerindeki rol kimlikleri
    okunur (O(bar), swing taraması yok) ve kimlik değişimleri aralık olarak
    kaydedilir. Motorun kendi ``replay`` çıktısı ile aynı final state'e
    ulaşılır; ek maliyet yalnız bağlam okumasıdır.
    """
    from domain_engines.market_structure import MarketStructureConfig, MarketStructureEngine

    engine = MarketStructureEngine(config=MarketStructureConfig(profile=profile))
    satirlar = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame)
    aktif: dict[tuple[str, str], tuple[int, int]] = {}
    gecmis: list[dict[str, Any]] = []
    bar_sayisi = len(satirlar)

    for bar_index, row in enumerate(satirlar):
        engine.update(row)
        for scope, ctx in (("EXTERNAL", engine.external_context), ("INTERNAL", engine.internal_context)):
            rol_gecmisi_guncelle(aktif, gecmis, scope, ctx, bar_index)

    # Replay bittiğinde hâlâ açık olan aralıklar: veri sonuna kadar sürdü.
    # Bunlar "rol hiç kaybedilmedi" demektir, sağdan sansürlüdür.
    for (scope, kisaltma), (kimlik, ilk) in aktif.items():
        gecmis.append({
            "scope": scope,
            "rol": kisaltma,
            "identity": kimlik,
            "rol_ilk_bar": ilk,
            "rol_son_bar": bar_sayisi - 1,
            "rol_sure_bar": (bar_sayisi - 1) - ilk + 1,
            "kapanis": "VERI_SONU_SANSURLU",
        })

    details = {
        "external_swings": engine.external_swings,
        "internal_swings": engine.internal_swings,
        "external_candidates": engine.external_candidates,
        "internal_candidates": engine.internal_candidates,
        "event_history": engine.event_history,
        "latest_external_event": engine.latest_external_event,
        "latest_internal_event": engine.latest_internal_event,
        "external_context": engine.external_context,
        "internal_context": engine.internal_context,
    }
    return details, gecmis


def vp_kosu(frame: Any) -> tuple[dict[str, Any], Any, str]:
    """VP motorunu doğrudan koşturur; ``metrics_history`` bar başına indekslenir.

    ``run_domain_engines`` yerine doğrudan çağrı kullanılmasının sebebi
    maliyettir: OB ve FVG zaten ayrı replay ediliyor, dolayısıyla oradan
    geçen dört domain'lik koşu iki domain'i boşa tekrar çalıştırırdı.
    ``to_domain_frame`` ile ``_normalize_frame`` aynı sözleşmeyi üretir
    (küçük harf kolonlar + ``timestamp`` + kronolojik sıra).
    """
    from domain_engines.volume_participation import VolumeParticipationEngine

    engine = VolumeParticipationEngine()
    engine.replay(frame)
    final_export = engine.final_export
    details = {
        "latest_metrics": engine.metrics_history[-1] if engine.metrics_history else None,
        "metrics_history": engine.metrics_history,
        "core_export": engine.export_contract,
        "lifecycle_export": engine.lifecycle_export,
    }
    return details, engine.metrics_history, str(getattr(final_export, "state", "") or "")


def rol_araliklari_by_identity(gecmis: Iterable[Mapping[str, Any]]) -> dict[tuple[str, int], list[dict[str, Any]]]:
    """Rol geçmişini ``(scope, identity)`` anahtarıyla gruplar."""
    grup: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for kayit in gecmis:
        anahtar = (str(kayit.get("scope")), int(kayit.get("identity") or 0))
        grup.setdefault(anahtar, []).append(dict(kayit))
    for degerler in grup.values():
        degerler.sort(key=lambda k: (k["rol_ilk_bar"], k["rol"]))
    return grup


def sembol_timeframe_gozlem(
    symbol: str,
    timeframe: str,
    frame: Any,
    *,
    profile: str = "Dengeli",
    enable_2h_fvg: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Bir sembol x zaman dilimi için tüm gözlem satırlarını üretir."""
    if frame is None or len(frame) == 0:
        return {"zone": [], "dokunus": [], "swing": [], "event": [], "meta": []}

    # TÜM hat boyunca normalize çerçeve kullanılır. Sebep: replay fonksiyonları
    # zone indekslerini bu çerçeveye göre üretir ve build_touch_episodes
    # `frame.at[index, ...]` ile POZİSYONEL erişim yapar. DatetimeIndex
    # verilirse KeyError ile patlar; karışık verilirse indeksler kayar ve
    # ölçüm yanlış bara bağlanır (sessiz hata, en tehlikelisi).
    data = _normalize_frame(frame)

    atr = compute_wilder_atr(data)
    frames_map = {(symbol, timeframe): data}

    # 1) OB: tam popülasyon (silinen zone'lar dahil)
    zones: list[dict[str, Any]] = list(replay_ob_zones(symbol, timeframe, data))

    # 2) FVG: yalnız motorun desteklediği zaman dilimlerinde
    fvg_meta: dict[str, Any] = {}
    if timeframe in FVG_TIMEFRAMELERI:
        fvg_zones, fvg_durum, fvg_isinanma = replay_fvg_zones(symbol, timeframe, data, profile=profile)
        zones.extend(fvg_zones)
        fvg_meta = {"fvg_durum": fvg_durum, "fvg_isinanma": fvg_isinanma}
    else:
        fvg_meta = {"fvg_durum": "ATLANDI_TIMEFRAME", "fvg_isinanma": 0}

    episodes = build_touch_episodes(zones, frames_map)
    zones_by_id = {z["zone_id"]: z for z in zones}
    atr_by_series = {(symbol, timeframe): atr}
    window_rows = build_window_rows(episodes, zones_by_id, frames_map, atr_by_series)

    # 3) MS (bar bar, rol geçmişiyle) + VP (doğrudan): iki geçiş, israf yok.
    # MS ayrı try bloğundadır: motor bazı gerçek BIST serilerinde
    # "confirmed break references must still be active" ile patlar ve bu,
    # canlı runner'ın kullandığı `replay()` yolunda da birebir görülür
    # (AEFES 1h üzerinde doğrulandı). Hata izole edilmezse o sembolün OB/FVG/VP
    # ölçümleri de kaybolur; oysa onlar MS'ten bağımsızdır.
    ms_hata: str | None = None
    try:
        ms_details, rol_gecmisi = ms_adimli_kosu(data, profile=profile)
    except Exception as exc:  # noqa: BLE001 - motor hatası ölçümü durdurmasın
        ms_hata = f"{type(exc).__name__}: {exc}"
        ms_details, rol_gecmisi = {}, []
    vp_details, vp_history, vp_durum = vp_kosu(data)
    rol_grup = rol_araliklari_by_identity(rol_gecmisi)

    dokunuslar = dokunus_satirlari(episodes, window_rows, zones_by_id, data, atr, vp_history)
    swingler = swing_satirlari(ms_details, data, atr, vp_history, rol_grup)
    eventler = event_satirlari(ms_details, data, atr, vp_history)
    for satir in swingler + eventler:
        satir["symbol"] = symbol
        satir["timeframe"] = timeframe

    zone_sat = zone_satirlari(zones, atr, data)
    meta = [{
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_sayisi": len(data),
        "atr_son": _yuvarla(atr[-1]) if atr else None,
        "zone_sayisi": len(zone_sat),
        "ob_zone_sayisi": sum(1 for z in zone_sat if z["family"] == "OB"),
        "fvg_zone_sayisi": sum(1 for z in zone_sat if z["family"] == "FVG"),
        "epizot_sayisi": len(dokunuslar),
        "swing_sayisi": len(swingler),
        "event_sayisi": len(eventler),
        "rol_araligi_sayisi": len(rol_gecmisi),
        "ms_data_quality": "",
        "ms_hata": ms_hata,
        "vp_data_quality": vp_durum,
        "engine_version": ENGINE_VERSION,
        "config_hash": config_hash(),
        **fvg_meta,
    }]
    # 4) FORMASYON: kendi motorunu replay eder; defterin offline karşılığı.
    #    MS rol geçmişi + VP + zone kesişimi aynı geçişte beslenir (ek geçiş yok).
    from research.formasyon import formasyon_kosu

    fiyat_by_swing = {}
    for _sw in (ms_details.get("external_swings") or ()):
        try:
            fiyat_by_swing[(str(getattr(_sw, "scope", "EXTERNAL")), int(getattr(_sw, "identity", 0) or 0))] = float(_sw.price)
        except (TypeError, ValueError, AttributeError):
            continue
    # MS BOS olay barları (FRM-11): teyit ile aynı barda mı?
    ms_bos = []
    for _ev in (ms_details.get("event_history") or ()):
        if str(getattr(_ev, "event_type", "")) != "EVENT_BOS":
            continue
        _bar = getattr(_ev, "event_bar", None)
        if _bar is None:
            continue
        try:
            ms_bos.append((int(_bar), int(getattr(_ev, "direction", 0) or 0)))
        except (TypeError, ValueError):
            continue

    frm, frm_olay, frm_meta = formasyon_kosu(
        data, symbol=symbol, timeframe=timeframe,
        rol_grup=rol_grup, fiyat_by_swing=fiyat_by_swing,
        vp_history=vp_history, zone_rows=zone_sat, ms_olaylari=ms_bos,
    )
    meta[0].update(frm_meta)

    return {"zone": zone_sat, "dokunus": dokunuslar, "swing": swingler, "event": eventler,
            "frm": frm, "frm_olay": frm_olay, "meta": meta}
