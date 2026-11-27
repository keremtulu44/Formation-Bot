"""AI API istemci katmanı: ApiWrapper (birincil) -> 2× Ücretsiz Gemini (yedek) -> normal alarm.

Sorumluluk sınırı:
  - Canlı bot döngüsüne, taramaya veya Telegram'a kendiliğinden bağlanmaz.
  - Ek ağır SDK bağımlılığı istemez; kurulu `httpx` ile hafif çalışır.
  - ApiWrapper sözleşmesine birebir uyar:
      * Yalnızca `POST {BASE_URL}/v1/ask` çağrılır (başka uç çağrılmaz).
      * `Authorization: Bearer {API_KEY}` ve `Content-Type: application/json`.
      * Gövde: `{"prompt": ...}` + isteğe bağlı `"system"` ve `"model"`.
      * HTTP 200 SSE satırları okunur: yalnız `data:` satırları JSON çözülür;
        boş satırlar ve `:` yorum satırları yok sayılır; yalnız `status`
        (`wait`, `done`, `problem`) alanına bakılır.
      * Bağlanma zaman aşımı 10 sn, okuma sessizlik zaman aşımı 45 sn;
        toplam süre sınırı varsayılan olarak YOKTUR (isteyen çağırıcı
        `max_wall_seconds` verebilir; dolunca bağlantı kapatılır).
      * `problem` alınan soru ApiWrapper'a TEKRAR GÖNDERİLMEZ; hemen yedek
        zincire (`gemini_free_1` -> `gemini_free_2` -> normal alarm) geçilir.
      * Bir sonraki soruda zincir yine en baştan (`ApiWrapper`) başlar.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

import httpx

from secrets_redaction import redact_sensitive_text

from .verdict import parse_ai_response

DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_READ_TIMEOUT_S = 45.0
DEFAULT_WRITE_TIMEOUT_S = 15.0
DEFAULT_POOL_TIMEOUT_S = 10.0

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# Dengeli sabit Gemini yedek modeli (Google AI resmi kararlı Flash modeli,
# Free Tier Standard destekli, 1M bağlam / 65K çıktı, thinking blokları ayıklanır).
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


@dataclass(frozen=True, slots=True)
class AIAttemptRecord:
    """Tek bir sağlayıcı denemesinin özet kaydı (gizli anahtar içermez)."""

    provider: str
    model: str | None
    ok: bool
    outcome: str
    http_status: int | None
    wait_events: int
    elapsed_s: float
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class AIAskResult:
    """Sıralı AI istemci zincirinin kesin sonucu."""

    ok: bool
    text: str | None
    provider: str | None
    model: str | None
    fallback_to_normal_alarm: bool
    total_elapsed_s: float
    attempts: tuple[AIAttemptRecord, ...]


class AIProviderClient(Protocol):
    """Zincirdeki her tekil AI sağlayıcısının ortak arayüzü."""

    name: str
    model: str | None

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[str | None, AIAttemptRecord]:
        ...


def _clean_env_value(value: Any) -> str:
    """Render/yerel env değerlerindeki boşluk ve kazara yapıştırılmış tırnakları temizler."""
    if value is None:
        return ""
    s = str(value).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()


def _normalize_wrapper_ask_url(base_url: str) -> str:
    raw = _clean_env_value(base_url).rstrip("/")
    if not raw or not raw.startswith(("http://", "https://")):
        raise ValueError("ApiWrapper BASE_URL geçerli bir http(s) adresi olmalı")
    if raw.endswith("/v1/ask"):
        return raw
    return f"{raw}/v1/ask"


def _make_httpx_client(
    *,
    connect_timeout: float,
    read_timeout: float,
    write_timeout: float = DEFAULT_WRITE_TIMEOUT_S,
    pool_timeout: float = DEFAULT_POOL_TIMEOUT_S,
    transport: httpx.BaseTransport | None = None,
) -> httpx.Client:
    # `httpx.Timeout` yalnız işlem bazlı süre uygular; toplam süre sınırı koymaz.
    timeout = httpx.Timeout(
        connect=float(connect_timeout),
        read=float(read_timeout),
        write=float(write_timeout),
        pool=float(pool_timeout),
    )
    kwargs: dict[str, Any] = {"timeout": timeout, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    return httpx.Client(**kwargs)


class ApiWrapperClient:
    """ApiWrapper `/v1/ask` SSE istemcisi (kurallara birebir uyumlu)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str | None = None,
        name: str = "api_wrapper",
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout: float = DEFAULT_READ_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ask_url = _normalize_wrapper_ask_url(base_url)
        key = _clean_env_value(api_key)
        if not key:
            raise ValueError("ApiWrapper API_KEY boş olamaz")
        self._api_key = key
        clean_model = _clean_env_value(model)
        self.model = clean_model or None
        self.name = str(name or "api_wrapper")
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self._transport = transport
        self._clock = clock

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[str | None, AIAttemptRecord]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt boş olamaz")
        if max_wall_seconds is not None and float(max_wall_seconds) <= 0:
            raise ValueError("max_wall_seconds pozitif olmalı")

        chosen_model = (
            str(model).strip()
            if model and str(model).strip()
            else self.model
        )
        payload: dict[str, str] = {"prompt": prompt}
        if system and str(system).strip():
            payload["system"] = str(system)
        if chosen_model:
            payload["model"] = chosen_model

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }

        started = self._clock()
        wait_events = 0
        http_status: int | None = None

        def _fail(outcome: str, detail: str | None = None) -> tuple[None, AIAttemptRecord]:
            safe_detail = (
                redact_sensitive_text(detail, self._api_key)
                if detail is not None
                else None
            )
            return None, AIAttemptRecord(
                provider=self.name,
                model=chosen_model,
                ok=False,
                outcome=outcome,
                http_status=http_status,
                wait_events=wait_events,
                elapsed_s=round(max(0.0, self._clock() - started), 3),
                detail=safe_detail,
            )

        effective_read = (
            min(self.read_timeout, float(max_wall_seconds))
            if max_wall_seconds is not None
            else self.read_timeout
        )

        try:
            with _make_httpx_client(
                connect_timeout=self.connect_timeout,
                read_timeout=effective_read,
                transport=self._transport,
            ) as client:
                with client.stream("POST", self.ask_url, headers=headers, json=payload) as resp:
                    http_status = int(resp.status_code)
                    if http_status != 200:
                        return _fail("http_error", f"HTTP {http_status}")

                    for raw_line in resp.iter_lines():
                        if (
                            max_wall_seconds is not None
                            and (self._clock() - started) >= float(max_wall_seconds)
                        ):
                            return _fail("wall_timeout", f"üst süre doldu ({max_wall_seconds}s)")

                        if not raw_line or not raw_line.strip():
                            continue
                        if raw_line.startswith(":"):
                            continue
                        if not raw_line.startswith("data:"):
                            continue

                        json_part = raw_line[5:].strip()
                        if not json_part:
                            return _fail("invalid_payload", "boş data satırı")
                        try:
                            event = json.loads(json_part)
                        except json.JSONDecodeError:
                            return _fail("invalid_payload", "JSON çözülemedi")
                        if not isinstance(event, dict):
                            return _fail("invalid_payload", "JSON nesne değil")

                        status = event.get("status")
                        if status == "wait":
                            wait_events += 1
                            continue
                        if status == "done":
                            text = event.get("text")
                            if not isinstance(text, str) or not text.strip():
                                return _fail("invalid_payload", "done satırında text boş")
                            rec = AIAttemptRecord(
                                provider=self.name,
                                model=chosen_model,
                                ok=True,
                                outcome="done",
                                http_status=http_status,
                                wait_events=wait_events,
                                elapsed_s=round(max(0.0, self._clock() - started), 3),
                                detail=None,
                            )
                            return text, rec
                        if status == "problem":
                            return _fail("problem", "sunucu problem bildirdi")
                        return _fail("invalid_payload", "tanınmayan status değeri")

                    # Akış "done" veya "problem" gelmeden kapandı (kural 4).
                    return _fail("stream_closed", "akış done/problem olmadan kapandı")

        except httpx.ReadTimeout:
            return _fail("read_timeout", f"{int(self.read_timeout)}s okuma sessizliği")
        except httpx.ConnectTimeout:
            return _fail("connect_timeout", f"{int(self.connect_timeout)}s bağlanma zaman aşımı")
        except httpx.HTTPError as exc:
            return _fail("connection_error", type(exc).__name__)


