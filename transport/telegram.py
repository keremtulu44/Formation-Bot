"""Batch 8 / C2 (8.5) — Telegram TAŞIMA katmanı: webhook kurulumu + API çağrıları.

`main.py`'den ayrılan parçalar: sır/adres çözümleme, Telegram Bot API çağrısı,
setWebhook/deleteWebhook ve komut katmanının (webhook ↔ yoklama) seçimi.

Davranış aynı: ağ hatası botu düşürmez, webhook kurulamazsa yoklama moduna
düşülür, çağrılan API fonksiyonu DIŞARIDAN verilir (main adaptörleri kendi
`_telegram_api_cagri` globalini geçirir; testlerde monkeypatch hâlâ çalışır).
"""

import logging

from health_server import WEBHOOK_YOL, WEBHOOK_YOL_ONEK

logger = logging.getLogger(__name__)


def webhook_secret_ayikla(secret=None, varsayilan="") -> str:
    """Parametre verilmediyse `varsayilan` (main: config TELEGRAM_WEBHOOK_SECRET)."""
    if secret is None:
        secret = varsayilan
    return (secret or "").strip()


def webhook_adres_gizle(adres: str, secret: str = "") -> str:
    """Log için: adresteki sırrı *** yapar (loglara sır düşmesin)."""
    return adres.replace(secret, "***") if secret else adres


def webhook_url_olustur(secret=None, webhook_url=None, render_url=None, *,
                        varsayilan_secret="", varsayilan_url="", varsayilan_render="") -> str:
    """Telegram webhook adresini üretir; webhook modu kapalıysa boş döner.

    A7 (Batch 6): adres artık SIR TAŞIMAZ — `…/webhook`. Doğrulama, `setWebhook`
    ile bildirilen `secret_token` başlığıyla yapılır; böylece sır URL ile birlikte
    Telegram sunucularına, proxy ve erişim loglarına düşmez.

    Öncelik:
      1. `TELEGRAM_WEBHOOK_URL` — tam adres. Sonunda `/webhook` varsa aynen
         kullanılır; eski biçim (`/webhook/<secret>`) verilmişse geriye dönük
         uyumluluk için korunur (uyarı loglanır); diğer durumda taban adres sayılır.
      2. `RENDER_EXTERNAL_URL` + `/webhook`
         (Render bunu otomatik verir: https://<servis>.onrender.com)

    Secret boşsa mod kapalıdır (boş döner) ve bot yoklamaya devam eder. Telegram
    webhook için HTTPS zorunlu kılar; http adres üretilirse kurulmaz, loga yazılır.
    """
    secret = webhook_secret_ayikla(secret, varsayilan_secret)
    if not secret:
        return ""
    webhook_url = (varsayilan_url if webhook_url is None else webhook_url or "").strip()
    render_url = (varsayilan_render if render_url is None else render_url or "").strip()

    if webhook_url:
        adres = webhook_url.rstrip("/")
        if adres.endswith(WEBHOOK_YOL):
            return adres                       # sırsız tam adres (önerilen)
        if WEBHOOK_YOL_ONEK in adres:
            # Eski kayıt: sır yolda. Çalışır ama sır loglara düşer; uyarı ver.
            logger.warning(
                "TELEGRAM_WEBHOOK_URL sır içeriyor (…/webhook/<secret>); önerilen biçim "
                f"…{WEBHOOK_YOL} + secret_token başlığı. Eski biçim kabul edildi."
            )
            return adres
        if adres.endswith("/webhook"):
            return adres
        adres = f"{adres}{WEBHOOK_YOL}"
    elif render_url:
        adres = f"{render_url.rstrip('/')}{WEBHOOK_YOL}"
    else:
        logger.warning(
            "TELEGRAM_WEBHOOK_SECRET tanimli ama taban adres yok "
            "(TELEGRAM_WEBHOOK_URL veya RENDER_EXTERNAL_URL gerekli) - yoklama kullanilacak"
        )
        return ""

    if not adres.startswith("https://"):
        logger.warning(
            "Webhook adresi https olmali (Telegram zorunlu): "
            f"{webhook_adres_gizle(adres, secret)} - webhook kurulmadi"
        )
        return ""
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
    ok = kod == 200 and bool(govde.get("ok"))
    aciklama = str(govde.get("description") or "").strip() or f"HTTP {kod}"
    return ok, aciklama


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
    import os

    if not yol or not os.path.exists(yol):
        return False, "png yok"
    metin_token = token_al(token=token, notifier=notifier)
    hedef = chat_id if chat_id is not None else getattr(notifier, "chat_id", "")
    if not metin_token or not hedef:
        return False, "token/chat_id yok"
    cagri = api or _multipart_cagri
    try:
        with open(yol, "rb") as akis:
            yanit = cagri("sendPhoto", metin_token, {
                "chat_id": hedef,
                "caption": str(caption or "")[:1024],
            }, {"photo": (os.path.basename(yol), akis.read(), "image/png")},
                timeout=timeout)
    except Exception as hata:   # ağ hatası: çağıran taraf sayar, alarm sürer
        return False, f"istek hatasi: {type(hata).__name__}"[:200]
    return yanit_oku(yanit)


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
    import os

    yollar = [y for y in (yollar or []) if y]
    if not (2 <= len(yollar) <= 10):
        return False, "albüm 2-10 kare ister"
    if not all(os.path.exists(y) for y in yollar):
        return False, "png yok"
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
            with open(yol, "rb") as akis:
                dosyalar[ad] = (os.path.basename(yol), akis.read(), "image/png")
    except OSError as hata:
        return False, f"dosya okunamadı: {type(hata).__name__}"[:200]
    cagri = api or _multipart_cagri
    try:
        yanit = cagri("sendMediaGroup", metin_token,
                      {"chat_id": hedef, "media": json.dumps(medya, ensure_ascii=False)},
                      dosyalar, timeout=timeout)
    except Exception as hata:   # ağ hatası: çağıran taraf sayar, alarm sürer
        return False, f"istek hatasi: {type(hata).__name__}"[:200]
    return yanit_oku(yanit)


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

    - `drop_pending_updates=True`: bot kapalıyken biriken BAYAT komutlar (örn. dünkü
      /tara) webhook kurulur kurulmaz çalışmasın. Yoklama modundaki "backlog atla"
      kuralının (telegram_commands.BACKLOG_SINIR_SN) webhook karşılığıdır.
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
    if not adres:
        logger.warning("Webhook kurulmadi: adres uretilemedi (secret/RENDER_EXTERNAL_URL eksik)")
        return False
    govde = {
        "url": adres,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }
    if secret:
        govde["secret_token"] = secret
    try:
        yanit = api("setWebhook", token, govde)
    except Exception as exc:  # noqa: BLE001 - ağ hatası botu düşürmesin
        logger.error(f"Webhook kurulamadi (ag hatasi): {exc}")
        return False
    ok, aciklama = yanit_oku_fn(yanit)
    if ok:
        logger.info(f"Telegram webhook kuruldu: {gizle_fn(adres, secret)} ({aciklama})")
    else:
        logger.error(f"Telegram webhook kurulamadi: {aciklama}")
    return ok


