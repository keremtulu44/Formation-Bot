# Render + Supabase + Telegram Dağıtım Rehberi

Bu dosya, botu **Render Free** üzerinde çalıştırmak için gereken her şeyi tek
yerde toplar: build hatasının kök nedeni, Supabase anahtar biçimi, Telegram
token'ın telefondan alınması ve servisi ayakta tutma (keep-alive) yöntemi.

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
`/health` endpoint'i açar. Bu endpoint sadece `{"status":"ok",...}` döner;
token, anahtar veya portföy verisi sızmaz. Servis canlıysa tarayıcıda
`https://<servis>.onrender.com/health` çalışıyor demektir.

> **Not:** Render Free disk kalıcı değildir. Her deploy/restart'ta `bot_data/`
> sıfırlanır. Bu yüzden önbellek ve Telegram cooldown state'i **Supabase**
> üzerinde tutulmalıdır (aşağıdaki bölüm). Repoda commit'lenmiş `bot_data/`
> dosyaları ilk açılışta botu hemen çalıştırmak için yeterlidir.

---

## 3. Supabase: URL public mi, anahtar secret mi?

Kısa cevap:

| Değişken | Ne girilir | Render'da nasıl işaretlenir |
|---|---|---|
| `SUPABASE_URL` | `https://<proje-ref>.supabase.co` | **Plain** (public, sır değil) |
| `SUPABASE_SERVICE_ROLE_KEY` | `sb_secret_...` **veya** eski `eyJ...` JWT | **Secret** |

**URL:** Supabase Dashboard → Project → **Settings → API → Project URL**.
Başında `https://` var, sonunda `/` yok. Bu bir sır değildir; tarayıcıdan da
görülebilen bir adrestir. Yine de "Secret" seçersen de çalışır, Render bunu
şifreleyip loglarda maskeler. Tavsiye: URL'yi **plain** bırak.

**Anahtar — `sb_secret_` formatı doğru mu? Evet, çalışır.** Supabase 2025'te
anahtar sistemini değiştirdi ve artık iki format bir arada geçerli:

| Format | Örnek başlangıç | Nerede |
|---|---|---|
| Yeni secret key | `sb_secret_...` | API Keys sayfasındaki **Secret** key |
| Eski service_role | `eyJhbGciOi...` (uzun JWT) | API → Service Role → `service_role` |

`supabase_store.py` anahtarı doğrudan `apikey` ve `Authorization: Bearer`
başlıklarında kullandığı için **her iki format da aynen çalışır**, aralarında
seçim yapmana gerek yok. `sb_secret_...` aldıysan doğrudan yapıştır.

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

   `7123456789:AA...` kısmının tamamı `TELEGRAM_BOT_TOKEN` olacak.

> Token'ı WhatsApp'a, README'ye, `.env`'i commit ederek ya da bu sohbete
> yapıştırma. Render'da **Secret** olarak gir. BotFather'da `/revoke` ile
> istediğin an iptal edebilirsin.

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

---

## 5. Servisi ayakta tutma (keep-alive)

Render Free bir web service'e **15 dakika inbound istek gelmezse** onu uyutur;
uyanması ~1 dakika sürer, o dakika boyunca tarama yapılmaz. Telegram'a 15
dakikada bir mesaj gelmesi de kendiliğinden koruma sağlamaz, çünkü mesaj
**outbound** bir istektir.

### Seçenek A — GitHub Actions (ücretsiz, önerilen) ✅

Repo içinde `.github/workflows/keepalive.yml` hazır. Her 10 dakikada bir
`/health` adresine istek atar (15 dakikalık eşiğe 5 dakika pay bırakarak).

Kurulum (tek seferlik, telefondan da yapılabilir):

1. GitHub → repo → **Settings → Secrets and variables → Actions**
2. **New repository secret** → ad: `RENDER_HEALTH_URL`,
   değer: `https://<servis-adin>.onrender.com/health`
3. Kaydet. İş akışı 10 dakika içinde yeşil "Render keep-alive" koşusu görünür.

GitHub Actions bu repo için **aylık 2000 dakika ücretsiz**; 10 dakikada bir
koşu ≈ 25 dakika/ay. Render'ın kendi Cron Job'u ise **ücretsiz değil**
(aylık en az 1 $) ve ayrıca çalışan bir web service'ı uyandırmaz.

### Seçenek B — cron-job.org / UptimeRobot (ücretsiz, daha basit)

`https://cron-job.org` veya UptimeRobot'a üye ol, `https://<servis>.onrender.com/health`
adresini **her 10 dakikada bir** GET ile çağrılan monitör olarak tanımla.
Kod değişikliği gerektirmez.

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

## 6. Ortam değişkenleri (Render → Environment)

| Anahtar | Değer | Secret? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather token'ı | Evet |
| `TELEGRAM_CHAT_ID` | Kendi Telegram id'n | Evet |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | Hayır (plain) |
| `SUPABASE_SERVICE_ROLE_KEY` | `sb_secret_...` veya `eyJ...` | Evet |
| `BOT_PROFILE` | `Dengeli` / `Hassas` / `Seçici` | Hayır |
| `LOG_LEVEL` | `INFO` (varsayılan) | Hayır |

Değişken ekleyip/ düzenleyince Render servisi otomatik yeniden başlatır
(redeploy). Loglarını **Logs → Live logs** veya **Events** sekmesinden izle.

---

## 7. Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| Build `metadata-generation-failed` | Python 3.14 seçilmiş. `.python-version` push edildi mi? Branch'i kontrol et (Render hangi branch'i deploy ediyor?) |
| `numpy/meson` derleme hatası | Aynı sorun; `.python-version` = 3.12 çözüm |
| `/health` 404 veriyor | Start Command `python main.py` değil. Logda `PORT ... başladı` satırını ara |
| Sayfa "Render is loading..." | Free instance uyuyor, ~1 dk sonra düzelir (keep-alive kurulmadıysa) |
| Telegram mesajleri gelmiyor | Logda `Telegram bağlantısı OK` yok → token/chat_id hatalı; bot'a `/start` atılmamış olabilir |
| `Supabase bağlantısı OK` yok | `supabase_schema.sql` çalıştırılmamış veya anahtar yanlış (yukarıdaki HTTP kodlarına bak) |
| Tarama çok yavaş | Free instance 0.1 CPU. Tarama 48 hisse × 4 zaman dilimi; ilk yükleme birkaç dakika sürebilir, sonraki turlar mum başına bir tarama yapılır |
| `MemoryError` / restart döngüsü | Free instance 512 MB. `BOT_PROFILE=Seçici` ile evreni daraltmak gerekebilir |
