"""Batch 8 / C2 (8.5) — Telegram TAŞIMA katmanı: webhook kurulumu + API çağrıları.

`main.py`'den ayrılan parçalar: sır/adres çözümleme, Telegram Bot API çağrısı,
setWebhook/deleteWebhook ve komut katmanının (webhook ↔ yoklama) seçimi.

Davranış aynı: ağ hatası botu düşürmez, webhook kurulamazsa yoklama moduna
düşülür, çağrılan API fonksiyonu DIŞARIDAN verilir (main adaptörleri kendi
`_telegram_api_cagri` globalini geçirir; testlerde monkeypatch hâlâ çalışır).
"""

import logging
import os
import re
import stat
from urllib.parse import urlsplit

from secrets_redaction import redact_sensitive_text
from health_server import WEBHOOK_YOL, WEBHOOK_YOL_ONEK
from telegram_commands import IZLENEN_GUNCELLEMELER

logger = logging.getLogger(__name__)


def webhook_secret_ayikla(secret=None, varsayilan="") -> str:
    """Parametre verilmediyse `varsayilan` (main: config TELEGRAM_WEBHOOK_SECRET)."""
    if secret is None:
        secret = varsayilan
    return (secret or "").strip()


def webhook_adres_gizle(adres: str, secret: str = "") -> str:
    """Log için: adresteki sırrı *** yapar (loglara sır düşmesin)."""
    return adres.replace(secret, "***") if secret else adres


def _guvenli_webhook_url(adres: str) -> bool:
    """Sırlar yalnız geçerli HTTPS adresine, URL kimlik bilgisi olmadan gider."""
    if not adres or any(ch.isspace() or ord(ch) < 32 for ch in adres):
        return False
    try:
        parca = urlsplit(adres)
        return bool(parca.scheme.lower() == "https" and parca.hostname and
                    parca.username is None and parca.password is None and
                    not parca.query and not parca.fragment and
                    (parca.port is None or 1 <= parca.port <= 65535))
    except ValueError:
        return False


def webhook_url_olustur(secret=None, webhook_url=None, render_url=None, *,
                        varsayilan_secret="", varsayilan_url="", varsayilan_render="") -> str:
    """Yalnız HTTPS webhook adresi üret; eski sırlı yolu uyumluluk için koru."""
    secret = webhook_secret_ayikla(secret, varsayilan_secret)
    if not secret:
        return ""
    webhook_url = (varsayilan_url if webhook_url is None else webhook_url or "").strip()
    render_url = (varsayilan_render if render_url is None else render_url or "").strip()
    taban = webhook_url or render_url
    if not taban:
        logger.warning("Webhook taban adresi yok; yoklama kullanilacak")
        return ""
    # Tam /webhook ve eski /webhook/<secret> yolları dahil HER yolda kontrol.
    if not _guvenli_webhook_url(taban):
        logger.warning("Webhook adresi geçerli HTTPS olmalı (sorgu/kimlik bilgisi yasak)")
        return ""
    adres = taban.rstrip("/")
    if not (adres.endswith(WEBHOOK_YOL) or WEBHOOK_YOL_ONEK in urlsplit(adres).path):
        adres += WEBHOOK_YOL
    elif WEBHOOK_YOL_ONEK in urlsplit(adres).path:
        logger.warning("Sırlı eski webhook yolu kullanılıyor; /webhook ve secret_token önerilir")
    return adres


def token_al(token=None, notifier=None) -> str:
    """Token parametresi yoksa verilen notifier'ın token'ı (main_loop sonrası dolu)."""
    if token:
        return str(token).strip()
    return (getattr(notifier, "token", "") or "").strip()


def api_cagri(method: str, token: str, payload: dict, timeout: int = 15):
    """Telegram Bot API POST çağrısı (test edilebilirlik için tek nokta)."""
    import requests
    return requests.post(f"https://api.telegram.org/bot{token}/{method}",
                         json=payload, timeout=timeout)


def yanit_oku(yanit):
    """(ok, aciklama) — Telegram yanıtından okunabilir sonuç çıkarır."""
    kod = getattr(yanit, "status_code", 0)
    try:
        govde = yanit.json() or {}
    except Exception:
        govde = {}
    if not isinstance(govde, dict):
        govde = {}
    ok = kod == 200 and bool(govde.get("ok"))
    aciklama = str(govde.get("description") or "").strip() or f"HTTP {kod}"
    return ok, aciklama


