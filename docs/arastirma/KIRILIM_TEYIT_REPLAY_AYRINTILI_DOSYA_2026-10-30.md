# 174 hisse kırılım ve teyit Replay — ayrıntılı sonuç ve yöntem dosyası

**Ölçüm ve kayıt:** 30 Ekim 2026 · **Veri sonu:** 19 Ekim 2026 · **Statü:** çevrimdışı gözlemsel araştırma; canlı sinyal, işlem getirisi veya yatırım tavsiyesi değil.

Bu belge önceki [kırılım/teyit raporunu](KIRILIM_TEYIT_REPLAY_SONUCLARI_2026-10-30.md), [teyit sonrası raporu](TEYIT_SONRASI_HAREKET_2026-10-30.md) ve aday–teyit karşılaştırmasını bir arada kaydeder. Kullanılan ayrıntıların ve ham ölçüm tablolarının bağlantıları aşağıdadır; önceki raporlar ve veriler silinmemiştir.

## 1. Kısa ve dürüst sonuç

1. Arşivdeki **174 hisse × 4 zaman dilimi = 696 seri** işlendi, raporlanmış seri hatası yok. Bu evren bütün BIST değildir ve önceki 48 deploy hissesi × piyasa araştırmasından ayrıdır.
2. **25.457 ham aday/deneme** kaydedildi. Adaya göre geçerli ve çakışmayan 21.244 olayın 15.947'si teyitli, 3.577'si teyit alamadı, 1.720'si başarısız kırılım oldu.
3. 45.255 takip kontrolünde bağımsız skor hesabıyla en büyük sayısal fark **1,82 × 10⁻¹²**; incelenen karar değişmezlerinde başarısızlık yok. Bunun kapsamı tüm formasyon matematiği, Pine, gerçek alarm ve teslim doğrulaması değildir.
4. Aynı seçili örneklerde 15.947 teyidin 12.163'ü ilk, 3.784'ü ikinci sonraki barda geldi. Teyit almayan 3.577 adayın 716'sı (%20,0) sonraki 10 kapanıştan en az birinde aday yönünde +2 ATR'ye ulaştı; **526'sında (%14,7)** onuncu kapanış da aynı eşiğin ötesindeydi. Bu, hepsine erken alarm verilmesini kanıtlamaz.
5. Teyit sonrası bağımsız incelemede 18.752 teyit girdisi, 18.495 iki hedefi gözlenebilir olay, teyit penceresi filtresiyle **18.131** olay vardır. Teyit öncesi/sonrası karşılaştırması aynı olayları kullanır; önceki 15.947 ile farklı filtre ve farklı payda vardır.
6. İleri dönemde 1 saat aşağı için aynı 1.402 olayda adaydan 10. kapanışa medyan fiyat değişimi **−%0,81**, teyitten adayın aynı 10. kapanışına **−%0,54**, teyitten sonraki kendi 10. kapanışına **−%0,56** idi. **Bunlar ayrı medyanlar** ve son iki hedef farklı zaman noktaları olabilir.
7. İleri dönemde aşağı teyitlerden sonraki medyan fiyat düşüşü, yukarı teyitlerden sonraki medyan fiyat değişiminden daha olumlu görünür. Keşif ve ileri dönemde bu fark ve piyasa koşulları değiştiğinden bunu zaman dilimine özgü değişmez kural sayamayız.

Canlı formasyon kodu, eşikleri, kararları, Telegram, Supabase ve ham arşiv bu araştırma için değiştirilmedi.

## 2. Evren, zaman dilimleri ve kapsam

- Hisse evreni `research.arsiv.arsiv_sembolleri()` içindeki `sembol_turu == hisse` filtresidir: 174. XU100, XU30 ve Brent hisse havuzuna alınmadı. Değerlendirme deploy listesi değil, arşiv hisseleridir.
- **1 saat ve 1 günlük:** yerel arşivdeki kaynak barlar. **2/4 saat:** kaynak 1 saatten repo `resample_ohlcv` ile 09:30 seans çapalı üretilir; her seri için son türetilmiş kova ihtiyatla çıkarılır.
- Kaynak 1 saat ve günlük dosyalarının her biri için SHA-256, seri kapsamı, bölme zamanı, kontrol sonuçları ve kod/bağımlılık hashleri [ana manifestte](sonuclar/kirilim_replay/manifest.json). En erken veri etiketi 21 Ekim 2024, en geç etiket 19 Ekim 2026; bütün hisse/TF serileri aynı başlangıca sahip değildir.
- Keşif = **her serinin kendi bar dizisinin ilk %70'i**, ileri = son %30'u. Tek bir bütün hisseler için sabit ayrım tarihi yoktur. Adayın ya da teyidin hedefi sınırı geçerse keşif sonucu sansürlenir; geçmiş durumun ileri döneme taşınması, o ana kadar bilinen tarihçe olarak kabul edilir.

### Kaynak kalitesi ve seans sınırlamaları

