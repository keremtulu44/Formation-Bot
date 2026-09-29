# Render + Supabase + Telegram Dağıtım Rehberi

Bu dosya, botu **Render Free** üzerinde çalıştırmak için gereken her şeyi tek
yerde toplar: build hatasının kök nedeni, Supabase anahtar biçimi, Telegram
token'ın telefondan alınması ve servisi ayakta tutma (keep-alive) yöntemi.

---

# ⚡ TEK SAYFA KONTROL LİSTESİ

`__` = boş yer. Her satırda **soldaki yere kendi değerini yaz**, sağdaki yere
o değeri yapıştır. Üç ayrı yere yazılacak toplam **7 zorunlu değer** var
(6 Render değişkeni + 1 GitHub secret'ı; `TELEGRAM_TEST_KEY` ve
`TELEGRAM_WEBHOOK_SECRET` opsiyoneldir).

> **Takıldığın yeri tek komutla bul:** `python deploy_check.py --url
> https://<servis-adin>.onrender.com` → hangi halka kopuk (Render mı, Supabase
> mi, Telegram mı) doğrudan söyler. Aşağıdaki A–D listesi o çıktıyı düzeltmek
> için var. Ayrıntı: **§D3**.

## A) Render → Environment (6 değişken)

Render Dashboard → servisin → **Environment** → **Add**. Sağdaki "Secret" sütununu
`TELEGRAM_*` ve `SUPABASE_SERVICE_ROLE_KEY` için **aç**, `SUPABASE_URL` ve
`BOT_PROFILE` için açma.

| # | Key (yazılacak isim) | Value (yapıştırılacak) | Secret? |
|---|---|---|---|
| 1 | `SUPABASE_URL` | `https://pzbuqlvehiokeondvrdq.supabase.co` | hayır |
| 2 | `SUPABASE_SERVICE_ROLE_KEY` | `__` ← Supabase → Settings → API → **service_role** (`eyJ...` ile başlayan uzun metin) | **evet** |
| 3 | `TELEGRAM_BOT_TOKEN` | `__` ← **@BotFather** → `/newbot` → "Use this token" satırındaki kod | **evet** |
| 4 | `TELEGRAM_CHAT_ID` | `__` ← **@userinfobot** → Start → verdiği `Id:` sayısı | **evet** |
| 5 | `BOT_PROFILE` | `Dengeli` | hayır |
| 6 | `TELEGRAM_TEST_KEY` | `__` ← istediğin rastgele bir yazı (örn. `k7m2x9`) | **evet** |
| 7 | `TELEGRAM_WEBHOOK_SECRET` | `__` ← **OPSİYONEL**: rastgele bir yazı (`python3 -c "import secrets; print(secrets.token_urlsafe(24))"`). Doldurursan Telegram komutları webhook ile gelir; boş bırakırsan bot `getUpdates` yoklamasını kullanır (bkz. **§4.6**) | **evet** |

> #2'nin değeri: `eyJhbGciOi...` diye başlayan **çok uzun** bir metin. Kısaltma,
> ortadan kesme — satır sonuna kadar tamamını yapıştır.
> #3'ün değeri: `8914822495:AAG...` biçiminde, iki nokta içeren tek satır.
> #7'nin adresi (webhook için) `RENDER_EXTERNAL_URL`'den otomatik üretilir:
> `https://<servis>.onrender.com/webhook/<secret>`. `RENDER_EXTERNAL_URL`'i elle
> **ekleme gerekmez**, Render Web Service'lerde otomatik tanımlıdır.

