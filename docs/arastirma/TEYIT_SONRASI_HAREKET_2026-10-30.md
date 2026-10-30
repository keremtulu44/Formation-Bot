# Teyitten sonraki hareket ve zaman dilimleri

**Birleştirilmiş kapsamlı kayıt:** [Aday ve teyit sonrası karşılaştırmalar, tüm tablolar, veriler ve yöntem](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md).

## Ölçümün kapsamı

174 arşiv hissesinde önceki Replay'in **18.752 teyitli adayını** yeniden inceledik. Teyit olan 694 hisse/zaman dilimi serisi vardır; MEGAP 1s ve 2s serilerinde kaydedilmiş teyit yoktur. Teyitli adayın fiyatı, **teyit mumunun kapanışı**dır; bu kapanıştan **sonraki** 10 mumun kapanışları ölçülür. Sıfır noktası artık aday kapanışı değil, teyit kapanışıdır. ATR, teyit mumundaki temiz segmentte hesaplanan 14 bar Wilder ATR'sidir; bütün 10 mum için sabittir.

18.495 olayda hedef gözlenebilir. Adaylar arasında aynı hisse/TF için teyit sonrası 10 mumluk pencereler çakışıyorsa yalnız ilk teyit seçilir; **18.131 teyit** kalır. Seçim yalnız teyitli olaylar arasında yeniden yapıldığı için bu sayı, önceki rapordaki tüm adaylar üzerinden örtüşme filtresi uygulanan 15.947 teyitle aynı payda değildir. Bu iki çalışma ve başlangıç noktaları doğrudan karşılaştırılamaz.

**Sansür:** dönem sınırı 133, seri sonu 112, veri kırılması 11, tamamlandığı doğrulanmamış son native 1s/1g mumun hedefe denk gelmesi 1. `horizon` 10 bar; 2s/4s son türetilmiş kova düşürülmüştür. 1s/1g son mum ve iç seans/kaynak kapanışları için genel belirsizlik devam eder. Kapanışlar dışındaki mum içi yüksek/düşük, emir, fiyat kayması ve gerçek Telegram teslimi ölçülmez.

## İleri dönemde teyitten sonra ne oldu?

Yönlü işaret: yukarı teyitte fiyat artışı, aşağı teyitte fiyat düşüşü pozitiftir. Medyan onuncu kapanış, teyit kapanışına göre o yöndeki medyan değişimdir; örneğin aşağı yönlü +%1,49, fiyatın medyanda yaklaşık %1,49 düştüğü anlamına gelir. `+2 ATR` sütunu sonraki on kapanışın **herhangi birinde** lehe eşik; `−2 ATR` herhangi birinde aleyhe eşiktir. Aynı olay iki eşiği de görebilir.

| TF | Yön | n | 10. kapanış medyanı | 10. kapanış medyanı % | Yol içi +2 ATR | Yol içi −2 ATR |
|---|---|---:|---:|---:|---:|---:|
| 1 saat | Yukarı | 1.239 | −0,19 ATR | −%0,25 | %24,5 (304) | %24,9 (309) |
| 1 saat | Aşağı | 1.402 | +0,53 ATR | +%0,56 | %29,3 (411) | %22,3 (313) |
| 2 saat | Yukarı | 744 | −0,37 ATR | −%0,59 | %23,9 (178) | %23,8 (177) |
| 2 saat | Aşağı | 741 | +0,66 ATR | +%1,01 | %33,7 (250) | %19,0 (141) |
| 4 saat | Yukarı | 516 | −0,67 ATR | −%1,41 | %19,8 (102) | %32,0 (165) |
| 4 saat | Aşağı | 415 | +0,81 ATR | +%1,49 | %41,7 (173) | %14,0 (58) |
| Günlük | Yukarı | 243 | −0,58 ATR | −%2,28 | %25,1 (61) | %37,0 (90) |
| Günlük | Aşağı | 230 | +0,34 ATR | +%1,23 | %29,1 (67) | %21,3 (49) |

Medyanlar ve eşik yüzdeleri farklı ölçülerdir. Yol içi 2 ATR görülüp 10. kapanışa kadar korunmayabilir. Örneğin 4s aşağıda 173/415 yol içi +2 ATR, ancak **132/415 (%31,8)** onuncu kapanışta +2 ATR veya üzerindeydi. Aşağı fiyat hareketinin kâra dönüştürülebileceği, açığa satış veya maliyet varsayılmadı.

### 2, 5 ve 10 bar medyanları — ileri dönem

Hepsi teyit kapanışından itibaren yönlü ve teyit ATR'si cinsinden:

