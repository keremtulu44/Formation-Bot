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
  3. Supabase varsa: tablo okunabiliyor mu? Yalnız GET yapılır; yazma testi ve
     güncellenmeyen uzak heartbeat üzerinden canlılık kontrolü yapılmaz.
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
from urllib.parse import urlsplit

from secrets_redaction import redact_sensitive_text
from grafik_ayar import GRAFIK_ACIK_DEGERLER, GRAFIK_KAPALI_DEGERLER, otomatik_grafik_acik

REPO_ROOT = Path(__file__).resolve().parent

OK = "OK  "
WARN = "UYARI"
FAIL = "HATA"

_sayac = {OK: 0, WARN: 0, FAIL: 0}


def _kisa(metin: str, sinir: int = 180, *secrets: str) -> str:
    """Sırları çıkardıktan sonra uzun hata metinlerini tek satıra indir."""
    guvenli = redact_sensitive_text(metin, *secrets)
    tek = " ".join(guvenli.split())
    return tek if len(tek) <= sinir else tek[: sinir - 1] + "…"


def _guvenli_url_kaynagi(url: str) -> str:
    """Log için yalnızca origin'i döndür; userinfo, path, query ve fragment yok."""
    try:
        parsed = urlsplit(str(url))
        host = parsed.hostname
        if not parsed.scheme or not host:
            return "[URL gizlendi]"
        host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port is not None:
            host = f"{host}:{port}"
        return f"{parsed.scheme}://{host}"
    except (TypeError, ValueError):
        return "[URL gizlendi]"


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


def _env_bool(deger, varsayilan: bool = False) -> bool:
    """Normalize environment booleans without treating an empty value as False."""
    ham = "" if deger is None else str(deger).strip().lower()
    if not ham:
        return bool(varsayilan)
    return ham not in {"0", "false", "no", "off", "kapali", "kapalı"}


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
        satir(OK, "Önerilen Build Command: pip install -r requirements.txt",
              "Start Command: python main.py; mevcut Render Dashboard ayarları ayrıca doğrulanmalıdır.")

    wf = REPO_ROOT / ".github" / "workflows" / "keepalive.yml"
    if wf.exists():
        icerik = wf.read_text(encoding="utf-8")
        cron_ok = '"*/5 * * * *"' in icerik or "*/5 * * * *" in icerik
        satir(OK, "keep-alive iş akışı var (.github/workflows/keepalive.yml)",
              ("cron */5" if cron_ok else "cron beklenenden farklı")
              + "; gerçek ping sıklığı garanti değildir. scripts/keepalive_audit.py ile gözlemleyin.")
    else:
        satir(WARN, "keep-alive iş akışı yok",
              "Render Free 15 dk hareketsizlikte uyuyabilir; bağımsız izleme/uyandırma gerekir.")

    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if ci.exists():
        satir(OK, "CI iş akışı var (.github/workflows/ci.yml)",
              "Python 3.12 + kurulum + /health duman testi koşar; deploy kapısı için Render Dashboard ayarını doğrulayın.")

    data_dir = REPO_ROOT / "bot_data"
    if data_dir.is_dir():
        hisseler = sorted({p.stem for p in data_dir.glob("*.json") if not p.stem.endswith("_gunluk")})
        if hisseler:
            satir(OK, f"yerel önbellek: {len(hisseler)} sembol (bot_data/)",
                  "Seed ilk açılışı hızlandırabilir. Yeni durum geçici diskte tutulur; Supabase'e yazılmaz.")
        else:
            satir(WARN, "bot_data boş", "İlk açılışta tüm evren (hisse + endeks + makro) Yahoo'dan çekilir; "
                   "birkaç dakika sürer.")
    else:
        satir(WARN, "bot_data/ yok", "İlk açılışta tüm evren Yahoo'dan indirilir.")

    stabil_kaynak = REPO_ROOT / "domain_engines" / "05_stabil.txt"
    if stabil_kaynak.exists():
        import hashlib
        stabil_sha = hashlib.sha256(stabil_kaynak.read_bytes()).hexdigest()
        beklenen_sha = "649896d2ba5860e7c1637e8e7aaae79f8b4574d6de331de7eb53e93f163e6a5e"
        if stabil_sha == beklenen_sha:
            satir(OK, "Stabil sertifikalı kaynak doğrulandı (domain_engines/05_stabil.txt)")
        else:
            satir(FAIL, "domain_engines/05_stabil.txt SHA256 uyuşmuyor",
                  f"beklenen {beklenen_sha[:12]}…, bulunan {stabil_sha[:12]}…")
    else:
        satir(FAIL, "domain_engines/05_stabil.txt bulunamadı",
              "Stabil destek motoru sertifikalı kaynak dosyası olmadan çalışmamalıdır.")