# Telegram sendPhoto için fotoğraf başına üst sınır. Albümde de toplam belleği
# sınırla: requests multipart içeriğini ayrıca bellekte birleştirebilir.
FOTO_MAKS_BAYT = 10 * 1024 * 1024
ALBUM_MAKS_BAYT = 40 * 1024 * 1024


class MedyaHatasi(str):
    """İstek kesin reddedildiyse tek tek fotoğraf denenebilir; timeout belirsizdir."""

    def __new__(cls, mesaj, *, kesin_red=False):
        nesne = super().__new__(cls, mesaj)
        nesne.kesin_red = bool(kesin_red)
        return nesne


def medya_kesin_reddedildi(aciklama) -> bool:
    return isinstance(aciklama, MedyaHatasi) and aciklama.kesin_red


def _foto_baytlari(yol):
    # Düzenli dosya + boyut kontrolü; FIFO'da bloklanma, sembolik bağlantı ile
    # yerel dosya sızıntısı ve sınırlandırılmamış read() engellenir.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(os.fspath(yol), flags)
    try:
        bilgi = os.fstat(fd)
        if not stat.S_ISREG(bilgi.st_mode) or bilgi.st_size <= 0 or bilgi.st_size > FOTO_MAKS_BAYT:
            raise ValueError("gecersiz veya buyuk fotograf")
        with os.fdopen(fd, "rb") as akis:
            fd = None
            bayt = akis.read(FOTO_MAKS_BAYT + 1)
        if not bayt or len(bayt) > FOTO_MAKS_BAYT:
            raise ValueError("gecersiz veya buyuk fotograf")
        return bayt
    finally:
        if fd is not None:
            os.close(fd)


def foto_gonder(yol, chat_id=None, token=None, notifier=None, caption="", *,
                timeout: int = 20, api=None):
    """`sendPhoto` ile tek kare gönderir: `(ok, aciklama)` (G4, §4).

    Neden ayrı fonksiyon: mesaj yolu `api_cagri`yı (JSON gövde) kullanıyor; fotoğraf
    multipart gövde ister, o yüzden burada `files` ile ayrı bir istek kurulur. Kaynak
    `notifier`dan okunur (token/chat_id anaLoop sonrası dolu olabilir) — aynı
    `token_al` deseni. Hata metni kırpılır ve token içermesin diye çağıran taraf
    `redact_sensitive_text` kullanır; burada ham açıklama döner.

    Görsel gönderimi hiçbir koşulda alarmı düşürmez: çağıran taraf sonucu yalnız
    sayaça yazar.
    """
    if not yol or not os.path.exists(yol):
        return False, "png yok"
    metin_token = token_al(token=token, notifier=notifier)
    hedef = chat_id if chat_id is not None else getattr(notifier, "chat_id", "")
    if not metin_token or not hedef:
        return False, "token/chat_id yok"
    try:
        bayt = _foto_baytlari(yol)
    except (OSError, TypeError, ValueError) as hata:
        return False, f"dosya okunamadı: {type(hata).__name__}"
    cagri = api or _multipart_cagri
    try:
        yanit = cagri("sendPhoto", metin_token, {
            "chat_id": hedef,
            "caption": str(caption or "")[:1024],
        }, {"photo": (os.path.basename(yol), bayt, "image/png")}, timeout=timeout)
    except Exception as hata:   # ağ hatası: çağıran taraf sayar, alarm sürer
        return False, f"istek hatasi: {type(hata).__name__}"[:200]
    ok, aciklama = yanit_oku(yanit)
    return ok, redact_sensitive_text(aciklama, metin_token)


