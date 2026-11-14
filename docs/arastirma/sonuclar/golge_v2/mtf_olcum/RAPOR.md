# D7 — işlem içi MTF ve kâr koruma karşılaştırması

## Sonuç

Önceden belirlenen MTF ve kâr koruma varyantları 601 ortak işlemde kıyaslandı. Test edilen kâr koruma kuralları tüm örneklemde baz beklentisini artırmadı. İki fiyat teyidine dayalı MTF sinyalinden sonra başa başa koruma, tüm örneklemde +0,0076 R/işlem iyileşti; ancak ileri dönemde −0,0127 R/işlem geriledi, hisse-bloklu belirsizlik aralığı sıfırı içerdi. Bu nedenle iyileşme doğrulanmış değil ve canlıya önerilmiyor.

## Kapsam ve yöntem

Mevcut D7 648 olayından 601'inde yeterli saatlik arşiv vardı (441 4s, 160 günlük; 375 keşif, 226 doğrulama). Kalan 47 olay dışlandı: 43'ünde ufuk günü saatlik veri yok, 4'ünde ufka kadar günlük arşivde görülen bir işlem günü saatlik arşivde hiç yok. Seans içi eksik saatlerin tümü ayrıca sertifikalandırılmadı. Kaynak kapanış saatleri de repo'nun BIST kapanış varsayımlarına dayanır; arşiv bütünlüğü/kapanışların gerçek piyasa sertifikasyonu değildir.

Aynı 601 olay, aynı giriş/ilk stop, 2 ATR hedef ve 10 özgün TF barlık zaman ufku; tüm varyantlar aynı saatlik OHLCV akışıyla kıyaslanır. Net getiri giriş+çıkış toplam %0,30 maliyet sonrasıdır. Basit işlem başı R ortalamasıdır; sermaye kısıtlı portföyün veya mevduat karşısında TL getirisinin yerine geçmez.

Saatlik ortak baz: **+0,1334 R**. Eski 4s/günlük mumlarla üretilen D7 bazında aynı 601 işlem **+0,1352 R**; mutlak işlem başına ortalama fark 0,0031 R. Günlük native ve saatlik arşiv farklıdır; günlük ufuk kapanışı 18:30, son saatlik kapanış sıklıkla 18:00'dır. Bazın farklı olması saatlik mum sırası, saatlik gap ve kaynak farklarıyla ilgilidir. Ortalamaların yakınlığı her işlemde eşitlik anlamına gelmez. Karşılaştırma yalnız yeni ortak bazla yapılmalıdır.

## MTF tanımı ve uygulama

* Long için 2s düşüş, short için aynalı yükseliş: son 2s kapanışında bir önceki 2s kapanışına göre en az 0,5 mevcut 2s ATR ters hareket; **veya** ayrı varyantta 2s yeni ters external BOS/CHoCH.
* Bununla birlikte 1s yeni ters external BOS/CHoCH **veya** 4s ters fiyat hareketi/ters MS durumu. İki ayrı 4s teyit türü ve iki ayrı 2s tanımı test edildi.
* Snapshot yalnız kapanışından sonra ve pozisyon açılışından sonra kullanılır. İlk deneyde aynı işlem gününden olma ve en fazla 1s/2s/4s yaş koşulları uygulanır. Sinyal sürekli güncellenen en son kapanmış snapshot üzerinden değerlendirilir; önceki 1s olayı daha yeni bir 1s barı oluşunca saklanmaz. 0,5 ATR ve tazelikler araştırma varsayımıdır.
* Doğrudan çıkış, sinyal sonrası **sonraki saatlik açılış** fiyatındandır. Kâr koruma varyantında uygun sinyalle pozisyon kârdaysa stop başa başa taşınır; yeni stop sonraki saatlik bardan geçerlidir. Alternatif olarak +1R/+1,5R görüldükten sonra girişe veya +0,25R'ye stop taşıma kolları da ayrı test edildi. Uygulanan saatlik mum aynı anda stop ve hedefe değerse stop önceliklidir. Gap stopta açılıştan gerçekleşir. Maliyet ve gap yüzünden kâr garantisi yoktur.
* MTF'nin hemen etkin olduğu ve önce +0,5R görülmesini bekleyen kollar ayrı test edildi. Son barda bekleyen çıkış için zaman ufku kapanışı kullanılır. Eski D7'nin üç barlık ters MS iptali bu 648 baz işlemde tetiklenmemiştir; yeni saatlik ortak bazda ayrıca işlenmedi.