- Bozuk OHLC veya önceki kapanışa göre %30'dan büyük sıçrama işaretlenir, ilgili mum çıkarılır, sonraki temiz segmentte ATR/motor yeniden başlatılır ve en az 80 mumluk geçmiş aranır (80. bar aday için uygundur). TF toplamında **48 işaretli mum** vardır; bir kaynak sorunu türetilmiş birden çok TF'de sayılabilir. Bu filtre kurumsal işlemleri teşhis etmez ve hatasız veri garantisi vermez.
- 1 saat kaynakta **558.724** mumun **59.604**'ünde hacim sıfır; 59.342'si 09:30 etiketlidir. Kullanıcının bildirdiği üzere bu, veri temin edilen sistemin normal kaynak davranışıdır. Bu çalışmada sıfır hacim silinmedi ve kendi başına bot hatası sayılmadı. Hacim puanına nötr değer ve hareketli ortalamaya etkisi yorumlanırken kaynak semantiği akılda tutulur. 1 günlükte 86.945 mumdan 170'i sıfır hacimlidir.
- Kullanılan 311.277 adet 2 saat kovasının 64.051'inde bir; 186.625 adet 4 saat kovasının 63.191'inde dörtten az 1 saat kaynak etiketi vardır. Bu kısa seans kovaları meşru olabilir; sayı tek başına hata değildir. İç seans boşlukları, tatil/yarım gün ve sağlayıcının geçmiş bar kapanış saatleri bağımsız takvimle doğrulanmadı.
- Son yerel 1s/1g mum hedefine denk gelen olaylar ayrıca `LAST_BAR_UNCERTAIN` olarak dışlandı. Bu, diğer tüm kaynak mumlarının tamamlanmış olduğunu ispatlamaz.

## 3. Terimler ve farklı pencereler

- **Aday:** motorun `KIRILIM_ADAYI` veya `KIRILIM_DENEMESI` durumuna yeni girdiği bar. Aynı durumdaki her bar yeni aday sayılmaz. Adayın kapanışı `P_A`, aday anındaki Wilder ATR `ATR_A`.
- **Teyit:** motorun aynı aday için `KIRILIM_TEYITLI` durumuna girdiği barın kapanışı `P_T`; bu barın Wilder ATR'si `ATR_T`. Bir adayın teyit alması, mesajın gerçekten ulaştığına dair kayıt değildir.
- **Aday hedefi:** `P_A`'dan sonraki **10. kapanış** `P_A10`. **Teyit hedefi:** `P_T`'den sonraki **10. kapanış** `P_T10`. Teyit 1–2 bar sonra geliyorsa `P_A10` ile `P_T10` farklı mumlardır.
- **Ortak hedefte kalan:** `(P_A10 / P_T − 1) × 100`; adayın 10. kapanışına kadar teyitten sonra olan fiyat değişimi. **Teyitten kendi 10 barı:** `(P_T10 / P_T − 1) × 100`. Bunları veya farklı olayların medyanlarını çıkarıp “kesin kaçan yüzde” diye sunma.
- Karşılaştırma tablolarındaki `%` sütunları **gerçek fiyat işaretiyle** yazılır: negatif fiyat düşüşü, pozitif fiyat artışıdır. Aday/teyit performans tablolarındaki `lehe` ve `aleyhe` sütunları ise kırılım yönüne göre işaretlenir; aşağı yönde fiyatın düşmesi lehedir.
- `yol içi +2 ATR`: sonraki 10 kapanıştan herhangi birinin başlangıç fiyatından yönlü en az +2 sabit başlangıç ATR'sine ulaşmasıdır. `10. kapanış +2 ATR` bunun korunup korunmadığını ayrı gösterir. Aynı olay hem lehe hem aleyhe eşiği görebilir; intrabar sıralama ölçülmez.
- 10 adet 1s, 2s, 4s ve 1g mum **eşit takvim/işlem süresi değildir**. Bu çalışma aralıkları eşitlemez ve işlem/komisyon/short erişimi varsaymaz.

## 4. Sayımlar, sansür ve iki farklı örtüşme filtresi

| Aşama | Sayı | Açıklama |
|---|---:|---|
| İşlenen seri | 696 | 174 hisse × dört TF; hata yok |
| Ham aday | 25.457 | Teyitli 18.752, teyit alamayan 4.776, başarısız 1.907, yaşam döngüsü sansürlü 22 |
| Aday hedefi geçerli | 25.133 | 156 sınır, 152 seri sonu, 12 veri kırılması, 4 belirsiz son mum ayrıca sansürlü |
| Aday penceresi örtüşmeyen | 21.244 | Teyitli 15.947; teyit alamadı 3.577; başarısız 1.720 |
| Teyit girdisi | 18.752 | Ham adayların teyit alanları; MEGAP 1s/2s'de teyit yok |
| Teyit hedefi geçerli | 18.495 | 133 sınır, 112 seri sonu, 11 veri kırılması, 1 belirsiz son mum sansürlü |
| Teyit penceresi örtüşmeyen | 18.131 | Yalnız teyitli olaylar arasındaki 10 bar örtüşmesi kaldırılır |
| Kontrol penceresi | 99.944 | Aday olmayan anlarda eşleşmemiş 10 bar ızgara; random/matched kontrol değil |

Aday filtresinde her hisse/TF'de ilk **geçerli aday** seçilip on bar bitene kadar başka aday alınmaz. Teyit filtresinde ilk **geçerli teyitli olay** ve teyit sonrası on bar esas alınır. Farklı filtreler bu yüzden farklı sayılar üretir; 15.947 ile 18.131 aynı olay kümesi değildir. 10 bar seçiminden sonra farklı hisselerde aynı piyasa günü ve aynı hissede farklı TF'ler hâlâ bağımlı olabilir.

Aday başlıca TF kapsamı:

| TF | Ham aday | Geçerli aday hedefi | Aday penceresi çakışmayan |
|---|---:|---:|---:|
| 1 saat | 12.189 | 12.130 | 10.277 |
| 2 saat | 6.905 | 6.814 | 5.711 |
| 4 saat | 4.395 | 4.298 | 3.616 |
| Günlük | 1.968 | 1.891 | 1.640 |

## 5. Adaydan itibaren: teyitli, teyit alamadı, başarısız

Bu tabloda örneklem **aday penceresi filtresidir**; her grubun durumu daha sonra gözlendiğinden bunlar başlangıç anında bilinen etiketler değildir. `Başarısız` ile zaman aşımı ayrı gruplardır. Tüm olguların olasılığı veya teyidin nedensel etkisi değildir.

### 5.1 Keşif dönemi

| TF | Yön | Son durum | Olay/hisse | Yol içi lehe +2 ATR | Yol içi aleyhe −2 ATR | 10. kapanış lehe +2 ATR |
|---|---|---|---:|---:|---:|---:|
| 1 saat | Yukarı | Teyitli | 2.767/171 | 971/2.767 (%35,1) | 459/2.767 (%16,6) | 666/2.767 (%24,1) |
| 1 saat | Yukarı | Başarısız | 256/124 | 18/256 (%7,0) | 181/256 (%70,7) | 13/256 (%5,1) |
| 1 saat | Yukarı | Teyit alamadı | 662/168 | 112/662 (%16,9) | 155/662 (%23,4) | 79/662 (%11,9) |
| 1 saat | Aşağı | Teyitli | 2.745/172 | 753/2.745 (%27,4) | 512/2.745 (%18,7) | 498/2.745 (%18,1) |
| 1 saat | Aşağı | Başarısız | 271/130 | 3/271 (%1,1) | 208/271 (%76,8) | 3/271 (%1,1) |
| 1 saat | Aşağı | Teyit alamadı | 532/166 | 80/532 (%15,0) | 117/532 (%22,0) | 56/532 (%10,5) |
| 2 saat | Yukarı | Teyitli | 1.467/172 | 555/1.467 (%37,8) | 254/1.467 (%17,3) | 399/1.467 (%27,2) |
| 2 saat | Yukarı | Başarısız | 168/107 | 8/168 (%4,8) | 108/168 (%64,3) | 7/168 (%4,2) |
| 2 saat | Yukarı | Teyit alamadı | 426/158 | 110/426 (%25,8) | 96/426 (%22,5) | 82/426 (%19,2) |
| 2 saat | Aşağı | Teyitli | 1.466/172 | 385/1.466 (%26,3) | 324/1.466 (%22,1) | 244/1.466 (%16,6) |
| 2 saat | Aşağı | Başarısız | 191/108 | 7/191 (%3,7) | 139/191 (%72,8) | 7/191 (%3,7) |
| 2 saat | Aşağı | Teyit alamadı | 260/132 | 41/260 (%15,8) | 62/260 (%23,8) | 26/260 (%10,0) |
| 4 saat | Yukarı | Teyitli | 960/174 | 415/960 (%43,2) | 138/960 (%14,4) | 278/960 (%29,0) |
| 4 saat | Yukarı | Başarısız | 118/92 | 12/118 (%10,2) | 77/118 (%65,3) | 11/118 (%9,3) |
| 4 saat | Yukarı | Teyit alamadı | 276/141 | 89/276 (%32,2) | 63/276 (%22,8) | 57/276 (%20,7) |
| 4 saat | Aşağı | Teyitli | 896/173 | 212/896 (%23,7) | 184/896 (%20,5) | 140/896 (%15,6) |
| 4 saat | Aşağı | Başarısız | 118/88 | 4/118 (%3,4) | 85/118 (%72,0) | 2/118 (%1,7) |
| 4 saat | Aşağı | Teyit alamadı | 147/95 | 26/147 (%17,7) | 39/147 (%26,5) | 20/147 (%13,6) |
| Günlük | Yukarı | Teyitli | 420/162 | 167/420 (%39,8) | 87/420 (%20,7) | 104/420 (%24,8) |
| Günlük | Yukarı | Başarısız | 62/51 | 8/62 (%12,9) | 41/62 (%66,1) | 6/62 (%9,7) |
| Günlük | Yukarı | Teyit alamadı | 110/77 | 27/110 (%24,5) | 26/110 (%23,6) | 22/110 (%20,0) |
| Günlük | Aşağı | Teyitli | 387/158 | 94/387 (%24,3) | 89/387 (%23,0) | 56/387 (%14,5) |
| Günlük | Aşağı | Başarısız | 48/45 | 2/48 (%4,2) | 33/48 (%68,8) | 1/48 (%2,1) |
| Günlük | Aşağı | Teyit alamadı | 40/34 | 4/40 (%10,0) | 6/40 (%15,0) | 4/40 (%10,0) |

### 5.2 İleri dönem

