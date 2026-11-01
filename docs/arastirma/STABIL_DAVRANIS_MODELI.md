# Stabil — kullanıcının fiyat/çizgi davranışı modeli

**Kayıt yenileme:** 2026-11-01. Önceki dosya bulunamadığı için konuşmadan
anlamı korunarak yeniden kaydedildi; önceki dosyanın bayt-kopyası değildir.
**Statü:** Kullanıcı gözlemi/hipotez; kanıtlanmış piyasa kuralı değil.
[Ana rehber](STABIL_REHBERI.md) · [48 soru](STABIL_DAVRANIS_SORULARI.md).

## Kritik düzeltme

Kullanıcı ilk açıklamadaki “yatay” kelimesini **“dikey”** olarak düzeltti.
Özet açıklaması:

> Fiyat düşerken desteğin altına inerse ve çizgi dikeyken yukarı çıkmaya
> çalışıyorsa altı boştur. Destek yataya döndüğünde düzgün destek oluşur;
> fiyat altında olsa bile üstüne çıkınca tutunacak bir şey olur.

Ek açıklaması: **“Yatay dönmesi Stabil onayı yeter, o teyitli zaten.”**
Bunun üzerine keyfî birkaç mum bekleme veya ek teyit şartı konmayacak.
“Altı boş” yalnız fiyat/çizgi arası sayısal mesafe olarak yorumlanmayacak.

## Yükseliş döngüsü

1. Fiyat genellikle destek üstündedir; önce destekten uzaklaşır.
2. Ya destek yukarı harekete başlar ya fiyat desteğe geri döner.
3. Destek fiyatı takip ederken dikleşir; fiyat yavaşlayınca yataylaşır.
4. Yeni yataydan yeniden destek alıp devam edebilir veya uzun süre bekleyebilir.
5. Kullanıcıya göre uzun yatay seviyelerde ani aşağı kırılma daha azdır.
6. Uzun yükseliş sonrası **henüz yeni yataylaşmış** seviyede aşağı kırılma
   riski olabilir; kırılırsa sert hareket ve düşüşe geçiş olabilir.

Yataylaşma öncesi yükselişin süresi/şiddeti ile mevcut yataylığın yaşı ayrı
ölçülmeli. “Destek eskidir” ikisini tek başına temsil etmez.

## Aşağı kırılma sonrası iki yol

### Destek aşağı hareketlenir

Fiyat kırar; destek de aşağı iner. Hareketli/dikey bölümdeki yukarı deneme
ile destek yeniden yataya yerleştikten sonraki çıkış aynı sayılmamalı.
Yerleşen referansın üstüne geçince fiyatın tutunabileceği seviye vardır.
Bu, yükselişin garanti olduğu iddiası değildir.

### Destek eski seviyesinde sabit kalır

Fiyatın sabit seviyeyi geri alma denemesi önemlidir. Üstüne çıkamazsa destek
sonradan aşağı hareketlenebilir. Üstüne çıkmaya başlarsa seviyeyi geri alıp
belirgin tepki verebilir. Her olayın zorunlu sonucu olduğu söylenmiyor.

## Kullanıcının açıkça bilmediği bölüm

**Küçük kırılma + geri dönüş** ile **büyük kırılma + geri dönüş** tepkilerinin
nasıl farklılaştığından emin olmadığını söyledi. Derinlik, altta kalma süresi,
fiyatın geri alıma kadar verdiği tepki ve geri alımdan sonra kalan hareket
birbirinden ayrılmalı. “Derin kırılma mutlaka daha iyi tepki verir” varsayılmamalı.

## Ölçülecek ana şey olay sırasıdır

`uzaklaşma → desteğin takibi veya fiyatın dönüşü → yataylaşma → temas/bekleme/
devam/kırılma → geri alım veya aşağı takip`

Sadece “üstünde/altında” ortalamaları bu modeli doğrudan sınamaz. Aynı güncel
konuma farklı yollardan gelmek farklı fiyat davranışı taşıyabilir.

## Çözümlenmemiş native/görsel eşleme

Stepline her seviye değişiminde dik bağ ve ardından yatay segment çizer.
Ekrandaki açı/zoom, zaman süren bağımsız native “dikey rejim” değildir.
Kullanıcının yataya dönüş tarifinin native teyit/güncelleme olayıyla birebir
örtüştüğü, görsel/kaynak örnekleriyle doğrulanmalı. `SAME` etiketi otomatik
olarak kullanıcının teyidi ilan edilmemeli.

Yataylığın **gelecekte** kaç gün süreceği ilk anda bilinmez. Yaş yalnız o ana
kadar değişmeden geçmiş süre olmalı. Pivot kökeni, teyit/bilinirlik ve seviye
yaşı ayrı tutulmalı; teyit geçmişteki dip mumuna geri taşınmamalı.

[Çalışma geçmişi](STABIL_CALISMA_GECMISI.md) eski araştırmaların bu modele
hangi ölçüde cevap verdiğini ve bugün neyin doğrulanamadığını açıklar.