## Eşleşmiş sonuçlar: 601 işlem

| Varyant | Net ort. R | Baz farkı | Kazanç oranı | MTF sinyali görülen işlem |
|---|---:|---:|---:|---:|
| Saatlik ortak baz | +0,1334 | — | %51,6 | — |
| +1R sonrası stop başa baş | +0,1268 | −0,0066 | — | — |
| +1R sonrası stop +0,25R | +0,1289 | −0,0046 | %55,9 | — |
| +1,5R sonrası stop başa baş | +0,1213 | −0,0121 | — | — |
| +1,5R sonrası stop +0,25R | +0,1264 | −0,0070 | — | — |
| 2s ve 4s ters fiyat teyidi; hemen çık | +0,1061 | −0,0273 | %46,8 | 187 |
| Aynı teyit; +0,5R sonrası çık | +0,1328 | −0,0006 | %51,7 | 93 |
| Aynı teyit; +0,5R sonrası kârdayken başa baş koru | +0,1410 | +0,0076 | %49,8 | 93 |
| 2s ters fiyat + (1s ters olay veya 4s ters MS); hemen çık | +0,1340 | +0,0006 | %51,6 | 14 |
| MTF başa baş koruma + +1R'de +0,25R koruma | +0,1270 | −0,0065 | %54,6 | 74 |

Hemen çıkış kolunda 187 sinyalden 186'sı sonraki açılış çıkışı, biri ufukta bekleyen sinyaldir. MTF koruma kolunda 93 uyarıdan yalnız 20 işlemde çıkış nedeni bazdan farklıydı; kârda olmayan uyarılarda stop sıkılmaz, ayrıca stop hiç tetiklenmeyebilir. +1R/+0,25R koruması kazanç oranını artırırken hedefe ulaşan işlemleri 254'ten 226'ya indirdi; daha yüksek kazanma yüzdesi daha yüksek beklenti demek değil.

## Keşif / ileri dönem

| Varyant | Keşif 375 | Doğrulama 226 |
|---|---:|---:|
| Baz | +0,0744 R | +0,2313 R |
| +1R → +0,25R | +0,1020 R | +0,1734 R |
| 2s/4s fiyat teyidi, +0,5R sonrası kârdayken başa baş | +0,0942 R | +0,2186 R |
| 2s/4s fiyat teyidi, hemen çık | +0,0463 R | +0,2055 R |

İlk iki alternatif keşifte iyileşirken ileri dönemde kötüleşti. 2s ters yapısal olayına dayalı ve 4s ters MS durumunu kullanan doğrudan çıkış kolu yalnız **1 işlemde** sinyal üretti; dolayısıyla bu koşulların değeri hakkında güçlü sonuç çıkarılamaz.

Hisse-bloklu bootstrap, 3.000 çekiliş ve seed 42 ile eşleşmiş ortalama fark için %95 yüzdelik aralıkları: +1R/+0,25R koruması [−0,0492; +0,0394], 2s/4s fiyat teyitli başa baş koruma [−0,0152; +0,0303], 2s fiyat + 4s MS/1s olay çıkışı [−0,0080; +0,0086] R. Aynı piyasa günündeki korelasyon tam modellenmedi. Çok sayıda varyant (37) denendiği için en iyi gözlenen sonuca ayrıca seçim yanlılığı uygulanır.

## Doğrulama ve tekrar

MTF, iptal ve v2 birim/kesme testleri 23/23 geçti. THYAO üzerinde 1s/2s/4s MS snapshotları için tek ön-ek kesme testi geçmişte fark göstermedi; bu bütün sembol ve kesimler için kanıt değildir. Kod: `python -m research.golge_v2_mtf_olcum --workers 2`. `olaylar.csv.gz` eşleşmiş olay/kol sonuçları, `ozet.json` tüm varyant ve dönem özetleridir. Ana ürün motoru değiştirilmedi.