| TF | Yön | Son durum | Olay/hisse | Yol içi lehe +2 ATR | Yol içi aleyhe −2 ATR | 10. kapanış lehe +2 ATR |
|---|---|---|---:|---:|---:|---:|
| 1 saat | Yukarı | Teyitli | 1.062/169 | 291/1.062 (%27,4) | 215/1.062 (%20,2) | 188/1.062 (%17,7) |
| 1 saat | Yukarı | Başarısız | 114/83 | 4/114 (%3,5) | 95/114 (%83,3) | 3/114 (%2,6) |
| 1 saat | Yukarı | Teyit alamadı | 298/135 | 50/298 (%16,8) | 87/298 (%29,2) | 40/298 (%13,4) |
| 1 saat | Aşağı | Teyitli | 1.237/166 | 405/1.237 (%32,7) | 221/1.237 (%17,9) | 283/1.237 (%22,9) |
| 1 saat | Aşağı | Başarısız | 99/77 | 1/99 (%1,0) | 67/99 (%67,7) | 1/99 (%1,0) |
| 1 saat | Aşağı | Teyit alamadı | 234/132 | 53/234 (%22,6) | 43/234 (%18,4) | 44/234 (%18,8) |
| 2 saat | Yukarı | Teyitli | 631/166 | 175/631 (%27,7) | 122/631 (%19,3) | 110/631 (%17,4) |
| 2 saat | Yukarı | Başarısız | 68/56 | 4/68 (%5,9) | 46/68 (%67,6) | 2/68 (%2,9) |
| 2 saat | Yukarı | Teyit alamadı | 197/120 | 31/197 (%15,7) | 55/197 (%27,9) | 25/197 (%12,7) |
| 2 saat | Aşağı | Teyitli | 672/160 | 261/672 (%38,8) | 99/672 (%14,7) | 195/672 (%29,0) |
| 2 saat | Aşağı | Başarısız | 65/59 | 7/65 (%10,8) | 33/65 (%50,8) | 4/65 (%6,2) |
| 2 saat | Aşağı | Teyit alamadı | 100/77 | 30/100 (%30,0) | 15/100 (%15,0) | 28/100 (%28,0) |
| 4 saat | Yukarı | Teyitli | 426/157 | 110/426 (%25,8) | 102/426 (%23,9) | 56/426 (%13,1) |
| 4 saat | Yukarı | Başarısız | 51/46 | 1/51 (%2,0) | 39/51 (%76,5) | 1/51 (%2,0) |
| 4 saat | Yukarı | Teyit alamadı | 149/108 | 23/149 (%15,4) | 47/149 (%31,5) | 13/149 (%8,7) |
| 4 saat | Aşağı | Teyitli | 377/154 | 186/377 (%49,3) | 35/377 (%9,3) | 141/377 (%37,4) |
| 4 saat | Aşağı | Başarısız | 33/32 | 0/33 (%0,0) | 19/33 (%57,6) | 0/33 (%0,0) |
| 4 saat | Aşağı | Teyit alamadı | 65/53 | 20/65 (%30,8) | 9/65 (%13,8) | 14/65 (%21,5) |
| Günlük | Yukarı | Teyitli | 215/134 | 66/215 (%30,7) | 67/215 (%31,2) | 33/215 (%15,3) |
| Günlük | Yukarı | Başarısız | 32/30 | 2/32 (%6,2) | 25/32 (%78,1) | 2/32 (%6,2) |
| Günlük | Yukarı | Teyit alamadı | 64/47 | 15/64 (%23,4) | 14/64 (%21,9) | 12/64 (%18,8) |
| Günlük | Aşağı | Teyitli | 219/134 | 69/219 (%31,5) | 39/219 (%17,8) | 52/219 (%23,7) |
| Günlük | Aşağı | Başarısız | 26/25 | 2/26 (%7,7) | 14/26 (%53,8) | 2/26 (%7,7) |
| Günlük | Aşağı | Teyit alamadı | 17/17 | 5/17 (%29,4) | 3/17 (%17,6) | 4/17 (%23,5) |

## 6. Teyitten sonraki hareket: yön, zaman, lehte ve aleyhte

Bu bölümde başlangıç **teyit kapanışı** ve sabit `ATR_T`; sonraki 10 kapanış ölçülür. Örtüşme filtresi yalnız teyitli olaylarda kullanılır. “Medyan ATR” yönlüdür: aşağı teyitte pozitif, fiyat düşüşüdür. “Medyan fiyat %” ise gerçek fiyat işaretiyle yazılır.

### 6.1 Keşif dönemi

| TF | Yön | Olay/hisse | Teyit→10. kapanış medyan fiyat | Medyan ATR | Lehe +2 ATR yol | Aleyhe −2 ATR yol | 10. kapanışta lehe +2 ATR |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 saat | Yukarı | 3.140/171 | %+0,00 | +0,00 | 903/3.140 (%28,8) | 679/3.140 (%21,6) | 627/3.140 (%20,0) |
| 1 saat | Aşağı | 3.093/172 | %-0,05 | +0,04 | 712/3.093 (%23,0) | 751/3.093 (%24,3) | 455/3.093 (%14,7) |
| 2 saat | Yukarı | 1.728/172 | %+0,43 | +0,33 | 604/1.728 (%35,0) | 375/1.728 (%21,7) | 410/1.728 (%23,7) |
| 2 saat | Aşağı | 1.639/172 | %+0,00 | +0,00 | 352/1.639 (%21,5) | 457/1.639 (%27,9) | 230/1.639 (%14,0) |
| 4 saat | Yukarı | 1.120/174 | %+0,54 | +0,31 | 393/1.120 (%35,1) | 207/1.120 (%18,5) | 273/1.120 (%24,4) |
| 4 saat | Aşağı | 996/173 | %+0,07 | -0,03 | 205/996 (%20,6) | 252/996 (%25,3) | 136/996 (%13,7) |
| Günlük | Yukarı | 476/170 | %+0,07 | +0,02 | 161/476 (%33,8) | 121/476 (%25,4) | 108/476 (%22,7) |
| Günlük | Aşağı | 409/160 | %+0,57 | -0,15 | 77/409 (%18,8) | 123/409 (%30,1) | 48/409 (%11,7) |

