"""Gölge zincir kayıt modelleri — §3 bildiri şeması ve işlem yaşam döngüsü.

Kırmızı çizgiler burada şemada gömülüdür:
* ``kaynak`` içinde ``n=`` yoksa kayıt yazılamaz (uydurma yasağı);
* ``bilinmeyenler`` boş plan kaydı olamaz (dürüst kayıt);
* sıfat yok, sayı var: ``Hukum`` yalnız hüküm + sayaç taşır.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

KIMLER = frozenset({"stabil", "formasyon", "ms", "blok"})
IDDIALAR = frozenset({
    "uyari", "izle", "bekle", "olasi_tepki", "onay_bekliyor",
    "konfluans", "onay", "bozulma",
})
HUKUMLER = frozenset({"BEKLE", "UYGUN", "RET"})
DIREKTLER = frozenset({"bekle", "takip_et", "haber_ver"})
SONUCLAR = frozenset({"hedef", "stop", "yok", "zaman"})
YONLER = frozenset({"long", "short"})
KAYIT_TIPLERI = frozenset({
    "bildirim", "hukum", "plan", "sonuc", "sessizlik", "zincir_ozet",
})
# Kaynak kanıtı: "tablo · n=123" biçiminde olmak zorunda (sayısız cümle yasak).
import re

_KAYNAK_N = re.compile(r"(?:^|[^a-zA-Z])n\s*=\s*\d+", re.IGNORECASE)


def kaynak_dogrula(kaynak: str) -> str:
    """Kaynak kanıtı: boş olamaz ve ``n=`` sayı barındırmak zorunda."""
    if not isinstance(kaynak, str) or not kaynak.strip():
        raise ValueError("kaynak bos olamaz")
    if not _KAYNAK_N.search(kaynak):
        raise ValueError(f"kaynak 'n=' icermez (uydurma yasagi): {kaynak!r}")
    return kaynak.strip()


@dataclass(frozen=True, slots=True)
class Bildirim:
    """Katmanın ölçülü konuşması (sözleşme §3). Karar vermez, görev + seviye verir."""

    tip: str = "bildirim"
    sembol: str = ""
    tf: str = ""
    t: str = ""                      # karar anı (kapanmış bar zamanı, ISO)
    kim: str = ""                    # stabil | formasyon | ms | blok
    iddia: str = ""                  # §3 iddia kümesi
    kosul: str = ""                  # iddianin kosulu
    kaynak: str = ""                 # olcum tablosu + n=…
    gecerlilik_bar: int = 0          # bitis: kac bar sonra soner
    seviyeler: tuple[float, ...] = ()
    uyari_metni: str = ""
    dogrudan: str = ""               # bekle | takip_et | haber_ver (varsa)

    def __post_init__(self) -> None:
        if self.tip != "bildirim":
            raise ValueError(f"tip 'bildirim' olmali: {self.tip!r}")
        if self.kim not in KIMLER:
            raise ValueError(f"gecersiz kim: {self.kim!r}")
        if self.iddia not in IDDIALAR:
            raise ValueError(f"gecersiz iddia: {self.iddia!r}")
        if not self.kosul or not self.kosul.strip():
            raise ValueError("kosul bos olamaz")
        kaynak_dogrula(self.kaynak)
        if self.gecerlilik_bar < 0:
            raise ValueError("gecerlilik_bar negatif olamaz")
        if self.dogrudan and self.dogrudan not in DIREKTLER:
            raise ValueError(f"gecersiz dogrudan: {self.dogrudan!r}")
        if not self.sembol or not self.tf or not self.t:
            raise ValueError("sembol/tf/t zorunlu")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["seviyeler"] = [float(x) for x in self.seviyeler]
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Bildirim":
        p = dict(d)
        p["seviyeler"] = tuple(float(x) for x in p.get("seviyeler") or ())
        p.pop("tip", None)
        return cls(**p)


@dataclass(frozen=True, slots=True)
class Hukum:
    """TYR'nin tek satır hükmü: sayı var, sıfat yok (sözleşme §4.6)."""

    tip: str = "hukum"
    sembol: str = ""
    tf: str = ""
    t: str = ""
    hukum: str = ""                  # BEKLE | UYGUN | RET
    lehte: int = 0
    celisi: int = 0
    gerekce: str = ""

    def __post_init__(self) -> None:
        if self.tip != "hukum":
            raise ValueError(f"tip 'hukum' olmali: {self.tip!r}")
        if self.hukum not in HUKUMLER:
            raise ValueError(f"gecersiz hukum: {self.hukum!r}")
        if self.lehte < 0 or self.celisi < 0:
            raise ValueError("sayaclar negatif olamaz")
        if not self.gerekce or not self.gerekce.strip():
            raise ValueError("gerekce bos olamaz")
        if not self.sembol or not self.tf or not self.t:
            raise ValueError("sembol/tf/t zorunlu")

    @property
    def satir(self) -> str:
        return f"{self.hukum} · {self.lehte} lehte · {self.celisi} celişki"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["satir"] = self.satir
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Hukum":
        p = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        p.pop("satir", None)
        return cls(**p)


