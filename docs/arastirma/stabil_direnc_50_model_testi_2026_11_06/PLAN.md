# Ters direnç — kullanıcının destek modeline karşı 50 hisselik replay planı

**Amaç:** Kullanıcının destek için anlattığı sıralı davranışın yönce tersine,
kullanıcının bu konuşmada verdiği cevaplarla bakmak. Kullanıcı, (1) direnç
modelinin destek tarifinin ters yönlü hali olduğunu, (2) kırıldıktan sonra sabit
kalma ile yukarı takibin ayrı incelenmesini, (3) temas/kapanış, sonraki tepki,
kırılma ve geri dönüşün ayrı gösterilmesini istedi. Evreni özellikle **50 veya
75 hisseyle** sınırladı; bu çalışma 50 kullanır. Önceki sonuçlar görüldükten
sonra hazırlandığı için plan kör ön kayıt değildir.

## Evren ve sabit sınırlama

- Önceki normal destek çalışmasının 100 hissesinden, önceki direnç evreninde de
  bulunan 100 hisse alınır. `selection.json` içinde kayıtlı sabit tohum + sembol
  SHA256 sıralamasının ilk 50'si seçilir; seçim tek tek hisse sonuçları ile
  yapılmaz. Bu yöntem eski 100 hisselik kolayda örneklemin sınırlılığını devralır.
- Aynı arşiv, aynı 50 hisse ve aynı kaynaklar; 2025 ve 2026 ayrı. Daha önce
  incelenmiş arşiv olduğundan 2026 bağımsız/kör doğrulama değildir. Eksik veya
  açık bar, şüpheli günlük geçmiş, eksik kova, aynı-bar sırası ve ufuk sansürü
  önceki [eş-kural planıyla](../stabil_destek_direnc_karsilastirma_2026_11_06/PLAN.md)
  aynı ve kayıtlıdır. Hata olursa çalışma sessizce hisse atlamadan durur.
- Gerçek günlük OHLC üzerinde değişmemiş native destek, ters günlük OHLC üzerinde
  aynı native çekirdeğin direnç karşılığı. 4s olay tanımları araştırma ölçüsüdür;
  canlı 4s oklarının matematiksel tersi olduğu varsayılmaz.
- Native teyide keyfî 2/3/5 bar bekleme eklenmez. 4/8/16 veya 24 bar ölçüm
  ufukları **ek alarm onayı veya zorunlu bekleme değildir**.

## Önceden belirtilen sorular ve alt gruplar

1. Yaklaşma ile gerçek temas, temas mumunda güvenli tarafta kapanış ve sonraki
   4/8/16 × 4s ±1 olay-4s-ATR yarışı iki tarafta ayrı. Gap çizgiye temas değildir.
2. Uzaklaşma → çizginin takip etmesi veya fiyatın eski çizgiye dönüşü; ayrıca
   eski A01'e yakın 1–2 günlük ATR ve 24 × 4s çizgi/fiyat yarışı. Farklı ATR ve
   ufuklu yüzdeler birbirine çıkarılmaz.
3. Aşağı destek / yukarı direnç kırılmasından sonra **aynı epizotta** 24 × 4s:
   eski çizgiyi fiyatın geri alması, çizginin ters yönde taşınması ve aynı-bar
   belirsizliği. Fiyat eski çizgiye döndüyse yeniden kırma/çizgi değişimi;
   çizgi önce taşındıysa o andaki fiyatın yeni çizgiye göre konumu ve aynı çizgi
   kimliğinde aday düz proxy'ye geçiş / eski çizgiye fiyat dönüşü ayrı.
4. Çizgiye göre taraf değişiminin fiyatın kendisi, çizgi değişimi, ikisinin
   birlikte veya ayrı ayrı yeterli olmasıyla oluşması aritmetik olarak sayılır.
5. Eski F01'e yakın, son 4 × 4s fiyat tepki yönünde >0,3 günlük ATR iken
   aday ters basamak ile onun sonrası aday düz rejim; fiyatın çizginin o anda
   güvenli/ihlal tarafında olmasına göre ayrıca ayrılır. Önceden bilinen bu
   grupların 8-bar ±1 **günlük** ATR sonuçları, payda ve hisse sayısıyla gösterilir.
6. Eski B04'e yakın yeni-düz/uzun-düz aday grupları için başlangıçta dondurulan
   çizginin izleyen 8 × 4s kapanışlardan herhangi biriyle ihlal edilmesi ayrı
   ölçülür; başlangıç kapanışı ve seviyenin kendisi o anda bilinmelidir. Bu,
   kullanıcı tarifinin grafik eşlemesi veya yeni canlı şart değildir.

Aday `HORIZONTAL_AFTER_DROP` sınıflandırması native günlük kapanışın ilgili
çizginin güvenli tarafında olmasına bağlıdır. Bu nedenle bu aday rejimin
altında/üstünde fiyat görülmesi bağımsız görsel kanıt değildir. Kural, kullanıcının
"dikey/yatay" görseline eşit sayılmayacak; stepline'ın tek dikey bağı kalıcı
rejim değildir. `NEWLY_FLATTENED_AFTER_RISE` ve `LONG_HORIZONTAL` varolan
araştırma proxy'lerinin yaş tanımlarıdır, yeni canlı bekleme değildir.

Sonuçlar yaklaşma ve gerçek temas kümelerinin farklılığı, örtüşen checkpoint'ler,
hisse/gün etkisi ve küçük alt grup n'leriyle birlikte yorumlanır. Tek bir yüksek
yüzde seçilerek otomatik aktif etme kararı verilmez. Kullanıcı bu aşamada replay
istedi; grafik/Telegram/canlı alarm değişikliği veya yeni direnç görseli yapılmaz.
