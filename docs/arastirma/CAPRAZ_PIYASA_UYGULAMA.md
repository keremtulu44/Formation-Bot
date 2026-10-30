# Çapraz piyasa: uygulama, çalıştırma ve ilk pilot

Araştırma hattı: `research/capraz_piyasa.py`, CLI: `scripts/capraz_piyasa_rapor.py`.
Canlı alarm/kart/puanı değiştirmez ve Supabase'e yazmaz. Girdi mevcut
`backfill_data/` hisseleri ve `capraz_piyasa_data/`; makro dosyalarında manifest
SHA-256 kontrolü yapılır. `var/` çıktıları Git'e alınmaz.

## Önemli veri kapısı

Bu arşivde makro serilerinin tümünde `closed_at_verified=false`. Bar etiketi
kapanış/kullanılabilirlik anı değildir. Bu nedenle varsayılan **STRICT_UNKNOWN**
modunda bağlamlar UNKNOWN olur; bu 12 serinin indirilememesi anlamına gelmez,
sadece BIST karar anında hangilerinin bilindiği henüz ispatlanmamıştır.

Sağlayıcının her barı için doğrulanmış erişim anları ayrıca temin edilirse
`--availability dosya.csv` ile `symbol,bar_time,available_at` (saat dilimli ISO
etiketler) verilir. Her kaynak için eksiksiz ve kronolojik eşleşme gerekir.
Dosyadaki zamanın gerçekliği hattın kendisi tarafından doğrulanmaz; belgeli
kaynak kontrolü operatörün sorumluluğudur. Eksik kaynak UNKNOWN kalır. BIST
kararı config `BIST_OPEN` (09:50 İstanbul) olup eşit zamanda gelen veriyi bile
ihtiyatla kullanmaz.

Yalnız teknoloji/hesap testi için `--assume-lag-days 2` denenebilir. Bu tarih
gecikmesi kapanış kanıtı değildir; çıktı `UNVERIFIED_EXPLORATION` olarak
etiketlenir ve gerçek bulgu/validasyon diye sunulamaz. USDTRY'deki 31 bozuk
OHLC mumu ve çevresindeki ATR pencereleri kullanılamazdır. Kapanış tek başına
doğrulanmış sayılmaz. Gram TL OHLC için uygun kaynak/eşzamanlılık bulunmadığından
her iki gram seri UNKNOWN kalır; farklı kaynakların günlük yüksek/düşükleri
çarpılmaz. Spot ve vadeli farklı serilerdir.

## Çalıştırma

```bash
# Veri kapısını gör: kısa örnek (hiç kaynak varsayımı yok)
python scripts/capraz_piyasa_rapor.py --symbols ASTOR,THYAO \
  --macro XU100,BRENT,XAUUSD,XAGUSD,USDTRY,XAU_GRAM_TRY \
  --order 2 --output var/capraz_kati

# YALNIZ keşif/test; geleceğe bakmama yerine geçmez
python scripts/capraz_piyasa_rapor.py --symbols ASTOR,THYAO \
  --macro XU100,BRENT,XAUUSD,XAGUSD,USDTRY,XAU_GRAM_TRY \
  --order 2 --assume-lag-days 2 --select --output var/capraz_kesif
```

`--symbols` verilmezse arşivdeki hisse sınıfı seçilir. `--macro` verilmezse 12
arşiv aracı ve iki gram değişkeni kullanılır. `--order` verilmezse **tüm 2^14−1
araç altkümesi** istenir: hücre sayısı, disk ve çalışma süresi çok büyük olabilir.
CSV yalnız gözlenmiş koşul durumlarını taşır; gözlenmeyen sınıflar yok sayılarak
değil, sıfır gözlem olarak yorumlanmalıdır. `summary.json` seçili kombinasyon,
kaynak, kalite ve mod bilgisini taşır. `cells.csv` her hisse, 0.5/1/1.5 ATR
piyasa/hisse katsayısı, 1/5/10 işlem günü, dönem ve gözlenmiş hücre için n,
kalite UNKNOWN ve sağ sansür ayrı sayımları, UP/FLAT/DOWN ve koşulsuz baz verir.
Discovery sonuna taşan hedefler dönem sızıntısı önlemek için purged edilir;
hisse ve ufuk bazında bunların ve sağ sansürün sayıları `summary.json` içindedir.
Validation sonunda kalan eksik ufuklar sansür olarak sayılır.

`--select` keşif döneminde her hisse/ufuk/araç altkümesinde en az 30 gözlemli
hücrelerin koşulsuz bazdan en büyük mutlak farkını seçer, aynı koşul ve ATR
çiftinin doğrulama sonucunu `selected.csv` dosyasında gösterir. Bu çok sayıda
aday arasından seçimin etkisini, bağımlı olayları veya çoklu testi düzeltmez;
yeterli doğrulama n olsa bile sonuç `UNADJUSTED_EXPLORATORY` durumundadır.
Daha küçük n `INSUFFICIENT_VALIDATION` olur. Çok sayıda kombinasyonda aday
seçiminin belleği de büyür. Komisyon, işlem fiyatı, anlamlılık, blok güven
aralığı ve bağımsız canlı ileri test yapılmadığından otomatik güçlü/doğrulanmış
bulgu veya yatırım kararı üretilmez. Önceki kapanıştan ölçülen değişim, seans
başında o fiyattan işlem yapılabildiği anlamına gelmez.

## Yerel pilot (2026-10-29)

ASTOR ve THYAO, altı bağlam ve iki araçlıya kadar toplam 21 altküme kullanıldı.
STRICT_UNKNOWN: 2.268 gözlenen hücre, 0 tamamen bilinen koşul. Yalnız deneme
için iki günlük gecikme varsayımıyla 11.454 gözlenen hücre, 8.394 bilinen
koşul satırı üretildi. Keşif seçiminde 90 adayın 74'ü ileri dönemde 30'un
altında gözleme sahipti; 16'sı ham karşılaştırmaya elverişliydi ama çoklu test
ve erişim saatleri doğrulanmadığından hiçbirine doğrulanmış bulgu denemez.
Bu rakamlar bağımsız olay sayısı veya başarı yüzdesi değildir. USDTRY için 31
bozuk mum raporlandı. Doğrulanmış kapanış ve gram OHLC olmadığı için araştırma
tamamlanmış sayılmaz.