### 6.2 İleri dönem

| TF | Yön | Olay/hisse | Teyit→10. kapanış medyan fiyat | Medyan ATR | Lehe +2 ATR yol | Aleyhe −2 ATR yol | 10. kapanışta lehe +2 ATR |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 saat | Yukarı | 1.239/170 | %-0,25 | -0,19 | 304/1.239 (%24,5) | 309/1.239 (%24,9) | 196/1.239 (%15,8) |
| 1 saat | Aşağı | 1.402/166 | %-0,56 | +0,53 | 411/1.402 (%29,3) | 313/1.402 (%22,3) | 283/1.402 (%20,2) |
| 2 saat | Yukarı | 744/168 | %-0,59 | -0,37 | 178/744 (%23,9) | 177/744 (%23,8) | 107/744 (%14,4) |
| 2 saat | Aşağı | 741/162 | %-1,01 | +0,66 | 250/741 (%33,7) | 141/741 (%19,0) | 192/741 (%25,9) |
| 4 saat | Yukarı | 516/167 | %-1,41 | -0,67 | 102/516 (%19,8) | 165/516 (%32,0) | 65/516 (%12,6) |
| 4 saat | Aşağı | 415/159 | %-1,49 | +0,81 | 173/415 (%41,7) | 58/415 (%14,0) | 132/415 (%31,8) |
| Günlük | Yukarı | 243/147 | %-2,28 | -0,58 | 61/243 (%25,1) | 90/243 (%37,0) | 33/243 (%13,6) |
| Günlük | Aşağı | 230/136 | %-1,23 | +0,34 | 67/230 (%29,1) | 49/230 (%21,3) | 49/230 (%21,3) |

İleri dönem 4s aşağı için 173/415 yol içi +2 ATR, ancak 132/415 onuncu kapanışta lehe +2 ATR'dir; tepe hareketi bütünüyle korunmuş sayılmaz. 4s yukarı %19,8 lehe, %32,0 aleyhe −2 ATR yol eşiği görmüştür. Keşifte 4s yukarı lehe +2 ATR %35,1, aşağı %20,6 iken ileri dönemde sırasıyla %19,8 ve %41,7'dir. Aynı piyasa günlerinde hisseler birlikte hareket edebildiğinden bu farkları kesin sistem üstünlüğü veya karneye taşınacak olasılık sayma.

## 7. Aynı olaylarda aday–teyit karşılaştırması

Her tabloda iki kaynak **sembol + TF + temiz segment başlangıcı + aday bar indeksi** ile bire bir birleştirildi; yön, dönem, aday ve teyit zamanları ayrıca eşitlik kontrolünden geçti. Her iki hedefi gözlenebilir teyitlerin teyit penceresi çakışmayanları seçildi. Böylece aynı satırın tüm sütunları aynı olay kümesidir. Sayılar **medyan gerçek fiyat değişimi**, artı yükseliş, eksi düşüştür.

- `Aday→teyit`: `P_A` ile `P_T` arası.
- `Aday→adayın 10. kapanışı`: `P_A` ile `P_A10` arası.
- `Teyit→aynı aday 10. kapanışı`: `P_T` ile **aynı** `P_A10` arası; adayın ufku teyitten sonra 8–9 bar kalabilir.
- `Teyit→teyidin 10. kapanışı`: `P_T` ile `P_T10` arası; `P_A10` ile aynı bitiş değildir.

### 7.1 Keşif dönemi

| TF | Yön | Olay/hisse | Aday→teyit | Aday→adayın 10. kapanışı | Teyit→aynı aday 10. kapanışı | Teyit→teyidin 10. kapanışı |
|---|---|---:|---:|---:|---:|---:|
| 1 saat | Yukarı | 3.140/171 | %+0,22 | %+0,36 | %+0,00 | %+0,00 |
| 1 saat | Aşağı | 3.093/172 | %-0,24 | %-0,39 | %-0,11 | %-0,05 |
| 2 saat | Yukarı | 1.728/172 | %+0,32 | %+0,70 | %+0,33 | %+0,43 |
| 2 saat | Aşağı | 1.639/172 | %-0,30 | %-0,29 | %+0,00 | %+0,00 |
| 4 saat | Yukarı | 1.120/174 | %+0,41 | %+1,14 | %+0,46 | %+0,54 |
| 4 saat | Aşağı | 996/173 | %-0,39 | %-0,41 | %+0,06 | %+0,07 |
| Günlük | Yukarı | 476/170 | %+1,20 | %+1,34 | %-0,24 | %+0,07 |
| Günlük | Aşağı | 409/160 | %-0,90 | %-0,49 | %+0,72 | %+0,57 |

### 7.2 İleri dönem

| TF | Yön | Olay/hisse | Aday→teyit | Aday→adayın 10. kapanışı | Teyit→aynı aday 10. kapanışı | Teyit→teyidin 10. kapanışı |
|---|---|---:|---:|---:|---:|---:|
| 1 saat | Yukarı | 1.239/170 | %+0,17 | %+0,00 | %-0,26 | %-0,25 |
| 1 saat | Aşağı | 1.402/166 | %-0,30 | %-0,81 | %-0,54 | %-0,56 |
| 2 saat | Yukarı | 744/168 | %+0,28 | %-0,15 | %-0,60 | %-0,59 |
| 2 saat | Aşağı | 741/162 | %-0,40 | %-1,33 | %-0,86 | %-1,01 |
| 4 saat | Yukarı | 516/167 | %+0,27 | %-0,71 | %-1,16 | %-1,41 |
| 4 saat | Aşağı | 415/159 | %-0,65 | %-2,35 | %-1,62 | %-1,49 |
| Günlük | Yukarı | 243/147 | %+1,11 | %-1,42 | %-2,78 | %-2,28 |
| Günlük | Aşağı | 230/136 | %-1,30 | %-2,25 | %-0,67 | %-1,23 |

