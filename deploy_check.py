#!/usr/bin/env python3
"""Kurulum doktoru — Render + Supabase + Telegram zincirini tek komutla doğrular.

Kullanım (yerelde, telefondan Termux'ta veya Render Shell'de):

    python deploy_check.py
    python deploy_check.py --url https://formation-bot-xxxx.onrender.com
    python deploy_check.py --url https://formation-bot-xxxx.onrender.com --test-key k7m2x9
    python deploy_check.py --env-file .env --send-test-message
    python deploy_check.py --skip-network          # sadece dosya/env kontrolü

Ne yapar:
  1. Repo tarafı: .python-version (Render 3.12 sabiti), requirements pinleri,
     .github/workflows/keepalive.yml varlığı, yerel bot_data önbelleği.
  2. Env: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (komutlar için gerekli),
     Supabase env'leri (opsiyonel) tanımlı mı? Değerleri ASLA yazdırmaz.
  3. Supabase varsa: tablo gerçekten var mı? (404 -> SQL çalıştırılmamış,
     401/403 -> anahtar yanlış, 200 -> hazır) ve bot canlı mı (state:heartbeat
     yaşı); yoksa analiz yine çalışır.
  4. Telegram: getMe ile token; istenirse gerçek test mesajı. Ardından
     getWebhookInfo ile KOMUT YOLU: webhook kayıtlı mı, teslim hatası
     (`last_error_message`) var mı, bekleyen güncelleme birikmiş mi? —
     "DM'den komut yazıyorum, cevap gelmiyor" sorusunun ilk bakılacak yeri.
  5. Render: https://<servis>.onrender.com/health ayakta mı; /test ucu açık mı.

Çıkış kodu 0 = kritik hata yok, 1 = en az bir HATA var (uyarılar kodu bozmaz).
Canlı modda (--url) eksik Telegram env'i = HATA; opsiyonel Supabase env'i eksikliği uyarıdır.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

OK = "OK  "
WARN = "UYARI"
FAIL = "HATA"

_sayac = {OK: 0, WARN: 0, FAIL: 0}


def _kisa(metin: str, sinir: int = 180) -> str:
    """Uzun istisna metinlerini tek satira indirir (okunabilirlik)."""
    tek = " ".join(str(metin).split())
    return tek if len(tek) <= sinir else tek[: sinir - 1] + "…"


def satir(seviye: str, baslik: str, detay: str = "") -> None:
    _sayac[seviye] = _sayac.get(seviye, 0) + 1
    isaret = {OK: "✅", WARN: "⚠️ ", FAIL: "❌"}[seviye]
    metin = f"{isaret} [{seviye}] {baslik}"
    if detay:
        metin += f"\n           {detay}"
    print(metin)


def bolum(baslik: str) -> None:
    print()
    print("=" * 72)
    print(baslik)
    print("=" * 72)


def _anahtari_temizle(deger) -> str:
    """Env değerlerindeki tırnak/boşluk kirliliğini temizle."""
    if deger is None:
        return ""
    s = str(deger).strip()
    while len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        s = s[1:-1].strip()
    return s.strip()


def _oku_env_dosyasi(yol: Path) -> dict:
    """Minimal .env okuyucu (python-dotenv bağımlılığı olmadan).

    Hiçbir değeri loglamaz; yalnızca sözlük döndürür.
    """
    veri: dict[str, str] = {}
    if not yol.exists():
        return veri
    for ham in yol.read_text(encoding="utf-8", errors="replace").splitlines():
        satir_ = ham.strip()
        if not satir_ or satir_.startswith("#") or "=" not in satir_:
            continue
        anahtar, _, deger = satir_.partition("=")
        veri[anahtar.strip()] = _anahtari_temizle(deger)
    return veri


def env_degeri(anahtar: str, dosya_env: dict) -> str:
    return _anahtari_temizle(os.environ.get(anahtar) or dosya_env.get(anahtar) or "")


def _jwt_rolu(anahtar: str) -> str:
    """JWT payload'ındaki 'role' alanını okur (imza doğrulaması yapmaz, sır yazmaz)."""
    k = _anahtari_temizle(anahtar)
    if k.count(".") != 2 or not k.startswith("eyJ"):
        return ""
    try:
        payload = k.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        veri = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8", "replace"))
        return str(veri.get("role", ""))
    except Exception:  # noqa: BLE001 - çözülemeyen token sessizce geçilir
        return ""


def anahtar_turu(anahtar: str) -> str:
    """Supabase anahtar türünü değerini loglamadan döndür."""
    k = _anahtari_temizle(anahtar)
    if not k:
        return "boş"
    if k.startswith("sb_secret_"):
        return "yeni secret key (sb_secret_)"
    if k.startswith("sb_publishable_"):
        return "publishable key (sb_publishable_)"
    if k.startswith("eyJ") and k.count(".") == 2:
        rol = _jwt_rolu(k)
        if rol == "service_role":
            return "legacy JWT (service_role)"
        if rol == "anon":
            return "legacy JWT (anon)"
        if rol:
            return f"legacy JWT ({rol})"
        return "legacy JWT"
    if k.startswith("sb_"):
        return f"yeni anahtar ({k[:20]}...)"
    return "bilinmeyen format"


