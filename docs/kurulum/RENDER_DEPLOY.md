# Render + Supabase + Telegram Dağıtım Rehberi

Bu dosya, botu **Render Free** üzerinde çalıştırmak için gereken her şeyi tek
yerde toplar: build hatasının kök nedeni, Supabase anahtar biçimi, Telegram
token'ın telefondan alınması ve servisi ayakta tutma (keep-alive) yöntemi.

---

# ⚡ TEK SAYFA KONTROL LİSTESİ

`__` = boş yer. DM Telegram komutları için `TELEGRAM_BOT_TOKEN` ve
`TELEGRAM_CHAT_ID` gereklidir. Supabase URL/anahtar çifti **opsiyoneldir** ve
mevcut botta yalnızca eski cache/durumu okumak içindir: yeni yedek yazılmaz.
`TELEGRAM_TEST_KEY` ve `TELEGRAM_WEBHOOK_SECRET` de opsiyoneldir.

> **Takıldığın yeri tek komutla bul:** `python deploy_check.py --url
> https://<servis-adin>.onrender.com` → Render/Telegram durumunu ve (varsa)
> Supabase okuma bağlantısını kontrol eder. Supabase eksikliği analiz çalışmasına
> engel değildir; Supabase tanımlı olsa bile yeni durum uzaktan yedeklenmez.
> Ayrıntı: **§D3**.

## A) Render → Environment (Telegram gerekli; Supabase opsiyonel)

Render Dashboard → servisin → **Environment** → **Add**. `TELEGRAM_BOT_TOKEN` ve
`TELEGRAM_CHAT_ID` DM komutları için gereklidir. Supabase URL/anahtar çifti
eski uzak kayıtların salt okunur kullanımı için isteğe bağlıdır; ekliyorsanız
anahtar Secret olmalı. `BOT_PROFILE` plain/isteğe bağlıdır.

| # | Key (yazılacak isim) | Value (yapıştırılacak) | Secret? |
|---|---|---|---|
| 1 | `SUPABASE_URL` | `https://pzbuqlvehiokeondvrdq.supabase.co` | hayır |
| 2 | `SUPABASE_SERVICE_ROLE_KEY` | `__` ← Supabase → Settings → API → **service_role** (`eyJ...` ile başlayan uzun metin) | **evet** |
| 3 | `TELEGRAM_BOT_TOKEN` | `__` ← **@BotFather** → `/newbot` → "Use this token" satırındaki kod | **evet** |
| 4 | `TELEGRAM_CHAT_ID` | `__` ← **@userinfobot** → Start → verdiği `Id:` sayısı | **evet** |
| 5 | `BOT_PROFILE` | `Dengeli` | hayır |
| 6 | `TELEGRAM_TEST_KEY` | `__` ← istediğin rastgele bir yazı (örn. `k7m2x9`) | **evet** |
| 7 | `TELEGRAM_WEBHOOK_SECRET` | `__` ← **OPSİYONEL**: rastgele bir yazı (`python3 -c "import secrets; print(secrets.token_urlsafe(24))"`). Doldurursan Telegram komutları webhook ile gelir; boş bırakırsan bot `getUpdates` yoklamasını kullanır (bkz. **§4.6**) | **evet** |

> Supabase'i kullanacaksan #2'nin değerini `eyJhbGciOi...` diye başlayan uzun
> anahtarın tamamından al; kısaltma veya ortadan kesme. Supabase kullanmıyorsan
> #1/#2 ve SQL kurulum adımları atlanabilir.
> #3'ün değeri: `8914822495:AAG...` biçiminde, iki nokta içeren tek satır.
> #7'nin adresi (webhook için) `RENDER_EXTERNAL_URL`'den otomatik üretilir:
> `https://<servis>.onrender.com/webhook` (sırsız; doğrulama secret_token
> başlığıyla). `RENDER_EXTERNAL_URL`'i elle
> **ekleme gerekmez**, Render Web Service'lerde otomatik tanımlıdır.

Boş bırakırsan bot çalışır ama: #1/#2 boşsa eski uzak kayıtlar okunamaz;
tanımlı olsalar da yeni kayıtlar Supabase'e **yazılmaz**. #3/#4 boşsa DM
komut/mesaj yolu çalışmaz (public hedef ayrı yapılandırılır). #7 boşsa komutlar
yoklama ile çalışır; uyuyan bir servis yoklama ile uyandırılamaz.

## B) Render → servis ayarları (env değil, ayar kutusu)

