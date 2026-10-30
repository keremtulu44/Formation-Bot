# Kod, Supabase ve Replay incelemesi — 29 Ekim 2026

## Kapsam ve bulgular

Repo, mevcut testler ve bağlı tek Supabase projesi salt okunur incelendi. Canlı
çalıştırma loglarına, Render diskine ve gerçek üretim ortam değişkenlerine erişim
yok; bu nedenle bazı bulguların kök nedeni henüz doğrulanmış değildir.

### Bu değişiklikte düzeltilenler

1. `get_many`: ön ekli sorgu başarılı olsa bile eksik anahtarlar için legacy
   sorgusu başarısızsa sonuç artık kısmi başarı/boş kayıt gibi sunulmaz; `None`
   dönülür ve çağıranın yerel geri dönüş yolu korunur.
2. Gerçek `SupabaseStore`, mirror kuyruğuna HTTP hata yanıtını gizliyordu;
   böylece sadece sahte store ile test edilen zehirli batch ayrımı gerçekte
   işlemiyordu. Mirror'a özel hata yanıtı yolu eklendi; diğer çağıranların
   `None` sözleşmesi değişmedi. 409 ve 404 artık kalıcı veri hatası sayılıp
   beş denemede düşürülmez: FK/ebeveyn sıralaması veya henüz kurulmamış şema
   geçici olabilir. 400/422 için mevcut beş denemede batch düşürme politikası
   devam ediyor; bu politika iyi satırları da etkileyebilir, izleme gerektirir.
3. Hydration sırasında snapshots, events veya outcome okuması başarısız ya da
   geçersizse eksik defter artık yerel dosyaya yazılmaz. Gerçekten boş ve
   başarıyla okunmuş tablolar yine kabul edilir: mevcut API, gerçek boş tablo
   ile geçmişte eksik yazılmış mirror'ı ayırt edemez.

### Canlı Supabase gözlemleri

- Sağlık kontrolünde DB, REST, auth, pooler ve storage sağlıklı; Realtime
  `UNHEALTHY` döndü. Bu botun mevcut REST kullanımına etkisi gösterilmiş değil;
  Dashboard sağlık/loglarıyla yeniden kontrol edilmeli.
- Tüm 13 public tablo RLS etkin ve policy yok. `bot_store`, `f2_*`, `dz_*`
  için anon/authenticated tablo yetkileri kaldırılmış. Buna karşılık
  `ileri_test` ve `gece_raporu` üzerinde bu rollere geniş tablo yetkileri var;
  RLS satır erişimini engellese de tüm PostgreSQL yetkileri RLS kapsamına
  girmez. Ayrıca postgres sahibi olan `v_ileri_test_ozet` görünümünde anon ve
  authenticated SELECT yetkisi var: varsayılan owner-bağlamı temel tablonun
  RLS'ini aşarak özet veriyi açabilir. Repo uygulaması service role kullanıyor,
  fakat başka istemci bulunup bulunmadığı bilinmiyor.
- `scripts/supabase/legacy_permissions_hardening.sql` bu üç nesnenin istemci
  yetkilerini kaldıran, service-role erişimini koruyan işlemdir. **Canlıya
  uygulanmadı**: önce Dashboard'da diğer istemciler ve erişim ihtiyacı gözden
  geçirilmeli; gerekirse yedek/rollback planı alınmalı. Tabloların ve görünümün
  tanımları repo SQL şemasında yok; şema sürümlemesine alınmaları önerilir.
- 135 `bot_store`, 1.307 `f2_formations`, 0 snapshot, 0 event ve 0 outcome
  satırı sayıldı. Bu, mevcut mirror'ın tüm yaşam döngüsünü kurtarabileceğini
  kanıtlamaz. Hatanın bugünkü kesin sebebi kod veya DB sayılarıyla tek başına
  saptanamaz. Render logları, kuyruk dosyası, son deploy sürümü, PostgREST
  hataları incelenmeli; canlı sorguda iki f2 sequence için service_role
  USAGE ve SELECT yetkileri mevcut. Düzeltme deploy edildikten sonra sentetik
  bir zincirle dört tablo birlikte kontrol edilmeli. Tarihsel
  verilerin geri doldurulması ancak yerel defter/backup varsa mümkündür.
- Altı `dz_*` tablosunun tamamı boş: README'deki 708 başarılı seri ve 1.3 GB
  yerel artefakt **Supabase'e yüklendiği anlamına gelmez**. Bilinçli olarak
  yükleme başlatılmadı; `dz_yukleme/` ve izinli anahtarın çalıştıran ortamda
  mevcut olması, kota ve veri kapsamı kontrol edilmesi gerekir. Komutlar ve
  `--bars` ayrımı `DZ_REPLAY_SONUCLARI_2026-10-28.md` §3'te.
