# Deploy hisse evreni × endeks / altın / gümüş: pilot sonuçları

**Araştırma; canlı alarm veya yatırım önerisi değil.** Örnekler aşağıda, tüm tekli hücreler CSV’de ve tüm tekli + ikili hücreler sıkıştırılmış CSV’dedir.

## Kapsam ve güvenilirlik

* `config.BIST_50` varsayılanındaki **48 hisse**. 30 Ekim 2026 tarihli Supabase günlük önbelleklerinde bu 48 hissenin güncel kayıtları gözlendi. Bu, `STOCK_UNIVERSE` ortam değişkeninin çalışan süreçteki değerinin doğrudan görülmesi değildir; değişken listeyi değiştirebilir.
* Hisseler yalnız 48’lik varsayılan evrenden: endeks ve emtialar hisse sıralamasına sokulmadı. `XU100`, `XU30`, `XU50`, `XBANK`, `XUSIN`, `XUTUM`; `XAUUSD` spot ons, `XAGUSD` spot ons, `XAU_FUT`, `XAG_FUT` vadeli, `BRENT` (BZ=F vadeli), `USDTRY` karşılaştırma değişkenleridir. XUTUM ve ayrı vadeli altın/gümüş araştırma serileridir; bunların deployda birebir canlı izlenmesi iddia edilmez. Deploydaki ons spot veri sağlayıcı fallback’i vadeli olabilir; bu raporun spot arşivi ile özdeş sayılmamalı.
* Her kaynağın kapanış/kullanılabilirlik saati doğrulanmadı. 2 takvim günü gecikme varsayımı kullanıldı; her kaynak için ayrı son uygun gün seçilir. Bu ileriye bakmama veya canlıda kullanılabilirlik kanıtı değildir. Gram altın/gümüş için eşzamanlı TL OHLC bulunmadığından sonuç üretilmedi.
* Makro yön eşiği ±0,5 günlük ATR; hisse sonucu ±1 ATR. Eşik içi ve eşit sınır **yatay**: küçük artış/azalışları içerir. 1/5/10 işlem günü: karar gününden önceki hisse kapanışından ilgili hedef kapanışa kadar. Aşağıdaki örnekler **5 gün**.
* Her hissede zaman sıralı %70 keşif, %30 ileri dönem; keşiften ileri sınıra taşan sonuçlar çıkarıldı. Aynı makro bar çifti ve örtüşen hisse sonuç pencereleri ayrı sayılmadı. Kalan sonuçlar da piyasa ve sektör nedeniyle bağımlı olabilir. Sonlar eksikse sansür; USDTRY bozuk OHLC sonrasında ATR yeniden başlatıldı.
* Tüm 12 tekli seri ve **66 ikili seri birleşimi** için UP/FLAT/DOWN koşulları, 1/5/10 gün ve iki dönem: **181.440 teorik hücre**. Üçlü ve daha yüksek birleşimler bu özel raporda çalıştırılmadı. CSV sıfır gözlemli hücreleri de içerir. İki takvim günü varsayımına dayalı; gerçek tarihsel seans/kurumsal işlem düzeltmesi tam doğrulanmadı.

## Nasıl okunur?

Her tabloda adaylar yalnız keşif döneminde ilgili yöndeki orana göre seçilen iki örnektir (keşifte en az 10 bağımsız olmayan pencere); daha sonra aynı koşul ve hissenin ileri dönem sayıları gösterilir. Sayılar **yukarı / yatay / aşağı** sırasındadır. Çok sayıda hisse ve koşul arasından seçildiği için tesadüfi uç değerler beklenir. İleri dönemde küçük n veya n=0, doğrulama anlamına gelmez.

Koşulsuz bazlar CSV’de `baseline_*` alanındadır; o bazlar dönem içi düzenli örtüşmesiz pencere ızgarasıdır ve makro koşullu günlere rejim/volatilite bakımından eşleştirilmiş kontrol değildir. Nedensel karşılaştırma değildir. `unknown_condition_n` her kombinasyonun satırlarında tekrar eder, hücreler boyunca toplanmamalıdır.

