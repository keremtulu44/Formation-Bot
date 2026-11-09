# Stabil — son değişikliklere ait görsel örnekler

Bu görseller projenin `grafik.anlik_goruntu` ve `grafik.ciz` zinciriyle,
sentetik test mumları üzerinde hazırlanmıştır. Gerçek hisse veya replay sonucu
değildir; görseller performans kanıtı olarak kullanılmamalıdır.

- `01_cok_mumlu_toparlanma.png`: Çok mumlu toparlanmanın ilk yeşil takip
  mumunda görünen destek oku; takip kapanışı destek altında da olabilir.
- `02_eski_tek_mum_kaldirildi.png`: Aynı test verisine eski `close_reclaim`
  kayıt türü yerleştirildiğinde bu türün artık ok olarak gösterilmemesi.
- `03_ters_bos_iptal.png`: Sonraki mumda sentetik ters BOS bağlamı verilince
  önceki destek okunun gri iptal işareti olarak kalması. BOS çizgisi bu örnekte
  çizilmez; burada gösterilen şey okun bağlama verdiği tepkidir.

Görseller mevcut uygulama davranışını gösterir; henüz modellenmemiş geometrik
boşluk ve rejim ayrımlarının tamamlandığı anlamına gelmez.
