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
  2. Env: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / TELEGRAM_BOT_TOKEN /
     TELEGRAM_CHAT_ID tanımlı mı (değerleri ASLA yazdırmaz, sadece uzunluk).
  3. Supabase: tablo gerçekten var mı? (404 -> SQL çalıştırılmamış,
     401/403 -> anahtar yanlış, 200 -> hazır)
  4. Telegram: getMe ile token; istenirse gerçek test mesajı.
  5. Render: https://<servis>.onrender.com/health ayakta mı; /test ucu açık mı.

Çıkış kodu 0 = kritik hata yok, 1 = en az bir HATA var (uyarılar kodu bozmaz).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
        deger = deger.strip().strip('"').strip("'")
        veri[anahtar.strip()] = deger
    return veri


def env_degeri(anahtar: str, dosya_env: dict) -> str:
    return (os.environ.get(anahtar) or dosya_env.get(anahtar) or "").strip()


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


def kontrol_env(dosya_env: dict) -> dict:
    bolum("2) ORTAM DEĞİŞKENLERİ (Render → Environment)")

    beklenti = [
        ("SUPABASE_URL", True, "Supabase → Settings → API → Project URL (sonda /rest/v1 OLMADAN)"),
        ("SUPABASE_SERVICE_ROLE_KEY", True, "service_role JWT (eyJ...) veya yeni 'sb_secret_...' anahtarı"),
        ("TELEGRAM_BOT_TOKEN", True, "@BotFather → /newbot → 'Use this token'"),
        ("TELEGRAM_CHAT_ID", True, "@userinfobot'un verdiği Id (kendine mesaj için pozitif sayı)"),
        ("BOT_PROFILE", False, "Dengeli / Hassas / Seçici"),
        ("TELEGRAM_TEST_KEY", False, "İsteğe bağlı: /test ucunu açar (telefondan Telegram testi)"),
    ]

    degerler = {}
    for anahtar, zorunlu, aciklama in beklenti:
        deger = env_degeri(anahtar, dosya_env)
        degerler[anahtar] = deger
        if deger:
            satir(OK, f"{anahtar} tanımlı ({len(deger)} karakter)")
        elif zorunlu:
            satir(WARN, f"{anahtar} tanımlı değil", aciklama)
        else:
            satir(OK, f"{anahtar} tanımlı değil (opsiyonel)", aciklama)

    if not degerler.get("TELEGRAM_BOT_TOKEN") and not degerler.get("TELEGRAM_CHAT_ID"):
        satir(WARN, "Telegram kapalı olacak", "Token/chat_id yoksa bot çalışır ama hiç mesaj göndermez (log: 'notifier pasif').")
    if not degerler.get("SUPABASE_URL") and not degerler.get("SUPABASE_SERVICE_ROLE_KEY"):
        satir(WARN, "Supabase kapalı olacak",
              "Render diski kalıcı değil: restart/deploy sonrası yerel önbellek ve Telegram sayaçları sıfırlanır.")
    anahtar = degerler.get("SUPABASE_SERVICE_ROLE_KEY", "")
    rol = _jwt_rolu(anahtar)
    if anahtar.startswith("sb_publishable_"):
        satir(WARN, "SUPABASE_SERVICE_ROLE_KEY 'publishable' anahtar",
              "RLS açıkken bu anahtar 401/403 alır; service_role JWT veya 'sb_secret_...' kullanın.")
    elif rol == "anon":
        satir(WARN, "SUPABASE_SERVICE_ROLE_KEY 'anon' rolünde",
              "service_role JWT veya 'sb_secret_...' kullanın; anon anahtar tabloya yazamaz.")
    elif rol == "service_role":
        satir(OK, "Supabase anahtarı service_role rolünde")
    return degerler


def _jwt_rolu(anahtar: str) -> str:
    """JWT payload'ındaki 'role' alanını okur (imza doğrulaması yapmaz, sır yazmaz)."""
    if anahtar.count(".") != 2 or not anahtar.startswith("eyJ"):
        return ""
    try:
        import base64

        payload = anahtar.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        veri = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8", "replace"))
        return str(veri.get("role", ""))
    except Exception:  # noqa: BLE001 - çözülemeyen token sessizce geçilir
        return ""


def kontrol_supabase(url: str, anahtar: str) -> None:
    bolum("3) SUPABASE")
    if not url or not anahtar:
        satir(WARN, "Atlandı", "SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY birlikte gerekli.")
        return

    try:
        import requests
    except ImportError:
        satir(WARN, "Atlandı", "requests kurulu değil (pip install -r requirements.txt).")
        return

    temiz = url.strip().rstrip("/")
    if temiz.endswith("/rest/v1"):
        temiz = temiz[: -len("/rest/v1")]
        satir(WARN, "SUPABASE_URL sonunda /rest/v1 var",
              "Kod bunu temizliyor, ama doğrusu: https://<ref>.supabase.co")
    if not temiz.startswith("https://"):
        satir(WARN, "SUPABASE_URL https:// ile başlamıyor", f"Girilen: {temiz[:40]}")

    basliklar = {
        "apikey": anahtar,
        "Authorization": f"Bearer {anahtar}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(
            f"{temiz}/rest/v1/bot_store",
            headers=basliklar,
            params={"select": "store_key", "limit": 1},
            timeout=12,
        )
    except Exception as exc:  # noqa: BLE001 - kullanıcıya tek satır özet yeter
        satir(FAIL, "Supabase'e ulaşılamadı", f"{type(exc).__name__}: {_kisa(exc)}")
        return

    if r.status_code == 200:
        satir(OK, "Supabase bağlantısı OK", f"{temiz} · tablo: bot_store")
    elif r.status_code == 404:
        satir(FAIL, "Tablo yok (HTTP 404)",
              "Supabase → SQL Editor → New query → supabase_schema.sql içeriğini yapıştır → Run.")
    elif r.status_code in (401, 403):
        satir(FAIL, f"Anahtar reddedildi (HTTP {r.status_code})",
              "service_role yerine anon/publishable anahtar girilmiş ya da anahtar iptal edilmiş. "
              "Doğrusu: Settings → API → service_role (veya Secret key).")
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


def _health_hedefi(url: str) -> str:
    temiz = url.strip().rstrip("/")
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
        r = requests.get(hedef.rsplit("/health", 1)[0] + "/test", params={"k": test_key}, timeout=60)
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

    kontrol_repo()
    degerler = kontrol_env(dosya_env)

    if args.skip_network:
        bolum("AĞ KONTROLLERİ")
        satir(WARN, "--skip-network verildi", "Supabase/Telegram/Render kontrolleri atlandı.")
    else:
        kontrol_supabase(degerler.get("SUPABASE_URL", ""), degerler.get("SUPABASE_SERVICE_ROLE_KEY", ""))
        kontrol_telegram(
            degerler.get("TELEGRAM_BOT_TOKEN", ""),
            degerler.get("TELEGRAM_CHAT_ID", ""),
            args.send_test_message,
        )
        kontrol_render(args.url or "", args.test_key or degerler.get("TELEGRAM_TEST_KEY", ""))

    bolum("ÖZET")
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