## 5 günlük hisse sonuçları — tekli koşullar

### BIST 100 — XU100

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 13 / 15 / 3 (n=31) | 4 / 8 / 3 (n=15) |
| Düştü | Yukarı | GUBRF | 11 / 11 / 9 (n=31) | 3 / 6 / 6 (n=15) |
| Düştü | Aşağı | KONTR | 6 / 10 / 14 (n=30) | 2 / 7 / 6 (n=15) |
| Düştü | Aşağı | TTRAK | 6 / 13 / 12 (n=31) | 2 / 9 / 4 (n=15) |
| Yatay | Yukarı | ASELS | 21 / 26 / 8 (n=55) | 7 / 13 / 6 (n=26) |
| Yatay | Yukarı | GUBRF | 21 / 26 / 8 (n=55) | 6 / 14 / 6 (n=26) |
| Yatay | Aşağı | PGSUS | 11 / 25 / 19 (n=55) | 5 / 13 / 8 (n=26) |
| Yatay | Aşağı | OTKAR | 15 / 24 / 16 (n=55) | 4 / 13 / 9 (n=26) |
| Yükseldi | Yukarı | GUBRF | 16 / 18 / 3 (n=37) | 5 / 8 / 6 (n=19) |
| Yükseldi | Yukarı | SKBNK | 16 / 13 / 8 (n=37) | 4 / 10 / 5 (n=19) |
| Yükseldi | Aşağı | PGSUS | 8 / 16 / 13 (n=37) | 2 / 10 / 7 (n=19) |
| Yükseldi | Aşağı | TTRAK | 11 / 14 / 12 (n=37) | 4 / 8 / 7 (n=19) |

### BIST 30 — XU30

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 16 / 16 / 3 (n=35) | 4 / 8 / 2 (n=14) |
| Düştü | Yukarı | EREGL | 13 / 11 / 11 (n=35) | 4 / 8 / 2 (n=14) |
| Düştü | Aşağı | KONTR | 6 / 12 / 15 (n=33) | 2 / 7 / 5 (n=14) |
| Düştü | Aşağı | TTRAK | 7 / 14 / 14 (n=35) | 2 / 8 / 4 (n=14) |
| Yatay | Yukarı | ASELS | 23 / 23 / 10 (n=56) | 7 / 14 / 5 (n=26) |
| Yatay | Yukarı | GUBRF | 22 / 23 / 11 (n=56) | 5 / 14 / 7 (n=26) |
| Yatay | Aşağı | SISE | 16 / 22 / 18 (n=56) | 6 / 13 / 7 (n=26) |
| Yatay | Aşağı | TSKB | 14 / 24 / 18 (n=56) | 6 / 11 / 9 (n=26) |
| Yükseldi | Yukarı | GUBRF | 16 / 17 / 4 (n=37) | 5 / 7 / 6 (n=18) |
| Yükseldi | Yukarı | SKBNK | 16 / 12 / 9 (n=37) | 4 / 9 / 5 (n=18) |
| Yükseldi | Aşağı | PGSUS | 8 / 16 / 13 (n=37) | 2 / 9 / 7 (n=18) |
| Yükseldi | Aşağı | OTKAR | 13 / 12 / 12 (n=37) | 2 / 9 / 7 (n=18) |

