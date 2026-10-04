"""Minimal server-side Supabase REST store for Formation-Bot.

The table stores one JSONB payload per key. If Supabase is not configured or
unavailable, callers keep using the existing local JSON cache without crashing.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Dict, Iterable, Optional

import requests

logger = logging.getLogger(__name__)


def _anahtari_temizle(deger: Any) -> str:
    """Env değerlerindeki tırnak/boşluk kirliliğini temizle.

    Kullanıcı Dashboard'dan kopyalarken yanlışlıkla tırnak içinde yapıştırabilir
    veya Render'da boşluk bırakabilir. Değer asla loglanmaz, sadece temizlenir.
    """
    if deger is None:
        return ""
    s = str(deger).strip()
    # Tekrarlayan tırnak sarımını temizle: "\"sb_secret_...\"" -> sb_secret_...
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()


def _jwt_rolu_coz(anahtar: str) -> str:
    """JWT payload'ındaki role alanını okur (imza doğrulaması yapmaz)."""
    if not anahtar or anahtar.count(".") != 2:
        return ""
    if not anahtar.startswith("eyJ"):
        return ""
    try:
        payload = anahtar.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        veri = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8", "replace"))
        return str(veri.get("role", ""))
    except Exception:
        return ""


def anahtar_turu(anahtar: str) -> str:
    """Anahtarın türünü değerini loglamadan döndür.

    - sb_secret_... -> yeni secret key
    - sb_publishable_... -> publishable key (RLS'de yazamaz)
    - eyJ... JWT -> legacy JWT (role bilgisiyle)
    - diğer -> bilinmeyen format
    """
    k = _anahtari_temizle(anahtar)
    if not k:
        return "boş"
    if k.startswith("sb_secret_"):
        return "yeni secret key (sb_secret_)"
    if k.startswith("sb_publishable_"):
        return "publishable key (sb_publishable_)"
    if k.startswith("eyJ") and k.count(".") == 2:
        rol = _jwt_rolu_coz(k)
        if rol == "service_role":
            return "legacy JWT (service_role)"
        if rol == "anon":
            return "legacy JWT (anon)"
        if rol:
            return f"legacy JWT ({rol})"
        return "legacy JWT"
    # sb_ ile başlayan diğer yeni formatlar da apikey-only olmalı
    if k.startswith("sb_"):
        return f"yeni anahtar ({k.split('_')[0]}_{k.split('_')[1] if '_' in k else ''})".strip()
    return "bilinmeyen format"


