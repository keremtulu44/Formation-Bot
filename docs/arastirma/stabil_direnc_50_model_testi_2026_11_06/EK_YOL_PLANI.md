# Aynı 50 hissede fiyat-bağımsız sabit çizgi yolu — ek kontrol

İlk 50-hisse sonuçlarında aday `HORIZONTAL_AFTER_DROP` sınıfının günlük kapanışın
çizgiye göre güvenli tarafta olmasına bağlı olduğu görüldü. Kullanıcının sorduğu
"fiyat kırılan çizginin üstündeyken çizgi ne yapıyor?" yolunu bu sınıfa
koşullamak, aranan davranışı daha baştan seçime katabilir. Bu ek plan sonuçlara
bakıldıktan sonra yazıldı; keşifseldir, kör ön kayıt değildir.

Aynı 50 hisse ve daha önce tanımlanmış, tam/temiz 24-bar kırılma epizotları
kullanılır. Fiyat eski çizgiye dönmeden önce çizgi **ters yönde ilk kez**
taşınmışsa (destek aşağı / direnç yukarı), bu ilk teyitli yeni çizgi ve native
kimliği alınır. O 4s kapanışında fiyatın yeni çizginin güvenli veya ihlal
tarafında olması **her iki durum için** ayrı tutulur; rejim ve fiyat yönüyle
bağlantılı `HORIZONTAL_AFTER_DROP` sınıfı giriş filtresi olarak kullanılmaz.

Kalan aynı 24-bar pencere içinde, yeni çizgi kimliği değişmeden fiyatın yeni
çizginin karşı tarafına ilk kapanışı ile çizgi kimliğinin değişmesi yarışır.
İkisi aynı 4s checkpoint'te ise belirsizdir. Güvenli tarafa çizgiye eşit kapanış da dahildir; kesin alt/üst kapanış ayrı sayılır. Başlangıçta ihlal tarafındayken
fiyat önce güvenli tarafa geçerse, aynı çizgi korunurken kalan pencerede tekrar
kırılma/çizgi değişimi de ayrı izlenir. Kalan bar sayısı her epizotta farklıdır;
hiç bar kalmaması ayrıca yazılır.

Bu, bilinen bir native seviyenin **sabit kalma** ölçümüdür. Bir stepline
segmentini kullanıcının grafikte kastettiği kalıcı "yatay" rejime eşitlemez ve
ek teyit/bekleme eklemez. Geçerli n, hisse sayıları, sansür, aynı-bar ve
başlangıç grubu açıkça gösterilir. Oranlar birbirinden bağımsız işlem veya
nedensel kanıt değildir.