Örneğin ileri 1s aşağıda 1.402 olayın aday→aday 10. kapanış medyanı −%0,81, teyit→aynı aday 10. kapanış medyanı −%0,54'tür. Bunlar ayrı olay dağılımlarının ortancalarıdır; `−0,81 − (−0,54)` bir “kesin kaçan getiri” değildir. Ayrıca aday başlangıcı hareketin gerçek başlangıcı olmayabilir. Teyit oluşmadan önce kaç hareketin meydana geldiği ve hareketin formasyon/adaydan önce başlaması başka çalışmadır.

## 8. Eşleşmemiş kontrol pencereleri

Her temiz segmentte 80 mum ısınma, sonrasında ilk 10 barlık ızgara noktası da atlanarak her 10 barda bir başlangıç seçilir; o anda kaydedilmiş aday süren noktalar çıkarılır. Bu **rastgele veya adayla tarih/hisse/rejim eşleşmiş** kontrol değildir; aktif formasyonun yokluğunu da garanti etmez. Aday ve kontrol arasında görülen farkı doğrudan teyidin katkısı sayamayız.

### 8.1 Keşif dönemi

| TF | Yön | Kontrol penceresi / hisse | Yol içi +2 ATR | 10. kapanışta +2 ATR |
|---|---|---:|---:|---:|
| 1 saat | Yukarı | 35.027/174 | 9.398/35.027 (%26,8) | 6.582/35.027 (%18,8) |
| 1 saat | Aşağı | 35.027/174 | 7.450/35.027 (%21,3) | 5.251/35.027 (%15,0) |
| 2 saat | Yukarı | 18.741/174 | 5.460/18.741 (%29,1) | 3.823/18.741 (%20,4) |
| 2 saat | Aşağı | 18.741/174 | 4.112/18.741 (%21,9) | 2.841/18.741 (%15,2) |
| 4 saat | Yukarı | 10.564/174 | 3.265/10.564 (%30,9) | 2.260/10.564 (%21,4) |
| 4 saat | Aşağı | 10.564/174 | 2.238/10.564 (%21,2) | 1.482/10.564 (%14,0) |
| Günlük | Yukarı | 4.074/174 | 1.288/4.074 (%31,6) | 901/4.074 (%22,1) |
| Günlük | Aşağı | 4.074/174 | 918/4.074 (%22,5) | 586/4.074 (%14,4) |

### 8.2 İleri dönem

| TF | Yön | Kontrol penceresi / hisse | Yol içi +2 ATR | 10. kapanışta +2 ATR |
|---|---|---:|---:|---:|
| 1 saat | Yukarı | 15.617/174 | 3.219/15.617 (%20,6) | 2.103/15.617 (%13,5) |
| 1 saat | Aşağı | 15.617/174 | 4.480/15.617 (%28,7) | 3.227/15.617 (%20,7) |
| 2 saat | Yukarı | 8.695/174 | 1.952/8.695 (%22,4) | 1.202/8.695 (%13,8) |
| 2 saat | Aşağı | 8.695/174 | 2.624/8.695 (%30,2) | 1.910/8.695 (%22,0) |
| 4 saat | Yukarı | 4.996/174 | 1.046/4.996 (%20,9) | 652/4.996 (%13,1) |
| 4 saat | Aşağı | 4.996/174 | 1.610/4.996 (%32,2) | 1.145/4.996 (%22,9) |
| Günlük | Yukarı | 2.230/174 | 515/2.230 (%23,1) | 281/2.230 (%12,6) |
| Günlük | Aşağı | 2.230/174 | 646/2.230 (%29,0) | 433/2.230 (%19,4) |

Kontrollerde 650 dönem sınırı, 700 segment sonu, 3 belirsiz son native mum sansürü; 6.834 ızgara noktası sürmekte olan aday nedeniyle dışlanmıştır. Aynı olay iki yönün eşiğini de görebilir.

## 9. Hesap denetimi ve anti-lookahead sınırı

