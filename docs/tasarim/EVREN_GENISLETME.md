# Evren genişletmesi — endeksler ve makro semboller (22 Ekim 2026)

> **Karar (kullanıcı):** "endeksleri ekle — banka, xu30, xu50" · "normal farksız,
> hacim yoksa o bilinsin" · "public'e de gitsin" · "XU100'e göre göreli güç, bir
> de altın ve gümüş, USD".
> **Kod:** `config.py` (evren + sınıflar), `notification_context.py` (hacim
> nedeni), `main.py` (`_endekse_gore_guc`, `_alarm_izni_var`), `notifier.py`
> (göreli güç satırı, evren etiketi).

---

## 1. Araştırma — hangi semboller gerçekten var

Yahoo Finance üzerinde doğrulanan BIST endeksleri (hepsi `.IS` ekli, fiyat
geçmişi geliyor):

| Yahoo | Endeks | Evrende |
|---|---|---|
| `XU100.IS` | BIST 100 | vardı |
| `XU030.IS` | BIST 30 | vardı (`XU30`) |
| `XU050.IS` | BIST 50 | **eklendi** (`XU50`) |
| `XBANK.IS` | BIST Banka | **eklendi** |
| `XUSIN.IS` | BIST Sınai | **eklendi** |
| `XGIDA.IS`, `XHOLD.IS`, `XULAS.IS`, `XILTM.IS` | Gıda, Holding, Ulaştırma, İletişim | yok (sonraki tur) |
| `XU500.IS`, `XUTUM.IS` | BIST 500, Tüm | `XUTUM` yalnız eşlemede |

Makro (BIST dışı, kendi seansı):

| Kod | Yahoo | Ne |
|---|---|---|
| `USDTRY` | `USDTRY=X` | dolar/TL |
| `XAUUSD` | `XAUUSD=X` (yoksa `GC=F`) | ons altın (USD) — parite adı |
| `XAGUSD` | `XAGUSD=X` (yoksa `SI=F`) | ons gümüş (USD) — parite adı |
| `BRENT` | `BZ=F` | Brent (zaten vardı) |

**Kritik bulgu — hacim:** Yahoo, endekslerde hacim sütununu **0 / boş** veriyor;
makro sembollerde hacim farklı birimde ve gün sonu hizalı değil. Bu yüzden
`volume_usable=False` (dokümanlarda XU100/XU30 için "KULLANILAMAZ" olarak zaten
işaretliydi). Karar: satır silinmez, **neden** yazılır (kullanıcı seçimi).

**Kritik bulgu — seans:** `tamamlanmis_mumlar` kapanış kuralı BIST seansına
bağlıdır (`mum_kapanis_anlari`). FX/emtia 24 saat işlem görür; gün sonu barları
BIST kapanışıyla hizalanmaz. Tarama penceresi BIST seansıyla sınırlı olduğu için
pratik etki küçük, ama kural **tam** doğrulanamaz → makro semboller varsayılan
olarak alarm üretmez (`MAKRO_ALARM=0`); veri, grafik ve bağlam çalışır.

---

## 2. Evren

```
57 sembol (48 hisse + 5 endeks + 4 makro)
```

`config.ACTIVE_STOCKS` → `BIST_50` listesi. Tek etiket kaynağı
`config.evren_ozeti()`; kısa hâli (`ayrinti=False`) özet/panel satırlarında,
ayrıntılı hâli `/durum`da kullanılır (uzun parantez 283 px bütçesini bölüyordu).

`config.sembol_turu(sembol)` → `"hisse" | "endeks" | "makro"`. Arayüzde artık
"hisse" yerine **sembol** denir: `/durum` evren satırı, tarama yanıtı, günlük
özet, `/formasyonlar` boş mesajı, kanal açıklaması.

---

## 3. Hacim satırı (kullanıcı kararı: "hacim yoksa o bilinsin")

| Sembol | Kart satırı |
|---|---|
| Hisse | `katılım 4s veri yok` (yalnız gerçekten veri yoksa) |
| Endeks | `katılım 4s hacim yok (endeks)` + `yön fiyattan okunur` |
| Makro | `katılım 4s hacim yok (makro)` + `yön fiyattan okunur` |

Ölçüm notu: tek satırlık "endeks hacmi toplanmıyor · yön fiyattan okunur"
**466 px** çıkıyor (eşik 262,85) ve `_satir` bölüyordu — girintili devam satırı
kart sözleşmesinde yasak. Bu yüzden açıklama iki kısa satıra bölündü
(237 px + 159 px).

---

## 4. Endekse göre göreli güç

- Pencere: **20 mum**, alarmın zaman diliminde (`_GORELI_MUM`).
- Taban: iki getiri **aynı pencerede**, **aynı TF'de**; endeks serisi hissenin
  son mumuna kadar kesilir (farklı bitiş tarihleri kıyaslanmaz).
- Birim: **puan** — iki yüzdenin farkı yüzde değildir. Satır:
  `· 20 mum endekse +2,1 puan` (negatifte `-2,1`), başabaşta
  `· 20 mum endeksle başabaş`.