def delete_webhook(token=None, *, api=None, yanit_oku_fn=None, token_al_fn=None) -> bool:
    """deleteWebhook: yoklama moduna dönmeden önce eski webhook kaydını siler.

    Neden gerekli: webhook kurulu bir token'da `getUpdates` 409 Conflict alır, yani
    mod değişince (secret silindi / yerelde yoklama) eski kayıt kalırsa komutlar
    sessizce çalışmaz. `drop_pending_updates=True` ile bayat güncellemeler de temizlenir.
    """
    token = token_al_fn(token)
    if not token:
        return False
    api = api if api is not None else api_cagri
    try:
        yanit = api("deleteWebhook", token, {"drop_pending_updates": True})
    except Exception as exc:  # noqa: BLE001 - ağ hatası botu düşürmesin
        logger.warning(f"Webhook kaldirilamadi (ag hatasi): {exc}")
        return False
    ok, aciklama = yanit_oku_fn(yanit)
    if ok:
        logger.info(f"Telegram webhook kaldirildi ({aciklama})")
    else:
        logger.warning(f"Telegram webhook kaldirilamadi: {aciklama}")
    return ok


def komut_katmanini_kur(notifier, isleyici=None, *, komutlar, yardim_metni, tarama_suruyor,
                        health_server_var, listener_factory, adres_olustur, gizle, secret_ayikla,
                        set_webhook_fn, delete_webhook_fn) -> dict:
    """Komut katmanını AYNI ANDA TEK modda kurar: 'webhook', 'yoklama' veya 'kapali'.

    - **webhook**: secret + taban adres var, HTTP sunucusu ayakta ve setWebhook
      başarılı. Güncellemeler `/webhook/<secret>` ucundan gelir; yoklama thread'i
      AÇILMAZ (aynı token'da getUpdates 409 alır).
    - **yoklama**: eski davranış (getUpdates daemon thread). Webhook kapalıyken ya da
      setWebhook başarısız olduğunda komutlar tamamen susmasın diye buraya düşülür;
      önce eski webhook kaydı silinir (yoksa 409).
    - **kapali**: token/chat_id yok - bot yalnızca alarm gönderir.

    `isleyici` yalnızca testler için verilir (ağa çıkmayan sahte dinleyici).
    """
    if notifier is None or not getattr(notifier, "enabled", False):
        # PUBLIC hedef varsa yayın sürer ama KOMUTLAR çalışmaz: komut yalnız DM'den
        # okunur (kanala üye mesaj yazamaz). Kullanıcı "bot çalışıyor ama /durum
        # cevap vermiyor" durumunu ancak bu satırdan anlayabilir.
        if getattr(notifier, "public_enabled", False):
            logger.warning(
                "Telegram komutları KAPALI: TELEGRAM_CHAT_ID (DM) tanımlı değil. "
                "Public hedefe yayın sürer ama /panel,/durum gibi komutlar çalışmaz; "
                "komutlar için DM chat_id ekle.")
        else:
            logger.info("Telegram komut dinleyicisi başlatılmadı (token/chat_id yok)")
        return {"mod": "kapali", "listener": None, "processor": None}
    if isleyici is None:
        isleyici = listener_factory(
            token=notifier.token,
            allowed_chat_id=notifier.chat_id,
            handlers=komutlar,
            help_text=yardim_metni,
            komutlari_yoksay=tarama_suruyor,
        )
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
                f"(yalnızca chat_id {notifier.chat_id})"
            )
            return {"mod": "webhook", "listener": None, "processor": isleyici}
        else:
            logger.warning("Webhook kurulamadi - yoklama moduna donuluyor")
    # Yoklama moduna dönerken eski webhook kaydı kalırsa getUpdates 409 alır.
    delete_webhook_fn(token=notifier.token)
    if isleyici.start():
        logger.info(f"Telegram komutları aktif (yoklama): {liste} "
                    f"(yalnızca chat_id {notifier.chat_id})")
        return {"mod": "yoklama", "listener": isleyici, "processor": None}
    return {"mod": "kapali", "listener": None, "processor": None}
