# --- TELEGRAM NOTIFIER - İNSANLAŞTIRMA V2 + KANAL MODELİ ---
# Tek sistem, gürültü azaltma, public kanal desteği

import os
import logging
import random
import re
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from config import DATA_DIR, ISTANBUL_TZ, TELEGRAM_MAX_MESAJ_SAAT, TELEGRAM_MAX_MESAJ_GUN
from notification_outbox import NotificationOutbox
from telegram_alert_flow import STATE_TR
from formation_dm_context import display_price

logger = logging.getLogger(__name__)


def _local_now_naive() -> datetime:
    """Consistent Istanbul wall-clock for persisted notifier cooldown/cap state."""
    return datetime.now(ISTANBUL_TZ).replace(tzinfo=None)


def _atomic_json_write(path: str, payload: dict, *, indent=None) -> None:
    """Replace persisted notifier state atomically so a restart cannot read a half JSON file."""
    import json

    directory = os.path.dirname(path) or "."
    temporary_path = path + ".tmp"
    os.makedirs(directory, exist_ok=True)
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=indent)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass


PATTERN_EMOJI = {
    "Yükselen Üçgen": "🔺",
    "Alçalan Üçgen": "🔻",
    "Simetrik Üçgen": "🔷",
    "Yükselen Kama": "📐⬆️",
    "Alçalan Kama": "📐⬇️",
    "Boğa Bayrağı": "🚩🐂",
    "Ayı Bayrağı": "🚩🐻",
    "Boğa Flaması": "🎏🐂",
    "Ayı Flaması": "🎏🐻",
}

KRITIK_STATELER = (
    "KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI",
    "KIRILIM_DENEMESI", "BASARISIZ_KIRILIM",
)

TF_HUMAN = {
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
}

DM_TF_LABEL = {"1h": "1H", "2h": "2H", "4h": "4H", "1d": "1D"}
DM_STATE_LABELS = {
    "ADAY_OLUSUYOR": "ADAY OLUŞUYOR",
    "GEOMETRI_ADAYI": "GEOMETRİ ADAYI",
    "FORMASYON_TANIMLANDI": "FORMASYON TANIMLANDI",
    "SIKISMA_GUCLENIYOR": "SIKIŞMA GÜÇLENİYOR",
    "KIRILIM_HAZIRLIGI": "KIRILIM HAZIRLIĞI",
    "KIRILIM_DENEMESI": "KIRILIM DENEMESİ",
    "KIRILIM_ADAYI": "KIRILIM ADAYI",
    "KIRILIM_TEYITLI": "KIRILIM TEYİTLİ",
    "RETEST_BEKLENIYOR": "RETEST BEKLENİYOR",
    "RETEST_EDILIYOR": "RETEST EDİLİYOR",
    "RETEST_BASARILI": "RETEST BAŞARILI",
    "FORMASYON_TAMAMLANDI": "FORMASYON TAMAMLANDI",
    "BASARISIZ_KIRILIM": "BAŞARISIZ KIRILIM",
    "FORMASYON_GECERSIZ": "FORMASYON GEÇERSİZ",
}

def yon_metni(deger) -> str:
    """Kırılım yön kodunu görüntüleme katmanında Türkçe metne çevirir.

    İç temsil kodda ölçülmüştür: break_dir=1 yukarı kırılım (main.py: kritik seviye
    upper_now seçilir; format_dm_message 'yukarı' der), -1 aşağı kırılım. Bilinmeyen,
    eksik veya 0 değeri tahmin edilmez; boş metin döner (mesaja yön yazılmaz).
    """
    try:
        kod = int(deger)
    except (TypeError, ValueError, OverflowError):
        return ""
    if kod > 0:
        return "yukarı"
    if kod < 0:
        return "aşağı"
    return ""


def quality_comment(q: float) -> str:
    if q >= 85:
        return "çok güçlü"
    elif q >= 75:
        return "güçlü"
    elif q >= 65:
        return "orta"
    else:
        return "zayıf"

def quality_emoji(q: float) -> str:
    if q >= 85:
        return "⭐⭐⭐"
    elif q >= 75:
        return "⭐⭐"
    elif q >= 65:
        return "⭐"
    else:
        return "〰️"

def _env_temizle(deger) -> str:
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()

def token_bicimi_uygun_mu(token: str) -> bool:
    t = _env_temizle(token)
    if not t:
        return False
    if ":" not in t:
        return False
    parcalar = t.split(":", 1)
    if len(parcalar) != 2:
        return False
    ilk, ikinci = parcalar
    if not ilk.isdigit():
        return False
    if len(ilk) < 5:
        return False
    if len(ikinci) < 20:
        return False
    if not re.match(r"^[A-Za-z0-9_\-]+$", ikinci):
        return False
    return True

def telegram_hata_ipucu(status_code: int, response_text: str = "") -> str:
    txt = (response_text or "").lower()
    if status_code == 401:
        return (
            "Token geçersiz veya iptal edilmiş (401). "
            "@BotFather'dan token'ı tam kopyala, Render → Environment → TELEGRAM_BOT_TOKEN'ı güncelle. "
            "Sızdıysa /revoke ile iptal edip yeni bot aç."
        )
    if status_code == 404:
        return (
            "Bot bulunamadı veya endpoint yanlış (404). "
            "Token doğru mu? URL https://api.telegram.org/bot<token>/... olmalı. "
            "BotFather'da bot silinmiş olabilir."
        )
    if "chat not found" in txt:
        return (
            "Sohbet bulunamadı (chat not found). "
            "Kendi botuna Telegram'da /start yaz, sonra tekrar dene. "
            "chat_id yanlışsa @userinfobot'tan Id'yi tekrar al."
        )
    if "bot was blocked" in txt or "blocked" in txt:
        return (
            "Bot engellenmiş (bot was blocked): Telegram'da bot sohbetinde Unblock yap, "
            "engellenmiş olabilir, /start ile yeniden başlat."
        )
    if status_code == 400:
        return (
            "İstek hatalı (400). chat_id sayı mı, mesaj boş mu? "
            "@userinfobot'tan Id'yi tekrar al, grup için -100... ile başlayan id kullan. "
            "Sohbet bulunamadı (chat not found) ise kendi botuna /start yaz. "
            "Mesaj çok uzun veya biçim hatalı olabilir."
        )
    if status_code == 403:
        return (
            "Bot bu sohbete mesaj gönderemiyor (403). "
            "Kendi botuna Telegram'da bir kez /start yaz, engeli kaldır, engellenmiş olabilir. "
            "Grup ise botu gruba ekle ve admin yap. chat not found ise botla hiç konuşmamışsındır. "
            "Unblock yapman gerekebilir."
        )
    if status_code == 409:
        return (
            "Aynı token'ı iki yer aynı anda dinliyor (409 Conflict). "
            "Termux/PC'de açık kalan ikinci kopyayı kapat, Render'da tek instance çalışmalı. "
            "getUpdates aynı anda iki süreçten çağrılamaz."
        )
    return f"Telegram hatası HTTP {status_code}: {response_text[:200]}"