def kontrol_env(dosya_env: dict, canli_mod: bool = False) -> dict:
    bolum("2) ORTAM DEĞİŞKENLERİ (Render → Environment)")

    beklenti = [
        ("SUPABASE_URL", False, "İsteğe bağlı: Supabase → Settings → API → Project URL (sonda /rest/v1 OLMADAN)"),
        ("SUPABASE_SERVICE_ROLE_KEY", False, "İsteğe bağlı eski uzak cache/state okuması için service_role JWT veya sb_secret_... anahtarı"),
        ("TELEGRAM_BOT_TOKEN", True, "@BotFather → /newbot → 'Use this token'"),
        ("TELEGRAM_CHAT_ID", True, "@userinfobot'un verdiği Id (kendine mesaj için pozitif sayı; KOMUTLAR buna bağlı)"),
        ("TELEGRAM_GROUP_ID", False, "PUBLIC GRUP/kanal hedefi (@FormationBot1 veya -100…): yayın burada açılır (eski adı TELEGRAM_CHANNEL_ID)"),
        ("TELEGRAM_WEBHOOK_SECRET", False, "İsteğe bağlı sabit webhook secret'ı; boşsa Render Web Service otomatik üretir"),
        ("TELEGRAM_WEBHOOK_AUTO", False, "Render Web Service'te varsayılan 1: secret otomatik üretilir; 0 = polling'e dön"),
        ("RENDER_EXTERNAL_URL", False, "Render otomatik verir (webhook adresi buradan üretilir); render.yaml'de tanımlıdır"),
        ("BOT_PROFILE", False, "Dengeli / Hassas / Seçici"),
        ("TELEGRAM_TEST_KEY", False, "İsteğe bağlı: /test ucunu açar (telefondan Telegram testi)"),
        ("SUPABASE_STORE_PREFIX", False, "Varsayılan formation-bot: ; aynı tabloyu paylaşan 2. kopya için değiştirin"),
        ("BOT_INSTANCE_ID", False, "Varsayılan hostname:pid; salt okunur modda uzak çoklu örnek tespiti kapalıdır"),
        ("PUBLIC_COMMANDS_ENABLED", False, "Public GRUP komutları (varsayılan 1 = açık): yalnız grup YÖNETİCİLERİ okuma komutlarını çalıştırır"),
        ("PUBLIC_COMMAND_CHATS", False, "Boş = TELEGRAM_GROUP_ID; virgülle çok sohbet (-100…,@grup_adi)"),
        ("PUBLIC_COMMAND_EXTRA", False, "Public'te kapalı komutları aç (örn. tara). Boş = yalnız okuma listesi"),
        ("PUBLIC_COMMAND_ADMIN_CACHE_SN", False, "getChatMember sonucu önbelleği (varsayılan 300 sn; 0 = kapalı)"),
        ("TELEGRAM_GRAFIK", False, ("İsteğe bağlı: 'alarm' uygun DM/public alarmlarına kare ekler; "
                                     "'yok' otomatik kareleri kapatır, /grafik bağımsızdır")),
        ("TELEGRAM_GRAFIK_ADET", False, "DM için üst sınır 1-4 (varsayılan 4); public normal olayda en fazla 2, geçersizleşmede 1"),
        ("GRAFIK_MUM_MAKS", False, "İsteğe bağlı: kadraj tavanı — kaç mum çizilsin "
                                   "(varsayılan TF matrisi: 1s 80 · 2s 74 · 4s 68 · 1g 62)"),
        ("GRAFIK_OLAY_MAKS", False, "İsteğe bağlı: kareye çizilen onaylı BOS/CHoCH sayısı (varsayılan 6)"),
        ("NIGHTLY_CANDLE_REFRESH_HOUR", False, "Gece Supabase-kayıtsız mum temizliği saati (varsayılan 2 -> 02:00 TSİ)"),
        ("STABIL_GERI_ALIM_ALARM", False, "Ayrı 4S Stabil güçlü geri alım alarmları (varsayılan 1 = açık)"),
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

    # Şalter yorumu çalışan kodla ortaktır; kapalıyken grafik katmanı yüklenmez.
    grafik_anahtari = (degerler.get("TELEGRAM_GRAFIK") or "").strip().lower()
    if grafik_anahtari not in GRAFIK_ACIK_DEGERLER | GRAFIK_KAPALI_DEGERLER:
        satir(WARN, "TELEGRAM_GRAFIK değeri tanınmıyor",
              "Geriye uyumluluk için açık sayılır; belirsizliği önlemek üzere alarm veya yok kullanın.")
    if otomatik_grafik_acik(grafik_anahtari):
        try:
            import matplotlib  # noqa: F401
            import grafik  # noqa: F401
            satir(OK, "Otomatik alarm grafikleri açık",
                  "Uygun DM/public olaylarında kare üretilebilir; /grafik ayrıca çalışır.")
        except Exception as hata:  # noqa: BLE001
            satir(FAIL, "TELEGRAM_GRAFIK tanımlı ama grafik katmanı çalışmıyor",
                  f"{type(hata).__name__}: "
                  f"{_kisa(hata, 120, degerler.get('TELEGRAM_BOT_TOKEN', ''), degerler.get('TELEGRAM_CHAT_ID', ''))} — "
                  "`pip install -r requirements.txt` sonra botu yeniden başlatın.")
    else:
        satir(OK, "Otomatik alarm grafikleri kapalı", "/grafik komutu bu şalterden bağımsızdır.")
    # --- DM kimliği görsel kapısı (2026-10-22) -----------------------------
    # DM grafik yolu pozitif tamsayı sohbet ister; public grafik ve grup /grafik
    # ayrı hedef/yetki kapıları kullanır. Bu kontrol public teslimini kanıtlamaz.
    dm_hedef = (degerler.get("TELEGRAM_CHAT_ID") or "").strip()
    public_hedef = ((degerler.get("TELEGRAM_GROUP_ID") or "").strip()
                    or (env_degeri("TELEGRAM_CHANNEL_ID", dosya_env) or "").strip())
    if dm_hedef:
        try:
            dm_pozitif = int(dm_hedef) > 0
        except (TypeError, ValueError):
            dm_pozitif = False
        if dm_pozitif:
            satir(OK, "TELEGRAM_CHAT_ID pozitif tamsayı (DM görsel kimliği uygun)",
                  "Bu yalnız biçim kontrolüdür; Telegram izinlerini ve teslimi ayrıca doğrulayın.")
        else:
            satir(WARN, "TELEGRAM_CHAT_ID pozitif tamsayı değil",
                  "Metin gidebilir ama DM GÖRSELLER gönderilmez (DM kapısı pozitif "
                  "tamsayı ister); public yol ayrıdır. @userinfobot'un verdiği sayıyı kullanın.")
        if public_hedef and dm_hedef == public_hedef:
            satir(FAIL, "TELEGRAM_CHAT_ID ile public hedef AYNI",
                  "Aynı sohbet hem DM hem grup olamaz; görseller DM kapısından "
                  "reddedilir ve alarm iki kez düşer. Grup için TELEGRAM_GROUP_ID'yi "
                  "-100… kimliğiyle ayrı tanımlayın.")
    if not degerler.get("TELEGRAM_BOT_TOKEN") and not degerler.get("TELEGRAM_CHAT_ID"):
        seviye = FAIL if canli_mod else WARN
        satir(seviye, "Telegram kapalı olacak", "Token/chat_id yoksa bot çalışır ama hiç mesaj göndermez (log: 'notifier pasif').")
    if not degerler.get("SUPABASE_URL") and not degerler.get("SUPABASE_SERVICE_ROLE_KEY"):
        satir(WARN, "Supabase kapalı olacak",
              "Analiz yine çalışır; eski uzak kayıtlar okunamaz.")
    satir(WARN, "Yeni durum Supabase'e yedeklenmez",
          "Bot salt okunur çalışır; geçici DATA_DIR silinirse yeni önbellek, karne ve bildirim durumu kaybolabilir. "
          "Uzak çoklu örnek tespiti de kapalıdır.")
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
        satir(WARN, "SUPABASE_URL https:// ile başlamıyor",
              f"Girilen kaynak: {_guvenli_url_kaynagi(temiz)}")

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
        satir(FAIL, "Supabase'e ulaşılamadı",
              f"{type(exc).__name__}: {_kisa(exc, 180, anahtar, temiz)}")
        return

    if r.status_code == 200:
        satir(OK, f"Supabase bağlantısı OK ({tur})",
              f"{_guvenli_url_kaynagi(temiz)} · tablo: bot_store")
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
        satir(FAIL, f"Beklenmeyen yanıt (HTTP {r.status_code})",
              _kisa(r.text, 180, anahtar, temiz))
        return

    # Bot salt okunur modda; tanılama da Supabase'e test satırı yazmamalı.
    # Uzak heartbeat artık güncellenmez, dolayısıyla canlılık için /health kullanılır.
    if r.status_code == 200:
        satir(OK, "Supabase salt okunur", "Yazma testi atlandı; canlılık için Render /health kullanın.")


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
        satir(FAIL, "Telegram'a ulaşılamadı",
              f"{type(exc).__name__}: {_kisa(exc, 180, token, chat_id)}")
        return

    if r.status_code == 200:
        try:
            govde = r.json()
        except ValueError:
            govde = None
        sonuc = govde.get("result") if isinstance(govde, dict) else None
        if not (isinstance(govde, dict) and govde.get("ok") is True
                and isinstance(sonuc, dict) and sonuc.get("id")):
            satir(FAIL, "getMe yanıtı geçersiz", _kisa(r.text, 160, token, chat_id))
            return
        kullanici = sonuc.get("username", "?")
        satir(OK, f"Token geçerli (bot: @{kullanici})")
    elif r.status_code == 401:
        satir(FAIL, "Token reddedildi (HTTP 401)",
              "BotFather token'ının tamamını kopyalayın; sızdıysa /revoke ile yenileyin.")
        return
    else:
        satir(FAIL, f"getMe beklenmeyen yanıt (HTTP {r.status_code})",
              _kisa(r.text, 160, token, chat_id))
        return

    if not chat_id:
        satir(WARN, "chat_id yok", "Telegram'a gönderim için TELEGRAM_CHAT_ID şart (@userinfobot).")
        return
    satir(OK, "DM hedefi tanımlı: /formasyonlar · /durum · /tara · /grafik · /yardim",
          "getMe ve hedefin varlığı komut yolunun veya mesaj tesliminin çalıştığını kanıtlamaz; "
          "yetkili sohbetten komut deneyin. Aynı token'ı ikinci bir kopya da dinlerse "
          "Telegram 409 Conflict verebilir.")
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
        satir(FAIL, "Test mesajı gönderilemedi",
              f"{type(exc).__name__}: {_kisa(exc, 180, token, chat_id)}")
        return

    if r.status_code == 200:
        satir(OK, "Test mesajı gönderildi", "Telegram'ı açıp kontrol edin.")
    else:
        aciklama = _kisa(r.text, 200, token, chat_id)
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


def _direnc_dumanini_raporla(meta: dict, token: str = "", chat_id: str = "") -> None:
    """PNG varlığını direnç katmanının hazır/çizilmiş olmasıyla karıştırma."""
    cizgiler = meta.get("cizgiler")
    katman = cizgiler.get("stabil_direnc") if isinstance(cizgiler, dict) else None
    if not isinstance(katman, dict):
        satir(WARN, "Stabil direnç durumu raporlanmadı",
              "PNG üretilmesi katmanın hazır veya çizilmiş olduğunu kanıtlamaz.")
    elif katman.get("hazir") is not True:
        durum = _kisa(katman.get("durum") or "bilinmiyor", 100, token, chat_id)
        neden = _kisa(katman.get("neden") or "belirtilmemiş", 100, token, chat_id)
        satir(WARN, "Stabil direnç bu karede hazır değil",
              f"durum: {durum} · neden: {neden}; kaynak/kadraj ve sade görünümü kontrol edin.")
    elif katman.get("cizildi") is not True:
        satir(WARN, "Stabil direnç hazır ama bu karede çizilmedi",
              "Seviye kadraj dışında veya gösterim kısıtlı olabilir; başka örneği de kontrol edin.")
    else:
        satir(OK, "Stabil direnç bu karede çizildi",
              "Bu tek örnek diğer semboller, canlı teslim veya veri tazeliğini kanıtlamaz.")


def kontrol_grafik(token: str, chat_id: str, mesaj_gonder: bool, *,
                   hisse: str = "AKBNK", tf: str = "4h") -> None:
    """Grafik katmanının canlı dumanı (G4): kare üret, isteğe bağlı gönder.

    Neden `deploy_check` içinde: alarm kareleri `TELEGRAM_GRAFIK=alarm` ile açılıyor
    ve tek hata kaynağı (matplotlib yok / önbellek boş / 413 boyut / yanlış chat)
    log'da kayboluyor. Bu kontrol hepsini tek bakışta ayırıyor. Çizim **yalnız
    önbellekten** veri okur — canlı çekme yapmaz (§4), bu yüzden ilk tarama
    öncesi „veri yok" normaldir (UYARI, hata değil).
    """
    bolum("2c) GRAFİK KARESİ DUMANI")
    try:
        import grafik  # noqa: F401
        import matplotlib  # noqa: F401
        satir(OK, f"Grafik katmanı import edildi (matplotlib {matplotlib.__version__})")
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "Grafik katmanı yüklenemedi",
              f"{type(exc).__name__}: {_kisa(exc, 160, token, chat_id)} · "
              "`pip install -r requirements.txt` (matplotlib 3.11.x) sonra yeniden başlat.")
        return
    if not mesaj_gonder and not otomatik_grafik_acik(os.environ.get("TELEGRAM_GRAFIK")):
        satir(OK, "Otomatik alarm grafikleri kapalı", "/grafik komutu yine çalışır. "
              "Fotoğraf göndermeyi denemek için: --grafik-test --send-test-message")
    try:
        import grafik_uret

        sonuc = grafik_uret.kare_uret(hisse, tf, zone=True)
    except SystemExit as exc:               # `_cerceve_yukle` uyumluluğu
        satir(WARN, "Kare çizilmedi", f"{_kisa(exc, 160, token, chat_id)} · "
              "ilk tarama öncesi önbellek boş olabilir (normal).")
        return
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, "Kare üretimi çöktü", f"{type(exc).__name__}: {_kisa(exc, 160, token, chat_id)}")
        return
    if not sonuc.get("yol"):
        satir(WARN, "Kare çizilmedi",
              " · ".join((sonuc.get("meta") or {}).get("uyarilar") or [])
              or sonuc.get("hata") or "neden bilinmiyor")
        return
    meta = sonuc.get("meta") or {}
    kb = float(meta.get("png_kb") or 0)
    satir(OK, f"Kare üretildi: {hisse} {tf} · {meta.get('mum_sayisi')} mum · {kb} KB · "
              f"{meta.get('sure_ms')} ms · kaynak: {sonuc.get('kaynak')}",
          "Boyut tavanı 500 KB (§6.3); eksik katman varsa kartta da yoktur.")
    eksik = list(meta.get("eksik_katmanlar") or [])
    if eksik:
        satir(WARN, "Karede eksik katman var", " · ".join(str(x) for x in eksik))
    _direnc_dumanini_raporla(meta, token, chat_id)
    if kb > 500:
        satir(FAIL, "Kare Telegram boyut riskinde", f"{kb} KB > 500 KB — kadrajı küçült "
              "(GRAFIK_MUM_MAKS) veya bölge/şerit katmanlarını kapat.")
    if not mesaj_gonder:
        satir(OK, "Fotoğraf gönderilmedi", "Denemek için: --grafik-test --send-test-message")
        return
    if not (token and chat_id):
        satir(FAIL, "chat_id/token yok", "sendPhoto denenemedi.")
        return
    from transport.telegram import foto_gonder

    ok, aciklama = foto_gonder(sonuc["yol"], chat_id=chat_id, token=token,
                               caption=f"{hisse} · {tf} · kurulum dumanı")
    try:
        os.remove(sonuc["yol"])
    except OSError:
        pass
    if ok:
        satir(OK, "sendPhoto kabul edildi", "Telegram medya akışı çalışıyor (caption + foto).")
    else:
        satir(FAIL, "sendPhoto reddedildi", _kisa(aciklama, 160, token, chat_id))