- Takip kontrolünde sınır doğrusal interpolasyonu ve beş skor bileşeni (gövde, kapanış yeri, çizgi aşımı, mum genişliği, hacim) ayrı referans ifadelerle hesaplandı. **45.255 kontrol**, maksimum fark **1,82×10⁻¹²**; >10⁻⁹ fark yok. Kontrollerin bir kısmı 80 bar ısınma sırasında başlayan adaylara aittir; aday tablosuna alınmamıştır.
- Aday tablosuyla eşleşen 18.752 teyitte: yalnız **güçlü aynı-yön koşulu** 9.930, yalnız **retest** 4.755, her ikisi 4.067. Güç koşulu, hem kapanışın tampon dışında olmasını hem de puanın eşiği geçmesini gerektirir; sadece puan geçmesi yeterli değildir. Önceki rapordaki 4.713/4.109 dağılımı bu nedenle düzeltildi: 42 olayda puan geçse de aynı-yön koşulu yoktu; doğru grup yalnız retesttir.
- Kontrol edilen teyit yaş/pencere ve güç veya retest koşullarında hata görülmedi. Tüm motor durum geçişleri, aday başlangıç puanının her bileşeni, doğrulanmış seans verisi ve Pine kaynak eşdeğerliği tamamen bağımsız sınanmadı.
- İlk prototip tüm seriyle tek çalıştırıldığında motorun tarihçe sınırı `len(close)` üzerinden gelecekteki seri uzunluğundan etkilendi: THYAO 1s'de 17 Aralık 2025'e kadar korumasız uzun seri 66, önek 38 aday verdi. Bu fark doğrudan canlı sistemin gelecek fiyatı gördüğünü kanıtlamaz; geçmişi sınırsız tam frame ile saymanın tehlikesidir.
- Araştırma sarmalayıcısı her bar işlenirken OHLCV/ATR dizilerinde yalnız o ana kadar olan elemanları görünür kılar. 1.453 örnek önek karşılaştırmasında aday zamanı/türü/yönü/kalıbı eşleşti; uzun seride geleceği değiştirme ve üç örnekte gerçek tek tek artımlı yürütme testleri geçti. Örnekler tüm durumların as-of doğruluğunu garanti etmez.
- Canlı taramada `tam_yeniden=True` ve kayan pencere kullanılır. Bu artımlı araştırma **canlının birebir yeniden oynatımı değil**; gerçek veri geliş zamanı, alarm kararı, susturma, Telegram teslim zamanı ve geçmiş loglar ayrıca doğrulanmalıdır.

## 10. Tekil vaka kayıtları

### THYAO günlük, 12 Haziran 2026: aday ama teyit yok

Aday kapanışı **307,75**, aday ATR'si **8,4564**. 15 ve 16 Haziran takip skorları **33,01** ve **35,55**, teyit eşiği **44**; o kontrollere göre retest yok. 17 Haziran pencere dolunca teyit alamadı. Adayın 10. kapanışı 26 Haziran'da **330,75**, yaklaşık **+2,72 ATR**. Bu seçili örnekte neden açıklanıyor; kuralın hata olduğu veya alarm/işlem gerçekleştiği kanıtlanmıyor. Teyit almadığından teyit sonrası örneklemine girmez.

### THYAO günlük, 6 Temmuz 2026: teyitli ama devam etmeyen örnek

Yukarı teyit kapanışı **347,00**; teyitten sonraki 10. kapanış 21 Temmuz'da **317,50**, **−%8,50**, yaklaşık **−3,55 teyit ATR'si**. Tekil karşı örnek; genelleme, emir veya teslim kaydı değildir.

### THYAO 1 saat, 14 Eylül 2026: aynı bitiş üzerinden karşılaştırma

Kaynak **bar etiketleri** 14 Eylül 09:30 ve 10:30 olan mumların kapanışları kullanılır; bunlar gerçek teslim anı olarak sunulmaz.

| Aşama | Kapanış | Açıklama |
|---|---:|---|
| Aşağı aday | 297,25 | Başlangıç |
| Teyit | 296,25 | Adaydan −%0,34 |
| Adaydan sonraki 10. kapanış, 15 Eylül 10:30 etiketi | 290,75 | Adaydan −%2,19; teyitten **aynı kapanışa** −%1,86 |
| Teyitten sonraki 10. kapanış, 15 Eylül 11:30 etiketi | 291,00 | Teyitten −%1,77; farklı bitiş mumu |

Örnek seçilmiştir, tüm olayların tipik davranışı değildir. Sağlayıcı bar etiketinin gerçek kapanış/erişim zamanı ve canlı teslim ayrıca doğrulanmadı.

## 11. Neler sonuç, neler henüz soru?

**Gözlenen:** Seçili takip hesapları matematiksel olarak tutarlı; adaydan sonraki sonuçta teyitli gruplar bu koşullu tabloların her ileri hücresinde teyit alamayan gruptan daha yüksek lehe +2 ATR oranı gösterdi. Teyitsiz bazı adaylar da ilerledi. Teyit sonrası 4s yukarı/aşağı sonuçları dönemlere göre ciddi değişti.

**Kanıtlanmayan:** strateji getirisi, teyidin nedensel katkısı, en iyi TF, eşik değişikliği, gerçek bildirim/teslim, tüm BIST için genelleme, Pine eşitliği, seans kusursuzluğu, tüm tarihçede rolling-rebuild eşitliği ve sonuçların kalıcı olarak tekrarlanması. Çoklu hücre incelemesi ve hisse/gün bağımlılığı için güven aralığı veya çoklu test düzeltmesi yapılmadı.

**Araştırma olarak sonraki adımlar:**
1. Teyit sonrası 10 mum yerine TF'leri aynı 1/2/5 işlem günü ufkunda ve doğrulanmış seans takvimiyle karşılaştır.
2. 1s/2s adayının teyit anında sadece gerçekten kapanmış 4s/günlük yapıyı uyumlu/ters/nötr/UNKNOWN olarak gölgede dene; etiket saatini erişim zamanı sayma.
3. Önceden tanımlanmış hareket başlangıcıyla aday öncesi, aday→teyit ve teyit sonrası bölümleri aynı fiyat penceresinde ölç; eşleşmiş kontrol, ileri dönem ve hisse/zaman blokları kullan.
4. Fazladan/kaçırılan alarm ve yanlış teyitleri gerçek arşiv/loglarla ölç; herhangi bir eşik veya bildirim değişikliğinden önce ayrıca onay ve gölge doğrulama gerekir.

