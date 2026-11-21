# İki OB arasında sıkışma: büyük olan gerçekten fiyatı itiyor mu?

**19.697 ayrı koridor, 176 sembol, 704 native seri.** Büyük olan taraf kuvvetli bir yön tahmincisi çıkmadı. Fiyat önce çoğunlukla yakın kenarı deniyor. Bir bandı *tamamen* aşmak söz konusu olduğunda ince taraf daha sık geçiliyor; bu, o yönde eşit mesafeli bir harekete avantaj olduğu anlamına gelmiyor.

## Deney

Her kapanışta mevcut OB motorunun seçtiği en yakın aktif yükseliş ve düşüş kayıtları kullanıldı. Alt yükseliş OB’sinin **kalan üst sınırı** ile üst düşüş OB’sinin **kalan alt sınırı** arasında arka arkaya iki kapanış ve her ikisinde en fazla 2 Wilder ATR(14) boşluk arandı. Bant içinde veya tam sınırda kapanış sayılmadı. Aynı kaynak mumlu çift her sembol/periyotta bir kez; olay sonrasındaki 12 bar boyunca ikinci gözlem yok. Olay anındaki dört kenar donduruldu: sonraki motor güncellemeleri ilk koşulu değiştirmiyor. Tarihler İstanbul mum etiketidir (2024-11-21 – 2026-11-18); kesin işlem saati değildir. Sonucu gözlemek için tam 12 ileri mum şarttır. 2s/4s native, yeniden örneklenmedi.

**Büyük iter** = destek bandı kalınsa yukarı, direnç kalınsa aşağı. **Büyüklük** o anki kalan bandın fiyat genişliğidir; aynı sembol ve mumda oran ATR biriminde de aynıdır. Orijinal genişlikle de ayrıca sınandı. **Belirgin fark** = kalın bant ince bandın en az 1,5 katı. Bu koşul 12.644 olayda var.

| Yönü nasıl tanımladık? | Büyük iter: doğru / yönü belli olay | Sonuç |
|---|---:|---|
| İç koridordan ilk kapanış hangi tarafa? | 6.262 / 12.065 = **%51,9** | Kenar ötesinde kapanış, bloğun tamamen kırılması değildir. 579 olayda çıkış yok. |
| Hangi OB’nin **dış kenarı** önce kapanışla aşıldı? | 5.572 / 8.986 = **%62,0** | Yön çözüldüyse ince blok daha sık aşıldı. 3.658 olayda iki dış kenar da aşılmadı. |
| Başlangıç kapanışından **eşit uzaklıkta ±1 ATR** hangisine önce gidildi? | 6.075 / 12.228 = **%49,7** | 283 olayda eşik yok, 133 olayda aynı mumda iki eşik var; sıralanamaz. |

İlk kapanışın ham yön dengesini de hesaba katmak gerekir: belirgin grupta çözülen 12.065 iç çıkışın 6.718’i aşağı. Her şeye “aşağı” demek bile bu örneklemde %55,7; %51,9’a tek başına başarı demek yanlış. Simetrik ölçüde ise 6.246 yukarı, 5.982 aşağı. Bütün oranlar çözülen, kuralın tahmin ürettiği olaylar üzerindendir; toplam, pas ve çözülmeyenler [sayım dosyasından](KIYAS.csv) ayrılabilir.

## Boyut mu, yakınlık mı? Aynı olayda karşı karşıya

- **Boyut ve yakınlık zıt yön gösterince:** 1,5× fark olan, iki kuralın ters yön söylediği 5.702 olay var. Yönü belli **5.430** ilk çıkışta yakın iç kenar **3.485 (%64,2)**, büyük blok itmesi **1.945 (%35,8)** kez doğru. Aynı grupta dış kenar için %50,9 / %49,1; simetrik 1 ATR için %51,2 / %48,8. **İlk sınır testi trend tahmini değil.**
- **Dış kenara ulaşmak için gereken mesafe:** Tüm belirgin grupta başlangıca yakın **dış** sınır %66,0 doğru (5.885/8.923). Fiyat iki dış kenar arasının ortadaki %10’undaysa, büyük iter kuralı **801/1.647 = %48,6**. Dış kenarların uzaklığı hesaba katılınca %62 bağımsız blok gücü gibi görünmüyor.
- **Farkı artırınca:** Kalan bant oranı ≥2 olunca büyük iter kuralı iç çıkışta %52,8, dış sınırda %65,7, simetrik harekette %49,9. Ayrıca son üç mumun yüksek–düşük aralığı önceki üç mumdan dar olan belirgin koridorlarda aynı üç oran %53,2 / %63,3 / %49,9. Sadece dar alanda gezinmekle fiilî daralma ayrı ayrı kontrol edildi.