- DB migration geçmişinde iki DZ migration'ı var; diğer tabloların kurulum
  geçmişi migration olarak görünmüyor. Şema drift kontrolü ve yeni boş projede
  uçtan uca kurulum testi eklenmeli. PostgREST satır limiti nedeniyle f2
  hydration sayfalama yapmadığında büyük sonuçlar sessizce kesilebilir; ayrıca
  birden fazla tablo okuması atomik snapshot değildir. Anahtarlı sayfalama ve
  tutarlı anlık görüntü/manifest, kurtarma öncesi doğrulama ile ele alınmalı.
- `state:instances` paylaşılan JSON üzerinde read-modify-write yapar; eşzamanlı
  instance'lar birbirini ezebilir. Bu mekanizma kilit değildir. Gerçek
  tekillik gerekiyorsa atomik lease/heartbeat ve süre dolumu kullanılmalı.

## Replay: kartların ötesinde, öncelikli kullanım planı

Replay geçmiş veride koşullu gözlemdir; canlı başarı olasılığı veya yatırım
önerisi değildir. Aynı zone/semboldeki gözlemler bağımsız değil; 2025–26 aralığı,
seçili evren, sıfır hacim/split, terminal ve sansür koşulları sonuçları etkiler.
Soru kapısının puan farkı + n eşiği üretime tek başına istatistiksel kanıt değildir.
Her aday için tetik anında yalnız o ana kadar bilinen alanlar kullanılmalı; zaman
ayrımlı walk-forward, sembol/zaman bloklu güven aralığı, maliyet ve ileri test
ile doğrulanmadan canlı karar, stop veya puan değişmemeli.

1. **Ölçüm/karne doğruluğu (P0):** S07–S09'da terminal anı, terminal sonrası
   hedef ve aynı bar belirsizliğini ayrı paydalarda raporla; S32 kirli pencereyi
   ayrıca say. Önce mevcut `karne.py` ve `research` etiketleriyle birebir
   tanım eşleştir; S08 yüzdelerini toplam tüm temasların oranı gibi sunma.
   Çıktı: sansür, kirli veri ve belirsizlik dahil denetlenebilir karne.
2. **Gölge alarm önceliklendirmesi (P1):** S04 temas süresi, S10 OB efor-sonuç
   ve S11 baskı uyumunu yalnız causal as-of alanlarla gölgede puanla; geçmişteki
   etiketleri karar anına taşımama özellikle kontrol edilmeli. Mevcut ve gölge
   sıralamayı alarm sayısı, tekrar, kaçan olumlu örnek ve gecikmeyle karşılaştır;
   kullanıcıya gitmesin. S10'daki FVG sonucu RED, FVG'ye genelleme yapma.
3. **Bildirim gürültüsü deneyi (P1):** S15 OB tekrar ziyaretini zone kimliği
   bazlı deduplikasyon için hipotez olarak kullan; FVG/no1 RED. Tekrarın kendisi
   gelecek bilgisi olduğundan önceden biliniyormuş gibi kullanma. Susturulan
   uyarıları kaydet, kaçırılan olayları karşılaştır; başlangıçta shadow-only.
4. **Risk/performans laboratuvarı (P2):** S05 ters hareket dağılımı, S06
   10/12 bar, S31 semboller arası farklılıkla ayrı stop/hedef/ufuk senaryoları
   üret; OHLC içinde hedef-stop sırası belirsizse iyimser varsayma, aralık raporla.
   S05 yalnız CALISTI alt kümesine koşullu: bunu bütün sinyallerin stop
   dağılımı sayma. S06 zone ve S30 formasyon ölçümüdür; birini diğerine taşıma.
5. **Motor regresyon kapısı (P1):** sabit veri/hash + motor/config sürümüyle
   eski/yeni sürümün zone, olay, bar kapanışı ve sansür farklarını CI'da küçük
   deterministik örnek üzerinde karşılaştır. Büyük koşuyu ayrıca zamanlanmış
   offline iş olarak işlet; yeni arşiv ve sembollerle out-of-sample rapor üret.
   S27'de 6+ susturma ve S24'te kontra sinyal reddedilmiş: yeniden icat etme.
6. **Veri kalitesi ve rejim paneli (P1):** S14 hacim kullanılamayan ve S32
   kirli pencereleri sembol/TF/kaynak bazında izle; S31 dağılımını tek bir
   küresel yüzde yerine n ve belirsizlikle göster. `UNKNOWN`/ölçülemedi ayrı
   kalsın. 1h FVG yokluğu ve internal/external ayrımını raporlarda koru.

### Deney kapısı önerisi

Ön kayıt: hipotez, karar zamanı, evren, ölçüt, maliyet, minimum örnek, kabul
kriteri ve iptal koşulu; ardından zaman + sembol dışı doğrulama ve shadow dönemi.
Veri sızıntısı/boş hücre/sansür, örnek bağımlılığı ve çoklu karşılaştırma açıkça
raporlansın. Etki istikrarlı değilse yalnız araştırma çıktısı olarak kalsın;
canlıya geçiş ayrı bir onay ve geri alma mekanizması gerektirir.