### BIST 50 — XU50

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 17 / 16 / 3 (n=36) | 4 / 7 / 3 (n=14) |
| Düştü | Yukarı | EREGL | 13 / 11 / 12 (n=36) | 4 / 9 / 1 (n=14) |
| Düştü | Aşağı | KONTR | 6 / 13 / 15 (n=34) | 2 / 7 / 5 (n=14) |
| Düştü | Aşağı | TTRAK | 8 / 14 / 14 (n=36) | 2 / 8 / 4 (n=14) |
| Yatay | Yukarı | ASELS | 22 / 24 / 9 (n=55) | 7 / 12 / 6 (n=25) |
| Yatay | Yukarı | GUBRF | 21 / 24 / 10 (n=55) | 5 / 14 / 6 (n=25) |
| Yatay | Aşağı | PGSUS | 12 / 24 / 19 (n=55) | 5 / 13 / 7 (n=25) |
| Yatay | Aşağı | TSKB | 12 / 24 / 19 (n=55) | 6 / 11 / 8 (n=25) |
| Yükseldi | Yukarı | GUBRF | 15 / 19 / 4 (n=38) | 5 / 8 / 6 (n=19) |
| Yükseldi | Yukarı | SKBNK | 15 / 14 / 9 (n=38) | 4 / 10 / 5 (n=19) |
| Yükseldi | Aşağı | PGSUS | 8 / 17 / 13 (n=38) | 2 / 10 / 7 (n=19) |
| Yükseldi | Aşağı | OTKAR | 12 / 14 / 12 (n=38) | 2 / 9 / 8 (n=19) |

### Banka endeksi — XBANK

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | EKGYO | 13 / 11 / 8 (n=32) | 2 / 8 / 4 (n=14) |
| Düştü | Yukarı | SKBNK | 13 / 14 / 5 (n=32) | 4 / 6 / 4 (n=14) |
| Düştü | Aşağı | PGSUS | 6 / 12 / 14 (n=32) | 2 / 8 / 4 (n=14) |
| Düştü | Aşağı | SASA | 4 / 14 / 14 (n=32) | 3 / 8 / 3 (n=14) |
| Yatay | Yukarı | ASELS | 22 / 24 / 8 (n=54) | 3 / 19 / 5 (n=27) |
| Yatay | Yukarı | AKSEN | 19 / 25 / 10 (n=54) | 8 / 12 / 7 (n=27) |
| Yatay | Aşağı | PGSUS | 11 / 25 / 18 (n=54) | 4 / 14 / 9 (n=27) |
| Yatay | Aşağı | THYAO | 10 / 26 / 18 (n=54) | 2 / 19 / 6 (n=27) |
| Yükseldi | Yukarı | DOHOL | 13 / 14 / 3 (n=30) | 4 / 9 / 3 (n=16) |
| Yükseldi | Yukarı | GUBRF | 12 / 15 / 3 (n=30) | 4 / 9 / 3 (n=16) |
| Yükseldi | Aşağı | KRDMD | 10 / 11 / 9 (n=30) | 3 / 10 / 3 (n=16) |
| Yükseldi | Aşağı | SASA | 5 / 16 / 9 (n=30) | 3 / 8 / 5 (n=16) |

### Sanayi endeksi — XUSIN

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 16 / 16 / 5 (n=37) | 4 / 11 / 5 (n=20) |
| Düştü | Yukarı | HALKB | 13 / 18 / 6 (n=37) | 7 / 8 / 5 (n=20) |
| Düştü | Aşağı | SASA | 7 / 14 / 16 (n=37) | 6 / 8 / 6 (n=20) |
| Düştü | Aşağı | FROTO | 6 / 16 / 15 (n=37) | 3 / 12 / 5 (n=20) |
| Yatay | Yukarı | EKGYO | 23 / 23 / 11 (n=57) | 6 / 11 / 6 (n=23) |
| Yatay | Yukarı | ISCTR | 23 / 21 / 13 (n=57) | 5 / 10 / 8 (n=23) |
| Yatay | Aşağı | PGSUS | 15 / 23 / 19 (n=57) | 4 / 11 / 8 (n=23) |
| Yatay | Aşağı | EGEEN | 13 / 27 / 17 (n=57) | 5 / 11 / 7 (n=23) |
| Yükseldi | Yukarı | SKBNK | 15 / 11 / 9 (n=35) | 5 / 8 / 4 (n=17) |
| Yükseldi | Yukarı | ASELS | 14 / 17 / 4 (n=35) | 3 / 10 / 4 (n=17) |
| Yükseldi | Aşağı | HEKTS | 6 / 16 / 13 (n=35) | 3 / 10 / 4 (n=17) |
| Yükseldi | Aşağı | KRDMD | 7 / 15 / 13 (n=35) | 5 / 8 / 4 (n=17) |

