# Deploy Kontrolü — Alarm Politikası Sürümü (2026-11-21)

**Kapsam:** `arena/80891cd0-formation-bot` (P6 politikası + cooldown düzeltmesi)
**Sonuç:** Kod tarafı **HAZIR** · Operatör tarafında **3 karar** bekliyor (§5)

---

## 1. Bu sürümde ne değişti

| Değişiklik | Dosya | Risk |
|---|---|---|
| P6 politikası varsayılan | `config.py`, `bot/domain_alarm_service.py` | Orta — alarm sayısını ~2,7× düşürür (bilinçli) |
| Cooldown gerçekten çalışıyor | `bot/domain_alarm_service.py` | Düşük — daha az kart, replay ile birebir |
| State atomik yazımı | `bot/domain_alarm_service.py` | Düşük — yarım JSON riski kapandı |
| Parite kontrol aracı | `scripts/politika_parite_kontrol.py` | Yok — yalnız okur |

Yeni env anahtarı **tek**: `YENI_DOMAIN_ALARM_POLITIKA` (P0 / P6 / P4).
Verilmezse kodda varsayılan **P6**. Tanınmayan değer fail-open ile P0'a düşer.

## 2. Doğrulanan kapılar

| Kapı | Komut | Sonuç |
|---|---|---|
| Tam test paketi | `pytest -q` | **4.756 passed / 43 skipped** |
| Statik | `ruff check .` | temiz |
| Bağımlılık uyumu | `pip check` | temiz |
| Render parity CI | GitHub Actions | **success** (20 dk, Python 3.12) |
| Bağlam paritesi | `python -m scripts.politika_parite_kontrol --seri 300` | **300/300 seri, 0 fark** |
| Uçtan uca kart sayısı | replay tetikleri → gerçek `dispatch` | P6 **902** · P4 **499** · P0 2.531 |
| Health/ready | `BOT_HEALTH_SMOKE_ONLY=1 python main.py` | `/health` 200, `/ready` **503** (doğru) |
| Kurulum doktoru | `python deploy_check.py --skip-network` | 46 tamam · 7 uyarı · **0 hata** |

Uyarıların hepsi bu ortamda token/anahtar olmamasından; deploy ortamında
Dashboard'daki gerçek değerlerle tekrar koşulmalı.

## 3. Zincir kontrolü (kod tarafı)

