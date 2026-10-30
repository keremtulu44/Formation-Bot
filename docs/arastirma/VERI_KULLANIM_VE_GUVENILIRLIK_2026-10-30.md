# Araştırma verileri: neye yarar, nerede durmalı?

**İnceleme:** 30 Ekim 2026 · **Kapsam:** depodaki dosyalar ve belgeler. Canlı
Telegram teslimi, güncel veri sağlayıcısı ve çalışan sunucunun durumu bu
incelemeyle doğrulanmadı. Tarihsel oranlar yatırım tavsiyesi veya gelecek başarı
olasılığı değildir.

## 1. Depoda gerçekten ne var?

Bu sayılar dosyalar okunarak kontrol edildi; arşiv güncellendiğinde değişebilir.

| Kaynak | Doğrulanan kapsam | Ne için uygun? |
|---|---|---|
| [`backfill_data/`](../../backfill_data/) | 354 sıkıştırılmış OHLCV dosyası: 177 sembol × kaynak 1s/1g. 174 hisse, XU100, XU30 ve BRENT. 1s toplam 572.059, günlük 88.445 kaynak satırı; iki aralıkta da dosya başına tekrarlı zaman etiketi görülmedi. | Fiyat kesitleri, yeniden üretilebilir Replay ve veri kalite testleri. Tekrarlı etiket olmaması verinin eksiksiz/doğru olduğunu kanıtlamaz. |
| Aynı arşiv, yalnız 174 hisse | 1s 558.724, günlük 86.945 satır. 1s 59.604, günlük 170 satırda hacim sıfır. 1s kaynak etiketleri 7 Mayıs 2025–19 Ekim 2026; günlük etiketler 21 Ekim 2024–19 Ekim 2026 arasında. Serilerin başlangıçları eşit değil. | Hisse araştırması; 2s/4s, 1s veriden seansa hizalı türetilir; günlük native seridir. Sıfır hacim kaynak semantiğiyle değerlendirilir, doğrudan eksik/hatalı ilan edilmez. |
| [`bot_data/`](../../bot_data/) | Repoda 28 hisseye ait JSON başlangıç önbelleği var. | Botun yerel başlangıcı için seed; bütün güncel evren veya uzun araştırma arşivi değil. |
| [Kırılım/teyit Replay sonuçları](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md) | 174 hisse × 4 TF = 696 seri; aday CSV'sinde 25.457, takip kontrol CSV'sinde 45.255 satır. Ana manifest kaynak ve bağımlılık hashlerini taşır. | Olayların gelişimi, teyit gecikmesi, aynı olayın farklı pencerelerde incelenmesi ve motor regresyonu. |
| [Zone / S01–S32 sonuçları](README.md) | Bir araştırma 176 BIST/endeks sembolü × 4 TF = 704 seri ve 994.142 gözlem satırı raporlar; ayrı DZ koşusu BRENT'i ayrıca işler ve 177 × 4 = 708 seridir. Bunlar farklı koşu/evren sayılarıdır. | OB/FVG/market-structure davranışını açıklama, tanım/sansür denetimi ve gölge deney hipotezleri. Ham JSONL çıktıları Git'te tutulmaz; rapor ve kod kalıcıdır. |
| [`capraz_piyasa_data/`](../../capraz_piyasa_data/) ve [48 hisse pilotu](DEPLOY_PIYASA_PILOTU.md) | 12 ayrı günlük makro/endeks serisi; pilot CSV'sinde 181.440 teorik tekli/ikili hücre, sıfır gözlemli hücreler dahil. | Keşif ve veri hattı deneyi. Her kaynakta gerçek kapanış/kullanılabilirlik saati doğrulanmamış; iki gün gecikme varsayımı doğrulama değildir. |
| [Kaçırılan hareket pilotu](KACIRILAN_HAREKETLER_PILOTU.md) | ASTOR, THYAO, AKBNK, GARAN, TUPRS; 1s ve 1g ayrı, sınırlı sayıda pencere. | Ölçüm yöntemini ve negatif kontrolleri tasarlama. Beş elle seçilmiş hisse tüm BIST'i veya gerçek teslimleri temsil etmez. |

Arşivin 1s/1g kapsamı, türetilmiş 2s/4s bar sayısı ve Replay **olay** sayısı
aynı şey değildir. Varsayılan çalışma evreni güncel kodda 57 semboldür (48 hisse,
5 endeks, 4 makro); `STOCK_UNIVERSE` bunu değiştirebilir. Makrolar varsayılan
olarak alarm üretmez. Araştırma havuzu ile çalışan botun evrenini eşitlemeyin.

## 2. İlk anlamlı kullanımlar

### A. Veri sağlığı ve değişiklik regresyonu — en yüksek öncelik