- Yer: kartın **YAPI** bloğu, olay başına bir kez. Geçersizleşme kartında
  basılmaz (geri alma kartı "ne oldu"yu anlatır).
- Veri yoksa satır yok; `XU100` alarmının kendisinde hesaplanmaz.

Ölçüm (satır bütçesi 262,85 px): `· 20 mumda endeksten +2,1 puan` **270,5 px**
(→ bölünüyordu), `· 20 mumda endekse +17,9 puan` **263,5 px** (eşiğin üstü),
seçilen biçim `· 20 mum endekse +17,9 puan` **243,5 px**.

---

## 5. Makro alarm kapısı

`config.MAKRO_ALARM` (env, varsayılan `0`). Kapalıyken makro sembol:
tarama ✓, grafik ✓, `/formasyonlar` ✓, **DM/public push ✗**;
`daily_stats['alerts_makro_kapali']` sayılır. `MAKRO_ALARM=1` → BRENT dâhil
eski davranış.

Endeksler bu kapıya **girmez** (kullanıcı: "normal farksız"): kendi formasyonu,
OB/FVG'si, kartı, grup mesajı vardır.

---

## 6. Public (grup) tarafı

Değişen bir şey yok — endeksler aynı yoldan gider:

```
motor → should_send_to_public (state ∩ PUBLIC_STATES, TF kalite eşiği)
      → public kuyruğu (tekrar mührü)
      → olay başına 1 mesaj: DM kartının BİREBİR aynısı
      → metnin hemen ardından 1 kare + üst TF karesi
```

Toplu bülten kaldırıldı (2026-10-22 akşamı): grup mesajı DM kartıyla byte byte
aynıdır — başlık, "N gelişme", tarih satırı yok; 3 `◇` de dâhil. Endeks olayı
da aynı yoldan gider; tek fark hacim bloğunun yukarıdaki iki satırı.

---

## 7. Maliyet

Her sembol taramaya ~1,5 sn + batch molaları ekler. 6 yeni sembol ⇒ tur başına
yaklaşık **+40 sn** (tam zamanlı tur ≈ 5 dk'da bir). Ölçüm: 57 sembolde
`SCAN_*` pacing ayarları değişmedi; `daily_stats` ve `tarama_suresi_dk`
`/durum`da izlenebilir. Sıkıntı görülürse `SCAN_REQUEST_BATCH_SIZE` /
`SCAN_BATCH_PAUSE_*` ile ayarlanır.

---

## 8. Testler

`test_endeks_evreni.py` — 23 test:

- sağlayıcı eşlemesi (`XU50→XU050.IS`, `USDTRY→USDTRY=X`, `XAUUSD→XAUUSD=X`; `.IS.IS` yok),
- evren içeriği + `evren_ozeti` (hisse/endeks/makro ayrımı, kısa biçim bütçesi),
- hacim nedeni (endeks/makro/hisse) + public mesajında görünmesi,
- makro alarm kapısı (varsayılan kapalı, bayrakla açılır, endeks muaf),
- göreli güç: puan farkı, yetersiz/bozuk veri, hizalama, satır bütçesi,
  XU100'ün kendisi, veri yokken satır yok,
- kart: satır bir kez, sarma yok, 20 satır tavanı, geçersizleşmede basılmaması,
- public kuyruğun göreli satırı saklaması.

Ayrıca evren sayısına sabit değer yazan üç eski test türetilmiş doğrulamaya
çevrildi (`test_scan_pacing`, `test_live_data_flow`, `test_yahoo_backfill`).

### 8.1 Veri yolu duman testi (22 Ekim 2026)

Sandbox'ta Yahoo çıkışı kapalı (`fetch_yfinance_1h` üç sembolde de `None`
döndü), bu yüzden canlı çekim yerine **aynı boru hattı sentetik seriyle**
çalıştırıldı: `append_candle → to_dataframe → resample_all_timeframes →
tamamlanmis_mumlar → anlik_goruntu → kareyi_yaz`.

| Sembol | Deque | 1h | 2h | 4h | 1d | Kare |
|---|---|---|---|---|---|---|
| XBANK (seanslı, hacim dolu) | 320 | 320 kapalı | 160 | 80 | 40 | üretildi, 68 KB, uyarı yok |
| USDTRY (24 saat, hacim 0) | 320 | 320 kapalı | 160 | 80 | 13/14 | üretildi, 61 KB, uyarı yok |

24 saatlik seride `tamamlanmis_mumlar` yalnız **son** günlük mumu eler (14 → 13);
seans sonrası başlayan barlar geri çekilmiyor — `BAR` kesme kuralı yalnız seans
içinde başlayıp seans sonunu aşan barlara uygulanıyor. Bu, makro sembollerde
günlük mumun kapanış anını BIST takvimine bağladığımız anlamına gelir; bu yüzden
`MAKRO_ALARM=0` varsayılanı korunuyor (bölüm 5).

Canlı doğrulama (gerçek Yahoo verisiyle) deploy sonrası ilk turda `/durum`dan
yapılmalı: endeks satırlarında `hacim yok (endeks)`, kartta göreli güç satırı.
