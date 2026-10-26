# grafik/kare.py — kare dosya I/O, disk, kare listesi (Faz 2).

from __future__ import annotations

import io
import textwrap
import logging
import math
import os
import shutil
import tempfile
import time
import uuid
import threading
from functools import wraps
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from reporting.format import sayi
import chart_experience as deneyim
from telegram_measure import SATIR_BUTCE, genislik as _genislik_16

import grafik as _pkg  # yamalı adlar için geç bağlama (plan §3)

log = logging.getLogger("grafik")  # eski kayıt adıyla aynı (__name__ yerine)

from grafik.core import (  # noqa: F401
    grafik_aktif_mi,
    grafik_kare_adedi,
)
from grafik.tarama import (  # noqa: F401
    anlik_goruntu,
)
from grafik.render import (  # noqa: F401
    ciz,
)

KARE_DESEN = "fb_grafik_"          # /tmp süpürme deseni (§4: bayat kare birikmesin)


KARE_OMR_SN = 6 * 3600             # açılışta bu kadar saatlik kare çöpü silinir


DISK_MIN_BOS_MB = 200              # bundan az yer varsa kare üretilmez (§4)


def kare_yolu(sembol: Any, tf: Any) -> str:
    """Geçici PNG yolu (§4): `DATA_DIR` DIŞINDA, adı uuid'li, tek kullanımlık.

    Neden /tmp: depo dizinine yazmak kalıcılık yollarını (Supabase yedeği,
    `bot_data` okuma-önce kuralı) kirletirdi; uuid ise aynı hissenin iki karesinin
    çakışmaması ve gönderimden sonra silinebilmesi için.
    """
    ad = "".join(ch for ch in str(sembol or "").upper() if ch.isalnum())[:12] or "SEM"
    tf_kisa = "".join(ch for ch in str(tf or "1h").lower() if ch.isalnum()) or "tf"
    return os.path.join(tempfile.gettempdir(),
                        f"{KARE_DESEN}{ad}_{tf_kisa}_{uuid.uuid4().hex[:8]}.png")


def bayat_kareleri_supur(simdi: Optional[float] = None) -> int:
    """Açılışta eski `fb_grafik_*.png` dosyalarını siler; silinen sayısını döner.

    Neden: gönderim yarıda kesilirse (çökme/restart) dosya /tmp'de kalıyor ve
    Render'ın sınırlı diskini doldurur. Yalnız kendi desenimize dokunur.
    """
    sayac = 0
    try:
        dizin = tempfile.gettempdir()
        simdi = time.time() if simdi is None else float(simdi)
        for ad in os.listdir(dizin):
            if not (ad.startswith(KARE_DESEN) and ad.endswith(".png")):
                continue
            yol = os.path.join(dizin, ad)
            try:
                # Yalnız OWN deseni + TTL'den eski: canlı başka bir sürecin az önce
                # yazdığı kareyi silmek gönderimi sessizce bozardı.
                if simdi - os.path.getmtime(yol) < KARE_OMR_SN:
                    continue
                os.remove(yol)
                sayac += 1
            except OSError:
                continue    # başka süreç tutuyor olabilir: sessiz geç
    except OSError as hata:   # pragma: no cover - /tmp okunamazsa sorun değil
        log.debug("grafik: bayat kare süpürülemedi (%s)", hata)
    return sayac


def disk_uygun_mu() -> bool:
    """Diskte yer var mı? Ölçülemezse EVET (üretimi keyfi engellememek için)."""
    try:
        return shutil.disk_usage(tempfile.gettempdir()).free >= DISK_MIN_BOS_MB * 1024 * 1024
    except OSError:
        return True


_MOTOR_ANAHTARLARI = ("order_block", "fvg", "market_structure", "volume_participation")


def _sonuc_sec(sonuclar: Any, tf: str, *, cikis: Optional[dict[str, Any]] = None) -> Any:
    """`sonuclar`dan bu TF'nin motor çıktısını çıkarır (iki biçim de geçerli).

    Neden çözümleyici: tarama turu sonuçları `zaman dilimi → çıktı` sözlüğü olarak
    taşınıyor (`domain_results_by_stock[sembol]`), CLI ise TEK TF'nin çıktısını
    veriyor. Köprü ilk sürümünde birincil kareye TF'yle İÇ İÇE sözlüğü geçirdi ve
    bölge/yapı katmanları SESİZCE boş kaldı — bu yüzden biçim tanınmazsa artık bir
    uyarı satırı bırakıyoruz, sessiz boş kare yok.
    """
    if not sonuclar:
        return None
    if isinstance(sonuclar, Mapping):
        if tf in sonuclar:
            return sonuclar.get(tf) or None
        if any(ad in sonuclar for ad in _MOTOR_ANAHTARLARI):
            return sonuclar                  # tek TF'lik çıktı (CLI biçimi)
        if cikis is not None:
            cikis["uyarilar"].append(f"{tf}: motor çıktıları tanınamadı (katmanlar çizilmedi)")
    return sonuclar                            # nesne biçimi: olduğu gibi ilet


# Alarm türleri: geçersizleşmede TEK kare (geçersizleşen TF), diğer olaylarda
# `TELEGRAM_GRAFIK_ADET`. GÖRSEL-4 kullanıcı kararı: "geçersizleşince görsel
# sadece geçersizleşen timeframede gelecek" — diğer TF'lerde o karede çizilecek
# bant/alarm YOK, yani üç ek kare neredeyse boş gidiyordu.
_TEK_KARE_ALARM = frozenset({"gecersiz"})