def _extract_gemini_text(body: Mapping[str, Any]) -> str | None:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0]
    if not isinstance(first, Mapping):
        return None
    content = first.get("content")
    if not isinstance(content, Mapping):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        return None
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, Mapping):
            continue
        # Gemini 2.5 thinking parçalarını görünür yanıta karıştırma.
        if part.get("thought") is True:
            continue
        piece = part.get("text")
        if isinstance(piece, str) and piece:
            chunks.append(piece)
    combined = "".join(chunks).strip()
    return combined or None


class GeminiFreeClient:
    """Ücretsiz Gemini REST (`generateContent`) yedek istemcisi (SDK'sız, hafif `httpx`)."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GEMINI_MODEL,
        name: str = "gemini_free_1",
        base_url: str = DEFAULT_GEMINI_BASE_URL,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_S,
        read_timeout: float = DEFAULT_READ_TIMEOUT_S,
        temperature: float | None = 0.2,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        key = _clean_env_value(api_key)
        if not key:
            raise ValueError("Gemini API anahtarı boş olamaz")
        mdl = _clean_env_value(model) or DEFAULT_GEMINI_MODEL
        if not mdl:
            raise ValueError("Gemini model adı boş olamaz")
        root = (_clean_env_value(base_url) or DEFAULT_GEMINI_BASE_URL).rstrip("/")
        if not root.startswith(("http://", "https://")):
            raise ValueError("Gemini base_url geçerli bir http(s) adresi olmalı")

        self._api_key = key
        self.model = mdl
        self.name = str(name or "gemini_free")
        self.endpoint_url = f"{root}/models/{mdl}:generateContent"
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self.temperature = temperature
        self._transport = transport
        self._clock = clock

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_wall_seconds: float | None = None,
    ) -> tuple[str | None, AIAttemptRecord]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt boş olamaz")
        if max_wall_seconds is not None and float(max_wall_seconds) <= 0:
            raise ValueError("max_wall_seconds pozitif olmalı")

        chosen_model = str(model).strip() if model and str(model).strip() else self.model
        url = (
            self.endpoint_url
            if chosen_model == self.model
            else self.endpoint_url.replace(f"/models/{self.model}:", f"/models/{chosen_model}:")
        )
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system and str(system).strip():
            body["system_instruction"] = {"parts": [{"text": str(system)}]}
        if self.temperature is not None:
            body["generationConfig"] = {"temperature": float(self.temperature)}

        # API anahtarı URL sorgu parametresine DEĞİL yalnızca başlığa yazılır.
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        effective_read = (
            min(self.read_timeout, float(max_wall_seconds))
            if max_wall_seconds is not None
            else self.read_timeout
        )

        started = self._clock()
        http_status: int | None = None

        def _fail(outcome: str, detail: str | None = None) -> tuple[None, AIAttemptRecord]:
            safe_detail = (
                redact_sensitive_text(detail, self._api_key)
                if detail is not None
                else None
            )
            return None, AIAttemptRecord(
                provider=self.name,
                model=chosen_model,
                ok=False,
                outcome=outcome,
                http_status=http_status,
                wait_events=0,
                elapsed_s=round(max(0.0, self._clock() - started), 3),
                detail=safe_detail,
            )

        try:
            with _make_httpx_client(
                connect_timeout=self.connect_timeout,
                read_timeout=effective_read,
                transport=self._transport,
            ) as client:
                resp = client.post(url, headers=headers, json=body)
                http_status = int(resp.status_code)
                if http_status != 200:
                    return _fail("http_error", f"HTTP {http_status}")
                try:
                    data = resp.json()
                except ValueError:
                    return _fail("invalid_payload", "JSON çözülemedi")
                if not isinstance(data, dict):
                    return _fail("invalid_payload", "JSON nesne değil")
                text = _extract_gemini_text(data)
                if not text:
                    return _fail("empty_or_blocked", "boş veya filtrelenmiş yanıt")
                return text, AIAttemptRecord(
                    provider=self.name,
                    model=chosen_model,
                    ok=True,
                    outcome="done",
                    http_status=http_status,
                    wait_events=0,
                    elapsed_s=round(max(0.0, self._clock() - started), 3),
                    detail=None,
                )
        except httpx.ReadTimeout:
            return _fail("read_timeout", f"{int(effective_read)}s okuma zaman aşımı")
        except httpx.ConnectTimeout:
            return _fail("connect_timeout", f"{int(self.connect_timeout)}s bağlanma zaman aşımı")
        except httpx.HTTPError as exc:
            return _fail("connection_error", type(exc).__name__)


class AIClientRouter:
    """Sıralı AI istemci yönlendiricisi: ApiWrapper -> Gemini #1 -> Gemini #2 -> normal alarm.

    Her yeni `ask()` çağrısı zinciri EN BAŞTAN (ApiWrapper'dan) dener.
    Bir sağlayıcı başarısız olursa aynı soru ona tekrar gönderilmez; sıradaki
    yedeğe geçilir. Hepsi düşerse `fallback_to_normal_alarm=True` döner.
    """

    def __init__(
        self,
        providers: Sequence[AIProviderClient],
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.providers: tuple[AIProviderClient, ...] = tuple(providers)
        self._clock = clock

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        wrapper_transport: httpx.BaseTransport | None = None,
        gemini_transport: httpx.BaseTransport | None = None,
    ) -> "AIClientRouter":
        source = env if env is not None else os.environ

        def _get(key: str, default: str = "") -> str:
            return _clean_env_value(source.get(key, default))

        providers: list[AIProviderClient] = []

        # 1) Birincil: ApiWrapper (/v1/ask) — model her zaman otomatik (gövdede gönderilmez)
        wrapper_url = _get("AI_WRAPPER_BASE_URL")
        wrapper_key = _get("AI_WRAPPER_API_KEY")
        if wrapper_url and wrapper_key:
            providers.append(
                ApiWrapperClient(
                    wrapper_url,
                    wrapper_key,
                    model=None,
                    name="api_wrapper",
                    transport=wrapper_transport,
                )
            )

        gemini_base = _get("GEMINI_BASE_URL") or DEFAULT_GEMINI_BASE_URL

        # 2) Yedek 1: Ücretsiz Gemini #1 — sabit dengeli model (DEFAULT_GEMINI_MODEL)
        gem_key_1 = _get("GEMINI_API_KEY_1") or _get("GEMINI_API_KEY")
        if gem_key_1:
            providers.append(
                GeminiFreeClient(
                    gem_key_1,
                    model=DEFAULT_GEMINI_MODEL,
                    name="gemini_free_1",
                    base_url=gemini_base,
                    transport=gemini_transport,
                )
            )

        # 3) Yedek 2: Ücretsiz Gemini #2 — sabit dengeli model (DEFAULT_GEMINI_MODEL)
        gem_key_2 = _get("GEMINI_API_KEY_2")
        if gem_key_2:
            providers.append(
                GeminiFreeClient(
                    gem_key_2,
                    model=DEFAULT_GEMINI_MODEL,
                    name="gemini_free_2",
                    base_url=gemini_base,
                    transport=gemini_transport,
                )
            )

        return cls(providers)

    def provider_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.providers)

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_wall_seconds_per_provider: float | None = None,
    ) -> AIAskResult:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt boş olamaz")

        started = self._clock()
        attempts: list[AIAttemptRecord] = []

        for provider in self.providers:
            text, rec = provider.ask(
                prompt,
                system=system,
                max_wall_seconds=max_wall_seconds_per_provider,
            )
            attempts.append(rec)
            if rec.ok and text:
                return AIAskResult(
                    ok=True,
                    text=text,
                    provider=provider.name,
                    model=rec.model,
                    fallback_to_normal_alarm=False,
                    total_elapsed_s=round(max(0.0, self._clock() - started), 3),
                    attempts=tuple(attempts),
                )

        return AIAskResult(
            ok=False,
            text=None,
            provider=None,
            model=None,
            fallback_to_normal_alarm=True,
            total_elapsed_s=round(max(0.0, self._clock() - started), 3),
            attempts=tuple(attempts),
        )

    def ask_bundle(
        self,
        bundle: Mapping[str, Any],
        *,
        parse_response: bool = True,
        require_verdict: bool = False,
        max_wall_seconds_per_provider: float | None = None,
    ) -> dict[str, Any]:
        """`build_api_prompt()` çıktısını (`system` + `user` ayrı) zincire gönderir."""
        result = self.ask(
            str(bundle["user"]),
            system=str(bundle.get("system") or "") or None,
            max_wall_seconds_per_provider=max_wall_seconds_per_provider,
        )
        parsed: dict[str, Any] | None = None
        if result.ok and result.text and parse_response:
            parsed = parse_ai_response(result.text, require_verdict=require_verdict)
        return {
            "result": result,
            "parsed": parsed,
            "fallback_to_normal_alarm": result.fallback_to_normal_alarm,
        }