@dataclass(frozen=True, slots=True)
class PlanKaydi:
    """İşlem planı — plandır, sinyal değildir (kırmızı çizgi 8).

    v1 zincir long tez üretir (destek/alt-bant tepkisi); ``yon`` alanı kısa
    tez için de doğrulamalıdır (stop < giriş < hedef zorunlu değil — yön'e göre).
    """

    tip: str = "plan"
    plan_id: str = ""
    sembol: str = ""
    tf: str = ""
    t: str = ""                      # tetik (onay) barı zamanı
    yon: str = "long"
    giris: float = 0.0               # tetik barının kapanışı
    band_lo: float = 0.0             # G5 giriş bandı
    band_hi: float = 0.0
    stop: float = 0.0                # tez ölümü
    hedef: float = 0.0               # en yakin karsit yapi
    R: float = 0.0
    zaman_stopu: int = 10
    bilinmeyenler: tuple[str, ...] = ()
    hukum_satiri: str = ""
    kaynak_bildirimler: tuple[str, ...] = ()
    donem: str = ""                  # kesif | dogrulama (sembol-bası kronolojik %70/%30)
    bar_index: int = -1              # tetik bar indeksi (örtüşmesizlik ölçümü için)

    def __post_init__(self) -> None:
        if self.tip != "plan":
            raise ValueError(f"tip 'plan' olmali: {self.tip!r}")
        if self.yon not in YONLER:
            raise ValueError(f"gecersiz yon: {self.yon!r}")
        if not self.plan_id or not self.sembol or not self.tf or not self.t:
            raise ValueError("plan_id/sembol/tf/t zorunlu")
        if not self.bilinmeyenler:
            raise ValueError("bilinmeyenler satiri zorunlu (durluk kaydi)")
        if self.zaman_stopu <= 0:
            raise ValueError("zaman_stopu pozitif olmali")
        if self.donem not in ("", "kesif", "dogrulama"):
            raise ValueError(f"gecersiz donem: {self.donem!r}")
        if self.yon == "long":
            if not (self.stop < self.giris < self.hedef):
                raise ValueError("long planda stop < giris < hedef zorunlu")
        else:
            if not (self.hedef < self.giris < self.stop):
                raise ValueError("short planda hedef < giris < stop zorunlu")
        if self.band_lo > self.band_hi:
            raise ValueError("band_lo > band_hi olamaz")
        beklenen = round((self.hedef - self.giris) / (self.giris - self.stop), 4) \
            if self.yon == "long" else \
            round((self.giris - self.hedef) / (self.stop - self.giris), 4)
        if abs(beklenen - self.R) > 0.01:
            raise ValueError(f"R tutarsiz: yazilan {self.R}, hesap {beklenen}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["bilinmeyenler"] = list(self.bilinmeyenler)
        d["kaynak_bildirimler"] = list(self.kaynak_bildirimler)
        return d

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PlanKaydi":
        p = dict(d)
        p["bilinmeyenler"] = tuple(p.get("bilinmeyenler") or ())
        p["kaynak_bildirimler"] = tuple(p.get("kaynak_bildirimler") or ())
        return cls(**p)


@dataclass(frozen=True, slots=True)
class IslemSonucu:
    """İleri yarış sonucu (sansür ``yok``; aynı barda çift dokunuş → stop)."""

    tip: str = "sonuc"
    plan_id: str = ""
    sembol: str = ""
    tf: str = ""
    t: str = ""
    sonuc: str = ""                  # hedef | stop | yok
    cozunme_bar: int | None = None   # girişten sonraki bar (1..H)
    pnl_atr: float = 0.0             # +T / -S / 0 (maliyetsiz, ATR birimi)
    mae_atr: float = 0.0             # çözüm öncesi en kötü geri çekilme (ATR, negatif)
    kural: str = "kural_yok"         # kural_yok | streak_atla | tavan_atla
    maliyetli: bool = False          # False: ham yarış (maliyet ölçümde ayrı)

    def __post_init__(self) -> None:
        if self.tip != "sonuc":
            raise ValueError(f"tip 'sonuc' olmali: {self.tip!r}")
        if self.sonuc not in SONUCLAR:
            raise ValueError(f"gecersiz sonuc: {self.sonuc!r}")
        if not self.plan_id or not self.sembol or not self.tf or not self.t:
            raise ValueError("plan_id/sembol/tf/t zorunlu")
        if self.sonuc == "yok" and self.cozunme_bar is not None:
            raise ValueError("sansurde cozunme_bar olamaz")
        if self.sonuc == "zaman" and (self.cozunme_bar is None or self.cozunme_bar <= 0):
            raise ValueError("zaman cikisinda cozunme_bar zorunlu")
        if self.kural not in {"kural_yok", "streak_atla", "tavan_atla"}:
            raise ValueError(f"gecersiz kural: {self.kural!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "IslemSonucu":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