### BIST TÜM — XUTUM

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 10 / 15 / 3 (n=28) | 3 / 8 / 4 (n=15) |
| Düştü | Yukarı | EKGYO | 9 / 10 / 9 (n=28) | 3 / 7 / 5 (n=15) |
| Düştü | Aşağı | KONTR | 2 / 10 / 14 (n=26) | 2 / 6 / 7 (n=15) |
| Düştü | Aşağı | FROTO | 2 / 14 / 12 (n=28) | 3 / 8 / 4 (n=15) |
| Yatay | Yukarı | ASELS | 21 / 24 / 7 (n=52) | 7 / 11 / 7 (n=25) |
| Yatay | Yukarı | GUBRF | 20 / 25 / 7 (n=52) | 5 / 13 / 7 (n=25) |
| Yatay | Aşağı | PGSUS | 13 / 22 / 17 (n=52) | 4 / 13 / 8 (n=25) |
| Yatay | Aşağı | TSKB | 13 / 22 / 17 (n=52) | 6 / 9 / 10 (n=25) |
| Yükseldi | Yukarı | SKBNK | 18 / 15 / 10 (n=43) | 4 / 9 / 5 (n=18) |
| Yükseldi | Yukarı | ASELS | 17 / 20 / 6 (n=43) | 4 / 9 / 5 (n=18) |
| Yükseldi | Aşağı | SASA | 7 / 20 / 16 (n=43) | 4 / 9 / 5 (n=18) |
| Yükseldi | Aşağı | PGSUS | 9 / 19 / 15 (n=43) | 2 / 10 / 6 (n=18) |

### Brent vadeli — BRENT

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | ASELS | 15 / 10 / 6 (n=31) | 3 / 7 / 6 (n=16) |
| Düştü | Yukarı | GUBRF | 12 / 13 / 6 (n=31) | 3 / 10 / 3 (n=16) |
| Düştü | Aşağı | AYDEM | 7 / 13 / 11 (n=31) | 3 / 8 / 5 (n=16) |
| Düştü | Aşağı | BRSAN | 10 / 10 / 11 (n=31) | 5 / 8 / 3 (n=16) |
| Yatay | Yukarı | ASELS | 23 / 21 / 11 (n=55) | 7 / 11 / 7 (n=25) |
| Yatay | Yukarı | GUBRF | 22 / 21 / 12 (n=55) | 4 / 13 / 8 (n=25) |
| Yatay | Aşağı | KONTR | 11 / 22 / 19 (n=52) | 6 / 6 / 13 (n=25) |
| Yatay | Aşağı | TTRAK | 11 / 26 / 18 (n=55) | 4 / 16 / 5 (n=25) |
| Yükseldi | Yukarı | GUBRF | 17 / 12 / 5 (n=34) | 4 / 8 / 2 (n=14) |
| Yükseldi | Yukarı | ISMEN | 16 / 13 / 5 (n=34) | 2 / 7 / 5 (n=14) |
| Yükseldi | Aşağı | PGSUS | 8 / 14 / 12 (n=34) | 3 / 8 / 3 (n=14) |
| Yükseldi | Aşağı | TTRAK | 8 / 14 / 12 (n=34) | 5 / 5 / 4 (n=14) |

### Dolar/TL — USDTRY

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | — | Yetersiz örnek | — | — |
| Yatay | Yukarı | ASELS | 19 / 21 / 9 (n=49) | 6 / 4 / 4 (n=14) |
| Yatay | Yukarı | HALKB | 16 / 23 / 10 (n=49) | 2 / 10 / 2 (n=14) |
| Yatay | Aşağı | TTRAK | 12 / 17 / 20 (n=49) | 3 / 10 / 1 (n=14) |
| Yatay | Aşağı | SISE | 12 / 20 / 17 (n=49) | 0 / 12 / 2 (n=14) |
| Yükseldi | Yukarı | GUBRF | 16 / 14 / 8 (n=38) | 2 / 6 / 2 (n=10) |
| Yükseldi | Yukarı | ASELS | 14 / 16 / 8 (n=38) | 3 / 6 / 1 (n=10) |
| Yükseldi | Aşağı | KONTR | 11 / 10 / 17 (n=38) | 2 / 3 / 5 (n=10) |
| Yükseldi | Aşağı | BRSAN | 10 / 13 / 15 (n=38) | 2 / 6 / 2 (n=10) |