def supabase_basliklari(service_key: str) -> dict:
    """Supabase REST için doğru başlıkları üret.

    Yeni anahtarlar (sb_secret_, sb_publishable_) JWT değildir;
    Authorization: Bearer gönderilirse 401 Invalid JWT döner.
    Sadece apikey başlığı gönderilmeli. Legacy eyJ... JWT'lerde eski davranış
    (apikey + Bearer) korunmalı.
    """
    k = _anahtari_temizle(service_key)
    basliklar = {
        "apikey": k,
        "Accept": "application/json",
    }
    if k.startswith("sb_"):
        # Yeni anahtarlar apikey-only
        return basliklar
    if k.startswith("eyJ") and k.count(".") == 2:
        basliklar["Authorization"] = f"Bearer {k}"
        return basliklar
    # Bilinmeyen: apikey-only (güvenli)
    return basliklar


def kontrol_repo() -> None:
    bolum("1) REPO TARAFI")

    pyver = REPO_ROOT / ".python-version"
    if pyver.exists():
        icerik = pyver.read_text(encoding="utf-8").strip()
        if icerik.startswith("3.12"):
            satir(OK, f".python-version = {icerik}", "Render bu dosyayı okur (varsayılan 3.14'te pandas derlenemez).")
        else:
            satir(WARN, f".python-version = {icerik}", "3.12 önerilir: pandas 2.2.2 / numpy 1.26.4 için cp312 tekerleği var.")
    else:
        satir(FAIL, ".python-version yok",
              "Render varsayılanı Python 3.14 olur ve 'pip install' pandas'ı kaynaktan derlemeye çalışıp patlar.")

    req = REPO_ROOT / "requirements.txt"
    if not req.exists():
        satir(FAIL, "requirements.txt yok", "Build Command: pip install -r requirements.txt")
    else:
        icerik = req.read_text(encoding="utf-8")
        for paket in ("pandas==2.2.2", "numpy==1.26.4", "yfinance"):
            if paket.split("==")[0] in icerik:
                satir(OK, f"requirements içinde {paket.split('==')[0]} var")
        if "borsapy" in icerik and not icerik.count("# borsapy"):
            satir(WARN, "requirements.txt borsapy içeriyor",
                  "borsapy Python 3.14'te Rust/C zinciri getirir; repo kodu import etmiyor -> çıkarın.")
        satir(OK, "Build Command: pip install -r requirements.txt",
              "Start Command: python main.py (render.yaml / Dashboard)")

    wf = REPO_ROOT / ".github" / "workflows" / "keepalive.yml"
    if wf.exists():
        icerik = wf.read_text(encoding="utf-8")
        cron_ok = '"*/5 * * * *"' in icerik or "*/5 * * * *" in icerik
        satir(OK, "keep-alive iş akışı var (.github/workflows/keepalive.yml)",
              "cron */5" + ("" if cron_ok else " (beklenenden farklı)"))
    else:
        satir(WARN, "keep-alive iş akışı yok",
              "Render Free 15 dk hareketsizlikte uyur; bu dosya servisi uyanık tutar.")

    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if ci.exists():
        satir(OK, "CI iş akışı var (.github/workflows/ci.yml)",
              "Aynı Python 3.12 + kurulum + /health duman testini deploy'dan önce koşar.")

    data_dir = REPO_ROOT / "bot_data"
    if data_dir.is_dir():
        hisseler = sorted({p.stem for p in data_dir.glob("*.json") if not p.stem.endswith("_gunluk")})
        if hisseler:
            satir(OK, f"yerel önbellek: {len(hisseler)} hisse (bot_data/)",
                  "Render'da disk kalıcı DEĞİL; ilk açılış bu dosyalarla hızlanır, sonrası Supabase'e yazılır.")
        else:
            satir(WARN, "bot_data boş", "İlk açılışta 48 hisse Yahoo'dan çekilir (birkaç dakika sürer).")
    else:
        satir(WARN, "bot_data/ yok", "İlk açılışta tüm evren Yahoo'dan indirilir.")