def kontrol_telegram_yol(token: str, webhook_secret_tanimli: bool, *,
                         render_service: bool = False, webhook_auto: bool = False) -> None:
    """Komutların gerçekten hangi yoldan geldiğini Telegram tarafından doğrular.

    Telegram `getWebhookInfo` webhook kaydını ve teslim hatalarını gösterir.
    Render auto-webhook modunda secret her açılışta bellekte üretildiğinden bu
    makinedeki `.env` dosyasında bulunmayabilir; kesin çalışma modu `/health`
    içinden ayrıca okunur. Polling yerelde uygundur ama uyuyan Render Free
    Web Service Telegram'ın getUpdates bağlantısıyla uyandırılamaz.
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

    if url and not webhook_secret_tanimli and not (render_service and webhook_auto):
        satir(FAIL, "Webhook kayıtlı ama yapılandırılmış secret yok",
              "Bu dağıtım webhook modunda değilse getUpdates 409 Conflict alır ve komutlar "
              "çalışmaz. Secret'ı ekleyin veya mevcut kaydı temizleyin; canlı mod için `/health` → komut.mod'u doğrulayın. "
              f"Kayıtlı adres: {_webhook_adres_gizle(url)}")
    elif url and not webhook_secret_tanimli:
        satir(WARN, f"Webhook kayıtlı: {_webhook_adres_gizle(url)}",
              "Secret bu makinede görünmüyor; Render otomatik üretmiş olabilir. Gerçek işlem modunu "
              "/health → komut.mod ve komut.dinleyici_canli alanlarından doğrulayın.")
    elif url:
        satir(OK, f"Webhook kayıtlı: {_webhook_adres_gizle(url)}",
              "Komutlar Telegram → /webhook üzerinden gelir (sunucu ayakta olmalı).")
    elif webhook_secret_tanimli:
        satir(WARN, "Webhook bekleniyor ama Telegram'da kayıtlı değil",
              "Bot açılışta setWebhook yapamamış (RENDER_EXTERNAL_URL/HTTPS?). Komutlar "
              "getUpdates yoklamasına düşebilir; canlı `/health` → komut.mod ve logları kontrol edin.")
    elif render_service and webhook_auto:
        satir(WARN, "Render otomatik webhook bekleniyor ama kayıtlı değil",
              "TELEGRAM_BOT_TOKEN, PORT ve RENDER_EXTERNAL_URL ile yeni sürümde webhook otomatik açılır. "
              "Eski commit çalışıyor olabilir veya setWebhook başarısızdır; Render logları ve `/health` → komut.mod'u kontrol edin.")
    elif render_service:
        satir(WARN, "Render'da komutlar polling (getUpdates) modunda",
              "TELEGRAM_WEBHOOK_AUTO=0 ve secret yok. Render Free uyursa polling servisi uyandıramaz; "
              "auto-webhook'u açın veya sürekli çalışan bir worker kullanın.")
    else:
        satir(OK, "Webhook yok; komutlar getUpdates yoklamasıyla gelir",
              "Yerel/systemd kullanımında beklenen mod. 15 dakikadan eski komutlar açılışta çalıştırılmaz.")

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


def kontrol_public_hedef(token: str, grup_id: str, chat_id: str = "",
                        public_komut_acik: bool = False) -> bool:
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
              "Grup/kanal yayını kapalı: yalnız DM çalışır. Hedefi tanımlayın ve botun üyeliğini kontrol edin.")
        return False
    from telegram_commands import telegram_sohbet_kimligi
    grup_id = telegram_sohbet_kimligi(grup_id)
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
        satir(OK, "Bot hedefte YÖNETİCİ", "Üyelik okundu; yayın izinleri ayrıca kontrol edilir.")
        if tip == "channel":
            if durum == "creator" or uye.get("can_post_messages"):
                satir(OK, "Kanal izni var: Mesaj gönderme", "Yayın açık.")
                ready = True
            else:
                satir(FAIL, "Kanal izni KAPALI: Mesaj gönderme",
                      "Kanal → Yöneticiler → bot → 'Mesaj gönderme' açık olmalı; yoksa gönderim 403 döner.")
        elif tip in ("group", "supergroup"):
            satir(OK, "Grup: mesaj gönderme serbest", "Yönetici bot grup ayarlarından etkilenmez.")
            ready = True
        else:
            satir(WARN, "Sohbet tipi bilinmiyor", "Yayın izni doğrulanamadı.")
    elif tip in ("group", "supergroup") and durum in ("member", "restricted"):
        if durum == "restricted" and not uye.get("is_member", True):
            satir(FAIL, "Bot hedefte YOK (restricted)", "Botu gruba ekleyin.")
        else:
            izin = uye if durum == "restricted" else sohbet.get("permissions") or {}
            metin = izin.get("can_send_messages")
            fotograf = izin.get("can_send_photos")
            if metin is True and fotograf is True:
                satir(OK, "Grup metin ve fotoğraf izni var", "Komut yönetici doğrulaması için bot yöneticiliği önerilir.")
                ready = True
            elif metin is False or fotograf is False:
                satir(FAIL, "Grup metin/fotoğraf izni kısıtlı", f"metin={metin}, fotoğraf={fotograf}")
            else:
                satir(WARN, "Grup metin/fotoğraf izni doğrulanamadı", f"metin={metin}, fotoğraf={fotograf}")
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
        # 2026-10-28: public komut yolu açıksa komutlar artık çalışır.
        if public_komut_acik:
            satir(OK, "DM chat_id yok; public komut yolu açık",
                  "Grup YÖNETİCİLERİ okuma komutlarını çalıştırabilir. Kendi DM'inizden "
                  "komut istiyorsanız TELEGRAM_CHAT_ID ekleyin.")
        else:
            satir(WARN, "DM chat_id yok: komutlar kapalı",
                  "Public yayın sürer ama /panel,/durum çalışmaz. Komutlar için "
                  "TELEGRAM_CHAT_ID ekleyin ya da PUBLIC_COMMANDS_ENABLED=1 bırakın.")
    return ready


def _public_komut_acik(degerler: dict) -> bool:
    """Public grup komut yolu açık mı? (env + grup hedefi birlikte gerekli).

    Kural `config.py` ile AYNI: PUBLIC_COMMANDS_ENABLED kapalı değilse ve bir grup
    hedefi (PUBLIC_COMMAND_CHATS ya da TELEGRAM_GROUP_ID) varsa açıktır. Kanal
    hedefi tek başına yetmez: `channel_post` gönderilerinde yöneticilik
    doğrulanamaz, kanal komut kabul etmez.
    """
    ham = str(degerler.get("PUBLIC_COMMANDS_ENABLED", "1") or "1").strip().lower()
    if ham in ("0", "false", "no", "off", "hayir"):
        return False
    acik = (degerler.get("PUBLIC_COMMAND_CHATS") or "").strip()
    if acik:
        return True
    return bool((degerler.get("TELEGRAM_GROUP_ID") or "").strip())


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
    """Canlı sürümü yerel HEAD ile karşılaştır; bilinmeyen de görünür olsun."""
    yerel = _yerel_commit()
    if not canli_commit or not yerel:
        satir(WARN, "Canlı sürüm doğrulanamadı",
              "/health commit alanı veya yerel Git HEAD yok; Render Deploys üzerinden kontrol edin.")
        return
    if canli_commit == yerel[:7] or yerel.startswith(canli_commit) or canli_commit.startswith(yerel):
        satir(OK, f"Canlı sürüm yerelle aynı ({canli_commit})")
        return
    satir(WARN, f"Canlı sürüm yerelden FARKLI (canlı {canli_commit} ≠ yerel {yerel})",
          "Render yeni commit'i henüz deploy etmemiş olabilir: Dashboard → servis → "
          "Events'te 'Deploy succeeded' var mı? Yoksa Manual Deploy → Deploy latest commit. "
          "Auto-Deploy kapalıysa her merge'de elle deploy gerekir.")


def _health_komut_sayisi(komut: dict, anahtar: str) -> int:
    try:
        return max(0, int(komut.get(anahtar) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def kontrol_render_komut_durumu(health: dict) -> None:
    """Live `/health` komut alanını değerlendir; env varlığını çalışma kanıtı sayma."""
    komut = health.get("komut") if isinstance(health, dict) else None
    if not isinstance(komut, dict):
        satir(WARN, "Canlı komut durumu raporlanmıyor",
              "Deploy eski olabilir. Güncel sürümde /health → komut.mod ve komut.dinleyici_canli alanlarını gösterir.")
        return

    mod = str(komut.get("mod") or "").strip().lower()
    canli = komut.get("dinleyici_canli")
    if mod == "webhook":
        if canli is True:
            satir(OK, "Telegram komut yolu aktif (webhook)",
                  "Webhook processor ve HTTP sunucusu hazır; teslim hatası/pending sayısını da kontrol edin.")
        elif canli is False:
            satir(FAIL, "Webhook komut yolu hazır değil",
                  "/health → komut.dinleyici_canli=false. Render loglarında setWebhook ve başlangıç hatalarını kontrol edin.")
        else:
            satir(WARN, "Webhook modu bildiriliyor ama liveness bilinmiyor",
                  "Deploy eski olabilir; güncel sürümde komut.dinleyici_canli alanı beklenir.")
    elif mod in {"yoklama", "polling"}:
        if canli is False or (canli is None and komut.get("calisiyor") is False):
            satir(FAIL, "Telegram polling dinleyicisi durmuş",
                  "Loglarda HTTP 401 token hatası veya HTTP 409 (aynı token'ı dinleyen ikinci süreç) arayın.")
        elif canli is True or komut.get("calisiyor") is True:
            satir(WARN, "Telegram komut yolu polling modunda",
                  "Dinleyici çalışıyor; Render Free servisi uyursa getUpdates servisi uyandıramaz. Webhook modunu kullanın.")
        else:
            satir(WARN, "Polling modu var ama dinleyici durumu bilinmiyor",
                  "Render Logs'ta Telegram komut dinleyicisinin başlangıç/409 kayıtlarını kontrol edin.")
    elif mod == "kapali":
        satir(FAIL, "Telegram komut katmanı kapalı",
              "TELEGRAM_BOT_TOKEN ile TELEGRAM_CHAT_ID'yi kontrol edin; public-only kullanımda grup komut ayarları da gerekir.")
    else:
        satir(WARN, "Komut modu bilinmiyor",
              "Bot henüz komutları kurmamış olabilir veya çalışan deploy eski olabilir.")

    yetkisiz = _health_komut_sayisi(komut, "yetkisiz_sohbet")
    if yetkisiz:
        son = str(komut.get("son_yetkisiz_sohbet") or "")
        satir(WARN, f"Yetkisiz sohbetten {yetkisiz} komut geldi",
              f"TELEGRAM_CHAT_ID gelen DM ile eşleşmiyor olabilir; görülen kimlik maskeli: {son or 'yok'}. @userinfobot'taki sayıyı kontrol edin.")
    bayat = _health_komut_sayisi(komut, "bayat_atlanan")
    if bayat:
        satir(WARN, f"{bayat} eski komut güvenlik nedeniyle çalıştırılmadı",
              "Komutu yeniden gönderin; /health → heartbeat ve Render uyku/uyanma süresini kontrol edin.")
    hatali = _health_komut_sayisi(komut, "isleyici_hatasi")
    if hatali:
        satir(WARN, f"Komut işleyicisinde {hatali} hata kaydı var",
              "Render Logs'ta ilgili /komut işleyicisi traceback'ini inceleyin.")


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
    kaynak = _guvenli_url_kaynagi(hedef)
    try:
        r = requests.get(hedef, timeout=120)  # uyuyan Free servis ~1 dk'da uyanır
    except Exception as exc:  # noqa: BLE001
        satir(FAIL, f"{kaynak} yanıt vermedi",
              f"{type(exc).__name__}: {_kisa(exc, 180, test_key, url, hedef)}")
        return

    if r.status_code == 200:
        try:
            govde = r.json()
        except ValueError:
            govde = {}
        if isinstance(govde, dict) and govde.get("status") == "ok":
            canli_commit = str(govde.get("commit") or "")
            detay = kaynak + (f" · canlı sürüm: {canli_commit}" if canli_commit else "")
            satir(OK, f"/health ayakta ({govde.get('service', '?')})", detay)
            _commit_karsilastir(canli_commit)
            if govde.get("startup_complete") is True:
                satir(OK, "Başlangıç tamamlandı", "Bu, Telegram veya veri/Supabase sağlığının garantisi değildir.")
            elif govde.get("startup_complete") is False:
                satir(WARN, "Bot henüz hazır değil veya kapanıyor", "/ready 503 döner; Render loglarını izleyin.")
            else:
                satir(WARN, "Başlangıç durumu bilinmiyor", "Eski sürüm veya sağlık sağlayıcısı yok/hatalı olabilir.")
            if govde.get("heartbeat_stale") is True:
                satir(WARN, "Heartbeat bayat", "Tarama ve veri durumunu inceleyin.")
            elif govde.get("heartbeat_stale") is None:
                satir(WARN, "Heartbeat durumu bilinmiyor", "Henüz ilk tarama yapılmamış olabilir; /health 200 çalışırlık kanıtı değildir.")
            if govde.get("scan_stale") is True:
                yas = _health_komut_sayisi(govde, "scan_age_s")
                esik = _health_komut_sayisi(govde, "scan_stale_after_s")
                satir(WARN, f"Aktif analiz uzadı ({yas // 60} dk)",
                      f"/health scan_age_s={yas}, eşik={esik}s. Render Logs'ta ilerleyen sembolü, fetch timeout/retry ve provider gecikmesini inceleyin.")
            elif govde.get("tarama_suruyor") is True and govde.get("scan_stale") is None:
                satir(WARN, "Aktif analiz süresi ölçülmüyor",
                      "Deploy eski olabilir; güncel /health scan_age_s ve scan_stale alanlarını döndürür.")
            kontrol_render_komut_durumu(govde)
        else:
            satir(FAIL, "200 döndü ama gövde beklenen JSON değil",
                  _kisa(govde, 160, test_key, url, hedef))
    elif r.status_code in (502, 503, 504):
        satir(WARN, f"Servis şu an uyanıyor/başlamadı (HTTP {r.status_code})",
              "30-60 sn sonra tekrar deneyin. Render → Logs'ta 'Render health endpoint ... başladı' satırını arayın.")
    elif r.status_code == 404:
        satir(FAIL, "HTTP 404 — yol yanlış ya da servis deploy edilmemiş",
              "Health Check Path '/health' olmalı; adres https://<servis>.onrender.com biçiminde olmalı.")
    else:
        satir(FAIL, f"Beklenmeyen yanıt (HTTP {r.status_code})",
              _kisa(r.text, 180, test_key, url, hedef))

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
        satir(FAIL, "/test çağrısı başarısız",
              f"{type(exc).__name__}: {_kisa(exc, 180, test_key, url, hedef)}")
        return

    test_govde = None
    if r.status_code == 200:
        try:
            test_govde = r.json()
        except ValueError:
            pass
    if isinstance(test_govde, dict) and test_govde.get("ok") is True:
        satir(OK, "/test Telegram mesajı gönderdi", "Telegram'da 'test mesaji' görünmeli.")
    elif r.status_code == 404:
        satir(FAIL, "/test kapalı (HTTP 404)",
              "Render → Environment → TELEGRAM_TEST_KEY ekleyin (secret), servis yeniden deploy edilsin.")
    elif r.status_code == 403:
        satir(FAIL, "Anahtar yanlış (HTTP 403)", "Render'daki TELEGRAM_TEST_KEY ile --test-key aynı olmalı.")
    elif r.status_code == 503:
        satir(WARN, "Bot henüz başlamadı (HTTP 503)", "Servis uyanıyor; 30 sn sonra tekrar deneyin.")
    else:
        satir(FAIL, f"/test beklenmeyen yanıt (HTTP {r.status_code})",
              _kisa(r.text, 200, test_key, url, hedef))


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
    ap.add_argument("--grafik-test", action="store_true",
                    help="Kare üretimini dene (önbellekten çiz; --send-test-message ile "
                         "fotoğrafı gerçekten gönder)")
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
        render_service = bool(args.url or degerler.get("RENDER_EXTERNAL_URL"))
        kontrol_telegram_yol(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            bool(degerler.get("TELEGRAM_WEBHOOK_SECRET", "")),
            render_service=render_service,
            webhook_auto=_env_bool(degerler.get("TELEGRAM_WEBHOOK_AUTO"), varsayilan=True),
        )
        public_hazir = kontrol_public_hedef(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            degerler.get("TELEGRAM_GROUP_ID", "") or degerler.get("TELEGRAM_CHANNEL_ID", ""),
            degerler.get("TELEGRAM_CHAT_ID", ""),
            public_komut_acik=_public_komut_acik(degerler),
        )
        kontrol_render(args.url or "", args.test_key or degerler.get("TELEGRAM_TEST_KEY", ""))

    if args.grafik_test:
        # Çizim çevrimdışı çalışır (yalnız önbellek okunur); fotoğraf gönderimi
        # `--send-test-message` ile ağa çıkar — o yüzden ağ dalının dışında.
        kontrol_grafik(degerler.get("TELEGRAM_BOT_TOKEN", ""),
                       degerler.get("TELEGRAM_CHAT_ID", ""),
                       args.send_test_message and not args.skip_network)

    bolum("ÖZET")
    # Değişkenlerin varlığı, kimlik/erişim veya teslimin başarıyla sınandığını
    # göstermez. Ağ kontrollerinin ayrıntısı yukarıdaki satırlarda kalır.
    telegram_tanimli = bool(degerler.get("TELEGRAM_BOT_TOKEN") and degerler.get("TELEGRAM_CHAT_ID"))
    supabase_tanimli = bool(degerler.get("SUPABASE_URL") and degerler.get("SUPABASE_SERVICE_ROLE_KEY"))
    kanal_hedefi = (degerler.get("TELEGRAM_GROUP_ID", "") or degerler.get("TELEGRAM_CHANNEL_ID", ""))
    ozet_telegram = "TANIMLI" if telegram_tanimli else "EKSİK/YOK"
    ozet_supabase = "TANIMLI (salt okunur)" if supabase_tanimli else "EKSİK/YOK"
    ozet_kanal = "YOK"
    if kanal_hedefi:
        if args.skip_network:
            ozet_kanal = "TANIMLI (DOĞRULANMADI)"
        else:
            ozet_kanal = "İZİN DOĞRULANDI" if public_hazir else "HEDEF VAR, İZİN DOĞRULANAMADI"
    print(f"ÖZET: Telegram {ozet_telegram} · Kanal {ozet_kanal} · Supabase {ozet_supabase}")
    print("TANIMLI yalnızca ayarın varlığıdır; erişim ve teslim için yukarıdaki kontrolleri okuyun.")
    print(f"✅ {_sayac[OK]} tamam   ⚠️  {_sayac[WARN]} uyarı   ❌ {_sayac[FAIL]} hata")
    if _sayac[FAIL] == 0 and _sayac[WARN] == 0:
        print("Her şey yerinde: Render tarafı hazır.")
    elif _sayac[FAIL] == 0:
        print("Kritik hata kaydedilmedi; uyarı ve atlanan kontroller servislerin hazır olduğunu kanıtlamaz.")
        print("UYARI satırlarını yukarıdan aşağı okuyun, docs/kurulum/RENDER_DEPLOY.md §1-5 karşılığını anlatır.")
    else:
        print("HATA satırlarını sırayla düzeltin; her biri için öneri satır altında yazıyor.")
    print("Ayrıntılı rehber: docs/kurulum/RENDER_DEPLOY.md")
    return 1 if _sayac[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