### Ons altın / USD (spot) — XAUUSD

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | TAVHL | 15 / 10 / 5 (n=30) | 2 / 9 / 3 (n=14) |
| Düştü | Yukarı | ASELS | 14 / 11 / 5 (n=30) | 1 / 10 / 3 (n=14) |
| Düştü | Aşağı | EGEEN | 4 / 15 / 11 (n=30) | 2 / 6 / 6 (n=14) |
| Düştü | Aşağı | SASA | 7 / 12 / 11 (n=30) | 1 / 10 / 3 (n=14) |
| Yatay | Yukarı | AKBNK | 24 / 21 / 12 (n=57) | 6 / 12 / 8 (n=26) |
| Yatay | Yukarı | ASELS | 24 / 24 / 9 (n=57) | 7 / 11 / 8 (n=26) |
| Yatay | Aşağı | KONTR | 13 / 20 / 20 (n=53) | 3 / 15 / 8 (n=26) |
| Yatay | Aşağı | EGEEN | 11 / 28 / 18 (n=57) | 5 / 15 / 6 (n=26) |
| Yükseldi | Yukarı | TUPRS | 17 / 17 / 10 (n=44) | 4 / 6 / 2 (n=12) |
| Yükseldi | Yukarı | ASTOR | 16 / 16 / 12 (n=44) | 5 / 5 / 2 (n=12) |
| Yükseldi | Aşağı | SISE | 8 / 18 / 18 (n=44) | 2 / 8 / 2 (n=12) |
| Yükseldi | Aşağı | PGSUS | 9 / 18 / 17 (n=44) | 2 / 5 / 5 (n=12) |

### Ons gümüş / USD (spot) — XAGUSD

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | HALKB | 16 / 12 / 3 (n=31) | 5 / 6 / 2 (n=13) |
| Düştü | Yukarı | ASELS | 14 / 12 / 5 (n=31) | 1 / 9 / 3 (n=13) |
| Düştü | Aşağı | ASTOR | 12 / 10 / 9 (n=31) | 3 / 7 / 3 (n=13) |
| Düştü | Aşağı | KONTR | 10 / 12 / 8 (n=30) | 1 / 6 / 6 (n=13) |
| Yatay | Yukarı | ASELS | 24 / 20 / 10 (n=54) | 6 / 13 / 8 (n=27) |
| Yatay | Yukarı | AKBNK | 21 / 22 / 11 (n=54) | 7 / 12 / 8 (n=27) |
| Yatay | Aşağı | TTRAK | 12 / 21 / 21 (n=54) | 4 / 19 / 4 (n=27) |
| Yatay | Aşağı | EGEEN | 10 / 25 / 19 (n=54) | 6 / 17 / 4 (n=27) |
| Yükseldi | Yukarı | GUBRF | 19 / 15 / 7 (n=41) | 1 / 4 / 4 (n=9) |
| Yükseldi | Yukarı | ASELS | 17 / 18 / 6 (n=41) | 2 / 5 / 2 (n=9) |
| Yükseldi | Aşağı | PGSUS | 8 / 19 / 14 (n=41) | 1 / 3 / 5 (n=9) |
| Yükseldi | Aşağı | ARCLK | 7 / 21 / 13 (n=41) | 0 / 6 / 3 (n=9) |