def medya_grubu_gonder(yollar, captions=None, chat_id=None, token=None, notifier=None, *,
                       timeout: int = 40, api=None):
    """`sendMediaGroup` ile kareleri TEK albüm olarak gönderir: `(ok, aciklama)`.

    Neden: 4 kare ayrı `sendPhoto` ile gidince araya metin ve mesaj parçalanması
    giriyordu; albüm tek mesaj gibi görünür. Telegram albümü 2–10 öğe ister; tek
    kare için çağıran taraf `foto_gonder` kullanır. Her öğenin caption'ı kendi
    karesinin altında görünür (1024 karakter sınırı, kırpılır). Dosyalar bu
    fonksiyonda okunur; silme çağıran tarafın sorumluluğundadır.
    """
    import json

    yollar = [y for y in (yollar or []) if y]
    if not (2 <= len(yollar) <= 10):
        return False, MedyaHatasi("albüm 2-10 kare ister", kesin_red=True)
    if not all(os.path.exists(y) for y in yollar):
        return False, MedyaHatasi("png yok", kesin_red=True)
    metin_token = token_al(token=token, notifier=notifier)
    hedef = chat_id if chat_id is not None else getattr(notifier, "chat_id", "")
    if not metin_token or not hedef:
        return False, "token/chat_id yok"
    caps = list(captions or [])
    caps += [""] * (len(yollar) - len(caps))
    medya, dosyalar = [], {}
    try:
        for i, yol in enumerate(yollar):
            ad = f"photo{i}"
            medya.append({"type": "photo", "media": f"attach://{ad}",
                          "caption": str(caps[i] or "")[:1024]})
            bayt = _foto_baytlari(yol)
            if sum(len(item[1]) for item in dosyalar.values()) + len(bayt) > ALBUM_MAKS_BAYT:
                raise ValueError("albüm çok büyük")
            dosyalar[ad] = (os.path.basename(yol), bayt, "image/png")
    except (OSError, TypeError, ValueError) as hata:
        return False, MedyaHatasi(f"dosya okunamadı: {type(hata).__name__}", kesin_red=True)
    cagri = api or _multipart_cagri
    try:
        yanit = cagri("sendMediaGroup", metin_token,
                      {"chat_id": hedef, "media": json.dumps(medya, ensure_ascii=False)},
                      dosyalar, timeout=timeout)
    except Exception as hata:   # Telegram kabul etmiş olabilir: tekillere düşme
        return False, MedyaHatasi(f"istek hatasi: {type(hata).__name__}"[:200])
    ok, aciklama = yanit_oku(yanit)
    aciklama = redact_sensitive_text(aciklama, metin_token)
    if not ok:
        # 400/413 kesin red; 5xx, 429, bozuk yanıt ve ağ hatası belirsizdir.
        aciklama = MedyaHatasi(aciklama, kesin_red=getattr(yanit, "status_code", 0) in (400, 413))
    return ok, aciklama


def _multipart_cagri(method: str, token: str, alanlar: dict, dosyalar: dict,
                     timeout: int = 20):
    """`api_cagri`nın çok-parçalı kardeşi (test noktası: tek yerden çıkış)."""
    import requests

    return requests.post(f"https://api.telegram.org/bot{token}/{method}",
                         data=alanlar, files=dosyalar, timeout=timeout)


def set_webhook(url=None, secret=None, token=None, *, api=None, yanit_oku_fn=None,
                secret_ayikla_fn=None, token_al_fn=None, adres_olustur_fn=None,
                gizle_fn=None) -> bool:
    """setWebhook: komutlar Telegram → `/webhook` (sırsız yol) ile gelsin.

    - Bekleyen güncellemeler korunur. Render uyurken gelen komut, webhook isteğiyle
      servisi uyandırır; açılışta kuyruğu silmek bu ilk komutu kaybettirirdi.
      Eski komutların güvenliği `TelegramCommandListener` içindeki yaş kapısıyla
      sağlanır: 15 dakikadan eski durum-değiştirici komut çalıştırılmaz.
    - `secret_token`: Telegram her istekte `X-Telegram-Bot-Api-Secret-Token`
      başlığını gönderir; health_server sırsız yolda bu başlığı ZORUNLU tutar (A7).
    """
    secret = secret_ayikla_fn(secret)
    token = token_al_fn(token)
    adres = (url or "").strip() or adres_olustur_fn(secret=secret)
    api = api if api is not None else api_cagri
    if not token:
        logger.warning("Webhook kurulmadi: Telegram token yok")
        return False
    if not adres or not _guvenli_webhook_url(adres):
        logger.warning("Webhook kurulmadi: geçerli HTTPS adresi gerekli")
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret or ""):
        logger.warning("Webhook kurulmadi: Telegram secret_token biçimi geçersiz")
        return False
    govde = {
        "url": adres,
        # TÜM izlenen türler: `channel_post` BİLİNÇLİ olarak dahil. Kanal hedefi
        # komut kabul etmez ama bu tür gelmezse "public'te komut çalışmıyor"
        # teşhis edilemez (sayaç artmaz, log düşmez). Tek kaynak:
        # telegram_commands.IZLENEN_GUNCELLEMELER (getUpdates ile aynı liste).
        "allowed_updates": list(IZLENEN_GUNCELLEMELER),
        "drop_pending_updates": False,
    }
    if secret:
        govde["secret_token"] = secret
    try:
        yanit = api("setWebhook", token, govde)
    except Exception as exc:  # noqa: BLE001 - ağ hatası botu düşürmesin
        logger.error("Webhook kurulamadi (ag hatasi): %s", redact_sensitive_text(exc, token, secret))
        return False
    ok, aciklama = yanit_oku_fn(yanit)
    if ok:
        logger.info("Telegram webhook kuruldu: %s (%s)", gizle_fn(adres, secret),
                    redact_sensitive_text(aciklama, token, secret))
    else:
        logger.error("Telegram webhook kurulamadi: %s", redact_sensitive_text(aciklama, token, secret))
    return ok