Boş bırakırsan bot çalışır ama: #2 boşsa önbellek/Telegram state'i kaydedilmez,
#3/#4 boşsa **hiç Telegram mesajı gelmez**. #7 boşsa komutlar yoklama ile çalışır
(işlevsel fark yok, yalnızca taşıma yolu değişir).

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
| B8 | Auto-Deploy | `Yes` (yoksa her merge'de elle "Manual Deploy" bas) |
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
`secrets.RENDER_HEALTH_URL` → `vars.RENDER_HEALTH_URL`. Hiçbiri yoksa iş
akışı kırmızı olmak yerine sarı `warning` verir ve atlar (Actions sekmesinde
görünür), yani sessizce kaybolmaz.

### C2) Secret oluşturmadan hemen denemek (telefondan yapılabilir)

GitHub → **Actions** → sol taraftan **Render keep-alive** → **Run workflow** →
`health_url` alanına `https://<servis-adin>.onrender.com/health` yaz → **Run**.
Elle tetikleme saat penceresini yok sayar ve 10 saniye içinde sonucu gösterir;
secret'ı sonra eklemen gerekir.

## C2) (Önerilir) Otomatik deploy için Deploy Hook

Render → servis → **Settings → Deploy Hook → Create deploy hook** → URL'i
GitHub'a secret olarak ekle: `RENDER_DEPLOY_HOOK`. Böylece her merge otomatik
deploy olur; Auto-Deploy kapalıysa bile kod canlıya iner. Ayrıntı: **§2.1**.

## D) Yapılacak son iki iş

- [ ] Repodaki değişiklikler (`main` branch'i) Render'ın deploy ettiği branch'e
      **merge** edilsin — yoksa Python 3.12 sabiti ve keep-alive çalışmaz.
- [ ] Supabase → SQL Editor → `supabase_schema.sql` içeriğini yapıştır → **Run**

## D2) Merge sonrası sırayla doğrula

1. Render → **Events**: yeşil **"Deploy succeeded"** ✅ (kırmızıysa logun
   son 20 satırına bak)
2. `https://<servis>.onrender.com/health` → `{"status":"ok"}`
3. Render → **Logs** → 3 satır:
   `Supabase bağlantısı OK` · `Telegram bağlantısı OK` · `health endpoint ... başladı`
4. `https://<servis>.onrender.com/test?k=<TELEGRAM_TEST_KEY>` → `{"ok":true}`
   ve Telegram'da test mesajı düşer
5. GitHub → **Actions** → "Render keep-alive" yeşil koşular (5 dk'da bir,
   yalnızca İstanbul saatiyle 09:30–18:50 arasında)

### D3) Tek komutla hepsini kontrol et: `deploy_check.py`

Dört adımı elle gezmek yerine (telefondan Termux'ta da çalışır):

```bash
python deploy_check.py --url https://<servis-adin>.onrender.com
python deploy_check.py --url https://<servis-adin>.onrender.com --test-key <TELEGRAM_TEST_KEY>
python deploy_check.py --env-file .env --send-test-message   # Supabase + Telegram
```

Her satır ya ✅ ya ⚠️ ya ❌ ile biter ve ❌ satırının altında **ne yapılacağı**
yazar (örn. "Supabase → SQL Editor → supabase_schema.sql"). Çıkış kodu 0 ise
kritik hata yok. Token/anahtar değerleri hiçbir zaman ekrana basılmaz.

## E) Doğrulama (loglarda arayacağın 3 satır)

```
Supabase bağlantısı OK (https://pzbuqlvehiokeondvrdq.supabase.co, tablo: bot_store)
Telegram bağlantısı OK (bot: @__ , chat_id: __)
Render health endpoint 0.0.0.0:____ üzerinde başladı (/health)
```

Webhook modunu açtıysanız (§4.6) 4. satır da gelir:

```
Telegram webhook ucu etkin (POST /webhook/<secret>, secret gizli)
Telegram webhook kuruldu: https://<servis>.onrender.com/webhook/*** (Webhook was set)
Telegram komutları WEBHOOK modunda: https://<servis>.onrender.com/webhook/*** (yalnızca chat_id __)
```

Webhook kapalıysa bunun yerine `Telegram webhook ucu kapali
(TELEGRAM_WEBHOOK_SECRET tanimli degil)` ve yoklama satırı görünür — ikisi aynı
anda asla açık olmaz.

Bu üçü varsa her şey yerindedir. Tarayıcıda
`https://<render-adresin>.onrender.com/health` açınca `{"status":"ok"}` görünür.

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

### 2.1 Otomatik deploy: Auto-Deploy ve Deploy Hook

İki yol var; **ikisinden biri mutlaka açık olmalı**, yoksa merge edilen kod
canlıya hiç düşmez ve bunu ancak `/health`'teki commit bilgisinden anlarsın.

| Yol | Kurulum | Not |
|---|---|---|
| Render Auto-Deploy | Dashboard → servis → Settings → **Auto-Deploy: Yes** | En basit; her `main` push'unda Render kendisi deploy eder |
| **Deploy Hook + GitHub Actions** | Aşağıdaki 3 adım | Auto-Deploy kapalıysa/bağlantı koptuysa kurtarıcı; deploy'u GitHub tetikler ve Actions'ta görünür |

Repo içindeki `.github/workflows/deploy.yml` hazırdır:

1. Render → servisin → **Settings → Deploy Hook → Create deploy hook** → URL'i kopyala
   (biçim: `https://api.render.com/deploy/srv-xxxxxxxx?key=yyyyyyyy`)
2. GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**
   → ad: `RENDER_DEPLOY_HOOK`, değer: kopyaladığın URL
3. Bundan sonra `main`'e her push'ta deploy otomatik tetiklenir.

Secret yoksa iş akışı kırmızı olmaz; “atlandı” uyarısı verir ve yapılacakları
Actions özetine yazar. Elle denemek için: **Actions → Render deploy → Run
workflow** (hook URL'ini girdi olarak da verebilirsin).

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

### 4.4 Mesaj gonderimini test etme (bir tikla)

`getMe` sadece **token'i** dogrular; asil soru "alarm mesajlari bana ulasacak mi?"
bunu `TELEGRAM_TEST_KEY` ile acilan `/test` ucu cevaplar. Render → Environment'a
istedigin rastgele bir yazi ekle (orn. `k7m2x9`), sonra telefondan tarayicida ac:

```
https://<servis-adin>.onrender.com/test?k=k7m2x9
```

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
webhook (§4.6) ile toplanır; **yalnızca `TELEGRAM_CHAT_ID`** komut verebilir,
başka sohbetlerden gelen mesajlar sessizce yok sayılır.

| Komut | Ne yapar |
|---|---|
| `/formasyonlar` | Günün canlı formasyonları (hisse, TF, tip, kalite, state, üst/alt seviye) |
| `/formasyonlar 1h` | Zaman dilimi filtresi (`1h`, `2h`, `4h`, `1d`) |
| `/formasyonlar THYAO` | Hisse veya formasyon adı filtresi |
| `/canli` veya `/c` | Canlı formasyonlar **tek kompakt mesajda** (kalabalık günde hızlı bakış) |
| `/panel` veya `/p` | **48 hisse x 4 zaman dilimi slot tablosu** + sayılar + **en kritik 12 kayıt**. Diğer adlar: `/genel`, `/tablo` |
| `/panel 1h` | Panel filtresi: yalnızca o TF kolonu (çoklu TF de verilebilir: `/panel 1h 4h`) |
| `/panel THYAO` | Panel filtresi: yalnızca o hisse(ler) satırı (kısmi ad yeter: `/panel thy`) |
| `/panel kirilim` | Panel filtresi: state/desen adı (`kirilim`, `retest`, `üçgen`, `KIRILIM_TEYITLI` ...) |
| `/panel 1h THYAO` | Filtreler birlikte de kullanılabilir |
| `/ozet` veya `/o` | Günlük özet tek mesajda (tamamlanan/retest/sıkışan sayıları) |
| `/sikisanlar` · `/tamamlanan` · `/retest` · `/kirilim` | Kısa listeler (kısayollar: `/s`, `/t`, `/r`, `/k`) |
| `/durum` | Profil, piyasa açık/kapalı, son tarama yaşı, canlı sayı, veri sağlığı, günlük alarm/hata sayacı |
| `/tara` | Şimdi tara (mum kapanışını beklemez). **Yalnızca seans içinde çalışır**; kapalıyken nazikçe reddeder |
| `/yardim`, `/start` | Komut listesi |

Panel nasıl okunur (tek satır = bir hisse, hücreler `TF kalite` + işaret):

```
THYAO 1h 87🚀 · 2h — · 4h 75⚡ · 1d —
        🚀 kırılım   🎯 retest   🏁 tamamlandı   ⚡ sıkışma   — boş slot
```

Akış: `/tara` isteği bir bayrağa yazılır, ana döngünün 5 dakikalık uykusu
kesilir ve tarama normal akışla (aynı pacing, aynı kalite eşikleri, aynı
Supabase kaydı) başlar; bitince `/formasyonlar` güncel listeyi gösterir.

> ⚠️ **Tek tüketici kuralı:** Telegram aynı token için **iki süreç** aynı anda
> `getUpdates` yaparsa ikincisi `409 Conflict` alır. Termux/PC'de açık kalmış
> ikinci bir kopya varsa **kapatın**; bot bunu logda net söyler ve dinleyiciyi
> durdurur (alarmlar çalışmaya devam eder). Render `/test` ucu yalnızca
> `sendMessage` kullanır, bu kuraldan etkilenmez.

Komut listesi `.env` değişkeni gerektirmez; token/chat_id doğruysa otomatik
açılır. Token/chat_id yoksa bot eskisi gibi yalnızca alarm gönderir.

Gönderim tarafını yine 4.4'teki `/test` ucuyla doğrula. Gerçek alarm akışı ise
bir formasyon tetiklendiğinde devreye girer: 48 hisse × 4 zaman dilimi
tarandığı için ilk alarm birkaç gün sürebilir — bu arada `/formasyonlar` ya da
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
https://formation-bot.onrender.com/webhook/<TELEGRAM_WEBHOOK_SECRET>
```

Bot açılışta `setWebhook` çağırır, Telegram'a `secret_token` olarak da bildirir
ve **yoklamayı kapatır** (aynı token'da `getUpdates` + webhook birlikte olmaz;
ikisi birlikte 409 Conflict üretir). Secret'i silip yeniden deploy ederseniz bot
`deleteWebhook` çağırır ve yoklamaya döner — mod geçişi otomatik ve tek yönlüdür.

Doğrulama (telefondan tarayıcıyla da yapılabilir):

| Adres / komut | Beklenen |
|---|---|
| `https://<servis>.onrender.com/webhook/<secret>` (GET, tarayıcı) | `{"ok": true, "webhook": "hazir", "bot_hazir": true, ...}` |
| `https://api.telegram.org/bot<token>/getWebhookInfo` | `"url"` sizin adres, `"pending_update_count"` düşük, `last_error_message` yok |
| Render → Logs | `Telegram webhook kuruldu: https://.../webhook/***` ve `Telegram komutları WEBHOOK modunda` |

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
> - Sır loglara **yazılmaz**; logda `.../webhook/***` görünür.
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

### Seçenek A — GitHub Actions (public repoda ücretsiz, önerilen) ✅

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

### Seçenek B — cron-job.org / UptimeRobot (ücretsiz, daha basit)

`https://cron-job.org` veya UptimeRobot'a üye ol, `https://<servis>.onrender.com/health`
adresini **her 5 dakikada bir** GET ile çağrılan monitör olarak tanımla
(gün/gece ayrımı yapmıyorsa da çalışır, sadece 750 saat kotasını daha hızlı
tüketir). Repo aktivitesi, Actions kotası veya 60 gün kuralıyla hiç işi yoktur;
GitHub tarafı tamamen kopsa bile çalışır. İkisini birlikte kurmak en sağlamıdır.

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
| `TELEGRAM_CHANNEL_ID` | Public kanal ID'si `-100...` (botu kanala admin ekle) | Evet |
| `SUPABASE_URL` | `https://<ref>.supabase.co` | Hayır (plain) |
| `SUPABASE_SERVICE_ROLE_KEY` | `sb_secret_...` veya `eyJ...` | Evet |
| `BOT_PROFILE` | `Dengeli` / `Hassas` / `Seçici` | Hayır |
| `SUMMARY_HOURS` | `09:55,18:15` (İstanbul, özet saatleri) | Hayır |
| `PUBLIC_MIN_QUALITY` | `80` (public kanala min kalite) | Hayır |
| `LOG_LEVEL` | `INFO` (varsayılan) | Hayır |
| `TELEGRAM_TEST_KEY` | `/test?k=<değer>` için anahtar (bkz. §4.4) | Evet |
| `TELEGRAM_WEBHOOK_SECRET` | Rastgele metin; doluysa komutlar webhook ile gelir (bkz. §4.6). Boş = yoklama | Evet |
| `TELEGRAM_WEBHOOK_URL` | (Opsiyonel) Tam webhook adresi; boşsa `RENDER_EXTERNAL_URL` + `/webhook/<secret>` | Evet |
| `RENDER_EXTERNAL_URL` | Render **otomatik** verir (`https://<servis>.onrender.com`); elle eklemeyin | Hayır |

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
| Bot komutlara cevap vermiyor | Logda `Telegram komut dinleyicisi başladı` (yoklama) ya da `Telegram komutları WEBHOOK modunda` var mı? `HTTP 409` varsa aynı token'ı başka bir kopya (Termux/PC) dinliyor → onu kapatın |
| Webhook adresi 404 döndürüyor | `TELEGRAM_WEBHOOK_SECRET` tanımlı değil (ya da deploy edilmedi). §4.6 |
| Webhook adresi 403 döndürüyor | Adresteki secret yanlış; Render'daki değerle birebir aynı olmalı (boşluk/kesme yok) |
| Webhook adresi 503 döndürüyor | Normal: servis uyanıyor ya da bot komutları henüz kurmadı; Telegram tekrar dener |
| `getWebhookInfo` `last_error_message` dolu | Adres yanlış/erişilemez ya da HTTPS değil. `TELEGRAM_WEBHOOK_URL`'i temizleyip `RENDER_EXTERNAL_URL` ile otomatik üretime dönün (§4.6) |
| Webhook açtım, komutlar bir süre sonra durdu | Render Free uykuya geçmiş olabilir. Telegram başarısız teslimatı bir süre tekrar dener; keep-alive penceresini genişletin (`KEEPALIVE_ALWAYS=true`, §5) |
| `/tara` "piyasa kapalı" diyor | Normal: elle tarama yalnızca seans içinde (İstanbul 09:50-18:40) çalışır |
| Komut cevabı 1 dk gecikiyor | Servis uyuyorsa ilk istek onu uyandırır (~1 dk); keep-alive penceresi bunu seans içinde engeller |
| `Supabase bağlantısı OK` yok | `supabase_schema.sql` çalıştırılmamış veya anahtar yanlış (yukarıdaki HTTP kodlarına bak) |
| Tarama çok yavaş | Free instance 0.1 CPU. Tarama 48 hisse × 4 zaman dilimi; ilk yükleme birkaç dakika sürebilir, sonraki turlar mum başına bir tarama yapılır |
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
   doğrulanır. Bu adım, Render'ın "Deploy failed / start command çıktı vermiyor"
   hatalarının hepsini önceden yakalar.

Kırmızı bir koşu görürsen: Actions → koşu → adım adım log. En sık iki sebep
sürüm uyumsuzluğu (adım 2) ve bir testin gerçekten bozulması (adım 3).

> Render Free'de her deploy ~1 dakika sürer ve yeni sürüm ayağa kalkana kadar
> eskisi çalışmaya devam eder. CI yeşilse deploy neredeyse her zaman yeşildir.