### Altın vadeli — XAU_FUT

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | TAVHL | 12 / 6 / 6 (n=24) | 4 / 7 / 2 (n=13) |
| Düştü | Yukarı | EKGYO | 11 / 8 / 5 (n=24) | 5 / 6 / 2 (n=13) |
| Düştü | Aşağı | THYAO | 10 / 5 / 9 (n=24) | 3 / 9 / 1 (n=13) |
| Düştü | Aşağı | ALARK | 8 / 8 / 8 (n=24) | 5 / 6 / 2 (n=13) |
| Yatay | Yukarı | ASELS | 26 / 22 / 9 (n=57) | 6 / 12 / 8 (n=26) |
| Yatay | Yukarı | ISCTR | 22 / 22 / 13 (n=57) | 4 / 13 / 9 (n=26) |
| Yatay | Aşağı | EGEEN | 11 / 25 / 21 (n=57) | 5 / 14 / 7 (n=26) |
| Yatay | Aşağı | FROTO | 14 / 23 / 20 (n=57) | 4 / 14 / 8 (n=26) |
| Yükseldi | Yukarı | ASTOR | 15 / 14 / 13 (n=42) | 3 / 5 / 3 (n=11) |
| Yükseldi | Yukarı | GUBRF | 15 / 19 / 8 (n=42) | 1 / 7 / 3 (n=11) |
| Yükseldi | Aşağı | PGSUS | 8 / 19 / 15 (n=42) | 2 / 5 / 4 (n=11) |
| Yükseldi | Aşağı | SISE | 8 / 19 / 15 (n=42) | 1 / 7 / 3 (n=11) |

### Gümüş vadeli — XAG_FUT

| Makro koşul | Keşif yönü | Hisse | Keşif: ↑ / yatay / ↓ | İleri dönem: ↑ / yatay / ↓ |
|---|---|---|---:|---:|
| Düştü | Yukarı | HALKB | 19 / 14 / 4 (n=37) | 4 / 6 / 3 (n=13) |
| Düştü | Yukarı | ASELS | 17 / 17 / 3 (n=37) | 1 / 10 / 2 (n=13) |
| Düştü | Aşağı | KRDMD | 13 / 13 / 11 (n=37) | 3 / 8 / 2 (n=13) |
| Düştü | Aşağı | ASTOR | 11 / 16 / 10 (n=37) | 3 / 6 / 4 (n=13) |
| Yatay | Yukarı | ASELS | 22 / 18 / 10 (n=50) | 8 / 7 / 10 (n=25) |
| Yatay | Yukarı | EKGYO | 18 / 22 / 10 (n=50) | 6 / 13 / 6 (n=25) |
| Yatay | Aşağı | TTRAK | 10 / 21 / 19 (n=50) | 6 / 14 / 5 (n=25) |
| Yatay | Aşağı | HEKTS | 11 / 22 / 17 (n=50) | 4 / 14 / 7 (n=25) |
| Yükseldi | Yukarı | ASELS | 20 / 19 / 7 (n=46) | 5 / 8 / 3 (n=16) |
| Yükseldi | Yukarı | GUBRF | 19 / 21 / 6 (n=46) | 3 / 9 / 4 (n=16) |
| Yükseldi | Aşağı | ARCLK | 11 / 19 / 16 (n=46) | 0 / 11 / 5 (n=16) |
| Yükseldi | Aşağı | KONTR | 8 / 21 / 15 (n=44) | 2 / 7 / 7 (n=16) |

## Dosyalar

* `DEPLOY_TEKLI_PIYASA_HUCRELERI.csv`: 48 hisse × tekli 12 seri × yönler × 3 vade × 2 dönem. UTF-8 BOM, elektronik tabloda açılabilir.
* `DEPLOY_PIYASA_PILOT.csv.gz`: aynı evrende tüm tekli ve ikili durumların ham ayrıntısı; önce gzip açılır.
* `DEPLOY_PIYASA_PILOT_META.json`: kaynak kapsamı, SHA-256 değerleri, hisse listesi ve eksik/hata kayıtları.

Hiçbir satır otomatik olarak güçlü/doğrulanmış bulgu değildir; kapanış kanıtı, daha büyük örneklem, çoklu test/bağımlılık düzeltmesi, seans ve şirket işlemi kontrolü gereklidir.