def supabase_basliklari(service_key: str) -> Dict[str, str]:
    """Supabase REST için doğru başlıkları üret.

    Yeni Supabase anahtarları (sb_secret_..., sb_publishable_...) JWT değildir;
    Authorization: Bearer olarak gönderilirse Supabase 401 \"Invalid JWT\" döner.
    Sadece apikey başlığı gönderilmeli. Legacy eyJ... JWT'lerde eski davranış
    (apikey + Bearer) korunmalı.
    """
    k = _anahtari_temizle(service_key)
    basliklar: Dict[str, str] = {
        "apikey": k,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    # sb_ prefix'li yeni anahtarlar apikey-only
    if k.startswith("sb_"):
        return basliklar
    # Legacy JWT'ler için Bearer ekle
    if k.startswith("eyJ") and k.count(".") == 2:
        basliklar["Authorization"] = f"Bearer {k}"
        return basliklar
    # Bilinmeyen format: güvenli tarafta kal, apikey-only (eski davranışa yakın)
    # Ama eğer JWT'ye benzemiyorsa Bearer ekleme.
    # Eğer kullanıcı eski olmayan ama JWT benzeri bir şey verdiyse Bearer eklemeyelim
    # çünkü 401 Invalid JWT üretir; en azından apikey denenecek.
    # Eski kod her zaman Bearer ekliyordu, şimdi sadece JWT'de ekliyoruz.
    return basliklar


class SupabaseStore:
    TABLE = "bot_store"
    REQUEST_TIMEOUT_SEC = 8
    # C3 (Batch 7): aynı `bot_store` tablosunu paylaşan ikinci bir proje/örnek
    # diğerinin verisini ezmesin diye anahtarlara ön ek eklenir.
    #   SUPABASE_STORE_PREFIX=formation-bot:   (varsayılan)
    #   SUPABASE_STORE_PREFIX=off              (öneksiz, eski davranış)
    # Eski (öneksiz) anahtarlar okunabilir; sonraki yazımda ön ekli hâle taşınır.
    VARSAYILAN_PREFIX = "formation-bot:"

    def __init__(self, project_url: str, service_key: str, session=None, prefix=None):
        # Kullanici Dashboard'dan \"https://<ref>.supabase.co\" yerine REST API
        # uc noktasini (https://<ref>.supabase.co/rest/v1/) kopyalayabiliyor.
        # Sondaki slash ve /rest/v1 suffix'i at ki URL iki kez eklenip 404 yemesin.
        temiz_url = _anahtari_temizle(project_url).rstrip("/")
        if temiz_url.endswith("/rest/v1"):
            temiz_url = temiz_url[: -len("/rest/v1")]
        self.project_url = temiz_url

        temiz_key = _anahtari_temizle(service_key)
        self._service_key = temiz_key  # debug için değil, sadece header üretiminde
        if prefix is None:
            ham_prefix = os.environ.get("SUPABASE_STORE_PREFIX")
            if ham_prefix is None:
                prefix = self.VARSAYILAN_PREFIX
            else:
                prefix = _anahtari_temizle(ham_prefix)
                if prefix.lower() in ("off", "none", "yok", "0"):
                    prefix = ""
        self.prefix = prefix or ""
        self._legacy_uyarildi = False
        self.rest_url = f"{self.project_url}/rest/v1/{self.TABLE}"
        self._session = session or requests.Session()
        self._headers = supabase_basliklari(temiz_key)

        self._disabled_reason: Optional[str] = None
        self._warned: set[str] = set()
        self._retry_after = 0.0

        # Anahtar türünü logla (değer asla loglanmaz)
        try:
            tur = anahtar_turu(temiz_key)
            logger.info(f"Supabase anahtar türü: {tur}")
            if temiz_key.startswith("sb_publishable_"):
                logger.warning(
                    "Supabase publishable key (sb_publishable_) kullanıyorsun; "
                    "RLS açıkken bu anahtar bot_store tablosuna yazamaz ve 401/403 alır. "
                    "Doğrusu: sb_secret_... veya legacy service_role JWT (eyJ...)."
                )
        except Exception:
            pass

    @classmethod
    def from_env(cls, environ=None) -> Optional["SupabaseStore"]:
        """Create a store from Render secrets; return None for local-only mode."""
        environ = os.environ if environ is None else environ
        project_url = _anahtari_temizle(environ.get("SUPABASE_URL", ""))
        service_key = _anahtari_temizle(
            environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or environ.get("SUPABASE_SECRET_KEY", "")
        )
        if not project_url and not service_key:
            logger.info("Supabase env tanımlı değil; mevcut yerel cache ile devam ediliyor")
            return None
        if not project_url or not service_key:
            logger.error(
                "Supabase env eksik: SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY birlikte gerekli; "
                "yerel cache ile devam edilecek"
            )
            return None

        # Anahtar türünü env aşamasında da logla (değer yok)
        try:
            tur = anahtar_turu(service_key)
            logger.info(f"Supabase anahtar türü: {tur}")
            if service_key.startswith("sb_publishable_"):
                logger.warning(
                    "Supabase publishable key (sb_publishable_) kullanıyorsun; "
                    "RLS açıkken bu anahtar bot_store tablosuna yazamaz ve 401/403 alır. "
                    "Doğrusu: sb_secret_... veya legacy service_role JWT (eyJ...)."
                )
        except Exception:
            pass

        return cls(project_url, service_key)

    @property
    def enabled(self) -> bool:
        return self._disabled_reason is None

    def request_table(self, table_name: str, method: str, *, params=None, json=None, headers=None):
        """Herhangi bir PostgREST tablosuna istek atar (f2_* tabloları ve bot_store)."""
        if not self.enabled or time.monotonic() < self._retry_after:
            return None

        url = f"{self.project_url}/rest/v1/{table_name}"
        req_headers = dict(self._headers)
        if headers:
            req_headers.update(headers)

        for attempt in range(2):
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=req_headers,
                    params=params,
                    json=json,
                    timeout=self.REQUEST_TIMEOUT_SEC,
                )
            except requests.RequestException as exc:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                self._retry_after = time.monotonic() + 30
                self._warn_once("network", f"Supabase bağlantı hatası; yerel cache kullanılacak: {exc}")
                return None

            if 200 <= response.status_code < 300:
                return response

            # Rate limit / server errors may be transient; retry once only.
            if (response.status_code == 429 or response.status_code >= 500) and attempt == 0:
                time.sleep(0.5)
                continue

            detail = (getattr(response, "text", "") or "")[:300]
            if 400 <= response.status_code < 500 and response.status_code != 429:
                if table_name == self.TABLE:
                    self._disabled_reason = f"HTTP {response.status_code}"
                self._warn_once(
                    f"config_{table_name}",
                    f"Supabase {table_name} tablo/anahtar/izin hatası (HTTP {response.status_code}); "
                    f"yerel cache kullanılacak: {detail}",
                )
            else:
                self._retry_after = time.monotonic() + (60 if response.status_code == 429 else 30)
                self._warn_once(
                    f"server_{table_name}",
                    f"Supabase {table_name} isteği başarısız (HTTP {response.status_code}); "
                    f"yerel cache kullanılacak: {detail}",
                )
            return None
        return None

    def _request(self, method: str, *, params=None, json=None):
        return self.request_table(self.TABLE, method, params=params, json=json)

    def _warn_once(self, category: str, message: str) -> None:
        if category not in self._warned:
            self._warned.add(category)
            logger.warning(message)

    def ping(self) -> bool:
        """Başlangıçta bağlantı/tablo/anahtar doğrulaması (tek satır SELECT).

        Render ortam değişkenleri yanlışsa (404 tablo yok, 401/403 anahtar
        geçersiz) hata mesajını loga düşürür; bot yerel cache ile çalışmaya
        devam eder. Mesaj göndermez, veri değiştirmez.
        """
        response = self._request("GET", params={"select": "store_key", "limit": 1})
        if response is None:
            return False
        logger.info(f"Supabase bağlantısı OK ({self.project_url}, tablo: {self.TABLE})")
        return True

    def _uzak_anahtar(self, yerel: str) -> str:
        return f"{self.prefix}{yerel}" if self.prefix else yerel

    def _yerel_anahtar(self, uzak: str) -> str:
        if self.prefix and uzak.startswith(self.prefix):
            return uzak[len(self.prefix):]
        return uzak

    def _satirlari_oku(self, response):
        rows = response.json()
        if not isinstance(rows, list):
            raise TypeError("beklenen liste yerine farklı JSON türü geldi")
        return {
            self._yerel_anahtar(row["store_key"]): row.get("payload")
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("store_key"), str)
        }

    def _tek_istek(self, keys) -> Optional[Dict[str, Any]]:
        response = self._request(
            "GET",
            params={
                "select": "store_key,payload",
                "store_key": f"in.({','.join(keys)})",
            },
        )
        if response is None:
            return None
        try:
            return self._satirlari_oku(response)
        except (ValueError, TypeError, KeyError) as exc:
            self._warn_once("response", f"Supabase yanıtı okunamadı: {exc}")
            return None

    def get_many(self, store_keys: Iterable[str]) -> Optional[Dict[str, Any]]:
        """Fetch multiple keys in one PostgREST request.

        Returns an empty dict for a successful query with no rows, and None when
        Supabase is unavailable so callers can distinguish the two cases.

        C3: istek ön ekli anahtarlarla yapılır; bulunamayanlar için eski
        (öneksiz) anahtarlarla ikinci bir tur atılır. Böylece ön ek devreye
        girerken mevcut veri kaybolmaz ve sonraki yazımda taşınır.
        """
        keys = list(dict.fromkeys(store_keys))
        if not keys:
            return {}
        sonuc = self._tek_istek([self._uzak_anahtar(k) for k in keys])
        if sonuc is None:
            return None
        eksik = [k for k in keys if k not in sonuc]
        if self.prefix and eksik:
            legacy = self._tek_istek(eksik)
            if legacy:
                sonuc.update(legacy)
                if not self._legacy_uyarildi:
                    self._legacy_uyarildi = True
                    logger.info(
                        "Supabase'de ön eksiz (legacy) %d anahtar bulundu; ön ek '%s' "
                        "devrede, bir sonraki yazımda taşınır.",
                        len(legacy), self.prefix,
                    )
        return sonuc

    def upsert_many(self, values: Dict[str, Any]) -> bool:
        """Insert/update key-payload pairs; updated_at is refreshed on every write."""
        if not values:
            return True
        from datetime import datetime, timezone

        updated_at = datetime.now(timezone.utc).isoformat()
        rows = [
            {"store_key": self._uzak_anahtar(key), "payload": payload, "updated_at": updated_at}
            for key, payload in values.items()
        ]
        response = self._request(
            "POST",
            params={"on_conflict": "store_key"},
            json=rows,
        )
        return response is not None

    def upsert(self, store_key: str, payload: Any) -> bool:
        return self.upsert_many({store_key: payload})

    # --- çoklu örnek tespiti (Batch 6 / B10) -------------------------------
    ORNEK_ANAHTARI = "state:instances"
    ORNEK_TTL_SN = 180          # bu süre içinde görülen başka kayıt "canlı" sayılır
    ORNEK_TEMIZLIK_SN = 86400   # 1 günden eski kayıtlar temizlenir

    def ornek_bildir(self, instance_id: str, now_iso: str = "") -> Optional[dict]:
        """Bu örneğin yaşadığını yazar ve BAŞKA canlı örnek var mı diye bakar.

        Neden: aynı token + aynı Supabase anahtarıyla iki kopya çalışırsa çift mesaj
        gider ve cache yarışır. Yoklama modunda Telegram 409 veriyordu; webhook
        modunda böyle bir koruma yoktu. Burası sert bir kilit kurmaz (kısa ağ
        kesintisinde botu durdurmak daha kötü olurdu) ama durumu görünür kılar.
        """
        from datetime import datetime, timezone
        simdi = datetime.now(timezone.utc)
        ham = self.get_many([self.ORNEK_ANAHTARI])
        if ham is None:
            return None  # Supabase erişilemez: sessizce vazgeç (bot durmasın)
        kayitlar = ham.get(self.ORNEK_ANAHTARI)
        if not isinstance(kayitlar, dict):
            kayitlar = {}
        temiz = {
            str(k): str(v) for k, v in kayitlar.items()
            if isinstance(v, str) and self._iso_taze(v, simdi, self.ORNEK_TEMIZLIK_SN)
        }
        temiz[instance_id] = (now_iso or simdi.isoformat())
        self.upsert(self.ORNEK_ANAHTARI, temiz)
        canli = [
            {"id": k, "son_gorulme": v} for k, v in temiz.items()
            if k != instance_id and self._iso_taze(v, simdi, self.ORNEK_TTL_SN)
        ]
        return {"canli_digerleri": canli, "kayit_sayisi": len(temiz)}

    @staticmethod
    def _iso_taze(zaman: str, simdi, azami_sn: int) -> bool:
        from datetime import datetime, timezone
        try:
            t = datetime.fromisoformat(str(zaman))
        except (TypeError, ValueError):
            return False
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (simdi - t).total_seconds() <= azami_sn