Arşiv, gerçek Telegram'a bağlanmadan motor veya çizim değişikliklerini sabit
örneklerde sınamak için değerlidir. Örneğin ASTOR yanında fiyat sürekliliği,
kısa seans ve farklı likidite yapıları içeren birkaç hisseyi önceden seçip
1s/2s/4s/1g için veri hash'i, motor/config sürümü, son kapalı mum, bulunan
formasyon/zone, eksik alan ve hata sayılarını kaydedin. Eski ve yeni sürümü aynı
girdiyle karşılaştırın; farkları otomatik başarı saymak yerine inceleyin.

**Tamamlanma ölçütü:** Her seri için hash ve kapsama bilgisi, ölçülemeyen/hatalı
seri listesi, deterministik küçük regresyon ve ayrı çalıştırılan büyük Replay
raporu. Veri sonu, zaman etiketi ve gerçek erişim anı ayrı alanlar olmalı.
Belirli bir zaman diliminde veri üretilemezse sessizce başarı yazılmamalı.

**Önce çözülmesi gereken kalite soruları:** doğrulanmış BIST tatil/yarım gün
ve geçmiş seans çizelgesiyle iç seans boşlukları; split/bedelsiz ve fiyat
düzeltmesi; 09:30 hacim semantiği; kaynağın geçmiş barları ne zaman
kullanılabilir kıldığı. Bunlar bilinmiyorsa `UNKNOWN` korunmalı; sıfır hacim
otomatik silinmemeli, eksik mum uydurulmamalıdır. KONTR'daki belirli boşlukların
nedeni bu incelemeden çıkarılamaz.

### B. Bildirim gürültüsü ve gecikme — önce gölgede

[Adaylar](sonuclar/kirilim_replay/adaylar.csv.gz), [teyit takipleri](sonuclar/kirilim_replay/teyit_kontrolleri.csv.gz)
ve [aynı olay karşılaştırması](sonuclar/aday_teyit_karsilastirma/olaylar.csv.gz)
birlikte, “teyidi beklemek ne kadar geciktiriyor ve hangi olaylarda beklemek
yararlı/zararlı olabilir?” sorusuna başlangıç sağlar. Adayın gelecekte teyit
alıp almadığı aday anında **bilinmez**. Adayın 10. mumu ve teyidin 10. mumu da
aynı bitiş değildir; ayrı medyanlar çıkarılarak “kaçan kâr” hesaplanamaz.

**Önerilen deney:** Mevcut kararları değiştirmeden aday/teyit için ayrı gölge
kayıt tutun. Kimlik, karar zamanı, kapanmış veri, sürüm, filtre gerekçesi,
tekrar/tekilleştirme, bildirim isteği ve gerçek teslim sonucunu ayrı izleyin.
Aynı olayda teyit gecikmesini, kapanış yönünü, aleyhte hareketi ve hisse/gün
başına fazladan uyarıyı raporlayın; delil yoksa teslim durumunu `UNKNOWN` yazın.
Replay'de olay görülmesi, geçmişte kullanıcıya mesaj gittiğini kanıtlamaz.

### C. “Kaçırılan hareket” incelemesi — kapsama ve yanlış alarm birlikte

Beş hisselik pilot, aktif formasyon/yakın OB gibi özelliklerin hem hareket hem
kontrol pencerelerinde bulunabildiğini gösteren bir **yöntem deneyi**. Bunu
“kaçanların şu kadarı kurtarılır” şeklinde kullanmayın.

Sonraki çalışmada hipotezi ve 2 ATR / 10 mum gibi ufku baştan dondurup, farklı
sektör ve likiditeden önceden belirlenmiş bir örnek seçin; hareketleri örtüşen
pencereler yerine tek epizotta birleştirin. Aynı hisse/TF ve benzer geçmiş
oynaklık/zaman için eşleşmiş hareket-dışı kontroller kurun. Mevcut formasyon,
OB/FVG ve birleşimlerini aynı kontrollerde karşılaştırın. **Birlikte** kapsama,
kontrolde tetiklenme, alarm/hisse/gün, gecikme, belirsiz/sansürlü oran ve
hisse/tarih bloklu güven aralığı verin. Yetersiz örneği sonuç diye zorlamayın.

### D. Eğitim ve açıklama

`/test`, gerçek arşivden geçmişi gizlenmiş kesit üzerinde formasyon okuma
alıştırması olarak kullanılabilir: dört TF, seçilen 8/10/20 kapanışlık ufuk ve
sonuç grafikleri aynı olaya bakar. Bu bir işlem simülasyonu veya tahmin
performansı sıralaması değildir; fiyatın geçmişteki sonucunu sonradan açar.
Zone/OB/FVG ve `◇` kart yüzdeleri de “bu tanıma uyan arşiv olaylarının
betimlemesi” olarak okunmalı, kişisel başarı olasılığı gibi sunulmamalı.
Örneklem ve tanım özellikle önemlidir: `S05` yalnız “çalıştı” alt kümesine
koşulludur; tüm sinyallerin stop dağılımı değildir. `S08` terminal öncesi,
sonrası ve aynı bar belirsizliğini ayrı paydalarda tutar.