def delete_webhook(token=None, *, api=None, yanit_oku_fn=None, token_al_fn=None) -> bool:
    """deleteWebhook: yoklama moduna dönmeden önce eski webhook kaydını siler.

    Neden gerekli: webhook kurulu bir token'da `getUpdates` 409 Conflict alır, yani
    mod değişince eski kayıt kalırsa polling komutları çalışmaz. Bekleyen güncellemeler
    silinmez; polling listener açılışta 15 dakikadan eski backlog'u sınıflandırır,
    taze komutları korur ve bayat komutları kullanıcıya bildirerek atlar.
    """
    token = token_al_fn(token)
    if not token:
        return False
    api = api if api is not None else api_cagri
    try:
        yanit = api("deleteWebhook", token, {"drop_pending_updates": False})
    except Exception as exc:  # noqa: BLE001 - ağ hatası botu düşürmesin
        logger.warning("Webhook kaldirilamadi (ag hatasi): %s", redact_sensitive_text(exc, token))
        return False
    ok, aciklama = yanit_oku_fn(yanit)
    if ok:
        logger.info("Telegram webhook kaldirildi (%s)", redact_sensitive_text(aciklama, token))
    else:
        logger.warning("Telegram webhook kaldirilamadi: %s", redact_sensitive_text(aciklama, token))
    return ok


def _kapsam_metni(dm_hedef: str, public_yolu: bool) -> str:
    """Log için yetki kapsamı: hangi sohbetlerden komut kabul edildiği."""
    parcalar = []
    if dm_hedef:
        parcalar.append(f"DM chat_id {dm_hedef}")
    if public_yolu:
        parcalar.append("public grup: yalnız yöneticiler, yalnız okuma komutları")
    return " · ".join(parcalar) or "kapsam yok"


