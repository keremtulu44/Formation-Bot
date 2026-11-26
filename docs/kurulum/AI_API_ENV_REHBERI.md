# AI API, KAP ve Gölge Kayıt Ortam Değişkenleri Rehberi

Bu dosya, gizli anahtarları **sonradan dolduracağınız** zaman hiçbir değişken adını unutmamanız için kalıcı başvuru listesidir. Gerçek anahtarlar/URL'ler repoya yazılmaz; **Render Dashboard → Service → Environment** (veya yerel `.env`) bölümüne eklenir.

---

## 1. Doldurmanız Gereken Gizli Anahtarlar (Render → Environment)

Aşağıdaki 4–5 alanı eklemeniz yeterlidir; tüm çalışma şalterleri kodda ve `render.yaml` içinde **varsayılan olarak AÇIK (`1`)** gelir:

```env
# 1) Birincil sağlayıcı: ApiWrapper (yalnızca POST {BASE_URL}/v1/ask çağrılır)
AI_WRAPPER_BASE_URL=https://...
AI_WRAPPER_API_KEY=...
# İsteğe bağlı; boş bırakılırsa ApiWrapper kendi varsayılan modelini kullanır
AI_WRAPPER_MODEL=

# 2) Yedek #1: Ücretsiz Gemini API anahtarı (x-goog-api-key başlığıyla gider)
GEMINI_API_KEY_1=...
GEMINI_MODEL_1=gemini-2.5-flash

# 3) Yedek #2: İkinci ücretsiz Gemini API anahtarı
GEMINI_API_KEY_2=...
GEMINI_MODEL_2=gemini-2.5-flash
```

> **Not:** Değerleri yanlışlıkla tırnak içinde (`"..."`) yapıştırsanız bile istemci katmanı tırnak ve boşlukları otomatik temizler. `AI_WRAPPER_BASE_URL` sonuna `/v1/ask` yazsanız da yazmasanız da otomatik tek `/v1/ask` olarak normalize edilir.

---

## 2. Zaten Varsayılan AÇIK Olan Çalışma Şalterleri (Değiştirmek İsterseniz)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `AI_YORUM_AKTIF` | `1` | Ana şalter: canlı alarmlarda düz kart yerine AI yorumu gönderir. Sağlayıcı anahtarı yoksa veya 3 sağlayıcı da düşerse otomatik düz kart gider. |
| `AI_YORUM_DM` | `1` | DM alarmlarında AI yorumu (`0` yaparsanız yalnız DM düz karta döner). |
| `AI_YORUM_PUBLIC` | `1` | Public grup/kanal alarmlarında AI yorumu (`0` yaparsanız yalnız Public düz karta döner). |
| `AI_YORUM_MAX_BEKLEME_SN` | `0` | `0` = ApiWrapper'da toplam süre sınırı yok (yalnız `10s` bağlanma + `45s` sessizlik zaman aşımı). İsteğe bağlı üst sınır koymak için örn. `240` yazılabilir. |
| `AI_SHADOW_LOG` | `1` | AI yanıtının sonundaki gizli `[AI_SONUC ...]` 5-filtre bloğunu yerel `DATA_DIR/ai_yorum_test.json` dosyasına ve `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` varsa doğrudan Supabase `public.ai_yorum_test` tablosuna kaydeder. Telegram mesajından gizli blok kesinlikle ayıklanır. |
| `KAP_BAGLAM_AKTIF` | `1` | Arka plan KAP SQLite WAL toplayıcısını çalıştırır; alarm anında yalnızca alarmdan ÖNCE yayımlanmış taze bildirimleri AI promptuna ekler. |
| `KAP_WARMUP_ACILISTA` | `1` | Render Free geçici diskte restart sonrası boş KAP arşivini son 7 günle hızlıca doldurur. |
| `KAP_TARAMA_ARALIK_SN` | `180` | KAP arka plan tarama aralığı (saniye). |
| `KAP_MAX_YAS_GUN` | `7` | Alarm bağlamına alınacak azami KAP bildirim yaşı (gün). |
| `KAP_ARSIV_YOLU` | *(boş)* | Boş = `DATA_DIR/kap_arsiv.sqlite`. |

---

## 3. Çalışma Sırası (Canlı Akış)

1. Alarm tetiklenir (Klasik Formasyon, Stabil 4s Geri Alım veya Yeni Domain).
2. Bot kapanmış 1s/2s/4s/1g mumlarını ve yerel KAP SQLite WAL arşivini kullanarak promptu derler (`system` ve `prompt` ayrı gönderilir).
3. Sırayla dener:
   1. **`ApiWrapper`** (`POST {AI_WRAPPER_BASE_URL}/v1/ask`, SSE `wait` → `done`; `problem` / 45 sn sessizlik / HTTP != 200 / kopma / bozuk JSON gelirse **tekrar denemeden** hemen yedeğe geçer; bir sonraki soruda yeniden önce ApiWrapper'ı dener).
   2. **`Ücretsiz Gemini #1`** (`GEMINI_API_KEY_1`)
   3. **`Ücretsiz Gemini #2`** (`GEMINI_API_KEY_2`)
   4. **Düz teknik kart yedeği** (hiçbir alarm kaybolmaz).
4. AI yanıtı 3 başlıklı yapı doğrulamasından geçerse gizli `[AI_SONUC ...]` bloğu ayıklanıp gölge tabloya (`ai_yorum_test`) yazılır; temiz görünür yorum hem DM hem Public kanala ana alarm mesajı olarak gider.

---

## 4. Anahtarları Ekledikten Sonra 3 Hızlı Kontrol

1. **Kurulum doktoru (yerel / Render Shell):**
   ```bash
   python deploy_check.py --skip-network
   ```
   `AI alarm zinciri hazır: ApiWrapper -> Gemini#1 -> Gemini#2 -> düz kart` satırını görmelisiniz.
2. **Canlı sağlık ucu (`GET /health`):**
   `ai_istemci.hazir: true`, `ai_istemci.saglayicilar: ["api_wrapper", "gemini_free_1", "gemini_free_2"]` ve `kap_baglam.aktif: true` görünür (hiçbir gizli değer dönmez).
3. **Telefondan canlı DM testi:**
   Botun özel DM'sine `/ai BIMAS 4s` yazın. Sağlayıcı adı, süre, görünür 3 başlıklı yorum ve 5-filtre özetini doğrudan Telegram DM'de görürsünüz.