def kontrol_env(dosya_env: dict, canli_mod: bool = False) -> dict:
    bolum("2) ORTAM DEĞİŞKENLERİ (Render → Environment)")

    beklenti = [
        ("SUPABASE_URL", False, "İsteğe bağlı: Supabase → Settings → API → Project URL (sonda /rest/v1 OLMADAN)"),
        ("SUPABASE_SERVICE_ROLE_KEY", False, "İsteğe bağlı uzak cache/state için service_role JWT veya sb_secret_... anahtarı"),
        ("TELEGRAM_BOT_TOKEN", True, "@BotFather → /newbot → 'Use this token'"),
        ("TELEGRAM_CHAT_ID", True, "@userinfobot'un verdiği Id (kendine mesaj için pozitif sayı; KOMUTLAR buna bağlı)"),
        ("TELEGRAM_GROUP_ID", False, "PUBLIC KANAL hedefi (@bisthisseveri veya -100…): kanal yayını bununla açılır (eski adı TELEGRAM_CHANNEL_ID)"),
        ("TELEGRAM_WEBHOOK_SECRET", False, "İsteğe bağlı: webhook modunu açar (komutlar Telegram → /webhook ile gelir; uyuyan servisi Telegram uyandırır)"),
        ("RENDER_EXTERNAL_URL", False, "Render otomatik verir (webhook adresi buradan üretilir); render.yaml'de tanımlıdır"),
        ("BOT_PROFILE", False, "Dengeli / Hassas / Seçici"),
        ("TELEGRAM_TEST_KEY", False, "İsteğe bağlı: /test ucunu açar (telefondan Telegram testi)"),
        ("SUPABASE_STORE_PREFIX", False, "Varsayılan formation-bot: ; aynı tabloyu paylaşan 2. kopya için değiştirin"),
        ("BOT_INSTANCE_ID", False, "Varsayılan hostname:pid ; ikinci canlı kopya varsa farklı ad verin (B10)"),
    ]

    degerler = {}
    for anahtar, zorunlu, aciklama in beklenti:
        deger = env_degeri(anahtar, dosya_env)
        degerler[anahtar] = deger
        if deger:
            satir(OK, f"{anahtar} tanımlı ({len(deger)} karakter)")
        elif zorunlu:
            seviye = FAIL if canli_mod else WARN
            satir(seviye, f"{anahtar} tanımlı değil", aciklama)
        else:
            satir(OK, f"{anahtar} tanımlı değil (opsiyonel)", aciklama)

    if not degerler.get("TELEGRAM_BOT_TOKEN") and not degerler.get("TELEGRAM_CHAT_ID"):
        seviye = FAIL if canli_mod else WARN
        satir(seviye, "Telegram kapalı olacak", "Token/chat_id yoksa bot çalışır ama hiç mesaj göndermez (log: 'notifier pasif').")
    if not degerler.get("SUPABASE_URL") and not degerler.get("SUPABASE_SERVICE_ROLE_KEY"):
        satir(WARN, "Supabase kapalı olacak",
              "Analiz yine çalışır; Render restart/deploy sonrası yerel OHLCV önbelleği ve Telegram sayaçları kalıcı olmayabilir.")
    anahtar = degerler.get("SUPABASE_SERVICE_ROLE_KEY", "")
    rol = _jwt_rolu(anahtar)
    tur = anahtar_turu(anahtar) if anahtar else ""
    if anahtar.startswith("sb_publishable_"):
        satir(WARN, f"SUPABASE_SERVICE_ROLE_KEY 'publishable' anahtar ({tur})",
              "RLS açıkken bu anahtar 401/403 alır; service_role JWT veya 'sb_secret_...' kullanın.")
    elif rol == "anon":
        satir(WARN, f"SUPABASE_SERVICE_ROLE_KEY 'anon' rolünde ({tur})",
              "service_role JWT veya 'sb_secret_...' kullanın; anon anahtar tabloya yazamaz.")
    elif rol == "service_role":
        satir(OK, f"Supabase anahtarı service_role rolünde ({tur})")
    elif anahtar.startswith("sb_secret_"):
        satir(OK, f"Supabase anahtarı yeni secret key ({tur})")
    elif anahtar:
        satir(OK, f"Supabase anahtar türü: {tur}")
    return degerler


def store_onek(deger: str = "") -> str:
    """SUPABASE_STORE_PREFIX'i normalize eder (uygulamayla aynı kural).

    Boş -> "formation-bot:" (uygulama varsayılanı); off/none/yok/0 -> öneksiz.
    """
    ham = (deger or "").strip()
    if not ham:
        return "formation-bot:"
    if ham.lower() in ("off", "none", "yok", "0"):
        return ""
    return ham


def heartbeat_seviyesi(yas_sn):
    """Heartbeat yaşına göre (seviye, başlık, detay) döner; None = bilinmiyor.

    Eşikler: <3 sa taze · <72 sa uyarı (seans dışı/tatil normal) · >=72 sa bayat.
    """
    if yas_sn is None:
        return (WARN, "Heartbeat okunamadı",
                "state:heartbeat kaydı yok ya da bozuk: bot henüz hiç tarama yapmamış olabilir.")
    if yas_sn < 3 * 3600:
        return (OK, f"Heartbeat taze ({yas_sn / 60:.0f} dk)",
                "Bot canlı yazıyor; /health?strict=1 ile bu kontrol monitöre devredilebilir.")
    if yas_sn < 72 * 3600:
        return (WARN, f"Heartbeat {yas_sn / 3600:.1f} saat",
                "Seans dışı/tatil için normaldir; seans içinde 30 dk'yı geçerse bot tıkanmış olabilir.")
    return (FAIL, f"Heartbeat {yas_sn / 3600:.1f} saat (bayat)",
            "Bot 3 gündür heartbeat yazmıyor: Render loglarını ve son deploy olayını kontrol edin.")