class TelegramNotifier:
    def __init__(self, persistent_store=None, initial_store_data=None):
        self.persistent_store = persistent_store
        self.initial_store_data = initial_store_data if isinstance(initial_store_data, dict) else {}
        self.token = _env_temizle(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        self.chat_id = _env_temizle(os.environ.get("TELEGRAM_CHAT_ID", ""))
        self.channel_id = _env_temizle(os.environ.get("TELEGRAM_CHANNEL_ID", ""))
        self.cooldown_hours = 4
        self.last_sent: Dict[str, datetime] = {}
        self.max_saatlik = TELEGRAM_MAX_MESAJ_SAAT
        self.max_gunluk = TELEGRAM_MAX_MESAJ_GUN
        self._saatlik_zamanlar: List[datetime] = []
        self._gunluk_sayac = 0
        self._gunluk_tarih = _local_now_naive().date()
        self._kap_uyarildi = False
        self._cooldown_dosya = os.path.join(os.path.dirname(DATA_DIR) or ".", "bot_data", "telegram_soguma.json")
        self._kap_dosya = os.path.join(os.path.dirname(self._cooldown_dosya), "telegram_kap.json")
        self._delivery_interval_seconds = 1.0
        self._outbox = NotificationOutbox(
            os.path.join(DATA_DIR, "telegram_delivery.json"),
            persistent_store=persistent_store,
            initial_state=self.initial_store_data.get("state:telegram_delivery"),
        )
        self._cooldown_yukle()
        self._kap_yukle()

        try:
            from config import PUBLIC_MIN_QUALITY, PUBLIC_STATES, PUBLIC_SIKISMA_MIN_CONTRACTION
            self.public_min_quality = PUBLIC_MIN_QUALITY
            self.public_states = set(PUBLIC_STATES)
            self.public_sikisma_min = PUBLIC_SIKISMA_MIN_CONTRACTION
        except Exception:
            self.public_min_quality = 80
            self.public_states = {"FORMASYON_TAMAMLANDI", "RETEST_BASARILI"}
            self.public_sikisma_min = 0.80

        if not self.token or not self.chat_id:
            logger.warning("Telegram token/chat_id env'de yok - notifier pasif (test modu)")
            self.enabled = False
        else:
            if self.channel_id:
                logger.info(f"Telegram public kanal aktif: {self.channel_id} (DM + kanal)")
            if not token_bicimi_uygun_mu(self.token):
                logger.warning("Telegram token biçimi uygun değil (beklenen 123456789:AA...). Kontrol et.")
            self.enabled = True
            logger.info("Telegram notifier aktif - insanlaştırma V2 + kanal")

    def _send_text_direct(self, text: str, chat_id: str):
        """One transport attempt. Success requires Telegram HTTP 200 and JSON ok=true."""
        if not self.enabled:
            logger.info("[MOCK TELEGRAM]\n%s\n", text[:500])
            return True, 200, "mock delivery", None, False
        if not chat_id:
            return False, 400, "chat_id is not configured", None, True
        try:
            import requests
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            payload = {}
            try:
                payload = response.json()
            except Exception:
                pass
            if response.status_code == 200 and payload.get("ok") is True:
                return True, 200, "Telegram confirmed ok=true", None, False
            detail = (getattr(response, "text", "") or "")[:200]
            status = int(response.status_code)
            retry_after = None
            try:
                retry_after = float(payload.get("parameters", {}).get("retry_after"))
            except (TypeError, ValueError, AttributeError):
                pass
            permanent = 400 <= status < 500 and status != 429
            return False, status, detail or f"Telegram ok={payload.get('ok')}", retry_after, permanent
        except Exception as exc:
            return False, 0, f"{type(exc).__name__}: {exc}"[:200], None, False

    def _cooldown_key_for_job(self, item: dict) -> str:
        return self._cooldown_key(
            item.get("stock", ""), item.get("pattern", ""), item.get("timeframe", ""),
            item.get("state", ""), event_id=item.get("event_id"),
            destination=item.get("destination", "dm"),
        )

    def _job_policy(self, item: dict):
        """Return (allowed, wait_seconds, terminal_reason) without consuming a send cap."""
        if not item.get("policy"):
            return True, 0.0, None
        event_id = item.get("event_id")
        key = self._cooldown_key_for_job(item)
        if key in self.last_sent:
            return False, 0.0, "confirmed by persisted cooldown"
        destination = item.get("destination", "dm")
        route_base_key = self._cooldown_key(
            item.get("stock", ""), item.get("pattern", ""), item.get("timeframe", ""),
            item.get("state", ""), destination=destination,
        )
        if event_id and route_base_key in self.last_sent:
            elapsed = _local_now_naive() - self.last_sent[route_base_key]
            if elapsed <= timedelta(hours=self.cooldown_hours):
                return False, 0.0, "suppressed by pre-event cooldown migration"
        elif not event_id and route_base_key in self.last_sent:
            elapsed = _local_now_naive() - self.last_sent[route_base_key]
            if elapsed <= timedelta(hours=self.cooldown_hours):
                return False, 0.0, "legacy state cooldown"
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        if self._gunluk_sayac >= self.max_gunluk:
            tomorrow = (_local_now_naive() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return False, max(60.0, (tomorrow - _local_now_naive()).total_seconds()), None
        if len(self._saatlik_zamanlar) >= self.max_saatlik and item.get("state") not in KRITIK_STATELER:
            return False, 3600.0, None
        return True, 0.0, None

    def drain_outbox(self, *, max_items: int = 10, only_ids=None) -> list[dict]:
        """Deliver due jobs independently; a bad/permanent item cannot stop later jobs."""
        sent = self._outbox.unacknowledged_sent(limit=max_items)
        attempted = 0
        max_items = max(1, int(max_items))
        allowed_ids = set(only_ids) if only_ids is not None else None
        for candidate in self._outbox.due_items(limit=max_items * 2):
            if attempted >= max_items:
                break
            item_id = candidate["id"]
            if allowed_ids is not None and item_id not in allowed_ids:
                continue
            allowed, wait_seconds, terminal_reason = self._job_policy(candidate)
            if terminal_reason:
                # If the cooldown was written after Telegram success but before
                # outbox acknowledgement, treat it as confirmed, not a duplicate.
                if terminal_reason == "confirmed by persisted cooldown":
                    self._outbox.mark_sent(item_id, confirmed_by_cooldown=True)
                    sent.append({**candidate, "recovered_confirmation": True})
                else:
                    self._outbox.mark_retry(item_id, terminal_reason, permanent=True)
                continue
            if not allowed:
                self._outbox.defer(item_id, wait_seconds)
                continue

            last_attempt = self._outbox.last_attempt()
            now_utc = datetime.now(timezone.utc)
            if last_attempt is not None:
                delay = self._delivery_interval_seconds - (now_utc - last_attempt).total_seconds()
                if delay > 0:
                    time.sleep(delay)
            item = self._outbox.claim(item_id)
            if item is None:
                continue
            attempted += 1
            self._outbox.set_last_attempt(datetime.now(timezone.utc))
            success, status, detail, retry_after, permanent = self._send_text_direct(
                item["text"], item.get("chat_id", "")
            )
            if success:
                if item.get("policy"):
                    self.last_sent[self._cooldown_key_for_job(item)] = _local_now_naive()
                    self._cooldown_kaydet()
                    if item.get("destination") == "dm":
                        self._gonderim_kaydet()
                self._outbox.mark_sent(item_id)
                sent.append(item)
                logger.info("Telegram outbox delivered id=%s route=%s", item_id[:12], item.get("destination"))
                continue

            if status == 429:
                delay_seconds = retry_after if retry_after is not None else None
            else:
                delay_seconds = None
            self._outbox.mark_retry(
                item_id, f"HTTP {status}: {detail}", delay_seconds=delay_seconds, permanent=permanent
            )
            logger.error(
                "Telegram outbox delivery failed id=%s route=%s status=%s detail=%s",
                item_id[:12], item.get("destination"), status, detail,
            )
        return sent

    def _queue_text(self, text: str, *, destination: str, chat_id: str, identity: str,
                    metadata: Optional[dict] = None, prepared: bool = False):
        item_id = self._outbox.make_id(identity, destination)
        existing = self._outbox.get(item_id)
        if existing is not None:
            return item_id, existing, False
        item = {
            "destination": destination,
            "chat_id": str(chat_id or ""),
            "text": str(text),
            "identity": identity,
            **(metadata or {}),
        }
        saved, created = self._outbox.enqueue(item_id, item, prepared=prepared)
        return item_id, saved, created

    def send_text(self, text: str, *, idempotency_key: Optional[str] = None):
        if not self.enabled:
            return False, "Telegram notifier pasif (token/chat_id env'de yok)"
        if idempotency_key is None:
            success, status, detail, _retry_after, _permanent = self._send_text_direct(text, self.chat_id)
            return success, "mesaj gönderildi" if success else f"HTTP {status}: {detail}"

        item_id, item, created = self._queue_text(
            text, destination="scheduled_dm", chat_id=self.chat_id,
            identity=f"scheduled:{idempotency_key}", metadata={"kind": "scheduled"},
        )
        if item is None:
            return False, "Telegram outbox could not persist/schedule the message"
        if item.get("status") == "sent":
            return True, "already delivered (idempotency key)"
        if item.get("status") in {"dead", "expired"}:
            return False, f"scheduled message is {item.get('status')}: {item.get('last_error')}"
        self.drain_outbox(max_items=1, only_ids={item_id})
        latest = self._outbox.get(item_id) or item
        return (latest.get("status") == "sent", "message sent" if latest.get("status") == "sent"
                else f"pending retry ({latest.get('last_error') or 'delivery deferred'})")

    def persist_watch_state(self, snapshot: dict, *, remote: bool = True) -> bool:
        return self._outbox.set_watch(snapshot, remote=remote)

    def load_watch_state(self) -> Optional[dict]:
        return self._outbox.get_watch()

    def acknowledge_delivery(self, item_id: str) -> bool:
        return self._outbox.acknowledge_delivery(item_id)

    def activate_prepared_fallbacks(self, *, stock: Optional[str] = None) -> int:
        """Unblock a same-process prepared event after a per-symbol exception."""
        activated = 0
        normalized_stock = str(stock).strip().upper() if stock is not None else None
        for item in self._outbox.prepared_items():
            if normalized_stock and str(item.get("stock", "")).upper() != normalized_stock:
                continue
            fallback = item.get("fallback_text") or item.get("text")
            if fallback and self._outbox.activate_prepared(
                item["id"], fallback, {"fallback_activated_after_symbol_error": True}
            ):
                activated += 1
        return activated

    def event_delivery_id(self, data: Dict, destination: str = "dm") -> Optional[str]:
        identity = self._formation_identity(data)
        return self._outbox.make_id(identity, destination) if identity is not None else None

    def check_connection(self) -> bool:
        if not self.enabled:
            return False
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{self.token}/getMe", timeout=10
            )
            if resp.status_code == 200:
                username = (resp.json().get("result") or {}).get("username", "?")
                logger.info(f"Telegram bağlantısı OK (bot: @{username}, chat_id: {self.chat_id})")
                return True
            ipucu = telegram_hata_ipucu(resp.status_code, resp.text)
            logger.error(f"Telegram token/chat_id reddedildi: HTTP {resp.status_code} {resp.text[:200]} | {ipucu}")
        except Exception as e:
            logger.error(f"Telegram bağlantı hatası (token yanlış olabilir): {e}")
        return False

    def should_send_to_public(self, data: Dict) -> bool:
        state = data.get('state', '')
        quality = data.get('confidence_score', 0)
        if state not in self.public_states:
            if state == "SIKISMA_GUCLENIYOR":
                contraction = data.get('contraction', 0) or 0
                if contraction >= self.public_sikisma_min and quality >= self.public_min_quality:
                    return False
            return False
        if quality < self.public_min_quality:
            return False
        return True

    def send_to_channel(self, text: str, *, idempotency_key: Optional[str] = None) -> bool:
        if idempotency_key is not None:
            if self.enabled and not self.channel_id:
                logger.debug("CHANNEL_ID yok, kanala gönderim atlandı")
                return False
            destination = self.channel_id or "mock-channel"
            item_id, item, _created = self._queue_text(
                text, destination="scheduled_channel", chat_id=destination,
                identity=f"scheduled:{idempotency_key}", metadata={"kind": "scheduled"},
            )
            if item is None:
                return False
            if item.get("status") == "sent":
                return True
            if item.get("status") in {"dead", "expired"}:
                return False
            self.drain_outbox(max_items=1, only_ids={item_id})
            latest = self._outbox.get(item_id) or item
            return latest.get("status") == "sent"
        if not self.enabled:
            logger.info(f"[MOCK CHANNEL] {text[:120]}")
            return True
        if not self.channel_id:
            logger.debug("CHANNEL_ID yok, kanala gönderim atlandı")
            return False
        success, status, detail, _retry_after, _permanent = self._send_text_direct(text, self.channel_id)
        if success:
            logger.info(f"Telegram kanala gönderildi: {self.channel_id}")
            return True
        logger.error(f"Telegram kanal hatası HTTP {status}: {detail}")
        return False

    def format_daily_summary(self, aktif_formasyonlar: List[Dict], gun_ozeti: Dict = None) -> str:
        now = datetime.now(ISTANBUL_TZ)
        baslik = f"📊 BIST Formasyon Özeti - {now.strftime('%d %b %H:%M')}\n"
        baslik += "─" * 30 + "\n"
        if not aktif_formasyonlar:
            baslik += "Şu an aktif yüksek kaliteli formasyon yok.\nTakipteyim 👀\n"
            return baslik
        sirali = sorted(aktif_formasyonlar, key=lambda x: x.get('confidence_score', 0), reverse=True)[:10]
        tamamlanan = [f for f in aktif_formasyonlar if f.get('state') == 'FORMASYON_TAMAMLANDI']
        retest = [f for f in aktif_formasyonlar if f.get('state') == 'RETEST_BASARILI']
        sikisan = [f for f in aktif_formasyonlar if f.get('state') == 'SIKISMA_GUCLENIYOR' and (f.get('contraction', 0) or 0) >= self.public_sikisma_min]
        if tamamlanan:
            baslik += f"\n🏁 TAMAMLANAN ({len(tamamlanan)}):\n"
            for f in tamamlanan[:3]:
                baslik += f"• {f.get('stock_name')} {f.get('pattern_name')} {f.get('timeframe')} - Kalite {f.get('confidence_score',0):.0f}\n"
        if retest:
            baslik += f"\n🎯 RETEST BAŞARILI ({len(retest)}):\n"
            for f in retest[:3]:
                yon = yon_metni(f.get("break_dir"))
                yon_parca = f" - {yon} yön" if yon else ""
                baslik += f"• {f.get('stock_name')} {f.get('pattern_name')}{yon_parca}\n"
        if sikisan:
            baslik += f"\n⚡ SIKIŞANLAR ({len(sikisan)}):\n"
            for f in sikisan[:5]:
                baslik += f"• {f.get('stock_name')} %{(f.get('contraction',0)*100):.0f} daralma - {f.get('pattern_name')}\n"
        if gun_ozeti:
            baslik += f"\n📈 Gün: {gun_ozeti.get('stocks_scanned',0)} hisse tarandı, {gun_ozeti.get('alerts_sent',0)} alert\n"
        baslik += "\n💡 Detay için kanalı takipte kal - yatırım tavsiyesi değildir"
        return baslik

    def _kap_yukle(self):
        """Merge local/remote cap state conservatively; stale remote must not win."""
        import json

        sources = []
        remote = self.initial_store_data.get("state:telegram_caps")
        if isinstance(remote, dict):
            sources.append(("Supabase", remote))
        if os.path.exists(self._kap_dosya):
            try:
                with open(self._kap_dosya, "r", encoding="utf-8") as stream:
                    local = json.load(stream)
                if isinstance(local, dict):
                    sources.append(("disk", local))
            except Exception as exc:
                logger.warning("Local Telegram cap state unreadable; using other source: %s", exc)
        candidates = []
        for source, value in sources:
            try:
                day = datetime.fromisoformat(str(value["gunluk_tarih"])).date()
                timezone_name = value.get("timezone")
                host_day = datetime.now().date()
                istanbul_day = _local_now_naive().date()
                # Legacy snapshots were written with host-local naive dates. If
                # a UTC host straddles Istanbul midnight, carry today's count
                # forward rather than silently resetting the cap early.
                if timezone_name != "Europe/Istanbul" and host_day != istanbul_day and day == host_day:
                    day = istanbul_day
                count = max(0, int(value.get("gunluk_sayac", 0)))
                times = []
                raw_times = value.get("saatlik", [])
                if isinstance(raw_times, list):
                    for raw_time in raw_times:
                        try:
                            stamp = datetime.fromisoformat(raw_time)
                            # Naive legacy values are interpreted in the host
                            # timezone used by the previous writer.
                            stamp = stamp.astimezone(ISTANBUL_TZ).replace(tzinfo=None)
                            times.append(stamp)
                        except (TypeError, ValueError):
                            continue
                candidates.append((day, count, times, source))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                logger.warning("Ignoring malformed %s Telegram cap snapshot: %s", source, exc)
        if not candidates:
            return
        newest_day = max(candidate[0] for candidate in candidates)
        same_day = [candidate for candidate in candidates if candidate[0] == newest_day]
        # On equal-day snapshots, maximum count and union of hourly timestamps
        # fail closed (may throttle slightly, never erase an observed send).
        self._gunluk_tarih = newest_day
        self._gunluk_sayac = max(candidate[1] for candidate in same_day)
        self._saatlik_zamanlar = sorted({stamp for candidate in same_day for stamp in candidate[2]})
        logger.info(
            "Telegram cap state merged from %s: hourly=%d daily=%d date=%s",
            "+".join(candidate[3] for candidate in same_day),
            len(self._saatlik_zamanlar), self._gunluk_sayac, newest_day,
        )

    def _gonderim_kaydet(self):
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        self._saatlik_zamanlar.append(_local_now_naive())
        self._gunluk_sayac += 1
        self._kap_kaydet()

    def _kap_kaydet(self):
        payload = {
            "gunluk_sayac": self._gunluk_sayac,
            "gunluk_tarih": self._gunluk_tarih.isoformat(),
            "saatlik": [
                (ISTANBUL_TZ.localize(t) if t.tzinfo is None else t.astimezone(ISTANBUL_TZ)).isoformat()
                for t in self._saatlik_zamanlar
            ],
            "updated_at": datetime.now(ISTANBUL_TZ).isoformat(),
            "timezone": "Europe/Istanbul",
        }
        try:
            _atomic_json_write(self._kap_dosya, payload)
        except Exception as e:
            logger.debug(f"Kap hafızası kaydedilemedi: {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_caps", payload)

    def _gunu_sifirla_gerekirse(self):
        bugun = _local_now_naive().date()
        if bugun != self._gunluk_tarih:
            self._gunluk_sayac = 0
            self._gunluk_tarih = bugun
            self._kap_uyarildi = False

    def _saatligi_temizle(self):
        sinir = _local_now_naive() - timedelta(hours=1)
        self._saatlik_zamanlar = [t for t in self._saatlik_zamanlar if t > sinir]

    def kap_durumu(self) -> Dict:
        self._saatligi_temizle()
        self._gunu_sifirla_gerekirse()
        return {
            "saatlik": len(self._saatlik_zamanlar),
            "saatlik_limit": self.max_saatlik,
            "gunluk": self._gunluk_sayac,
            "gunluk_limit": self.max_gunluk,
        }

    def _cooldown_yukle(self):
        """Merge local/remote per-key timestamps; keep the newest observed value."""
        import json

        sources = []
        remote = self.initial_store_data.get("state:telegram_cooldowns")
        if isinstance(remote, dict):
            sources.append(("Supabase", remote))
        if os.path.exists(self._cooldown_dosya):
            try:
                with open(self._cooldown_dosya, "r", encoding="utf-8") as stream:
                    local = json.load(stream)
                if isinstance(local, dict):
                    sources.append(("disk", local))
            except Exception as exc:
                logger.warning("Local Telegram cooldown state unreadable; using other source: %s", exc)
        now = _local_now_naive()
        for source, values in sources:
            for key, raw_time in values.items():
                if not isinstance(key, str) or not isinstance(raw_time, str):
                    continue
                try:
                    parsed = datetime.fromisoformat(raw_time)
                    # Older app versions stored host-local naive timestamps;
                    # astimezone() preserves that legacy interpretation.
                    parsed = parsed.astimezone(ISTANBUL_TZ).replace(tzinfo=None)
                except (TypeError, ValueError, OverflowError):
                    continue
                retention = timedelta(days=30) if "|event:" in key else timedelta(hours=self.cooldown_hours)
                if parsed < now - retention:
                    continue
                existing = self.last_sent.get(key)
                if existing is None or parsed > existing:
                    self.last_sent[key] = parsed
        logger.info(
            "Telegram cooldown state merged from %s: %d active key(s)",
            "+".join(source for source, _ in sources) or "default",
            len(self.last_sent),
        )

    def _cooldown_kaydet(self):
        now = _local_now_naive()
        retained = {}
        for key, value in self.last_sent.items():
            if value.tzinfo is not None:
                value = value.astimezone(ISTANBUL_TZ).replace(tzinfo=None)
            retention = timedelta(days=30) if "|event:" in key else timedelta(hours=self.cooldown_hours)
            if value >= now - retention:
                retained[key] = value
        self.last_sent = retained
        payload = {
            key: (ISTANBUL_TZ.localize(value) if value.tzinfo is None else value.astimezone(ISTANBUL_TZ)).isoformat()
            for key, value in self.last_sent.items()
        }
        try:
            _atomic_json_write(self._cooldown_dosya, payload, indent=0)
        except Exception as e:
            logger.warning(f"Cooldown kaydedilemedi (devam ediliyor): {e}")
        if self.persistent_store is not None:
            self.persistent_store.upsert("state:telegram_cooldowns", payload)

    def _cooldown_key(
        self,
        stock: str,
        pattern: str,
        timeframe: str,
        state: str,
        event_id: Optional[str] = None,
        destination: str = "dm",
    ) -> str:
        key = f"{stock}_{pattern}_{timeframe}_{state}"
        if destination != "dm":
            key = f"{destination}|{key}"
        if event_id:
            key = f"{key}|event:{event_id}"
        return key

    def can_send(
        self,
        stock: str,
        pattern: str,
        timeframe: str,
        state: str = "",
        event_id: Optional[str] = None,
        destination: str = "dm",
    ) -> bool:
        key = self._cooldown_key(
            stock, pattern, timeframe, state, event_id=event_id, destination=destination
        )
        # Event identities are permanent within the retained cooldown record;
        # unlike the legacy state cooldown, they do not reopen after four hours.
        if event_id and key in self.last_sent:
            return False
        # One-time route-specific migration protection for pre-event cooldown keys.
        legacy_key = self._cooldown_key(
            stock, pattern, timeframe, state, destination=destination
        )
        if event_id and legacy_key in self.last_sent:
            elapsed = _local_now_naive() - self.last_sent[legacy_key]
            if elapsed <= timedelta(hours=self.cooldown_hours):
                return False
        if key not in self.last_sent:
            cooldown_tamam = True
        else:
            elapsed = _local_now_naive() - self.last_sent[key]
            cooldown_tamam = elapsed > timedelta(hours=self.cooldown_hours)
        if not cooldown_tamam:
            return False
        self._gunu_sifirla_gerekirse()
        self._saatligi_temizle()
        if self._gunluk_sayac >= self.max_gunluk:
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.error(f"TELEGRAM GÜNLÜK KAPANI AŞILDI ({self.max_gunluk} mesaj) - bugün başka mesaj gönderilmeyecek.")
            return False
        if len(self._saatlik_zamanlar) >= self.max_saatlik:
            if state in KRITIK_STATELER:
                return True
            if not self._kap_uyarildi:
                self._kap_uyarildi = True
                logger.warning(f"TELEGRAM SAATLİK KAPANI AŞILDI ({self.max_saatlik} mesaj/saat) - sadece kritik sinyaller.")
            return False
        return True

    def format_message(self, data: Dict) -> str:
        stock = data.get('stock_name', 'Bilinmiyor')
        timeframe = data.get('timeframe', '1h')
        pattern = data.get('pattern_name', 'Formasyon')
        state = data.get('state', 'ADAY_OLUSUYOR')
        quality = data.get('confidence_score', 0)
        price = data.get('critical_price_level', 0)
        timestamp = data.get('timestamp', _local_now_naive())
        break_dir = data.get('break_dir', 0)
        upper = data.get('upper_now', price)
        lower = data.get('lower_now', price)
        contraction = data.get('contraction', None)
        retest_seen = data.get('retest_seen', True)
        upper_touches = data.get('upper_touches', None)
        lower_touches = data.get('lower_touches', None)
        age_bars = data.get('age_bars', None)
        mtf_destek = data.get('mtf_destek', False)

        tf_human = TF_HUMAN.get(timeframe, timeframe)
        emoji = PATTERN_EMOJI.get(pattern, "📈")
        q_comment = quality_comment(quality)
        q_emoji = quality_emoji(quality)

        if isinstance(timestamp, str):
            time_str = timestamp
        else:
            try:
                time_str = timestamp.strftime("%d %b %H:%M")
            except:
                time_str = str(timestamp)

        contraction_str = ""
        if contraction is not None:
            pct = contraction * 100
            if pct >= 80:
                contraction_str = f"daralma %{pct:.0f} - baya sıkışmış"
            elif pct >= 60:
                contraction_str = f"daralma %{pct:.0f} - sıkışıyor"
            elif pct >= 40:
                contraction_str = f"daralma %{pct:.0f}"
            else:
                contraction_str = f"daralma %{pct:.0f} - erken"

        temas_str = ""
        if upper_touches is not None and lower_touches is not None:
            toplam = upper_touches + lower_touches
            temas_str = f", {toplam} temas"
        yas_str = f", {age_bars} bar" if age_bars else ""
        mtf_str = " + 4h destekliyor" if mtf_destek else ""

        if state == "ADAY_OLUSUYOR":
            templates = [
                f"{emoji} {stock} {tf_human} grafikte {pattern} oluşuyor...\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}), {contraction_str}{temas_str}{yas_str}\n"
                f"Üst {upper:.2f} / Alt {lower:.2f} bandında sıkışma var\n"
                f"Takipteyiz 👀 - kırılıma yaklaştıkça haber veririm",
                f"👀 {stock}'da bir şeyler oluyor\n"
                f"{tf_human} grafikte {pattern} {q_comment} duruyor (kalite {quality:.0f}){temas_str}\n"
                f"{contraction_str}, bant {lower:.2f} - {upper:.2f}\n"
                f"Henüz erken ama radarımda 📡",
            ]
            msg = random.choice(templates)

        elif state == "GEOMETRI_ADAYI":
            msg = (
                f"{emoji} {stock} {tf_human} - {pattern} geometrisi oturuyor\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}{temas_str}\n"
                f"Bant: {lower:.2f} - {upper:.2f}\n"
                f"Olgunlaşmasını bekliyorum..."
            )

        elif state == "FORMASYON_TANIMLANDI":
            msg = (
                f"📋 {stock} {tf_human} {pattern} tanımlandı\n"
                f"Kalite {quality:.0f} {q_emoji} ({q_comment}) {contraction_str}{temas_str}{yas_str}\n"
                f"Üst: {upper:.2f} Alt: {lower:.2f}\n"
                f"Sıkışma güçlenirse kırılım gelebilir"
            )

        elif state == "SIKISMA_GUCLENIYOR":
            msg = (
                f"⚡ {stock}'da sıkışma güçleniyor!\n"
                f"{tf_human} {pattern} {contraction_str}{temas_str}{yas_str} - sona yaklaşıyor\n"
                f"Kalite {quality:.0f} {q_emoji}, bant {lower:.2f}-{upper:.2f}\n"
                f"Kırılım yakın olabilir, gözüm üstünde 👁️"
            )

        elif state == "KIRILIM_HAZIRLIGI":
            msg = (
                f"⚠️ {stock} {tf_human} {pattern} kırılım hazırlığında\n"
                f"{contraction_str}, kalite {quality:.0f} {q_emoji}{temas_str}\n"
                f"Kritik seviyeler: {lower:.2f} / {upper:.2f}\n"
                f"Birkaç mum içinde hareket gelebilir"
            )

        elif state == "KIRILIM_DENEMESI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            msg = (
                f"🔥 {stock}'da deneme var!\n"
                f"{tf_human} {pattern} {direction} {level:.2f}'i zorluyor\n"
                f"Güç henüz düşük, teyit bekliyorum...{mtf_str}\n"
                f"Kalite {quality:.0f} {q_emoji} | {time_str}"
            )

        elif state == "KIRILIM_ADAYI":
            direction = "YUKARI" if break_dir == 1 else "AŞAĞI" if break_dir == -1 else ""
            level = upper if break_dir == 1 else lower
            power = data.get('break_strength', quality)
            kapanis_yonu = "üstünde" if break_dir == 1 else "altında" if break_dir == -1 else "yakınında"
            templates = [
                f"🚀 {stock} KIRIYOR! {direction}\n"
                f"{tf_human} {pattern} {level:.2f} {kapanis_yonu} kapanış{mtf_str}\n"
                f"Güç {power:.0f} {q_emoji} - teyit mumu bekleniyor\n"
                f"Retest olursa fırsat olabilir, takipteyim",
                f"💥 {stock} {tf_human} {pattern}\n"
                f"{direction} kırılım adayı! {level:.2f} kırıldı\n"
                f"Güç {power:.0f} ({q_comment}) - teyit gelirse haber veririm\n"
                f"Şimdilik izle, acele etme",
            ]
            msg = random.choice(templates)

        elif state == "KIRILIM_TEYITLI":
            direction = "yukarı" if break_dir == 1 else "aşağı" if break_dir == -1 else ""
            level = data.get('break_price', upper if break_dir==1 else lower)
            msg = (
                f"✅ {stock} teyit aldı! {direction} kırılım{mtf_str}\n"
                f"{tf_human} {pattern} {level:.2f} kırılımı teyitli\n"
                f"Kalite {quality:.0f} {q_emoji}, {contraction_str}{temas_str}\n"
                f"{level:.2f} artık {'destek' if break_dir==1 else 'direnç'} olabilir\n"
                f"Retest bekleniyor..."
            )

        elif state == "RETEST_BEKLENIYOR":
            level = data.get('break_price', price)
            msg = (
                f"⏳ {stock} retest bekleniyor\n"
                f"{tf_human} {pattern} kırılım sonrası {level:.2f}'e dönüş olabilir\n"
                f"Kalite {quality:.0f} {q_emoji} - retest tutarsa güçlenir"
            )

        elif state == "RETEST_EDILIYOR":
            msg = (
                f"🔄 {stock}'da retest oluyor\n"
                f"{tf_human} {pattern} kırılan seviyeye geri döndü\n"
                f"Tutunursa devamı gelebilir, izliyorum"
            )

        elif state == "RETEST_BASARILI":
            direction = "yukarı" if break_dir == 1 else "aşağı"
            msg = (
                f"🎯 {stock} RETEST BAŞARILI!\n"
                f"{tf_human} {pattern} {direction} kırılım sonrası retest tuttu{mtf_str}\n"
                f"Kalite {quality:.0f} {q_emoji}{temas_str}{yas_str} - formasyon tamamlanmaya yakın\n"
                f"Bu seviyelerden sonrası için kendi analizini yap"
            )

        elif state == "FORMASYON_TAMAMLANDI":
            direction = "yukarı" if break_dir == 1 else "aşağı"
            detay = f"{temas_str}{yas_str}{mtf_str}"
            if retest_seen:
                msg = (
                    f"🏁 {stock} {pattern} TAMAMLANDI\n"
                    f"{tf_human} grafikte {direction} kırılım + retest başarılı{detay}\n"
                    f"Kalite {quality:.0f} {q_emoji} - görev tamam\n"
                    f"Yeni formasyon için taramaya devam"
                )
            else:
                msg = (
                    f"🏁 {stock} {pattern} TAMAMLANDI\n"
                    f"{tf_human} grafikte {direction} kırılım - retest olmadan ilerledi / "
                    f"fiyat kırılan seviyeye geri dönmedi{detay}\n"
                    f"Kalite {quality:.0f} {q_emoji} - görev tamam\n"
                    f"Yeni formasyon için taramaya devam"
                )

        elif state == "BASARISIZ_KIRILIM":
            msg = (
                f"❌ {stock} kırılım başarısız\n"
                f"{tf_human} {pattern} kırılım denedi ama geri döndü\n"
                f"Formasyon alanına dönüş - sahte kırılım olabilir\n"
                f"Tekrar sıkışma bekleniyor"
            )

        elif state == "FORMASYON_GECERSIZ":
            reason = data.get('invalid_reason', 'Süre doldu veya bozuldu')
            msg = (
                f"⚪ {stock} {tf_human} {pattern} geçersiz oldu\n"
                f"Sebep: {reason}\n"
                f"Yeni oluşum için takipteyim"
            )

        else:
            msg = (
                f"{emoji} {stock} {tf_human} {pattern}\n"
                f"Durum: {state} | Kalite: {quality:.0f} {q_emoji}\n"
                f"Seviye: {price:.2f} | {contraction_str}\n"
                f"{time_str}"
            )

        footer_options = [
            f"\n\n💡 Detaylı analiz için grafiğe bak - {stock} {timeframe}",
            f"\n\n📊 Kendi analizini de ekle, sadece formasyon yetmez",
            f"\n\n🔍 {stock} {tf_human} - daha fazlası için takipte kal",
        ]
        if state in ["KIRILIM_ADAYI", "KIRILIM_TEYITLI", "RETEST_BASARILI", "FORMASYON_TAMAMLANDI"]:
            msg += random.choice(footer_options)

        # Acil olay mesajına, ayrı alarm olarak henüz gönderilmemiş en fazla üç
        # kısa izleme adayı bağlamı eklenir. Adaylar kendi başlarına gönderilmez.
        watch_context = data.get("watch_context") or []
        context_lines = []
        for candidate in watch_context[:3]:
            if not isinstance(candidate, dict):
                continue
            candidate_stock = str(candidate.get("stock") or "?")
            candidate_tf = TF_HUMAN.get(candidate.get("timeframe"), candidate.get("timeframe", ""))
            candidate_pattern = str(candidate.get("pattern_name") or "formasyon")
            candidate_state = str(candidate.get("state") or "izlemede").replace("_", " ").lower()
            try:
                candidate_quality = float(candidate.get("quality") or 0)
                quality_suffix = f" · kalite {candidate_quality:.0f}"
            except (TypeError, ValueError):
                quality_suffix = ""
            context_lines.append(
                f"• {candidate_stock} {candidate_tf} {candidate_pattern}: {candidate_state}{quality_suffix}"
            )
        if context_lines:
            msg += "\n\n👀 Diğer izleme adayları\n" + "\n".join(context_lines)

        return msg

    def format_dm_message(self, data: Dict) -> str:
        """Compact Formation-first DM formatter; public channel keeps format_message."""
        stock = str(data.get("stock_name", "Bilinmiyor"))
        timeframe = str(data.get("timeframe", "1h")).lower()
        pattern = str(data.get("pattern_name", "Formasyon"))
        state = str(data.get("state", "ADAY_OLUSUYOR"))
        direction_value = data.get("break_dir", 0)
        try:
            direction_value = int(direction_value)
        except (TypeError, ValueError, OverflowError):
            direction_value = 0
        direction = "yukarı" if direction_value > 0 else "aşağı" if direction_value < 0 else ""
        level = data.get("break_price")
        if level is None:
            level = data.get("critical_price_level")
        # Görüntüleme katmanı: ham seviye değeri korunur, mesajda iki ondalık
        # gösterilir (bant/OB-FVG sınırlarıyla aynı standart). Geçersizse yazılmaz.
        level_gosterim = display_price(level) if level is not None else ""
        level_text = f" {level_gosterim}" if level_gosterim else ""
        lines = [
            f"{stock} · {DM_TF_LABEL.get(timeframe, timeframe)} {pattern}",
            DM_STATE_LABELS.get(state, state.replace("_", " ")),
        ]

        stats = []
        try:
            quality = data.get("confidence_score")
            if quality is not None:
                stats.append(f"Kalite {float(quality):.0f}")
        except (TypeError, ValueError, OverflowError):
            pass
        try:
            contraction = data.get("contraction")
            if contraction is not None:
                stats.append(f"Daralma %{float(contraction) * 100:.0f}")
        except (TypeError, ValueError, OverflowError):
            pass
        try:
            upper_touches = data.get("upper_touches")
            lower_touches = data.get("lower_touches")
            if upper_touches is not None and lower_touches is not None:
                stats.append(f"{int(upper_touches) + int(lower_touches)} temas")
        except (TypeError, ValueError, OverflowError):
            pass
        try:
            age_bars = data.get("age_bars")
            if age_bars is not None:
                stats.append(f"{int(age_bars)} bar")
        except (TypeError, ValueError, OverflowError):
            pass
        if stats:
            lines.append(" · ".join(stats))

        event_line = ""
        if state == "KIRILIM_TEYITLI" and direction:
            retest = "retest görüldü" if data.get("retest_seen", False) else "retest bekleniyor"
            event_line = f"{direction.capitalize()} kırılım{level_text} teyitli · {retest}"
        elif state == "RETEST_BEKLENIYOR" and direction:
            event_line = f"{direction.capitalize()} kırılım{level_text} · retest bekleniyor"
        elif state == "RETEST_EDILIYOR" and direction:
            event_line = f"{direction.capitalize()} kırılım{level_text} · kırılan seviye yeniden test ediliyor"
        elif state == "RETEST_BASARILI" and direction:
            event_line = f"{direction.capitalize()} kırılım{level_text} · retest başarılı"
        elif state == "FORMASYON_TAMAMLANDI" and direction:
            retest = (
                "retest başarılı" if data.get("retest_seen", True)
                else "retest olmadı; fiyat kırılan seviyeye dönmedi"
            )
            event_line = f"{direction.capitalize()} kırılım{level_text} · {retest}"
        elif state == "KIRILIM_ADAYI" and direction:
            event_line = f"{direction.capitalize()} kırılım adayı{level_text}"
            try:
                strength = data.get("break_strength")
                if strength is not None:
                    event_line += f" · kırılım gücü {float(strength):.0f}"
            except (TypeError, ValueError, OverflowError):
                pass
            event_line += " · teyit bekleniyor"
        elif state == "KIRILIM_DENEMESI" and direction:
            event_line = f"{direction.capitalize()} kırılım denemesi{level_text}"
            try:
                strength = data.get("break_strength")
                if strength is not None:
                    event_line += f" · kırılım gücü {float(strength):.0f}"
            except (TypeError, ValueError, OverflowError):
                pass
            event_line += " · teyit bekleniyor"
            timestamp = data.get("timestamp")
            try:
                event_line += f" · {timestamp.strftime('%d %b %H:%M')}"
            except (AttributeError, TypeError, ValueError):
                pass
        elif state == "KIRILIM_HAZIRLIGI" and direction:
            event_line = f"{direction.capitalize()} kırılım hazırlığı{level_text}"
        elif state == "BASARISIZ_KIRILIM":
            event_line = f"Başarısız kırılım{level_text}"
        if event_line:
            lines.append(event_line)
        if state == "BASARISIZ_KIRILIM":
            # All native transitions to this state are triggered by price returning
            # inside the active formation after the attempted/confirmed break.
            lines.append("Fiyat kırılım sonrası formasyon alanına döndü")
        if state == "KIRILIM_TEYITLI" and direction and level is not None:
            role = "destek" if direction_value > 0 else "direnç"
            lines.append(f"Seviye {role} olabilir")
        if data.get("mtf_destek"):
            # Formation's existing MTF flag is computed against 4H for 1H alerts
            # and 1D for 4H alerts; this only restores that known label.
            mtf_timeframe = data.get("mtf_timeframe") or {"1h": "4H", "4h": "1D"}.get(timeframe)
            if mtf_timeframe:
                mtf_label = DM_TF_LABEL.get(str(mtf_timeframe).lower(), str(mtf_timeframe))
                lines.append(f"MTF: {mtf_label} destekliyor")

        watch_context = data.get("watch_context") or []
        watch_lines = []
        for candidate in watch_context[:3]:
            if not isinstance(candidate, dict):
                continue
            candidate_stock = str(candidate.get("stock") or "?")
            candidate_tf = DM_TF_LABEL.get(
                str(candidate.get("timeframe") or "").lower(),
                str(candidate.get("timeframe") or ""),
            )
            candidate_pattern = str(candidate.get("pattern_name") or "formasyon")
            # Ortak Türkçe durum sözlüğü (telegram_alert_flow.STATE_TR) kullanılır;
            # digest tarafıyla aynı terminoloji korunur. Bilinmeyen durum ham kod
            # olarak kalır, uydurulmaz.
            candidate_state = STATE_TR.get(
                str(candidate.get("state") or ""), str(candidate.get("state") or "izlemede")
            )
            try:
                quality_text = f" · kalite {float(candidate.get('quality')):.0f}"
            except (TypeError, ValueError, OverflowError):
                quality_text = ""
            watch_lines.append(
                f"• {candidate_stock} {candidate_tf} {candidate_pattern}: "
                f"{candidate_state}{quality_text}"
            )
        if watch_lines:
            lines.extend(["Diğer izleme adayları", *watch_lines])

        context = data.get("dm_context")
        if isinstance(context, dict):
            structure = context.get("structure")
            if isinstance(structure, str) and structure:
                lines.append(f"Yapı: {structure}")
            volume = context.get("volume")
            if isinstance(volume, str) and volume:
                lines.append(f"Hacim: {volume}")
            nearby = context.get("nearby_zones")
            if isinstance(nearby, (list, tuple)) and nearby:
                lines.append("Yakın bölgeler")
                lines.extend(str(zone) for zone in nearby[:2] if zone)
        return "\n".join(lines)

    @staticmethod
    def _formation_identity(data: Dict) -> Optional[str]:
        """Stable notification identity; deliberately excludes domain/watch context and quality."""
        timestamp = data.get("lifecycle_event_id")
        if not timestamp:
            timestamp = data.get("timestamp")
            if hasattr(timestamp, "isoformat"):
                timestamp = timestamp.isoformat()
        if not timestamp:
            return None
        identity = [
            "formation",
            str(data.get("stock_name", "")).strip().upper(),
            str(data.get("pattern_name", "")).strip(),
            str(data.get("timeframe", "")).strip().lower(),
            str(data.get("state", "")).strip().upper(),
            str(timestamp),
        ]
        return json.dumps(identity, ensure_ascii=False, separators=(",", ":"))

    def _formation_job_metadata(self, data: Dict, destination: str) -> dict:
        return {
            "kind": "formation", "policy": True,
            "event_id": str(data.get("lifecycle_event_id")) if data.get("lifecycle_event_id") else None,
            "stock": str(data.get("stock_name", "")),
            "pattern": str(data.get("pattern_name", "")),
            "timeframe": str(data.get("timeframe", "")),
            "state": str(data.get("state", "")),
            "series_key": f"{destination}|{data.get('stock_name', '')}|{data.get('timeframe', '')}",
            "watch_context": list(data.get("watch_context") or []) if destination == "dm" else [],
        }

    def prepare_formation(self, data: Dict) -> bool:
        """Durably record eligible Formation events before domain context work.

        Prepared items cannot be sent by the same process until `send()` activates
        them with this scan's context. A restart converts a leftover prepared item
        to its already-persisted Formation-only fallback text.
        """
        identity = self._formation_identity(data)
        if identity is None:
            logger.error("Formation prepare rejected: no stable event/bar timestamp")
            return False
        stock = str(data.get("stock_name", ""))
        pattern = str(data.get("pattern_name", ""))
        timeframe = str(data.get("timeframe", ""))
        state = str(data.get("state", ""))
        event_id = str(data.get("lifecycle_event_id")) if data.get("lifecycle_event_id") else None
        prepared_any = False

        dm_id = self._outbox.make_id(identity, "dm")
        dm_job = self._outbox.get(dm_id)
        if dm_job is None and self.can_send(stock, pattern, timeframe, state, event_id=event_id, destination="dm"):
            fallback_data = dict(data)
            fallback_data["dm_context"] = {}
            try:
                fallback_text = self.format_dm_message(fallback_data)
            except Exception:
                logger.exception("Formation DM fallback formatter failed; trying legacy formatter")
                try:
                    fallback_text = self.format_message(fallback_data)
                except Exception:
                    logger.exception("Both DM fallback formatters failed; no prepared DM created")
                    fallback_text = None
            if fallback_text is not None:
                _item_id, dm_job, _created = self._queue_text(
                    fallback_text, destination="dm", chat_id=self.chat_id, identity=identity,
                    metadata=self._formation_job_metadata(data, "dm"), prepared=True,
                )
                prepared_any = dm_job is not None
        elif dm_job is not None:
            prepared_any = dm_job.get("status") in {"prepared", "pending", "sending", "sent"} or prepared_any

        if self.should_send_to_public(data) and (self.channel_id or not self.enabled):
            channel_id = self._outbox.make_id(identity, "channel")
            channel_job = self._outbox.get(channel_id)
            if channel_job is None and self.can_send(
                stock, pattern, timeframe, state, event_id=event_id, destination="channel"
            ):
                public_data = {
                    key: value for key, value in data.items()
                    if key not in {"dm_context", "watch_context", "lifecycle_event_id"}
                }
                try:
                    public_text = self.format_message(public_data)
                except Exception:
                    logger.exception("Public fallback formatter failed; DM decision remains durable")
                    public_text = None
                if public_text is not None:
                    _item_id, channel_job, _created = self._queue_text(
                        public_text, destination="channel", chat_id=self.channel_id or "mock-channel",
                        identity=identity, metadata=self._formation_job_metadata(data, "channel"),
                        prepared=True,
                    )
                    prepared_any = channel_job is not None or prepared_any
            elif channel_job is not None:
                prepared_any = channel_job.get("status") in {"prepared", "pending", "sending", "sent"} or prepared_any
        return prepared_any

    def send(self, data: Dict) -> bool:
        stock = str(data.get("stock_name", ""))
        pattern = str(data.get("pattern_name", ""))
        timeframe = str(data.get("timeframe", ""))
        state = str(data.get("state", ""))
        event_id = str(data.get("lifecycle_event_id")) if data.get("lifecycle_event_id") else None
        identity = self._formation_identity(data)
        if identity is None:
            logger.error("Formation notification has no stable event/bar timestamp; refusing volatile enqueue")
            return False

        # One durable job per event+destination. Existing pending jobs retain the
        # original rendered text/context; retries never replace identity by fresh context.
        dm_id = self._outbox.make_id(identity, "dm")
        dm_job = self._outbox.get(dm_id)
        dm_was_sent = bool(dm_job and dm_job.get("status") == "sent")
        if dm_job and dm_job.get("status") == "prepared":
            try:
                dm_text = self.format_dm_message(data)
            except Exception:
                logger.exception("Formation DM context formatter failed; activating Formation-only fallback")
                dm_text = dm_job.get("fallback_text") or dm_job.get("text")
            if dm_text:
                self._outbox.activate_prepared(
                    dm_id, dm_text, self._formation_job_metadata(data, "dm")
                )
                dm_job = self._outbox.get(dm_id)
        elif dm_job is None and self.can_send(stock, pattern, timeframe, state, event_id=event_id, destination="dm"):
            try:
                dm_text = self.format_dm_message(data)
            except Exception:
                logger.exception("Formation DM formatter failed; trying legacy DM formatter")
                try:
                    dm_text = self.format_message(data)
                except Exception:
                    logger.exception("Both DM formatters failed; no DM outbox record created")
                    dm_text = None
            if dm_text is not None:
                _item_id, dm_job, _created = self._queue_text(
                    dm_text, destination="dm", chat_id=self.chat_id, identity=identity,
                    metadata=self._formation_job_metadata(data, "dm"),
                )
        elif dm_job is None:
            logger.info("%s %s %s %s - policy/cooldown/cap suppressed before enqueue", stock, pattern, timeframe, state)

        public_id = None
        if self.should_send_to_public(data) and (self.channel_id or not self.enabled):
            public_id = self._outbox.make_id(identity, "channel")
            public_job = self._outbox.get(public_id)
            if public_job is None or public_job.get("status") == "prepared":
                if public_job is None and not self.can_send(
                    stock, pattern, timeframe, state, event_id=event_id, destination="channel"
                ):
                    public_data = None
                else:
                    public_data = {
                        key: value for key, value in data.items()
                        if key not in {"dm_context", "watch_context", "lifecycle_event_id"}
                    }
                if public_data is not None:
                    try:
                        public_text = self.format_message(public_data)
                    except Exception:
                        logger.exception("Public formatter failed; DM remains independent")
                        public_text = (
                            public_job.get("fallback_text") or public_job.get("text")
                            if public_job and public_job.get("status") == "prepared"
                            else None
                        )
                    if public_text is not None:
                        metadata = self._formation_job_metadata(data, "channel")
                        if public_job and public_job.get("status") == "prepared":
                            self._outbox.activate_prepared(public_id, public_text, metadata)
                        else:
                            _item_id, public_job, _created = self._queue_text(
                                public_text, destination="channel", chat_id=self.channel_id or "mock-channel",
                                identity=identity, metadata=metadata,
                            )

        job_ids = [job_id for job_id, job in ((dm_id, dm_job), (public_id, None)) if job_id]
        # If a prior pending job exists it remains eligible even when current
        # context/cap evaluation no longer allows creating a new one.
        self.drain_outbox(max_items=2, only_ids=job_ids)
        latest_dm = self._outbox.get(dm_id)
        # Existing sent events are suppressed, not reported as newly sent. The
        # caller updates watch/live state only for a successful delivery now.
        return bool(not dm_was_sent and latest_dm and latest_dm.get("status") == "sent")