| Halka | Durum | Not |
|---|---|---|
| `.python-version` → 3.12 | ✅ | Render 3.14 varsayılanı pandas tekerleğini patlatıyordu; sabitlendi |
| `install_deploy_dependencies.sh` | ✅ | pip/setuptools pinli, `pip check` build'i kırıyor |
| `requirements-deploy.txt` | ✅ | `requirements.txt` **kullanılmamalı** (tarihsel hash'li) |
| `buildCommand` | ✅ | `bash scripts/install_deploy_dependencies.sh` |
| `startCommand` | ✅ | `python main.py` |
| `healthCheckPath` | ✅ | `/health`, sorgu dizesiyle de 200 (keepalive uyumlu) |
| Webhook kapalıyken 404 | ✅ | `/test`, `/webhook/*` — CI'da kilitli |
| SIGTERM dayanıklılığı | ⚠️ | `maxShutdownDelaySeconds: 120` **yalnız Blueprint'te**; Dashboard'da elle doğrulanmalı |
| CI on push (`arena/**`) | ✅ | bu dal CI'da yeşil |

## 4. Bu sürüme özgü riskler

1. **Deploy sonrası ilk alarmlar.** Eski state dosyası `sembol|TF|bar_open`
   anahtarlarıyla dolu. Yeni kod `sembol|TF` arar, bulamaz → o sembol/TF için
   **ilk alarm hemen geçer** (cooldown henüz yok). Deploy saati seans içindeyse
   kısa bir "ilk kart" dalgası normaldir; 6 bar sonra oturur.
2. **DATA_DIR=/tmp kalıcılığı.** Render'da her deploy/restart state'i sıfırlar →
   cooldown ve karne defteri kaybolur, ilk taramada mükerrer alarm riski.
   Çözüm ya kalıcı disk ya `SUPABASE_DELIVERY_WRITES=1`; **ikisi de şu an kapalı.**
3. **İki bot örneği.** `render.yaml` Blueprint'i Dashboard'daki mevcut servise
   uygulanırsa ikinci servis açılır ve iki bot aynı Telegram hedefine yazar.
   Dosyanın başında bu uyarı var; uygulamamalı.
4. **Politika geri alınabilir ama sessizce değil.** `P0` yazınca eski davranış
   döner; `P6` altında elenen her aday `DEBUG` seviyesinde gerekçesiyle loglanır.
   Üretimde `LOG_LEVEL=DEBUG` açmadan elenen adaylar görünmez.

## 5. Operatör kararları (deploy'dan önce)

### 5.1 Kalıcılık

Render Dashboard → Settings → Disks ile `DATA_DIR` ile aynı yola kalıcı disk
bağlanmalı **veya** risk bilinçli kabul edilmeli. Aksi halde:

- her deploy'da cooldown sıfırlanır → ilk tarama mükerrer alarm
- karne defteri (`karne_defteri.json`) sıfırlanır → geçmiş kaybolur

### 5.2 Env doğrulaması

Dashboard'da şunlar **gerçek değerlerle** olmalı:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` veya `TELEGRAM_GROUP_ID`,
`TZ=Europe/Istanbul`, `TELEGRAM_GRAFIK`, `STOCK_UNIVERSE` (boşsa BIST 50).
Politika için **hiçbir şey eklemek zorunlu değil** (kodda varsayılan P6).
Görünür olsun istenirse `YENI_DOMAIN_ALARM_POLITIKA=P6` elle eklenir.

### 5.3 Deploy zamanlaması

Seans dışında deploy etmek §4.1'deki "ilk kart dalgası"nı görünmez kılar.
Öneri: **18:30 sonrası veya hafta sonu**.

## 6. Deploy sonrası ilk 3 seans — neye bakılır

1. `🆕 YENİ` kart sayısı ≈ **41/seans** (P0'da 115 idi). Belirgin yüksekse
   cooldown devrede değil demektir → state dosyası yazılabiliyor mu bakılır.
2. Aynı sembol/TF için 6 bar içinde ikinci kart **gelmemeli**.
3. `/health` içindeki `bildirim` bloğunda `teslim_kuyrugu` ve
   `son_basarili_gonderim` alanları dolu mu.
4. Logda `politika P6 ile elendi` satırları (DEBUG) — "sinyal mi kaçtı, gürültü
   mü elendi" sorusu buradan cevaplanır.
5. Restart sonrası state korunuyor mu: `DATA_DIR` içindeki
   `yeni_domain_alarm_state.json` yeniden başlatmadan sonra da duruyor mu.

## 7. Geri alma

```
YENI_DOMAIN_ALARM_POLITIKA=P0    # eski kart davranışı (cooldown düzeltmesi kalır)
```

Cooldown düzeltmesini de geri almak gerekirse `dedup_key`/`bar_key` değişikliği
tek commit'te (`769a338`) — `git revert` ile ayrılabilir.

**DİKKAT:** P0'a dönmek cooldown'u geri almaz; artık P0 de 6 bar sessizlikle
çalışır (115 kart/seans, önceki 350 değil). Bu bilinçli: eski davranış hatalıydı.

---

# EK — Baştan sona denetim (2026-11-21, ikinci tur)

Bu bölüm deploy zincirini uçtan uca yeniden taradı; §1–§7'yi **tamamlar**.

## E1. Depo durumu: `main` ile ortak ata YOK

| | main | bu dal |
|---|---|---|
| Son commit | 2026-11-09 | 2026-11-21 |
| Dosya | 1.326 | 1.927 |
| `bot/domain_alarm_service.py` | cooldown **hatalı** (bar anahtarlı) | düzeltilmiş |

`git merge-base` **boş** döner — iki geçmiş birleşmiyor. Pratikte:
`main`'de olup bu dalda olmayan **0 kod dosyası** var; bu dal `main`'in tüm
kodunu + 12 günlük birikimi içeriyor. Yani bu dal **daha yeni ve daha doğru**.

**Karar gerekiyor — deploy kaynağı hangisi?**
`render.yaml` bir branch belirtmiyor; Render Dashboard'daki bağlı branch neyse
o deploy edilir. Bu dal merge edilmezse:

- canlı bugünkü (main) kodu çalıştırmaya devam eder → **P6 yok, cooldown hâlâ hatalı**
- bu dalda yapılan düzeltmeler hiç canlıya çıkmaz

## E2. `main`'de kullanılmayan bir CI dosyası var

`.github/workflows/keepalive.yml` (Render uyku engelleyici, 5 dk cron):

- `on.schedule` **yalnız varsayılan branch'te** (main) çalışır → bu dalda merge
  edilene kadar **çalışmıyor**
- Render Free 15 dk inbound istek gelmezse uyur; keepalive olmadan servis
  uykuya dalar ve Telegram komutları ~1 dk gecikir
- Kurulum: repo secret/variable `RENDER_HEALTH_URL = https://<servis>.onrender.com/health`
- **Bilinen tuzak:** public repoda 60 gün aktivite olmazsa GitHub zamanlanmış
  iş akışlarını sessizce kapatır

## E3. Env: sembolik olarak sağlam

| Kontrol | Sonuç |
|---|---|
| Kodda okunan env | 65 (aslında daha fazlası `_env_int`/`_env_bayrak` ile) |
| `.env.example` | 101 anahtar — süperset, ölü anahtar yok |
| `render.yaml` | 35 anahtar, hepsi `.env.example` içinde |
| Kodda var / `.env.example`'da yok | 14 — hepsi **araştırma/teşhis** (aşağıda) |
| `.env` git'te | ✅ yok (`.gitignore:8`) |
| `.env` yükleme | `load_dotenv()` = `override=False` → **OS/Render env öncelikli**, doğru |

Belgelenmemiş 14 anahtarın hiçbiri canlı akışı etkilemez:
`BOT_HEALTH_SMOKE_ONLY` (CI), `RENDER`/`RENDER_GIT_COMMIT`/`RENDER_GIT_BRANCH`
(Render enjekte eder), `GRAFIK_SAG_BOSLUK`, `GRAFIK_YAZI`, `TELEGRAM_KART_YORUM`,
`FB_ARSIV_KOKU`, `LIMIT`, `GORSEL_*`, `FORMATION_API_POC_KEY`,
`FORMATION_BOT_ALLOW_LIVE_YAHOO_RESEARCH`, `FORMATION_BOT_EXPLORATORY_DATA_DIR`.

## E4. ⚠️ Env eksikse bot ÖLMÜYOR — "sessiz ölüm"

Ampirik (token/chat_id boş, Render'a benzer ortam):

```
/health   -> HTTP 200  status: "ok"
/ready    -> HTTP 503
bildirim  -> {"durum": "kapali", "mod": "kapali", "nedenler": ["Telegram teslim hedefi yok"]}
log       -> [WARNING] Telegram token env'de yok - notifier pasif (test modu)
```

`healthCheckPath: /health` olduğu için Render servisi **sağlıklı** sayar.
Sonuç: token yanlış/eksikse Render yeşil, bot ayakta, tarama çalışıyor ama
**tek bir mesaj gitmiyor**. Panel/uyarı yok.

**Deploy sonrası ilk kontrol (zorunlu):**
```
curl -s https://<servis>.onrender.com/health | grep -o '"durum": "[^"]*"'
```
`"durum": "acik"` değilse alarm yok demektir.

## E5. `deploy_check.py` — 0 hata, 7 uyarı

`46 tamam / 7 uyarı / 0 hata`. Uyarılar bu ortamda token/anahtar olmamasından
(temizlik kanıtı). **Deploy ortamında tekrar koşulmalı** — orada da uyarı
çıkarsa gerçek eksik var demektir.

## E6. Sağlık uçları

| Uç | Beklenen | Doğrulandı |
|---|---|---|
| `/health` | 200 + `status: ok` + `commit` | ✅ |
| `/health?ka=1` | 200 (keepalive uyumlu) | ✅ CI'da kilitli |
| `/ready` açılışta | 503 (`startup_complete: false`) | ✅ |
| `/test` anahtar yokken | 404 (kapalı) | ✅ CI'da kilitli |
| `/webhook/*` secret yokken | 404 (kapalı) | ✅ CI'da kilitli |

## E7. CI kapsaması

| Commit | CI |
|---|---|
| `bb80d14` (P6) | success |
| `769a338` (cooldown) | ayrı koşu yok |
| `58b86a0` (docs) | **success** — `769a338`'i ata olarak içeriyor |

Cooldown commit'i 23 dk sonraki docs commit'iyle birlikte koştu ve geçti;
tam paket yerelde de 4.756 passed.

## E8. Bu turda kapatılan iki bulgu

1. **State atomik yazımı** — `_save_state` doğrudan yazıyordu; SIGTERM/OOM
   anında yarım JSON → tüm cooldown kaybı → mükerrer alarm.
   `tmp` + `os.replace` yapıldı (`stabil_service` ile aynı desen).
2. **Cooldown semantiği** — `dedup_key` artık `sembol|TF`; ayrıntı karar
   belgesinde (§4b).

## E9. Sıralı deploy kontrol listesi

1. `YENI_DOMAIN_ALARM_POLITIKA` **eklemek zorunlu değil** (kodda P6). İstersen
   görünürlük için `P6` olarak ekle.
2. `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` **veya** `TELEGRAM_GROUP_ID`,
   `TZ=Europe/Istanbul` Dashboard'da gerçek değerlerle dolu mu?
3. Git repo secret: `RENDER_HEALTH_URL` (keepalive için)
4. Kalıcılık: `DATA_DIR` için disk **veya** riski kabul et (§5.1)
5. Render Dashboard'daki bağlı branch bu dal mı, `main` mi? (E1)
6. Deploy → `/health` içinde `"durum": "acik"` gör → ilk 3 seans §6'yı izle
