# XU100 + Brent düşüşü: hisse bazında ön araştırma

174 arşiv hissesi; günlük. Kaynaklar XU100 Yahoo `XU100.IS` ve **Brent vadeli**
Yahoo `BZ=F` (spot petrol değil). İkisinin de sağlayıcı kapanış/kullanılabilirlik
anları bağımsız doğrulanmadı. İki takvim günü gecikmeli kaynak tarihleri varsayımı
kullanılmıştır; gerçek zamanlı uygulanabilirlik, eşzamanlı kapanış veya ileriye
bakmama garanti edilmez. Bu yalnızca keşiftir.

Kural: her piyasa aracının kendi günlük kapanış değişimi, kendi 14 günlük ATR'sinin
0,5 katından fazla aşağı ise koşul sağlanır. Hisse sonucu, karar gününden önceki
kapanışa göre sonraki 5 işlem günü sonundaki kapanıştır; hareket kendi başlangıç
ATR'sinin +1 katını aşıyorsa `up`, −1 katının altındaysa `down`, ikisinin arası
ve eşikler `flat`. `flat` küçük artışları ve düşüşleri de içerir. Hatalı/eksik
OHLC ve ATR sonrası veri ile sınırı ileri döneme taşan keşif pencereleri atılır.

Aynı makro bar çifti ve çakışan 5 günlük sonuç pencereleri için yalnız ilk geçerli
pencere tutulur; böylece tekrarlama azaltılır, ancak kalan pencereler ekonomik
olarak bağımsız değildir. Hisse evreni seçili arşivdir, tüm BIST değildir.
Hisse başına kronolojik %70/%30 bölünmüş, keşifte öne çıkanlar ileri dönemde
tekrar kontrol edilmiştir. Çoğu hissede keşifte 10, ileri dönemde yalnız 4
örtüşmeyen gözlem vardır; çoklu hisse/koşul seçimi sonucu güvenilir bulunamaz.

`XU100_BRENT_PILOT_HISSELER.csv` her hisse ve dönem için: `signal_rows` tekrarlar
dahil ham koşul satırları; `n` örtüşme/tekrar azaltıldıktan sonraki geçerli sayı;
`up`, `flat`, `down` yön sayıları ve yüzdeler. `baseline_*` tüm geçerli günleri
saydığı için tekrar içeren, farklı örneklemli tanımlayıcı bazdır; tekil olaylarla
nedensel kıyas veya anlamlılık testi değildir. `first`/`last`, tekil karar
pencerelerinin başlangıçlarıdır, ham piyasa mumunun tarihi değildir.

Öne çıkan bazı hisselerin keşif→ileri sonuçları (yukarı/yatay/aşağı): ASELS
5/3/2 → 0/3/1, GRTHO 5/4/1 → 0/3/1, HEDEF 5/5/0 → 2/2/0, PASEU 5/4/1 →
2/0/2; KRTEK 0/3/7 → 1/2/0, KONTR 2/1/6 → 0/3/1, VESBE 1/3/6 → 0/2/2,
KLSER 2/3/5 → 0/1/3. Tek ileri örneklem KRTEK için 3, diğerleri için 4'tür.
Bunlar güvenilir yatırım sinyali, canlı alarm veya doğrulanmış ilişki değildir.