## 12. Veriler, kolonlar ve tekrar üretim

### 12.1 Ham ve özet dosyaları

| Dosya | İçerik |
|---|---|
| [Adaylar](sonuclar/kirilim_replay/adaylar.csv.gz) | 25.457 aday; durum, zaman, fiyat, ATR, 10 bar hedef, sansür ve aday örtüşme bayrağı |
| [Teyit kontrolleri](sonuclar/kirilim_replay/teyit_kontrolleri.csv.gz) | 45.255 takip; skor bileşenleri, çizgi, eşik, retest ve değişmez sonucu |
| [Teyit nedenleri: olaylar](sonuclar/teyit_nedenleri/olaylar.csv.gz) · [TF/dönem/yön özeti](sonuclar/teyit_nedenleri/ozet.csv) · [manifest](sonuclar/teyit_nedenleri/manifest.json) | 18.752 teyitte güçlü aynı-yön ve retest koşullarının ayrı sayımı |
| [Aday grup özeti](sonuclar/kirilim_replay/ozet.csv) | TF/dönem/yön/durum; aday penceresi örtüşmeyen gruplar |
| [Aday ilk iki mum](sonuclar/kirilim_replay/iki_mum.csv.gz) · [özet](sonuclar/kirilim_replay/iki_mum_ozet.csv) | İlk 2 kapanışın lehte/aleyhte gelişimi |
| [Kontrol pencereleri](sonuclar/kirilim_replay/kontroller.csv.gz) · [özet](sonuclar/kirilim_replay/kontrol_ozet.csv) · [manifest](sonuclar/kirilim_replay/kontrol_manifest.json) | Eşleşmemiş kontrol ve sansür sayıları |
| [Teyit sonrası olaylar](sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz) · [özet](sonuclar/teyit_sonrasi/ozet.csv) · [manifest](sonuclar/teyit_sonrasi/manifest.json) | Teyitten sonraki 1/2/5/10 kapanış, ATR/yüzde ve yol eşikleri |
| [Aday–teyit eşleştirilmiş olaylar](sonuclar/aday_teyit_karsilastirma/olaylar.csv.gz) · [grup özeti](sonuclar/aday_teyit_karsilastirma/ozet.csv) · [hisse/TF özeti](sonuclar/aday_teyit_karsilastirma/hisse_tf_ozet.csv) · [manifest](sonuclar/aday_teyit_karsilastirma/manifest.json) | Aynı olaylarda dört fiyat yüzdesi; ham geçerli ve teyit penceresi örtüşmeyen seçim |
| [Kaynak hacim profili](sonuclar/kirilim_replay/kaynak_veri_profili.csv) · [kova profili](sonuclar/kirilim_replay/kova_veri_profili.csv) · [ana manifest](sonuclar/kirilim_replay/manifest.json) | Kaynak sayıları, TF kova sayıları, veri/kod hashleri ve seri kapsamı |

Eşleştirilmiş dosyada `candidate_to_confirm_pct`, `candidate_to_candidate_end_pct`, `confirm_to_candidate_end_pct` ve `confirm_to_confirm_end_pct` **gerçek fiyat işaretli** yüzdelerdir. `candidate_end_time` ve `end_time` iki farklı hedefi, `candidate_nonoverlap` ve `nonoverlap` iki farklı seçim bayrağını gösterir. `ozet.csv` içinde `raw_valid` ve `confirm_nonoverlap` ayrı; medyan ve %10/%25/%75/%90 yüzdelikler mevcuttur. Hisse bazlı küçük n'ler güvenilir tekil sıralama olarak okunmamalıdır.

### 12.2 Üretim sırası

Tüm arşivin araştırma Replay'i CPU ve zaman tüketir. Yeniden üretim ham veriyi değiştirmez; varsayılan çıktı dizinlerine yeniden yazar. Eski çıktıyı korumak için kopyala veya `--output` ile yeni dizinler ve takip eden aşamalarda bu dizinleri kullan. Çalışılan checkout'un ve Python bağımlılıklarının hashlerini manifestle karşılaştır.

```bash
mkdir -p var
WORKDIR=$(mktemp -d var/kirilim-replay-XXXXXX)
python scripts/kirilim_replay.py --workers 2 --workdir "$WORKDIR"
python scripts/kirilim_sonuc_sansuru.py --workdir "$WORKDIR/checkpoints"
python scripts/kirilim_kontrolleri.py
python scripts/kirilim_iki_mum.py
python scripts/kirilim_veri_profili.py
python scripts/kirilim_teyit_sonrasi.py
python scripts/kirilim_aday_teyit_karsilastirma.py
python scripts/kirilim_teyit_nedenleri.py
python -m pytest -q test_kirilim_denetim.py test_kirilim_teyit_sonrasi.py test_kirilim_aday_teyit_karsilastirma.py test_kirilim_teyit_nedenleri.py
```

Checkpoint geçersizleştirmesi 1s/1g kaynak ve iki ana araştırma dosyasını kontrol eder, fakat motor/config dâhil bütün bağımlılıkları otomatik kontrol etmez: tam tekrar için yeni `WORKDIR` kullan. Manifestteki checkpoint yazılma aralığı kesin gerçek işlem başlangıç saati değildir. Çıktıların üretilme koşulları/kodları bu dosyalar ve ilişkili manifestlerle birlikte korunur.
