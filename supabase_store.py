"""Minimal server-side Supabase REST store for Formation-Bot.

The table stores one JSONB payload per key. If Supabase is not configured or
unavailable, callers keep using the existing local JSON cache without crashing.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)


class SupabaseStore:
    TABLE = "bot_store"
    REQUEST_TIMEOUT_SEC = 8

    def __init__(self, project_url: str, service_key: str, session=None):
        # Kullanici Dashboard'dan "https://<ref>.supabase.co" yerine REST API
        # uc noktasini (https://<ref>.supabase.co/rest/v1/) kopyalayabiliyor.
        # Sondaki slash ve /rest/v1 suffix'i at ki URL iki kez eklenip 404 yemesin.
        self.project_url = project_url.strip().rstrip("/")
        if self.project_url.endswith("/rest/v1"):
            self.project_url = self.project_url[: -len("/rest/v1")]
        self.rest_url = f"{self.project_url}/rest/v1/{self.TABLE}"
        self._session = session or requests.Session()
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        self._disabled_reason: Optional[str] = None
        self._warned: set[str] = set()
        self._retry_after = 0.0

    @classmethod
    def from_env(cls, environ=None) -> Optional["SupabaseStore"]:
        """Create a store from Render secrets; return None for local-only mode."""
        environ = os.environ if environ is None else environ
        project_url = environ.get("SUPABASE_URL", "").strip()
        service_key = (
            environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or environ.get("SUPABASE_SECRET_KEY", "").strip()
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
        return cls(project_url, service_key)

    @property
    def enabled(self) -> bool:
        return self._disabled_reason is None

    def _request(self, method: str, *, params=None, json=None):
        if not self.enabled or time.monotonic() < self._retry_after:
            return None

        for attempt in range(2):
            try:
                response = self._session.request(
                    method,
                    self.rest_url,
                    headers=self._headers,
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
                # Bad key, missing table, or invalid schema is not recoverable by
                # retrying every candle write. Keep the bot running in local mode.
                self._disabled_reason = f"HTTP {response.status_code}"
                self._warn_once(
                    "configuration",
                    f"Supabase tablo/anahtar/izin hatası (HTTP {response.status_code}); "
                    f"bu süreçte Supabase yazımı durduruldu: {detail}",
                )
            else:
                self._retry_after = time.monotonic() + (60 if response.status_code == 429 else 30)
                self._warn_once(
                    "server",
                    f"Supabase isteği başarısız (HTTP {response.status_code}); "
                    f"yerel cache kullanılacak: {detail}",
                )
            return None
        return None

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

    def get_many(self, store_keys: Iterable[str]) -> Optional[Dict[str, Any]]:
        """Fetch multiple keys in one PostgREST request.

        Returns an empty dict for a successful query with no rows, and None when
        Supabase is unavailable so callers can distinguish the two cases.
        """
        keys = list(dict.fromkeys(store_keys))
        if not keys:
            return {}
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
            rows = response.json()
            if not isinstance(rows, list):
                raise TypeError("beklenen liste yerine farklı JSON türü geldi")
            return {
                row["store_key"]: row.get("payload")
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("store_key"), str)
            }
        except (ValueError, TypeError, KeyError) as exc:
            self._warn_once("response", f"Supabase yanıtı okunamadı: {exc}")
            return None

    def upsert_many(self, values: Dict[str, Any]) -> bool:
        """Insert/update key-payload pairs; updated_at is refreshed on every write."""
        if not values:
            return True
        from datetime import datetime, timezone

        updated_at = datetime.now(timezone.utc).isoformat()
        rows = [
            {"store_key": key, "payload": payload, "updated_at": updated_at}
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