def _heartbeat_kontrol(kok: str, basliklar: dict, onek: str) -> None:
    """Supabase'deki state:heartbeat kaydından botun canlı olup olmadığını raporlar."""
    try:
        import requests
    except ImportError:
        return
    anahtar = f"{onek}state:heartbeat"
    try:
        r = requests.get(
            f"{kok}/rest/v1/bot_store",
            headers=basliklar,
            params={"select": "payload", "store_key": f"eq.{anahtar}", "limit": 1},
            timeout=12,
        )
    except Exception as exc:  # noqa: BLE001
        satir(WARN, "Heartbeat okunamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return
    if r.status_code != 200:
        satir(WARN, "Heartbeat okunamadı", f"HTTP {r.status_code}: {_kisa(r.text)}")
        return
    yas_sn = None
    try:
        satirlar = r.json()
        payload = (satirlar[0] or {}).get("payload") if satirlar else None
        ham = (payload or {}).get("last_scan") if isinstance(payload, dict) else None
        if ham:
            damga = datetime.fromisoformat(str(ham))
            if damga.tzinfo is None:
                damga = damga.replace(tzinfo=timezone.utc)
            yas_sn = max(0.0, (datetime.now(timezone.utc) - damga).total_seconds())
    except Exception:  # noqa: BLE001 - bozuk kayıt "bilinmiyor" sayılır
        yas_sn = None
    satir(*heartbeat_seviyesi(yas_sn))


def kontrol_supabase(url: str, anahtar: str, onek: str = None) -> None:
    bolum("3) SUPABASE")
    if not url or not anahtar:
        satir(WARN, "Atlandı", "SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY birlikte gerekli.")
        return

    try:
        import requests
    except ImportError:
        satir(WARN, "Atlandı", "requests kurulu değil (pip install -r requirements.txt).")
        return

    temiz = _anahtari_temizle(url).rstrip("/")
    if temiz.endswith("/rest/v1"):
        temiz = temiz[: -len("/rest/v1")]
        satir(WARN, "SUPABASE_URL sonunda /rest/v1 var",
              "Kod bunu temizliyor, ama doğrusu: https://<ref>.supabase.co")
    if not temiz.startswith("https://"):
        satir(WARN, "SUPABASE_URL https:// ile başlamıyor", f"Girilen: {temiz[:40]}")

    basliklar = supabase_basliklari(anahtar)
    # Content-Type ve Prefer sadece yazma için, okuma için de ekleyelim zararsız
    basliklar_okuma = {**basliklar, "Accept": "application/json"}
    tur = anahtar_turu(anahtar)

    try:
        r = requests.get(
            f"{temiz}/rest/v1/bot_store",
            headers=basliklar_okuma,
            params={"select": "store_key", "limit": 1},
            timeout=12,
        )
    except Exception as exc:  # noqa: BLE001 - kullanıcıya tek satır özet yeter
        satir(FAIL, "Supabase'e ulaşılamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200:
        satir(OK, f"Supabase bağlantısı OK ({tur})", f"{temiz} · tablo: bot_store")
    elif r.status_code == 404:
        satir(FAIL, "Tablo yok (HTTP 404)",
              "Supabase → SQL Editor → New query → supabase_schema.sql içeriğini yapıştır → Run.")
    elif r.status_code in (401, 403):
        # Anahtar türü ipucu
        ipucu = ""
        if "sb_publishable_" in anahtar or tur.startswith("publishable"):
            ipucu = "Publishable anahtar (sb_publishable_) RLS açıkken yazamaz ve 401/403 döner. Doğrusu: sb_secret_... veya service_role JWT."
        elif tur.startswith("legacy JWT (anon)") or _jwt_rolu(anahtar) == "anon":
            ipucu = "Anon anahtar (anon rolü) tabloya yazamaz, 401/403 alır. Doğrusu: service_role JWT (eyJ... service_role) veya sb_secret_..."
        elif "Invalid JWT" in r.text or "invalid" in r.text.lower():
            ipucu = f"Anahtar türü {tur} için Bearer başlığı hatalı olabilir. sb_secret_/sb_publishable_ anahtarlarında sadece apikey gönderilmeli (kod bunu yapıyor). Anahtar iptal edilmiş veya yanlış kopyalanmış olabilir."
        else:
            ipucu = f"Anahtar türü: {tur}. service_role yerine anon/publishable girilmiş ya da anahtar iptal edilmiş. Doğrusu: Settings → API → service_role (veya Secret key sb_secret_...)."
        satir(FAIL, f"Anahtar reddedildi (HTTP {r.status_code}) [{tur}]",
              ipucu)
    elif r.status_code == 400:
        satir(FAIL, "İstek reddedildi (HTTP 400)",
              "URL biçimini kontrol edin: https://<ref>.supabase.co (sonda /rest/v1 olmadan).")
    else:
        satir(FAIL, f"Beklenmeyen yanıt (HTTP {r.status_code})", _kisa(r.text))
        return

    # Şema gerçekten kullanılabilir mi: bir satır yazıp okuyalım (zararsız test anahtarı).
    if r.status_code == 200:
        try:
            test_anahtar = "deploy_check:ping"
            yaz = requests.post(
                f"{temiz}/rest/v1/bot_store",
                headers={**basliklar, "Content-Type": "application/json",
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                json={"store_key": test_anahtar, "payload": {"t": time.time()}},
                timeout=12,
            )
            if yaz.status_code in (200, 201, 204):
                satir(OK, "Yazma izni var (service_role doğru)", "commit/replace politikası çalışıyor.")
            else:
                satir(FAIL, f"Yazma başarısız (HTTP {yaz.status_code})",
                      "service_role anahtarı kullanılmalı; yazma için upsert politikası şart. " + yaz.text[:160])
        except Exception as exc:  # noqa: BLE001
            satir(WARN, "Yazma testi yapılamadı", f"{type(exc).__name__}: {_kisa(exc)}")

    # B-4: bot gerçekten yaşıyor mu? (heartbeat yaşı; /health?strict=1 ile aynı kaynak)
    _heartbeat_kontrol(temiz, basliklar_okuma, store_onek(onek if onek is not None
                                                          else os.environ.get("SUPABASE_STORE_PREFIX", "")))


def kontrol_telegram(token: str, chat_id: str, mesaj_gonder: bool) -> None:
    bolum("4) TELEGRAM")
    if not token:
        satir(WARN, "Atlandı", "TELEGRAM_BOT_TOKEN yok (bot çalışır ama mesaj göndermez).")
        return

    try:
        import requests
    except ImportError:
        satir(WARN, "Atlandı", "requests kurulu değil.")
        return

    if ":" not in token:
        satir(FAIL, "Token biçimi hatalı", "'123456789:AA...' gibi iki nokta içermeli.")
        return

    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=12)
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "Telegram'a ulaşılamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200:
        kullanici = ((r.json() or {}).get("result") or {}).get("username", "?")
        satir(OK, f"Token geçerli (bot: @{kullanici})")
    elif r.status_code == 401:
        satir(FAIL, "Token reddedildi (HTTP 401)",
              "BotFather token'ının tamamını kopyalayın; sızdıysa /revoke ile yenileyin.")
        return
    else:
        satir(FAIL, f"getMe beklenmeyen yanıt (HTTP {r.status_code})", _kisa(r.text, 160))
        return

    if not chat_id:
        satir(WARN, "chat_id yok", "Telegram'a gönderim için TELEGRAM_CHAT_ID şart (@userinfobot).")
        return
    satir(OK, "Komutlar açık: /formasyonlar · /durum · /tara · /yardim",
          "Komutlar yalnızca bu chat_id'den kabul edilir. Aynı token'ı ikinci bir kopya "
          "(Termux/PC) da dinlerse Telegram 409 Conflict verir ve komutlar çalışmaz.")
    if not chat_id.lstrip("-").isdigit():
        satir(WARN, "chat_id sayı değil", "Kendine mesaj için pozitif Id, grup için -100... ile başlar.")
    else:
        satir(OK, f"chat_id sayı biçiminde (uzunluk {len(chat_id)})")

    if not mesaj_gonder:
        satir(OK, "Gerçek mesaj gönderilmedi", "Denemek için: --send-test-message")
        return

    metin = "✅ Formation-Bot kurulum kontrolü: bu mesajı görüyorsan Telegram tarafı tamam."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": metin},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "Test mesajı gönderilemedi", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200:
        satir(OK, "Test mesajı gönderildi", "Telegram'ı açıp kontrol edin.")
    else:
        aciklama = r.text[:200]
        ipucu = ""
        if "chat not found" in aciklama:
            ipucu = " Kendi botunuza Telegram'da bir kez 'Start' yazın."
        elif "bot was blocked" in aciklama:
            ipucu = " Bot engellenmiş: sohbette Unblock yapın."
        satir(FAIL, f"sendMessage başarısız (HTTP {r.status_code})", aciklama + ipucu)


def _webhook_sir_gizle(metin: str) -> str:
    """`…/webhook/<sır>` geçen metinlerde sırrı maskeler.

    Telegram'ın `last_error_message` alanı kayıtlı adresi içerebilir; eski
    biçimde adresin son parçası sırdır ve ekrana/loglara düşmemelidir.
    """
    metin = str(metin or "")
    if "/webhook/" not in metin:
        return metin
    cikti: list = []
    kalan = metin
    while "/webhook/" in kalan:
        bas, _, kalan = kalan.partition("/webhook/")
        cikti.append(bas + "/webhook/")
        i = 0
        while i < len(kalan) and kalan[i] not in " \t\r\n\"'),;":
            i += 1
        if i > 0:
            cikti.append("***")
            kalan = kalan[i:]
    cikti.append(kalan)
    return "".join(cikti)


def _webhook_adres_gizle(url: str) -> str:
    """Eski biçimdeki sırlı yolu (…/webhook/<secret>) maskeler; sır ekrana düşmez."""
    return _kisa(_webhook_sir_gizle((url or "").strip()), 120)


def kontrol_telegram_yol(token: str, webhook_secret_tanimli: bool) -> None:
    """Komutların gerçekten hangi yoldan geldiğini Telegram tarafından doğrular.

    NEDEN: "DM'den /yardim yazıyorum, cevap gelmiyor" şikâyetinin en sık iki
    sebebi yalnız buradan görülür:

      1. **409 çakışması**: Telegram'da webhook kayıtlı ama bot `getUpdates`
         yoklaması kullanıyor → güncellemeler hiç gelmez.
      2. **Teslim hatası**: Webhook kayıtlı ama Telegram `last_error_message`
         ile teslim edemiyor (servis 5xx döndü, adres yanlış, sır uyuşmuyor…).

    Ayrıca bekleyen güncelleme sayısı, komutların birikip birikmediğini gösterir
    (servis uykudayken Telegram mesajları kuyrukta tutar, 24 saat sonra atar).
    """
    if not token:
        return
    try:
        import requests
    except ImportError:
        return

    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=12)
    except Exception as exc:  # noqa: BLE001
        satir(WARN, "Webhook durumu okunamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return
    if getattr(r, "status_code", 0) != 200:
        satir(WARN, f"getWebhookInfo beklenmeyen yanıt (HTTP {getattr(r, 'status_code', '?')})",
              _kisa(getattr(r, "text", ""), 160))
        return
    try:
        bilgi = ((r.json() or {}).get("result") or {})
    except Exception:  # noqa: BLE001
        satir(WARN, "getWebhookInfo gövdesi çözümlenemedi", "")
        return

    url = (bilgi.get("url") or "").strip()
    bekleyen = bilgi.get("pending_update_count")
    son_hata = (bilgi.get("last_error_message") or "").strip()
    hata_zamani = bilgi.get("last_error_date")

    if url and not webhook_secret_tanimli:
        satir(FAIL, "Webhook kayıtlı ama bot yoklama modunda",
              "TELEGRAM_WEBHOOK_SECRET tanımlı değil; getUpdates 409 Conflict alır ve DM "
              "komutları çalışmaz. Ya secret'ı tanımlayın ya da webhook'u silin "
              f"(deleteWebhook). Kayıtlı adres: {_webhook_adres_gizle(url)}")
    elif url:
        satir(OK, f"Webhook kayıtlı: {_webhook_adres_gizle(url)}",
              "Komutlar Telegram → /webhook üzerinden gelir (sunucu ayakta olmalı).")
    elif webhook_secret_tanimli:
        satir(WARN, "Webhook bekleniyor ama kayıtlı değil",
              "Bot açılışta setWebhook yapamamış (RENDER_EXTERNAL_URL/HTTPS?). Komutlar "
              "getUpdates yoklamasına düşer; servis uykudaysa yanıt gelmez.")
    else:
        satir(OK, "Webhook yok; komutlar getUpdates yoklamasıyla gelir",
              "Bu yolda 15 dakikadan eski komutlar açılışta atlanır; servis uykuya "
              "girdiyse komut saatler sonra işlenmez.")

    if bekleyen:
        satir(WARN, f"Telegram'da bekleyen güncelleme: {bekleyen}",
              "Bot bunları işlemiyor: servis uykuda/çökmüş ya da webhook adresi hatalı "
              "olabilir. /health → komut alanına ve Render loglarına bakın.")

    if son_hata:
        yas = None
        if hata_zamani:
            try:
                yas = max(0, int(time.time() - float(hata_zamani)))
            except (TypeError, ValueError):
                yas = None
        yas_metni = "" if yas is None else f" ({yas // 60} dk önce)"
        gizli_hata = _kisa(_webhook_sir_gizle(son_hata), 160)
        if yas is not None and yas > 3600:
            satir(WARN, f"Telegram webhook teslim hatası (eski){yas_metni}", gizli_hata)
        else:
            satir(FAIL, f"Telegram webhook teslim hatası{yas_metni}", gizli_hata)


def kontrol_public_hedef(token: str, grup_id: str, chat_id: str = "") -> bool:
    """Kanal/grup hedefini doğrular: bot orada mı, yönetici mi, mesaj yazabilir mi?

    NEDEN: Public yayın DM'den bağımsız çalışır; hedef yanlışsa bot çalışır ama
    kanala hiçbir şey düşmez ve bunu ancak loglardan anlarsınız. Bu kontrol
    kurulumun en kritik adımını (yönetici + mesaj izni) tek komutla doğrular.
    Döner: hedef hazır mı (özet satırı için).
    """
    if not token:
        # Token yoksa Telegram bölümü zaten uyarı verdi.
        return False
    ready = False
    try:
        import requests
    except ImportError:
        return False
    if not grup_id:
        satir(WARN, "Public kanal hedefi yok (TELEGRAM_GROUP_ID)",
              "Kanal yayını kapalı: yalnız DM çalışır. Kanal açtıysanız KANAL_ACILIS_PAKETI.md "
              "adımlarını izleyin: TELEGRAM_GROUP_ID=@kanal_adi + bot YÖNETİCİ.")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/getChat",
                          json={"chat_id": grup_id}, timeout=12)
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "Public hedefe ulaşılamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return False
    veri = (r.json() or {}) if r.status_code == 200 else {}
    sohbet = veri.get("result") or {}
    if not sohbet:
        ipucu = "Bot hedefe ekli değil ya da adres yanlış (@... / -100...)."
        if "channel" in (r.text or "") or "chat not found" in (r.text or "").lower():
            ipucu = "Bot kanala eklenmeli ve YÖNETİCİ yapılmalı (kanal → Yöneticiler → Bot Ekle)."
        satir(FAIL, f"Public hedef bulunamadı ({grup_id})", ipucu)
        return False
    baslik = sohbet.get("title") or sohbet.get("username") or grup_id
    tip = sohbet.get("type", "?")
    satir(OK, f"Public hedef bulundu: {baslik} ({tip})")

    # Bot kimliği + üyelik durumu
    uye = {}
    try:
        ben = requests.post(f"https://api.telegram.org/bot{token}/getMe", timeout=12)
        bot_id = ((ben.json() or {}).get("result") or {}).get("id")
        if bot_id:
            ru = requests.post(f"https://api.telegram.org/bot{token}/getChatMember",
                               json={"chat_id": grup_id, "user_id": bot_id}, timeout=12)
            if ru.status_code == 200:
                uye = (ru.json() or {}).get("result") or {}
    except Exception as exc:  # noqa: BLE001
        satir(WARN, "Üyelik durumu okunamadı", f"{type(exc).__name__}: {_kisa(exc)}")

    durum = str(uye.get("status") or "?")
    if durum in ("administrator", "creator"):
        satir(OK, "Bot hedefte YÖNETİCİ", "Kanal listesinde 1 mesaj/gün yerine kalıcı görünür.")
        if tip == "channel":
            if uye.get("can_post_messages"):
                satir(OK, "Kanal izni var: Mesaj gönderme", "Yayın açık.")
                ready = True
            else:
                satir(FAIL, "Kanal izni KAPALI: Mesaj gönderme",
                      "Kanal → Yöneticiler → bot → 'Mesaj gönderme' açık olmalı; yoksa gönderim 403 döner.")
        else:
            satir(OK, "Grup: mesaj gönderme serbest", "Yönetici bot grup ayarlarından etkilenmez.")
            ready = True
    elif durum == "left":
        satir(FAIL, "Bot hedefte YOK (left)",
              "Botu kanala/grupa ekleyin; kanalda ayrıca YÖNETİCİ yapın (Mesaj gönderme izni).")
    else:
        satir(FAIL, f"Bot yönetici değil (status={durum})",
              "Kanal → Yöneticiler → Bot Ekle → 'Mesaj gönderme' (+ sabit mesaj için 'Mesajları sabitle').")

    if tip == "channel" and uye and not uye.get("can_post_messages"):
        satir(WARN, "Sabit karşılama için 'Mesajları sabitle' izni",
              "İzin yoksa kanal_acilis.py --uygula yalnız açıklama yazar.")
    if not chat_id:
        satir(WARN, "DM chat_id yok: komutlar kapalı",
              "Public yayın sürer ama /panel,/durum çalışmaz. Komutlar için TELEGRAM_CHAT_ID ekleyin.")
    return ready


def _health_hedefi(url: str) -> str:
    temiz = _anahtari_temizle(url).rstrip("/")
    if temiz.endswith("/health") or temiz.endswith("/"):
        return temiz if temiz.endswith("/health") else temiz + "health"
    # Servis kökü verildiyse /health'e tamamla; başka bir yol verildiyse dokunma.
    if temiz.count("/") == 2:
        return temiz + "/health"
    return temiz


def _yerel_commit() -> str:
    """Yerel main/HEAD kısa commit'i (git yoksa boş)."""
    import subprocess

    try:
        cikti = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        return cikti.stdout.strip() if cikti.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - git yoksa karşılaştırma yapılmaz
        return ""


def _commit_karsilastir(canli_commit: str) -> None:
    """Canlı sürüm yerelden farklıysa: deploy düşmemiş ya da eski kod çalışıyor."""
    yerel = _yerel_commit()
    if not canli_commit or not yerel:
        return
    if canli_commit == yerel[:7] or yerel.startswith(canli_commit) or canli_commit.startswith(yerel):
        satir(OK, f"Canlı sürüm yerelle aynı ({canli_commit})")
        return
    satir(WARN, f"Canlı sürüm yerelden FARKLI (canlı {canli_commit} ≠ yerel {yerel})",
          "Render yeni commit'i henüz deploy etmemiş olabilir: Dashboard → servis → "
          "Events'te 'Deploy succeeded' var mı? Yoksa Manual Deploy → Deploy latest commit. "
          "Auto-Deploy kapalıysa her merge'de elle deploy gerekir.")


def kontrol_render(url: str, test_key: str) -> None:
    bolum("5) RENDER SERVİSİ")
    if not url:
        satir(WARN, "Atlandı", "Adresi verin: --url https://<servis-adin>.onrender.com")
        return

    try:
        import requests
    except ImportError:
        satir(WARN, "Atlandı", "requests kurulu değil.")
        return

    hedef = _health_hedefi(url)
    try:
        r = requests.get(hedef, timeout=120)  # uyuyan Free servis ~1 dk'da uyanır
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, f"{hedef} yanıt vermedi", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200:
        try:
            govde = r.json()
        except ValueError:
            govde = {}
        if govde.get("status") == "ok":
            canli_commit = str(govde.get("commit") or "")
            detay = hedef + (f" · canlı sürüm: {canli_commit}" if canli_commit else "")
            satir(OK, f"/health ayakta ({govde.get('service', '?')})", detay)
            _commit_karsilastir(canli_commit)
        else:
            satir(WARN, "200 döndü ama gövde beklenen JSON değil", str(govde)[:160])
    elif r.status_code in (502, 503, 504):
        satir(WARN, f"Servis şu an uyanıyor/başlamadı (HTTP {r.status_code})",
              "30-60 sn sonra tekrar deneyin. Render → Logs'ta 'Render health endpoint ... başladı' satırını arayın.")
    elif r.status_code == 404:
        satir(FAIL, "HTTP 404 — yol yanlış ya da servis deploy edilmemiş",
              "Health Check Path '/health' olmalı; adres https://<servis>.onrender.com biçiminde olmalı.")
    else:
        satir(FAIL, f"Beklenmeyen yanıt (HTTP {r.status_code})", _kisa(r.text))

    if not test_key:
        satir(OK, "/test ucu denenmedi", "Göndermeyi doğrulamak için: --test-key <TELEGRAM_TEST_KEY>")
        return

    try:
        # A7 sonrası /test anahtarı varsayılan BAŞLIKTAN okunur (X-Test-Key).
        r = requests.get(
            hedef.rsplit("/health", 1)[0] + "/test",
            headers={"X-Test-Key": test_key},
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "/test çağrısı başarısız", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200 and r.json().get("ok"):
        satir(OK, "/test Telegram mesajı gönderdi", "Telegram'da 'test mesaji' görünmeli.")
    elif r.status_code == 404:
        satir(FAIL, "/test kapalı (HTTP 404)",
              "Render → Environment → TELEGRAM_TEST_KEY ekleyin (secret), servis yeniden deploy edilsin.")
    elif r.status_code == 403:
        satir(FAIL, "Anahtar yanlış (HTTP 403)", "Render'daki TELEGRAM_TEST_KEY ile --test-key aynı olmalı.")
    elif r.status_code == 503:
        satir(WARN, "Bot henüz başlamadı (HTTP 503)", "Servis uyanıyor; 30 sn sonra tekrar deneyin.")
    else:
        satir(FAIL, f"/test beklenmeyen yanıt (HTTP {r.status_code})", r.text[:200])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Formation-Bot Render/Supabase/Telegram kurulum doktoru",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--url", help="Render servis adresi (https://<servis>.onrender.com)")
    ap.add_argument("--test-key", default="", help="TELEGRAM_TEST_KEY değeri (/test ucunu dener)")
    ap.add_argument("--env-file", default=".env", help="Okunacak .env dosyası (varsayılan: .env)")
    ap.add_argument("--send-test-message", action="store_true",
                    help="Telegram'a gerçek bir test mesajı gönder")
    ap.add_argument("--skip-network", action="store_true",
                    help="Supabase/Telegram/Render çağrılarını atla (sadece dosya + env)")
    args = ap.parse_args()

    print("Formation-Bot kurulum doktoru")
    print("Kritik sırlar (token/anahtar) hiçbir zaman yazdırılmaz; yalnızca varlık ve uzunluk bilgisi.")

    dosya_env = {}
    env_yolu = (REPO_ROOT / args.env_file) if not Path(args.env_file).is_absolute() else Path(args.env_file)
    if env_yolu.exists():
        dosya_env = _oku_env_dosyasi(env_yolu)
        print(f".env okundu: {env_yolu.name} ({len(dosya_env)} değişken)")
    else:
        print("Not: .env bulunamadı; yalnızca süreç ortam değişkenleri kullanılacak (Render'da normaldir).")

    canli_mod = bool(args.url)
    kontrol_repo()
    degerler = kontrol_env(dosya_env, canli_mod=canli_mod)

    public_hazir = False
    if args.skip_network:
        bolum("AĞ KONTROLLERİ")
        satir(WARN, "--skip-network verildi", "Supabase/Telegram/Render kontrolleri atlandı.")
    else:
        kontrol_supabase(degerler.get("SUPABASE_URL", ""), degerler.get("SUPABASE_SERVICE_ROLE_KEY", ""),
                         degerler.get("SUPABASE_STORE_PREFIX", ""))
        kontrol_telegram(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            degerler.get("TELEGRAM_CHAT_ID", ""),
            args.send_test_message,
        )
        # Komut yolu: webhook mı yoklama mı, Telegram tarafında ne kayıtlı?
        # (DM komutlarının çalışmaması en çok buradan anlaşılır.)
        kontrol_telegram_yol(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            bool(degerler.get("TELEGRAM_WEBHOOK_SECRET", "")),
        )
        public_hazir = kontrol_public_hedef(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            degerler.get("TELEGRAM_GROUP_ID", "") or degerler.get("TELEGRAM_CHANNEL_ID", ""),
            degerler.get("TELEGRAM_CHAT_ID", ""),
        )
        kontrol_render(args.url or "", args.test_key or degerler.get("TELEGRAM_TEST_KEY", ""))

    bolum("ÖZET")
    # Yeni istenen satır: ÖZET: Telegram HAZIR|YOK · Supabase HAZIR|YOK
    telegram_hazir = bool(degerler.get("TELEGRAM_BOT_TOKEN") and degerler.get("TELEGRAM_CHAT_ID"))
    supabase_hazir = bool(degerler.get("SUPABASE_URL") and degerler.get("SUPABASE_SERVICE_ROLE_KEY"))
    kanal_hedefi = (degerler.get("TELEGRAM_GROUP_ID", "") or degerler.get("TELEGRAM_CHANNEL_ID", ""))
    ozet_telegram = "HAZIR" if telegram_hazir else "YOK"
    ozet_supabase = "HAZIR" if supabase_hazir else "YOK"
    # Kanal: hedef tanımlı + (ağ kontrolü yapıldıysa) gerçekten yazabiliyor olmalı.
    ozet_kanal = "YOK"
    if kanal_hedefi:
        ozet_kanal = "HAZIR" if (args.skip_network or public_hazir) else "HEDEF VAR, IZIN YOK"
    print(f"ÖZET: Telegram {ozet_telegram} · Kanal {ozet_kanal} · Supabase {ozet_supabase}")
    print(f"✅ {_sayac[OK]} tamam   ⚠️  {_sayac[WARN]} uyarı   ❌ {_sayac[FAIL]} hata")
    if _sayac[FAIL] == 0 and _sayac[WARN] == 0:
        print("Her şey yerinde: Render tarafı hazır.")
    elif _sayac[FAIL] == 0:
        print("Kritik hata yok. Uyarıların çoğu 'opsiyonel' (örn. TELEGRAM_TEST_KEY) olabilir:")
        print("UYARI satırlarını yukarıdan aşağı okuyun, RENDER_DEPLOY.md §1-5 karşılığını anlatır.")
    else:
        print("HATA satırlarını sırayla düzeltin; her biri için öneri satır altında yazıyor.")
    print("Ayrıntılı rehber: RENDER_DEPLOY.md")
    return 1 if _sayac[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