def komut_katmanini_kur(notifier, isleyici=None, *, komutlar, yardim_metni, tarama_suruyor,
                        health_server_var, listener_factory, adres_olustur, gizle, secret_ayikla,
                        set_webhook_fn, delete_webhook_fn,
                        public_sohbetler=None, public_komutlar=None, admin_kontrol=None,
                        admin_cache_sn=300.0) -> dict:
    """Komut katmanını AYNI ANDA TEK modda kurar: 'webhook', 'yoklama' veya 'kapali'.

    - **webhook**: secret + taban adres var, HTTP sunucusu ayakta ve setWebhook
      başarılı. Güncellemeler sırsız `/webhook` ucuna Telegram'ın secret header'ı
      ile gelir; yoklama thread'i AÇILMAZ (aynı token'da getUpdates 409 alır).
    - **yoklama**: eski davranış (getUpdates daemon thread). Webhook kapalıyken ya da
      setWebhook başarısız olduğunda komutlar tamamen susmasın diye buraya düşülür;
      önce eski webhook kaydı silinir (yoksa 409).
    - **kapali**: token yok VEYA (DM chat_id yok ve public komut yolu da kapalı).

    PUBLIC yol (2026-10-28): `public_sohbetler` + `public_komutlar` + `admin_kontrol`
    üçü de verilirse grup/supergroup yöneticileri okuma komutlarını çalıştırabilir.
    DM chat_id boş olsa bile dinleyici açılır ("public-only" kurulum): eskiden DM
    tanımlı değilse komut katmanı hiç başlamıyordu.

    `isleyici` yalnızca testler için verilir (ağa çıkmayan sahte dinleyici).
    """
    token_var = bool((getattr(notifier, "token", "") or "").strip()) if notifier is not None else False
    dm_hedef = str(getattr(notifier, "chat_id", "") or "").strip() if notifier is not None else ""
    if dm_hedef and (not dm_hedef.isdecimal() or int(dm_hedef) <= 0):
        # Dinleyici yalnız pozitif sayısal özel sohbeti DM kabul eder; aksi
        # halde "açık" mod raporlayıp hiçbir DM'i yanıtlayamazdı.
        logger.warning("TELEGRAM_CHAT_ID geçersiz: DM için pozitif sayısal sohbet kimliği gerekli")
        dm_hedef = ""
    public_hedefler = [str(x).strip() for x in (public_sohbetler or []) if str(x).strip()]
    public_komut_adlari = [str(x).strip() for x in (public_komutlar or []) if str(x).strip()]
    public_yolu = bool(public_hedefler and public_komut_adlari and admin_kontrol is not None)
    if not token_var or not (dm_hedef or public_yolu):
        # PUBLIC hedef varsa yayın sürer ama KOMUTLAR çalışmaz: komut yalnız DM'den
        # okunur (kanala üye mesaj yazamaz). Kullanıcı "bot çalışıyor ama /durum
        # cevap vermiyor" durumunu ancak bu satırdan anlayabilir.
        if notifier is not None and getattr(notifier, "public_enabled", False):
            logger.warning(
                "Telegram komutları KAPALI: TELEGRAM_CHAT_ID (DM) tanımlı değil ve "
                "public komut yolu kapalı. Public hedefe yayın sürer ama /panel,/durum "
                "gibi komutlar çalışmaz; DM chat_id ekleyin ya da "
                "PUBLIC_COMMANDS_ENABLED=1 bırakın.")
        else:
            logger.info("Telegram komut dinleyicisi başlatılmadı (token/chat_id yok)")
        return {"mod": "kapali", "listener": None, "processor": None}
    if isleyici is None:
        isleyici = listener_factory(
            token=notifier.token,
            allowed_chat_id=dm_hedef,
            handlers=komutlar,
            help_text=yardim_metni,
            komutlari_yoksay=tarama_suruyor,
            public_chat_ids=public_hedefler,
            public_commands=public_komut_adlari,
            admin_checker=admin_kontrol,
            admin_cache_sn=admin_cache_sn,
        )
    if public_yolu:
        logger.info(
            "Public grup komutları AÇIK: %s sohbet · %s komut · yalnız yöneticiler",
            len(public_hedefler), len(public_komut_adlari))
    if not dm_hedef:
        logger.info(
            "Telegram komutları yalnız PUBLIC yoldan çalışıyor "
            "(TELEGRAM_CHAT_ID boş): DM komutları kapalı.")
    liste = ", ".join("/" + k for k in komutlar)
    webhook_url = adres_olustur()
    if webhook_url:
        if not health_server_var:
            logger.warning(
                "TELEGRAM_WEBHOOK_SECRET tanimli ama HTTP sunucusu yok "
                "(PORT env yok ya da sunucu baslatilamadi) - yoklama moduna donuldu"
            )
        elif set_webhook_fn(url=webhook_url, token=notifier.token):
            # Güncellemeler health_server thread'inden gelir; bu referans olmadan
            # /webhook ucu 503 döner ve Telegram güncellemeyi tekrar dener.
            pass
            logger.info(
                "Telegram komutları WEBHOOK modunda: "
                f"{gizle(webhook_url, secret_ayikla())} "
                f"({_kapsam_metni(dm_hedef, public_yolu)})"
            )
            return {"mod": "webhook", "listener": None, "processor": isleyici}
        else:
            logger.warning("Webhook kurulamadi - yoklama moduna donuluyor")
    # Yoklama moduna dönerken eski webhook kaydı kalırsa getUpdates 409 alır.
    delete_webhook_fn(token=notifier.token)
    if isleyici.start():
        logger.info(f"Telegram komutları aktif (yoklama): {liste} "
                    f"({_kapsam_metni(dm_hedef, public_yolu)})")
        return {"mod": "yoklama", "listener": isleyici, "processor": None}
    return {"mod": "kapali", "listener": None, "processor": None}