def kare_listesi(cift: Any = None, tf: str = "1h", cerceve: Any = None, *,
                 sonuclar: Optional[Mapping[str, Any]] = None,
                 ek_cerceveler: Optional[Mapping[str, Any]] = None,
                 alarm_turu: Optional[str] = None, alarm_bar: Optional[int] = None,
                 sembol: str = "", zaman_damgasi: Any = None,
                 adet: Optional[int] = None,
                 simdi: Optional[datetime] = None) -> dict[str, Any]:
    """Tarama anında payload'a eklenecek kare sözlükleri (§4 köprüsü).

    Kartın beslendiği AYNI `cift`/`sonuclar` kullanılır; bu yüzden kare ile kart
    aynı veriyi anlatır. `ek_cerceveler` {tf: çerçeve} — birincil TF her zaman
    İLK karedir, kalanları `TELEGRAM_GRAFIK_ADET` kadar eklenir; fazlası kesilir
    ve `kota`da sayılır (veri kusuru değil, görüntü sınırı → dipnot yazılmaz).
    `alarm_turu="gecersiz"` (geçersizleşme) istisnadır: yalnız birincil TF'nin
    karesi üretilir (GÖRSEL-4).

    Dönüş: `{"sembol", "goruntular": [goruntu...], "kota": int, "uyarilar": [...]}`;
    kill-switch kapalıysa veya çerçeve yoksa `goruntular` boş döner (çağıran
    taraf bundan hiçbir şey kaybetmez).
    """
    cikti: dict[str, Any] = {"sembol": str(sembol or ""), "goruntular": [], "kota": 0,
                             "uyarilar": []}
    if not grafik_aktif_mi():
        return cikti
    tf = str(tf or "1h")
    sinir = int(grafik_kare_adedi() if adet is None else adet)
    if str(alarm_turu or "").strip().lower() in _TEK_KARE_ALARM:
        ek_cerceveler = {}
    plan: list[tuple[str, Any, Optional[Mapping[str, Any]]]] = [
        (tf, cerceve, _sonuc_sec(sonuclar, tf, cikis=cikti))]
    for ek_tf, ek_cerceve in (ek_cerceveler or {}).items():
        ek_tf = str(ek_tf or "")
        if not ek_tf or ek_tf == tf or ek_cerceve is None:
            continue
        plan.append((ek_tf, ek_cerceve, _sonuc_sec(sonuclar, ek_tf, cikis=cikti)))
    if len(plan) > sinir:
        cikti["kota"] = len(plan) - sinir
        plan = plan[:sinir]
    for sira, (kare_tf, kare_cerceve, kare_sonuclar) in enumerate(plan):
        birincil = sira == 0
        try:
            cikti["goruntular"].append({
                "tf": kare_tf,
                # Bant ve alarm SADECE birincil kareye çizilir: `start_bar`/
                # `alarm_bar` o çerçevenin mum indeksleridir; diğer TF'nin
                # kadrajına taşımak yanlız konum değil, sahte „bant teması" sayısı
                # de üretirdi (duman ölçümünde 1s karesi 266 temas saydı).
                "goruntu": anlik_goruntu(cift if birincil else None, kare_tf, kare_cerceve,
                                         sonuclar=kare_sonuclar,
                                         alarm_turu=alarm_turu if birincil else None,
                                         alarm_bar=alarm_bar if birincil else None,
                                         sembol=sembol,
                                         zaman_damgasi=_zaman_bul(kare_cerceve, zaman_damgasi),
                                         simdi=simdi),
            })
        except Exception as hata:   # pragma: no cover - kare alarmı düşürmesin
            log.warning("grafik: kare hazırlanamadı (%s %s): %s", sembol, kare_tf, hata)
            cikti["uyarilar"].append(f"{kare_tf}: {type(hata).__name__}")
    for kare in cikti["goruntular"][1:]:
        kare["goruntu"]["notlar"].append(
            "bant/alarm diğer zaman dilimine ait: bu karede çizilmedi (§14.1)")
    return cikti


def _zaman_bul(cerceve: Any, varsayilan: Any) -> Any:
    """Karenin „son kapanan" satırı kendi çerçevesinin son barından okunur."""
    try:
        deger = cerceve.index[-1]
        return deger if deger is not None else varsayilan
    except Exception:
        return varsayilan


def kareyi_yaz(goruntu: Mapping[str, Any], tf: str, *, serit: bool = True,
               beklenen_son_bar_ts: Any = None) -> tuple[Optional[str], dict[str, Any]]:
    """Bir kareyi diske yazar: `(yol, meta)`. Hata → `(None, meta)`; görsel alarmı
    asla engellemez (§4). Yol çağrıandan gelir: gönderim sonrası O siler.
    """
    hedef = _pkg.kare_yolu(goruntu.get("sembol"), tf)
    yol = None
    try:
        yol, meta = ciz(goruntu, tf, secenekler={
            "cikti": hedef,
            "serit": serit,
            "beklenen_son_bar_ts": beklenen_son_bar_ts,
        })
        return yol, meta
    finally:
        if yol is None:
            try:
                os.remove(hedef)
            except OSError:
                pass