## Başka neyi denedik?

Belirgin grupta **ilk iç çıkış / simetrik 1 ATR** doğruluğu: yakın iç kenar **%64,9 / %50,8**; daha az test edilmiş OB’nin itmesi **%58,7 / %52,0**; son üç mumun net yönü **%56,8 / %51,6**; kaynak mumu daha yeni olan OB’nin itmesi **%54,3 / %51,5**; dolum oranı düşük OB’nin itmesi **%53,8 / %50,9**. Eşit değerler ilgili kuralda pas; örneklemleri aynı sayıda değil. Temas sayısı, aktif kayıt orijinal bandına ayrı ziyaret sayısıdır; art arda kesişen mumlar tek ziyarettir.

**Üç işaret aynı yönü gösterirse:** kalın tarafın itmesi + daha az test edilmiş tarafın itmesi + fiyatın karşı iç kenara yakınlığı. 3.521 adayda çözülen iç çıkış **2.289/3.365 (%68,0)**, dış sınır **1.992/2.673 (%74,5)**; simetrik harekette sadece **1.778/3.405 (%52,2)**. Bu keşif, bir sonraki sınırın hangisi olabileceğini anlatıyor; bağımsız tarihlerde doğrulanmış yön alarmı değildir.

**Çıktıktan sonra ne oluyor?** Bütün koridorlarda ilk 6 barda iç sınır dışına kapanan 16.072 olayın çıkış kapanışından *yeniden* ölçüldü. Sonraki 6 mumda, ilk koridor ATR’siyle eşit uzaklıkta, 7.332 kez çıkış yönü, 6.663 kez ters yön önce; 236 aynı mum, 1.841 eşiksiz. Çıkış mumunda zaten yapılmış hareketi devam saymadık.

## Tarihli örnekler

- **KCHOL · 4s · 21 Ekim 2026 09:00:** Destek **198,20–203,10**, direnç **209,70–211,20**, kapanış **204,00**. Alt blok **3,27×** kalın, ama alt iç kenar yalnız **0,90** uzakta; üst iç kenar **5,70** uzakta. **22 Ekim 09:00** kapanış **202,30** ile destek bandına; **13:00** kapanış **197,60** ile desteğin tamamen altına gitti. Bu örnekte kalın destek yenildi.
- **EREGL · 4s · 30 Eylül 2026 09:00:** Destek **35,46–36,40**, direnç **37,34–37,90**, kapanış **36,68**. Alt blok **1,68×** kalın. Aynı gün **13:00**, kapanış **36,18**: ilk çıkış **aşağı**, yakın desteğe. Ama iki dış kenardan ilk aşılan **yukarı** oldu: **5 Ekim 13:00**, kapanış **37,94**. “Hangi bandı ilk denedi?” ile “hangisini tamamen geçti?” aynı olayda bile ters cevap verebilir.

**Öneri:** Kartta “kalın OB kazandı” yerine alt/üst kalan bant ve iki iç kenara uzaklığı göster. Örneğin “ilk yakın test destek; yön teyidi yok”. Gözlemler farklı sembol ve zaman dilimlerinde aynı piyasa hareketini paylaşabilir. Masraf, işlem fiyatı, gerçek alarm teslimi ve arşiv dışı ileri dönem doğrulanmadı. Canlı motor değişmedi.

[Tüm tarihli koridorlar, dört sınır ve çıkış kapanışları](KORIDORLAR.csv.gz) · [Kural ve alt grup sayımları](KIYAS.csv) · [Çıkıştan sonraki hareket](CIKIS_SONRASI.csv).

```bash
python -m research.ob_koridor --cikti var/ob_koridor
python -m research.ob_koridor_kiyas --dizin var/ob_koridor
```