| # | Ayar | Yazılacak |
|---|---|---|
| B1 | Region | `Frankfurt` (ABD ise calisir ama Turk'e ping uzun) |
| B2 | Instance Type | `Free` |
| B3 | Build Command | `pip install -r requirements.txt` |
| B4 | Start Command | `python main.py` |
| B5 | Health Check Path | `/health` |
| B6 | Python Version | Bos birak - repodaki `.python-version` (3.12) zorlar |
| B7 | Root Directory | Bos birak (repo kok) |
| B8 | Auto-Deploy | `After CI Checks Pass` (§2.1; mevcut Dashboard servisinde ayrıca doğrula) |
| B9 | Branch | `main` olmali - `main`de bot kodu yoksa servis acilmaz |

## C) GitHub → repo → Settings → Secrets and variables → Actions

| # | Ad | Nereye | Değer |
|---|---|---|---|
| C1 | `RENDER_HEALTH_URL` | **Secrets** *veya* **Variables** | `__` ← Render adresi + `/health` |

> **Deploy doğrulama:** `/health` yanıtı artık canlı commit'i de içerir:
> `{"status":"ok",...,"commit":"67cadbd","branch":"main"}`. `deploy_check.py`
> bunu yerel HEAD ile karşılaştırır ve fark varsa "Render yeni commit'i deploy
> etmemiş" uyarısı verir. Böylece "merge ettim ama eski sürüm çalışıyor" durumu
> tek komutla görünür olur.

Render'ın servis sayfasında en üstte `https://<adın>.onrender.com` yazar;
`SUPABASE_URL`'deki gibi sadece o adresi al, `/rest/v1` gibi bir şey ekleme.
Örnek biçim: `https://formation-bot-xxxx.onrender.com/health`

Bu adres gizli bir bilgi değildir; **Variables** sekmesine (secret olmadan)
eklemek de yeterlidir. İş akışı sırayla şuna bakar: elle tetikleme girdisi →
`secrets.RENDER_HEALTH_URL` → `vars.RENDER_HEALTH_URL`. Ping adımı çalışırken
hiçbiri yoksa koşu hata verir; zaman penceresi dışında adım atlanabilir. Yeşil
bir koşu tek başına ping gönderildiği anlamına gelmez; adımı ve sonucu inceleyin.

### C2) Secret oluşturmadan hemen denemek (telefondan yapılabilir)

GitHub → **Actions** → sol taraftan **Render keep-alive** → **Run workflow** →
`health_url` alanına `https://<servis-adin>.onrender.com/health` yaz → **Run**.
Elle tetikleme saat penceresini yok sayar; servis uyanırken birkaç dakika sürebilir;
secret'ı sonra eklemen gerekir.

## C2) Otomatik dağıtım kapısı

Mevcut Render servisi → **Settings → Auto-Deploy → After CI Checks Pass**
seçeneğini doğrulayın. Blueprint sadece onunla yönetilen servisleri etkiler;
mevcut servise ikinci Blueprint eklemeyin. Manuel kurtarma hook'u için §2.1'e bakın.

## D) Yapılacak son iki iş

- [ ] Repodaki değişiklikler (`main` branch'i) Render'ın deploy ettiği branch'e
      **merge** edilsin — yoksa Python 3.12 sabiti ve keep-alive çalışmaz.
- [ ] (İsteğe bağlı) Supabase → SQL Editor → `supabase_schema.sql` içeriğini yapıştır → **Run**

## D2) Merge sonrası sırayla doğrula

1. Render → **Events**: yeşil **"Deploy succeeded"** ✅ (kırmızıysa logun
   son 20 satırına bak)
2. `https://<servis>.onrender.com/health`: `status: ok`, `commit` alanı merge
   commit'iyle aynı mı? `/ready` 200 mü? `heartbeat_stale: null` bilinmeyendir.
3. Render → **Logs**: `Telegram bağlantısı OK` · `health endpoint ... başladı`;
   Supabase yapılandırıldıysa ayrıca salt okunur bağlantı sonucu. Loglar tek
   başına güncel veri veya teslim garantisi değildir.
4. Test anahtarı yapılandırıldıysa `X-Test-Key` başlığıyla `/test` çağrılabilir;
   gerçek mesaj gönderir. Ardından yetkili sohbetten `/durum` gibi bir komutu
   bizzat deneyin (HTTP testi komut yolunu doğrulamaz).
5. GitHub → **Actions** → "Render keep-alive": belirli koşuda `GET /health`
   adımının çalıştığını ve HTTP 200 aldığını inceleyin. Koşu yeşili tek başına
   ping kanıtı değildir; varsayılan pencere 08:00–23:00 İstanbul saatidir.

### D3) Tek komutla hepsini kontrol et: `deploy_check.py`

Dört adımı elle gezmek yerine (telefondan Termux'ta da çalışır):

```bash
python deploy_check.py --url https://<servis-adin>.onrender.com
python deploy_check.py --url https://<servis-adin>.onrender.com --test-key <TELEGRAM_TEST_KEY>
python deploy_check.py --env-file .env --send-test-message   # Telegram; Supabase varsa onu da denetler
```

Her satır ya ✅ ya ⚠️ ya ❌ ile biter ve ❌ satırının altında **ne yapılacağı**
yazar (örn. "Supabase → SQL Editor → supabase_schema.sql"). Çıkış kodu 0 yalnız
kritik hata bulunmadığı anlamına gelir; uyarı/atlanan kontroller varken hazır
olunduğunun kanıtı değildir. Token/anahtar değerleri ekrana basılmaz.

## E) Doğrulama (loglarda arayacağın 3 satır)

```
Supabase bağlantısı OK (https://pzbuqlvehiokeondvrdq.supabase.co, tablo: bot_store)
Telegram bağlantısı OK (bot: @__ , chat_id: __)
Render health endpoint 0.0.0.0:____ üzerinde başladı (/health)
```

Webhook modunu açtıysanız (§4.6) 4. satır da gelir:

```
Telegram webhook ucu etkin (POST /webhook, secret X-Telegram-Bot-Api-Secret-Token basliginda)
Telegram webhook kuruldu: https://<servis>.onrender.com/webhook (Webhook was set)
Telegram komutları WEBHOOK modunda: https://<servis>.onrender.com/webhook (yalnızca chat_id __)
```

Webhook kapalıysa bunun yerine `Telegram webhook ucu kapali
(TELEGRAM_WEBHOOK_SECRET tanimli degil)` ve yoklama satırı görünür — ikisi aynı
anda asla açık olmaz.

Bu satırlar yalnızca ilgili başlangıç adımlarını gösterir; veri, teslim ve
başlangıcın tamamlandığını kanıtlamaz. Deploy commit'ini, `/ready` durumunu ve
Telegram komut/mesaj yolunu ayrıca §D2'deki gibi doğrulayın.

---

## 1. Build hatası: `Preparing metadata (pyproject.toml) ... error`

Logdaki asıl satır şu:

```
Preparing metadata (pyproject.toml): started ... finished with status 'error'
╰─> pandas/_libs/window/aggregations...pyx.cpp:422:31: error:
   standard attributes in middle of decl-specifiers
```

Bu bir kod hatası değil, **"hazır tekerlek (wheel) yok"** hatası:

- Render, **2026-02-11'den sonra** oluşturulan servislerde varsayılan Python
  **3.14.3**'tür. Logdaki `Program python found: ... python3.14` bunu doğrular.
- `pandas==2.2.2` ve `numpy==1.26.4` sürümlerinde **cp314 tekerleği yoktur**
  (PyPI'de cp312 var, cp313/cp314 yok).
- pip tekerlek bulamayınca paketi **kaynak koddan derlemeye** düşer; Render
  build imajında gcc 12 vardır ama pandas'ın Cython çıktısı gcc 12 ile derlenemez
  → `metadata-generation-failed` → build düşer.

**Çözüm:** Python'u 3.12'ye sabitlemek. Repoya `.python-version` dosyası eklendi:

```
3.12
```

Render dokümanına göre patch sürümü yazmadan `3.12` yazabilirsin; Render en güncel
3.12.x sürümünü kendisi seçer. Bu yöntem dashboard'daki Python ayarından daha
önceliklidir, yani servisi dashboard'dan elle değiştirmen gerekmiyor.

Dashboard'dan ayarlamak istersen (aynı sonuç): **Settings → Python Version →
`3.12.x` tam sürüm** veya Environment'a `PYTHON_VERSION=3.12.x`.

> Doğrulama: PyPI'da `pandas 2.2.2` → cp312 için 7 tekerlek, `numpy 1.26.4` →
> cp312 için 8 tekerlek var. 3.12'de ikisi de hazır tekerlekten kurulur,
> derleme yapılmaz.

### İkinci temizlik: `borsapy` build zincirinden çıkarıldı

`requirements.txt` içindeki `borsapy==0.11.0` → `openai`, `pymupdf4llm`, `lxml`,
`tradingview-screener` gibi C/Rust uzantılı ağır bir zincir getiriyordu. Repo
içinde `borsapy`'yi import eden **tek bir satır yok** (kullanılan veri kaynağı
`yfinance`). Kaldırıldı, `requirements-optional.txt` dosyasına taşındı; Render
build'ı artık 10 saniyede tamamlanıyor. Yerelde denemek istersen:

```bash
pip install -r requirements-optional.txt
```

---

## 2. Render servis ayarları

Dashboard → **New → Web Service** → repoyu bağla:

| Alan | Değer |
|---|---|
| Runtime | Python |
| Region | Frankfurt (Türkiye'ye en yakın) |
| Instance Type | Free |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Health Check Path | `/health` |

Bot, Render'ın verdiği `PORT` değişkenini görünce `0.0.0.0:$PORT` üzerinde
`/health` açar. HTTP 200 yalnızca bu sunucunun yanıt verdiğini gösterir;
veri, Telegram, Supabase ve tarama sağlığının kanıtı değildir.

Yanıt ayrıca **canlılık alanları** taşır (denetim B-4) — bot donmuş mu, yoksa
yalnız internet mi yavaş, dışarıdan görünür:

| Alan | Anlamı |
|---|---|
| `startup_complete` | Ana döngüye kadar başlangıç işlemleri tamamlandı mı? Harici servislerin sağlığı garantisi değildir. |
| `heartbeat_age_s` | Son heartbeat içindeki `last_scan` zamanının yaşı; yoksa null |
| `heartbeat_stale` | Eşiğe göre `true`/`false` (tarama sürerken 45 dk, seans açıkken 30 dk, seans kapalıyken 72 sa) |
| `heartbeat_stale_esik_s` | O an geçerli eşik (saniye) |
| `tarama_suruyor` / `seans_acik` | Anlık durum bayrakları |
| `evren` / `instance_id` | Taranan hisse sayısı / örnek kimliği |

Render'ın kendi health check'i sorgusuz `/health` çağırdığı için **her zaman 200**
alır (davranış değişmedi). Gerçek izleme yapmak istersen UptimeRobot/cron-job.org
adresini `/health?strict=1` yap: heartbeat bayatken uç **503** döner ve monitör
alarm verir. `heartbeat_stale: null` ise `strict=1` de 200 döner; bu,
heartbeat doğrulandı demek değildir. `/ready` başlangıç tamamlanana kadar ve
kapanışta 503, tamamlandıktan sonra 200 döner. `/ready` tek başına veri/Telegram/
Supabase testi değildir. Render health path'ini `/ready` yapmayın: ilk yükleme
uzun sürebilir ve bu değişiklik dağıtım davranışını etkiler.

> **Kalıcılık:** Render Free üzerindeki varsayılan `DATA_DIR` geçicidir;
> deploy/restart'ta yeni OHLCV, karne, kuyruk ve Telegram limit durumu
> kaybolabilir. Supabase yapılandırılsa da bot şu anda **yalnız okur**, yeni
> yedek veya örnek heartbeat'i yazmaz; uzak çoklu örnek tespiti kapalıdır.
> Eski uzak kayıtlar okunabilir, ancak yeni verinin korunması için uygun kalıcı
> disk ve `DATA_DIR` gerekir. Tek bot örneği kullandığınızı ayrıca doğrulayın.

---

### 2.1 Otomatik deploy: CI kapısı ve manuel kurtarma

Tek otomatik yol kullanın: Render Dashboard → mevcut servis → Settings →
**Auto-Deploy: After CI Checks Pass**, bağlı branch `main`. CI'ın gerçekten bu
commit'te yeşil olduğunu, Render **Deploys** ve `/health` commit alanıyla
canlı sürümü doğrulayın. `render.yaml` yalnızca Blueprint yönetiminde bu ayarı
ister; Dashboard'dan ayrı oluşturulmuş servisi **değiştirmez**. Blueprint
senkronizasyonu ayrı bir dağıtım yolu olabilir; ayarları Dashboard'da doğrulayın.

`.github/workflows/deploy.yml` artık **yalnız manuel** kurtarma içindir; push'ta
hook çağırmaz. Bu değişiklikten önce yalnız hook'a güveniyorsanız Dashboard'da
Auto-Deploy kapısını etkinleştirmeden otomatik deploy durur. Manuel kullanım:
Render → Deploy Hook URL'ini GitHub Actions secret `RENDER_DEPLOY_HOOK` olarak
kaydedin; Actions → Render deploy (manuel) → Run workflow → main. Girdi alanına
hook URL'i yapıştırmayın. Secret eksikse koşu başarısızdır. Manuel hook **CI'ı
atlayabilir**, o anda bağlı branch'in son commitini ister; kabul yanıtı, deploy'un
bittiği veya koşudaki SHA'nın dağıtıldığı anlamına gelmez. `ref` parametresiyle
belirli bir commit deploy etmek Render otomatik deploy'u devre dışı bırakabilir.

**Deploy gerçekten düştü mü?** `python deploy_check.py --url
https://<servis>.onrender.com` komutu `/health` içindeki `commit` alanını yerel
HEAD ile karşılaştırır:

```
✅ [OK  ] /health ayakta (formation-bot)
           https://<servis>.onrender.com/health · canlı sürüm: a1b2c3d
⚠️  [UYARI] Canlı sürüm yerelden FARKLI (canlı a1b2c3d ≠ yerel e4f5g6h)
           Render yeni commit'i henüz deploy etmemiş olabilir: ...
```

---

## 3. Supabase: URL public mi, anahtar secret mi?

Kısa cevap:

| Değişken | Ne girilir | Render'da nasıl işaretlenir |
|---|---|---|
| `SUPABASE_URL` | `https://<proje-ref>.supabase.co` | **Plain** (public, sır değil) |
| `SUPABASE_SERVICE_ROLE_KEY` | `sb_secret_...` **veya** eski `eyJ...` JWT | **Secret** |

**URL:** Supabase Dashboard → Project → **Settings → API → Project URL**.

Render'a yapıştıracağın değer **sonda `/rest/v1/` olmadan**:

```
https://<proje-ref>.supabase.co
```

Dashboard'da gördüğün `https://<proje-ref>.supabase.co/rest/v1/` ise **o
REST API uç noktası**, projeyle ilgili değil. (Kod artık sondaki `/rest/v1`
yazılsa da onu temizliyor, yine de doğru olanı yapıştırmak en temiz yol.)
Bu bir sır değildir; tarayıcıdan da görülebilen bir adrestir. Yine de "Secret"
seçersen de çalışır, Render bunu şifreleyip loglarda maskeler. Tavsiye: URL'yi
**plain** bırak.

**Anahtar — `sb_secret_` formatı doğru mu? Evet, çalışır.** Supabase 2025'te
anahtar sistemini değiştirdi ve artık iki format bir arada geçerli:

| Format | Örnek başlangıç | Nerede | Başlık kuralı |
|---|---|---|---|
| Yeni secret key | `sb_secret_...` | API Keys sayfasındaki **Secret** key | sadece `apikey` |
| Yeni publishable | `sb_publishable_...` | API Keys → Publishable | sadece `apikey` (ama RLS'de yazamaz) |
| Eski service_role | `eyJhbGciOi...` (uzun JWT) | API → Service Role → `service_role` | `apikey` + `Authorization: Bearer` |
| Eski anon | `eyJ...` (anon rolü) | API → anon | `apikey` + `Bearer` (yazamaz) |

`supabase_store.py` artık anahtar türüne göre başlık seçer:

- `sb_secret_...` ve `sb_publishable_...` **JWT değildir**; `Authorization: Bearer`
  olarak gönderilirse Supabase `401 Invalid JWT` döner. Bu yüzden kod **sadece
  `apikey` başlığı** gönderir (`supabase_basliklari()`).
- Legacy `eyJ...` JWT'lerde eski davranış korunur: `apikey` + `Bearer` birlikte.

`sb_secret_...` aldıysan doğrudan yapıştır. Loglarda şunu görürsün (değer asla
loglanmaz):

```
Supabase anahtar türü: yeni secret key (sb_secret_)
Supabase bağlantısı OK (https://xxxx.supabase.co, tablo: bot_store)
```

veya

```
Supabase anahtar türü: legacy JWT (service_role)
```

> **Asla yapma:** `service_role` anahtarını `.env` dosyasını Git'e commit ederek
> paylaşma, README'ye yazma, sohbete yapıştırma. `.env` zaten `.gitignore`'da.
> `anon` / `sb_publishable_...` (publishable) anahtarı **işe yaramaz** —
> RLS açık ve tabloya erişim kapalı; senin tablon için service role/secret şart.

**Doğrulama:** Environment'a ekledikten sonra servis loglarında şunu aramak
gerekir. Yeni `ping()` kontrolü bunu tek bakışta söyler:

```
Supabase bağlantısı OK (https://xxxx.supabase.co, tablo: bot_store)
```

Şunları görüyorsan anahtar/şema hatalıdır (bot yine de çalışır, yerel cache
kullanır):

| Log | Anlamı |
|---|---|
| `Supabase env tanımlı değil` | Environment'a hiç girilmemiş |
| `Supabase env eksik: ... birlikte gerekli` | URL ya da anahtardan biri boş |
| `HTTP 404` | `supabase_schema.sql` çalıştırılmamış ya da tablo adı yanlış |
| `HTTP 401` / `HTTP 403` | Anahtar yanlış/iptal edilmiş, `anon` key yapıştırılmış |

### Tabloyu oluşturma (tek seferlik)

1. Supabase Dashboard → **SQL Editor → New query**
2. Repodaki `supabase_schema.sql` dosyasının tamamını yapıştır → **Run**
3. `public.bot_store` tablosu oluşur (tek satır/anahtar JSONB store)

Bu adım atlanırsa tablo 404 döner ve bot yalnızca yerel cache ile çalışır.

---

## 4. Telegram token'ı telefondan almak

Telefonundayken 2 dakikada alınır, bilgisayar gerekmez.

### 4.1 Bot token'ı

1. Telegram uygulamasını aç, arama çubuğuna **@BotFather** yaz → **Open**
   (mavi tikli, doğru olanı seç).
2. **Start** butonuna bas.
3. `/newbot` yaz ve gönder.
4. **Bot adı** sorar (örn. `BIST Formasyon Radarı`) → bir isim yaz.
5. **Kullanıcı adı** sorar, sonu `bot` ile bitmeli ve benzersiz olmalı
   (örn. `bist_formation_radar_bot`) → yaz.
6. BotFather şunu verir — **bu senin token'ın**:

   ```
   Use this token to access the HTTP API:
   7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
   ```

   `7123456789:AA...` kısmının **tamamı** (rakamlar + iki nokta + `AA` ile
   başlayan 35 karakter) `TELEGRAM_BOT_TOKEN` olacak. Tek bir karakter eksik
   yazarsan `401 Unauthorized` alırsın.

> 🔴 **Token'ı hiçbir yere yapıştırma.** Telegram token'ı olan biri botun adına
> mesaj gönderebilir, botu başka gruplara ekleyebilir. Bu sohbete, WhatsApp'a,
> README'ye veya `.env`'i commit ederek yazma. Yalnızca Render → Environment →
> **Secret** alanına gir. BotFather'da `/revoke` ile istediğin an iptal edip
> yenisini alabilirsin; bir yere sızdıysa hemen iptal et, sonra `/newbot` ile
> yeni bot aç (revoke edilen botun token'ı geri kazanılamaz).

### 4.2 Chat ID (kendine mesaj göndermesi için)

1. Önce **kendi botuna** Telegram'da bir mesaj at ve **Start**'a bas
   (yoksa bot sana mesaj gönderemez, `403 chat not found` alırsın).
2. Arama çubuğuna **@userinfobot** yaz → aç → **Start**.
3. Şu cevabı verir:

   ```
   Id: 1857xxxxxx
   First: Kerem
   Username: ktulu
   ```

   Bu `1857xxxxxx` değeri `TELEGRAM_CHAT_ID` olacak. (Gruba göndermek istersen
   grup id'si `-100...` ile başlar ve negatiftir; bu bot şu an tek kişiye
   gönderim yapacak şekilde kurulu.)

### 4.3 Doğrulama

Environment'a ekledikten sonra loglarda:

```
Telegram bağlantısı OK (bot: @bist_formation_radar_bot, chat_id: 1857xxxxxx)
```

Bu mesajı görmüyorsan token/chat_id yanlış, hata satırı tam neyi söylüyor.
Mesaj gönderilmez, sadece `getMe` ile kontrol edilir.

### 4.4 Mesaj gönderimini test etme

`getMe` yalnız token'ı doğrular. İsteğe bağlı `TELEGRAM_TEST_KEY` ile açılan
`/test` gerçek bir Telegram mesajı gönderir. Anahtarı URL'ye koymayın; başlıkla
kullanın (komut geçmişinde sır bırakmamaya dikkat edin):

```bash
read -rs TEST_KEY; echo
curl -H "X-Test-Key: $TEST_KEY" https://<servis-adin>.onrender.com/test
unset TEST_KEY
```

Eski `?k=` adresleri ancak açıkça `TELEGRAM_TEST_KEY_QUERY=1` seçilirse çalışır;
URL ve erişim kayıtlarına sır sızdırdığı için önerilmez.

| Cevap | Anlami |
|---|---|
| `{"ok": true, "detail": "mesaj gonderildi"}` | Telegram'da test mesaji dustu |
| `{"ok": false, "detail": "HTTP 403: ..."}` | `chat_id` yanlis - bot bu sohbete gidemiyor |
| `{"ok": false, "detail": "HTTP 401: ..."}` | Token yanlis/iptal edilmis |
| `404 ... test endpoint kapali` | `TELEGRAM_TEST_KEY` tanimli degil (ya da henuz deploy edilmedi) |
| `503 ... bot henuz baslamadi` | Servis uyaniyor, 30 sn sonra tekrar ac |

Anahtar yanlissa `403` doner ve **Telegram'a hicbir istek gitmez** - yani
adresi tanimadigi icin disaridan spam gonderilemez.

### 4.5 Telegram'dan komut gönderme (iki yönlü — YENİ)

Bot artık **iki yönlüdür**: alarm göndermenin yanında Telegram'dan gelen
komutları okuyup yanıtlar. Komutlar yoklama (`getUpdates`, varsayılan) ya da
webhook (§4.6) ile toplanır.

İki yetki yolu vardır (2026-10-28'den itibaren):

| Yol | Kim çalıştırabilir | Hangi komutlar |
|---|---|---|
| **DM** (`TELEGRAM_CHAT_ID`) | Bot sahibi | Listelenen **her** komut |
| **Grup/supergroup** (`TELEGRAM_GROUP_ID` ya da `PUBLIC_COMMAND_CHATS`) | O grubun **YÖNETİCİLERİ** (`getChatMember` → `creator`/`administrator`) | Yalnız **okuma** komutları |

Başka sohbetlerden gelen mesajlar sessizce yok sayılır.

> 🔴 **Kanal komut kabul etmez — kanaldan komut İMKÂNSIZDIR.** Telegram **kanal**
> gönderilerini `channel_post` türünde teslim eder; orada gönderen kullanıcı
> bilgisi (`from`) yoktur, yani yöneticilik doğrulanamaz. Ayrıca üyeler zaten
> kanala mesaj **yazamaz**. Kanal hedefi yalnız yayın alır.
>
> ⚠️ **Ad yanıltıcı:** `TELEGRAM_GROUP_ID` alanına `@bisthisseveri` gibi bir
> **kanal** adresi yazmak çok yaygın ve sessiz bir hatadır (kanal kimliği de
> `@ad` / `-100…` biçimindedir). Bu projede **02.10.2026 kararı KANAL** olduğu
> için `TELEGRAM_GROUP_ID` büyük olasılıkla kanalı gösterir → o sohbette komut
> çalışmaz. Kanal yayın için kalabilir; komutlar için **ayrı bir grup** açıp
> kimliğini `PUBLIC_COMMAND_CHATS` olarak verin.
>
> **Kesin teşhis:** bot sahibi DM'den `/teshis` yazar (ya da sunucuda
> `python public_komut_teshis.py`) → hedefin `channel` mı `supergroup` mu olduğu,
> webhook teslimi ve bot üyeliği tek mesajda söylenir. `/health` → `komut.public_hedefler`.
>
> **Kimliği elle aramayın:** kanala bağlı bir tartışma grubu varsa `/teshis` onun
> `-100…` kimliğini `getChat.linked_chat_id` ile okur ve yapıştırılacak satırı
> hazır verir: `PUBLIC_COMMAND_CHATS=-100…` (`komut.public_hedefler[*].bagli_grup`).
>
> ⚠️ **Kimlik biçimi:** `getChat`/`getChatMember` kullanıcı adını `@` ile ister.
> Config eşleştirme için `@`yı atar, API sınırında `telegram_sohbet_kimligi()`
> geri ekler. Tırnak, boşluk ve `t.me/...` bağlantıları da temizlenir; sayısal
> kimlik (`-100…`) aynen kullanılır. (2026-10-29: `PUBLIC_COMMAND_CHATS=@ad`
> eklenince `@` atıldığı için `getChat` "chat not found" dönüyordu.)

#### Grup komutlarını açma (varsayılan: AÇIK)

```text
PUBLIC_COMMANDS_ENABLED=1          # 0 = grubu tamamen salt-okunur yayına çevir
PUBLIC_COMMAND_CHATS=              # boş = TELEGRAM_GROUP_ID
PUBLIC_COMMAND_EXTRA=              # public'te kapalı komutları aç (örn. tara)
PUBLIC_COMMAND_ADMIN_CACHE_SN=300  # getChatMember önbelleği (0 = kapalı)
```

Üç kilit **birlikte** çalışır: sohbet listede olacak + komut beyaz listede olacak
+ gönderen yönetici çıkacak. Kendi grubunuzda denemek için:

1. Botu gruba ekleyin (en az bir kez mesaj atabilmesi yeterli).
2. Sizin hesabınız grupta **yönetici** olsun.
3. Grupta `/durum` yazın → cevap **gruba**, isteğinizi alıntılayarak gelir.

Davranış ayrıntıları:

* Yönetici **olmayan** üyenin komutu sessizce yok sayılır (grupta "yetkiniz yok"
  cevabı bot spam'i olurdu). Sayaç `/health` → `komut.yetkisiz_kullanici`.
* Yöneticilik **API'ye sorulamazsa yetki verilmez** (fail-closed). Sayaç
  `/health` → `komut.admin_kontrol_hatasi`.
* Public'te varsayılan **kapalı**: `/tara`, `/grafik`, `/evet`, `/hayir` — ağır
  ya da durum değiştiren komutlar. `PUBLIC_COMMAND_EXTRA=tara` ile açılabilir
  (uyarı: `/tara` tam evren taramasıdır, dakikalarca sürer).
* **`/grafik` grupta (2026-10-28):** `PUBLIC_COMMAND_EXTRA=grafik,g` yazılınca
  komut grupta çalışır ve **kareler + sonuç metni o gruba** gider
  (`grafik_sohbete_gonder(chat_id=…)` / `send_to_chat`). DM'den çağrıldığında
  davranış değişmez (kareler DM'e). İlerleme/gecikme mesajları her iki yolda da
  DM'de kalır. `/g` ayrı bir addır: yalnız `grafik` yazarsan `/g` kapalı kalır.
  Bot gruba **yönetici** olmalıdır; değilse `sendMediaGroup` 403 döner ve kareler
  gönderilemez (log: "grafik albümü gruba gönderilemedi").
* `PUBLIC_COMMAND_EXTRA` **alias'ları da** kapsar: `/p` açıksa `/panel` de açıktır
  (beyaz liste işleyici bazlıdır).
* `/health` → `komut` bloğunda `public_komut_hazir`, `public_islenen`,
  `yetkisiz_kullanici`, `admin_kontrol_hatasi`, `public_kapali_komut` alanları
  "grupta komut çalışmıyor" sorusunun hangi kapıda takıldığını gösterir.
* **Kanal teşhisi:** `komut.public_hedefler` her hedefin `getChat` ile okunan
  gerçek tipini (`tur`) ve komut alıp alamadığını (`komut`) taşır;
  `komut.kanal_gonderisi` kanaldan gelen gönderi sayısıdır. Sıfırdan büyükse
  hedef kanaldır → komut beklemeyin.
* **Hangi yoldan işlendi:** `komut.son_komut_kaynagi` (`dm`/`public`) ve
  `komut.son_sohbet_tipi`. `dm` ise grup yolu hiç devreye girmemiştir.
* `/teshis` **public beyaz listede** (salt-okunur): grup yöneticisi de çalıştırabilir.
* Telegram'a `allowed_updates` olarak `message`, `edited_message`, `channel_post`,
  `edited_channel_post` bildirilir. `channel_post` **bilinçli**: kanal hedefinde
  "hiçbir şey olmuyor" yerine "hedef kanal" cevabını verebilmek için.

| Komut | Ne yapar |
|---|---|
| `/formasyonlar` | Günün canlı formasyonları (hisse, TF, tip, kalite, state, üst/alt seviye) |
| `/formasyonlar 1h` | Zaman dilimi filtresi (`1h`, `2h`, `4h`, `1d`) |
| `/formasyonlar THYAO` | Hisse veya formasyon adı filtresi |
| `/canli` veya `/c` | Canlı formasyonlar **tek kompakt mesajda** (kalabalık günde hızlı bakış) |
| `/panel` veya `/p` | **Evrendeki semboller × 4 zaman dilimi slot tablosu** (varsayılan 57 sembol) + sayılar + **puanı en yüksek 12 anlamlı aday**. Diğer adlar: `/genel`, `/tablo` |
| `/panel 1h` | Panel filtresi: yalnızca o TF kolonu (çoklu TF de verilebilir: `/panel 1h 4h`) |
| `/panel THYAO` | Panel filtresi: yalnızca o hisse(ler) satırı (kısmi ad yeter: `/panel thy`) |
| `/panel kirilim` | Panel filtresi: state/desen adı (`kirilim`, `retest`, `üçgen`, `KIRILIM_TEYITLI` ...) |
| `/panel 1h THYAO` | Filtreler birlikte de kullanılabilir |
| `/ozet` veya `/o` | Günlük özet tek mesajda (tamamlanan/retest/sıkışan sayıları) |
| `/sikisanlar` · `/tamamlanan` · `/retest` · `/kirilim` | Kısa listeler (kısayollar: `/s`, `/t`, `/r`, `/k`) |
| `/durum` | Profil, piyasa açık/kapalı, son tarama yaşı, canlı sayı, veri sağlığı, günlük alarm/hata sayacı |
| `/tara [HISSE]` | Yeni veriyi çekerek analiz eder (seans dışı da; cache'teki en yeni timestamp/veri yaşı raporlanır; timestamp'in tamamlanmış mum anlamı provider sözleşmesine bağlıdır) |
| `/yardim`, `/start` | Komut listesi |

Panel nasıl okunur (tek satır = bir sembol, hücreler `TF kalite` + işaret):

```
THYAO 1h 87🚀 · 2h — · 4h 75⚡ · 1d —
        🚀 kırılım   🎯 retest   🏁 tamamlandı   ⚡ sıkışma   — boş slot
```

Akış: `/panel` tüm evreni (varsayılan 57 sembol), `/tara [HISSE]` istenen kapsamı kuyruğa alır.
Ana döngü uyandırılır ve iş tamamlanınca kapsam, cache'teki en yeni mum timestamp'i,
veri yaşı ve sonuç tek mesajda raporlanır. Bu timestamp'in tamamlanmış mum anlamı
provider sözleşmesine bağlıdır ve bu doğrulama turunda canlı provider'da ölçülmemiştir;
seans dışı veri ayrıca canlı olmayabilir. Supabase sonuç üretmek için zorunlu
değildir; yalnızca OHLCV önbelleği/geçmiş kaydı için opsiyoneldir.

> ⚠️ **Sonuç güvenliği:** Eksik/başarısız tarama başarılı boş sonuç sayılmaz ve
> önceki başarılı sonuçları silmez. Başarılı, gerçekten boş tarama ise açıkça
> “canlı formasyon bulunmadı” olarak raporlanır. Yeniden başlatılmış eski analiz
> snapshot'ı güncel kabul edilmez; `/panel` yeni veriyle hesaplama başlatır.
> İstanbul saatiyle `POST_CLOSE_ANALYSIS_TIME` (varsayılan `20:00`) anında
> bağımsız bir tam evren analizi ve ayrı rapor çalışır. Analiz sürerken `/durum`
> ilerlemeyi, liste komutları son tamamlanan sonuçları gösterir. Yeni `/panel` ve
> `/tara` istekleri tek tek çalışır; en fazla 3 istek bekler. Tekrarlanan aynı
> istek yeni iş eklemez; zamanlı işler bekleyen manuel analizlerin arasına girebilir.
> Sırası geldiğinde 30 dakikayı aşmış istek çalıştırılmaz ve kullanıcı bilgilendirilir;
> bildirim önceki işler bitene kadar gecikebilir. Bellek içi sıra yeniden başlatmada kaybolur.

> ⚠️ **Tek tüketici kuralı:** Telegram aynı token için **iki süreç** aynı anda
> `getUpdates` yaparsa ikincisi `409 Conflict` alır. Termux/PC'de açık kalmış
> ikinci bir kopya varsa **kapatın**; bot bunu logda net söyler ve dinleyiciyi
> durdurur (alarmlar çalışmaya devam eder). Render `/test` ucu yalnızca
> `sendMessage` kullanır, bu kuraldan etkilenmez.

Komut listesi `.env` değişkeni gerektirmez; token/chat_id doğruysa otomatik
açılır. Token/chat_id yoksa bot eskisi gibi yalnızca alarm gönderir.

> 😴 **Servis uykudayken komut:** Render Free 15 dakika inbound istek almazsa
> uyur; uyuyan servis DM komutunu göremez (Telegram mesajı HTTP isteği değildir).
> Bot uyandığında 15 dakikadan eski komutları **çalıştırmaz** (dünkü `/tara`
> yanlış sonuç üretmesin diye) ama artık sessiz de kalmaz: atlanan komutlar için
> tek bir "bot uyanık değildi" mesajı, geç teslim edilen `/yardim`, `/durum`
> gibi okuma komutları için gecikme notlu yanıt gönderilir.
> Sebebi ve modu **`/health`** çıktısındaki `komut` alanından okuyabilirsin:
> `{"mod": "webhook|yoklama|kapali", "dinleyici_canli": true, "islenen": 3,
> "yetkisiz_sohbet": 0, "bayat_atlanan": 12, "mesgul_atlanan": 4,
> "son_komut_sn_once": 240}`.
> `yetkisiz_sohbet > 0` ise komutlar başka bir sohbetten (yanlış `chat_id`)
> geliyordur; `mod: kapali` ise token/chat_id tanımlı değildir.
> Telegram tarafını (webhook kaydı, teslim hatası, bekleyen güncelleme) tek
> komutla görmek için: `python deploy_check.py --url https://<servis>.onrender.com`.

Gönderim tarafını yine 4.4'teki `/test` ucuyla doğrula. Gerçek alarm akışı ise
bir formasyon tetiklendiğinde devreye girer: varsayılan evrende 57 sembol × 4
zaman dilimi taranır; ilk alarm birkaç gün sürebilir — bu arada `/formasyonlar` ya da
`/panel` yazarak canlı adayları görebilirsin.

### 4.6 Webhook modu (opsiyonel — Render Web Service için önerilir)

Varsayılan mod **yoklama**dır: bot `getUpdates` ile Telegram'ı uzun süre dinler.
Render gibi bir web serviste komutları **webhook** ile almak daha stabildir:
Telegram güncellemeyi doğrudan HTTPS ile iter, bot da zaten `/health` için açık
olan küçük HTTP sunucusunu kullanır (ayrı port/thread yoktur).

**Açmak için:** Render → Environment → `TELEGRAM_WEBHOOK_SECRET` = rastgele bir
yazı. Başka hiçbir şey gerekmez; `RENDER_EXTERNAL_URL` Render tarafından
otomatik verilir ve adres şöyle kurulur:

```
https://formation-bot.onrender.com/webhook
```

A7 (Batch 6): sır artık adresin içinde DEĞİL. Doğrulama, `setWebhook` sırasında
bildirilen `secret_token` ile gelen `X-Telegram-Bot-Api-Secret-Token` başlığından
yapılır; böylece sır Telegram sunucularına, proxy ve Render erişim loglarına
düşmez. Eski kayıtlar (`…/webhook/<secret>`) geriye dönük kabul edilir ama sır
loglara düşer ve bir sonraki açılışta sırsız adresle değiştirilir.

Bot açılışta `setWebhook` çağırır, Telegram'a `secret_token` olarak da bildirir
ve **yoklamayı kapatır** (aynı token'da `getUpdates` + webhook birlikte olmaz;
ikisi birlikte 409 Conflict üretir). Secret'i silip yeniden deploy ederseniz bot
`deleteWebhook` çağırır ve yoklamaya döner — mod geçişi otomatik ve tek yönlüdür.

**Bekleyen güncelleme politikası:** Her açılış/mod geçişinde webhook kurulurken
`setWebhook`, polling'e dönülürken `deleteWebhook`, `drop_pending_updates=True`
ile çağrılır. Telegram çağrıyı başarıyla onayladığında o anda bekleyen **tüm**
güncellemeler (taze görünen komutlar dahil) bilerek atılır; bot yalnızca bu onaydan
sonra gelen yeni güncellemeleri işler. Bu kasıtlı davranıştır; yeniden başlatma
öncesi kuyruğun korunacağı varsayılmamalıdır. Polling'e geçişte Telegram bu silmeyi
başarıyla onaylamazsa bot en çok beş kez artan aralıklarla (1, 2, 4, 8 sn) dener;
onay yine alınamazsa eski update'leri çalıştırmamak için polling listener'ı başlatmaz
ve hata loglar. Komut dinleyicisi bu başlangıçta kapalı kalır.

Doğrulama (telefondan tarayıcıyla da yapılabilir):

| Adres / komut | Beklenen |
|---|---|
| `https://<servis>.onrender.com/webhook` (GET, tarayıcı; eski `<secret>` yolu da çalışır) | `{"ok": true, "webhook": "hazir", "bot_hazir": true, ...}` |
| `https://api.telegram.org/bot<token>/getWebhookInfo` | `"url"` sizin adres, `"pending_update_count"` düşük, `last_error_message` yok |
| Render → Logs | `Telegram webhook kuruldu: https://.../webhook` ve `Telegram komutları WEBHOOK modunda` |

| Cevap | Anlamı |
|---|---|
| `404 webhook kapali` | `TELEGRAM_WEBHOOK_SECRET` tanımlı değil (ya da henüz deploy edilmedi) |
| `403 yanlis webhook adresi` | Adresteki secret yanlış (Telegram'a yazılanla aynı olmalı) |
| `503 bot henuz baslamadi` | Servis uyanıyor; Telegram tekrar dener, komut kaybolmaz |
| `500 isleyici hatasi` | Komut işleyicisi patladı; Telegram tekrar dener, logda ayrıntı var |
| `400 JSON cozumlenemedi` / `413 govde cok buyuk` | Bozuk/kötü niyetli istek; 1 MB üstü gövde reddedilir |

> - Telegram webhook için **HTTPS zorunludur**; `http://` adres üretilirse bot
>   webhook kurmaz, logda söyler ve yoklama moduna döner.
> - Uç, secret tanımlı değilken **404** döner (aynı `/test` kuralı): kurulu
>   olmayan bir uç kendini belli etmez.
> - Sır loglara **yazılmaz**; logda yalnız `.../webhook` görünür (sır başlıkta taşınır).
> - Render Free uykuya geçerse webhook teslimatı başarısız olur; Telegram bunu
>   birkaç saat boyunca artan aralıklarla **tekrar dener** (§5 keep-alive
>   penceresi içinde kalırsanız pratikte kayıp olmaz). Uzun süren uykularda
>   güncellemeler Telegram tarafında düşebilir — kritik komutları seans
>   saatlerinde gönderin.
> - Yerelde (Render dışı) `PORT` env'i yoksa HTTP sunucusu başlamaz; secret
>   tanımlı olsa bile bot otomatik olarak yoklamaya düşer, komutlar susmaz.

---

## 5. Servisi ayakta tutma (keep-alive)

Render Free bir web service'e **15 dakika inbound istek gelmezse** onu uyutur;
uyanması ~1 dakika sürer, o dakika boyunca tarama yapılmaz. Telegram'a 15
dakikada bir mesaj gelmesi de kendiliğinden koruma sağlamaz, çünkü mesaj
**outbound** bir istektir.

> ⚠️ **Ölçüm (Ekim 2026) — Actions cron'u 5 dakikada bir ÇALIŞMIYOR.**
> Bu repoda `*/5 * * * *` yazmasına rağmen GitHub koşuları seyrek tetikledi:
> 29 Eylül – 4 Ekim arasında **günde yalnızca 4–6 koşu** düştü (beklenen 288),
> bunların da çoğu pencere dışı olduğu için **günde 0–3 gerçek ping**. Sonuç:
> servis gün içinde saatlerce uyuyor ve o sırada yazılan `/yardim`, `/durum`
> gibi DM komutları SESSİZCE yanıtsız kalıyor — Telegram mesajı Render'a gelen
> bir HTTP isteği olmadığı için servisi uyandırmaz.
> Ölçümü istediğin an tekrarla:
>
> ```bash
> gh run list --workflow keepalive.yml --limit 20
> ```
>
> Bu yüzden **Seçenek B (dış monitör) birincil yol olmalı**; Actions tek başına
> yeterli değildir. Komutların uyku sırasında da çalışması için **§4.6 webhook
> modu** en etkili çözümdür (Telegram'un POST'u gerçek bir inbound istektir ve
> servisi uyandırır).

### Seçenek A — GitHub Actions (public repoda ücretsiz; tek başına YETERSİZ) ⚠️

Repo içinde `.github/workflows/keepalive.yml` hazır. **5 dakikada bir**
`/health` adresine istek atar. Neden 5 ve neden sadece gündüz:

- GitHub `schedule` **“en iyi çaba”** ile çalışır; yoğun saatlerde koşular
  5–20 dakika gecikebilir. 15 dakikalık uyku eşiğine karşı 5 dakikalık aralık
  pay bırakır (10 dakikalık aralıkta bir gecikme servisi uyutabilir).
- Komutlar (`/formasyonlar`, `/tara`, ...) da bu yüzden servis uyanıkken çalışır:
  servis uykuya geçtiyse ilk komut onu ~1 dakikada uyandırır ama cevap ilk turda
  gecikebilir. Seans içinde ping penceresi bunu zaten engeller.
- Ping **her gün İstanbul saatiyle 08:00–23:00** arasında atılır; gece servis
  uyur. Pencere BIST seansını (09:50–18:40) kapsar **ve akşam Telegram
  komutları da anında cevaplanır** (uyuyan servis komuta cevap veremez, çünkü
  Telegram mesajı Render'a gelen bir HTTP isteği değildir; gelen tek trafik bu
  pingdir). Kota: Render Free aylık **750 instance saat** verir; 15 sa/gün
  ≈ 450–465 saat/ay, 7/24 ise ≈ 730 saat/ay (sınıra çok yakın). Kota taşarsa
  servis ay sonuna kadar askıya alınır.
- Pencere dışında iş akışı “içeride miyim?” kontrolünden sonra hiçbir şey
  yapmaz ve yeşil biter; servis 15 dakikada bir normal şekilde uyur, 08:00'deki
  ilk ping onu ~1 dakikada uyandırır ve bot ilk taramayı 10:35'te yapar.
- Gece komut yanıtı da istiyorsan `KEEPALIVE_ALWAYS=true` yap (7/24 ping).

Ayarlar (istersen, Actions → Variables):

| Değişken | Etkisi |
|---|---|
| `KEEPALIVE_ALWAYS=true` | Pencereyi kapatır, 7/24 ping atar (komutlar gece de çalışır, kota ~730 sa/ay) |
| `KEEPALIVE_WINDOW_START` / `KEEPALIVE_WINDOW_END` | Pencereyi değiştirir (varsayılan `0800` / `2300`; `0930`/`1850` = yalnızca seans) |
| `KEEPALIVE_WEEKDAYS_ONLY=true` | Hafta sonu ping atmaz (pencere hafta içi kalır) |

Kurulum (tek seferlik, telefondan da yapılabilir):

1. GitHub → repo → **Settings → Secrets and variables → Actions**
2. **New repository secret** (veya sekmesi **Variables**) → ad:
   `RENDER_HEALTH_URL`, değer: `https://<servis-adin>.onrender.com/health`
3. Kaydet. İlk koşu en geç 5 dakika içinde Actions sekmesinde görünür.

> Secret oluşturmadan denemek istersen: **Actions → Render keep-alive →
> Run workflow → `health_url` alanına adresi yaz → Run.** Elle tetikleme
> pencereyi yok sayar, yani hemen ping atar.

#### Kota gerçeği: public mi, private mı? (önemli)

| Repo tipi | Actions dakikası | 5 dk'lık cron ne yakar? |
|---|---|---|
| **Public** (bu repo) | Ücretsiz ve **sınırsız** | Sorun yok, `*/5` en güvenli seçenek |
| Private | 2.000 dk/ay ücretsiz | Her koşu **en az 1 dk** yazılır: `*/5` ≈ 8.600 dk/ay, `*/10` ≈ 4.300 dk/ay → **kota biter** |

Yani repo private olsaydı GitHub Actions ile keep-alive ücretsiz olmazdı;
o durumda **Seçenek B**'ye (cron-job.org / UptimeRobot, ücretsiz) geç.
(Eski sürümde yazan “10 dakikada bir koşu ≈ 25 dk/ay” hesabı yanlıştı;
GitHub her koşuyu en az 1 dakika olarak faturalandırır.)

#### ⚠️ 60 gün kuralı: public repoda zamanlanmış işler sessizce durur

GitHub, **public** bir repoda 60 gün boyunca hiç repo aktivitesi (commit/PR)
olmazsa zamanlanmış iş akışlarını **kendiliğinden devre dışı bırakır** — koşu
durmaz, hata da vermez. Actions sekmesinde gri bir uyarı ve “Enable workflow”
düğmesi görürsün; `gh workflow enable keepalive.yml` de işe yarar. Kalıcı
çözüm: Seçenek B'yi (dış monitör) kurmak ya da repoya ara ara commit atmak.

Render'ın kendi Cron Job'u ise **ücretsiz değil** (aylık en az 1 $) ve ayrıca
uyuyan bir web service'ı uyandırmaz.


#### ⚠️ Self-hosted runner sayfasını KULLANMA

GitHub, "Self-hosted runners" bölümünden bir **runner kayıt token'ı** veren
kurulum sayfası açıyor. O sayfa **bize gerekmiyor** — `keepalive.yml`
`runs-on: ubuntu-latest` kullanıyor, yani GitHub'ın kendi ücretsiz
makinesinde koşuyor. Self-hosted runner'ın çalışması için 7/24 açık bir Linux
sunucu ister; Render Free, telefonun veya bu repo için hiçbir şeye ihtiyacımız
yok. İndirdiğin `actions-runner-*.tar.gz` klasörünü silebilirsin.

O sayfadaki `--token CAJRK...` değeri de gizli bir bilgidir (yalnızca runner
kaydı yetkisi verir, 1 saatte geçerliliği biter). Kimseyle paylaşma, ihtiyacımız
da yok.

#### ⚠️ Schedule sadece varsayılan branch'te çalışır

GitHub, `schedule` tetikleyicisini **yalnızca repo'nun varsayılan branch'inde**
(varsayılan olarak `main`) çalıştırır. `.github/workflows/keepalive.yml`
`main` üzerinde değilse Actions sekmesinde hiç görünmez ve hiç çalışmaz.

Bu, `.python-version` için de geçerli: Render hangi branch'i deploy ediyorsa
oraya merge edilmesi gerekir. İkisi de tek seferde çözülür.

### Seçenek B — cron-job.org / UptimeRobot (ücretsiz — ÖNERİLEN BİRİNCİL YOL) ✅

`https://cron-job.org` veya UptimeRobot'a üye ol, `https://<servis>.onrender.com/health`
adresini **her 5 dakikada bir** GET ile çağrılan monitör olarak tanımla
(gün/gece ayrımı yapmıyorsa da çalışır, sadece 750 saat kotasını daha hızlı
tüketir). Repo aktivitesi, Actions kotası, cron gecikmesi veya 60 gün kuralıyla
hiç işi yoktur; GitHub tarafı tamamen kopsa bile çalışır. Actions'ı yedek olarak
bırakmak en sağlamıdır.

### Seçenek B2 — Webhook modu (komutların uykuyu uyandırması, §4.6)

`TELEGRAM_WEBHOOK_SECRET` tanımlıysa Telegram güncellemeyi doğrudan servise
POST eder. Bu **inbound** bir istek olduğu için uyuyan servisi uyandırır:
DM'den `/yardim` yazınca servis ~1 dakikada açılır ve komut yanıtlanır
(Telegram teslim edemezse birkaç saat boyunca tekrar dener). Keep-alive hiç
çalışmasa bile DM komutları kaybolmaz; yalnızca ilk yanıt gecikir.

### Seçenek C — Background Worker (ücretli, ama en sağlam)

Instance tipini **Background Worker** yaparsan 15 dakikalık uyku kuralı
uygulanmaz; sürekli çalışır, ping'e ihtiyaç duymaz. Render cron/worker için
ücretli plandır.

### Günlük saat 750 sınırı

Tek bir Free web service 7/24 çalışsa bile ayda ~720 saat eder; workspace
başına ücretsiz sınır 750 saat/aydır. Yani **tek bot için saat sorunu yoktur**,
tüm süre boyunca ayakta kalabilir. 750 saati aşmamak için ikinci bir Free
servis açma.

---

## 5.1 Dengeli Deployment ve Gece Döngüsü (GÜNCEL - Render Free için sadeleştirildi)

Eski planda 5 görevli, 1.5dk iş / 3.5dk uyku döngüsü vardı (Oracle reclaim'i engellemek için %35-45 CPU hedefi).
Render Free'de bu gereksiz, hatta zararlı. 750 saat sınırı içindeyiz:

- 20 iş günü x 24 saat = 480 saat, 30 gün x 24 = 720 saat < 750 saat
- Keep-alive zaten GitHub Actions ile 08:00-23:00 arası yapılıyor (15 saat/gün)
- Gece CPU yakmak saati boşa harcar, RAM şişirir, Yahoo rate-limit yedirir

**Güncel 3 fazlı mimari (bedava kalma odaklı):**

| Faz | Saat | CPU | İş |
|---|---|---|---|
| Canlı | 09:50-18:10 | %60-80 | Mum kapanış +5dk tarama, Telegram DM + kanal |
| Kapanış Bakımı | 18:10-19:00 | %20 15dk | Veri hijyeni (hacim 0 bar), state temizliği (48h ölü), gün sonu raporu |
| Gece | 19:00-08:00 | %0-2 | Derin uyku `sleep(300)`, sadece keep-alive ping, Yahoo'ya istek yok |
| Pre-load | 08:30 | %25 | Sabah 10 hissenin son 5 gününü yavaşça çek, 09:50'de 0-latency |

Self-calibration (botun kendi skorunu otomatik değiştirmesi) public öncesi kapatıldı - manuel tuning daha güvenli.
`fetch_last_bar()` ve `evening_maintenance()` fonksiyonları eklendi.

## 6. Ortam değişkenleri (Render → Environment)

| Anahtar | Değer | Secret? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather token'ı | Evet |
| `TELEGRAM_CHAT_ID` | Kendi Telegram id'n (owner DM) | Evet |
| `TELEGRAM_GROUP_ID` | **Public kanal hedefi (ÖNERİLEN ad):** `@bisthisseveri` veya `-100...`. Bot kanalda **yönetici** olmalı (Mesaj gönderme; sabit mesaj için Mesajları sabitle). DM olmadan da yayın çalışır. Kontrol: `python deploy_check.py` ve `python kanal_acilis.py --durum` | Evet |
| `TELEGRAM_CHANNEL_ID` | Aynı şeyin eski adı (hâlâ desteklenir; ikisi de kanal/grup için çalışır) | Evet |
| `SUPABASE_URL` | `https://<ref>.supabase.co` (opsiyonel eski cache/state için salt okunur erişim) | Hayır (plain) |
| `SUPABASE_SERVICE_ROLE_KEY` | `sb_secret_...` veya `eyJ...` | Evet |
| `BOT_PROFILE` | `Dengeli` / `Hassas` / `Seçici` | Hayır |
| `SUMMARY_HOURS` | `09:55,18:45` (İstanbul; akşam özeti son tarama sonrasına alınır) | Hayır |
| `DEFERRED_ALERT_DIGEST_TIME` | `18:45` (İstanbul; ertelenen adaylar kapanış özetine eklenir) | Hayır |
| `POST_CLOSE_ANALYSIS_TIME` | `20:00` (İstanbul, ayrı günlük tam evren analizi) | Hayır |
| `OFFSESSION_CACHE_MAX_AGE_DAYS` | `14` (fetch yokken izin verilen en eski seans dışı cache) | Hayır |
| `PUBLIC_MIN_QUALITY` | `80` (public kanala min kalite) | Hayır |
| `PUBLIC_STATES` | `FORMASYON_TAMAMLANDI,RETEST_BASARILI` (public kanala giden state'ler) | Hayır |
| `BOT_INSTANCE_ID` | Boş = `hostname:pid`. Örnek adı; salt okunur modda uzak çoklu örnek tespiti kapalıdır | Hayır |
| `LOG_LEVEL` | `INFO` (varsayılan) | Hayır |
| `TELEGRAM_TEST_KEY` | `/test` için anahtar; `X-Test-Key` başlığı (bkz. §4.4). `?k=` yalnız `TELEGRAM_TEST_KEY_QUERY=1` iken kabul edilir | Evet |
| `TELEGRAM_WEBHOOK_SECRET` | Rastgele metin; doluysa komutlar webhook ile gelir (bkz. §4.6). Boş = yoklama | Evet |
| `TELEGRAM_WEBHOOK_URL` | (Opsiyonel) Tam webhook adresi; boşsa `RENDER_EXTERNAL_URL` + `/webhook` (sırsız) | Evet |
| `HEALTH_RATE_LIMIT_PER_MIN` | `60` — public HTTP uçlarında IP başına dakikalık istek limiti (0 = kapalı) | Hayır |
| `TELEGRAM_TEST_KEY_QUERY` | `0` — `/test?k=` sorgu anahtarı kabul edilsin mi (0 = yalnız başlık) | Hayır |
| `HEARTBEAT_MIN_ARALIK_SN` | `60` — yerel heartbeat dosyası yazım aralığı (B5) | Hayır |
| `HEARTBEAT_UZAK_ARALIK_SN` | `300` — yazılabilir store için aralık; mevcut salt okunur modda uzak heartbeat yazılmaz | Hayır |
| `PICKLE_CACHE` | `0` — 1 ise eski `.pkl` kopyası da yazılır (JSON birincil; A8) | Hayır |
| `MARKET_SUFFIX` | `.IS` — Yahoo sembol eki (BIST). BIST dışı pazar izlerseniz değiştirin | Hayır |
| `STOCK_UNIVERSE` | Virgülle ayrılmış semboller (`THYAO,GARAN`); boş = BIST 50 | Hayır |
| `KARNE_GUNU` | `4` — karne gönderim günü (0=Pazartesi ... 4=Cuma) | Hayır |
| `KARNE_HEDEF_ATR` | `1.5` — kırılım sonrası "hedef" sayılan lehte hareket (ATR katı) | Hayır |
| `KARNE_STOP_ATR` | `1.0` — "stop" sayılan alehte hareket (ATR katı) | Hayır |
| `TELEGRAM_GRAFIK` | `yok` (varsayılan) / `alarm` — alarm metninin altına mum karesi ekler (§6.2) | Hayır |
| `TELEGRAM_GRAFIK_ADET` | `4` — alarm başına kare sayısı (1-4). Free planda `1-2` | Hayır |
| `GRAFIK_MUM_MAKS` | `80` — formasyon YOKKEN gösterilen mum sayısı (üst sınır). Varsayılan TF matrisi: 1s 80 · 2s 74 · 4s 68 · 1g 62; formasyon varsa kadraj formasyona odaklanır (formasyon + 10 mum tampon, 35-180 arası — 2026-10-23: 85 mum formasyonun kırılım tabanını kesiyordu) | Hayır |
| `GRAFIK_OLAY_MAKS` | `6` — kareye çizilen onaylı BOS/CHoCH sayısı | Hayır |
| `GRAFIK_SAG_BOSLUK_ORANI` | `0.15` — son mumun sağındaki boş alan, **eksen genişliğinin yüzdesi** (%15; kabul penceresi %10-20, otomatik kural bu aralığa kırpılır). Fiyat etiketleri ve 🎯 hedef kutusu buraya çizilir, bant/kutu/aktif BOS çizgileri buraya uzar. `0` = kapalı | Hayır |
| `GRAFIK_SAG_BOSLUK_MUM` | tanımsız — verilirse üstteki yüzde kuralını ezer ve boşluğu SABİT MUM sayısı yapar (eski yol; `0` = kapalı) | Hayır |
| `GRAFIK_HACIM_PANELI` | `0` (kapalı) — kaldırılan alt hacim kulvarını geri getirir; hacim yalnız sıra dışı mumların altında YÖNLÜ rozetle gösterilir: `⚡↑ x2,5` patlama (RVOL > 2,0×), `⚡↓ x0,5` kuruma (RVOL ≤ 0,5×) | Hayır |
| `GRAFIK_RVOL_ROZET_ESIK` | `2.0` — bu RVOL üstü mumlara `⚡↑` rozeti (patlama) | Hayır |
| `GRAFIK_RVOL_ROZET_MAKS` | `6` — kare başına toplam rozet tavanı (iki yön); her yönün EN YENİ uygun mumu her durumda rozet alır | Hayır |
| `GRAFIK_RVOL_ROZET_ESIK_DUSUK` | `0.5` — bu RVOL altı/eşit mumlara `⚡↓` rozeti (kuruma); `0` yazarsanız kapatır | Hayır |
| `GRAFIK_RVOL_ROZET_DUSUS_MAKS` | `2` — kuruma (`⚡↓`) rozeti kare başına en fazla kaç mumda görünür (en sert kurumalar seçilir); `0` = kuruma rozeti kapalı | Hayır |
| `GRAFIK_LEJANT_KARE` | `0` (kapalı) — lejant/dipnot bloğunu kare içine geri koyar (varsayılan: bu bilgiler kare altı caption dipnotuna gider) | Hayır |
| `KARNE_HORIZON_BAR` | `10` — sinyalden sonra izlenen bar sayısı | Hayır |
| `DATA_DIR` | Veri dizini. Render'da varsayılan `/tmp/formation-bot-data` geçicidir; Supabase yeni yedek almaz. Kalıcı disk bağlarsanız buradan verin | Hayır |
| `SEED_DATA_DIR` | `./bot_data` — DATA_DIR'de dosya yoksa **yalnız okuma** için kullanılan seed veri | Hayır |
| `LOG_DIR` | `/var/log/bist-bot`; yazılamıyorsa otomatik `./logs` | Hayır |
| `SUPABASE_STORE_PREFIX` | `formation-bot:` — `bot_store` tablosundaki anahtar ön eki (aynı tabloyu paylaşan ikinci örnekle çakışmayı önler; `off` = eski öneksiz davranış) | Hayır |
| `RENDER_EXTERNAL_URL` | Render **otomatik** verir (`https://<servis>.onrender.com`); elle eklemeyin | Hayır |

Bildirim akışı: teyitli kırılım, başarılı retest, tamamlanma ve başarısız kırılım
anında gönderilir. Sıkışma/hazırlık/adayı/retest bekleme durumları slot başına
bellekte güncellenir ve 18:45 DM kapanış özetinde en yüksek kalite puanlı en fazla
12 aday olarak yer alır. Kuyruk `DATA_DIR` içinde tutulur; dosya korunursa
restart'ta geri yüklenebilir ve 18:45 kaçırıldıysa telafi denenir. Geçici disk
silinirse bu durum ve engellenmiş acil alarm kuyruğu da kaybolabilir; Supabase'e
yeni yedek yazılmaz. 20:00 tam evren raporu ayrı kalır.

### 6.1 Haftalık doğruluk karnesi (canlıda nasıl çalışır)

* Karne **her Cuma** gün sonu mesajının altında gelir (18:45 `📋 Günlük Özet`;
  gönderim kaçarsa 20:00 `🌙 GÜN SONU ANALİZİ` altında). Haftada bir kez gider.
* Anında görmek için Telegram'dan `/karne` (bu hafta) veya `/karne 30` (son 30 gün).
* Sinyal defteri **yerel dosyadadır**: `DATA_DIR/karne_defteri.json`. **Supabase
  kurmak zorunlu değildir**; Supabase yoksa karne yine tam çalışır.
* Render Free'de varsayılan `DATA_DIR=/tmp/formation-bot-data` geçicidir.
  Eski `state:karne_defteri` uzaktan okunabilir ama mevcut salt okunur modda yeni
  kayıt oraya yazılmaz; disk kaybolursa yeni yerel karne de kaybolabilir.
  Koruma gerekiyorsa uygun kalıcı disk ve `DATA_DIR` yapılandırın.
* Karne içeriği: formasyon sayısı + zaman dilimi dağılımı, hisse listesi (adet),
  kırılım sayısı (yukarı/aşağı), "N bar içinde hedef / nötr / stop", kırılım
  yönünde kapatan oranı, ortalama lehte/aleyhte hareket, TF ve kalite performansı,
  en iyi/en kötü sinyaller ve huni (`kırılım → retest → tamamlanan/başarısız`).
* Mesaj sınırı: karne özetle birlikte 3900 karakteri aşarsa **ayrı mesaj** olarak
  gönderilir (kesilmez).

### 6.2 Alarm kareleri (isteğe bağlı; kapalıyken hiçbir şey değişmez)

`TELEGRAM_GRAFIK=alarm` iken her alarmın METNİNDEN SONRA, tarama turunun sonunda
hissenin mum karesi gider (1 olay = 1 metin + kareler; görseller mesaj kotasını
yemez, grup/kanala hiç görsel gitmez). Kare kartla AYNI veriyi çizer: formasyon bandı + temaslar, OB/FVG kutuları
(doluluk %'siyle), BOS/CHoCH + `kritik` seviyesi, `rvol` şeridi ve kartın yapı satırı
(`4s yapı: …` — kelimeleri mesajdaki satırla birebir aynı, §27).

Kurulum sonrası tek komutla duman (çizim çevrimdışıdır; fotoğraf da göndermek için
`--send-test-message` ekleyin):

```bash
python deploy_check.py --grafik-test                     # sadece üret: boyut/süre
python deploy_check.py --grafik-test --send-test-message # sendPhoto'yu da dener
```

Beklenen satırlar: `Grafik katmanı import edildi (matplotlib 3.11.x)`,
`Kare üretildi: AKBNK 4h · 120 mum · ~72 KB · ~450 ms`, ardından
`Fotoğraf gönderilmedi` / `sendPhoto kabul edildi`. `veri yok` uyarısı İLK
tarama öncesi normaldir (kare yalnız önbelleği okur, canlı çekmez).

Ölçülen maliyet (`python grafik_uret.py --hisse AKBNK --tum-tf --zone`, gerçek önbellek
+ gerçek motorlar, 2026-10-14): kare **başına 134-568 ms** ve 52-78 KB → **4 kare ≈
1,3 sn**; süreç tepesi 129 MB (çizim sırasında +52 MB). Render Free 512 MB için
kabul edilebilir, ama aynı turda 10 alarm varsa tura ~13 sn ekler; gerekirse
`TELEGRAM_GRAFIK_ADET=1`. Kare üretilemezse alarm DÜŞMEZ. Şalter açıkken
`/durum`, sıfırlar dâhil `🖼 Grafik karesi` satırını; gönderim, köprü ve karesiz
sayaçlarını ayrı ayrı gösterir. Build: matplotlib 3.11.2'nin cp312 manylinux
tekerleği VAR (kaynak derleme yok; `pip download --python-version 312 --only-binary=:all:`
ile doğrulandı) —
§1'deki "wheel yoksa build patlar" tuzağına girmez. `TELEGRAM_GRAFIK=yok` iken
`matplotlib` HİÇ import edilmez (taze süreçte ölçüldü).

#### Görsel gitmiyorsa

1. Render → **Shell**: `python deploy_check.py --grafik-test` ile çizim bağımlılığını ve
   yerel kare üretimini doğrula (bu adım Telegram'a fotoğraf göndermez).
2. Gerekirse `TELEGRAM_GRAFIK=alarm` yap; Render env değişikliği sonrası servisi
   **restart et**. Yeni env anahtarı gerekmez.
3. Kayıtlı DM'de `/grafik SEM 4s` çalıştır: bu komut otomatik alarm şalterinden
   bağımsızdır ve doğrudan `sendPhoto` yolunu sınar.
4. Aynı DM'de `/durum` aç: `alarm kartı`, `karesiz`, `köprü hatası` ve son neden
   sayaçlarını; kapalı şalter uyarısını ve gönderim hatalarını kontrol et.

Değişken ekleyip/ düzenleyince Render servisi otomatik yeniden başlatır
(redeploy). Loglarını **Logs → Live logs** veya **Events** sekmesinden izle.

---

## 7. Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| Build `metadata-generation-failed` | Python 3.14 seçilmiş. `.python-version` push edildi mi? Branch'i kontrol et (Render hangi branch'i deploy ediyor?) |
| `numpy/meson` derleme hatası | Aynı sorun; `.python-version` = 3.12 çözüm |
| `/health` 404 veriyor | Start Command `python main.py` değil. Logda `PORT ... başladı` satırını ara |
| `/health?ka=...` 404 veriyordu | Düzeltildi: uç artık sorgu dizesini ve sondaki slash'ı yok sayar. Eski sürümde keep-alive pingi 404 alıp "servis ölü" sanılıyordu |
| Merge ettim ama `/health`'teki `commit` değişmedi | Otomatik deploy tetiklenmemiş: Auto-Deploy'u aç (§2.1) veya `RENDER_DEPLOY_HOOK` secret'ı ekleyip **Actions → Render deploy → Run workflow**. Alternatif: Dashboard → Manual Deploy → Deploy latest commit |
| Merge ettim ama davranış değişmedi | Render yeni commit'i deploy etmemiş olabilir: `deploy_check.py` canlı sürümü (`/health` içindeki `commit`) yerel HEAD ile karşılaştırır. Dashboard → Events → yoksa **Manual Deploy → Deploy latest commit**; Auto-Deploy'un açık olduğundan emin ol (B8) |
| Sayfa "Render is loading..." | Free instance uyuyor, ~1 dk sonra düzelir (keep-alive kurulmadıysa) |
| Telegram mesajleri gelmiyor | Logda `Telegram bağlantısı OK` yok → token/chat_id hatalı; bot'a `/start` atılmamış olabilir |
| Bot komutlara cevap vermiyor | Önce `/health` içindeki `komut` alanına bak: `mod`, `dinleyici_canli`, `yetkisiz_sohbet`, `bayat_atlanan`, `son_komut_sn_once`. Sonra `python deploy_check.py --url https://<servis>.onrender.com` → webhook kaydı/teslim hatası/bekleyen güncelleme. Logda `Telegram komut dinleyicisi başladı` (yoklama) ya da `Telegram komutları WEBHOOK modunda` var mı? `HTTP 409` varsa aynı token'ı başka bir kopya (Termux/PC) dinliyor → onu kapatın |
| DM'den komut yazıyorum, hiç cevap yok (gece/hafta sonu) | Servis uyuyor (Render Free 15 dk). Telegram mesajı servisi uyandırmaz. Keep-alive'ı dış monitörle güçlendir (§5 Seçenek B) veya webhook moduna geç (§4.6); ölçüm: `gh run list --workflow keepalive.yml --limit 20` — günde 288 değil 4-6 koşu görürsen GitHub cron'u beklediğin gibi çalışmıyor |
| Komut yanıtı "Bot uyanık değildi…" diyor | Komut 15 dakikadan eski teslim edilmiş (servis o sırada uyuyordu). Durum değiştiren komutlar geç çalıştırılmaz; güncel sonuç için yeniden gönderin. `/yardim`,`/durum` gibi okuma komutları gecikme notuyla yanıtlanır |
| Webhook adresi 404 döndürüyor | `TELEGRAM_WEBHOOK_SECRET` tanımlı değil (ya da deploy edilmedi). §4.6 |
| `/test` 429 döndürüyor | Dakikalık istek limiti aşıldı (`HEALTH_RATE_LIMIT_PER_MIN`); bir dakika bekleyin |
| Webhook adresi 403 döndürüyor | `X-Telegram-Bot-Api-Secret-Token` başlığı eksik/yanlış (sırsız yolda zorunlu). Eski `<secret>` yolunda adresteki secret Render'daki değerle birebir aynı olmalı |
| Webhook adresi 503 döndürüyor | Normal: servis uyanıyor ya da bot komutları henüz kurmadı; Telegram tekrar dener |
| `getWebhookInfo` `last_error_message` dolu | Adres yanlış/erişilemez ya da HTTPS değil. `TELEGRAM_WEBHOOK_URL`'i temizleyip `RENDER_EXTERNAL_URL` ile otomatik üretime dönün (§4.6) |
| Webhook açtım, komutlar bir süre sonra durdu | Render Free uykuya geçmiş olabilir. Telegram başarısız teslimatı bir süre tekrar dener; keep-alive penceresini genişletin (`KEEPALIVE_ALWAYS=true`, §5) |
| `/tara` sonucu eski görünüyor | Seans dışı veri canlı olmayabilir; rapordaki en yeni cache timestamp'ini/veri yaşını kontrol edin (tamamlanmışlık provider sözleşmesine bağlıdır) |
| `/panel` boş geliyor | Üstteki tarama durumunu kontrol et: “henüz başarılı analiz yok”, “eksik/başarısız” ve “başarılı ama aday yok” birbirinden ayrıdır. `/panel` yeni tam evren analizi başlatır |
| Komut cevabı 1 dk gecikiyor | Servis uyuyorsa ilk istek onu uyandırır (~1 dk); keep-alive penceresi bunu seans içinde engeller |
| Supabase bağlantısı yok | Zorunlu değildir; bot Yahoo verisi ve yerel cache ile analiz yapar. Supabase yalnızca opsiyonel OHLCV cache/geçmiş kaydıdır |
| Tarama çok yavaş | Free instance 0.1 CPU. Varsayılan tarama 57 sembol × 4 zaman dilimi; ilk yükleme birkaç dakika sürebilir, sonraki turlar mum başına bir tarama yapılır |
| `MemoryError` / restart döngüsü | Free instance 512 MB. `BOT_PROFILE=Seçici` ile evreni daraltmak gerekebilir |
| Actions'ta "Render keep-alive" koşusu **sarı** ve logda `RENDER_HEALTH_URL tanımlı değil` | Secret/Variable hiç eklenmemiş (bkz. §C). Bu bir hata değil uyarıdır; ekleyince yeşile döner |
| Actions "Render keep-alive" hiç görünmüyor | İş akışı `main`'e merge edilmemiş (schedule sadece varsayılan branch'te çalışır) |
| Keep-alive bir süre çalıştı, sonra durdu | Public repoda 60 gün aktivite olmaması (bkz. §5). Actions sekmesinden **Enable workflow** |
| Koşular 5 dk yerine 20+ dk aralıkla geliyor | GitHub cron'u gecikebilir; pencere dışıysa normal. Sık oluyorsa Seçenek B'yi kur |
| `deploy_check.py` "Supabase'e ulaşılamadı" | Ağ/proxy engeli ya da URL yanlış; `--skip-network` ile dosya tarafını yine kontrol edebilirsin |

---

## 8. GitHub Actions ile otomatik kontrol (CI)

Render'a giden kod, deploy'dan **önce** GitHub tarafında sınanır:
`.github/workflows/ci.yml` her `main` push'unda ve pull request'te şunları koşar.

1. **Python sürümü**: `actions/setup-python` ile repodaki `.python-version`
   (3.12) okunur — yani Render'ın göreceği sürümün aynısı.
2. **Kurulum**: `pip install -r requirements.txt` (Render Build Command'in
   birebir aynısı). Tekerlek bulunamazsa, yani Render'ı patlatacak durum
   (cp314 senaryosu) oluşursa burada kırmızı olur — deploy'u hiç denemezsin.
3. **Testler**: `python -m pytest -q` + `python test_tarama_zamani.py`
   (zamanlama ve ölü formasyon regresyonu, 90 kontrol).
4. **Render duman testi**: `PORT=10000 python main.py` arka planda başlatılır,
   `/health` 200 ve `{"status":"ok"}` dönene kadar beklenir; `TELEGRAM_TEST_KEY`
   tanımsızken `/test` ucunun **404** döndüğü (yani Telegram'a istek gitmediği)
   doğrulanır. `BOT_HEALTH_SMOKE_ONLY=1` ana döngüyü ve dış servisleri kapatır:
   bu kontrol gerçek Render başlangıcının, veri ve Telegram tesliminin tamamını
   doğrulamaz.

Kırmızı bir koşu görürsen: Actions → koşu → adım adım log. En sık iki sebep
sürüm uyumsuzluğu (adım 2) ve bir testin gerçekten bozulması (adım 3).

> CI başarısı gerçek deploy'un başladığını veya tamamlandığını göstermez.
> Render Dashboard olaylarını ve canlı `/health` commit'ini ayrıca doğrulayın;
> başlangıç süresi veri yüküne ve servis koşullarına bağlıdır.
