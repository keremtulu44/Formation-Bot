# Stabil — bekleyen araştırma ve görselleştirme notları

**Kayıt:** 2026-11-06. **Durum:** Kullanıcı bu aşamada yalnızca söylediklerinin kaydedilmesini istedi. Aşağıdakiler henüz başlatılmış bir çalışma, doğrulanmış sonuç veya canlı kural değişikliği değildir.

Önceki aynı-veri karşılaştırmasında destek ve ters direnç bazı temel davranışlarda benzer, fakat bütün alt durumlarda birebir aynı bulunmadı: [karşılaştırma özeti](stabil_destek_direnc_karsilastirma_2026_11_06/SONUC.md).

## 1. Normal Stabil desteğinde yukarı ok ve mumun gücü

- Kullanıcı, bazen anlamsız gördüğü **yukarı oklar** çıktığını, yukarı çıkan mum yeterince güçlü görünmese de okun oluştuğunu gözlemledi.
- Beklentisini, yukarı çıkışta **güçlü mumla** oluşan oka bağladı; mevcut davranışın sanki yalnız mumun yeşil olmasına bakıyor olabileceğinden şüpheleniyor.
- **Bu bir gözlem ve araştırılacak şüphedir:** Mevcut kodun gerçekten sadece yeşil mumu kontrol ettiği henüz bu istek kapsamında doğrulanmadı. Önce yukarı okun gerçek koşulları, zaman dilimi ve mum gücünün nasıl değerlendirildiği incelenmeli; ardından güçlü ve zayıf görünen örnekler ile yukarı okların replay sonuçları araştırılmalı. Bir hataya veya değişecek eşiğe önceden karar verilmemeli.

## 2. BOS ile yukarı ok ve destek kırılması ilişkisi

- Kullanıcı, yukarı ok çıkarken **BOS aşağı** dediği durumlarda fiyatın genellikle düştüğünü gördüğünü belirtti; BOS'un desteğin kırılmasıyla ciddi bağlantısı olabileceğini düşünüyor.
- Araştırma soruları: Yukarı ok anındaki BOS yönüne göre sonraki fiyat davranışı değişiyor mu? BOS aşağıyken desteğin sonraki kırılma davranışı nasıl? Gerekirse BOS ile yukarı ok arasında bir bağlantı kurulması değerlendirilebilir.
- Bunlar **kullanıcı gözlemi/hipotezi**, kanıtlanmış neden-sonuç ilişkisi veya uygulanmış filtre değildir. İleride karşılaştırırken olay anında gerçekten bilinen BOS durumu ve ilgili zaman dilimi esas alınmalı; bilinmeyen durumlar ayrı tutulmalı ve sonuçlar gözlemlenmeden canlı filtre seçilmemeli.

## 3. Ters direnç: dikey/yatay mantığıyla küçük görsel deneme — sonra

- Kullanıcı, ters direnç davranışının dikey/yatay mantığıyla küçük bir testini ve kendisinin deneyebilmesi için görselliğe aktarılmasını istiyor; **bunun şimdi yapılmamasını**, ama unutulmamasını özellikle belirtti.
- Sonraki deneme, fiyat–çizgi sırasını ve desteğin karşıt yönlü direnç davranışını gösterebilmeli. Önceki çalışmalarda aday native rejimler ile kullanıcının görsel dikey/yatay tarifinin birebir eşleşmesi doğrulanmadı; stepline'ın dikey bağ çizgisi tek başına kalıcı dikey rejim kabul edilmemeli.
- Native teyidin üzerine keyfî 2/3/5 bar bekleme eklenmemeli. Görsel deney veya olası canlı entegrasyon, kullanıcı daha sonra istediğinde ayrıca ele alınmalı.

## Bu kayıt sırasında yapılmayanlar

Yeni replay/analiz, BOS bağlantısı veya filtresi, direnç görseli, canlı alarm değişikliği ve dağıtım **yapılmadı**. Önceki araştırma çıktıları olduğu gibi korunur.

## Sonraki gelişme — kullanıcı onayıyla 50 hisselik direnç replay'i

Bu not kaydedildikten sonra kullanıcı destek tarifinin direnç için yönce tersini
onayladı ve aynı kırılma yollarının **50 veya 75 hissede** replay edilmesini
istedi. 50 hisselik araştırma yapıldı: [odak raporu](stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md)
ve [doğrulama](stabil_direnc_50_model_testi_2026_11_06/DOGRULAMA.md). Native
sabit çizgi kimliği, kullanıcının görsel yatay rejimiyle hâlâ doğrulanmış değildir.

Bu yeni replay, bu dosyanın 1–3. maddelerindeki güçlü görünen/görünmeyen destek
okları, BOS ilişkisi veya **daha sonra istenen** küçük direnç görselinin yerine
geçmez; bu başlıklar beklemektedir. BOS filtresi, yeni görsel, canlı aktivasyon
ve alarm değişikliği yapılmadı.

## Sonraki talep — direnç canlı grafik testi için ön kontrol

Kullanıcı direnç çizgisi ve oklarının destek davranışının ters yönünde yazılıp
grafiğe bağlanmasını ve canlıda kendisinin test etmesini istedi. Direnç için
ana çizgi kırmızı; destekte kırmızı olan karşıt rol burada yeşil olacak. Mevcut
formasyon veya Stabil destek alarmında grafik üretildiğinde direnç de yer alacak;
dirence özel yeni tetikleme veya otomatik mesaj olmayacak. Mevcut üç barlık
momentum-ok tekrar kısıtı dirençte ters yönde uygulanacak; bu yeni native teyit
beklemesi değildir.

Kullanıcı BOS ve üç barlık tekrar kısıtının etkisi için replay'i özellikle
**en sonraya** bıraktı; önce direnç canlı grafik işi ele alınacak. Kod incelemesi,
mevcut ok kuralları ve uygulama sırası: [uygulama ön kontrolü](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md).
Bu kayıt sırasında kod veya canlı ayar değiştirilmedi; direnç henüz yayında değil.

## Güncelleme — yerel grafik bağlantısı, 2026-11-07

Kullanıcının sonraki açık isteğiyle direnç çizgisi ve ters okların **yerel**
`/grafik` ve mevcut alarm grafiklerine bağlantısı yapıldı; [uygulama ve kaynak
sınırları](../tasarim/STABIL_DIRENC_CANLI_TEST_ON_KONTROL_2026-11-06.md#3-adım-uygulanan-yerel-bağlantı-ve-sınırları-2026-11-07)
burada tutuluyor. Bu, canlı görsel test veya dağıtım yapıldığı anlamına gelmez.
BOS ilişkisi, güçlü/zayıf görünen mumlar ve üç barlık momentum tekrar kısıtının
etkisine yönelik araştırmalar hâlâ sonraya bırakılmıştır; yeni BOS filtresi veya
ek teyit beklemesi seçilmemiştir.
