# Stabil: dikey destek üzerinde yukarı deneme

Grafikte destek dikey/kademeli durumdayken yukarı deneme eski yeşil `▲` ile
sunulmaz; mumun üstünde mercan `▼` **yapı/geri dönüş riski uyarısı** gösterilir.
Bu işaret kesin fiyat düşüşü, satış tavsiyesi veya gerçekleşmiş kazanç değildir.
Destek yatayken normal güçlü geri alım ve momentum `▲` kuralları değişmez.
Native `05_stabil.txt` hesabı ve destek seviyeleri değiştirilmemiştir.

## Uygulama ve sınırlar

* Görsel bir çizgi segmentinin gerçek eğimini sınıflandıran doğrulanmış bir
  model henüz yok. `STEPPING_UP`/`STEPPING_DOWN` aday rejimleri ve **o mumda**
  bilinen destek seviyesi değişimi, temkinli bir dikey **proxy** olarak alınır.
  Bu proxy gerçek dikey parçadan daha geniş olabilir: özellikle yukarı rebase
  sonrasında native pivot spacing süresince `STEPPING_UP` devam eder. Fiyat
  desteğin altındaysa rejim etiketi `BREACHED_FIXED_SUPPORT` olsa bile aynı
  yakın dönemli yukarı basamak proxy'si korunur. Kural bu aralıkta yatay
  görünen parçada da `▲` bastırabilir; tam görsel etiket
  doğruluğu veya kârlılık iddia edilmez.
* Dikey proxy'de aşağıdan yukarı temas, geri alım veya momentum denemesi
  `vertical_attempt_kind` ile izlenir; `reclaim_kind`/`momentum_kind` boş kalır.
  Komut özeti aynı önceliği izler; yanlış pozitif bir geri alım özetlenmez.
* Grafik katmanı bu barlarda `▼` çizer ve eski/çelişkili `▲` verisini filtreler.
  Yeni alanları olmayan eski snapshot'ta yalnız görünür destek seviye değişimi
  saptanabilir; kadrajın ilk mumundan öncesi/rejim geçmişi yoksa gerçek dikeylik
  güvenle geri çıkarılamaz. Eski snapshot'ta hem alan hem görünür değişim yoksa
  dikeylik bilinmez; yeni snapshot'a dönüştürmek gerçek durumu geri getirmez.
* Zaman eşlemesinde destek seviyesi önceki kapanmış noktadan taşınabilir;
  **olay işaretleri** ise yalnız eşit kapanış zamanında görünür, veri boşluğuna
  eski ok kopyalanmaz. Tüm karşılaştırmalar kapanmış mum itibarıyladır.

Bu sözleşme, `GENEL_KONTROL_VE_STABIL_OK_DUZELTMESI_2026-11-03.md`
belgesindeki dikey basamakta `upward_rebase_momentum` için `▲` önerisini
geçersiz kılar; yatay momentum bölümü geçerlidir. Replay sonuçları yatırım
stratejisi olarak kullanılmadan önce görsel örnekler, veri kalitesi, maliyetler
ve canlı/paper doğrulaması ayrıca incelenmelidir.