### E. Piyasa bağlamı — şu an yalnız araştırma

Katı modda [`STRICT_UNKNOWN`](CAPRAZ_PIYASA_UYGULAMA.md), kapanış/erişim kanıtı
olmayan makro değerleri bilinmiyor sayar. 181.440 hücrede çok sayıda seçim ve
bağımlı gözlem bulunur; örneklerde ileri dönem `n` sıkça küçüktür. “X yükseldi,
bu hisse de yükselecek” diye canlı karta, puana ya da al/sat filtresine taşımak
şu anda anlamlı değildir.

Önce her kaynağın tarihsel `available_at` bilgisini ve saat dilimini belgeli
kanıtla doğrulayın, spot/vadeli farkını koruyun; eşzamanlı gram/TL OHLC yoksa
üretmeyin. Ardından baştan belirlenmiş az sayıda koşulu aynı piyasa rejimi ve
oynaklığa göre eşleşmiş kontrolle, farklı takvim dönemlerinde test edin. Varsayılan
çok büyük kombinasyon kümesi yerine `--order 1` veya `--order 2` ile başlayın.

## 3. Bir bulguyu canlı davranışa taşımadan önce

1. **Tanım ve zaman:** olay birimi, karar anı, hedef, yön, başlangıç ATR'si,
sansür ve aynı mum içi sıralama önceden yazılmalı. Sadece o anda gerçekten
kullanılabilir veriler alınmalı; sonradan oluşan durum geçmişe taşınmamalı.
2. **Ayrı veri:** ortak takvim tarihli keşif/ileri ayrımı ve ufuk kadar embargo;
aynı hisse/olay/zaman bloklarının sızıntısı önlenmeli. Mevcut bazı raporlarda
%70/%30 ayrımı her serinin kendi bar dizisindedir; bütün hisselerde aynı tarihli
tek holdout anlamına gelmez.
3. **Örneklem:** ham `n` yanında benzersiz hisse/gün/epizot, sağ sansür,
UNKNOWN, bloklu güven aralığı ve çoklu karşılaştırma etkisi gösterilmeli.
`n≥30` veya soru kapısındaki puan eşiği tek başına istatistiksel geçerlilik
kanıtı değildir.
4. **Performans:** uygun eşleştirilmiş baz, maliyet/kayma ve uygulanabilirlik;
aynı mumda hedef/stop sırası bilinmiyorsa iyimser seçim yerine belirsizlik veya
muhafazakâr senaryo raporlanmalı. Aşağı yönlü sonuç, açığa satışın mümkün veya
maliyetsiz olduğunu göstermez.
5. **İşletim:** yalnız gölge dönem ve teslim kanıtından sonra, kullanıcıya açık
ayrı onay/geri alma planıyla değişiklik düşünülmeli. Önceki tarihli belgelerdeki
“YAZILIR/kural” ifadeleri otomatik canlı geçiş yetkisi değildir.

`/backtest` kayıtlı yerel geçmişin betimsel raporudur, tarihsel veriyi yeniden
oynatan işlem backtest'i değildir; `/karne` de tanımlı ATR ilk-dokunuş ölçümünü
gösterir. İkisi de fiili portföy getirisi veya tamamlanmış canlı teslim kaydı
olarak yorumlanmamalıdır.

## 4. Kaynaklar ve yeniden üretim

- [Araştırma haritası](README.md) · [son Replay dizini](SON_REPLAY_SONUCLARI.md)
  · [ölçüm hattı ve anti-lookahead sözleşmesi](ARASTIRMA_HATTI.md).
- [174 hisse ayrıntılı yöntem, kontrol ve manifestler](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md)
  · [kaçırılan hareket pilotu](KACIRILAN_HAREKETLER_PILOTU.md)
  · [çapraz piyasa veri kapısı](CAPRAZ_PIYASA_UYGULAMA.md).
- [Önceki kod/Supabase değerlendirmesi](DENETIM_VE_REPLAY_ONERILERI_2026-10-29.md)
  tarihli bir gözlemdir; o tarihteki tablo sayıları bugünkü canlı DB durumu değildir.
- Büyük ara çıktılar Git'e konmaz. Büyük koşu öncesi boş çalışma dizini seçin,
  hash/sürüm ve bağımlılıkları kaydedin; var olan sonuçları yanlışlıkla
  üzerine yazmayın. Kaynak CSV'lerinin sayımı ve bu belge yeniden çalıştırılan
  araştırma sonuçlarıyla değil, depoda bulunan dosyalarla yapılmıştır.