if __name__ == "__main__":
    notifier = TelegramNotifier()
    test_cases = [
        {'stock_name': 'THYAO', 'timeframe': '1h', 'pattern_name': 'Yükselen Üçgen', 'state': 'ADAY_OLUSUYOR', 'confidence_score': 83, 'critical_price_level': 302.11, 'upper_now': 302.11, 'lower_now': 294.32, 'contraction': 0.87, 'timestamp': _local_now_naive(), 'upper_touches': 2, 'lower_touches': 2, 'age_bars': 18},
        {'stock_name': 'GARAN', 'timeframe': '4h', 'pattern_name': 'Simetrik Üçgen', 'state': 'SIKISMA_GUCLENIYOR', 'confidence_score': 88, 'critical_price_level': 120.5, 'upper_now': 122.0, 'lower_now': 119.0, 'contraction': 0.91, 'timestamp': _local_now_naive(), 'upper_touches': 3, 'lower_touches': 2, 'age_bars': 22},
        {'stock_name': 'AKBNK', 'timeframe': '1h', 'pattern_name': 'Alçalan Kama', 'state': 'KIRILIM_ADAYI', 'confidence_score': 82, 'critical_price_level': 58.3, 'upper_now': 58.3, 'lower_now': 55.1, 'contraction': 0.75, 'break_dir': 1, 'break_strength': 82, 'timestamp': _local_now_naive()},
    ]
    for tc in test_cases:
        print(notifier.format_message(tc))
        print("---")