| TF | Yön | 2. kapanış | 5. kapanış | 10. kapanış |
|---|---|---:|---:|---:|
| 1 saat | Yukarı | −0,10 | −0,14 | −0,19 |
| 1 saat | Aşağı | +0,07 | +0,20 | +0,53 |
| 2 saat | Yukarı | −0,06 | −0,15 | −0,37 |
| 2 saat | Aşağı | +0,13 | +0,35 | +0,66 |
| 4 saat | Yukarı | −0,21 | −0,38 | −0,67 |
| 4 saat | Aşağı | +0,20 | +0,59 | +0,81 |
| Günlük | Yukarı | −0,07 | −0,35 | −0,58 |
| Günlük | Aşağı | +0,22 | +0,24 | +0,34 |

Bunlar yalnızca bu evrenin son %30'luk dönemindeki dağılımlardır. 10 adet 1s bar ile 10 adet 1g bar **aynı süre değildir**; üstelik 2s/4s kovalarında seans sonu kısa kovalar bulunabilir. Zaman dilimlerinin sayıları bu nedenle eşit süreli strateji karşılaştırması değildir.

## Somut örnek: THYAO günlük yukarı teyit

Önceki 12 Haziran adayı teyit alamadığı için bu örneklemde yoktur. Ayrı bir olayda motor, **6 Temmuz 2026** mumunda 347,00 kapanışta yukarı teyit üretmiştir. Teyitten sonraki 10. kapanış **21 Temmuz'da 317,50**; başlangıca göre −%8,50 veya teyit ATR'siyle yaklaşık −3,55 ATR. Bu olay teyidin her zaman devam anlamına gelmediğini gösteren tek bir örnektir; gerçek bildirimin gönderildiğini veya bir işlem yapıldığını kanıtlamaz.

## Dönem değişince sonuç değişiyor

Örnek: 4s teyit sonrası yol içi +2 ATR:

| Yön | Keşif | İleri |
|---|---:|---:|
| Yukarı | 393/1.120 (%35,1) | 102/516 (%19,8) |
| Aşağı | 205/996 (%20,6) | 173/415 (%41,7) |

Yukarı ve aşağı farkı dönemle birlikte yön değiştirdi. Aynı piyasa hareketleri çok sayıda hisseyi etkileyebilir; gözlemler bağımsız değildir. Sadece bu ileri döneme bakarak “4 saatlik aşağı her zaman en iyi” veya 4 saatlik yukarıyı kapatmak gibi bir karar çıkarılamaz. Genel piyasa ve eşleşmiş zaman kontrolü, hisse/zaman bloklu belirsizlik ve yeni bağımsız dönem gerekir.

## Zamandan yararlanma fikri — yalnız araştırma/gölge

1. **Aynı saat süresini karşılaştır:** Örneğin tüm TF'lerde teyitten sonraki 1, 2 ve 5 işlem günü için kapanışları eşleştir; 10 barı farklı sürelerle eşitleme. Gerçek işlem takvimi, eksik/kısa seans ve kaynak kapanış zamanlarını doğrula.
2. **Üst TF bağlamı:** 1s veya 2s teyit anında, yalnız o ana kadar gerçekten kapanmış 4s/günlük barla uyum/ters/nötr/UNKNOWN olarak gölgede sınıflandır. Üst TF tarih etiketini kapanış anı sanma; kanıtlanamayan zamanı UNKNOWN bırak. Önceden belirlenen kurallarla yukarı/aşağı ayrı, eşleşmiş kontrol ve ileri dönem kullan.
3. **Erken uyarı/teyit ayrımı:** adaydan önce hareket ne zaman başladı, adaydan teyide ne kadar gidildi ve teyitten sonra ne kaldı? Karşılaştırmayı ortak bir hareket başlangıcıyla ayrıca yap. Bu çalışma yalnız son kısmı ölçer.
4. **Alarm yükü ve yanlışları:** Hangi aday gerçekten kaçıyor, hangisi erken uyarı verilirse ters dönüyor, fazladan kaç bildirim doğuyor? Canlı değişikliğe geçmeden sessiz gölgede ölç.

Bu fikirler canlı kural, eşik, kart veya bildirim değişikliği değildir. 09:30'da görülen sıfır hacim kullanıcının belirttiği kaynak davranışıdır; bu çalışmada silinmemiş ve kendi başına bot hatası sayılmamıştır. Hacim bazlı kararların kaynak semantiği ayrıca akılda tutulmalıdır.

## Dosyalar ve tekrar

- [Olay bazlı veri](sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz): teyit zamanı/fiyatı/ATR, 1/2/5/10 kapanış, yönlü lehe/aleyhe eşikler ve sansür.
- [TF/yön/dönem özeti](sonuclar/teyit_sonrasi/ozet.csv): ham ve teyit sonrası penceresi örtüşmeyen iki seçim ayrı.
- [Manifest](sonuclar/teyit_sonrasi/manifest.json); temel 174 hisse kaynak hashleri ve ön çalışma [manifestinde](sonuclar/kirilim_replay/manifest.json). Bu rapor artımlı Replay ve canlı rolling rebuild/gerçek teslim eşdeğerliği iddiası taşımaz.

```bash
python scripts/kirilim_teyit_sonrasi.py
python -m pytest -q test_kirilim_teyit_sonrasi.py
```
